"""Risk Intelligence: intent classification and the query endpoint (mock AI)."""
import pytest

from app.routers.intelligence import classify_intent

from .conftest import flag_transaction


@pytest.mark.parametrize("question,intent", [
    ("Why was txn_800012 flagged?", "transaction_lookup"),
    ("Show the audit trail for inv_100003", "audit_log_search"),
    ("Which fraud rule caused the most false positives?", "false_positive_analysis"),
    ("Show cases where AI recommended hold but the reviewer cleared it.", "reviewer_outcome_analysis"),
    ("Which merchants had the highest average risk score?", "merchant_risk_ranking"),
    ("How is each rule performing?", "rule_performance"),
    ("Show critical-risk cases from today.", "investigation_search"),
    ("Show recent audit events for inv_100003", "audit_log_search"),
    ("Generate a daily fraud operations summary.", "operations_summary"),
])
def test_intent_classification(question, intent):
    assert classify_intent(question)[0] == intent


def test_transaction_lookup_extracts_id():
    intent, params = classify_intent("Why was txn_800012 flagged?")
    assert params["transaction_id"] == "txn_800012"
    assert params["explain_routing"] is True


def test_query_endpoint_returns_grounded_answer(client, seeded, analyst):
    inv = flag_transaction(seeded, "txn_900200")

    res = client.post("/risk-intelligence/query",
                      json={"question": f"Why was {inv.transaction_id} flagged?"}, headers=analyst)
    assert res.status_code == 200
    body = res.json()
    assert body["intent"] == "transaction_lookup"
    assert body["provider"] == "mock"
    assert inv.transaction_id in body["answer"]
    assert {"type": "transaction", "id": inv.transaction_id} in body["sources"]


def test_daily_summary_query(client, seeded, analyst):
    res = client.post("/risk-intelligence/query",
                      json={"question": "Generate a daily fraud operations summary."}, headers=analyst)
    assert res.status_code == 200
    body = res.json()
    assert body["intent"] == "operations_summary"
    assert body["params"]["timeframe"] == "today"
    assert body["answer"].startswith("Daily fraud operations summary")


def test_suggestions_require_auth(client):
    assert client.get("/risk-intelligence/suggestions").status_code == 401
