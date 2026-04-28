# Mathematical Reference: Trust Scoring Formula

## Additive Trust Scoring

### Formula Definition

$$\text{trust\_score} = \left(\text{edge\_weight} \times 0.50 + \text{outcome\_score} \times 0.30 + \text{recency\_score} \times 0.20\right) - \text{hop\_discount}$$

$$\text{trust\_score} = \min(0.95, \max(0.0, \text{raw\_score}))$$

### Component Definitions

#### 1. Edge Weight Component
$$\text{edge\_component} = \text{edge\_weight} \times 0.50$$

- **Source**: `trust_edges.weight` column (direct) or 0.6 (hub node)
- **Range**: 0.0–0.50
- **Meaning**: Strength of trust relationship with recommender
- **Example**: 
  - Strong trust (0.85) → 0.425
  - Hub node (0.6) → 0.30

#### 2. Outcome Score Component
$$\text{outcome\_component} = \text{outcome\_score} \times 0.30$$

Where outcome_score is:
- **positive** = 0.8 → outcome_component = 0.24
- **neutral** = 0.1 → outcome_component = 0.03
- **negative** = -0.6 → outcome_component = -0.18
- **regret** = -0.3 → outcome_component = -0.09

- **Range**: -0.18 to 0.24
- **Meaning**: Quality of their past experience
- **Note**: Negative outcomes pull down score, not zero it out

#### 3. Recency Score Component
$$\text{recency\_days} = \text{days since last visit}$$

$$\text{recency\_score} = \max\left(0.0, 1.0 - \frac{\text{recency\_days}}{180}\right)$$

$$\text{recency\_component} = \text{recency\_score} \times 0.20$$

- **Timeline**:
  - 0 days (today) → recency_score = 1.0 → component = 0.20
  - 90 days (3 months) → recency_score = 0.5 → component = 0.10
  - 180 days (6 months) → recency_score = 0.0 → component = 0.00
  - >180 days → recency_score = 0.0 → component = 0.00

- **Range**: 0.0–0.20
- **Meaning**: How fresh is the recommendation?

#### 4. Hop Discount
$$\text{hop\_discount} = \begin{cases} 0.00 & \text{if } \text{hops} = 1 \\ 0.15 & \text{if } \text{hops} \geq 2 \end{cases}$$

- **1 hop (direct trust)**: No penalty
- **2 hops (hub fallback)**: -0.15 penalty
- **Meaning**: Direct recommendations valued more

#### 5. Capping
$$\text{trust\_score} = \min(0.95, \max(0.0, \text{raw\_score}))$$

- **Minimum**: 0.0 (no negative scores)
- **Maximum**: 0.95 (intent never completely overridden)
- **Meaning**: Trust enhances intent match, but doesn't dominate

## Example Calculations

### Example 1: Direct Trust with Recent Positive Outcome

**Inputs:**
- edge_weight = 0.8 (user trusts Alice highly)
- outcome = "positive" (Alice had great experience)
- visited_at = today (0 days ago)
- hops = 1 (direct friend)

**Calculation:**
```
edge_component = 0.8 × 0.50 = 0.40
outcome_score = 0.8 (positive)
outcome_component = 0.8 × 0.30 = 0.24
recency_days = 0
recency_score = 1.0 - (0 / 180) = 1.0
recency_component = 1.0 × 0.20 = 0.20
hop_discount = 0.00 (1 hop)

raw_score = 0.40 + 0.24 + 0.20 - 0.00 = 0.84
trust_score = min(0.95, max(0.0, 0.84)) = 0.84
```

**Result: 0.84** ✅ Strong recommendation

### Example 2: Hub Node Fallback

**Inputs:**
- edge_weight = 0.6 (synthetic for hub node)
- outcome = "positive" (expert visited recently)
- visited_at = 1 day ago
- hops = 2 (fallback via domain expert)

**Calculation:**
```
edge_component = 0.6 × 0.50 = 0.30
outcome_score = 0.8 (positive)
outcome_component = 0.8 × 0.30 = 0.24
recency_days = 1
recency_score = 1.0 - (1 / 180) = 0.994
recency_component = 0.994 × 0.20 = 0.199
hop_discount = 0.15 (2 hops)

raw_score = 0.30 + 0.24 + 0.199 - 0.15 = 0.589
trust_score = min(0.95, max(0.0, 0.589)) = 0.589
```

**Result: 0.589** ✅ Hub node still gets competitive score

### Example 3: Direct Trust with Negative Outcome (Old)

**Inputs:**
- edge_weight = 0.8
- outcome = "negative" (friend had bad experience)
- visited_at = 30 days ago
- hops = 1

**Calculation:**
```
edge_component = 0.8 × 0.50 = 0.40
outcome_score = -0.6 (negative)
outcome_component = -0.6 × 0.30 = -0.18
recency_days = 30
recency_score = 1.0 - (30 / 180) = 0.833
recency_component = 0.833 × 0.20 = 0.167
hop_discount = 0.00 (1 hop)

raw_score = 0.40 + (-0.18) + 0.167 - 0.00 = 0.387
trust_score = min(0.95, max(0.0, 0.387)) = 0.387
```

**Result: 0.387** ⚠️ Penalized but not eliminated

### Example 4: Maximum Possible Score

**Inputs:**
- edge_weight = 1.0 (perfect trust)
- outcome = "positive" (best outcome)
- visited_at = today (most recent)
- hops = 1 (direct)

**Calculation:**
```
edge_component = 1.0 × 0.50 = 0.50
outcome_component = 0.8 × 0.30 = 0.24
recency_component = 1.0 × 0.20 = 0.20
hop_discount = 0.00

raw_score = 0.50 + 0.24 + 0.20 - 0.00 = 0.94
trust_score = min(0.95, max(0.0, 0.94)) = 0.94
```

**Result: 0.94** ✅ Capped at 0.95 (intended)

## Integration with Displacement Score

The final ranking score combines intent and trust:

$$\text{displacement\_score} = (\text{intent\_score} \times \alpha) + (\text{trust\_score} \times \beta)$$

Where:
- α (alpha) = intent weight = 0.55–0.85 (depends on trust graph density)
- β (beta) = trust weight = 1.0 - α
- Intent always dominates (α > β always)

### Example: New User (Sparse Trust Graph)
```
Density = 0 edges / 10 = 0.0 (new user)
α = 0.85 (intent dominates)
β = 0.15 (trust helps but secondary)

displacement_score = (0.75 × 0.85) + (0.59 × 0.15)
                   = 0.638 + 0.089
                   = 0.727
```

### Example: Mature User (Dense Trust Graph)
```
Density = 15 edges / 10 = 1.0 (mature user)
α = 0.55 (trust more important now)
β = 0.45

displacement_score = (0.75 × 0.55) + (0.84 × 0.45)
                   = 0.413 + 0.378
                   = 0.791
```

## Score Ranges by Scenario

| Scenario | Component Calculation | Raw Score | Final Score |
|----------|----------------------|-----------|-------------|
| Perfect 1-hop positive today | 0.50+0.24+0.20 | 0.94 | 0.94 |
| Good 1-hop positive old | 0.50+0.24+0.00 | 0.74 | 0.74 |
| Medium 1-hop neutral recent | 0.40+0.03+0.15 | 0.58 | 0.58 |
| Hub fallback positive today | 0.30+0.24+0.20-0.15 | 0.59 | 0.59 |
| Bad 1-hop negative recent | 0.40-0.18+0.20 | 0.42 | 0.42 |
| No trust path at all | — | 0.00 | 0.00 |

## Properties of the Formula

### ✅ Properties Maintained

1. **Additive Independence**
   - Each component independent
   - Low outcome doesn't zero out score

2. **Fair to Hub Nodes**
   - 0.6 synthetic edge → ~0.59 score when positive+recent
   - Competitive with weaker direct paths

3. **Recency Matters**
   - Linear decay (not logarithmic)
   - 180-day window meaningful

4. **Transparent**
   - Each component visible
   - No hidden multiplicative effects
   - Predictable outputs

5. **Bounded**
   - Always [0.0, 0.95]
   - Never negative
   - Capped below intent dominance

6. **Intent Preserves Dominance**
   - Max trust_score = 0.95
   - With β = 0.15: max trust contribution = 0.143
   - Intent still drives ranking

## Comparison: Old vs New

| Aspect | Old (Multiplicative) | New (Additive) |
|--------|---------------------|----------------|
| Formula | `edge × outcome_mod × hop_log` | `(edge×0.5 + outcome×0.3 + recency×0.2) - hop_discount` |
| Hub nodes (0.6) | 0.6 × 1.0 × 0.909 = 0.545 | (0.3 + 0.24 + 0.2) - 0.15 = 0.59 |
| Negative outcome | Severe penalty | Moderate penalty |
| Recency | Logarithmic | Linear |
| Transparency | Opaque | Clear |
| Predictability | Variable | Consistent |

---

**Note**: All components are tuned for restaurants domain. Scaling to other domains (jobs, matrimonial, etc.) may require adjusting weights (0.50, 0.30, 0.20, 0.15).
