"""
UNIVERSAL CONNECTOR — REST API  v3.0
Domain-agnostic trust routing infrastructure.

Endpoints:
  POST /search              — tiered search: trusted / community / cold / ghost
  POST /outcome             — capture visit outcome (updates trust graph)
  POST /ghost               — enter an offline source by reference
  POST /community/join      — declare community membership (village/profession/etc.)
  POST /tenant/register     — register an external app on the shared graph
  POST /graph/contribute    — contribute trust data from an external app
  GET  /graph/query         — query the trust graph from an external app
  GET  /user/{id}/trust     — trust graph summary for a user
  GET  /domains             — list available domains
  GET  /health              — health check

Run:
  uvicorn api.main:app --reload --port 8000
"""

import json
import os
import secrets
import time
from datetime import datetime, timezone
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

try:
    from fastapi import FastAPI, HTTPException, Depends, Header
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
from engine.matcher import match, get_conn, SIGNAL_LAYERS
from engine.domains import get_domain, REGISTRY

# ── APP SETUP ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Universal Connector API",
    description="Trust routing infrastructure — domain-agnostic, graph-first",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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


# ── SIGNAL TIER HELPERS ───────────────────────────────────────────────────────

_TRUSTED_LAYERS    = {'direct_trust', 'network_trust'}
_COMMUNITY_LAYERS  = {'community_trust', 'domain_expert', 'crowd_wisdom'}
_COLD_LAYERS       = {'intent_only'}

_TIER_INDICATOR = {
    'trusted':   '●',
    'community': '◐',
    'cold':      '○',
    'ghost':     '◌',
}


def _assign_tier(signal_layer: str) -> str:
    if signal_layer in _TRUSTED_LAYERS:
        return 'trusted'
    if signal_layer in _COMMUNITY_LAYERS:
        return 'community'
    return 'cold'


def _relative_time(visited_at: Optional[str]) -> str:
    if not visited_at:
        return "some time ago"
    try:
        dt = datetime.fromisoformat(visited_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        days = (datetime.now(timezone.utc) - dt).days
        if days == 0:
            return "today"
        if days == 1:
            return "yesterday"
        if days < 7:
            return f"{days} days ago"
        if days < 30:
            return f"{days // 7} weeks ago"
        if days < 365:
            return f"{days // 30} months ago"
        return f"{days // 365} years ago"
    except Exception:
        return "recently"


def _build_trust_sentence(signal, source_name: str) -> str:
    layer = signal.signal_layer
    name  = signal.trusted_user_name or "Someone"
    when  = _relative_time(signal.visited_at)
    outcome_word = {
        'positive': 'loved it',
        'neutral':  'found it okay',
        'negative': "didn't enjoy it",
        'regret':   'regretted going',
    }.get(signal.outcome or '', 'visited')

    if layer == 'direct_trust':
        return f"{name} went {when} and {outcome_word}"

    if layer == 'network_trust':
        hops = signal.hops
        hop_phrase = "a friend of a friend" if hops == 2 else f"{hops} hops away in your network"
        network_part = f" · {signal.path_count} people in your network agree" if signal.path_count > 1 else ""
        return f"{name} ({hop_phrase}) went {when} and {outcome_word}{network_part}"

    if layer == 'community_trust':
        ctx = signal.community_context or "shared community"
        ctx_label = ctx.split(":")[-1] if ":" in ctx else ctx
        return f"{name} from {ctx_label} went {when} and {outcome_word}"

    if layer == 'domain_expert':
        return f"{name} (trusted expert in this space) has been here and {outcome_word}"

    if layer == 'crowd_wisdom':
        pct = int(min(100, signal.edge_weight * 100))
        return f"Community rated this positively — {pct}% satisfaction score"

    return "No trust signal yet — this matches your description"


def _build_trust_path(signal, source_name: str) -> Optional[str]:
    layer = signal.signal_layer
    name  = signal.trusted_user_name

    if layer == 'direct_trust' and name:
        return f"You → {name} → {source_name}"

    if layer == 'network_trust' and name:
        mid = " → … → " if signal.hops > 2 else " → "
        return f"You → {name}{mid}{source_name}"

    if layer == 'community_trust' and name:
        ctx = signal.community_context or "community"
        ctx_label = ctx.split(":")[-1] if ":" in ctx else ctx
        return f"You ({ctx_label}) ↔ {name} → {source_name}"

    return None


# ── REQUEST / RESPONSE MODELS ─────────────────────────────────────────────────

class SearchRequest(BaseModel):
    user_id: str
    query:   str
    domain:  str = 'restaurants'
    top_k:   int = 5


class TieredMatch(BaseModel):
    source_id:          str
    name:               str
    domain:             str
    signal_tier:        str           # trusted | community | cold
    signal_indicator:   str           # ● ◐ ○
    signal_layer:       str           # direct_trust | network_trust | … | intent_only
    trust_sentence:     str           # human-readable trust explanation
    trust_path_display: Optional[str] # "You → Priya → [Restaurant]"
    attributes:         dict
    avg_outcome_score:  float
    displacement_score: float
    intent_score:       float
    trust_score:        float
    fit_score:          float         # bidirectional: how much source wants this user
    is_bidirectional:   bool          # true if source declared a target_profile


class GhostResult(BaseModel):
    ghost_id:          str
    name:              str
    domain:            str
    description:       Optional[str]
    attributes:        dict
    entered_by_name:   str
    trust_sentence:    str
    contact_hint:      Optional[str]
    location_hint:     Optional[str]
    community_tags:    list[str]
    signal_tier:       str = 'ghost'
    signal_indicator:  str = '◌'


class SuggestedContact(BaseModel):
    user_id:       str
    name:          str
    trust_weight:  float
    domain_visits: int


class TieredSearchResponse(BaseModel):
    query:              str
    user_id:            str
    domain:             str
    confident_matches:  list[TieredMatch]      # trusted tier
    community_matches:  list[TieredMatch]      # community tier
    cold_matches:       list[TieredMatch]      # cold tier (intent only)
    ghost_matches:      list[GhostResult]      # offline sources entered by reference
    no_path_found:      bool
    suggested_contacts: list[SuggestedContact] # who to ask if no trust path
    result_count:       int
    intent_parsed:      dict
    alpha:              float
    beta:               float
    trust_density:      float
    search_time_ms:     float


class OutcomeRequest(BaseModel):
    user_id:    str
    source_id:  str
    domain:     str = 'restaurants'
    outcome:    str
    notes:      Optional[str] = None
    intent_query: Optional[str] = None


class OutcomeResponse(BaseModel):
    success:       bool
    trust_updated: bool
    message:       str


class GhostSourceRequest(BaseModel):
    user_id:        str
    domain:         str
    name:           str
    description:    Optional[str] = None
    attributes:     dict          = {}
    contact_hint:   Optional[str] = None
    location_hint:  Optional[str] = None
    community_tags: list[str]     = []


class GhostSourceResponse(BaseModel):
    ghost_id:  str
    message:   str


class JoinCommunityRequest(BaseModel):
    user_id:       str
    context_type:  str   # village | profession | family | neighborhood | school | workplace | other
    context_value: str


class TenantRegisterRequest(BaseModel):
    name:    str
    domains: list[str]


class TenantRegisterResponse(BaseModel):
    tenant_id: str
    api_key:   str
    message:   str


class GraphContributeRequest(BaseModel):
    contribution_type: str    # ghost_source | community_membership | trust_signal
    payload:           dict


class GraphQueryRequest(BaseModel):
    user_id:    str
    domain:     str
    query_type: str           # trust_path | community | ghost_sources
    source_id:  Optional[str] = None


# ── HELPERS ───────────────────────────────────────────────────────────────────

def _format_tiered_match(r) -> TieredMatch:
    tier      = _assign_tier(r.signal_layer)
    indicator = _TIER_INDICATOR.get(tier, '○')
    sentence  = _build_trust_sentence(r.signal, r.name)
    path      = _build_trust_path(r.signal, r.name)
    is_bidir  = r.attributes.get('target_profile') is not None

    return TieredMatch(
        source_id=r.source_id,
        name=r.name,
        domain=r.domain,
        signal_tier=tier,
        signal_indicator=indicator,
        signal_layer=r.signal_layer,
        trust_sentence=sentence,
        trust_path_display=path,
        attributes=r.attributes,
        avg_outcome_score=r.avg_outcome_score,
        displacement_score=r.displacement_score,
        intent_score=r.intent_score,
        trust_score=r.trust_score,
        fit_score=r.fit_score,
        is_bidirectional=is_bidir,
    )


def _format_ghost_result(g, user_name: str = "You") -> GhostResult:
    if g.trust_weight > 0:
        sentence = f"{g.entered_by_name} (in your network, trust={g.trust_weight:.2f}) knows this place"
    else:
        sentence = f"Entered by {g.entered_by_name} — not yet in your trust network"
    return GhostResult(
        ghost_id=g.ghost_id,
        name=g.name,
        domain=g.domain,
        description=g.description,
        attributes=g.attributes,
        entered_by_name=g.entered_by_name,
        trust_sentence=sentence,
        contact_hint=g.contact_hint,
        location_hint=g.location_hint,
        community_tags=g.community_tags,
    )


def _verify_tenant(api_key: Optional[str], conn) -> dict:
    """Verify tenant API key. Returns tenant row or raises 401."""
    if not api_key:
        raise HTTPException(status_code=401, detail="X-Tenant-Key header required")
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, domains, can_write, can_read
        FROM tenants WHERE api_key = %s AND active = true
    """, (api_key,))
    row = cur.fetchone()
    cur.close()
    if not row:
        raise HTTPException(status_code=401, detail="Invalid or inactive tenant API key")
    return {'id': str(row[0]), 'name': row[1], 'domains': row[2],
            'can_write': row[3], 'can_read': row[4]}


# ── ENDPOINTS ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "version": "3.0.0", "domains": list(REGISTRY.keys())}


@app.get("/domains")
def list_domains():
    return {
        "domains": {
            name: {
                "fields": [
                    {
                        "name":               fd.name,
                        "type":               fd.field_type,
                        "valid_values":       fd.valid_values,
                        "default_constraint": fd.default_constraint,
                        "score_weight":       fd.score_weight,
                    }
                    for fd in config.fields
                ]
            }
            for name, config in REGISTRY.items()
        }
    }


@app.post("/search", response_model=TieredSearchResponse)
def search(req: SearchRequest, conn=Depends(get_db)):
    """
    Tiered search. Results grouped by trust quality:
      ● confident_matches — direct or network trust (you know someone who knows this)
      ◐ community_matches — community/expert/crowd signal
      ○ cold_matches      — intent match only, no trust data
      ◌ ghost_matches     — offline sources entered by someone who knows them

    When no trusted path exists, suggests who in your network to ask.
    """
    start = time.time()

    try:
        domain_config = get_domain(req.domain)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE id = %s", (req.user_id,))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail=f"User {req.user_id} not found")
    cur.close()

    try:
        intent = parse_intent(req.query, domain_config)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Intent parsing failed: {e}")

    try:
        output = match(intent, req.user_id, conn, domain_config, top_k=req.top_k)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Matching failed: {e}")

    # Log search
    try:
        cur = conn.cursor()
        top = output.results[0] if output.results else None

        cur.execute("""
            INSERT INTO intent_logs
              (user_id, raw_query, parsed_intent, results_returned,
               top_result_id, top_result_score, had_trust_path)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            req.user_id,
            req.query,
            Json(intent.to_dict()),
            len(output.results),
            top.source_id if top else None,
            top.displacement_score if top else None,
            not output.no_path_found,
        ))

        now = datetime.now().isoformat()
        fk  = domain_config.source_fk_column
        for r in output.results:
            has_personal   = r.signal.trusted_user_id is not None
            recommended_by = r.signal.trusted_user_id if has_personal else None
            trust_weight   = r.signal.edge_weight      if has_personal else None
            trust_hops     = r.signal.hops             if has_personal else 0
            cur.execute(f"""
                INSERT INTO interactions
                  (user_id, {fk}, recommended_by, trust_path_weight,
                   trust_hops, intent_query, intent_parsed,
                   outcome, outcome_score, visited_at, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NULL, NULL, NULL, %s)
                ON CONFLICT (user_id, {fk}) WHERE outcome IS NULL AND {fk} IS NOT NULL
                DO UPDATE SET
                    recommended_by    = EXCLUDED.recommended_by,
                    trust_path_weight = EXCLUDED.trust_path_weight,
                    trust_hops        = EXCLUDED.trust_hops,
                    intent_query      = EXCLUDED.intent_query,
                    intent_parsed     = EXCLUDED.intent_parsed,
                    created_at        = EXCLUDED.created_at
            """, (
                req.user_id, r.source_id,
                recommended_by, trust_weight, trust_hops,
                req.query, Json(intent.to_dict()), now,
            ))

        conn.commit()
        cur.close()
    except Exception:
        pass   # logging failure must not break search

    # Partition into tiers
    confident, community, cold = [], [], []
    for r in output.results:
        tier = _assign_tier(r.signal_layer)
        tm   = _format_tiered_match(r)
        if tier == 'trusted':
            confident.append(tm)
        elif tier == 'community':
            community.append(tm)
        else:
            cold.append(tm)

    ghost_results = [_format_ghost_result(g) for g in output.ghost_matches]

    elapsed = round((time.time() - start) * 1000, 1)

    return TieredSearchResponse(
        query=req.query,
        user_id=req.user_id,
        domain=req.domain,
        confident_matches=confident,
        community_matches=community,
        cold_matches=cold,
        ghost_matches=ghost_results,
        no_path_found=output.no_path_found,
        suggested_contacts=[
            SuggestedContact(**c) for c in output.suggested_contacts
        ],
        result_count=len(output.results),
        intent_parsed=intent.to_dict(),
        alpha=output.alpha,
        beta=output.beta,
        trust_density=output.density,
        search_time_ms=elapsed,
    )


@app.post("/ghost/{ghost_id}/materialize")
def materialize_ghost(ghost_id: str, source_id: str, conn=Depends(get_db)):
    """
    Convert a ghost source into a real platform source.

    Called when the offline source (the rice seller, the tailor) finally
    joins the platform. Links ghost_sources.materialized_to → real source,
    so any trust context built around the ghost node transfers to the real one.

    source_id: the real restaurant_id or product_id they registered as.
    """
    cur = conn.cursor()
    cur.execute("SELECT id, domain, name FROM ghost_sources WHERE id = %s AND active = true",
                (ghost_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Ghost source not found")

    _, domain, name = row

    cur.execute("""
        UPDATE ghost_sources
        SET is_materialized = true,
            materialized_to = %s,
            updated_at      = %s
        WHERE id = %s
    """, (source_id, datetime.now().isoformat(), ghost_id))

    conn.commit()
    cur.close()

    return {
        "success": True,
        "ghost_id": ghost_id,
        "source_id": source_id,
        "message": f"'{name}' is now on the platform. "
                   f"Trust signals built around this ghost node will route to the real source.",
    }


@app.post("/outcome", response_model=OutcomeResponse)
def record_outcome(req: OutcomeRequest, conn=Depends(get_db)):
    """
    Record the outcome of a visit.
    Updates source_trust and trust_edges — the self-correction feedback loop.
    """
    valid_outcomes = {"positive", "negative", "neutral", "regret"}
    if req.outcome not in valid_outcomes:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid outcome. Must be one of: {valid_outcomes}",
        )

    try:
        domain_config = get_domain(req.domain)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    fk = domain_config.source_fk_column
    cur = conn.cursor()

    cur.execute(f"""
        SELECT id, recommended_by, trust_path_weight, trust_hops, intent_query, intent_parsed
        FROM interactions
        WHERE user_id = %s AND {fk} = %s AND outcome IS NULL
        ORDER BY created_at DESC
        LIMIT 1
    """, (req.user_id, req.source_id))
    row = cur.fetchone()
    if row:
        pending_id, recommended_by, trust_path_weight, trust_hops, stored_query, intent_parsed_data = row
    else:
        pending_id, recommended_by, trust_path_weight, trust_hops, stored_query, intent_parsed_data = (
            None, None, None, 0, req.intent_query, None
        )

    outcome_score_map = {
        "positive":  0.8,
        "neutral":   0.1,
        "negative": -0.6,
        "regret":   -0.3,
    }
    outcome_score = outcome_score_map[req.outcome]
    now = datetime.now().isoformat()

    if pending_id:
        cur.execute("""
            UPDATE interactions
            SET outcome             = %s,
                outcome_score       = %s,
                outcome_notes       = %s,
                outcome_recorded_at = %s,
                visited_at          = %s
            WHERE id = %s
        """, (req.outcome, outcome_score, req.notes, now, now, pending_id))
    else:
        cur.execute(f"""
            INSERT INTO interactions
              (user_id, {fk}, recommended_by, trust_path_weight,
               trust_hops, intent_query, outcome, outcome_score,
               outcome_notes, outcome_recorded_at, visited_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            req.user_id, req.source_id,
            recommended_by, trust_path_weight,
            trust_hops if recommended_by else 0,
            req.intent_query or stored_query,
            req.outcome, outcome_score,
            req.notes, now, now,
        ))

    is_positive = req.outcome == "positive"
    is_negative = req.outcome in ("negative", "regret")
    cur.execute(f"""
        INSERT INTO source_trust
          (user_id, {fk}, domain, weight,
           visit_count, positive_outcome_count, negative_outcome_count,
           last_visited_at, last_outcome, last_intent_parsed, status)
        VALUES (%s, %s, %s, %s, 1, %s, %s, %s, %s, %s, 'active')
        ON CONFLICT (user_id, {fk}) WHERE {fk} IS NOT NULL
        DO UPDATE SET
            visit_count            = source_trust.visit_count + 1,
            positive_outcome_count = source_trust.positive_outcome_count + %s,
            negative_outcome_count = source_trust.negative_outcome_count + %s,
            last_visited_at        = %s,
            last_outcome           = %s,
            last_intent_parsed     = COALESCE(%s, source_trust.last_intent_parsed),
            weight = CASE
                WHEN %s THEN LEAST(1.0,   source_trust.weight + 0.05)
                WHEN %s THEN GREATEST(0.0, source_trust.weight - 0.03)
                ELSE source_trust.weight
            END,
            updated_at = %s
    """, (
        req.user_id, req.source_id, req.domain,
        0.6 if is_positive else 0.2,
        1 if is_positive else 0,
        1 if is_negative else 0,
        now, req.outcome,
        Json(intent_parsed_data) if intent_parsed_data else None,
        1 if is_positive else 0,
        1 if is_negative else 0,
        now, req.outcome,
        Json(intent_parsed_data) if intent_parsed_data else None,
        is_positive, is_negative,
        now,
    ))

    trust_updated = False
    if recommended_by:
        cur.execute("""
            INSERT INTO trust_edges
              (from_user_id, to_user_id, domain, weight, basis,
               implicit_count, last_reinforced_at, decay_rate, status)
            VALUES (%s, %s, %s, 0.30, 'implicit', 0, %s, 0.01, 'active')
            ON CONFLICT (from_user_id, to_user_id, domain) DO NOTHING
        """, (req.user_id, recommended_by, req.domain, now))

        if is_positive:
            cur.execute("""
                UPDATE trust_edges
                SET weight             = LEAST(1.0, weight + 0.03),
                    implicit_count     = implicit_count + 1,
                    last_reinforced_at = %s,
                    updated_at         = %s
                WHERE from_user_id = %s AND to_user_id = %s AND domain = %s
            """, (now, now, req.user_id, recommended_by, req.domain))
        elif is_negative:
            cur.execute("""
                UPDATE trust_edges
                SET weight         = GREATEST(0.0, weight - 0.02),
                    implicit_count = implicit_count + 1,
                    updated_at     = %s
                WHERE from_user_id = %s AND to_user_id = %s AND domain = %s
            """, (now, req.user_id, recommended_by, req.domain))

        cur.execute("""
            UPDATE trust_edges
            SET status = CASE
                WHEN weight < 0.15 THEN 'dormant'
                WHEN weight < 0.40 THEN 'decaying'
                ELSE 'active'
            END,
            updated_at = %s
            WHERE from_user_id = %s AND to_user_id = %s AND domain = %s
        """, (now, req.user_id, recommended_by, req.domain))

        trust_updated = True

    conn.commit()
    cur.close()

    msg_map = {
        "positive": "Trust weights reinforced for this recommendation path.",
        "negative": "Trust weights adjusted. We'll improve future recommendations.",
        "neutral":  "Outcome recorded.",
        "regret":   "Trust weights adjusted for future matches.",
    }

    return OutcomeResponse(
        success=True,
        trust_updated=trust_updated,
        message=msg_map[req.outcome],
    )


@app.post("/ghost", response_model=GhostSourceResponse)
def enter_ghost_source(req: GhostSourceRequest, conn=Depends(get_db)):
    """
    Enter an offline source by reference.

    This is how the connection that "already exists in the universe" gets
    captured. The rice seller in Mandya, the tailor who only takes referrals,
    the restaurant with no online presence — entered by someone who knows them.

    The person entering it becomes the trust signal for anyone who finds it.
    """
    try:
        get_domain(req.domain)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE id = %s", (req.user_id,))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail=f"User {req.user_id} not found")

    try:
        cur.execute("""
            INSERT INTO ghost_sources
              (domain, name, description, attributes, entered_by,
               contact_hint, location_hint, community_tags)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            req.domain, req.name, req.description,
            Json(req.attributes), req.user_id,
            req.contact_hint, req.location_hint, req.community_tags,
        ))
        ghost_id = str(cur.fetchone()[0])
        conn.commit()
        cur.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create ghost source: {e}")

    return GhostSourceResponse(
        ghost_id=ghost_id,
        message=f"'{req.name}' added as an offline reference. "
                f"It will appear in search results for people in your trust network.",
    )


@app.post("/community/join")
def join_community(req: JoinCommunityRequest, conn=Depends(get_db)):
    """
    Declare community membership — village, profession, family, etc.

    This creates implicit trust bridges. If you and Ravi both list
    context_type=village, context_value=Mandya — and Ravi has visited
    a rice seller — you'll find it via community_trust layer.

    The connection already exists. This just makes it visible.
    """
    valid_types = {'village','profession','family','neighborhood','school','workplace','other'}
    if req.context_type not in valid_types:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid context_type. Must be one of: {sorted(valid_types)}",
        )

    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE id = %s", (req.user_id,))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail=f"User {req.user_id} not found")

    try:
        cur.execute("""
            INSERT INTO user_community (user_id, context_type, context_value)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, context_type, context_value) DO NOTHING
        """, (req.user_id, req.context_type, req.context_value))
        conn.commit()
        cur.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to record community: {e}")

    return {
        "success": True,
        "message": f"Joined {req.context_type}: {req.context_value}. "
                   f"You will now see recommendations from people who share this context.",
    }


@app.post("/tenant/register", response_model=TenantRegisterResponse)
def register_tenant(req: TenantRegisterRequest, conn=Depends(get_db)):
    """
    Register an external application on the Universal Connector shared graph.

    Any app can contribute trust data and query the trust graph — like DNS.
    A village community app mapping local vendors, a professional network
    mapping mentors, a family app tracking trusted contacts — all contribute
    to one universal trust graph.
    """
    for domain in req.domains:
        try:
            get_domain(domain)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown domain: {domain}")

    api_key = secrets.token_hex(32)
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO tenants (name, api_key, domains)
            VALUES (%s, %s, %s)
            RETURNING id
        """, (req.name, api_key, req.domains))
        tenant_id = str(cur.fetchone()[0])
        conn.commit()
        cur.close()
    except Exception as e:
        if "unique" in str(e).lower():
            raise HTTPException(status_code=409, detail=f"Tenant '{req.name}' already exists")
        raise HTTPException(status_code=500, detail=str(e))

    return TenantRegisterResponse(
        tenant_id=tenant_id,
        api_key=api_key,
        message=f"Tenant '{req.name}' registered. Store your API key securely — it won't be shown again.",
    )


@app.post("/graph/contribute")
def contribute_to_graph(
    req: GraphContributeRequest,
    x_tenant_key: Optional[str] = Header(default=None),
    conn=Depends(get_db),
):
    """
    Contribute trust data from an external app.

    contribution_type = ghost_source | community_membership | trust_signal

    ghost_source payload:
      { "domain": "restaurants", "name": "...", "description": "...",
        "entered_by_user_id": "<uuid>", "attributes": {...},
        "contact_hint": "...", "location_hint": "...", "community_tags": [...] }

    community_membership payload:
      { "user_id": "<uuid>", "context_type": "village", "context_value": "Mandya" }

    trust_signal payload:
      { "from_user_id": "<uuid>", "to_user_id": "<uuid>",
        "domain": "restaurants", "weight": 0.4, "basis": "implicit" }
    """
    tenant = _verify_tenant(x_tenant_key, conn)
    if not tenant['can_write']:
        raise HTTPException(status_code=403, detail="This tenant does not have write access")

    valid_types = {'ghost_source', 'community_membership', 'trust_signal'}
    if req.contribution_type not in valid_types:
        raise HTTPException(status_code=422, detail=f"contribution_type must be one of: {valid_types}")

    cur = conn.cursor()

    # Log the contribution
    cur.execute("""
        INSERT INTO tenant_contributions (tenant_id, contribution_type, payload)
        VALUES (%s, %s, %s)
        RETURNING id
    """, (tenant['id'], req.contribution_type, Json(req.payload)))
    contrib_id = str(cur.fetchone()[0])

    result_id = None
    try:
        if req.contribution_type == 'ghost_source':
            p = req.payload
            cur.execute("""
                INSERT INTO ghost_sources
                  (domain, name, description, attributes, entered_by,
                   contact_hint, location_hint, community_tags)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                p['domain'], p['name'], p.get('description'),
                Json(p.get('attributes', {})), p['entered_by_user_id'],
                p.get('contact_hint'), p.get('location_hint'),
                p.get('community_tags', []),
            ))
            result_id = str(cur.fetchone()[0])

        elif req.contribution_type == 'community_membership':
            p = req.payload
            cur.execute("""
                INSERT INTO user_community (user_id, context_type, context_value)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, context_type, context_value) DO NOTHING
                RETURNING id
            """, (p['user_id'], p['context_type'], p['context_value']))
            row = cur.fetchone()
            result_id = str(row[0]) if row else None

        elif req.contribution_type == 'trust_signal':
            p = req.payload
            now = datetime.now().isoformat()
            weight = max(0.0, min(1.0, float(p.get('weight', 0.3))))
            cur.execute("""
                INSERT INTO trust_edges
                  (from_user_id, to_user_id, domain, weight, basis,
                   last_reinforced_at, decay_rate, status)
                VALUES (%s, %s, %s, %s, %s, %s, 0.01, 'active')
                ON CONFLICT (from_user_id, to_user_id, domain)
                DO UPDATE SET
                    weight             = LEAST(1.0, trust_edges.weight + 0.02),
                    last_reinforced_at = %s,
                    updated_at         = %s
                RETURNING id
            """, (
                p['from_user_id'], p['to_user_id'], p['domain'],
                weight, p.get('basis', 'implicit'), now, now, now,
            ))
            row = cur.fetchone()
            result_id = str(row[0]) if row else None

        # Mark contribution as processed
        cur.execute("""
            UPDATE tenant_contributions
            SET processed = true, processed_at = %s, result_id = %s
            WHERE id = %s
        """, (datetime.now().isoformat(), result_id, contrib_id))

        conn.commit()
        cur.close()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Contribution failed: {e}")

    return {
        "success": True,
        "contribution_id": contrib_id,
        "result_id": result_id,
        "message": f"{req.contribution_type} contribution processed by tenant '{tenant['name']}'",
    }


@app.post("/graph/query")
def query_graph(
    req: GraphQueryRequest,
    x_tenant_key: Optional[str] = Header(default=None),
    conn=Depends(get_db),
):
    """
    Query the trust graph from an external app.

    query_type = trust_path | community | ghost_sources

    Returns trust routing data that any app can use to make trust-aware
    decisions — without building their own graph.
    """
    tenant = _verify_tenant(x_tenant_key, conn)
    if not tenant['can_read']:
        raise HTTPException(status_code=403, detail="This tenant does not have read access")

    cur = conn.cursor()

    if req.query_type == 'trust_path':
        if not req.source_id:
            raise HTTPException(status_code=422, detail="source_id required for trust_path query")
        try:
            domain_config = get_domain(req.domain)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        fk = domain_config.source_fk_column
        cur.execute(f"""
            SELECT
                te.to_user_id, u.name, te.weight, te.status,
                st.last_outcome, st.last_visited_at
            FROM trust_edges te
            JOIN users u         ON u.id = te.to_user_id
            JOIN source_trust st ON st.user_id    = te.to_user_id
                                AND st.{fk}       = %s
                                AND st.domain     = %s
            WHERE te.from_user_id = %s AND te.status = 'active' AND te.domain = %s
            ORDER BY te.weight DESC
            LIMIT 5
        """, (req.source_id, req.domain, req.user_id, req.domain))
        rows = cur.fetchall()
        cur.close()
        return {
            "query_type": "trust_path",
            "paths": [
                {"user_id": str(r[0]), "name": r[1], "weight": float(r[2]),
                 "status": r[3], "outcome": r[4], "visited_at": str(r[5]) if r[5] else None}
                for r in rows
            ]
        }

    elif req.query_type == 'community':
        cur.execute("""
            SELECT context_type, context_value
            FROM user_community
            WHERE user_id = %s
            ORDER BY context_type, context_value
        """, (req.user_id,))
        rows = cur.fetchall()
        cur.close()
        return {
            "query_type": "community",
            "memberships": [{"context_type": r[0], "context_value": r[1]} for r in rows]
        }

    elif req.query_type == 'ghost_sources':
        cur.execute("""
            SELECT gs.id, gs.name, gs.description, gs.attributes,
                   u.name AS entered_by, gs.contact_hint, gs.location_hint, gs.community_tags
            FROM ghost_sources gs
            JOIN users u ON u.id = gs.entered_by
            WHERE gs.domain = %s AND gs.active = true AND gs.is_materialized = false
            ORDER BY gs.created_at DESC
            LIMIT 20
        """, (req.domain,))
        rows = cur.fetchall()
        cur.close()
        return {
            "query_type": "ghost_sources",
            "sources": [
                {"id": str(r[0]), "name": r[1], "description": r[2],
                 "attributes": r[3], "entered_by": r[4],
                 "contact_hint": r[5], "location_hint": r[6], "community_tags": r[7]}
                for r in rows
            ]
        }

    else:
        raise HTTPException(status_code=422, detail=f"Unknown query_type: {req.query_type}")


@app.get("/user/{user_id}/trust")
def get_user_trust(user_id: str, domain: str = 'restaurants', conn=Depends(get_db)):
    """Trust graph summary for a user in a given domain."""
    try:
        domain_config = get_domain(domain)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    cur = conn.cursor()
    col = domain_config.trust_received_column

    cur.execute(f"""
        SELECT name, friend_group, {col}, cold_start_flag
        FROM users WHERE id = %s
    """, (user_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    name, group, trust_recv, cold_start = row

    cur.execute("""
        SELECT u.name, te.weight, te.status, te.basis, te.last_reinforced_at
        FROM trust_edges te
        JOIN users u ON u.id = te.to_user_id
        WHERE te.from_user_id = %s AND te.domain = %s
        ORDER BY te.weight DESC
    """, (user_id, domain))
    edges = cur.fetchall()

    # Community memberships
    community = []
    try:
        cur.execute("""
            SELECT context_type, context_value FROM user_community
            WHERE user_id = %s ORDER BY context_type
        """, (user_id,))
        community = [{"type": r[0], "value": r[1]} for r in cur.fetchall()]
    except Exception:
        pass

    cur.close()

    return {
        "user_id":       user_id,
        "name":          name,
        "friend_group":  group,
        "domain":        domain,
        "cold_start":    cold_start,
        "trust_score":   trust_recv,
        "graph_density": min(1.0, len(edges) / 10.0),
        "trust_network": [
            {
                "name":            e[0],
                "weight":          float(e[1]),
                "status":          e[2],
                "basis":           e[3],
                "last_reinforced": str(e[4]) if e[4] else None,
            }
            for e in edges
        ],
        "network_size":  len(edges),
        "community":     community,
    }


@app.get("/test/users")
def get_sample_users(conn=Depends(get_db)):
    """Sample users for testing — one per friend group."""
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
