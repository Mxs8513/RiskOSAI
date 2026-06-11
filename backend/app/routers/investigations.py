from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from .. import models
from ..ai import generate_evidence_packet
from ..database import get_db
from ..pipeline import log
from ..policies import POLICIES, run_policy_check
from ..security import has_permission, require
from ..serializers import inv_row, txn_row

router = APIRouter(prefix="/investigations", tags=["investigations"])

DECISIONS = {
    "confirm_fraud": ("Confirmed Fraud", "true_positive"),
    "clear": ("Cleared", "false_positive"),
    "step_up": ("Hold for Review", "pending_verification"),
    "escalate": ("Escalated", "escalated"),
}


def _ctx(db: Session, inv: models.Investigation) -> dict:
    t = inv.transaction
    rs = db.query(models.RiskScore).filter_by(transaction_id=t.id).one()
    m = db.get(models.Merchant, t.merchant_id)
    c = db.get(models.Customer, t.customer_id)
    return {
        "transaction": {"transaction_id": t.id, "amount": t.amount, "transaction_type": t.transaction_type,
                        "is_new_device": t.is_new_device, "velocity_10_min": t.velocity_10_min,
                        "distance_from_home_miles": t.distance_from_home_miles, "device_id": t.device_id,
                        "merchant_risk_score": t.merchant_risk_score, "user_avg_amount": c.avg_transaction_amount,
                        "city": t.city, "state": t.state},
        "merchant": {"name": m.name, "category": m.category, "city": m.city, "state": m.state},
        "customer": {"customer_id": c.id, "home_city": c.home_city, "home_state": c.home_state,
                     "avg_transaction_amount": c.avg_transaction_amount, "risk_profile": c.risk_profile},
        "risk_score": rs.score, "risk_level": rs.risk_level,
        "ml_fraud_probability": rs.ml_fraud_probability, "hybrid_score": rs.hybrid_score,
        "model_rule_agreement": rs.model_rule_agreement,
        "rules_triggered": rs.rules_triggered, "recommended_action": rs.recommended_action,
        "policies": POLICIES,
    }


@router.get("")
def list_investigations(db: Session = Depends(get_db), user=Depends(require("investigations")),
                        status: Optional[str] = None, risk_level: Optional[str] = None,
                        limit: int = Query(100, le=500), offset: int = Query(0, ge=0)):
    q = (db.query(models.Investigation)
         .options(joinedload(models.Investigation.transaction).joinedload(models.Transaction.merchant),
                  joinedload(models.Investigation.assignee), joinedload(models.Investigation.decision))
         .order_by(models.Investigation.created_at.desc()))
    if status:
        q = q.filter(models.Investigation.status == status)
    if risk_level:
        q = q.filter(models.Investigation.risk_level == risk_level)
    return [inv_row(i) for i in q.offset(offset).limit(limit)]


@router.get("/{inv_id}")
def get_investigation(inv_id: str, db: Session = Depends(get_db), user=Depends(require("investigations"))):
    inv = db.get(models.Investigation, inv_id)
    if not inv:
        raise HTTPException(404, "Investigation not found")
    rs = db.query(models.RiskScore).filter_by(transaction_id=inv.transaction_id).one()
    report = inv.ai_report
    pc = (db.query(models.PolicyCheck).filter_by(investigation_id=inv.id)
          .order_by(models.PolicyCheck.created_at.desc()).first())
    decision = inv.decision
    timeline = [
        {"timestamp": a.created_at.isoformat(), "event_type": a.event_type, "message": a.message,
         "actor": a.actor.name if a.actor else "system"}
        for a in db.query(models.AuditLog).filter_by(investigation_id=inv.id)
        .order_by(models.AuditLog.created_at.asc()).all()
    ]
    return {
        **inv_row(inv),
        "transaction": txn_row(inv.transaction),
        "rules_triggered": rs.rules_triggered,
        "rule_score": rs.score,
        "ml_fraud_probability": rs.ml_fraud_probability,
        "hybrid_score": rs.hybrid_score,
        "model_rule_agreement": rs.model_rule_agreement,
        "routing_score_basis": "hybrid" if rs.ml_fraud_probability is not None else "rule",
        "ai_report": None if not report else {
            "risk_summary": report.risk_summary, "evidence_bullets": report.evidence,
            "rules_explanation": report.rules_explanation, "comparable_pattern": report.comparable_pattern,
            "recommended_action": report.recommended_action, "customer_impact_note": report.customer_impact_note,
            "reviewer_checklist": report.reviewer_checklist, "audit_note": report.audit_note,
            "generated_by": report.generated_by, "created_at": report.created_at.isoformat(),
        },
        "policy_check": None if not pc else {
            "policy_status": pc.policy_status, "policies_checked": pc.policies_checked,
            "issues": pc.issues, "explanation": pc.explanation, "created_at": pc.created_at.isoformat(),
        },
        "reviewer_decision": None if not decision else {
            "decision": decision.decision, "reviewer": decision.reviewer.name, "note": decision.reviewer_note,
            "ai_agreed": decision.ai_agreed, "outcome": decision.outcome,
            "review_time_seconds": decision.review_time_seconds, "created_at": decision.created_at.isoformat(),
        },
        "timeline": timeline,
        "policies": POLICIES,
    }


@router.post("/{inv_id}/generate-ai-report")
def generate_report(inv_id: str, db: Session = Depends(get_db), user=Depends(require("investigations"))):
    inv = db.get(models.Investigation, inv_id)
    if not inv:
        raise HTTPException(404, "Investigation not found")
    ctx = _ctx(db, inv)
    packet, raw, provider = generate_evidence_packet(ctx)
    existing = db.query(models.AIReport).filter_by(investigation_id=inv.id).first()
    if existing:
        db.delete(existing)
        db.flush()
    db.add(models.AIReport(investigation_id=inv.id, risk_summary=packet["risk_summary"],
                           evidence=packet.get("evidence_bullets", []), rules_explanation=packet.get("rules_explanation", ""),
                           comparable_pattern=packet.get("comparable_pattern", ""), recommended_action=packet.get("recommended_action", inv.recommended_action),
                           customer_impact_note=packet.get("customer_impact_note", ""), reviewer_checklist=packet.get("reviewer_checklist", []),
                           audit_note=packet.get("audit_note", ""), raw_model_output=raw, generated_by=provider))
    inv.ai_summary = packet["risk_summary"]
    log(db, "ai_report_generated", actor_id=user.id, actor_role=user.role, investigation_id=inv.id,
        transaction_id=inv.transaction_id, message=f"AI evidence packet generated for {inv.id}",
        meta={"provider": provider})
    db.commit()
    return {"status": "ok", "provider": provider, "report": packet}


@router.post("/{inv_id}/policy-check")
def policy_check(inv_id: str, db: Session = Depends(get_db), user=Depends(require("investigations"))):
    inv = db.get(models.Investigation, inv_id)
    if not inv:
        raise HTTPException(404, "Investigation not found")
    rs = db.query(models.RiskScore).filter_by(transaction_id=inv.transaction_id).one()
    report = inv.ai_report
    result = run_policy_check(risk_score=rs.score, rules_triggered=rs.rules_triggered,
                              ai_text=report.risk_summary if report else "",
                              transaction=_ctx(db, inv)["transaction"], routed_to_review=True)
    db.add(models.PolicyCheck(investigation_id=inv.id, **result))
    inv.policy_check_status = result["policy_status"]
    log(db, "policy_check_completed", actor_id=user.id, actor_role=user.role, investigation_id=inv.id,
        transaction_id=inv.transaction_id, message=f"Policy check completed for {inv.id}: {result['policy_status']}",
        meta={"status": result["policy_status"], "issues": result["issues"]})
    db.commit()
    return result


class ReviewRequest(BaseModel):
    decision: str = Field(max_length=40)  # confirm_fraud | clear | step_up | escalate
    note: Optional[str] = Field(None, max_length=2000)
    review_time_seconds: int = Field(0, ge=0)


@router.post("/{inv_id}/review")
def review(inv_id: str, body: ReviewRequest, db: Session = Depends(get_db), user=Depends(require("review"))):
    inv = db.get(models.Investigation, inv_id)
    if not inv:
        raise HTTPException(404, "Investigation not found")
    if body.decision not in DECISIONS:
        raise HTTPException(422, f"decision must be one of {list(DECISIONS)}")
    if inv.decision and not has_permission(user.role, "override"):
        raise HTTPException(403, "Case already decided — only a Risk Manager or Admin can override")

    new_status, outcome = DECISIONS[body.decision]
    ai_recommended_hold = inv.recommended_action.lower() != "approve"
    ai_agreed = (body.decision in ("confirm_fraud", "escalate", "step_up")) == ai_recommended_hold

    if inv.decision:  # override path
        db.delete(inv.decision)
        db.flush()
        log(db, "case_status_overridden", actor_id=user.id, actor_role=user.role, investigation_id=inv.id,
            transaction_id=inv.transaction_id, message=f"{user.name} overrode prior decision on {inv.id}",
            meta={"new_decision": body.decision})

    d = models.ReviewerDecision(investigation_id=inv.id, reviewer_id=user.id, decision=body.decision,
                                reviewer_note=body.note, review_time_seconds=body.review_time_seconds,
                                ai_agreed=ai_agreed, outcome=outcome)
    db.add(d)
    inv.status = new_status
    inv.assigned_to = user.id
    txn = inv.transaction
    txn.status = new_status
    rs = db.query(models.RiskScore).filter_by(transaction_id=txn.id).one()
    log(db, "reviewer_decision_submitted", actor_id=user.id, actor_role=user.role, investigation_id=inv.id,
        transaction_id=txn.id,
        message=f"{user.name} decided '{body.decision}' on {inv.id} — outcome: {outcome.replace('_', ' ')}",
        meta={"decision": body.decision, "outcome": outcome, "ai_agreed": ai_agreed,
              "risk_score": rs.score, "rules_triggered": [r["code"] for r in rs.rules_triggered],
              "ai_recommendation": rs.recommended_action})
    log(db, "case_status_updated", actor_id=user.id, actor_role=user.role, investigation_id=inv.id,
        transaction_id=txn.id, message=f"Investigation {inv.id} status updated to {new_status}",
        meta={"status": new_status})
    db.commit()
    return {"status": "ok", "investigation_status": new_status, "outcome": outcome, "ai_agreed": ai_agreed}
