"""Automated Response Orchestrator: tier routing, pipeline integration,
audit events per route, and orchestrator metrics."""
import pytest

from app import models
from app.pipeline import process_transaction
from app.response_orchestrator import decide_response, response_tier

from .conftest import make_enriched

# Signal combinations that land in each response tier.
LOW = {}                                                                    # 0
MEDIUM = {"is_new_device": True, "velocity_10_min": 5}                      # 40
ELEVATED = {"amount": 900.0, "is_new_device": True, "velocity_10_min": 5}   # 65
HIGH = {"amount": 900.0, "is_new_device": True, "velocity_10_min": 5,
        "transaction_type": "card_not_present"}                             # 75
CRITICAL = {**HIGH, "distance_from_home_miles": 1500}                       # 95


# ---- unit: tier mapping ----

@pytest.mark.parametrize("score,tier", [
    (0, "Low"), (39, "Low"), (40, "Medium"), (59, "Medium"),
    (60, "Elevated"), (74, "Elevated"), (75, "High"), (84, "High"),
    (85, "Critical"), (100, "Critical"),
])
def test_response_tier_boundaries(score, tier):
    assert response_tier(score) == tier


def test_decide_response_low():
    r = decide_response(risk_score=10, risk_level="Low", rules_triggered=[])
    assert r["automation_decision"] == "approved"
    assert r["verification_status"] == "not_required"
    assert r["human_review_required"] is False
    assert r["hold_status"] is False
    assert r["escalation_reason"] is None
    assert r["customer_action_required"] is False


def test_decide_response_medium():
    r = decide_response(risk_score=45, risk_level="Medium", rules_triggered=[])
    assert r["automation_decision"] == "monitored"
    assert r["human_review_required"] is False
    assert r["hold_status"] is False


def test_decide_response_elevated():
    r = decide_response(risk_score=65, risk_level="Medium", rules_triggered=[])
    assert r["automation_decision"] == "verification_required"
    assert r["verification_status"] == "pending_verification"
    assert r["human_review_required"] is False
    assert r["hold_status"] is False
    assert r["customer_action_required"] is True


def test_decide_response_high():
    r = decide_response(risk_score=78, risk_level="High", rules_triggered=[])
    assert r["automation_decision"] == "held_for_verification"
    assert r["verification_status"] == "pending_verification"
    assert r["human_review_required"] is False
    assert r["hold_status"] is True
    assert r["customer_action_required"] is True


def test_decide_response_critical():
    rules = [{"code": "R-001", "name": "Amount Anomaly", "points": 25, "detail": "d"}]
    r = decide_response(risk_score=95, risk_level="Critical", rules_triggered=rules)
    assert r["automation_decision"] == "escalated_to_human_review"
    assert r["verification_status"] == "escalated"
    assert r["human_review_required"] is True
    assert r["hold_status"] is True
    assert "R-001" in r["escalation_reason"]


# ---- pipeline integration ----

def run(db, overrides, txn_id):
    txn, rs, inv = process_transaction(db, make_enriched(id=txn_id, **overrides))
    return txn, rs, inv


def audit_events(db, txn_id):
    return {a.event_type for a in db.query(models.AuditLog).filter_by(transaction_id=txn_id)}


def test_low_risk_auto_approved_no_investigation(seeded):
    txn, rs, inv = run(seeded, LOW, "txn_910001")
    assert rs.score < 40
    assert txn.automation_decision == "approved"
    assert txn.status == "Approved"
    assert txn.human_review_required is False
    assert inv is None
    assert "transaction_auto_approved" in audit_events(seeded, txn.id)


def test_medium_risk_monitored_no_investigation(seeded):
    txn, rs, inv = run(seeded, MEDIUM, "txn_910002")
    assert 40 <= rs.score < 60
    assert txn.automation_decision == "monitored"
    assert txn.status == "Monitoring"
    assert inv is None
    assert "transaction_monitored" in audit_events(seeded, txn.id)


def test_elevated_risk_requires_verification_not_human(seeded):
    txn, rs, inv = run(seeded, ELEVATED, "txn_910003")
    assert 60 <= rs.score < 75
    assert txn.automation_decision == "verification_required"
    assert txn.verification_status == "pending_verification"
    assert txn.status == "Pending Verification"
    assert txn.hold_status is False
    assert txn.human_review_required is False
    assert inv is None, "elevated risk must not open a human investigation"
    assert "verification_required" in audit_events(seeded, txn.id)


def test_high_risk_held_for_verification_not_human(seeded):
    txn, rs, inv = run(seeded, HIGH, "txn_910004")
    assert 75 <= rs.score < 85
    assert txn.automation_decision == "held_for_verification"
    assert txn.hold_status is True
    assert txn.status == "Held for Verification"
    assert txn.human_review_required is False
    assert inv is None, "high risk routes to verification, not human review"
    assert "transaction_held_for_verification" in audit_events(seeded, txn.id)


def test_critical_risk_escalates_and_opens_investigation(seeded):
    txn, rs, inv = run(seeded, CRITICAL, "txn_910005")
    assert rs.score >= 85
    assert txn.automation_decision == "escalated_to_human_review"
    assert txn.human_review_required is True
    assert txn.hold_status is True
    assert txn.escalation_reason and "Critical" in txn.escalation_reason
    assert inv is not None
    events = audit_events(seeded, txn.id)
    assert "critical_escalation" in events
    assert "investigation_created" in events


# ---- metrics ----

def test_orchestrator_metrics(client, seeded, analyst):
    run(seeded, LOW, "txn_910010")
    run(seeded, MEDIUM, "txn_910011")
    run(seeded, ELEVATED, "txn_910012")
    run(seeded, HIGH, "txn_910013")
    run(seeded, CRITICAL, "txn_910014")

    m = client.get("/metrics/overview", headers=analyst).json()
    assert m["transactions_processed"] == 5
    assert m["human_review_required"] == 1
    assert m["automation_rate"] == 0.8          # 4 of 5 handled without a human
    assert m["human_review_avoided"] == 2       # elevated + high
    assert m["verification_required"] == 2      # both pending
    assert m["held_transactions"] == 2          # high + critical
    assert m["critical_escalations"] == 1


def test_txn_api_exposes_orchestrator_fields(client, seeded, analyst):
    run(seeded, HIGH, "txn_910020")
    rows = client.get("/transactions?limit=10", headers=analyst).json()
    row = next(r for r in rows if r["transaction_id"] == "txn_910020")
    assert row["automation_decision"] == "held_for_verification"
    assert row["verification_status"] == "pending_verification"
    assert row["human_review_required"] is False
    assert row["hold_status"] is True
