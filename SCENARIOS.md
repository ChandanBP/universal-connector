"""
EXAMPLE SCENARIOS: Hub Node Fallback in Action
Universal Connector — Phase 1

Shows how the new hub node fallback system handles different user situations.
"""

# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO 1: New User with No Direct Trust Path
# ══════════════════════════════════════════════════════════════════════════════

SCENARIO_1 = """
SCENARIO: New User (Day 1)
─────────────────────────────────────────────────────────────────────────────

User:     Priya (new, just joined)
Query:    "quiet cozy cafe in Indiranagar"
Trust Graph: Empty (0 trust edges)

BEFORE (Old System):
────────────────────
1. Parse intent → medium clarity, soft constraints on vibe/noise_level
2. Filter restaurants → 12 candidates matching constraints
3. Find trust path:
   - Query: SELECT ... WHERE from_user_id = priya_id
   - Result: NULL (no trust edges)
   - Mark as "cold_result" = true
4. Score:
   - intent_score: 0.75 (good match)
   - trust_score: 0.0 (cold)
   - displacement: (0.75 × 0.85) + (0.0 × 0.15) = 0.638

Result: Top restaurant based ONLY on intent. No social signal.

AFTER (New System with Hub Node Fallback):
────────────────────────────────────────────
1. Parse intent → same as before
2. Filter restaurants → same 12 candidates
3. Find trust path:
   - Step 1: Query direct trust
     SELECT ... WHERE from_user_id = priya_id
     Result: NULL (no direct edges)
   
   - Step 2: Query hub node fallback
     SELECT u.id, u.name, i.outcome, ...
     FROM users u
     JOIN interactions i ON i.user_id = u.id
       AND i.restaurant_id = "cafe-123"
     WHERE u.trust_received_restaurants >= 0.6
       AND i.outcome IN ('positive', 'neutral')
     ORDER BY u.trust_received_restaurants DESC
     Result: "Roshan" (domain expert, trust_received = 0.82)
   
   - Return: TrustPath(
       trusted_user_id="roshan-456",
       trusted_user_name="Roshan",
       edge_weight=0.6,      # ← synthetic for hub node
       hops=2,               # ← fallback is 2 hops
       outcome="positive",
       visited_at="2025-03-15T10:30:00Z"
     )

4. Score:
   - intent_score: 0.75
   - trust_score: (0.6 × 0.50) + (0.8 × 0.30) + (0.95 × 0.20) - 0.15
                = 0.30 + 0.24 + 0.19 - 0.15
                = 0.58
   - displacement: (0.75 × 0.85) + (0.58 × 0.15) = 0.728

Result: Same cafe, but now backed by Roshan's recommendation.
Explanation: "Roshan (domain expert recommendation) has been here and rated it positive"

Benefit: ✅ 0.728 vs 0.638 — 14% boost from domain expert signal
         ✅ Addresses cold-start
         ✅ Transparent about the fallback
"""

# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO 2: User with Sparse Trust Graph
# ══════════════════════════════════════════════════════════════════════════════

SCENARIO_2 = """
SCENARIO: Sparse Trust Network
─────────────────────────────────────────────────────────────────────────────

User:     Aditya
Query:    "premium business lunch spot"
Trust Graph: 
  ├─ Alice (weight=0.85) — 2 restaurants visited together
  ├─ Bob (weight=0.60) — 1 restaurant, neutral outcome
  └─ Charlie (weight=0.40) — 1 restaurant, bad experience

Candidate: "The Imperial" (premium, business-friendly)

MATCHING LOGIC:
───────────────

Step 3a: Try direct trust path
  SELECT ... FROM trust_edges te
    JOIN interactions i ON ...
    WHERE te.from_user_id = aditya_id
      AND i.restaurant_id = "the-imperial"
  
  Check Alice's visits: No visit to The Imperial
  Check Bob's visits: No visit to The Imperial
  Check Charlie's visits: No visit to The Imperial
  
  Result: NULL (no direct path)

Step 3b: Hub node fallback
  SELECT u.id, u.name, i.outcome, ...
  WHERE u.id != aditya_id
    AND u.trust_received_restaurants >= 0.6
    AND i.restaurant_id = "the-imperial"
  
  Found: "Priya" (trust_received=0.78, visited The Imperial yesterday, rated positive)
  
  Return: TrustPath(
    trusted_user_name="Priya",
    edge_weight=0.6,      # synthetic
    hops=2,               # hub fallback
    outcome="positive",
    visited_at="2025-04-10T13:00:00Z"  # recent!
  )

Step 4: Score trust path
  - edge_component: 0.6 × 0.50 = 0.30
  - outcome_component: 0.8 × 0.30 = 0.24
  - recency_days: 1 day old → recency_score = 0.99
  - recency_component: 0.99 × 0.20 = 0.198
  - hop_discount: 0.15 (2 hops)
  - trust_score = 0.30 + 0.24 + 0.198 - 0.15 = 0.588

Insight: Even 2 hops away, recent positive outcome from expert gives 0.588 score.
         This will rank high in displacement scoring.
"""

# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO 3: Trust Path Scoring Breakdown
# ══════════════════════════════════════════════════════════════════════════════

SCENARIO_3 = """
SCENARIO: Additive Scoring Components
─────────────────────────────────────────────────────────────────────────────

Three restaurants, different trust paths. Same user, same query.

RESTAURANT 1: "The Spice House" (premium North Indian)
─────────────────────────────────────────────────────────
Trust path: Alice (edge_weight=0.85, positive outcome, visited 5 days ago, 1 hop)

intent_score: 0.82 (matches query well)
trust_score breakdown:
  - edge_component:     0.85 × 0.50 = 0.425
  - outcome_component:  0.8 × 0.30 = 0.24
  - recency_score:      1.0 - (5/180) = 0.972
  - recency_component:  0.972 × 0.20 = 0.194
  - hop_discount:       0.00 (1 hop)
  - trust_score = 0.425 + 0.24 + 0.194 - 0.00 = 0.859

displacement_score (α=0.85, β=0.15):
  = (0.82 × 0.85) + (0.859 × 0.15)
  = 0.697 + 0.129
  = 0.826 🏆 RANK 1

RESTAURANT 2: "Pepper Mint" (mid-range North Indian)
──────────────────────────────────────────────────────
Trust path: Bob (edge_weight=0.60, neutral outcome, visited 60 days ago, 1 hop)

intent_score: 0.70 (reasonable match)
trust_score breakdown:
  - edge_component:     0.60 × 0.50 = 0.30
  - outcome_component:  0.1 × 0.30 = 0.03
  - recency_score:      1.0 - (60/180) = 0.667
  - recency_component:  0.667 × 0.20 = 0.133
  - hop_discount:       0.00 (1 hop)
  - trust_score = 0.30 + 0.03 + 0.133 - 0.00 = 0.463

displacement_score (α=0.85, β=0.15):
  = (0.70 × 0.85) + (0.463 × 0.15)
  = 0.595 + 0.069
  = 0.664 🥈 RANK 2

RESTAURANT 3: "Tamarind Cafe" (budget North Indian)
───────────────────────────────────────────────────
Trust path: Roshan (hub node, edge_weight=0.6, positive, today, 2 hops)

intent_score: 0.68 (ok match, different vibe/price)
trust_score breakdown:
  - edge_component:     0.6 × 0.50 = 0.30
  - outcome_component:  0.8 × 0.30 = 0.24
  - recency_score:      1.0 - (0/180) = 1.0
  - recency_component:  1.0 × 0.20 = 0.20
  - hop_discount:       0.15 (2 hops - hub fallback)
  - trust_score = 0.30 + 0.24 + 0.20 - 0.15 = 0.59

displacement_score (α=0.85, β=0.15):
  = (0.68 × 0.85) + (0.59 × 0.15)
  = 0.578 + 0.089
  = 0.667 🥇 TIED with #2!

Notice:
  ✓ Recent recommendation (today) from expert almost beats older weak recommendation
  ✓ Hub node (2 hops) still scores well due to recency
  ✓ Additive formula is fair to all trust paths
  ✓ Hop penalty (0.15) is transparent, not harsh
"""

# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO 4: Cold Result (True Cold, Not Hub Fallback)
# ══════════════════════════════════════════════════════════════════════════════

SCENARIO_4 = """
SCENARIO: True Cold Result (Brand New Restaurant)
─────────────────────────────────────────────────────────────────────────────

User:     Maya
Query:    "Italian in Koramangala"
Restaurant: "Osteria Nuova" (just opened yesterday)

Step 3a: Direct trust path
  Query for any friend who visited Osteria Nuova
  Result: NULL (too new, no one visited yet)

Step 3b: Hub node fallback
  Query for domain experts who visited Osteria Nuova
  Result: NULL (too new, even experts haven't been)

Final: trust_path = None (true cold result)

Scoring:
  - intent_score: 0.88 (perfect match for query)
  - trust_score: 0.0 (no path)
  - displacement: (0.88 × 0.85) + (0.0 × 0.15) = 0.748

Explanation:
  "No one in your trust network has been here yet
   (but it matches what you're looking for)"

This is legitimate cold-start. Eventually:
  - Day 2: Domain expert Alice tries it, rates positive → hub node appears
  - Day 3: Your friend Bob tries it via Osteria → direct trust path appears
"""

if __name__ == "__main__":
    print("\n" + "="*80)
    print("HUB NODE FALLBACK — SCENARIO WALKTHROUGHS")
    print("="*80 + "\n")
    
    print(SCENARIO_1)
    print("\n" + "─"*80 + "\n")
    print(SCENARIO_2)
    print("\n" + "─"*80 + "\n")
    print(SCENARIO_3)
    print("\n" + "─"*80 + "\n")
    print(SCENARIO_4)
    
    print("\n" + "="*80 + "\n")
