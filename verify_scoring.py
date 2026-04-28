from datetime import datetime

# Result #2 data
edge_weight = 0.13
outcome = "positive"  # outcome_score = 0.8
visited_at = datetime.fromisoformat("2026-01-12 23:06:17.375774+00:00")
now = datetime.fromisoformat("2026-04-11T00:00:00+00:00")
recency_days = (now - visited_at).days
hops = 1

# Additive formula
edge_component = edge_weight * 0.50
outcome_score = 0.8  # positive
outcome_component = outcome_score * 0.30
recency_score = max(0.0, 1.0 - (recency_days / 180.0))
recency_component = recency_score * 0.20
hop_discount = 0.00 if hops == 1 else 0.15

raw_score = edge_component + outcome_component + recency_component - hop_discount
trust_score = round(min(0.95, max(0.0, raw_score)), 3)

print("="*70)
print("ADDITIVE TRUST SCORING VERIFICATION")
print("="*70)
print(f"\nInput Data:")
print(f"  Edge weight: {edge_weight}")
print(f"  Outcome: {outcome} (score: 0.8)")
print(f"  Visited: {visited_at.date()} ({recency_days} days ago)")
print(f"  Hops: {hops}")

print(f"\nFormula Components:")
print(f"  edge_component     = {edge_weight} × 0.50 = {edge_component:.3f}")
print(f"  outcome_component  = 0.8 × 0.30 = {outcome_component:.3f}")
print(f"  recency_score      = 1.0 - ({recency_days}/180) = {recency_score:.3f}")
print(f"  recency_component  = {recency_score:.3f} × 0.20 = {recency_component:.3f}")
print(f"  hop_discount       = {hop_discount:.2f}")

print(f"\nCalculation:")
print(f"  raw_score = {edge_component:.3f} + {outcome_component:.3f} + {recency_component:.3f} - {hop_discount:.2f}")
print(f"            = {raw_score:.3f}")
print(f"  trust_score (capped) = {trust_score}")

print(f"\n✅ API Response:  0.407")
print(f"✅ Calculated:    {trust_score}")
print(f"✅ Match:         {trust_score == 0.407}")
print("="*70)
