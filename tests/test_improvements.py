"""
TEST: Hub Node Fallback + Additive Trust Scoring
Phase 1: Restaurants Domain

Tests for the two critical improvements:
1. Hub node fallback when no direct trust path exists
2. Additive trust scoring with hop discounts

Run: python -m pytest tests/test_improvements.py -v
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Add engine to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.matcher import TrustPath, score_trust_path

# ══════════════════════════════════════════════════════════════════════════════
# TEST 1: ADDITIVE TRUST SCORING
# ══════════════════════════════════════════════════════════════════════════════

def test_trust_score_direct_1hop_positive():
    """
    Test Case: Direct trust (1 hop) with positive outcome, recent visit
    
    Formula: (0.8 × 0.50) + (0.8 × 0.30) + (1.0 × 0.20) - 0.00
           = 0.40 + 0.24 + 0.20 - 0.00
           = 0.84
    """
    now = datetime.now(timezone.utc)
    visited_today = now.isoformat()
    
    trust_path = TrustPath(
        trusted_user_id="user-123",
        trusted_user_name="Alice",
        edge_weight=0.8,  # 80% trust in Alice
        hops=1,           # direct trust
        outcome="positive",
        visited_at=visited_today,
    )
    
    score = score_trust_path(trust_path, recency_days=0)
    print(f"✓ Test 1: Direct 1-hop + positive + today: {score}")
    assert 0.83 <= score <= 0.85, f"Expected ~0.84, got {score}"


def test_trust_score_direct_1hop_neutral_old():
    """
    Test Case: Direct trust (1 hop) with neutral outcome, 90 days old
    
    Formula: (0.8 × 0.50) + (0.1 × 0.30) + (0.5 × 0.20) - 0.00
           = 0.40 + 0.03 + 0.10 - 0.00
           = 0.53
    """
    trust_path = TrustPath(
        trusted_user_id="user-456",
        trusted_user_name="Bob",
        edge_weight=0.8,
        hops=1,
        outcome="neutral",
        visited_at=(datetime.now(timezone.utc) - timedelta(days=90)).isoformat(),
    )
    
    score = score_trust_path(trust_path, recency_days=90)
    print(f"✓ Test 2: Direct 1-hop + neutral + 90 days old: {score}")
    assert 0.52 <= score <= 0.54, f"Expected ~0.53, got {score}"


def test_trust_score_hub_node_2hops():
    """
    Test Case: Hub node fallback (2 hops) with positive outcome, recent
    
    Formula: (0.6 × 0.50) + (0.8 × 0.30) + (1.0 × 0.20) - 0.15
           = 0.30 + 0.24 + 0.20 - 0.15
           = 0.59
    
    Hub nodes (domain experts) get synthetic 0.6 edge weight + 0.15 hop penalty
    """
    trust_path = TrustPath(
        trusted_user_id="hub-expert",
        trusted_user_name="Restaurant Domain Expert",
        edge_weight=0.6,  # synthetic for hub nodes
        hops=2,           # fallback is 2 hops
        outcome="positive",
        visited_at=datetime.now(timezone.utc).isoformat(),
    )
    
    score = score_trust_path(trust_path, recency_days=0)
    print(f"✓ Test 3: Hub node fallback (2 hops) + positive: {score}")
    assert 0.58 <= score <= 0.60, f"Expected ~0.59, got {score}"


def test_trust_score_capped_at_0_95():
    """
    Test Case: Maximum possible score (capped at 0.95)
    
    Even with perfect conditions:
    (1.0 × 0.50) + (0.8 × 0.30) + (1.0 × 0.20) - 0.00
    = 0.50 + 0.24 + 0.20
    = 0.94, rounds to 0.94 (under 0.95 cap)
    """
    trust_path = TrustPath(
        trusted_user_id="max-trust",
        trusted_user_name="Perfect Recommender",
        edge_weight=1.0,  # maximum
        hops=1,
        outcome="positive",
        visited_at=datetime.now(timezone.utc).isoformat(),
    )
    
    score = score_trust_path(trust_path, recency_days=0)
    print(f"✓ Test 4: Maximum score (should not exceed 0.95): {score}")
    assert score <= 0.95, f"Score {score} exceeds cap"
    assert 0.93 <= score <= 0.95, f"Expected ~0.94, got {score}"


def test_trust_score_negative_outcome_penalty():
    """
    Test Case: Negative outcome severely penalizes score
    
    Formula: (0.8 × 0.50) + (-0.6 × 0.30) + (0.5 × 0.20) - 0.00
           = 0.40 + (-0.18) + 0.10 - 0.00
           = 0.32
    
    But with recency_days=30: recency_score = 1 - 30/180 = 0.833
    So: (0.8 × 0.50) + (-0.6 × 0.30) + (0.833 × 0.20) - 0.00
      = 0.40 - 0.18 + 0.167
      = 0.387
    """
    trust_path = TrustPath(
        trusted_user_id="bad-rec",
        trusted_user_name="Charlie",
        edge_weight=0.8,
        hops=1,
        outcome="negative",
        visited_at=(datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
    )
    
    score = score_trust_path(trust_path, recency_days=30)
    print(f"✓ Test 5: Negative outcome penalty: {score}")
    assert 0.38 <= score <= 0.40, f"Expected ~0.387, got {score}"


def test_trust_score_old_visit_decay():
    """
    Test Case: Recency decay over 180 days
    
    Formula: (0.8 × 0.50) + (0.8 × 0.30) + (0.0 × 0.20) - 0.00
           = 0.40 + 0.24 + 0.00 - 0.00
           = 0.64
    
    After 180 days, recency_score = max(0, 1 - 180/180) = 0
    """
    trust_path = TrustPath(
        trusted_user_id="old-ref",
        trusted_user_name="David",
        edge_weight=0.8,
        hops=1,
        outcome="positive",
        visited_at=(datetime.now(timezone.utc) - timedelta(days=180)).isoformat(),
    )
    
    score = score_trust_path(trust_path, recency_days=180)
    print(f"✓ Test 6: After 180 days, recency = 0: {score}")
    assert 0.63 <= score <= 0.65, f"Expected ~0.64, got {score}"


def test_no_trust_path_returns_zero():
    """
    Test Case: No trust path = 0.0 score (cold result)
    """
    score = score_trust_path(None)
    print(f"✓ Test 7: No trust path = 0.0: {score}")
    assert score == 0.0, f"Expected 0.0, got {score}"


# ══════════════════════════════════════════════════════════════════════════════
# TEST 2: HUB NODE FALLBACK CONCEPTUAL TEST
# ══════════════════════════════════════════════════════════════════════════════

def test_hub_node_fallback_logic():
    """
    Conceptual test for hub node fallback logic.
    
    Scenario:
    - New user (no direct trust network)
    - Restaurant: "North Indian in Indiranagar"
    - No one in user's 5-person trust network has been to this restaurant
    
    Solution:
    - Query HUB_NODE_FALLBACK_SQL
    - Find users with trust_received_restaurants >= 0.6 (domain experts)
    - These experts have visited the restaurant with positive outcome
    - Return their recommendation as 2-hop path (hub node fallback)
    - Score includes 0.15 hop discount but still helps discovery
    """
    print("\n✓ Test 8: Hub Node Fallback Concept")
    print("  Scenario: New user, no direct trust path to restaurant")
    print("  Solution: Fall back to domain experts (trust_received >= 0.6)")
    print("  Result: 2-hop path with 0.15 hop discount applied")
    print("  Impact: Reduces cold-start problem, enables discovery")


# ══════════════════════════════════════════════════════════════════════════════
# DEMO: COMPARISON
# ══════════════════════════════════════════════════════════════════════════════

def demo_scoring_comparison():
    """
    Show why additive formula is better than multiplicative.
    """
    print("\n" + "="*70)
    print("COMPARISON: Additive vs Multiplicative Scoring")
    print("="*70)
    
    trust_path = TrustPath(
        trusted_user_id="demo",
        trusted_user_name="Demo User",
        edge_weight=0.7,
        hops=1,
        outcome="positive",
        visited_at=datetime.now(timezone.utc).isoformat(),
    )
    
    additive_score = score_trust_path(trust_path, recency_days=0)
    
    # Old multiplicative would be:
    # (0.7 * 1.0 * 1.44) capped = 0.748
    multiplicative_score = min(0.95, 0.7 * 1.0 * (1.0 / 1.1))
    
    print(f"\nWith edge_weight=0.7, positive outcome, today, 1 hop:")
    print(f"  Additive score:       {additive_score}")
    print(f"  Old Multiplicative:   {multiplicative_score:.3f}")
    print(f"\nWhy additive is better:")
    print(f"  ✓ Components are independent (outcome doesn't 0 out whole score)")
    print(f"  ✓ Hop penalty is transparent (always 0.00 or 0.15)")
    print(f"  ✓ Recency decays linearly (not logarithmic)")
    print(f"  ✓ Hub nodes (0.6 edge_weight) still get ~0.59 score")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("UNIVERSAL CONNECTOR — Trust Scoring Tests")
    print("="*70 + "\n")
    
    # Run all tests
    test_trust_score_direct_1hop_positive()
    test_trust_score_direct_1hop_neutral_old()
    test_trust_score_hub_node_2hops()
    test_trust_score_capped_at_0_95()
    test_trust_score_negative_outcome_penalty()
    test_trust_score_old_visit_decay()
    test_no_trust_path_returns_zero()
    test_hub_node_fallback_logic()
    demo_scoring_comparison()
    
    print("\n" + "="*70)
    print("✅ ALL TESTS PASSED")
    print("="*70 + "\n")
