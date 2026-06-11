from __future__ import annotations

from typing import Optional
import random
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from .. import models
from ..database import get_db
from ..pipeline import build_enriched_txn, next_txn_id, process_transaction
from ..security import require
from ..serializers import txn_row

router = APIRouter(prefix="/transactions", tags=["transactions"])
_rng = random.Random()


@router.get("")
def list_transactions(
    db: Session = Depends(get_db),
    user=Depends(require("transactions")),
    risk_level: Optional[str] = None,
    status: Optional[str] = None,
    merchant_category: Optional[str] = None,
    search: Optional[str] = None,
    since: Optional[str] = None,
    limit: int = Query(60, le=300),
    offset: int = Query(0, ge=0),
):
    q = (db.query(models.Transaction)
         .options(joinedload(models.Transaction.merchant), joinedload(models.Transaction.risk_score))
         .order_by(models.Transaction.timestamp.desc()))
    if status:
        q = q.filter(models.Transaction.status == status)
    if since:
        try:
            q = q.filter(models.Transaction.timestamp > datetime.fromisoformat(since.replace("Z", "")))
        except ValueError:
            raise HTTPException(422, "Invalid 'since' timestamp — use ISO 8601, e.g. 2026-06-10T12:00:00Z")
    rows = [txn_row(t) for t in q.offset(offset).limit(limit * 3)]
    if risk_level:
        rows = [r for r in rows if r["risk_level"] == risk_level]
    if merchant_category:
        rows = [r for r in rows if r["merchant_category"] == merchant_category]
    if search:
        s = search.lower()
        rows = [r for r in rows if s in r["transaction_id"].lower() or s in (r["merchant"] or "").lower() or s in r["customer_id"].lower()]
    return rows[:limit]


@router.get("/{txn_id}")
def get_transaction(txn_id: str, db: Session = Depends(get_db), user=Depends(require("transactions"))):
    t = db.get(models.Transaction, txn_id)
    if not t:
        raise HTTPException(404, "Transaction not found")
    inv = db.query(models.Investigation).filter_by(transaction_id=txn_id).first()
    row = txn_row(t)
    row["investigation_id"] = inv.id if inv else None
    return row


@router.post("/generate-batch")
def generate_batch(count: int = Query(3, le=20), db: Session = Depends(get_db), user=Depends(require("transactions"))):
    """Simulation endpoint: inject `count` new live transactions through the pipeline."""
    customers = db.query(models.Customer).all()
    merchants = db.query(models.Merchant).all()
    if not customers:
        raise HTTPException(400, "Database not seeded — run `python -m scripts.seed`")
    out = []
    for _ in range(count):
        enriched = build_enriched_txn(_rng, _rng.choice(customers), _rng.choice(merchants),
                                      datetime.now(timezone.utc), next_txn_id(db))
        txn, rs, inv = process_transaction(db, enriched, actor_id=user.id)
        row = txn_row(txn)
        row["investigation_id"] = inv.id if inv else None
        out.append(row)
    return {"generated": len(out), "transactions": out}
