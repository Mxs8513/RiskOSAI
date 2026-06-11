from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from .. import models
from ..database import get_db
from ..security import has_permission, require
from ..serializers import audit_row

router = APIRouter(prefix="/audit-logs", tags=["audit"])

LIMITED_EVENTS = {"transaction_processed", "risk_score_generated", "investigation_created",
                  "ai_report_generated", "policy_check_completed", "reviewer_decision_submitted",
                  "case_status_updated",
                  # Automated Response Orchestrator events
                  "transaction_auto_approved", "transaction_monitored", "verification_required",
                  "transaction_held_for_verification", "critical_escalation",
                  "customer_verification_completed",
                  # Phase 2: outbound SMS verification
                  "verification_sms_queued", "verification_sms_sent", "verification_sms_failed",
                  # Evidence intake & cross-check
                  "evidence_document_uploaded", "evidence_document_analyzed"}


@router.get("")
def list_logs(db: Session = Depends(get_db), user=Depends(require("audit:limited")),
              event_type: Optional[str] = None, investigation_id: Optional[str] = None,
              transaction_id: Optional[str] = None, limit: int = Query(100, le=500),
              offset: int = Query(0, ge=0)):
    q = (db.query(models.AuditLog).options(joinedload(models.AuditLog.actor))
         .order_by(models.AuditLog.created_at.desc()))
    if event_type:
        q = q.filter(models.AuditLog.event_type == event_type)
    if investigation_id:
        q = q.filter(models.AuditLog.investigation_id == investigation_id)
    if transaction_id:
        q = q.filter(models.AuditLog.transaction_id == transaction_id)
    limited = not has_permission(user.role, "audit")
    if limited:  # analysts/developers see case-workflow events only
        q = q.filter(models.AuditLog.event_type.in_(LIMITED_EVENTS))
    return {"limited_view": limited, "logs": [audit_row(a) for a in q.offset(offset).limit(limit)]}


@router.get("/{log_id}")
def get_log(log_id: int, db: Session = Depends(get_db), user=Depends(require("audit"))):
    a = db.get(models.AuditLog, log_id)
    if not a:
        raise HTTPException(404, "Audit log not found")
    return audit_row(a)
