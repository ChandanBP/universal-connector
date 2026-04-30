"""
UNIVERSAL CONNECTOR — Matching Engine
Domain-agnostic: all domain knowledge comes from DomainConfig.

Displacement score = (intent_score × α) + (trust_score × β)
  α > β always — intent is the primary signal.
  α/β adjusts dynamically based on trust graph density.

Trust signal has five layers, tried in order:
  1. direct_trust   — 1-hop: someone the user directly trusts has visited
  2. network_trust  — 2-N hop recursive traversal through real trust edges
  3. domain_expert  — high trust_received node, not in personal network
  4. crowd_wisdom   — avg outcome across all users, no personal connection
  5. intent_only    — no outcome data at all, pure intent match

Granularity additions:
  A. Intent-contextualized trust — trust score is discounted when the
     trusted person's past visit context doesn't match the current intent.
     (e.g. your friend went for a casual lunch; you need a business dinner)

  B. User taste profile — scoring weights are personalized per user from
     their past positive outcome history. Users who consistently search
     by vibe get higher vibe weight; cuisine-obsessed users get higher
     cuisine weight. Falls back to domain defaults with sparse history.

Usage:
  from engine.domains import get_domain
  from engine.matcher import match

  config  = get_domain('restaurants')
  results = match(intent, user_id, conn, config)
"""

import os
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

from engine.domains.base import DomainConfig, FieldDefinition, IntentObject


# ── SIGNAL LAYERS ─────────────────────────────────────────────────────────────
# Score caps enforce the trust hierarchy even when lower layers have strong data.

SIGNAL_LAYERS = {
    'direct_trust':   0.95,
    'network_trust':  0.75,
    'domain_expert':  0.55,
    'crowd_wisdom':   0.35,
    'intent_only':    0.00,
}

# Minimum interaction history before personalized weights are applied.
_MIN_INTERACTIONS_FOR_PROFILE = 5


# ── DATA STRUCTURES ───────────────────────────────────────────────────────────

@dataclass
class TrustSignal:
    signal_layer:       str             # one of SIGNAL_LAYERS keys
    trusted_user_id:    Optional[str]   # None for crowd_wisdom / intent_only
    trusted_user_name:  Optional[str]
    edge_weight:        float
    hops:               int
    outcome:            Optional[str]
    visited_at:         Optional[str]
    path_count:         int  = 1        # convergence: paths found (network_trust)
    interaction_intent: Optional[dict] = None  # intent_parsed from the interaction


@dataclass
class MatchResult:
    source_id:          str
    name:               str
    domain:             str
    attributes:         dict            # all domain-specific source fields
    avg_outcome_score:  float

    intent_score:       float
    trust_score:        float
    displacement_score: float

    signal:             TrustSignal
    signal_layer:       str             # copy of signal.signal_layer for quick access
    explanation:        dict = field(default_factory=dict)


# ── DATABASE ──────────────────────────────────────────────────────────────────

def get_conn():
    try:
        import psycopg2
        return psycopg2.connect(os.getenv("DATABASE_URL"))
    except ImportError:
        raise ImportError("Run: pip install psycopg2-binary")
    except Exception as e:
        raise ConnectionError(f"Database connection failed: {e}")


# ── STEP 1: FILTER — hard constraint elimination ──────────────────────────────

def filter_candidates(cur, intent: IntentObject, domain_config: DomainConfig) -> list:
    """
    Eliminate sources that violate hard constraints.
    Table/column names come from DomainConfig (trusted code, never user input).
    Values are always passed as SQL params.
    """
    hard = intent.hard_constraints()
    filter_clauses = []
    params = []

    for fd in domain_config.filterable_fields():
        if fd.name not in hard:
            continue
        value = hard[fd.name]

        if fd.filter_type == 'exact':
            filter_clauses.append(f"AND {fd.db_column} = %s")
            params.append(value)
        elif fd.filter_type == 'array_overlap':
            filter_clauses.append(f"AND {fd.db_column} && %s::text[]")
            params.append(value)
        elif fd.filter_type == 'boolean' and value is True:
            filter_clauses.append(f"AND {fd.db_column} = true")

    cols = ', '.join(domain_config.select_columns)
    sql = f"""
        SELECT {cols}
        FROM {domain_config.source_table}
        WHERE active = true
        {' '.join(filter_clauses)}
        LIMIT 100
    """

    cur.execute(sql, params)
    rows = cur.fetchall()
    return [dict(zip(domain_config.select_columns, row)) for row in rows]


def _relax_hard_constraints(intent: IntentObject, domain_config: DomainConfig) -> IntentObject:
    """Fallback: demote relaxable hard constraints to soft on zero results."""
    relaxed = deepcopy(intent)
    for fd in domain_config.relaxable_fields():
        f = relaxed.fields.get(fd.name)
        if f and f.constraint == 'hard':
            f.constraint = 'soft'
    return relaxed


# ── STEP 2: INTENT MATCH SCORING (with taste profile) ────────────────────────

def _score_field(intent_value, source_value, fd: FieldDefinition, constraint: str) -> float:
    if source_value is None:
        return 0.1

    if fd.field_type == 'list':
        if not isinstance(intent_value, list) or not isinstance(source_value, list):
            return 0.0
        if fd.similarity_map:
            scores = []
            for iv in intent_value:
                sim = fd.similarity_map.get(iv, {iv: 1.0})
                best = max((sim.get(sv, 0.0) for sv in source_value), default=0.1)
                scores.append(best)
            return sum(scores) / len(scores) if scores else 0.1
        else:
            overlap = len(set(intent_value) & set(source_value))
            return min(1.0, overlap / len(intent_value))

    elif fd.field_type == 'string':
        if source_value == intent_value:
            return 1.0
        return 0.3 if constraint == 'soft' else 0.0

    elif fd.field_type == 'boolean':
        return 1.0 if source_value == intent_value else 0.3

    return 0.0


def load_user_taste_profile(
    cur,
    user_id:       str,
    domain_config: DomainConfig,
) -> dict[str, float]:
    """
    Derive personalized field weights from the user's past positive outcomes.
    Returns {field_name: normalized_weight}.

    Strategy:
      - Scan recent positive interactions, look at which intent fields were
        specified and whether they were hard (counts double) or soft.
      - Blend frequency signal with domain defaults (50/50).
      - Normalize so weights sum to 1.0.

    Falls back to domain defaults when history is too sparse.
    """
    domain_defaults = {fd.name: fd.score_weight for fd in domain_config.scored_fields()}

    cur.execute("""
        SELECT intent_parsed
        FROM interactions
        WHERE user_id = %s
          AND outcome = 'positive'
          AND intent_parsed IS NOT NULL
        ORDER BY visited_at DESC
        LIMIT 20
    """, (user_id,))
    rows = cur.fetchall()

    if len(rows) < _MIN_INTERACTIONS_FOR_PROFILE:
        return domain_defaults

    field_counts: dict[str, float] = {fd.name: 0.0 for fd in domain_config.scored_fields()}

    for (intent_json,) in rows:
        if not intent_json or 'fields' not in intent_json:
            continue
        past_fields = intent_json['fields']
        for fd in domain_config.scored_fields():
            fdata = past_fields.get(fd.name, {})
            value = fdata.get('value')
            if not value or value in [[], '', None]:
                continue
            # Hard constraint signals stronger preference than soft
            weight = 2.0 if fdata.get('constraint') == 'hard' else 1.0
            field_counts[fd.name] += weight

    total = sum(field_counts.values())
    if total == 0:
        return domain_defaults

    # Blend: 50% from user frequency signal, 50% from domain defaults
    personalized = {}
    for fd in domain_config.scored_fields():
        freq_weight = field_counts[fd.name] / total
        personalized[fd.name] = round(0.5 * freq_weight + 0.5 * domain_defaults[fd.name], 4)

    # Normalize to sum to 1.0
    weight_sum = sum(personalized.values())
    if weight_sum > 0:
        personalized = {k: round(v / weight_sum, 4) for k, v in personalized.items()}

    return personalized


def score_intent(
    source:        dict,
    intent:        IntentObject,
    domain_config: DomainConfig,
    taste_profile: Optional[dict] = None,   # {field_name: weight} — personalized
) -> tuple[float, dict]:
    """
    Score how well a source matches the intent.
    Uses personalized weights from taste_profile when available,
    falls back to domain defaults per field.

    Returns (score 0.0–1.0, per-field breakdown for transparency layer).
    """
    breakdown = {}
    total_score = 0.0
    total_weight = 0.0

    for fd in domain_config.scored_fields():
        intent_field = intent.fields.get(fd.name)
        if not intent_field or intent_field.value in [None, [], '']:
            continue

        source_value = source.get(fd.db_column)
        score = _score_field(intent_field.value, source_value, fd, intent_field.constraint)

        # Use personalized weight if available, else domain default
        weight = taste_profile.get(fd.name, fd.score_weight) if taste_profile else fd.score_weight

        breakdown[fd.name] = round(score, 2)
        total_score  += score * weight
        total_weight += weight

    final_score = (total_score / total_weight) if total_weight > 0 else 0.5

    if intent.ambiguity_score > 0.7:
        final_score = max(final_score, 0.4)

    return round(final_score, 3), breakdown


# ── STEP 3: LAYERED TRUST SIGNAL ─────────────────────────────────────────────
# Tried in order. Always returns a TrustSignal — never None.

_DIRECT_TRUST_SQL = """
    SELECT
        te.to_user_id,
        u.name          AS trusted_user_name,
        te.weight       AS edge_weight,
        i.outcome,
        i.visited_at,
        i.intent_parsed
    FROM trust_edges te
    JOIN users u ON u.id = te.to_user_id
    JOIN interactions i
        ON  i.user_id = te.to_user_id
        AND i.{source_fk} = %s
    WHERE te.from_user_id = %s
      AND te.status       = 'active'
      AND te.domain       = %s
      AND i.outcome IN ('positive', 'neutral')
    ORDER BY te.weight DESC, i.visited_at DESC
    LIMIT 1
"""

_NETWORK_TRUST_SQL = """
    WITH RECURSIVE trust_paths AS (
        SELECT
            te.to_user_id                  AS reached_user,
            te.weight                      AS avg_weight,
            1                              AS hops,
            ARRAY[te.to_user_id]::uuid[]   AS visited
        FROM trust_edges te
        WHERE te.from_user_id = %s
          AND te.status = 'active'
          AND te.domain = %s

        UNION ALL

        SELECT
            te.to_user_id,
            (tp.avg_weight + te.weight) / 2,
            tp.hops + 1,
            tp.visited || te.to_user_id
        FROM trust_paths tp
        JOIN trust_edges te ON te.from_user_id = tp.reached_user
        WHERE tp.hops < %s
          AND te.status = 'active'
          AND te.domain = %s
          AND NOT te.to_user_id = ANY(tp.visited)
    )
    SELECT
        tp.reached_user,
        u.name,
        ROUND(
            (tp.avg_weight * POWER(0.85::float, tp.hops - 1))::numeric, 3
        )                   AS path_score,
        tp.hops,
        i.outcome,
        i.visited_at,
        i.intent_parsed
    FROM trust_paths tp
    JOIN users u ON u.id = tp.reached_user
    JOIN interactions i
        ON  i.user_id = tp.reached_user
        AND i.{source_fk} = %s
    WHERE i.outcome IN ('positive', 'neutral')
      AND tp.hops >= 2
    ORDER BY path_score DESC
    LIMIT 3
"""

_DOMAIN_EXPERT_SQL = """
    SELECT
        u.id,
        u.name,
        i.outcome,
        i.visited_at
    FROM users u
    JOIN interactions i
        ON  i.user_id = u.id
        AND i.{source_fk} = %s
    WHERE u.id != %s
      AND u.{trust_col} >= 0.6
      AND i.outcome IN ('positive', 'neutral')
    ORDER BY u.{trust_col} DESC, i.visited_at DESC
    LIMIT 1
"""


def find_best_trust_signal(
    cur,
    user_id:           str,
    source_id:         str,
    domain_config:     DomainConfig,
    avg_outcome_score: float,
) -> TrustSignal:
    """
    Find the best available trust signal for (user, source).
    Tries all five layers in order, returns the first hit.
    Always returns a TrustSignal — never raises or returns None.
    """
    fk  = domain_config.source_fk_column
    col = domain_config.trust_received_column

    # ── Layer 1: Direct trust (1 hop) ────────────────────────────────────────
    cur.execute(_DIRECT_TRUST_SQL.format(source_fk=fk),
                (source_id, user_id, domain_config.domain))
    row = cur.fetchone()
    if row:
        return TrustSignal(
            signal_layer='direct_trust',
            trusted_user_id=row[0],
            trusted_user_name=row[1],
            edge_weight=float(row[2]),
            hops=1,
            outcome=row[3],
            visited_at=str(row[4]) if row[4] else None,
            interaction_intent=row[5],  # dict or None
        )

    # ── Layer 2: Multi-hop network traversal ─────────────────────────────────
    cur.execute(
        _NETWORK_TRUST_SQL.format(source_fk=fk),
        (user_id, domain_config.domain,
         domain_config.max_trust_hops, domain_config.domain,
         source_id),
    )
    rows = cur.fetchall()
    if rows:
        best = rows[0]
        return TrustSignal(
            signal_layer='network_trust',
            trusted_user_id=best[0],
            trusted_user_name=best[1],
            edge_weight=float(best[2]),
            hops=best[3],
            outcome=best[4],
            visited_at=str(best[5]) if best[5] else None,
            path_count=len(rows),
            interaction_intent=best[6],
        )

    # ── Layer 3: Domain expert (outside personal network) ────────────────────
    cur.execute(_DOMAIN_EXPERT_SQL.format(source_fk=fk, trust_col=col),
                (source_id, user_id))
    row = cur.fetchone()
    if row:
        return TrustSignal(
            signal_layer='domain_expert',
            trusted_user_id=row[0],
            trusted_user_name=row[1],
            edge_weight=0.55,
            hops=0,
            outcome=row[2],
            visited_at=str(row[3]) if row[3] else None,
        )

    # ── Layer 4: Crowd wisdom ─────────────────────────────────────────────────
    if avg_outcome_score > 0.0:
        return TrustSignal(
            signal_layer='crowd_wisdom',
            trusted_user_id=None,
            trusted_user_name=None,
            edge_weight=avg_outcome_score,
            hops=0,
            outcome='positive' if avg_outcome_score >= 0.5 else 'neutral',
            visited_at=None,
        )

    # ── Layer 5: Intent only ──────────────────────────────────────────────────
    return TrustSignal(
        signal_layer='intent_only',
        trusted_user_id=None,
        trusted_user_name=None,
        edge_weight=0.0,
        hops=0,
        outcome=None,
        visited_at=None,
    )


# ── STEP 4A: INTENT SIMILARITY (granularity A) ────────────────────────────────

def compute_intent_similarity(
    current_intent: IntentObject,
    past_intent:    Optional[dict],
    domain_config:  DomainConfig,
) -> float:
    """
    Compare the current search intent against the intent stored in a past
    interaction. Returns a multiplier in [0.2, 1.0].

    1.0 = contexts match well (business dinner → business dinner)
    0.5 = partial overlap
    0.2 = no overlap (minimum floor — recommendation still has inherent value)

    Only applies to direct_trust and network_trust layers where a specific
    interaction can be compared. All other layers return 1.0.
    """
    if not past_intent or 'fields' not in past_intent:
        return 1.0   # no stored context → no discount

    past_fields = past_intent['fields']
    total_score  = 0.0
    total_weight = 0.0

    for fd in domain_config.scored_fields():
        current_field = current_intent.fields.get(fd.name)
        if not current_field or current_field.value in [None, [], '']:
            continue   # field not in current intent → skip

        past_field = past_fields.get(fd.name, {})
        past_value = past_field.get('value')

        if not past_value or past_value in [[], '', None]:
            # Past visit didn't specify this field — neutral (no boost, no penalty)
            score = 0.5
        else:
            score = _score_field(current_field.value, past_value, fd, 'soft')

        total_score  += score * fd.score_weight
        total_weight += fd.score_weight

    if total_weight == 0:
        return 1.0

    similarity = total_score / total_weight
    return round(max(0.2, similarity), 3)


# ── STEP 4B: TRUST SIGNAL SCORING ────────────────────────────────────────────

_OUTCOME_SCORES = {
    'positive':  0.8,
    'neutral':   0.1,
    'negative': -0.6,
    'regret':   -0.3,
}


def score_trust_signal(
    signal:           TrustSignal,
    intent_similarity: float = 1.0,
) -> float:
    """
    Score a TrustSignal, discounted by intent_similarity.

    direct_trust / network_trust / domain_expert:
        raw = (edge_weight × 0.50) + (outcome × 0.30) + (recency × 0.20)
        network_trust gets convergence bonus (+0.05 per extra path, max +0.10)
        then: raw × intent_similarity

    crowd_wisdom:
        raw = edge_weight × 0.50  (edge_weight IS avg_outcome_score)
        no intent_similarity discount (crowd signal has no specific context)

    intent_only: 0.0
    """
    layer = signal.signal_layer
    cap   = SIGNAL_LAYERS[layer]

    if layer == 'intent_only':
        return 0.0

    if layer == 'crowd_wisdom':
        return round(min(cap, max(0.0, signal.edge_weight * 0.50)), 3)

    # direct_trust, network_trust, domain_expert
    edge_component    = signal.edge_weight * 0.50
    outcome_component = _OUTCOME_SCORES.get(signal.outcome, 0.0) * 0.30

    if signal.visited_at:
        visited = datetime.fromisoformat(signal.visited_at)
        if visited.tzinfo is None:
            visited = visited.replace(tzinfo=timezone.utc)
        recency_days = (datetime.now(timezone.utc) - visited).days
    else:
        recency_days = 180

    recency_component = max(0.0, 1.0 - recency_days / 180.0) * 0.20
    raw = edge_component + outcome_component + recency_component

    if layer == 'network_trust' and signal.path_count > 1:
        raw += min(0.10, (signal.path_count - 1) * 0.05)

    # Apply intent similarity discount for personal layers
    raw *= intent_similarity

    return round(min(cap, max(0.0, raw)), 3)


# ── STEP 5: DISPLACEMENT SCORING ─────────────────────────────────────────────

def get_trust_graph_density(cur, user_id: str, domain: str) -> float:
    cur.execute("""
        SELECT COUNT(*) FROM trust_edges
        WHERE from_user_id = %s AND status = 'active' AND domain = %s
    """, (user_id, domain))
    return min(1.0, cur.fetchone()[0] / 10.0)


def compute_alpha_beta(density: float) -> tuple[float, float]:
    if density < 0.3:
        alpha = 0.85
    elif density < 0.7:
        alpha = 0.70
    else:
        alpha = 0.55
    return alpha, round(1.0 - alpha, 2)


def compute_displacement_score(
    intent_score: float,
    trust_score:  float,
    alpha:        float,
    beta:         float,
) -> float:
    return round((intent_score * alpha) + (trust_score * beta), 3)


# ── STEP 6: EXPLANATION ───────────────────────────────────────────────────────

def _layer_summary(signal: TrustSignal) -> str:
    layer = signal.signal_layer
    if layer == 'direct_trust':
        return f"{signal.trusted_user_name} visited and rated it {signal.outcome}"
    if layer == 'network_trust':
        base = f"{signal.trusted_user_name} ({signal.hops} hops away) rated it {signal.outcome}"
        return base + (f" · {signal.path_count} in your network agree" if signal.path_count > 1 else "")
    if layer == 'domain_expert':
        return f"{signal.trusted_user_name} is a trusted voice in this domain"
    if layer == 'crowd_wisdom':
        return "Rated positively by the broader community"
    return "No outcome data yet — matches your description only"


def build_explanation(
    intent_score:       float,
    intent_breakdown:   dict,
    signal:             TrustSignal,
    trust_score:        float,
    intent_similarity:  float,
    alpha:              float,
    beta:               float,
    displacement:       float,
    taste_profile:      Optional[dict],
    is_personalized:    bool,
) -> dict:
    return {
        "displacement_score": displacement,
        "intent_layer": {
            "score":        intent_score,
            "weight":       alpha,
            "summary":      f"{round(intent_score * 100)}% matches your description",
            "breakdown":    intent_breakdown,
            "personalized": is_personalized,
            "taste_weights": taste_profile if is_personalized else None,
        },
        "trust_layer": {
            "score":              trust_score,
            "weight":             beta,
            "signal_layer":       signal.signal_layer,
            "trusted_person":     signal.trusted_user_name,
            "edge_weight":        signal.edge_weight,
            "hops":               signal.hops,
            "their_outcome":      signal.outcome,
            "visited_at":         signal.visited_at,
            "path_count":         signal.path_count,
            "intent_similarity":  intent_similarity,
            "summary":            _layer_summary(signal),
        },
    }


# ── MAIN MATCH FUNCTION ───────────────────────────────────────────────────────

def match(
    intent:        IntentObject,
    user_id:       str,
    conn,
    domain_config: DomainConfig,
    top_k:         int = 5,
) -> list[MatchResult]:
    """
    Core displacement matching function.

    Args:
        intent:        IntentObject from parse_intent()
        user_id:       UUID of the searching user
        conn:          Postgres connection (created if None)
        domain_config: Domain configuration
        top_k:         Results to return

    Returns:
        List of MatchResult sorted by displacement_score descending
    """
    should_close = conn is None
    if should_close:
        conn = get_conn()
    cur = conn.cursor()

    try:
        density     = get_trust_graph_density(cur, user_id, domain_config.domain)
        alpha, beta = compute_alpha_beta(density)

        # Load personalized weights once per search, not per source
        taste_profile   = load_user_taste_profile(cur, user_id, domain_config)
        domain_defaults = {fd.name: fd.score_weight for fd in domain_config.scored_fields()}
        is_personalized = taste_profile != domain_defaults

        candidates = filter_candidates(cur, intent, domain_config)
        if not candidates:
            candidates = filter_candidates(
                cur, _relax_hard_constraints(intent, domain_config), domain_config
            )

        results = []
        for source in candidates:
            sid               = source["id"]
            avg_outcome_score = float(source.get("avg_outcome_score") or 0)

            intent_score, intent_breakdown = score_intent(
                source, intent, domain_config, taste_profile
            )
            signal = find_best_trust_signal(
                cur, user_id, sid, domain_config, avg_outcome_score
            )

            # Intent similarity only meaningful for personal layers
            intent_similarity = (
                compute_intent_similarity(
                    intent, signal.interaction_intent, domain_config
                )
                if signal.signal_layer in ('direct_trust', 'network_trust')
                else 1.0
            )

            trust_score  = score_trust_signal(signal, intent_similarity)
            displacement = compute_displacement_score(intent_score, trust_score, alpha, beta)
            explanation  = build_explanation(
                intent_score, intent_breakdown,
                signal, trust_score, intent_similarity,
                alpha, beta, displacement,
                taste_profile, is_personalized,
            )

            attributes = {
                k: v for k, v in source.items()
                if k not in ('id', 'avg_outcome_score', 'total_visits', 'trust_citations')
            }

            results.append(MatchResult(
                source_id=sid,
                name=source["name"],
                domain=domain_config.domain,
                attributes=attributes,
                avg_outcome_score=avg_outcome_score,
                intent_score=intent_score,
                trust_score=trust_score,
                displacement_score=displacement,
                signal=signal,
                signal_layer=signal.signal_layer,
                explanation=explanation,
            ))

        results.sort(key=lambda r: r.displacement_score, reverse=True)

        # Tie-break: higher signal layer wins
        _layer_rank = {k: i for i, k in enumerate(SIGNAL_LAYERS)}
        for i in range(len(results) - 1):
            r1, r2 = results[i], results[i + 1]
            if (r1.displacement_score == r2.displacement_score and
                    _layer_rank.get(r2.signal_layer, 99) < _layer_rank.get(r1.signal_layer, 99)):
                results[i], results[i + 1] = r2, r1

        return results[:top_k]

    finally:
        cur.close()
        if should_close:
            conn.close()


# ── TEST ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))

    from engine.domains import get_domain
    from engine.intent_parser import parse_intent

    config = get_domain('restaurants')
    conn   = get_conn()

    cur = conn.cursor()
    cur.execute("""
        SELECT u.id, u.name, COUNT(te.id) AS edge_count
        FROM users u
        LEFT JOIN trust_edges te
            ON te.from_user_id = u.id AND te.status = 'active'
        WHERE u.cold_start_flag = false
        GROUP BY u.id, u.name
        ORDER BY edge_count DESC
        LIMIT 1
    """)
    row = cur.fetchone()
    user_id, user_name, edge_count = row
    cur.close()

    print(f"\nUniversal Connector — Matching Engine Test")
    print(f"Domain   : {config.domain}  |  Max hops: {config.max_trust_hops}")
    print(f"User     : {user_name}  ({edge_count} trust edges)")
    print("=" * 60)

    TEST_QUERIES = [
        "I want a quiet place for a business dinner, good North Indian, Indiranagar, not too loud, parking available",
        "Casual dinner with friends in Koramangala, something lively",
        "Something nice for tonight",
    ]

    for query in TEST_QUERIES:
        print(f"\n{'─' * 60}")
        print(f"Query: \"{query}\"")
        try:
            intent  = parse_intent(query, config)
            results = match(intent, user_id, conn, config)

            print(f"Hard  : {intent.hard_constraints()}")
            print(f"Soft  : {intent.soft_constraints()}")
            print(f"\nTop {len(results)} results:")
            for i, r in enumerate(results, 1):
                tl = r.explanation.get("trust_layer", {})
                il = r.explanation.get("intent_layer", {})
                print(f"  [{i}] {r.name}")
                print(f"       disp={r.displacement_score}  "
                      f"intent={r.intent_score}  trust={r.trust_score}")
                print(f"       layer={r.signal_layer}  "
                      f"paths={r.signal.path_count}  "
                      f"hops={r.signal.hops}  "
                      f"intent_sim={tl.get('intent_similarity', 1.0)}")
                print(f"       personalized={il.get('personalized', False)}")
        except Exception as e:
            import traceback
            print(f"ERROR: {e}")
            traceback.print_exc()

    conn.close()
    print("\nDone.\n")
