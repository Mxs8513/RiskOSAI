from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models
from ..communications import send_verification_sms
from ..database import get_db
from ..security import require

router = APIRouter(prefix="/notifications", tags=["notifications"])

ELIGIBLE_DECISIONS = ("verification_required", "held_for_verification")


def notif_row(n: models.NotificationEvent) -> dict:
    return {
        "id": n.id,
        "transaction_id": n.transaction_id,
        "investigation_id": n.investigation_id,
        "channel": n.channel,
        "provider": n.provider,
        "to_phone_masked": n.to_phone_masked,
        "message_body": n.message_body,
        "status": n.status,
        "provider_message_id": n.provider_message_id,
        "sent_at": n.sent_at.isoformat() if n.sent_at else None,
        "metadata": n.meta,
        "created_at": n.created_at.isoformat(),
    }


@router.get("")
def list_notifications(db: Session = Depends(get_db), user=Depends(require("transactions")),
                       status: Optional[str] = None, transaction_id: Optional[str] = None,
                       limit: int = Query(50, le=200), offset: int = Query(0, ge=0)):
    q = db.query(models.NotificationEvent).order_by(models.NotificationEvent.created_at.desc())
    if status:
        q = q.filter(models.NotificationEvent.status == status)
    if transaction_id:
        q = q.filter(models.NotificationEvent.transaction_id == transaction_id)
    return [notif_row(n) for n in q.offset(offset).limit(limit)]


@router.get("/{notif_id}")
def get_notification(notif_id: int, db: Session = Depends(get_db), user=Depends(require("transactions"))):
    n = db.get(models.NotificationEvent, notif_id)
    if not n:
        raise HTTPException(404, "Notification not found")
    return notif_row(n)


@router.post("/send-verification/{txn_id}")
def manual_send_verification(txn_id: str, db: Session = Depends(get_db),
                             user=Depends(require("developer"))):
    """Admin/Developer only. Re-sends the templated verification SMS for an
    eligible transaction. The DEMO_CUSTOMER_PHONE safety guard still applies —
    this can never message a generated customer number."""
    txn = db.get(models.Transaction, txn_id)
    if not txn:
        raise HTTPException(404, "Transaction not found")
    if txn.automation_decision not in ELIGIBLE_DECISIONS:
        raise HTTPException(422, "Transaction is not in a verification-eligible state "
                                 f"(automation_decision={txn.automation_decision})")
    merchant = db.get(models.Merchant, txn.merchant_id)
    event = send_verification_sms(db, txn, merchant.name if merchant else txn.merchant_id,
                                  actor_id=user.id)
    db.commit()
    return notif_row(event)
