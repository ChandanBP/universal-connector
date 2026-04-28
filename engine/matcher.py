"""
UNIVERSAL CONNECTOR — Matching Engine
Domain-agnostic: all domain knowledge comes from DomainConfig.

Displacement score = (intent_score × α) + (trust_path_score × β)
  α > β always — intent is the primary signal.
  α/β adjusts dynamically based on trust graph density for this user.

Usage:
  from engine.domains import get_domain
  from engine.matcher import match

  config = get_domain('restaurants')
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


# ── DATA STRUCTURES ───────────────────────────────────────────────────────────

@dataclass
class TrustPath:
    trusted_user_id:   str
    trusted_user_name: str
    edge_weight:       float
    hops:              int
    outcome:           Optional[str]
    visited_at:        Optional[str]


@dataclass
class MatchResult:
    source_id:          str
    name:               str
    domain:             str
    attributes:         dict    # all domain-specific source fields
    avg_outcome_score:  float

    intent_score:       float
    trust_path_score:   float
    displacement_score: float

    trust_path:         Optional[TrustPath]
    is_cold_result:     bool
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
    Table/column names come from DomainConfig (trusted code, not user input).
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


# ── STEP 2: INTENT MATCH SCORING ─────────────────────────────────────────────

def _score_field(intent_value, source_value, fd: FieldDefinition, constraint: str) -> float:
    """Score a single field match. Returns 0.0–1.0."""
    if source_value is None:
        return 0.1   # missing data, not a hard zero

    if fd.field_type == 'list':
        if not isinstance(intent_value, list) or not isinstance(source_value, list):
            return 0.0
        if fd.similarity_map:
            # Fuzzy match: each intent value looks up its similarity map
            scores = []
            for iv in intent_value:
                sim = fd.similarity_map.get(iv, {iv: 1.0})
                best = max((sim.get(sv, 0.0) for sv in source_value), default=0.1)
                scores.append(best)
            return sum(scores) / len(scores) if scores else 0.1
        else:
            # Exact overlap
            overlap = len(set(intent_value) & set(source_value))
            return min(1.0, overlap / len(intent_value))

    elif fd.field_type == 'string':
        if source_value == intent_value:
            return 1.0
        # Soft miss gets partial credit (still a reasonable choice)
        return 0.3 if constraint == 'soft' else 0.0

    elif fd.field_type == 'boolean':
        return 1.0 if source_value == intent_value else 0.3

    return 0.0


def score_intent(
    source: dict,
    intent: IntentObject,
    domain_config: DomainConfig,
) -> tuple[float, dict]:
    """
    Score how well a source matches the intent.
    Returns (score 0.0–1.0, per-field breakdown for the explanation layer).
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

        breakdown[fd.name] = round(score, 2)
        total_score  += score * fd.score_weight
        total_weight += fd.score_weight

    final_score = (total_score / total_weight) if total_weight > 0 else 0.5

    if intent.ambiguity_score > 0.7:
        final_score = max(final_score, 0.4)  # floor for vague queries

    return round(final_score, 3), breakdown


# ── STEP 3: TRUST PATH QUERY ──────────────────────────────────────────────────
# Table/column names interpolated from DomainConfig — never from user input.

_DIRECT_TRUST_SQL = """
    SELECT
        te.to_user_id,
        u.name       AS trusted_user_name,
        te.weight    AS edge_weight,
        i.outcome,
        i.visited_at,
        1            AS hops
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

_HUB_NODE_SQL = """
    SELECT
        u.id,
        u.name       AS trusted_user_name,
        0.6          AS edge_weight,
        i.outcome,
        i.visited_at,
        2            AS hops
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


def find_trust_path(
    cur,
    user_id:       str,
    source_id:     str,
    domain_config: DomainConfig,
) -> Optional[TrustPath]:
    """
    Find the best trust path from user to a source.
      1. Direct trust (1 hop) — someone the user trusts has been here
      2. Hub node fallback (2 hops) — a domain expert with high trust_received
    Returns None if neither exists (true cold result).
    """
    fk  = domain_config.source_fk_column
    col = domain_config.trust_received_column

    cur.execute(_DIRECT_TRUST_SQL.format(source_fk=fk),
                (source_id, user_id, domain_config.domain))
    row = cur.fetchone()
    if row:
        return TrustPath(
            trusted_user_id=row[0], trusted_user_name=row[1],
            edge_weight=float(row[2]), hops=row[5],
            outcome=row[3], visited_at=str(row[4]) if row[4] else None,
        )

    cur.execute(_HUB_NODE_SQL.format(source_fk=fk, trust_col=col),
                (source_id, user_id))
    row = cur.fetchone()
    if row:
        return TrustPath(
            trusted_user_id=row[0], trusted_user_name=row[1],
            edge_weight=float(row[2]), hops=row[5],
            outcome=row[3], visited_at=str(row[4]) if row[4] else None,
        )

    return None


# ── STEP 4: TRUST PATH SCORING ────────────────────────────────────────────────

_OUTCOME_SCORES = {
    'positive': 0.8,
    'neutral':  0.1,
    'negative': -0.6,
    'regret':   -0.3,
}


def score_trust_path(trust_path: Optional[TrustPath]) -> float:
    """
    Additive trust path score (not multiplicative — avoids score collapse).

    Formula:
        score = (edge_weight × 0.50)
              + (outcome_score × 0.30)
              + (recency_score × 0.20)
              - hop_discount

    hop_discount: 1 hop = 0.00, 2+ hops = 0.15
    Capped at 0.95 — hub nodes never beat direct trust + perfect intent.
    """
    if trust_path is None:
        return 0.0

    edge_component    = trust_path.edge_weight * 0.50
    outcome_component = _OUTCOME_SCORES.get(trust_path.outcome, 0.0) * 0.30

    if trust_path.visited_at:
        visited = datetime.fromisoformat(trust_path.visited_at)
        if visited.tzinfo is None:
            visited = visited.replace(tzinfo=timezone.utc)
        recency_days = (datetime.now(timezone.utc) - visited).days
    else:
        recency_days = 180   # unknown recency treated as old

    recency_component = max(0.0, 1.0 - recency_days / 180.0) * 0.20
    hop_discount      = 0.00 if trust_path.hops == 1 else 0.15

    return round(min(0.95, max(0.0,
        edge_component + outcome_component + recency_component - hop_discount
    )), 3)


# ── STEP 5: DISPLACEMENT SCORING ─────────────────────────────────────────────

def get_trust_graph_density(cur, user_id: str, domain: str) -> float:
    """0.0 = no edges (cold start), 1.0 = dense graph (10+ edges)."""
    cur.execute("""
        SELECT COUNT(*) FROM trust_edges
        WHERE from_user_id = %s AND status = 'active' AND domain = %s
    """, (user_id, domain))
    return min(1.0, cur.fetchone()[0] / 10.0)


def compute_alpha_beta(density: float) -> tuple[float, float]:
    """
    Dynamic α/β weighting — intent always dominates (α > β).
    Sparse (new user): α=0.85, β=0.15
    Medium:            α=0.70, β=0.30
    Dense:             α=0.55, β=0.45
    """
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

def build_explanation(
    intent_score:     float,
    intent_breakdown: dict,
    trust_path:       Optional[TrustPath],
    trust_score:      float,
    alpha:            float,
    beta:             float,
    displacement:     float,
) -> dict:
    explanation = {
        "displacement_score": displacement,
        "intent_layer": {
            "score":     intent_score,
            "weight":    alpha,
            "summary":   f"{round(intent_score * 100)}% matches your description",
            "breakdown": intent_breakdown,
        },
        "cold_result": trust_path is None,
    }

    if trust_path:
        is_hub = trust_path.hops >= 2
        explanation["trust_layer"] = {
            "score":          trust_score,
            "weight":         beta,
            "trusted_person": trust_path.trusted_user_name,
            "edge_weight":    trust_path.edge_weight,
            "hops":           trust_path.hops,
            "their_outcome":  trust_path.outcome or "neutral",
            "visited_at":     trust_path.visited_at,
            "is_hub_node":    is_hub,
            "summary": (
                f"{trust_path.trusted_user_name}"
                f"{' (domain expert)' if is_hub else ''} "
                f"visited and rated it {trust_path.outcome or 'neutral'}"
            ),
        }
    else:
        explanation["trust_layer"] = {
            "score":   0.0,
            "summary": "No one in your trust network has been here yet",
        }

    return explanation


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
        density      = get_trust_graph_density(cur, user_id, domain_config.domain)
        alpha, beta  = compute_alpha_beta(density)

        candidates = filter_candidates(cur, intent, domain_config)
        if not candidates:
            candidates = filter_candidates(
                cur, _relax_hard_constraints(intent, domain_config), domain_config
            )

        results = []
        for source in candidates:
            sid = source["id"]

            intent_score, intent_breakdown = score_intent(source, intent, domain_config)
            trust_path   = find_trust_path(cur, user_id, sid, domain_config)
            trust_score  = score_trust_path(trust_path)
            displacement = compute_displacement_score(intent_score, trust_score, alpha, beta)
            explanation  = build_explanation(
                intent_score, intent_breakdown,
                trust_path, trust_score,
                alpha, beta, displacement,
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
                avg_outcome_score=float(source.get("avg_outcome_score") or 0),
                intent_score=intent_score,
                trust_path_score=trust_score,
                displacement_score=displacement,
                trust_path=trust_path,
                is_cold_result=(trust_path is None),
                explanation=explanation,
            ))

        results.sort(key=lambda r: r.displacement_score, reverse=True)

        # Tie-break: trust-pathed result wins over equally-scored cold result
        for i in range(len(results) - 1):
            r1, r2 = results[i], results[i + 1]
            if (r1.displacement_score == r2.displacement_score
                    and r2.trust_path and not r1.trust_path):
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
    print(f"Domain : {config.domain}")
    print(f"User   : {user_name}  ({edge_count} trust edges)")
    print("=" * 55)

    TEST_QUERIES = [
        "I want a quiet place for a business dinner, good North Indian, Indiranagar, not too loud, parking available",
        "Casual dinner with friends in Koramangala, something lively",
        "Something nice for tonight",
    ]

    for query in TEST_QUERIES:
        print(f"\n{'─' * 55}")
        print(f"Query: \"{query}\"")
        try:
            intent  = parse_intent(query, config)
            results = match(intent, user_id, conn, config)

            print(f"Hard: {intent.hard_constraints()}")
            print(f"Soft: {intent.soft_constraints()}")
            print(f"\nTop {len(results)} results:")
            for i, r in enumerate(results, 1):
                trust_info = (
                    f"via {r.trust_path.trusted_user_name} (w={r.trust_path.edge_weight})"
                    if r.trust_path else "cold"
                )
                print(f"  [{i}] {r.name} — disp={r.displacement_score} "
                      f"intent={r.intent_score} trust={r.trust_path_score}  {trust_info}")
        except Exception as e:
            import traceback
            print(f"ERROR: {e}")
            traceback.print_exc()

    conn.close()
    print("\nDone.\n")
