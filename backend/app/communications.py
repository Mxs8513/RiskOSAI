"""Outbound customer communications (Phase 2: SMS verification via Twilio).

Customer messages are strict templates only — never LLM-generated.

Safety rules:
- When SMS is enabled, messages go ONLY to DEMO_CUSTOMER_PHONE (simulation
  guard). Generated customer phone numbers are never contacted.
- If SMS_ENABLED is false or Twilio isn't configured, the notification event
  is still recorded (status "queued" with a reason) and the transaction
  pipeline never crashes.
- Only masked phone numbers are persisted or returned by the API; Twilio
  credentials never leave the settings object.

Inbound replies and voice fallback are planned for later phases.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from . import models
from .config import get_settings

settings = get_settings()
logger = logging.getLogger("riskos.communications")

SMS_TEMPLATE = ("Northstar Financial: Did you attempt a ${amount:,.2f} transaction at "
                "{merchant} in {city}, {state}? Reply YES or NO.")


def mask_phone(phone: str) -> str:
    digits = "".join(c for c in (phone or "") if c.isdigit())
    return f"***-***-{digits[-4:]}" if len(digits) >= 4 else "—"


def twilio_configured() -> bool:
    return bool(settings.twilio_account_sid and settings.twilio_auth_token
                and settings.twilio_from_number and settings.demo_customer_phone)


def _send_via_twilio(to: str, body: str) -> str:
    """POST to the Twilio Messages API; returns the provider message SID.

    Kept as a tiny seam so tests can mock it — no real network calls in CI.
    """
    res = httpx.post(
        f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json",
        auth=(settings.twilio_account_sid, settings.twilio_auth_token),
        data={"To": to, "From": settings.twilio_from_number, "Body": body},
        timeout=15,
    )
    res.raise_for_status()
    return res.json()["sid"]


def send_verification_sms(db: Session, txn: models.Transaction, merchant_name: str, *,
                          actor_id: Optional[int] = None,
                          investigation_id: Optional[str] = None) -> models.NotificationEvent:
    """Create a notification event for `txn` and attempt delivery if enabled.

    Returns the event; never raises. The caller is responsible for commit.
    """
    from .pipeline import log  # local import; pipeline imports this module

    body = SMS_TEMPLATE.format(amount=txn.amount, merchant=merchant_name,
                               city=txn.city, state=txn.state)
    # Simulation guard: the ONLY number we ever contact. Generated customer
    # phone numbers do not exist in this system and must never be added here.
    to = settings.demo_customer_phone

    event = models.NotificationEvent(
        transaction_id=txn.id, investigation_id=investigation_id,
        channel="sms", provider="twilio",
        to_phone_masked=mask_phone(to), message_body=body, status="queued",
        meta={})
    db.add(event)
    db.flush()
    log(db, "verification_sms_queued", actor_id=actor_id, transaction_id=txn.id,
        message=f"Verification SMS queued for {txn.id} (to {event.to_phone_masked})",
        meta={"notification_id": event.id, "channel": "sms"})

    if not settings.sms_enabled:
        event.meta = {"reason": "sms_disabled"}
        return event
    if not twilio_configured():
        event.meta = {"reason": "twilio_not_configured"}
        return event

    logger.info("SMS send attempt: txn=%s notification=%s to=%s", txn.id, event.id, event.to_phone_masked)
    try:
        sid = _send_via_twilio(to, body)
        event.status = "sent"
        event.provider_message_id = sid
        event.sent_at = datetime.now(timezone.utc)
        logger.info("SMS sent: txn=%s notification=%s to=%s sid=%s", txn.id, event.id, event.to_phone_masked, sid)
        log(db, "verification_sms_sent", actor_id=actor_id, transaction_id=txn.id,
            message=f"Verification SMS sent for {txn.id} (to {event.to_phone_masked})",
            meta={"notification_id": event.id, "provider_message_id": sid})
    except httpx.HTTPStatusError as e:
        # Twilio rejected the request — log status + Twilio error code (no secrets)
        detail = str(e.response.status_code)
        try:
            detail += f" (Twilio error {e.response.json().get('code')})"
        except Exception:
            pass
        event.status = "failed"
        event.meta = {"error": "HTTPStatusError", "detail": detail}
        logger.warning("SMS failed: txn=%s notification=%s to=%s %s", txn.id, event.id, event.to_phone_masked, detail)
        log(db, "verification_sms_failed", actor_id=actor_id, transaction_id=txn.id,
            message=f"Verification SMS failed for {txn.id} ({detail})",
            meta={"notification_id": event.id, "error": "HTTPStatusError", "detail": detail})
    except Exception as e:
        event.status = "failed"
        event.meta = {"error": type(e).__name__}  # class name only — never credentials or response bodies
        logger.warning("SMS failed: txn=%s notification=%s to=%s error=%s", txn.id, event.id, event.to_phone_masked, type(e).__name__)
        log(db, "verification_sms_failed", actor_id=actor_id, transaction_id=txn.id,
            message=f"Verification SMS failed for {txn.id} ({type(e).__name__})",
            meta={"notification_id": event.id, "error": type(e).__name__})
    return event
