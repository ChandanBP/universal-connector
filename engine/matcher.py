"""
UNIVERSAL CONNECTOR — Matching Engine
Phase 1: Restaurants Domain

Takes a Structured Intent Object + user_id
Returns ranked list of restaurants via displacement scoring.

Displacement score = (intent_score × α) + (trust_path_score × β)
α > β always — intent is the primary signal.
α/β ratio adjusts dynamically based on trust graph density.

Usage:
  from engine.matcher import match
  results = match(intent, user_id, conn)
"""

import json
import math
import os
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# ── DATA STRUCTURES ───────────────────────────────────────────────────────────

@dataclass
class TrustPath:
    """The trust path from user to a restaurant recommendation."""
    trusted_user_id:   str
    trusted_user_name: str
    edge_weight:       float
    hops:              int
    outcome:           Optional[str]   # their past outcome at this restaurant
    visited_at:        Optional[str]

@dataclass
class MatchResult:
    """A single ranked result returned by the matching engine."""
    restaurant_id:      str
    name:               str
    area:               str
    cuisine:            list
    vibe:               list
    occasion:           list
    price_range:        str
    noise_level:        str
    parking:            bool
    seating_type:       list
    avg_outcome_score:  float

    # Scoring
    intent_score:       float
    trust_path_score:   float
    displacement_score: float

    # Trust path details — for transparency layer
    trust_path:         Optional[TrustPath]
    is_cold_result:     bool   # True = no trust path found

    # Explanation components — for "Why was this shown?"
    explanation:        dict   = field(default_factory=dict)


# ── DATABASE CONNECTION ───────────────────────────────────────────────────────

def get_conn():
    """Get Postgres connection from DATABASE_URL env var."""
    try:
        import psycopg2
        return psycopg2.connect(os.getenv("DATABASE_URL"))
    except ImportError:
        raise ImportError("Run: pip install psycopg2-binary")
    except Exception as e:
        raise ConnectionError(f"Database connection failed: {e}")


# ── STEP 1: FILTER — hard constraint elimination ──────────────────────────────

FILTER_SQL = """
    SELECT
        id, name, area, cuisine, vibe, occasion,
        price_range, noise_level, seating_type,
        parking, tags, avg_outcome_score,
        total_visits, trust_citations
    FROM restaurants
    WHERE active = true
    {area_filter}
    {noise_filter}
    {parking_filter}
    {price_filter}
    {cuisine_filter}
    {seating_filter}
    LIMIT 100
"""

def filter_candidates(cur, intent) -> list:
    """
    Apply hard constraints to eliminate non-matching restaurants.
    Any restaurant violating a hard constraint is excluded entirely.
    """
    hard = intent.hard_constraints()
    soft = intent.soft_constraints()

    # Merge hard + soft for cuisine/occasion/vibe (just need them present)
    all_constraints = {**soft, **hard}  # hard overwrites soft on conflict

    filters = {
        "area_filter":    "",
        "noise_filter":   "",
        "parking_filter": "",
        "price_filter":   "",
        "cuisine_filter": "",
        "seating_filter": "",
    }
    params = []

    # Area — hard constraint only
    if hard.get("area"):
        filters["area_filter"] = "AND area = %s"
        params.append(hard["area"])

    # Noise level — hard constraint only
    if hard.get("noise_level"):
        filters["noise_filter"] = "AND noise_level = %s"
        params.append(hard["noise_level"])

    # Parking — hard constraint only
    if hard.get("parking") is True:
        filters["parking_filter"] = "AND parking = true"

    # Price range — hard constraint only
    if hard.get("price_range"):
        filters["price_filter"] = "AND price_range = %s"
        params.append(hard["price_range"])

    # Cuisine — hard constraint: must contain at least one matching cuisine
    if hard.get("cuisine"):
        filters["cuisine_filter"] = "AND cuisine && %s::text[]"
        params.append(hard["cuisine"])

    # Seating — hard constraint
    if hard.get("seating_type"):
        filters["seating_filter"] = "AND seating_type && %s::text[]"
        params.append(hard["seating_type"])

    sql = FILTER_SQL.format(**filters)
    cur.execute(sql, params)
    rows = cur.fetchall()

    columns = ["id", "name", "area", "cuisine", "vibe", "occasion",
               "price_range", "noise_level", "seating_type", "parking",
               "tags", "avg_outcome_score", "total_visits", "trust_citations"]

    return [dict(zip(columns, row)) for row in rows]


# ── STEP 2: INTENT MATCH SCORING ─────────────────────────────────────────────

# Weight of each attribute in intent score
INTENT_WEIGHTS = {
    "occasion": 0.35,
    "vibe":     0.30,
    "cuisine":  0.20,   # lower weight — often already filtered as hard constraint
    "area":     0.10,
    "other":    0.05,
}

def score_intent(restaurant: dict, intent) -> tuple[float, dict]:
    """
    Score how well a restaurant matches the intent object.
    Returns (score 0.0-1.0, breakdown dict for explanation).
    """
    breakdown = {}
    total_score = 0.0
    total_weight = 0.0

    # ── Occasion match (fuzzy) ───────────────────────────────────────────────
    # Occasions are soft signals — restaurants dont always tag perfectly.
    # Use fuzzy matching: exact match = 1.0, related match = 0.5, no match = 0.1
    # This prevents good restaurants from scoring 0.0 just due to tagging gaps.
    OCCASION_SIMILARITY = {
        "business":       {"business": 1.0, "casual": 0.4, "celebration": 0.3},
        "date-night":     {"date-night": 1.0, "romantic": 0.8, "casual": 0.3, "celebration": 0.5},
        "family":         {"family": 1.0, "casual": 0.4, "celebration": 0.5},
        "casual":         {"casual": 1.0, "friends-hangout": 0.8, "quick-lunch": 0.6, "family": 0.4},
        "celebration":    {"celebration": 1.0, "date-night": 0.6, "family": 0.5, "casual": 0.3},
        "friends-hangout":{"friends-hangout": 1.0, "casual": 0.8, "celebration": 0.4},
        "quick-lunch":    {"quick-lunch": 1.0, "casual": 0.6},
    }
    intent_occasions = (
        intent.occasion.value if intent.occasion.value else []
    )
    if intent_occasions:
        rest_occasions = restaurant.get("occasion", [])
        best_scores = []
        for intent_occ in intent_occasions:
            sim_map = OCCASION_SIMILARITY.get(intent_occ, {intent_occ: 1.0})
            best = max((sim_map.get(ro, 0.0) for ro in rest_occasions), default=0.1)
            best_scores.append(best)
        score = sum(best_scores) / len(best_scores) if best_scores else 0.1
        breakdown["occasion"] = round(score, 2)
        total_score  += score * INTENT_WEIGHTS["occasion"]
        total_weight += INTENT_WEIGHTS["occasion"]

    # ── Vibe match ────────────────────────────────────────────────────────────
    intent_vibes = intent.vibe.value if intent.vibe.value else []
    if intent_vibes:
        rest_vibes = restaurant.get("vibe", [])
        overlap = len(set(intent_vibes) & set(rest_vibes))
        score = overlap / len(intent_vibes) if intent_vibes else 0.0
        breakdown["vibe"] = round(score, 2)
        total_score  += score * INTENT_WEIGHTS["vibe"]
        total_weight += INTENT_WEIGHTS["vibe"]

    # ── Cuisine match ─────────────────────────────────────────────────────────
    intent_cuisines = intent.cuisine.value if intent.cuisine.value else []
    if intent_cuisines:
        rest_cuisines = restaurant.get("cuisine", [])
        overlap = len(set(intent_cuisines) & set(rest_cuisines))
        score = min(1.0, overlap / len(intent_cuisines)) if intent_cuisines else 0.0
        breakdown["cuisine"] = round(score, 2)
        total_score  += score * INTENT_WEIGHTS["cuisine"]
        total_weight += INTENT_WEIGHTS["cuisine"]

    # ── Area match ────────────────────────────────────────────────────────────
    intent_area = intent.area.value
    if intent_area:
        score = 1.0 if restaurant.get("area") == intent_area else 0.0
        breakdown["area"] = score
        total_score  += score * INTENT_WEIGHTS["area"]
        total_weight += INTENT_WEIGHTS["area"]

    # ── Noise level match ─────────────────────────────────────────────────────
    intent_noise = intent.noise_level.value
    if intent_noise and intent.noise_level.constraint == "soft":
        score = 1.0 if restaurant.get("noise_level") == intent_noise else 0.3
        breakdown["noise_level"] = score
        total_score  += score * INTENT_WEIGHTS["other"]
        total_weight += INTENT_WEIGHTS["other"]

    # ── Price match ───────────────────────────────────────────────────────────
    intent_price = intent.price_range.value
    if intent_price and intent.price_range.constraint == "soft":
        score = 1.0 if restaurant.get("price_range") == intent_price else 0.3
        breakdown["price_range"] = score
        total_score  += score * INTENT_WEIGHTS["other"]
        total_weight += INTENT_WEIGHTS["other"]

    # Normalise
    final_score = (total_score / total_weight) if total_weight > 0 else 0.5

    # If query is very vague — give all restaurants a base score
    if intent.ambiguity_score > 0.7:
        final_score = max(final_score, 0.4)

    return round(final_score, 3), breakdown


# ── STEP 3: TRUST PATH QUERY ──────────────────────────────────────────────────

TRUST_PATH_SQL = """
    SELECT
        te.to_user_id,
        u.name AS trusted_user_name,
        te.weight AS edge_weight,
        i.outcome,
        i.visited_at,
        1 AS hops
    FROM trust_edges te
    JOIN users u ON u.id = te.to_user_id
    JOIN interactions i
        ON i.user_id     = te.to_user_id
        AND i.restaurant_id = %s
    WHERE te.from_user_id = %s
      AND te.status       = 'active'
      AND te.domain       = 'restaurants'
      AND i.outcome IN ('positive', 'neutral')
    ORDER BY
        te.weight DESC,
        i.visited_at DESC
    LIMIT 1
"""

def find_trust_path(cur, user_id: str, restaurant_id: str) -> Optional[TrustPath]:
    """
    Find the best trust path from user to a restaurant.
    Phase 1: Direct trust only (1 hop).
    Returns None if no trust path exists (cold result).
    """
    cur.execute(TRUST_PATH_SQL, (restaurant_id, user_id))
    row = cur.fetchone()

    if not row:
        return None

    return TrustPath(
        trusted_user_id=row[0],
        trusted_user_name=row[1],
        edge_weight=float(row[2]),
        hops=row[5],
        outcome=row[3],
        visited_at=str(row[4]) if row[4] else None,
    )


# ── STEP 4: TRUST PATH SCORING ────────────────────────────────────────────────

def score_trust_path(trust_path: Optional[TrustPath]) -> float:
    """
    Convert trust path into a normalised score 0.0-1.0.
    No trust path → 0.0 (cold result, still eligible via intent score).

    Formula: avg(edge_weights) × (1 / log(hop_count + 1))
    Phase 1: Only 1 hop, so log factor is always 1/log(2) ≈ 1.44
    Capped at 0.95 — indirect trust never equals direct certainty.
    """
    if trust_path is None:
        return 0.0

    # Outcome modifier — neutral outcome reduces trust score slightly
    outcome_modifier = 1.0 if trust_path.outcome == "positive" else 0.8

    # Log hop penalty (Phase 1 always 1 hop, formula ready for multi-hop Phase 2)
    hop_penalty = 1.0 / math.log(trust_path.hops + 2)  # log(3) ≈ 1.1 for 1 hop

    raw_score = trust_path.edge_weight * outcome_modifier * hop_penalty

    return round(min(0.95, raw_score), 3)


# ── STEP 5: DISPLACEMENT SCORE ────────────────────────────────────────────────

def get_trust_graph_density(cur, user_id: str) -> float:
    """
    Compute trust graph density for this user.
    0.0 = no edges (cold start), 1.0 = very dense graph.
    Used to dynamically set α/β weighting.
    """
    cur.execute("""
        SELECT COUNT(*) FROM trust_edges
        WHERE from_user_id = %s
          AND status = 'active'
          AND domain = 'restaurants'
    """, (user_id,))
    count = cur.fetchone()[0]

    # Normalise: 0 edges = 0.0, 10+ edges = 1.0
    return min(1.0, count / 10.0)


def compute_alpha_beta(density: float) -> tuple[float, float]:
    """
    Dynamic α/β weighting based on trust graph density.

    Sparse (new user):    α=0.85, β=0.15  — intent dominates
    Medium:               α=0.70, β=0.30
    Dense (mature user):  α=0.55, β=0.45  — trust contributes strongly

    α > β always — intent is always the primary signal.
    """
    if density < 0.3:
        alpha = 0.85
    elif density < 0.7:
        alpha = 0.70
    else:
        alpha = 0.55

    beta = round(1.0 - alpha, 2)
    return alpha, beta


def compute_displacement_score(
    intent_score: float,
    trust_score: float,
    alpha: float,
    beta: float
) -> float:
    return round((intent_score * alpha) + (trust_score * beta), 3)


# ── STEP 6: BUILD EXPLANATION ─────────────────────────────────────────────────

def build_explanation(
    restaurant:    dict,
    intent,
    intent_score:  float,
    intent_breakdown: dict,
    trust_path:    Optional[TrustPath],
    trust_score:   float,
    alpha:         float,
    beta:          float,
    displacement:  float,
) -> dict:
    """
    Build the transparency explanation for "Why was this shown?"
    Shown when user expands a result card.
    """
    explanation = {
        "displacement_score": displacement,
        "intent_layer": {
            "score":     intent_score,
            "weight":    alpha,
            "summary":   f"{round(intent_score * 100)}% matches your description",
            "breakdown": intent_breakdown,
        },
        "trust_layer": None,
        "cold_result": trust_path is None,
    }

    if trust_path:
        explanation["trust_layer"] = {
            "score":            trust_score,
            "weight":           beta,
            "trusted_person":   trust_path.trusted_user_name,
            "edge_weight":      trust_path.edge_weight,
            "hops":             trust_path.hops,
            "their_outcome":    trust_path.outcome,
            "visited_at":       trust_path.visited_at,
            "summary": (
                f"{trust_path.trusted_user_name} who you trust "
                f"has been here and rated it {trust_path.outcome}"
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
    intent,
    user_id: str,
    conn=None,
    top_k: int = 5
) -> list[MatchResult]:
    """
    Core displacement matching function.

    Args:
        intent:  IntentObject from intent_parser.parse_intent()
        user_id: UUID of the searching user
        conn:    Postgres connection (creates one if None)
        top_k:   Number of results to return (default 5)

    Returns:
        List of MatchResult sorted by displacement_score descending
    """
    should_close = False
    if conn is None:
        conn = get_conn()
        should_close = True

    cur = conn.cursor()

    try:
        # ── Get trust graph density for this user ─────────────────────────────
        density = get_trust_graph_density(cur, user_id)
        alpha, beta = compute_alpha_beta(density)

        # ── Step 1: Filter candidates by hard constraints ─────────────────────
        candidates = filter_candidates(cur, intent)

        if not candidates:
            # Relax hard constraints if no results
            # Try area-only filter as fallback
            from copy import deepcopy
            relaxed = deepcopy(intent)
            # Drop non-area hard constraints
            for fname in ["cuisine", "noise_level", "parking", "price_range"]:
                f = getattr(relaxed, fname)
                if f.constraint == "hard":
                    f.constraint = "soft"
            candidates = filter_candidates(cur, relaxed)

        results = []

        for restaurant in candidates:
            rid = restaurant["id"]

            # ── Step 2: Score intent match ────────────────────────────────────
            intent_score, intent_breakdown = score_intent(restaurant, intent)

            # ── Step 3: Find trust path ───────────────────────────────────────
            trust_path = find_trust_path(cur, user_id, rid)

            # ── Step 4: Score trust path ──────────────────────────────────────
            trust_score = score_trust_path(trust_path)

            # ── Step 5: Compute displacement score ────────────────────────────
            displacement = compute_displacement_score(
                intent_score, trust_score, alpha, beta
            )

            # ── Step 6: Build explanation ─────────────────────────────────────
            explanation = build_explanation(
                restaurant, intent,
                intent_score, intent_breakdown,
                trust_path, trust_score,
                alpha, beta, displacement
            )

            results.append(MatchResult(
                restaurant_id=rid,
                name=restaurant["name"],
                area=restaurant["area"],
                cuisine=restaurant["cuisine"],
                vibe=restaurant["vibe"],
                occasion=restaurant["occasion"],
                price_range=restaurant["price_range"],
                noise_level=restaurant["noise_level"],
                parking=restaurant["parking"],
                seating_type=restaurant["seating_type"],
                avg_outcome_score=float(restaurant["avg_outcome_score"] or 0),
                intent_score=intent_score,
                trust_path_score=trust_score,
                displacement_score=displacement,
                trust_path=trust_path,
                is_cold_result=(trust_path is None),
                explanation=explanation,
            ))

        # ── Sort by displacement score ────────────────────────────────────────
        results.sort(key=lambda r: r.displacement_score, reverse=True)

        # ── Tie-breaking: prefer trust-pathed results ─────────────────────────
        # If two results have identical displacement score,
        # trust-pathed result wins
        for i in range(len(results) - 1):
            r1, r2 = results[i], results[i+1]
            if (r1.displacement_score == r2.displacement_score and
                    r2.trust_path and not r1.trust_path):
                results[i], results[i+1] = r2, r1

        return results[:top_k]

    finally:
        cur.close()
        if should_close:
            conn.close()


# ── TEST ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))

    from engine.intent_parser import parse_intent
    import psycopg2

    print("\n⚙️  Universal Connector — Matching Engine Test")
    print("=" * 55)

    conn = get_conn()

    # Get a real user from simulated data
    cur = conn.cursor()
    cur.execute("""
        SELECT u.id, u.name, u.friend_group,
               COUNT(te.id) AS edge_count
        FROM users u
        LEFT JOIN trust_edges te ON te.from_user_id = u.id
            AND te.status = 'active'
        WHERE u.cold_start_flag = false
        GROUP BY u.id, u.name, u.friend_group
        ORDER BY edge_count DESC
        LIMIT 1
    """)
    row = cur.fetchone()
    user_id, user_name, friend_group, edge_count = row
    cur.close()

    print(f"Test user   : {user_name} ({friend_group})")
    print(f"Trust edges : {edge_count}")

    TEST_QUERIES = [
        "I want a quiet place for a business dinner, good North Indian, Indiranagar, not too loud, parking available",
        "Casual dinner with friends in Koramangala, something lively",
        "Something nice for tonight",   # vague — tests ambiguity handling
    ]

    for query in TEST_QUERIES:
        print(f"\n{'─'*55}")
        print(f"Query: \"{query}\"")

        try:
            intent = parse_intent(query)
            print(f"Ambiguity   : {intent.ambiguity_score}")
            print(f"Hard        : {intent.hard_constraints()}")
            print(f"Soft        : {intent.soft_constraints()}")

            results = match(intent, user_id, conn)

            print(f"\nTop {len(results)} results:")
            for i, r in enumerate(results, 1):
                trust_info = (
                    f"via {r.trust_path.trusted_user_name} (weight {r.trust_path.edge_weight})"
                    if r.trust_path else "cold result"
                )
                print(f"  [{i}] {r.name} ({r.area})")
                print(f"       displacement={r.displacement_score}  "
                      f"intent={r.intent_score}  trust={r.trust_path_score}")
                print(f"       {trust_info}")

        except Exception as e:
            print(f"  ❌ Error: {e}")
            import traceback
            traceback.print_exc()

    conn.close()
    print(f"\n✅ Matching engine test complete\n")