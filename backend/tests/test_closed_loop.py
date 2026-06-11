"""Closed loop: reviewer decisions feed back into metrics and rule stats."""
from .conftest import flag_transaction


def overview(client, headers) -> dict:
    res = client.get("/metrics/overview", headers=headers)
    assert res.status_code == 200
    return res.json()


def test_clear_decision_updates_false_positive_rate(client, seeded, analyst):
    inv = flag_transaction(seeded, "txn_900100")

    before = overview(client, analyst)
    assert before["false_positive_rate"] == 0.0
    assert before["cleared"] == 0

    res = client.post(f"/investigations/{inv.id}/review",
                      json={"decision": "clear", "note": "verified travel", "review_time_seconds": 120},
                      headers=analyst)
    assert res.status_code == 200
    assert res.json()["outcome"] == "false_positive"

    after = overview(client, analyst)
    assert after["cleared"] == 1
    assert after["false_positive_rate"] == 1.0
    assert after["avg_review_seconds"] == 120.0


def test_mixed_outcomes_compute_correct_rates(client, seeded, analyst):
    inv1 = flag_transaction(seeded, "txn_900101")
    inv2 = flag_transaction(seeded, "txn_900102")

    client.post(f"/investigations/{inv1.id}/review", json={"decision": "clear"}, headers=analyst)
    client.post(f"/investigations/{inv2.id}/review", json={"decision": "confirm_fraud"}, headers=analyst)

    m = overview(client, analyst)
    assert m["confirmed_fraud"] == 1
    assert m["cleared"] == 1
    assert m["false_positive_rate"] == 0.5


def test_decision_feeds_rule_false_positive_stats(client, seeded, analyst, manager):
    inv = flag_transaction(seeded, "txn_900103")
    client.post(f"/investigations/{inv.id}/review", json={"decision": "clear"}, headers=analyst)

    rules = client.get("/metrics/rules", headers=manager).json()
    r002 = next(r for r in rules if r["rule_code"] == "R-002")
    assert r002["trigger_count"] == 1
    assert r002["false_positives"] == 1
    assert r002["false_positive_rate"] == 1.0


def test_step_up_outcome_is_pending_not_resolved(client, seeded, analyst):
    inv = flag_transaction(seeded, "txn_900104")
    res = client.post(f"/investigations/{inv.id}/review", json={"decision": "step_up"}, headers=analyst)
    assert res.json()["outcome"] == "pending_verification"

    m = overview(client, analyst)
    # pending verification must not count toward the resolved FP rate
    assert m["false_positive_rate"] == 0.0
    assert m["confirmed_fraud"] == 0 and m["cleared"] == 0
