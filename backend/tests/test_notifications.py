"""Phase 2: notification events + outbound SMS verification (Twilio mocked).

No real network calls — `_send_via_twilio` is monkeypatched everywhere.
"""
import pytest

from app import communications, models
from app.pipeline import process_transaction

from .conftest import make_enriched
from .test_orchestrator import CRITICAL, ELEVATED, HIGH, LOW, MEDIUM

DEMO_PHONE = "+15551230199"


@pytest.fixture()
def sms_enabled(monkeypatch):
    """Twilio fully configured + enabled, with the network call captured."""
    calls = []
    monkeypatch.setattr(communications.settings, "sms_enabled", True)
    monkeypatch.setattr(communications.settings, "twilio_account_sid", "ACtest")
    monkeypatch.setattr(communications.settings, "twilio_auth_token", "token")
    monkeypatch.setattr(communications.settings, "twilio_from_number", "+15550000001")
    monkeypatch.setattr(communications.settings, "demo_customer_phone", DEMO_PHONE)
    monkeypatch.setattr(communications, "_send_via_twilio",
                        lambda to, body: calls.append((to, body)) or "SMtest123")
    return calls


def run(db, overrides, txn_id):
    return process_transaction(db, make_enriched(id=txn_id, **overrides))


def events_for(db, txn_id):
    return db.query(models.NotificationEvent).filter_by(transaction_id=txn_id).all()


def audit_types(db, txn_id):
    return {a.event_type for a in db.query(models.AuditLog).filter_by(transaction_id=txn_id)}


# ---- event creation per tier ----

def test_elevated_creates_notification_event(seeded):
    txn, _, _ = run(seeded, ELEVATED, "txn_920001")
    evs = events_for(seeded, txn.id)
    assert len(evs) == 1
    assert evs[0].channel == "sms" and evs[0].provider == "twilio"
    assert "Reply YES or NO" in evs[0].message_body
    assert "verification_sms_queued" in audit_types(seeded, txn.id)


def test_high_creates_notification_event(seeded):
    txn, _, _ = run(seeded, HIGH, "txn_920002")
    assert len(events_for(seeded, txn.id)) == 1


def test_low_and_medium_create_no_notification(seeded):
    t1, _, _ = run(seeded, LOW, "txn_920003")
    t2, _, _ = run(seeded, MEDIUM, "txn_920004")
    assert events_for(seeded, t1.id) == []
    assert events_for(seeded, t2.id) == []


def test_critical_creates_no_sms_goes_straight_to_human(seeded):
    txn, _, inv = run(seeded, CRITICAL, "txn_920005")
    assert inv is not None
    assert events_for(seeded, txn.id) == []


# ---- template ----

def test_message_is_strict_template(seeded):
    txn, _, _ = run(seeded, ELEVATED, "txn_920010")
    ev = events_for(seeded, txn.id)[0]
    assert ev.message_body == (
        f"Northstar Financial: Did you attempt a ${txn.amount:,.2f} transaction at "
        f"Test Mart in {txn.city}, {txn.state}? Reply YES or NO.")


# ---- delivery paths ----

def test_disabled_sms_stays_queued_without_crashing(seeded):
    txn, _, _ = run(seeded, HIGH, "txn_920020")
    ev = events_for(seeded, txn.id)[0]
    assert ev.status == "queued"
    assert ev.meta["reason"] == "sms_disabled"
    assert "verification_sms_sent" not in audit_types(seeded, txn.id)


def test_missing_twilio_config_stays_queued_without_crashing(seeded, monkeypatch):
    monkeypatch.setattr(communications.settings, "sms_enabled", True)
    txn, _, _ = run(seeded, HIGH, "txn_920021")
    ev = events_for(seeded, txn.id)[0]
    assert ev.status == "queued"
    assert ev.meta["reason"] == "twilio_not_configured"


def test_enabled_sms_sends_and_audits(seeded, sms_enabled):
    txn, _, _ = run(seeded, HIGH, "txn_920022")
    ev = events_for(seeded, txn.id)[0]
    assert ev.status == "sent"
    assert ev.provider_message_id == "SMtest123"
    assert ev.sent_at is not None
    assert "verification_sms_sent" in audit_types(seeded, txn.id)


def test_sms_only_ever_goes_to_demo_phone(seeded, sms_enabled):
    run(seeded, ELEVATED, "txn_920023")
    run(seeded, HIGH, "txn_920024")
    assert len(sms_enabled) == 2
    assert all(to == DEMO_PHONE for to, _ in sms_enabled)


def test_provider_failure_marks_failed_and_audits(seeded, sms_enabled, monkeypatch):
    def boom(to, body):
        raise RuntimeError("twilio down")
    monkeypatch.setattr(communications, "_send_via_twilio", boom)
    txn, _, _ = run(seeded, HIGH, "txn_920025")
    ev = events_for(seeded, txn.id)[0]
    assert ev.status == "failed"
    assert ev.meta == {"error": "RuntimeError"}  # class name only, no secrets
    assert "verification_sms_failed" in audit_types(seeded, txn.id)


# ---- API ----

def test_phone_is_masked_in_api(client, seeded, sms_enabled, analyst):
    run(seeded, HIGH, "txn_920030")
    rows = client.get("/notifications?transaction_id=txn_920030", headers=analyst).json()
    assert rows[0]["to_phone_masked"] == "***-***-0199"
    assert DEMO_PHONE not in str(rows)


def test_list_filters_and_pagination(client, seeded, analyst):
    for i in range(3):
        run(seeded, ELEVATED, f"txn_92004{i}")
    all_rows = client.get("/notifications?limit=10", headers=analyst).json()
    assert len(all_rows) == 3
    page = client.get("/notifications?limit=2&offset=2", headers=analyst).json()
    assert len(page) == 1
    queued = client.get("/notifications?status=queued", headers=analyst).json()
    assert len(queued) == 3
    assert client.get("/notifications?status=sent", headers=analyst).json() == []


def test_manual_send_requires_developer_or_admin(client, seeded, analyst, manager, developer):
    txn, _, _ = run(seeded, HIGH, "txn_920050")
    url = f"/notifications/send-verification/{txn.id}"
    assert client.post(url, headers=analyst).status_code == 403
    assert client.post(url, headers=manager).status_code == 403
    res = client.post(url, headers=developer)
    assert res.status_code == 200
    assert res.json()["status"] in ("queued", "sent")


def test_manual_send_rejects_ineligible_transaction(client, seeded, developer):
    txn, _, _ = run(seeded, LOW, "txn_920051")
    res = client.post(f"/notifications/send-verification/{txn.id}", headers=developer)
    assert res.status_code == 422
