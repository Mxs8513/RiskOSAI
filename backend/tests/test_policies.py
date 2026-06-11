"""Policy check engine: determinism and individual policy behavior."""
from app.policies import run_policy_check

BASE_KWARGS = dict(
    risk_score=75,
    rules_triggered=[{"code": "R-001", "name": "Amount Anomaly", "points": 25, "detail": "8x average"}],
    ai_text="Amount is 8x the customer's average spend; card-not-present channel.",
    transaction={"transaction_id": "txn_1", "amount": 800.0},
    routed_to_review=True,
)


def test_policy_check_is_deterministic():
    a = run_policy_check(**BASE_KWARGS)
    b = run_policy_check(**BASE_KWARGS)
    assert a == b


def test_all_pass_for_clean_case():
    result = run_policy_check(**BASE_KWARGS)
    assert result["policy_status"] == "Passed"
    assert result["issues"] == []
    assert {c["code"] for c in result["policies_checked"]} == {"POL-001", "POL-002", "POL-003", "POL-004", "POL-005"}


def test_pol001_fails_when_critical_not_routed():
    result = run_policy_check(**{**BASE_KWARGS, "risk_score": 90, "routed_to_review": False})
    assert result["policy_status"] == "Needs Review"
    assert any(i["code"] == "POL-001" for i in result["issues"])


def test_pol002_flags_ungrounded_ai_claims():
    result = run_policy_check(**{**BASE_KWARGS, "ai_text": "Customer has a prior conviction and low credit score."})
    assert any(i["code"] == "POL-002" for i in result["issues"])


def test_pol003_requires_step_up_for_device_plus_velocity():
    rules = [{"code": "R-002", "name": "New Device", "points": 20, "detail": "d"},
             {"code": "R-004", "name": "Transaction Velocity", "points": 20, "detail": "d"}]
    result = run_policy_check(**{**BASE_KWARGS, "rules_triggered": rules})
    pol3 = next(c for c in result["policies_checked"] if c["code"] == "POL-003")
    assert pol3["status"] == "attention"


def test_pol005_flags_protected_attributes():
    result = run_policy_check(**{**BASE_KWARGS, "ai_text": "Flagged due to the customer's gender and location."})
    assert any(i["code"] == "POL-005" for i in result["issues"])


def test_two_issues_mean_failed():
    result = run_policy_check(**{**BASE_KWARGS,
                                 "ai_text": "Customer's race and criminal record were considered.",
                                 })
    assert len(result["issues"]) == 2  # POL-002 + POL-005
    assert result["policy_status"] == "Failed"
