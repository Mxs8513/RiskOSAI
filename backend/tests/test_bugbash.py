"""Bug-bash regression tests: sort-direction bugs in Risk Intelligence,
answer/data consistency, input validation, empty-DB metrics, and ML edge cases.
"""
import json

import pytest

from app import ml_model, models
from app.ai import _mock_intel_summary
from app.ml_model import compute_hybrid_score, predict_fraud_probability
from app.pipeline import process_transaction
from app.routers.intelligence import classify_intent, retrieve

from .conftest import flag_transaction, make_enriched


# ---- merchant ranking direction (the reported bug) ----

@pytest.mark.parametrize("question,direction", [
    ("What merchants had the lowest average risk score?", "asc"),
    ("Which merchants are the least risky?", "asc"),
    ("Show me the safest merchants", "asc"),
    ("Which merchants had the highest average risk score?", "desc"),
    ("What are the riskiest merchants?", "desc"),
    ("Show merchant risk ranking", "desc"),
])
def test_merchant_direction_classified(question, direction):
    intent, params = classify_intent(question)
    assert intent == "merchant_risk_ranking"
    assert params["direction"] == direction


def seed_merchant_spread(db):
    """Three merchants with clearly different risk profiles, ≥3 txns each."""
    for i, risk in enumerate([0.05, 0.4, 0.9]):
        db.add(models.Merchant(id=f"mer_b{i}", name=f"Merchant {('Low', 'Mid', 'High')[i]}",
                               category="retail", city="Dallas", state="TX", merchant_risk_score=risk))
    db.commit()
    n = 0
    for i, overrides in enumerate([{}, {"velocity_10_min": 4}, {"amount": 900.0, "is_new_device": True, "velocity_10_min": 5}]):
        for _ in range(3):
            process_transaction(db, make_enriched(id=f"txn_95{i}{n:02d}", merchant_id=f"mer_b{i}", **overrides))
            n += 1


def test_lowest_merchants_sorted_ascending(seeded):
    seed_merchant_spread(seeded)
    records, sources = retrieve(seeded, "merchant_risk_ranking", {"direction": "asc"})
    scores = [r["avg_risk_score"] for r in records]
    assert scores == sorted(scores), "lowest-first query must return ascending order"
    # answer wording must match the data direction
    answer = _mock_intel_summary("lowest", "merchant_risk_ranking", records)
    assert answer.startswith("Lowest")


def test_highest_merchants_sorted_descending(seeded):
    seed_merchant_spread(seeded)
    records, sources = retrieve(seeded, "merchant_risk_ranking", {"direction": "desc"})
    scores = [r["avg_risk_score"] for r in records]
    assert scores == sorted(scores, reverse=True)
    answer = _mock_intel_summary("highest", "merchant_risk_ranking", records)
    assert answer.startswith("Highest")


def test_sources_match_records(seeded):
    seed_merchant_spread(seeded)
    records, sources = retrieve(seeded, "merchant_risk_ranking", {"direction": "asc"})
    assert [s["id"] for s in sources] == [r["merchant_id"] for r in records]


def test_end_to_end_lowest_query(client, seeded, analyst):
    seed_merchant_spread(seeded)
    res = client.post("/risk-intelligence/query",
                      json={"question": "What merchants had the lowest average risk score?"},
                      headers=analyst)
    body = res.json()
    assert body["intent"] == "merchant_risk_ranking"
    scores = [r["avg_risk_score"] for r in body["records"]]
    assert scores == sorted(scores)
    assert "Lowest" in body["answer"]
    assert "Highest" not in body["answer"]


# ---- rule performance direction ----

def test_rule_performance_direction_wording(seeded):
    flag_transaction(seeded, "txn_950100")  # triggers several rules once each + extras
    process_transaction(seeded, make_enriched(id="txn_950101", transaction_type="card_not_present"))
    asc_records, _ = retrieve(seeded, "rule_performance", {"direction": "asc"})
    desc_records, _ = retrieve(seeded, "rule_performance", {"direction": "desc"})
    assert [r["trigger_count"] for r in asc_records] == sorted(r["trigger_count"] for r in asc_records)
    assert [r["trigger_count"] for r in desc_records] == sorted((r["trigger_count"] for r in desc_records), reverse=True)
    assert "least-triggered" in _mock_intel_summary("q", "rule_performance", asc_records)
    assert "most-triggered" in _mock_intel_summary("q", "rule_performance", desc_records)


# ---- answer must not contradict data ----

def test_transaction_lookup_flag_wording_uses_routing_score(seeded):
    # rule 20 + fake ML 0.95 -> hybrid 65 -> routed to verification (flagged)
    artifact = {"model": type("M", (), {"predict_proba": lambda self, X: [[0.05, 0.95]]})(),
                "model_name": "fake", "feature_names": ml_model.FEATURE_NAMES,
                "trained_at": "t", "version": 1}
    ml_model._cache.update({"attempted": True, "artifact": artifact})
    try:
        process_transaction(seeded, make_enriched(id="txn_950200", is_new_device=True))
        records, _ = retrieve(seeded, "transaction_lookup", {"transaction_id": "txn_950200"})
        answer = _mock_intel_summary("why", "transaction_lookup", records)
        assert records[0]["hybrid_score"] == 65
        assert "flagged for verification" in answer
        assert "not flagged" not in answer
    finally:
        ml_model._cache.update({"attempted": True, "artifact": None})


def test_unsupported_query_does_not_hallucinate(client, seeded, analyst):
    res = client.post("/risk-intelligence/query",
                      json={"question": "tell me a joke about pirates"}, headers=analyst)
    body = res.json()
    assert body["intent"] == "unknown"
    assert body["records"] == [] and body["sources"] == []


# ---- auth edge cases ----

def test_garbage_and_expired_tokens_rejected(client, seeded):
    import time

    import jwt as pyjwt
    assert client.get("/transactions",
                      headers={"Authorization": "Bearer not-a-jwt"}).status_code == 401
    expired = pyjwt.encode({"sub": "1", "role": "fraud_analyst", "exp": int(time.time()) - 60},
                           "test-secret", algorithm="HS256")
    assert client.get("/transactions",
                      headers={"Authorization": f"Bearer {expired}"}).status_code == 401
    wrong_secret = pyjwt.encode({"sub": "1", "role": "admin", "exp": int(time.time()) + 600},
                                "attacker-secret", algorithm="HS256")
    assert client.get("/transactions",
                      headers={"Authorization": f"Bearer {wrong_secret}"}).status_code == 401


# ---- input validation ----

def test_invalid_since_returns_422_not_500(client, seeded, analyst):
    res = client.get("/transactions?since=not-a-date", headers=analyst)
    assert res.status_code == 422


# ---- empty-DB metrics safety ----

def test_overview_empty_db_no_division_errors(client, seeded, analyst):
    m = client.get("/metrics/overview", headers=analyst).json()
    assert m["transactions_processed"] == 0
    assert m["false_positive_rate"] == 0.0
    assert m["reviewer_agreement_rate"] == 0.0
    assert m["automation_rate"] == 0.0
    assert m["avg_review_seconds"] == 0.0
    assert m["most_triggered_rule"] is None


def test_charts_empty_db(client, seeded, analyst):
    c = client.get("/metrics/charts", headers=analyst).json()
    assert len(c["daily_trend"]) == 7
    assert c["score_distribution"] == []
    assert c["top_risk_merchants"] == []


def test_daily_summary_empty_db_no_none_in_text(client, seeded, analyst):
    res = client.get("/metrics/daily-summary", headers=analyst)
    assert res.status_code == 200
    assert "None" not in res.json()["summary"]


# ---- ML edge cases ----

def test_hybrid_extremes():
    assert compute_hybrid_score(0, 0.0) == 0
    assert compute_hybrid_score(100, 1.0) == 100
    assert compute_hybrid_score(0, 1.0) == 60
    assert compute_hybrid_score(100, 0.0) == 40


def test_prediction_clamped_to_unit_interval():
    artifact = {"model": type("M", (), {"predict_proba": lambda self, X: [[-0.5, 1.5]]})(),
                "model_name": "fake", "feature_names": ml_model.FEATURE_NAMES,
                "trained_at": "t", "version": 1}
    ml_model._cache.update({"attempted": True, "artifact": artifact})
    try:
        p = predict_fraud_probability(make_enriched())
        assert p == 1.0
    finally:
        ml_model._cache.update({"attempted": True, "artifact": None})


def test_malformed_model_metadata_returns_none(tmp_path, monkeypatch):
    bad = tmp_path / "model_metrics.json"
    bad.write_text("{not valid json")
    monkeypatch.setattr(ml_model, "METRICS_PATH", bad)
    assert ml_model.get_model_metadata() is None


def test_model_endpoint_with_malformed_metadata(client, seeded, analyst, tmp_path, monkeypatch):
    bad = tmp_path / "model_metrics.json"
    bad.write_text("{broken")
    monkeypatch.setattr(ml_model, "METRICS_PATH", bad)
    res = client.get("/metrics/model", headers=analyst)
    assert res.status_code == 200
    assert res.json()["available"] is False


def test_feature_mismatch_artifact_rejected(tmp_path, monkeypatch):
    import pickle
    artifact_path = tmp_path / "fraud_model.pkl"
    with open(artifact_path, "wb") as f:
        pickle.dump({"model": None, "feature_names": ["wrong"], "trained_at": "t"}, f)
    monkeypatch.setattr(ml_model, "MODEL_PATH", artifact_path)
    ml_model._cache.update({"attempted": False, "artifact": None})
    try:
        assert ml_model.load_model(force=True) is None
        assert predict_fraud_probability(make_enriched()) is None
    finally:
        ml_model._cache.update({"attempted": True, "artifact": None})
