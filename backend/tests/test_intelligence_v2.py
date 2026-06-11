"""Risk Intelligence v2: broad NL coverage, parameterized intents, timeframes,
unsafe-request blocking, clarification fallback, and grounded answers."""
import pytest

from app import models
from app.pipeline import process_transaction
from app.routers.intelligence import classify_intent, retrieve

from .conftest import flag_transaction, make_enriched


# ---- intent routing: natural variations ----

@pytest.mark.parametrize("question,intent", [
    ("Generate a weekly fraud operations summary", "operations_summary"),
    ("summary for this week", "operations_summary"),
    ("what happened this week in fraud ops", "operations_summary"),
    ("monthly fraud report", "operations_summary"),
    ("show me risky merchants", "merchant_risk_ranking"),
    ("safest merchants", "merchant_risk_ranking"),
    ("least risky merchants", "merchant_risk_ranking"),
    ("which rule is noisy", "false_positive_analysis"),
    ("which rule has most false positives", "false_positive_analysis"),
    ("show cleared cases", "investigation_search"),
    ("which critical cases are still open", "investigation_search"),
    ("how many transactions were automated", "automation_metrics_question"),
    ("how often did ML disagree with rules", "model_performance_question"),
    ("what is model recall", "model_performance_question"),
    ("show Twilio failures", "notification_status_question"),
    ("show notification failures", "notification_status_question"),
    ("show audit events for transaction txn_800012", "audit_log_search"),
    ("why was txn_800012 routed this way", "transaction_lookup"),
])
def test_natural_variations(question, intent):
    assert classify_intent(question)[0] == intent


def test_parameter_extraction():
    _, p = classify_intent("Generate a weekly fraud operations summary")
    assert p["timeframe"] == "this_week"
    _, p = classify_intent("top 5 safest merchants")
    assert p["direction"] == "asc" and p["limit"] == 5
    _, p = classify_intent("show open critical cases")
    assert p["status"] == "Open" and p["risk_tier"] == "Critical"
    _, p = classify_intent("show notification failures")
    assert p["status"] == "failed"
    _, p = classify_intent("show audit events for transaction txn_800012")
    assert p["transaction_id"] == "txn_800012"


def test_summary_defaults_to_last_7_days():
    intent, p = classify_intent("summarize fraud operations")
    assert intent == "operations_summary"
    assert p["timeframe"] == "last_7_days"
    assert p["timeframe_explicit"] is False


# ---- unsafe requests blocked ----

@pytest.mark.parametrize("question", [
    "delete all fraud cases",
    "approve all transactions",
    "clear all investigations",
    "send SMS to every customer",
    "show me secrets",
    "what is the api key",
    "write SQL to delete audit logs",
    "drop table transactions",
    "wipe the audit logs",
    "override the risk score for txn_800001",
])
def test_unsafe_requests_classified(question):
    intent, params = classify_intent(question)
    assert intent == "unsafe_destructive_request", question


def test_unsafe_request_blocked_via_api(client, seeded, analyst):
    res = client.post("/risk-intelligence/query",
                      json={"question": "delete all fraud cases"}, headers=analyst)
    body = res.json()
    assert body["blocked"] is True
    assert body["intent"] == "unsafe_destructive_request"
    assert "can't perform destructive actions" in body["answer"]
    assert len(body["alternatives"]) > 0
    assert body["records"] == [] and body["sources"] == []
    # blocked attempt is audit logged
    blocked = [a for a in seeded.query(models.AuditLog).all() if "BLOCKED" in a.message]
    assert len(blocked) == 1


# ---- timeframe correctness ----

def test_weekly_summary_answer_reflects_timeframe(client, seeded, analyst):
    flag_transaction(seeded, "txn_960001")
    res = client.post("/risk-intelligence/query",
                      json={"question": "Generate a weekly fraud operations summary"}, headers=analyst)
    body = res.json()
    assert body["intent"] == "operations_summary"
    assert body["params"]["timeframe"] == "this_week"
    assert body["answer"].startswith("Weekly fraud operations summary")
    assert body["records"][0]["timeframe"] == "this_week"


def test_windowed_summary_excludes_old_transactions(seeded):
    from datetime import datetime, timedelta

    # one recent, one 20 days old
    process_transaction(seeded, make_enriched(id="txn_960010"))
    old_txn, _, _ = process_transaction(seeded, make_enriched(id="txn_960011"))
    old_txn.timestamp = datetime.utcnow() - timedelta(days=20)
    seeded.commit()

    week, _ = retrieve(seeded, "operations_summary", {"timeframe": "last_7_days"})
    alltime, _ = retrieve(seeded, "operations_summary", {"timeframe": "all_time"})
    assert week[0]["transactions"] == 1
    assert alltime[0]["transactions"] == 2


# ---- new retrieval intents ----

def test_investigation_search_filters_status(client, seeded, analyst):
    inv1 = flag_transaction(seeded, "txn_960020")
    flag_transaction(seeded, "txn_960021")
    client.post(f"/investigations/{inv1.id}/review", json={"decision": "clear"}, headers=analyst)

    res = client.post("/risk-intelligence/query",
                      json={"question": "show cleared cases"}, headers=analyst).json()
    assert res["intent"] == "investigation_search"
    assert len(res["records"]) == 1
    assert res["records"][0]["status"] == "Cleared"
    assert "Cleared" in res["answer"]

    res = client.post("/risk-intelligence/query",
                      json={"question": "which critical cases are still open"}, headers=analyst).json()
    assert all(r["status"] == "Open" and r["risk_level"] == "Critical" for r in res["records"])


def test_automation_metrics_question(client, seeded, analyst):
    process_transaction(seeded, make_enriched(id="txn_960030"))           # approved
    flag_transaction(seeded, "txn_960031")                                # critical
    res = client.post("/risk-intelligence/query",
                      json={"question": "how many transactions were automated"}, headers=analyst).json()
    rec = res["records"][0]
    assert rec["transactions_processed"] == 2
    assert rec["human_review_required"] == 1
    assert "50%" in res["answer"]


def test_model_performance_question_without_model(client, seeded, analyst):
    res = client.post("/risk-intelligence/query",
                      json={"question": "what is model recall"}, headers=analyst).json()
    assert res["intent"] == "model_performance_question"
    assert res["records"][0]["model_available"] is False
    assert "rules-only" in res["answer"]


def test_notification_failures_question(client, seeded, analyst, monkeypatch):
    from app import communications
    monkeypatch.setattr(communications.settings, "sms_enabled", True)
    monkeypatch.setattr(communications.settings, "twilio_account_sid", "AC")
    monkeypatch.setattr(communications.settings, "twilio_auth_token", "t")
    monkeypatch.setattr(communications.settings, "twilio_from_number", "+15550000001")
    monkeypatch.setattr(communications.settings, "demo_customer_phone", "+15551230199")
    monkeypatch.setattr(communications, "_send_via_twilio",
                        lambda to, body: (_ for _ in ()).throw(RuntimeError("down")))
    process_transaction(seeded, make_enriched(id="txn_960040", amount=900.0, is_new_device=True,
                                              velocity_10_min=5, transaction_type="card_not_present"))

    res = client.post("/risk-intelligence/query",
                      json={"question": "show notification failures"}, headers=analyst).json()
    assert res["intent"] == "notification_status_question"
    assert len(res["records"]) == 1
    assert res["records"][0]["status"] == "failed"
    assert "failed" in res["answer"]


def test_audit_search_by_transaction(client, seeded, analyst):
    flag_transaction(seeded, "txn_960050")
    res = client.post("/risk-intelligence/query",
                      json={"question": "show audit events for transaction txn_960050"}, headers=analyst).json()
    assert res["intent"] == "audit_log_search"
    assert len(res["records"]) >= 3
    assert all(r["transaction_id"] == "txn_960050" for r in res["records"])


def test_routing_explanation_lookup(client, seeded, analyst):
    flag_transaction(seeded, "txn_960060")
    res = client.post("/risk-intelligence/query",
                      json={"question": "why was txn_960060 routed this way"}, headers=analyst).json()
    assert res["intent"] == "transaction_lookup"
    rec = res["records"][0]
    assert rec["automation_decision"] == "escalated_to_human_review"
    assert "flagged" in res["answer"]


# ---- clarification fallback ----

def test_related_query_gets_clarification_not_failure(client, seeded, analyst):
    res = client.post("/risk-intelligence/query",
                      json={"question": "how risky are we doing"}, headers=analyst).json()
    assert res["intent"] == "related_clarification"
    assert res["confidence"] == "low"
    assert len(res["alternatives"]) >= 2
    assert res["blocked"] is False


def test_totally_unknown_query(client, seeded, analyst):
    res = client.post("/risk-intelligence/query",
                      json={"question": "what's the weather in tokyo"}, headers=analyst).json()
    assert res["intent"] == "unknown"
    assert res["records"] == []


# ---- grounding: empty data says so ----

def test_empty_db_answers_safely(client, seeded, analyst):
    res = client.post("/risk-intelligence/query",
                      json={"question": "show me risky merchants"}, headers=analyst).json()
    assert "No matching records" in res["answer"]
    assert res["records"] == []
