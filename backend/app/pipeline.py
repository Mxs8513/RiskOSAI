"""Data layer: PaySim-style synthetic generation + enrichment + pipeline.

The seed can run in two modes:
1. Pure synthetic (default): generates PaySim-shaped transactions (including
   an `isFraud`-style dataset label) so the repo runs with zero downloads.
2. PaySim CSV ingest: `python -m scripts.seed --paysim path/to/PS_*.csv`
   samples real PaySim rows and enriches them into card-style records.

Either way, every transaction flows through the same pipeline:
enrich -> score -> (flag -> investigation) -> audit log.
"""
from __future__ import annotations

from typing import Optional
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from . import ml_model, models
from .communications import send_verification_sms
from .response_orchestrator import AUDIT_EVENT_BY_DECISION, STATUS_BY_DECISION, decide_response
from .risk_engine import band_for_score, score_transaction

FIRST = ["North", "Blue", "Iron", "Cedar", "Summit", "Vert", "Lake", "Atlas", "Pine", "Nova", "Halo", "Quarry", "Delta", "Ember", "Crest"]
SECOND = ["line", "peak", "field", "works", "mart", "port", "forge", "grove", "stone", "byte", "loop", "haven", "ridge", "row", "lane"]
SUFFIX = {"electronics": "Electronics", "travel": "Travel", "jewelry": "Jewelers", "grocery": "Market", "fuel": "Fuel", "dining": "Kitchen", "digital_goods": "Digital", "money_transfer": "Pay", "retail": "Supply Co.", "crypto_exchange": "Exchange"}
CATEGORY_RISK = {"grocery": 0.08, "fuel": 0.10, "dining": 0.12, "retail": 0.18, "travel": 0.35, "electronics": 0.45, "digital_goods": 0.55, "jewelry": 0.62, "money_transfer": 0.74, "crypto_exchange": 0.86}
CITIES = [("Dallas", "TX"), ("Frisco", "TX"), ("Austin", "TX"), ("Miami", "FL"), ("Atlanta", "GA"), ("Chicago", "IL"), ("New York", "NY"), ("Seattle", "WA"), ("Denver", "CO"), ("Phoenix", "AZ"), ("Boston", "MA"), ("Nashville", "TN")]


def _merchant_name(rng: random.Random, category: str) -> str:
    return f"{rng.choice(FIRST)}{rng.choice(SECOND).capitalize()} {SUFFIX[category]}".replace("Capitalize", "")


def seed_reference_data(db: Session, rng: random.Random, n_customers=60, n_merchants=40):
    customers, merchants = [], []
    for i in range(n_customers):
        city, state = rng.choice(CITIES)
        customers.append(models.Customer(
            id=f"usr_{1000 + i}", home_city=city, home_state=state,
            avg_transaction_amount=round(rng.uniform(35, 220), 2),
            risk_profile=rng.choices(["standard", "elevated", "trusted"], weights=[0.7, 0.15, 0.15])[0],
        ))
    cats = list(CATEGORY_RISK)
    for i in range(n_merchants):
        category = rng.choice(cats)
        city, state = rng.choice(CITIES)
        base = CATEGORY_RISK[category]
        merchants.append(models.Merchant(
            id=f"mer_{2000 + i}", name=_merchant_name(rng, category), category=category,
            city=city, state=state,
            merchant_risk_score=round(min(0.97, max(0.02, rng.gauss(base, 0.12))), 2),
        ))
    db.add_all(customers + merchants)
    db.commit()
    return customers, merchants


def build_enriched_txn(rng: random.Random, customer: models.Customer, merchant: models.Merchant,
                       ts: datetime, txn_id: str, force_fraudy: Optional[bool] = None) -> dict:
    """Create an enriched transaction dict. ~12% of traffic is fraud-shaped."""
    fraudy = force_fraudy if force_fraudy is not None else rng.random() < 0.12
    if fraudy:
        amount = round(customer.avg_transaction_amount * rng.uniform(4, 14), 2)
        is_new_device = rng.random() < 0.75
        velocity = rng.choice([1, 3, 4, 5, 6, 7])
        distance = rng.choice([rng.uniform(0, 40), rng.uniform(600, 3200)])
        txn_type = "card_not_present" if rng.random() < 0.7 else "card_present"
        dataset_label = rng.random() < 0.45
    else:
        amount = round(max(2.5, rng.gauss(customer.avg_transaction_amount, customer.avg_transaction_amount * 0.45)), 2)
        is_new_device = rng.random() < 0.06
        velocity = rng.choices([1, 2, 3], weights=[0.8, 0.15, 0.05])[0]
        distance = abs(rng.gauss(8, 15))
        txn_type = "card_not_present" if rng.random() < 0.3 else "card_present"
        dataset_label = rng.random() < 0.01

    far = distance > 200
    city, state = (rng.choice([c for c in CITIES if c[1] != customer.home_state]) if far
                   else (customer.home_city, customer.home_state))
    return {
        "id": txn_id, "customer_id": customer.id, "merchant_id": merchant.id,
        "amount": amount, "currency": "USD", "city": city, "state": state,
        "device_id": f"dev_{'new_' if is_new_device else ''}{rng.randint(1000, 9999)}",
        "transaction_type": txn_type, "timestamp": ts,
        "is_new_device": is_new_device, "velocity_10_min": velocity,
        "distance_from_home_miles": round(distance, 1),
        "merchant_risk_score": merchant.merchant_risk_score,
        "dataset_label": dataset_label,
        "user_avg_amount": customer.avg_transaction_amount,
    }


def next_txn_id(db: Session) -> str:
    n = db.query(models.Transaction).count()
    return f"txn_{800000 + n}"


def next_inv_id(db: Session) -> str:
    n = db.query(models.Investigation).count()
    return f"inv_{100000 + n}"


def active_rule_codes(db: Session) -> set[str]:
    return {r.rule_code for r in db.query(models.FraudRule).filter(models.FraudRule.status == "active")}


RESPONSE_AUDIT_MESSAGES = {
    "approved": "auto-approved (low risk; no human involvement)",
    "monitored": "approved with monitoring (medium risk)",
    "verification_required": "routed to customer verification (elevated risk; human review avoided)",
    "held_for_verification": "held pending customer verification (high risk; human review avoided)",
    "escalated_to_human_review": "held and escalated to human review (critical risk)",
}


def process_transaction(db: Session, enriched: dict, actor_id: Optional[int] = None) -> tuple[models.Transaction, models.RiskScore, Optional[models.Investigation]]:
    """The core pipeline: persist txn -> score -> orchestrate response -> audit.

    The Automated Response Orchestrator decides what happens next; only
    Critical-tier transactions open a human investigation immediately.

    Scoring is hybrid: the deterministic rule score (explainability layer) is
    always computed; if the optional ML model is available its probability is
    blended in (0.6 ML + 0.4 rules) and routing uses the hybrid score.
    Without a model, routing falls back to the rule score unchanged.
    """
    result = score_transaction(enriched, active_rule_codes(db))
    ml_prob = ml_model.predict_fraud_probability(enriched)
    hybrid = ml_model.compute_hybrid_score(result["score"], ml_prob)
    agreement = ml_model.score_agreement(result["score"], ml_prob)
    routing_basis = "hybrid" if ml_prob is not None else "rule"
    response = decide_response(risk_score=hybrid, risk_level=result["risk_level"],
                               rules_triggered=result["rules_triggered"])

    txn = models.Transaction(**{k: v for k, v in enriched.items() if k != "user_avg_amount"},
                             status=STATUS_BY_DECISION[response["automation_decision"]],
                             automation_decision=response["automation_decision"],
                             verification_status=response["verification_status"],
                             human_review_required=response["human_review_required"],
                             hold_status=response["hold_status"],
                             escalation_reason=response["escalation_reason"])
    db.add(txn)
    rs = models.RiskScore(transaction_id=txn.id, score=result["score"], risk_level=result["risk_level"],
                          rules_triggered=result["rules_triggered"], recommended_action=result["recommended_action"],
                          ml_fraud_probability=ml_prob, hybrid_score=hybrid, model_rule_agreement=agreement)
    db.add(rs)
    log(db, "transaction_processed", actor_id=actor_id, transaction_id=txn.id,
        message=f"Transaction {txn.id} processed: ${enriched['amount']:,.2f} at merchant {enriched['merchant_id']}",
        meta={"amount": enriched["amount"], "type": enriched["transaction_type"]})
    score_msg = (f"Risk engine scored {txn.id}: rule {result['score']}/100"
                 + (f", ML {ml_prob:.0%}, hybrid {hybrid}/100 ({agreement} agreement)" if ml_prob is not None else "")
                 + f" ({result['risk_level']})")
    log(db, "risk_score_generated", actor_id=actor_id, transaction_id=txn.id,
        message=score_msg,
        meta={"score": result["score"], "risk_level": result["risk_level"],
              "ml_fraud_probability": ml_prob, "hybrid_score": hybrid,
              "model_rule_agreement": agreement, "routing_score_basis": routing_basis,
              "rules_triggered": [r["code"] for r in result["rules_triggered"]],
              "recommended_action": result["recommended_action"]})
    log(db, AUDIT_EVENT_BY_DECISION[response["automation_decision"]], actor_id=actor_id, transaction_id=txn.id,
        message=f"Orchestrator: {txn.id} {RESPONSE_AUDIT_MESSAGES[response['automation_decision']]}",
        meta={"automation_decision": response["automation_decision"],
              "response_tier": response["response_tier"],
              "verification_status": response["verification_status"],
              "human_review_required": response["human_review_required"],
              "hold_status": response["hold_status"],
              "customer_action_required": response["customer_action_required"]})

    # Elevated/High tiers trigger customer verification — queue (and, if
    # configured, send) the templated SMS. Never blocks the pipeline.
    if response["automation_decision"] in ("verification_required", "held_for_verification"):
        merchant = db.get(models.Merchant, txn.merchant_id)
        send_verification_sms(db, txn, merchant.name if merchant else txn.merchant_id,
                              actor_id=actor_id)

    inv = None
    if response["human_review_required"]:
        # Investigations carry the routing score (hybrid when ML is available)
        inv = models.Investigation(
            id=next_inv_id(db), transaction_id=txn.id, risk_score=hybrid,
            risk_level=band_for_score(hybrid), status="Open",
            recommended_action=result["recommended_action"],
        )
        db.add(inv)
        log(db, "investigation_created", actor_id=actor_id, transaction_id=txn.id, investigation_id=inv.id,
            message=f"Investigation {inv.id} opened for {txn.id} ({inv.risk_level}, score {hybrid}): {response['escalation_reason']}",
            meta={"risk_level": inv.risk_level, "escalation_reason": response["escalation_reason"],
                  "routing_score_basis": routing_basis})
    db.commit()
    db.refresh(txn)
    return txn, rs, inv


def log(db: Session, event_type: str, *, message: str, actor_id: Optional[int] = None, actor_role: Optional[str] = None,
        transaction_id: Optional[str] = None, investigation_id: Optional[str] = None, meta: Optional[dict] = None):
    db.add(models.AuditLog(event_type=event_type, actor_id=actor_id, actor_role=actor_role,
                           transaction_id=transaction_id, investigation_id=investigation_id,
                           message=message, meta=meta or {}))
