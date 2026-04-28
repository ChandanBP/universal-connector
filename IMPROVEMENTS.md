# Implementation Summary: Hub Node Fallback + Additive Trust Scoring

## Overview
Two critical improvements to the Universal Connector matching engine:

1. **Hub Node Fallback** — Solves the reachability problem for new users
2. **Additive Trust Scoring** — Transparent, component-based scoring with hop discounts

---

## 1. Hub Node Fallback

### Problem
Previously, if a user had no direct trust connections to a restaurant, the result was marked as "cold" regardless of how good the recommendation was. New users with sparse trust graphs would only get intent-based scores, losing valuable signal from domain experts.

### Solution
**Two-stage trust path discovery:**

```
Stage 1: Direct Trust (1 hop)
├─ Query: user → their trusted friend → restaurant
├─ Hops: 1
├─ Edge weight: Real from trust_edges table
└─ Return if found

Stage 2: Hub Node Fallback (if Stage 1 fails)
├─ Query: Find domain experts (trust_received_restaurants >= 0.6)
├─ Filter: Who have visited this specific restaurant with positive outcome
├─ Hops: 2 (synthetic fallback)
├─ Edge weight: Synthetic 0.6
└─ Return if found

Stage 3: Cold Result (if both fail)
└─ No trust path exists
```

### Implementation Details

**SQL Queries Added:**

```sql
-- HUB_NODE_FALLBACK_SQL
SELECT
    u.id,
    u.name AS trusted_user_name,
    0.6 AS edge_weight,  -- synthetic edge to hub node
    i.outcome,
    i.visited_at,
    2 AS hops  -- fallback is considered 2+ hops
FROM users u
JOIN interactions i
    ON i.user_id     = u.id
    AND i.restaurant_id = %s
WHERE u.id != %s
  AND u.trust_received_restaurants >= 0.6
  AND i.outcome IN ('positive', 'neutral')
ORDER BY
    u.trust_received_restaurants DESC,
    i.visited_at DESC
LIMIT 1
```

### Impact

- **New users**: Can discover restaurants via domain experts even with empty trust graphs
- **Cold-start solved**: Intent score + hub node fallback provides path forward
- **Network effects**: Domain experts become valuable nodes early in adoption
- **Transparent**: Result shows "domain expert recommendation" label

---

## 2. Additive Trust Scoring Formula

### Problem
Old multiplicative formula: `trust_score = edge_weight × outcome_modifier × hop_penalty`

Issues:
- Outcome modifier of 0.8 for neutral could zero out entire score
- Logarithmic hop penalty was opaque
- Didn't account for recency independently
- Hub nodes (0.6 edge weight) scored too low

### Solution
**Additive formula with component transparency:**

$$\text{trust\_score} = \left(\text{edge\_weight} \times 0.50 + \text{outcome\_score} \times 0.30 + \text{recency\_score} \times 0.20\right) - \text{hop\_discount}$$

**Capped at 0.95**

### Components

| Component | Weight | Calculation | Range |
|-----------|--------|-------------|-------|
| **Edge Weight** | 0.50 | Direct from `trust_edges.weight` | 0.0–1.0 |
| **Outcome Score** | 0.30 | positive=0.8, neutral=0.1, negative=-0.6, regret=-0.3 | -0.18–0.24 |
| **Recency Score** | 0.20 | Linear decay: 1.0 @ 0 days → 0.0 @ 180 days | 0.0–0.20 |
| **Hop Discount** | — | 1 hop=0.00, 2 hops=0.15 | 0.00–0.15 |

### Score Ranges

**Direct Trust (1 hop):**
- Best case: 0.8 + 0.24 + 0.20 - 0.00 = **0.94** ✓
- Hub node (synthetic 0.6): 0.30 + 0.24 + 0.20 - 0.15 = **0.59** ✓
- Positive, old: 0.40 + 0.24 + 0.00 - 0.00 = **0.64** ✓
- Negative, recent: 0.40 - 0.18 + 0.20 - 0.00 = **0.42** ✓

### Code Changes

**In `engine/matcher.py`:**

```python
def score_trust_path(trust_path: Optional[TrustPath], recency_days: Optional[float] = None) -> float:
    """Score trust path using additive formula."""
    if trust_path is None:
        return 0.0

    # Component 1: Edge weight (0.50)
    edge_component = trust_path.edge_weight * 0.50

    # Component 2: Outcome score (0.30)
    outcome_score_map = {
        "positive": 0.8, "neutral": 0.1,
        "negative": -0.6, "regret": -0.3,
    }
    outcome_score = outcome_score_map.get(trust_path.outcome, 0.0)
    outcome_component = outcome_score * 0.30

    # Component 3: Recency (0.20)
    if recency_days is None:
        # Calculate from visited_at timestamp
        ...
    recency_score = max(0.0, 1.0 - (recency_days / 180.0))
    recency_component = recency_score * 0.20

    # Hop discount
    hop_discount = 0.00 if trust_path.hops == 1 else 0.15

    # Additive formula
    raw_score = edge_component + outcome_component + recency_component - hop_discount

    # Cap at 0.95
    return round(min(0.95, max(0.0, raw_score)), 3)
```

---

## 3. Transparency Layer Update

The explanation object now indicates hub node fallbacks:

```python
explanation["trust_layer"] = {
    "score": trust_score,
    "weight": beta,
    "trusted_person": trust_path.trusted_user_name,
    "edge_weight": trust_path.edge_weight,
    "hops": trust_path.hops,
    "their_outcome": trust_path.outcome,
    "visited_at": trust_path.visited_at,
    "is_hub_node": is_hub_node,  # NEW
    "summary": (
        f"{trust_path.trusted_user_name} "
        f"{'(domain expert recommendation)' if is_hub_node else ''}"
        f" has been here and rated it {outcome_text}"
    ),
}
```

---

## 4. Test Suite

Created `tests/test_improvements.py` with 8 comprehensive tests:

1. ✅ Direct 1-hop + positive + today → 0.84
2. ✅ Direct 1-hop + neutral + 90 days → 0.53
3. ✅ Hub node (2 hops) + positive → 0.59
4. ✅ Maximum score capped at 0.95
5. ✅ Negative outcome penalty → 0.387
6. ✅ Old visit decay (180 days) → 0.64
7. ✅ No trust path → 0.0
8. ✅ Hub node fallback concept validation

**Run tests:**
```bash
python tests/test_improvements.py
```

---

## 5. Benefits Summary

### Hub Node Fallback
- ✅ **Solves cold-start**: New users discover via domain experts
- ✅ **Reachability**: Good restaurants outside user's network are findable
- ✅ **Network effects**: Creates incentive to build high trust_received score
- ✅ **Transparent**: Clear labeling of hub node recommendations

### Additive Scoring
- ✅ **Transparent**: Each component visible in breakdown
- ✅ **Fair to hub nodes**: 0.6 edge weight → ~0.59 score (not penalized)
- ✅ **Recency-aware**: Independent linear decay (not logarithmic)
- ✅ **Outcome-sensitive**: Negative outcomes don't eliminate score completely
- ✅ **Predictable**: Same conditions always produce same score

---

## 6. Next Steps

1. **Test with database**: Run `/search` endpoint with seeded data
2. **Monitor cold-start ratio**: Track percentage of hub node fallbacks used
3. **Adjust thresholds**: Consider tweaking `trust_received_restaurants >= 0.6`
4. **Phase 2**: Multi-hop trust paths (2 → 3 → restaurant)
5. **Analytics**: Track which hub nodes generate best outcomes

---

## Files Modified

- `engine/matcher.py` — Added hub node fallback + additive scoring
- `tests/test_improvements.py` — New test suite (created)
