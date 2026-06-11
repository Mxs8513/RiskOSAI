"""Lightweight serializers for API responses."""
from . import models


def txn_row(t: models.Transaction) -> dict:
    rs = t.risk_score
    return {
        "transaction_id": t.id,
        "timestamp": t.timestamp.isoformat(),
        "customer_id": t.customer_id,
        "merchant": t.merchant.name if t.merchant else t.merchant_id,
        "merchant_category": t.merchant.category if t.merchant else None,
        "amount": t.amount,
        "currency": t.currency,
        "city": t.city,
        "state": t.state,
        "device_id": t.device_id,
        "transaction_type": t.transaction_type,
        "is_new_device": t.is_new_device,
        "velocity_10_min": t.velocity_10_min,
        "distance_from_home_miles": t.distance_from_home_miles,
        "merchant_risk_score": t.merchant_risk_score,
        "dataset_label": t.dataset_label,
        "status": t.status,
        "rule_score": rs.score if rs else None,
        "ml_fraud_probability": rs.ml_fraud_probability if rs else None,
        "hybrid_score": rs.hybrid_score if rs else None,
        "model_rule_agreement": rs.model_rule_agreement if rs else None,
        "routing_score_basis": ("hybrid" if rs and rs.ml_fraud_probability is not None else "rule") if rs else None,
        "automation_decision": t.automation_decision,
        "verification_status": t.verification_status,
        "human_review_required": t.human_review_required,
        "hold_status": t.hold_status,
        "escalation_reason": t.escalation_reason,
        "risk_score": rs.score if rs else None,
        "risk_level": rs.risk_level if rs else None,
        "recommended_action": rs.recommended_action if rs else None,
        "rules_triggered": rs.rules_triggered if rs else [],
    }


def inv_row(i: models.Investigation) -> dict:
    t = i.transaction
    return {
        "investigation_id": i.id,
        "transaction_id": i.transaction_id,
        "customer_id": t.customer_id if t else None,
        "merchant": t.merchant.name if t and t.merchant else None,
        "amount": t.amount if t else None,
        "risk_score": i.risk_score,
        "risk_level": i.risk_level,
        "status": i.status,
        "recommended_action": i.recommended_action,
        "policy_check_status": i.policy_check_status,
        "assigned_to": i.assignee.name if i.assignee else None,
        "has_ai_report": i.ai_report is not None,
        "decision": i.decision.decision if i.decision else None,
        "created_at": i.created_at.isoformat(),
    }


def audit_row(a: models.AuditLog) -> dict:
    return {
        "id": a.id,
        "timestamp": a.created_at.isoformat(),
        "event_type": a.event_type,
        "actor": a.actor.name if a.actor else "system",
        "actor_role": a.actor_role,
        "transaction_id": a.transaction_id,
        "investigation_id": a.investigation_id,
        "message": a.message,
        "metadata": a.meta,
    }
