"""Evidence Intake & Cross-Check (document intelligence).

Customers and analysts submit photos of receipts, tickets, bank letters,
police reports, and handwritten dispute letters. The pipeline:

1. EXTRACT — Claude vision reads the image (handwriting included) and returns
   structured fields. Deliberately, the model NEVER sees the transaction it
   will be compared against, so it cannot bias its reading toward agreement.
2. CROSS-CHECK — deterministic code (this module, not the LLM) reconciles the
   extraction against the actual transaction record: amount, date, merchant,
   location. Mismatches are evidence about the document itself.
3. The verdict, field checks, and confidence are attached to the case as
   audit-logged evidence.

Mock mode (no ANTHROPIC_API_KEY): a deterministic extraction is synthesized
from the transaction with hash-seeded variation so the full flow demos
offline. The mock does NOT read the image — it is labeled provider="mock".
"""
import base64
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from .config import get_settings

settings = get_settings()
logger = logging.getLogger("riskos.document_intel")

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_FILE_BYTES = 8 * 1024 * 1024  # 8 MB

DOC_TYPES = ("receipt", "invoice", "ticket", "bank_letter", "police_report",
             "id_document", "handwritten_letter", "other")

EXTRACTION_SYSTEM_PROMPT = """You are a document analyst for a bank fraud-operations team (simulation environment).
You are given a photo of a document a customer submitted as evidence (receipt, invoice, travel ticket, bank letter, police report, ID, or handwritten letter).

Rules:
- Report ONLY what is visible in the document. Never infer or invent values.
- If a field is not present or unreadable, use null.
- Respond with ONLY a JSON object (no markdown fences) with keys:
  document_type (one of: receipt, invoice, ticket, bank_letter, police_report, id_document, handwritten_letter, other),
  merchant_or_issuer (string|null — the business/organization named on the document),
  total_amount (number|null — the main total, no currency symbol),
  currency (string|null, e.g. "USD"),
  dates (array of ISO YYYY-MM-DD strings visible on the document),
  location_city (string|null), location_state (string|null — 2-letter if shown),
  claim_summary (1-2 sentences: what this document asserts, e.g. "Receipt for a $1,250 laptop purchased at VertMart on June 3."),
  handwritten (boolean), signatures_present (boolean),
  readable_text_quality (high|medium|low),
  suspicious_artifacts (array of strings — visible signs of tampering: mismatched fonts, misaligned totals, edited digits; empty if none)."""


def _call_anthropic_vision(image_bytes: bytes, media_type: str) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    msg = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=1024,
        system=EXTRACTION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": media_type,
                                         "data": base64.b64encode(image_bytes).decode()}},
            {"type": "text", "text": "Extract the document fields as specified."},
        ]}],
    )
    return "".join(b.text for b in msg.content if b.type == "text")


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        t = t.rsplit("```", 1)[0]
    return t.strip()


def extract_document(image_bytes: bytes, media_type: str, filename: str,
                     txn_context: dict) -> tuple:
    """Returns (extraction dict, provider). Falls back to mock on any failure."""
    if not settings.mock_ai:
        try:
            raw = _call_anthropic_vision(image_bytes, media_type)
            extraction = json.loads(_strip_fences(raw))
            return extraction, "anthropic"
        except Exception as e:
            logger.warning("Vision extraction failed (%s) — using mock", type(e).__name__)
    return _mock_extraction(image_bytes, filename, txn_context), "mock"


def _mock_extraction(image_bytes: bytes, filename: str, txn: dict) -> dict:
    """Deterministic offline extraction synthesized from the transaction.

    Hash-seeded so the same image always yields the same result; ~60% of
    documents come out consistent with the transaction, the rest carry an
    amount or merchant/date discrepancy so cross-check has something to find.
    """
    h = int(hashlib.sha256(image_bytes or filename.encode()).hexdigest(), 16)
    variant = h % 10
    fname = filename.lower()
    doc_type = ("ticket" if "ticket" in fname or "airline" in fname or "flight" in fname
                else "handwritten_letter" if "letter" in fname
                else "police_report" if "police" in fname
                else "invoice" if "invoice" in fname or "bill" in fname
                else "receipt")
    txn_date = str(txn.get("timestamp", ""))[:10] or "2026-06-01"

    if variant < 6:  # consistent document
        amount, merchant, date = txn.get("amount"), txn.get("merchant"), txn_date
        artifacts = []
    elif variant < 8:  # amount altered
        amount = round((txn.get("amount") or 100) * 0.62, 2)
        merchant, date = txn.get("merchant"), txn_date
        artifacts = ["total amount digits appear edited"]
    else:  # different merchant + shifted date
        amount = txn.get("amount")
        merchant = "QuickServe Holdings"
        try:
            date = (datetime.fromisoformat(txn_date) + timedelta(days=4)).date().isoformat()
        except ValueError:
            date = txn_date
        artifacts = []

    return {
        "document_type": doc_type,
        "merchant_or_issuer": merchant,
        "total_amount": amount,
        "currency": "USD",
        "dates": [date],
        "location_city": txn.get("city") if variant < 8 else None,
        "location_state": txn.get("state") if variant < 8 else None,
        "claim_summary": (f"{doc_type.replace('_', ' ').title()} asserting a "
                          f"${amount:,.2f} charge at {merchant} on {date}." if amount and merchant
                          else "Document with partially readable details."),
        "handwritten": doc_type == "handwritten_letter",
        "signatures_present": doc_type in ("handwritten_letter", "police_report"),
        "readable_text_quality": "medium",
        "suspicious_artifacts": artifacts,
    }


# ----------------------------------------------------------------- cross-check

def _norm(s: Optional[str]) -> set:
    return {w for w in (s or "").lower().replace(",", " ").split() if len(w) > 2}


def cross_check(extraction: dict, txn: dict) -> dict:
    """Deterministically reconcile extracted document fields with the
    transaction record. The LLM plays no part in this comparison."""
    checks = []

    doc_amount = extraction.get("total_amount")
    if doc_amount is not None and txn.get("amount") is not None:
        tolerance = max(1.0, 0.02 * float(txn["amount"]))
        checks.append({"field": "amount",
                       "document_value": f"${float(doc_amount):,.2f}",
                       "transaction_value": f"${float(txn['amount']):,.2f}",
                       "match": abs(float(doc_amount) - float(txn["amount"])) <= tolerance})

    doc_dates = extraction.get("dates") or []
    if doc_dates and txn.get("timestamp"):
        txn_date = datetime.fromisoformat(str(txn["timestamp"]).replace("Z", "")).date()
        matched = False
        for d in doc_dates:
            try:
                if abs((datetime.fromisoformat(d).date() - txn_date).days) <= 2:
                    matched = True
                    break
            except ValueError:
                continue
        checks.append({"field": "date", "document_value": ", ".join(doc_dates),
                       "transaction_value": txn_date.isoformat(), "match": matched})

    doc_merchant = extraction.get("merchant_or_issuer")
    if doc_merchant and txn.get("merchant"):
        overlap = _norm(doc_merchant) & _norm(txn["merchant"])
        checks.append({"field": "merchant", "document_value": doc_merchant,
                       "transaction_value": txn["merchant"], "match": bool(overlap)})

    if extraction.get("location_city") and txn.get("city"):
        checks.append({"field": "location",
                       "document_value": f"{extraction['location_city']}, {extraction.get('location_state') or ''}".strip(", "),
                       "transaction_value": f"{txn['city']}, {txn['state']}",
                       "match": extraction["location_city"].strip().lower() == str(txn["city"]).strip().lower()})

    matched = sum(1 for c in checks if c["match"])
    artifacts = extraction.get("suspicious_artifacts") or []
    if not checks:
        verdict = "unverifiable"
    elif matched == len(checks) and not artifacts:
        verdict = "consistent"
    elif matched >= len(checks) / 2:
        verdict = "partially_consistent"
    else:
        verdict = "inconsistent"

    quality_weight = {"high": 1.0, "medium": 0.8, "low": 0.55}.get(
        extraction.get("readable_text_quality"), 0.7)
    confidence = round((matched / len(checks)) * quality_weight, 2) if checks else 0.0

    mismatch_notes = [f"{c['field']}: document says {c['document_value']}, "
                      f"transaction shows {c['transaction_value']}"
                      for c in checks if not c["match"]]
    return {"verdict": verdict, "checks": checks, "confidence": confidence,
            "mismatches": mismatch_notes, "suspicious_artifacts": artifacts,
            "summary": _verdict_summary(verdict, matched, len(checks), mismatch_notes, artifacts)}


def _verdict_summary(verdict: str, matched: int, total: int, mismatches: list, artifacts: list) -> str:
    if verdict == "unverifiable":
        return "No comparable fields could be read from the document."
    s = f"{matched} of {total} document fields match the transaction record."
    if mismatches:
        s += " Discrepancies: " + "; ".join(mismatches) + "."
    if artifacts:
        s += " Visual tampering signals: " + "; ".join(artifacts) + "."
    if verdict == "consistent":
        s += " The document corroborates the transaction details."
    return s
