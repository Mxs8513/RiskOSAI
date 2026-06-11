from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..pipeline import log
from ..security import require

router = APIRouter(prefix="/rules", tags=["rules"])


def rule_stats(db: Session) -> dict[str, dict]:
    stats: dict[str, dict] = {}
    decided = {d.investigation_id: d for d in db.query(models.ReviewerDecision).all()}
    inv_by_txn = {i.transaction_id: i for i in db.query(models.Investigation).all()}
    for rs in db.query(models.RiskScore).all():
        inv = inv_by_txn.get(rs.transaction_id)
        d = decided.get(inv.id) if inv else None
        for r in rs.rules_triggered:
            s = stats.setdefault(r["code"], {"trigger_count": 0, "false_positives": 0, "true_positives": 0})
            s["trigger_count"] += 1
            if d and d.outcome == "false_positive":
                s["false_positives"] += 1
            if d and d.outcome == "true_positive":
                s["true_positives"] += 1
    for s in stats.values():
        resolved = s["false_positives"] + s["true_positives"]
        s["false_positive_rate"] = (s["false_positives"] / resolved) if resolved else 0.0
    return stats


@router.get("")
def list_rules(db: Session = Depends(get_db), user=Depends(require("rules"))):
    stats = rule_stats(db)
    return [{
        "id": r.id, "rule_code": r.rule_code, "name": r.name, "description": r.description,
        "threshold": r.threshold, "weight": r.weight, "status": r.status,
        "updated_at": r.updated_at.isoformat(),
        **stats.get(r.rule_code, {"trigger_count": 0, "false_positives": 0, "true_positives": 0, "false_positive_rate": 0.0}),
    } for r in db.query(models.FraudRule).order_by(models.FraudRule.rule_code).all()]


class RulePatch(BaseModel):
    status: Optional[str] = None
    threshold: Optional[str] = None


@router.patch("/{rule_id}")
def patch_rule(rule_id: int, body: RulePatch, db: Session = Depends(get_db), user=Depends(require("rules:edit"))):
    r = db.get(models.FraudRule, rule_id)
    if not r:
        raise HTTPException(404, "Rule not found")
    if body.status:
        if body.status not in ("active", "disabled"):
            raise HTTPException(422, "status must be 'active' or 'disabled'")
        r.status = body.status
    if body.threshold:
        r.threshold = body.threshold
    log(db, "rule_updated", actor_id=user.id, actor_role=user.role,
        message=f"{user.name} updated rule {r.rule_code}: status={r.status}", meta={"rule_code": r.rule_code})
    db.commit()
    return {"status": "ok", "rule_code": r.rule_code, "rule_status": r.status}
