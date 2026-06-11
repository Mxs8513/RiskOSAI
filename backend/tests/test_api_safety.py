"""P4 guardrails: input limits, offset pagination, unknown-intent fallback."""
from .conftest import flag_transaction


def test_unknown_question_returns_suggestions_not_daily_summary(client, seeded, analyst):
    res = client.post("/risk-intelligence/query",
                      json={"question": "what is the meaning of life?"}, headers=analyst)
    assert res.status_code == 200
    body = res.json()
    assert body["intent"] == "unknown"
    assert body["provider"] is None
    assert "couldn't map" in body["answer"].lower() or "try one of these" in body["answer"].lower()
    assert len(body["alternatives"]) > 0


def test_intelligence_question_length_capped(client, seeded, analyst):
    res = client.post("/risk-intelligence/query",
                      json={"question": "x" * 501}, headers=analyst)
    assert res.status_code == 422


def test_developer_scenario_count_capped(client, seeded, developer):
    res = client.post("/developer/generate-scenario",
                      json={"rule_code": "R-001", "count": 999}, headers=developer)
    assert res.status_code == 422


def test_developer_run_scenario_rejects_out_of_range(client, seeded, developer):
    res = client.post("/developer/run-scenario",
                      json={"amount": -5}, headers=developer)
    assert res.status_code == 422


def test_review_note_length_capped(client, seeded, analyst):
    inv = flag_transaction(seeded, "txn_900300")
    res = client.post(f"/investigations/{inv.id}/review",
                      json={"decision": "clear", "note": "x" * 2001}, headers=analyst)
    assert res.status_code == 422


def test_offset_pagination_on_investigations(client, seeded, analyst):
    for i in range(3):
        flag_transaction(seeded, f"txn_90040{i}")

    full = client.get("/investigations?limit=10", headers=analyst).json()
    assert len(full) == 3
    page2 = client.get("/investigations?limit=2&offset=2", headers=analyst).json()
    assert len(page2) == 1
    assert page2[0]["investigation_id"] == full[2]["investigation_id"]


def test_offset_pagination_on_audit_logs(client, seeded, analyst):
    flag_transaction(seeded, "txn_900500")
    all_logs = client.get("/audit-logs?limit=100", headers=analyst).json()["logs"]
    assert len(all_logs) >= 3
    shifted = client.get("/audit-logs?limit=100&offset=1", headers=analyst).json()["logs"]
    assert len(shifted) == len(all_logs) - 1
    assert shifted[0]["id"] == all_logs[1]["id"]


def test_offset_pagination_on_transactions(client, seeded, analyst):
    for i in range(3):
        flag_transaction(seeded, f"txn_90060{i}")
    full = client.get("/transactions?limit=10", headers=analyst).json()
    shifted = client.get("/transactions?limit=10&offset=1", headers=analyst).json()
    assert len(shifted) == len(full) - 1
