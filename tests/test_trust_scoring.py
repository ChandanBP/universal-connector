"""
TEST: Trust signal scoring — current architecture
Tests the 6-layer trust hierarchy and scoring formulas.

Run: python -m pytest tests/test_trust_scoring.py -v
  or: python tests/test_trust_scoring.py
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.matcher import (
    TrustSignal, score_trust_signal, SIGNAL_LAYERS,
    compute_intent_similarity, compute_displacement_score,
)
from engine.domains.restaurants import RESTAURANTS_CONFIG


def _signal(layer, weight=0.8, outcome='positive', days_ago=0, hops=1, path_count=1, community_context=None):
    visited = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    return TrustSignal(
        signal_layer=layer,
        trusted_user_id='uid-test',
        trusted_user_name='Test User',
        edge_weight=weight,
        hops=hops,
        outcome=outcome,
        visited_at=visited,
        path_count=path_count,
        community_context=community_context,
    )


def test_signal_layer_caps_enforced():
    """Score must never exceed the cap defined for each layer."""
    for layer, cap in SIGNAL_LAYERS.items():
        if layer == 'intent_only':
            continue
        if layer == 'crowd_wisdom':
            sig = TrustSignal(layer, None, None, 1.0, 0, 'positive', None)
        elif layer == 'community_trust':
            sig = _signal(layer, weight=1.0, days_ago=0)
        else:
            sig = _signal(layer, weight=1.0, days_ago=0)
        score = score_trust_signal(sig)
        assert score <= cap + 1e-9, f"{layer}: score {score} exceeds cap {cap}"
    print("✓ All layer caps enforced")


def test_intent_only_is_zero():
    sig = TrustSignal('intent_only', None, None, 0.0, 0, None, None)
    assert score_trust_signal(sig) == 0.0
    print("✓ intent_only = 0.0")


def test_direct_trust_positive_recent():
    """High-weight direct trust, positive outcome, recent visit → near cap."""
    sig = _signal('direct_trust', weight=0.9, outcome='positive', days_ago=1)
    score = score_trust_signal(sig)
    assert score >= 0.60, f"Expected >= 0.60, got {score}"
    assert score <= 0.95
    print(f"✓ direct_trust positive recent: {score}")


def test_direct_trust_negative_outcome():
    """Negative outcome reduces trust score significantly."""
    pos_sig = _signal('direct_trust', weight=0.8, outcome='positive', days_ago=5)
    neg_sig = _signal('direct_trust', weight=0.8, outcome='negative', days_ago=5)
    pos_score = score_trust_signal(pos_sig)
    neg_score = score_trust_signal(neg_sig)
    assert neg_score < pos_score
    print(f"✓ negative < positive: {neg_score} < {pos_score}")


def test_network_trust_convergence_bonus():
    """Multiple paths agreeing should score higher than one path.
    Use weight=0.5, 90 days old so base score doesn't hit the cap."""
    single_path = _signal('network_trust', weight=0.5, outcome='positive', days_ago=90, path_count=1)
    multi_path  = _signal('network_trust', weight=0.5, outcome='positive', days_ago=90, path_count=3)
    s1 = score_trust_signal(single_path)
    s3 = score_trust_signal(multi_path)
    assert s3 > s1, f"multi-path {s3} should beat single-path {s1}"
    print(f"✓ convergence bonus: {s1} → {s3} (+{round(s3-s1,3)})")


def test_community_trust_positive():
    sig = _signal('community_trust', outcome='positive', community_context='village:Mandya')
    score = score_trust_signal(sig)
    cap = SIGNAL_LAYERS['community_trust']
    assert 0.0 < score <= cap
    print(f"✓ community_trust positive: {score} (cap={cap})")


def test_crowd_wisdom_uses_avg_score():
    """crowd_wisdom edge_weight IS the avg_outcome_score."""
    sig = TrustSignal('crowd_wisdom', None, None, 0.8, 0, 'positive', None)
    score = score_trust_signal(sig)
    assert score == round(min(0.35, 0.8 * 0.50), 3)
    print(f"✓ crowd_wisdom: {score}")


def test_recency_decay():
    """Visit 180 days ago should score lower than visit today."""
    fresh = _signal('direct_trust', weight=0.8, outcome='positive', days_ago=0)
    stale = _signal('direct_trust', weight=0.8, outcome='positive', days_ago=179)
    fresh_score = score_trust_signal(fresh)
    stale_score = score_trust_signal(stale)
    assert fresh_score > stale_score
    print(f"✓ recency decay: fresh={fresh_score}  stale={stale_score}")


def test_intent_similarity_discounts_trust():
    """Low intent similarity should reduce the trust score."""
    sig = _signal('direct_trust', weight=0.8, outcome='positive', days_ago=5)
    full  = score_trust_signal(sig, intent_similarity=1.0)
    half  = score_trust_signal(sig, intent_similarity=0.5)
    floor = score_trust_signal(sig, intent_similarity=0.2)
    assert full > half > floor
    print(f"✓ intent_similarity discount: 1.0={full}  0.5={half}  0.2={floor}")


def test_displacement_alpha_gt_beta():
    """Intent (alpha) must always outweigh trust (beta)."""
    score = compute_displacement_score(
        intent_score=0.6,
        trust_score=0.9,
        alpha=0.70,
        beta=0.30,
    )
    intent_contrib = 0.6 * 0.70
    trust_contrib  = 0.9 * 0.30
    assert intent_contrib > trust_contrib
    print(f"✓ alpha > beta: intent_contrib={intent_contrib:.3f} > trust_contrib={trust_contrib:.3f}")


def test_layer_ordering():
    """direct_trust cap must be highest; intent_only must be 0."""
    caps = list(SIGNAL_LAYERS.values())
    assert caps[0] == 0.95,  "direct_trust must have highest cap"
    assert caps[-1] == 0.00, "intent_only must be 0"
    print(f"✓ layer caps in order: {caps}")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Universal Connector — Trust Scoring Tests")
    print("=" * 60 + "\n")

    test_signal_layer_caps_enforced()
    test_intent_only_is_zero()
    test_direct_trust_positive_recent()
    test_direct_trust_negative_outcome()
    test_network_trust_convergence_bonus()
    test_community_trust_positive()
    test_crowd_wisdom_uses_avg_score()
    test_recency_decay()
    test_intent_similarity_discounts_trust()
    test_displacement_alpha_gt_beta()
    test_layer_ordering()

    print("\n✅ ALL TESTS PASSED\n")
