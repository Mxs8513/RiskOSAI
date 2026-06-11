"""RBAC enforcement through the live API: 401s, 403s, and override rules."""
from .conftest import flag_transaction


def test_unauthenticated_requests_rejected(client):
    assert client.get("/transactions").status_code == 401
    assert client.get("/metrics/overview").status_code == 401


def test_analyst_blocked_from_manager_only_endpoints(client, analyst):
    assert client.get("/metrics/rules", headers=analyst).status_code == 403
    assert client.patch("/rules/1", json={"status": "disabled"}, headers=analyst).status_code == 403


def test_manager_allowed_on_manager_endpoints(client, manager):
    assert client.get("/metrics/rules", headers=manager).status_code == 200
    res = client.patch("/rules/1", json={"status": "disabled"}, headers=manager)
    assert res.status_code == 200
    assert res.json()["rule_status"] == "disabled"


def test_analyst_blocked_from_developer_console(client, analyst, developer):
    payload = {"rule_code": "R-001", "count": 2}
    assert client.post("/developer/generate-scenario", json=payload, headers=analyst).status_code == 403
    assert client.post("/developer/generate-scenario", json=payload, headers=developer).status_code == 200


def test_analyst_override_blocked_manager_allowed(client, seeded, analyst, manager):
    inv = flag_transaction(seeded)

    first = client.post(f"/investigations/{inv.id}/review",
                        json={"decision": "clear", "note": "looks legitimate"}, headers=analyst)
    assert first.status_code == 200

    # Analyst cannot override a decided case.
    retry = client.post(f"/investigations/{inv.id}/review",
                        json={"decision": "confirm_fraud"}, headers=analyst)
    assert retry.status_code == 403

    # Risk manager can.
    override = client.post(f"/investigations/{inv.id}/review",
                           json={"decision": "confirm_fraud", "note": "card reported stolen"},
                           headers=manager)
    assert override.status_code == 200
    assert override.json()["investigation_status"] == "Confirmed Fraud"

    detail = client.get(f"/investigations/{inv.id}", headers=manager).json()
    assert detail["reviewer_decision"]["decision"] == "confirm_fraud"
    assert any(e["event_type"] == "case_status_overridden" for e in detail["timeline"])
