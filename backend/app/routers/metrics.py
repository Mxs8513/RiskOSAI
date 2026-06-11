from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..security import require
from .rules import rule_stats

router = APIRouter(prefix="/metrics", tags=["metrics"])


def compute_overview(db: Session) -> dict:
    txns = db.query(models.Transaction).count()
    invs = db.query(models.Investigation).all()
    decisions = db.query(models.ReviewerDecision).all()
    resolved = [d for d in decisions if d.outcome in ("true_positive", "false_positive")]
    fp = sum(1 for d in resolved if d.outcome == "false_positive")
    agreed = [d for d in decisions if d.ai_agreed is not None]
    stats = rule_stats(db)
    top_rule = max(stats.items(), key=lambda kv: kv[1]["trigger_count"])[0] if stats else None

    # Automated Response Orchestrator metrics
    human_required = (db.query(models.Transaction)
                      .filter(models.Transaction.human_review_required.is_(True)).count())
    # Elevated/High cases that pre-orchestrator would have gone straight to a human
    review_avoided = (db.query(models.Transaction)
                      .filter(models.Transaction.automation_decision.in_(
                          ("verification_required", "held_for_verification"))).count())
    verification_pending = (db.query(models.Transaction)
                            .filter(models.Transaction.verification_status == "pending_verification").count())
    held = db.query(models.Transaction).filter(models.Transaction.hold_status.is_(True)).count()
    critical_escalations = (db.query(models.Transaction)
                            .filter(models.Transaction.automation_decision == "escalated_to_human_review").count())
    sms_sent = db.query(models.NotificationEvent).filter_by(status="sent").count()
    sms_failed = db.query(models.NotificationEvent).filter_by(status="failed").count()
    return {
        "verification_sms_sent_count": sms_sent,
        "verification_sms_failed_count": sms_failed,
        "pending_verification_count": verification_pending,
        "automation_rate": ((txns - human_required) / txns) if txns else 0.0,
        "human_review_required": human_required,
        "human_review_avoided": review_avoided,
        "verification_required": verification_pending,
        "held_transactions": held,
        "critical_escalations": critical_escalations,
        "transactions_processed": txns,
        "flagged_alerts": len(invs),
        "critical_cases": sum(1 for i in invs if i.risk_level == "Critical"),
        "open_cases": sum(1 for i in invs if i.status == "Open"),
        "confirmed_fraud": sum(1 for d in decisions if d.outcome == "true_positive"),
        "cleared": sum(1 for d in decisions if d.outcome == "false_positive"),
        "false_positive_rate": (fp / len(resolved)) if resolved else 0.0,
        "reviewer_agreement_rate": (sum(1 for d in agreed if d.ai_agreed) / len(agreed)) if agreed else 0.0,
        "avg_review_seconds": (sum(d.review_time_seconds for d in decisions) / len(decisions)) if decisions else 0.0,
        "ai_recommendation_accuracy": (sum(1 for d in agreed if d.ai_agreed) / len(agreed)) if agreed else 0.0,
        "most_triggered_rule": top_rule,
    }


@router.get("/overview")
def overview(db: Session = Depends(get_db), user=Depends(require("overview"))):
    return compute_overview(db)


@router.get("/daily-summary")
def daily_summary(db: Session = Depends(get_db), user=Depends(require("overview"))):
    """AI-written operations summary for the Overview page (same retrieval as Risk Intelligence)."""
    from ..ai import summarize_intelligence
    from .intelligence import retrieve  # local import avoids a circular module dependency

    records, _ = retrieve(db, "operations_summary", {"timeframe": "today"})
    answer, provider = summarize_intelligence(
        "Generate a daily fraud operations summary.", "operations_summary", records,
        params={"timeframe": "today"})
    return {"summary": answer, "provider": provider}


@router.get("/model")
def model_performance(db: Session = Depends(get_db), user=Depends(require("overview"))):
    """ML model training metrics plus a live rule-vs-ML comparison.

    Returns {"available": false} when no model has been trained — the app
    runs rules-only in that case.
    """
    from ..ml_model import get_model_metadata, model_available

    meta = get_model_metadata()
    scored = (db.query(models.RiskScore)
              .filter(models.RiskScore.ml_fraud_probability.isnot(None)).all())
    live = None
    if scored:
        agreement = Counter(rs.model_rule_agreement for rs in scored)
        live = {
            "transactions_scored_by_ml": len(scored),
            "avg_rule_score": round(sum(rs.score for rs in scored) / len(scored), 1),
            "avg_ml_probability": round(sum(rs.ml_fraud_probability for rs in scored) / len(scored), 4),
            "avg_hybrid_score": round(sum(rs.hybrid_score for rs in scored) / len(scored), 1),
            "agreement_distribution": {k: agreement.get(k, 0) for k in ("high", "medium", "low")},
        }
    return {"available": meta is not None and model_available(), "metadata": meta, "live": live}


@router.get("/rules")
def rules_metrics(db: Session = Depends(get_db), user=Depends(require("metrics"))):
    names = {r.rule_code: r.name for r in db.query(models.FraudRule).all()}
    return [{"rule_code": code, "name": names.get(code, code), **s}
            for code, s in sorted(rule_stats(db).items())]


@router.get("/charts")
def charts(db: Session = Depends(get_db), user=Depends(require("overview"))):
    now = datetime.now(timezone.utc)
    days = [(now - timedelta(days=i)).date() for i in range(6, -1, -1)]
    trend = {d.isoformat(): {"date": d.strftime("%b %d"), "flagged": 0, "critical": 0, "confirmed": 0} for d in days}
    for i in db.query(models.Investigation).all():
        k = i.created_at.date().isoformat()
        if k in trend:
            trend[k]["flagged"] += 1
            if i.risk_level == "Critical":
                trend[k]["critical"] += 1
            if i.status == "Confirmed Fraud":
                trend[k]["confirmed"] += 1
    dist = Counter()
    for rs in db.query(models.RiskScore).all():
        dist[min(rs.score // 10 * 10, 90)] += 1
    outcomes = Counter(d.outcome for d in db.query(models.ReviewerDecision).all())
    merchant_risk = defaultdict(lambda: {"total": 0, "n": 0})
    for rs in (db.query(models.RiskScore).join(models.Transaction, models.RiskScore.transaction_id == models.Transaction.id).all()):
        m = db.get(models.Merchant, db.get(models.Transaction, rs.transaction_id).merchant_id)
        merchant_risk[m.name]["total"] += rs.score
        merchant_risk[m.name]["n"] += 1
    top_merchants = sorted(({"name": k, "avg_risk_score": v["total"] / v["n"], "transactions": v["n"]}
                            for k, v in merchant_risk.items() if v["n"] >= 3),
                           key=lambda x: -x["avg_risk_score"])[:8]
    return {
        "daily_trend": list(trend.values()),
        "score_distribution": [{"bucket": f"{b}-{b+9 if b < 90 else 100}", "count": c} for b, c in sorted(dist.items())],
        "reviewer_outcomes": [{"outcome": (k or "unresolved").replace("_", " "), "count": v} for k, v in outcomes.items()],
        "top_risk_merchants": top_merchants,
    }
