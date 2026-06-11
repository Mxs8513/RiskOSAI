from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload

from .. import models
from ..database import get_db
from ..document_intel import (ALLOWED_CONTENT_TYPES, MAX_FILE_BYTES, cross_check,
                              extract_document)
from ..pipeline import log
from ..security import require

router = APIRouter(tags=["evidence"])

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "evidence_uploads"


def evidence_row(e: models.EvidenceDocument) -> dict:
    return {
        "id": e.id,
        "investigation_id": e.investigation_id,
        "transaction_id": e.transaction_id,
        "uploaded_by": e.uploader.name if e.uploader else None,
        "filename": e.filename,
        "content_type": e.content_type,
        "document_type": e.document_type,
        "extraction": e.extraction,
        "claim_summary": e.claim_summary,
        "verdict": e.verdict,
        "checks": e.checks,
        "mismatches": e.mismatches,
        "confidence": e.confidence,
        "provider": e.provider,
        "created_at": e.created_at.isoformat(),
    }


def _txn_context(db: Session, txn: models.Transaction) -> dict:
    merchant = db.get(models.Merchant, txn.merchant_id)
    return {"amount": txn.amount, "merchant": merchant.name if merchant else txn.merchant_id,
            "timestamp": txn.timestamp.isoformat(), "city": txn.city, "state": txn.state}


@router.post("/investigations/{inv_id}/evidence")
async def upload_evidence(inv_id: str, file: UploadFile = File(...),
                          db: Session = Depends(get_db), user=Depends(require("investigations"))):
    """Upload a document photo/scan as case evidence. The vision model extracts
    fields (without seeing the transaction); deterministic code cross-checks
    them against the transaction record."""
    inv = db.get(models.Investigation, inv_id)
    if not inv:
        raise HTTPException(404, "Investigation not found")
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(422, f"Unsupported file type {file.content_type}; "
                                 f"use one of {sorted(ALLOWED_CONTENT_TYPES)}")
    data = await file.read()
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(422, f"File too large (max {MAX_FILE_BYTES // (1024*1024)} MB)")
    if not data:
        raise HTTPException(422, "Empty file")

    txn = db.get(models.Transaction, inv.transaction_id)
    txn_ctx = _txn_context(db, txn)

    # 1. extract (the model never sees the transaction)  2. deterministic cross-check
    extraction, provider = extract_document(data, file.content_type, file.filename or "upload", txn_ctx)
    result = cross_check(extraction, txn_ctx)

    UPLOAD_DIR.mkdir(exist_ok=True)
    safe_ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}[file.content_type]
    stored = UPLOAD_DIR / f"{uuid.uuid4().hex}{safe_ext}"
    stored.write_bytes(data)

    doc = models.EvidenceDocument(
        investigation_id=inv.id, transaction_id=inv.transaction_id, uploaded_by=user.id,
        filename=file.filename or stored.name, content_type=file.content_type,
        stored_path=str(stored), document_type=extraction.get("document_type") or "other",
        extraction=extraction, claim_summary=extraction.get("claim_summary"),
        verdict=result["verdict"], checks=result["checks"], mismatches=result["mismatches"],
        confidence=result["confidence"], provider=provider)
    db.add(doc)
    db.flush()

    log(db, "evidence_document_uploaded", actor_id=user.id, actor_role=user.role,
        investigation_id=inv.id, transaction_id=inv.transaction_id,
        message=f"{user.name} uploaded evidence document '{doc.filename}' ({doc.document_type}) to {inv.id}",
        meta={"evidence_id": doc.id, "document_type": doc.document_type})
    log(db, "evidence_document_analyzed", actor_id=user.id, actor_role=user.role,
        investigation_id=inv.id, transaction_id=inv.transaction_id,
        message=f"Evidence cross-check for '{doc.filename}': {result['verdict']} "
                f"(confidence {result['confidence']:.0%}) — {result['summary']}",
        meta={"evidence_id": doc.id, "verdict": result["verdict"],
              "confidence": result["confidence"], "mismatches": result["mismatches"],
              "provider": provider})
    db.commit()
    return {**evidence_row(doc), "summary": result["summary"]}


@router.get("/investigations/{inv_id}/evidence")
def list_evidence(inv_id: str, db: Session = Depends(get_db), user=Depends(require("investigations"))):
    if not db.get(models.Investigation, inv_id):
        raise HTTPException(404, "Investigation not found")
    docs = (db.query(models.EvidenceDocument).options(joinedload(models.EvidenceDocument.uploader))
            .filter_by(investigation_id=inv_id)
            .order_by(models.EvidenceDocument.created_at.desc()).all())
    return [evidence_row(d) for d in docs]


@router.get("/evidence/{evidence_id}/file")
def get_evidence_file(evidence_id: int, db: Session = Depends(get_db),
                      user=Depends(require("investigations"))):
    doc = db.get(models.EvidenceDocument, evidence_id)
    if not doc:
        raise HTTPException(404, "Evidence not found")
    path = Path(doc.stored_path)
    if not path.exists():
        raise HTTPException(404, "Stored file missing")
    return FileResponse(path, media_type=doc.content_type, filename=doc.filename)
