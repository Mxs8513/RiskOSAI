"""Risk engine: each rule R-001..R-007, band boundaries, rule toggling, score cap."""
import pytest

from app.risk_engine import band_for_score, score_transaction

from .conftest import make_enriched


def codes(result: dict) -> set:
    return {r["code"] for r in result["rules_triggered"]}


def test_baseline_triggers_nothing():
    result = score_transaction(make_enriched())
    assert result["score"] == 0
    assert result["risk_level"] == "Low"
    assert result["rules_triggered"] == []
    assert result["recommended_action"] == "Approve"


# ---- individual rules ----

def test_r001_amount_anomaly():
    result = score_transaction(make_enriched(amount=501.0, user_avg_amount=100.0))
    assert "R-001" in codes(result)
    assert sum(r["points"] for r in result["rules_triggered"] if r["code"] == "R-001") == 25


def test_r001_requires_strictly_over_5x():
    result = score_transaction(make_enriched(amount=500.0, user_avg_amount=100.0))
    assert "R-001" not in codes(result)


def test_r002_new_device():
    result = score_transaction(make_enriched(is_new_device=True))
    assert codes(result) == {"R-002"}
    assert result["score"] == 20


def test_r003_location_jump():
    assert "R-003" in codes(score_transaction(make_enriched(distance_from_home_miles=501)))
    assert "R-003" not in codes(score_transaction(make_enriched(distance_from_home_miles=500)))


def test_r004_velocity():
    assert "R-004" in codes(score_transaction(make_enriched(velocity_10_min=4)))
    assert "R-004" not in codes(score_transaction(make_enriched(velocity_10_min=3)))


def test_r005_merchant_risk():
    assert "R-005" in codes(score_transaction(make_enriched(merchant_risk_score=0.71)))
    assert "R-005" not in codes(score_transaction(make_enriched(merchant_risk_score=0.70)))


def test_r006_card_not_present():
    result = score_transaction(make_enriched(transaction_type="card_not_present"))
    assert codes(result) == {"R-006"}
    assert result["score"] == 10


def test_r007_dataset_label():
    result = score_transaction(make_enriched(dataset_label=True))
    assert codes(result) == {"R-007"}
    assert result["score"] == 20


# ---- band boundaries ----

@pytest.mark.parametrize("score,expected", [
    (39, "Low"), (40, "Medium"),
    (69, "Medium"), (70, "High"),
    (84, "High"), (85, "Critical"),
    (0, "Low"), (100, "Critical"),
])
def test_band_boundaries(score, expected):
    assert band_for_score(score) == expected


def test_score_capped_at_100():
    result = score_transaction(make_enriched(
        amount=2000.0, user_avg_amount=100.0, is_new_device=True,
        distance_from_home_miles=1500, velocity_10_min=6,
        merchant_risk_score=0.9, transaction_type="card_not_present", dataset_label=True))
    assert result["score"] == 100  # raw sum is 130, clamped
    assert result["risk_level"] == "Critical"
    assert codes(result) == {"R-001", "R-002", "R-003", "R-004", "R-005", "R-006", "R-007"}


def test_disabled_rule_does_not_trigger():
    txn = make_enriched(is_new_device=True, velocity_10_min=5)
    everything = score_transaction(txn, active_rule_codes=None)
    assert codes(everything) == {"R-002", "R-004"}
    only_r004 = score_transaction(txn, active_rule_codes={"R-004"})
    assert codes(only_r004) == {"R-004"}
    assert only_r004["score"] == 20
