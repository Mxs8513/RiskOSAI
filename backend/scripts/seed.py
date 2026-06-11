"""Seed RiskOS AI with demo users, fraud rules, and a week of synthetic history.

Usage:
    python -m scripts.seed                 # pure synthetic (PaySim-shaped)
    python -m scripts.seed --paysim FILE   # sample + enrich a real PaySim CSV
    python -m scripts.seed --reset         # drop and recreate everything

History is backdated realistically: daily volume follows a weekday curve,
intraday volume peaks in business hours, and every derived record (risk score,
investigation, AI report, policy check, decision, audit events) carries a
timestamp consistent with the transaction it belongs to.
"""
import argparse
import csv
import random
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, ".")

from app import models  # noqa: E402
from app.ai import generate_evidence_packet  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.pipeline import (build_enriched_txn, log, next_txn_id, process_transaction,  # noqa: E402
                          seed_reference_data)
from app.policies import run_policy_check  # noqa: E402
from app.risk_engine import RULES_CATALOG  # noqa: E402
from app.security import hash_password  # noqa: E402

DEMO_USERS = [
    ("analyst@northstar.demo", "demo1234", "Avery Chen", "fraud_analyst"),
    ("manager@northstar.demo", "demo1234", "Jordan Reyes", "risk_manager"),
    ("developer@northstar.demo", "demo1234", "Sam Okafor", "developer"),
    ("admin@northstar.demo", "demo1234", "Riley Park", "admin"),
]

DECISION_OUTCOME = {
    "confirm_fraud": "true_positive",
    "clear": "false_positive",
    "step_up": "pending_verification",
    "escalate": "escalated",
}
DECISION_STATUS = {
    "confirm_fraud": "Confirmed Fraud",
    "clear": "Cleared",
    "step_up": "Hold for Review",
    "escalate": "Escalated",
}

REVIEWER_NOTES = {
    "confirm_fraud": [
        "Called the customer — they did not recognize the charge. Card blocked and reissued.",
        "Device fingerprint matches two prior confirmed-fraud cases. Issuer notified.",
        "Customer confirmed their card details were phished last week. Charging back.",
        "No travel notice on file and customer answered from home number. Confirmed fraudulent.",
        "Merchant has an open dispute cluster this week; customer denies the purchase.",
        "Velocity pattern plus new device — customer verified they were asleep at the time.",
    ],
    "clear": [
        "Customer verified the purchase via OTP — traveling for work this week.",
        "Travel notification on file covers this location. Cleared.",
        "Spoke with customer; gift purchase outside normal pattern but confirmed legitimate.",
        "New device is the customer's replacement phone — verified via registered email.",
        "Recurring vendor, amount within seasonal range. False positive on the velocity rule.",
        "Customer pre-authorized this large purchase with the branch yesterday. Cleared.",
    ],
    "step_up": [
        "Could not reach the customer — step-up verification SMS sent, holding until response.",
        "Signals are mixed; requested ID verification before final disposition.",
        "Customer asked to call back; holding pending verification.",
        "Device unrecognized and number rings out — verification link issued.",
    ],
    "escalate": [
        "Overlaps with the ring flagged on Monday — escalating to senior review.",
        "Amount above my disposition limit; escalating per policy.",
        "Conflicting evidence and a POL-003 step-up requirement — needs manager sign-off.",
        "Third case for this merchant in 48h; escalating for pattern review.",
    ],
}

# Mon..Sun multipliers — busier toward end of week, quieter weekends.
WEEKDAY_VOLUME = [1.00, 1.05, 1.10, 1.18, 1.25, 0.80, 0.62]


def realistic_timestamp(rng: random.Random, now: datetime, day_weights: list) -> datetime:
    """Pick a day (weekday-weighted) then an hour peaked around mid-afternoon."""
    days_ago = rng.choices(range(7), weights=day_weights)[0]
    hour = min(23, max(0, int(rng.gauss(14, 4.5))))
    ts = (now - timedelta(days=days_ago)).replace(
        hour=hour, minute=rng.randint(0, 59), second=rng.randint(0, 59), microsecond=0)
    return min(ts, now - timedelta(minutes=2))


def load_paysim_rows(path: str, limit: int, rng: random.Random) -> list[dict]:
    rows = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        pool = []
        for i, row in enumerate(reader):
            if i > 400_000:
                break
            pool.append(row)
        rng.shuffle(pool)
        for row in pool[:limit]:
            rows.append({"amount": float(row["amount"]), "is_fraud": row.get("isFraud") == "1",
                         "type": row.get("type", "PAYMENT")})
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--paysim", help="Path to PaySim CSV to sample and enrich")
    parser.add_argument("--transactions", type=int, default=420)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    if args.reset:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    rng = random.Random(42)

    if db.query(models.User).count():
        print("Database already seeded. Use --reset to reseed.")
        return

    users = [models.User(email=e, password_hash=hash_password(p), name=n, role=r) for e, p, n, r in DEMO_USERS]
    db.add_all(users)
    db.add_all([models.FraudRule(**{k: v for k, v in r.items()}) for r in RULES_CATALOG])
    db.commit()
    analyst, manager = users[0], users[1]

    customers, merchants = seed_reference_data(db, rng)
    print(f"Seeded {len(users)} users, {len(RULES_CATALOG)} rules, {len(customers)} customers, {len(merchants)} merchants")

    paysim = load_paysim_rows(args.paysim, args.transactions, rng) if args.paysim else None
    if paysim:
        print(f"Enriching {len(paysim)} sampled PaySim rows")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    # Per-day volume weights for the trailing week (index = days ago), with noise.
    day_weights = [WEEKDAY_VOLUME[(now - timedelta(days=i)).weekday()] * rng.uniform(0.85, 1.15)
                   for i in range(7)]

    investigations = []
    txn_ts: dict[str, datetime] = {}
    for i in range(args.transactions):
        ts = realistic_timestamp(rng, now, day_weights)
        customer, merchant = rng.choice(customers), rng.choice(merchants)
        enriched = build_enriched_txn(rng, customer, merchant, ts, next_txn_id(db),
                                      force_fraudy=(paysim[i]["is_fraud"] or rng.random() < 0.06) if paysim else None)
        if paysim:  # keep PaySim's amount + fraud label as ground truth
            enriched["amount"] = round(min(paysim[i]["amount"] / 60 + 5, 15000), 2)
            enriched["dataset_label"] = paysim[i]["is_fraud"]
        txn, rs, inv = process_transaction(db, enriched)
        txn_ts[txn.id] = ts
        # Backdate the records the pipeline stamped with "now".
        txn.created_at = ts
        rs.created_at = ts
        if inv:
            inv.created_at = ts
            inv.updated_at = ts
            investigations.append(inv)
    db.commit()

    # Resolve most historical customer verifications (recent ones stay pending)
    verifications_resolved = 0
    for t in db.query(models.Transaction).filter_by(verification_status="pending_verification").all():
        age_hours = (now - txn_ts[t.id]).total_seconds() / 3600
        if age_hours < 6 or rng.random() < 0.2:
            continue  # still awaiting customer response
        outcome = rng.choices(["confirmed_legitimate", "expired"], weights=[0.85, 0.15])[0]
        t.verification_status = outcome
        if outcome == "confirmed_legitimate":
            t.status = "Approved"
            t.hold_status = False
        log(db, "customer_verification_completed", transaction_id=t.id,
            message=f"Customer verification for {t.id}: {outcome.replace('_', ' ')}",
            meta={"verification_status": outcome})
        verifications_resolved += 1
    db.commit()

    # Resolve ~70% of historical investigations with reviewer decisions + AI reports
    resolved = 0
    review_ts: dict[str, datetime] = {}
    for inv in investigations:
        txn = db.get(models.Transaction, inv.transaction_id)
        rs = db.query(models.RiskScore).filter_by(transaction_id=txn.id).one()
        merchant = db.get(models.Merchant, txn.merchant_id)
        customer = db.get(models.Customer, txn.customer_id)
        opened = txn_ts[txn.id]
        report_ts = min(opened + timedelta(minutes=rng.uniform(1, 25)), now)
        ctx = {
            "transaction": {"transaction_id": txn.id, "amount": txn.amount, "transaction_type": txn.transaction_type,
                            "is_new_device": txn.is_new_device, "velocity_10_min": txn.velocity_10_min,
                            "distance_from_home_miles": txn.distance_from_home_miles,
                            "merchant_risk_score": txn.merchant_risk_score, "device_id": txn.device_id,
                            "user_avg_amount": customer.avg_transaction_amount, "city": txn.city, "state": txn.state},
            "merchant": {"name": merchant.name, "category": merchant.category},
            "risk_score": rs.score, "risk_level": rs.risk_level,
            "ml_fraud_probability": rs.ml_fraud_probability, "hybrid_score": rs.hybrid_score,
            "model_rule_agreement": rs.model_rule_agreement,
            "rules_triggered": rs.rules_triggered, "recommended_action": rs.recommended_action,
        }
        packet, raw, provider = generate_evidence_packet({**ctx})  # seeded history always uses mock provider
        report = models.AIReport(investigation_id=inv.id, risk_summary=packet["risk_summary"],
                                 evidence=packet["evidence_bullets"], rules_explanation=packet["rules_explanation"],
                                 comparable_pattern=packet["comparable_pattern"], recommended_action=packet["recommended_action"],
                                 customer_impact_note=packet["customer_impact_note"], reviewer_checklist=packet["reviewer_checklist"],
                                 audit_note=packet["audit_note"], raw_model_output=raw, generated_by=provider,
                                 created_at=report_ts)
        db.add(report)
        inv.ai_summary = packet["risk_summary"]
        log(db, "ai_report_generated", investigation_id=inv.id, transaction_id=txn.id,
            message=f"AI evidence packet generated for {inv.id}", meta={"provider": provider})

        pc = run_policy_check(risk_score=rs.score, rules_triggered=rs.rules_triggered,
                              ai_text=packet["risk_summary"], transaction=ctx["transaction"], routed_to_review=True)
        db.add(models.PolicyCheck(investigation_id=inv.id, **pc,
                                  created_at=min(report_ts + timedelta(minutes=rng.uniform(0.5, 5)), now)))
        inv.policy_check_status = pc["policy_status"]
        log(db, "policy_check_completed", investigation_id=inv.id, transaction_id=txn.id,
            message=f"Policy check {pc['policy_status']} for {inv.id}", meta={"status": pc["policy_status"]})

        if rng.random() < 0.7:
            # Simulate outcome: most critical cases are real fraud, but reviewers
            # still clear a meaningful share (false positives keep metrics honest)
            actually_bad = rng.random() < (0.8 if txn.dataset_label else 0.45)
            decision = "confirm_fraud" if actually_bad else rng.choices(["clear", "step_up"], weights=[0.8, 0.2])[0]
            if rs.risk_level == "Critical" and not actually_bad and rng.random() < 0.25:
                decision = "escalate"
            reviewer = rng.choice([analyst, manager])
            ai_agreed = decision in ("confirm_fraud", "escalate", "step_up")
            decided_at = min(opened + timedelta(minutes=rng.uniform(30, 2400)), now)
            review_ts[inv.id] = decided_at
            d = models.ReviewerDecision(investigation_id=inv.id, reviewer_id=reviewer.id, decision=decision,
                                        reviewer_note=rng.choice(REVIEWER_NOTES[decision]),
                                        review_time_seconds=rng.randint(45, 600), ai_agreed=ai_agreed,
                                        outcome=DECISION_OUTCOME[decision], created_at=decided_at)
            db.add(d)
            inv.status = DECISION_STATUS[decision]
            inv.assigned_to = reviewer.id
            inv.updated_at = decided_at
            txn.status = DECISION_STATUS[decision] if decision != "step_up" else "Hold for Review"
            log(db, "reviewer_decision_submitted", actor_id=reviewer.id, actor_role=reviewer.role,
                investigation_id=inv.id, transaction_id=txn.id,
                message=f"{reviewer.name} decided '{decision}' on {inv.id} (AI {'agreed' if ai_agreed else 'disagreed'})",
                meta={"decision": decision, "ai_agreed": ai_agreed, "outcome": DECISION_OUTCOME[decision],
                      "risk_score": rs.score, "rules_triggered": [r["code"] for r in rs.rules_triggered],
                      "ai_recommendation": rs.recommended_action})
            resolved += 1
        else:
            inv.assigned_to = rng.choice([analyst.id, manager.id, None])
            inv.updated_at = report_ts
    db.commit()

    # Backdate audit events to sit on their transaction/decision timeline.
    AUDIT_OFFSETS = {
        "transaction_processed": timedelta(seconds=0),
        "risk_score_generated": timedelta(seconds=1),
        "transaction_auto_approved": timedelta(seconds=2),
        "transaction_monitored": timedelta(seconds=2),
        "verification_required": timedelta(seconds=2),
        "transaction_held_for_verification": timedelta(seconds=2),
        "critical_escalation": timedelta(seconds=2),
        "investigation_created": timedelta(seconds=3),
        "ai_report_generated": timedelta(minutes=3),
        "policy_check_completed": timedelta(minutes=5),
        "customer_verification_completed": timedelta(hours=7),
        "verification_sms_queued": timedelta(seconds=3),
        "verification_sms_sent": timedelta(seconds=6),
        "verification_sms_failed": timedelta(seconds=6),
    }
    for a in db.query(models.AuditLog).all():
        base = txn_ts.get(a.transaction_id)
        if base is None:
            continue
        if a.event_type == "reviewer_decision_submitted" and a.investigation_id in review_ts:
            a.created_at = review_ts[a.investigation_id]
        else:
            a.created_at = min(base + AUDIT_OFFSETS.get(a.event_type, timedelta(seconds=3)), now)

    # Backdate notification events; mark the ones whose verification was
    # resolved as delivered (simulated history — no real SMS during seeding).
    for n in db.query(models.NotificationEvent).all():
        base = txn_ts.get(n.transaction_id)
        if base is None:
            continue
        n.created_at = base + timedelta(seconds=3)
        t = db.get(models.Transaction, n.transaction_id)
        if t and t.verification_status in ("confirmed_legitimate", "expired"):
            n.status = "sent"
            n.sent_at = n.created_at + timedelta(seconds=4)
            n.to_phone_masked = "***-***-0199"
            n.meta = {"simulated": True, "note": "seeded demo history — no real SMS was sent"}
    db.commit()

    print(f"Seeded {args.transactions} transactions, {len(investigations)} investigations ({resolved} resolved), "
          f"{verifications_resolved} customer verifications resolved")
    print("Demo users (password: demo1234):")
    for e, _, n, r in DEMO_USERS:
        print(f"  {e:32s} {r:15s} {n}")


if __name__ == "__main__":
    main()
