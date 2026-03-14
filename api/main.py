"""
UNIVERSAL CONNECTOR — REST API
Phase 1: Restaurants Domain

Endpoints:
  POST /search         — main search endpoint
  POST /outcome        — capture visit outcome
  GET  /user/{id}/trust — get trust graph summary for user
  GET  /health         — health check

Run:
  uvicorn api.main:app --reload --port 8000
"""

import json
import os
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

try:
    from fastapi import FastAPI, HTTPException, Depends
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
except ImportError:
    raise ImportError("Run: pip install fastapi uvicorn")

try:
    import psycopg2
    from psycopg2.extras import Json
except ImportError:
    raise ImportError("Run: pip install psycopg2-binary")

import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))

from engine.intent_parser import parse_intent
from engine.matcher import match, get_conn

# ── APP SETUP ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Universal Connector API",
    description="Phase 1 — Restaurant discovery via trust-weighted intent matching",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── DB DEPENDENCY ─────────────────────────────────────────────────────────────
def get_db():
    conn = get_conn()
    try:
        yield conn
    finally:
        conn.close()

# ── REQUEST / RESPONSE MODELS ─────────────────────────────────────────────────

class SearchRequest(BaseModel):
    user_id: str
    query:   str
    top_k:   int = 5

class TrustPathResponse(BaseModel):
    trusted_person:  str
    edge_weight:     float
    hops:            int
    their_outcome:   Optional[str]
    visited_at:      Optional[str]

class ExplanationResponse(BaseModel):
    displacement_score: float
    intent_summary:     str
    intent_score:       float
    trust_summary:      str
    trust_score:        float
    is_cold_result:     bool
    breakdown:          dict

class RestaurantResult(BaseModel):
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
    displacement_score: float
    intent_score:       float
    trust_score:        float
    is_cold_result:     bool
    trust_path:         Optional[TrustPathResponse]
    explanation:        ExplanationResponse

class SearchResponse(BaseModel):
    query:          str
    user_id:        str
    results:        list[RestaurantResult]
    result_count:   int
    intent_parsed:  dict
    alpha:          float
    beta:           float
    search_time_ms: float

class OutcomeRequest(BaseModel):
    user_id:        str
    restaurant_id:  str
    outcome:        str   # positive | negative | neutral | regret
    notes:          Optional[str] = None
    intent_query:   Optional[str] = None

class OutcomeResponse(BaseModel):
    success:          bool
    trust_updated:    bool
    message:          str

# ── HELPER: format match results ──────────────────────────────────────────────

def format_result(r) -> RestaurantResult:
    tp = None
    if r.trust_path:
        tp = TrustPathResponse(
            trusted_person=r.trust_path.trusted_user_name,
            edge_weight=r.trust_path.edge_weight,
            hops=r.trust_path.hops,
            their_outcome=r.trust_path.outcome,
            visited_at=r.trust_path.visited_at,
        )

    exp = r.explanation
    intent_layer = exp.get("intent_layer", {})
    trust_layer  = exp.get("trust_layer", {})

    explanation = ExplanationResponse(
        displacement_score=exp.get("displacement_score", 0),
        intent_summary=intent_layer.get("summary", ""),
        intent_score=intent_layer.get("score", 0),
        trust_summary=trust_layer.get("summary", ""),
        trust_score=trust_layer.get("score", 0),
        is_cold_result=exp.get("cold_result", True),
        breakdown=intent_layer.get("breakdown", {}),
    )

    return RestaurantResult(
        restaurant_id=r.restaurant_id,
        name=r.name,
        area=r.area,
        cuisine=r.cuisine,
        vibe=r.vibe,
        occasion=r.occasion,
        price_range=r.price_range,
        noise_level=r.noise_level,
        parking=r.parking,
        seating_type=r.seating_type,
        avg_outcome_score=r.avg_outcome_score,
        displacement_score=r.displacement_score,
        intent_score=r.intent_score,
        trust_score=r.trust_path_score,
        is_cold_result=r.is_cold_result,
        trust_path=tp,
        explanation=explanation,
    )

# ── ENDPOINTS ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0", "domain": "restaurants"}


@app.post("/search", response_model=SearchResponse)
def search(req: SearchRequest, conn=Depends(get_db)):
    """
    Main search endpoint.
    Takes natural language query + user_id.
    Returns ranked restaurants via displacement scoring.
    """
    import time
    start = time.time()

    # Validate user exists
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE id = %s", (req.user_id,))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail=f"User {req.user_id} not found")
    cur.close()

    # Parse intent
    try:
        intent = parse_intent(req.query)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Intent parsing failed: {e}")

    # Run matching engine
    try:
        results = match(intent, req.user_id, conn, top_k=req.top_k)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Matching failed: {e}")

    # Log search to intent_logs
    try:
        cur = conn.cursor()
        top = results[0] if results else None
        cur.execute("""
            INSERT INTO intent_logs
              (user_id, raw_query, parsed_intent, results_returned,
               top_result_id, top_result_score, had_trust_path)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            req.user_id,
            req.query,
            Json(intent.to_dict()),
            len(results),
            top.restaurant_id if top else None,
            top.displacement_score if top else None,
            any(r.trust_path for r in results),
        ))
        conn.commit()
        cur.close()
    except Exception:
        pass   # logging failure should not break search

    elapsed = round((time.time() - start) * 1000, 1)

    # Get α/β from first result explanation (or defaults)
    alpha = 0.85
    beta  = 0.15
    if results:
        exp = results[0].explanation
        il  = exp.get("intent_layer", {})
        tl  = exp.get("trust_layer", {})
        alpha = il.get("weight", 0.85)
        beta  = tl.get("weight", 0.15) if tl else 0.15

    return SearchResponse(
        query=req.query,
        user_id=req.user_id,
        results=[format_result(r) for r in results],
        result_count=len(results),
        intent_parsed=intent.to_dict(),
        alpha=alpha,
        beta=beta,
        search_time_ms=elapsed,
    )


@app.post("/outcome", response_model=OutcomeResponse)
def record_outcome(req: OutcomeRequest, conn=Depends(get_db)):
    """
    Record the outcome of a restaurant visit.
    Updates trust edge weights based on outcome.
    This is the feedback loop that makes the graph self-correct.
    """
    valid_outcomes = {"positive", "negative", "neutral", "regret"}
    if req.outcome not in valid_outcomes:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid outcome. Must be one of: {valid_outcomes}"
        )

    cur = conn.cursor()

    # Check if there was a trust path for this restaurant → user combination
    cur.execute("""
        SELECT recommended_by, trust_path_weight
        FROM interactions
        WHERE user_id       = %s
          AND restaurant_id = %s
        ORDER BY created_at DESC
        LIMIT 1
    """, (req.user_id, req.restaurant_id))
    row = cur.fetchone()
    recommended_by   = row[0] if row else None
    trust_path_weight = row[1] if row else None

    # Record interaction
    outcome_score_map = {
        "positive": 0.8,
        "neutral":  0.1,
        "negative": -0.6,
        "regret":   -0.3,
    }
    outcome_score = outcome_score_map[req.outcome]
    now = datetime.now().isoformat()

    cur.execute("""
        INSERT INTO interactions
          (user_id, restaurant_id, recommended_by, trust_path_weight,
           trust_hops, intent_query, outcome, outcome_score,
           outcome_notes, outcome_recorded_at, visited_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        req.user_id, req.restaurant_id,
        recommended_by, trust_path_weight,
        1 if recommended_by else 0,
        req.intent_query, req.outcome, outcome_score,
        req.notes, now, now,
    ))

    # Update trust edge weights based on outcome
    trust_updated = False
    if recommended_by:
        if req.outcome == "positive":
            # Reinforce trust edge
            cur.execute("""
                UPDATE trust_edges
                SET weight             = LEAST(1.0, weight + 0.03),
                    implicit_count     = implicit_count + 1,
                    last_reinforced_at = %s,
                    status             = 'active',
                    updated_at         = %s
                WHERE from_user_id = %s
                  AND to_user_id   = %s
                  AND domain       = 'restaurants'
            """, (now, now, req.user_id, recommended_by))

        elif req.outcome in ("negative", "regret"):
            # Downweight trust edge
            cur.execute("""
                UPDATE trust_edges
                SET weight         = GREATEST(0.0, weight - 0.02),
                    implicit_count = implicit_count + 1,
                    updated_at     = %s
                WHERE from_user_id = %s
                  AND to_user_id   = %s
                  AND domain       = 'restaurants'
            """, (now, req.user_id, recommended_by))

        # Update status if weight dropped below thresholds
        cur.execute("""
            UPDATE trust_edges
            SET status = CASE
                WHEN weight < 0.15 THEN 'dormant'
                WHEN weight < 0.40 THEN 'decaying'
                ELSE 'active'
            END,
            updated_at = %s
            WHERE from_user_id = %s
              AND to_user_id   = %s
              AND domain       = 'restaurants'
        """, (now, req.user_id, recommended_by))

        trust_updated = True

    # Update source trust
    cur.execute("""
        INSERT INTO source_trust
          (user_id, restaurant_id, domain, weight,
           visit_count, positive_outcome_count, negative_outcome_count,
           last_visited_at, status)
        VALUES (%s, %s, 'restaurants', %s, 1,
                %s, %s, %s, 'active')
        ON CONFLICT (user_id, restaurant_id)
        DO UPDATE SET
            visit_count             = source_trust.visit_count + 1,
            positive_outcome_count  = source_trust.positive_outcome_count + %s,
            negative_outcome_count  = source_trust.negative_outcome_count + %s,
            last_visited_at         = %s,
            weight = CASE
                WHEN EXCLUDED.positive_outcome_count > 0
                THEN LEAST(1.0, source_trust.weight + 0.05)
                ELSE GREATEST(0.0, source_trust.weight - 0.03)
            END,
            updated_at = %s
    """, (
        req.user_id, req.restaurant_id,
        0.6 if req.outcome == "positive" else 0.2,
        1 if req.outcome == "positive" else 0,
        1 if req.outcome in ("negative", "regret") else 0,
        now,
        1 if req.outcome == "positive" else 0,
        1 if req.outcome in ("negative", "regret") else 0,
        now, now,
    ))

    conn.commit()
    cur.close()

    msg_map = {
        "positive": "Great! Trust weights reinforced for this recommendation path.",
        "negative": "Noted. Trust weights adjusted. We'll improve future recommendations.",
        "neutral":  "Thanks for the feedback. Outcome recorded.",
        "regret":   "Understood. Trust weights adjusted for future matches.",
    }

    return OutcomeResponse(
        success=True,
        trust_updated=trust_updated,
        message=msg_map[req.outcome],
    )


@app.get("/user/{user_id}/trust")
def get_user_trust(user_id: str, conn=Depends(get_db)):
    """
    Get trust graph summary for a user.
    Shows who they trust, their trust scores, and graph density.
    """
    cur = conn.cursor()

    # User info
    cur.execute("""
        SELECT name, friend_group,
               trust_received_restaurants,
               trust_given_restaurants,
               cold_start_flag
        FROM users WHERE id = %s
    """, (user_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    name, group, trust_recv, trust_given, cold_start = row

    # Trust edges
    cur.execute("""
        SELECT u.name, te.weight, te.status, te.basis,
               te.last_reinforced_at
        FROM trust_edges te
        JOIN users u ON u.id = te.to_user_id
        WHERE te.from_user_id = %s
          AND te.domain = 'restaurants'
        ORDER BY te.weight DESC
    """, (user_id,))
    edges = cur.fetchall()

    cur.close()

    return {
        "user_id":        user_id,
        "name":           name,
        "friend_group":   group,
        "cold_start":     cold_start,
        "trust_scores": {
            "restaurants": trust_recv,
            "given":       trust_given,
        },
        "graph_density":  min(1.0, len(edges) / 10.0),
        "trust_network": [
            {
                "name":              e[0],
                "weight":            float(e[1]),
                "status":            e[2],
                "basis":             e[3],
                "last_reinforced":   str(e[4]) if e[4] else None,
            }
            for e in edges
        ],
        "network_size": len(edges),
    }


@app.get("/users/sample")
def get_sample_users(conn=Depends(get_db)):
    """
    Get sample users for testing — returns one user per friend group.
    Useful for quickly getting test user_ids.
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT ON (friend_group)
            id, name, friend_group,
            trust_received_restaurants,
            cold_start_flag
        FROM users
        ORDER BY friend_group, trust_received_restaurants DESC
    """)
    rows = cur.fetchall()
    cur.close()

    return {
        "users": [
            {
                "user_id":      str(r[0]),
                "name":         r[1],
                "friend_group": r[2],
                "trust_score":  float(r[3]),
                "cold_start":   r[4],
            }
            for r in rows
        ]
    }
