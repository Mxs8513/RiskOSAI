"""Hybrid ML + rule-based scoring: fallback, hybrid math, agreement,
orchestrator routing, API exposure, AI evidence, and the model endpoint.

No real model artifact is ever loaded (conftest points ML_MODEL_PATH at a
nonexistent file); ML behavior is exercised with small fakes.
"""
import pytest

from app import ml_model, models
from app.ai import _mock_evidence
from app.ml_model import compute_hybrid_score, predict_fraud_probability, score_agreement
from app.pipeline import process_transaction

from .conftest import make_enriched
from .test_orchestrator import HIGH, LOW


class FakeModel:
    """sklearn-like stub with a fixed positive-class probability."""
    def __init__(self, prob):
        self.prob = prob

    def predict_proba(self, X):
        return [[1 - self.prob, self.prob] for _ in X]


@pytest.fixture()
def ml(monkeypatch):
    """Install a fake trained model returning the given probability."""
    def install(prob):
        monkeypatch.setitem(ml_model._cache, "attempted", True)
        monkeypatch.setitem(ml_model._cache, "artifact", {
            "model": FakeModel(prob), "model_name": "fake",
            "feature_names": ml_model.FEATURE_NAMES, "trained_at": "test", "version": 1})
    return install


# ---- fallback ----

def test_missing_model_predicts_none_and_hybrid_equals_rule(seeded):
    assert ml_model.load_model() is None
    assert predict_fraud_probability(make_enriched()) is None

    txn, rs, _ = process_transaction(seeded, make_enriched(id="txn_930001", **HIGH))
    assert rs.ml_fraud_probability is None
    assert rs.hybrid_score == rs.score          # rules-only fallback
    assert rs.model_rule_agreement is None
    assert txn.automation_decision == "held_for_verification"  # routed on rule score


# ---- hybrid math + agreement ----

def test_hybrid_score_formula():
    assert compute_hybrid_score(76, 0.83) == 80   # 0.6*83 + 0.4*76 = 80.2
    assert compute_hybrid_score(50, None) == 50
    assert compute_hybrid_score(0, 1.0) == 60
    assert compute_hybrid_score(100, 0.0) == 40
    assert 0 <= compute_hybrid_score(100, 1.0) <= 100


@pytest.mark.parametrize("rule,prob,expected", [
    (80, 0.80, "high"),     # diff 0
    (80, 0.65, "high"),     # diff 15 (boundary)
    (80, 0.64, "medium"),   # diff 16
    (80, 0.45, "medium"),   # diff 35 (boundary)
    (80, 0.44, "low"),      # diff 36
    (10, 0.95, "low"),
    (50, None, None),
])
def test_agreement_categories(rule, prob, expected):
    assert score_agreement(rule, prob) == expected


def test_prediction_is_valid_probability(ml):
    ml(0.83)
    p = predict_fraud_probability(make_enriched())
    assert p is not None and 0.0 <= p <= 1.0
    assert p == pytest.approx(0.83)


# ---- orchestrator routing on hybrid ----

def test_orchestrator_routes_on_hybrid_not_rule(seeded, ml):
    # Rule score is 20 (new device only) -> rules alone would approve/monitor.
    # ML says 95% fraud -> hybrid = 0.6*95 + 0.4*20 = 65 -> Elevated tier.
    ml(0.95)
    txn, rs, inv = process_transaction(seeded, make_enriched(id="txn_930002", is_new_device=True))
    assert rs.score == 20
    assert rs.hybrid_score == 65
    assert txn.automation_decision == "verification_required"
    assert inv is None


def test_ml_can_downgrade_rule_critical_to_high(seeded, ml):
    # Rule score 95 (Critical) but ML says 40% -> hybrid = 0.6*40 + 0.4*95 = 62
    ml(0.40)
    txn, rs, inv = process_transaction(
        seeded, make_enriched(id="txn_930003", amount=900.0, is_new_device=True,
                              velocity_10_min=5, distance_from_home_miles=1500,
                              transaction_type="card_not_present"))
    assert rs.score == 95
    assert rs.hybrid_score == 62
    assert rs.model_rule_agreement == "low"
    assert txn.automation_decision == "verification_required"
    assert inv is None  # human review avoided; rules stay visible for audit


def test_investigation_carries_hybrid_score(seeded, ml):
    ml(0.95)
    txn, rs, inv = process_transaction(
        seeded, make_enriched(id="txn_930004", amount=900.0, is_new_device=True,
                              velocity_10_min=5, distance_from_home_miles=1500,
                              transaction_type="card_not_present"))
    # hybrid = 0.6*95 + 0.4*95 = 95 -> Critical -> investigation
    assert inv is not None
    assert inv.risk_score == rs.hybrid_score == 95


# ---- API exposure ----

def test_api_exposes_ml_fields(client, seeded, ml, analyst):
    ml(0.83)
    process_transaction(seeded, make_enriched(id="txn_930010", **HIGH))
    rows = client.get("/transactions?limit=5", headers=analyst).json()
    row = next(r for r in rows if r["transaction_id"] == "txn_930010")
    assert row["rule_score"] == 75
    assert row["ml_fraud_probability"] == pytest.approx(0.83)
    assert row["hybrid_score"] == 80
    assert row["model_rule_agreement"] == "high"
    assert row["routing_score_basis"] == "hybrid"


def test_api_fields_safe_without_model(client, seeded, analyst):
    process_transaction(seeded, make_enriched(id="txn_930011", **LOW))
    rows = client.get("/transactions?limit=5", headers=analyst).json()
    row = next(r for r in rows if r["transaction_id"] == "txn_930011")
    assert row["ml_fraud_probability"] is None
    assert row["hybrid_score"] == row["rule_score"]
    assert row["routing_score_basis"] == "rule"


# ---- AI evidence ----

def test_mock_evidence_includes_ml_fields():
    ctx = {
        "transaction": {"transaction_id": "txn_x", "amount": 800.0, "transaction_type": "card_not_present",
                        "is_new_device": True, "velocity_10_min": 5, "distance_from_home_miles": 10,
                        "merchant_risk_score": 0.2, "device_id": "dev_1", "user_avg_amount": 100.0},
        "merchant": {"name": "Test Mart", "category": "retail"},
        "risk_score": 76, "risk_level": "High",
        "ml_fraud_probability": 0.83, "hybrid_score": 80, "model_rule_agreement": "high",
        "rules_triggered": [{"code": "R-001", "name": "Amount Anomaly", "points": 25, "detail": "8x avg"}],
        "recommended_action": "Hold for review",
    }
    packet = _mock_evidence(ctx)
    assert any("83%" in b and "hybrid score 80" in b for b in packet["evidence_bullets"])
    assert "high agreement" in packet["risk_summary"]


def test_mock_evidence_omits_ml_when_unavailable():
    ctx = {
        "transaction": {"transaction_id": "txn_x", "amount": 800.0, "transaction_type": "card_present",
                        "is_new_device": False, "velocity_10_min": 1, "distance_from_home_miles": 10,
                        "merchant_risk_score": 0.2, "device_id": "dev_1", "user_avg_amount": 100.0},
        "merchant": {"name": "Test Mart", "category": "retail"},
        "risk_score": 76, "risk_level": "High",
        "ml_fraud_probability": None, "hybrid_score": 76, "model_rule_agreement": None,
        "rules_triggered": [], "recommended_action": "Hold for review",
    }
    packet = _mock_evidence(ctx)
    assert "ML" not in packet["risk_summary"]


# ---- model metrics endpoint ----

def test_model_endpoint_unavailable_without_artifact(client, seeded, analyst):
    res = client.get("/metrics/model", headers=analyst)
    assert res.status_code == 200
    assert res.json()["available"] is False


def test_model_endpoint_structure_with_metadata(client, seeded, ml, analyst, monkeypatch):
    ml(0.83)
    fake_meta = {"model_name": "random_forest", "trained_at": "t",
                 "dataset": {"n_samples": 8000, "fraud_rate": 0.12},
                 "metrics": {"accuracy": 0.97, "precision": 0.9, "recall": 0.88,
                             "f1": 0.89, "roc_auc": 0.99, "confusion_matrix": [[1700, 60], [30, 210]]}}
    monkeypatch.setattr("app.ml_model.get_model_metadata", lambda: fake_meta)
    process_transaction(seeded, make_enriched(id="txn_930020", **HIGH))

    body = client.get("/metrics/model", headers=analyst).json()
    assert body["available"] is True
    assert body["metadata"]["metrics"]["roc_auc"] == 0.99
    live = body["live"]
    assert live["transactions_scored_by_ml"] == 1
    assert live["agreement_distribution"]["high"] == 1
