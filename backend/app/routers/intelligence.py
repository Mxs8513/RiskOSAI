"""Risk Intelligence: a safe natural-language query layer (not a chatbot).

Pipeline: question -> classify into a safe parameterized intent (deterministic,
auditable) -> extract parameters (timeframe, direction, risk tier, limit, IDs)
-> hand-written parameterized retrieval -> AI summarizes ONLY the retrieved
records. The LLM never writes SQL, never performs actions, and destructive or
sensitive requests are refused before any retrieval happens.
"""
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from .. import models
from ..ai import summarize_intelligence
from ..database import get_db
from ..pipeline import log
from ..security import require
from ..serializers import audit_row
from .metrics import compute_overview
from .rules import rule_stats

router = APIRouter(prefix="/risk-intelligence", tags=["risk-intelligence"])

SUGGESTED = [
    "Why was txn_800012 flagged?",
    "Which critical cases are still open?",
    "Which fraud rule caused the most false positives?",
    "What merchants had the lowest average risk score?",
    "Show cases where AI recommended hold but the reviewer cleared it.",
    "Generate a weekly fraud operations summary.",
    "How many transactions were automated this week?",
    "Show notification failures.",
]

SAFE_ALTERNATIVES = [
    "Show open fraud cases",
    "Summarize fraud operations for this week",
    "Show audit events for a transaction",
    "Which rule has the most false positives?",
]

# ---------------------------------------------------------------- parameter parsing

ASCENDING_WORDS = ("lowest", "least", "safest", "best", "fewest", "smallest", "bottom")

TIMEFRAMES = {
    "today": ("today", timedelta(days=1)),
    "yesterday": ("yesterday", timedelta(days=2)),
    "this week": ("this_week", timedelta(days=7)),
    "weekly": ("this_week", timedelta(days=7)),
    "last 7 days": ("last_7_days", timedelta(days=7)),
    "past week": ("last_7_days", timedelta(days=7)),
    "this month": ("this_month", timedelta(days=30)),
    "monthly": ("this_month", timedelta(days=30)),
    "last 30 days": ("this_month", timedelta(days=30)),
    "all time": ("all_time", None),
    "daily": ("today", timedelta(days=1)),
}

TIMEFRAME_LABELS = {"today": "Daily", "yesterday": "Yesterday's", "this_week": "Weekly",
                    "last_7_days": "Weekly", "this_month": "Monthly", "all_time": "All-time"}

STATUS_WORDS = {"open": "Open", "cleared": "Cleared", "confirmed": "Confirmed Fraud",
                "escalated": "Escalated", "hold": "Hold for Review"}

TIER_WORDS = {"critical": "Critical", "high": "High", "medium": "Medium", "low": "Low"}

# Destructive / action / sensitive patterns — Risk Intelligence is read-only.
UNSAFE_PATTERNS = [
    (r"\b(delete|drop|erase|wipe|purge|truncate|destroy)\b", "destructive"),
    (r"\bremove\b.*\b(case|cases|transaction|log|logs|record|records|data|investigation)", "destructive"),
    (r"\b(approve|clear|close|decline|block|cancel|reset)\b.*\b(all|every|everything)\b", "bulk_action"),
    (r"\ball\b.*\b(approve|clear|close|decline)\b", "bulk_action"),
    (r"\bsend\b.*\b(sms|text|message|email|call)\b", "outbound_action"),
    (r"\b(sql|query language|select \*|update |insert |drop table)\b", "sql"),
    (r"\b(secret|secrets|password|passwords|api key|auth token|credential|credentials|\.env)\b", "sensitive"),
    (r"\b(modify|update|change|edit|override)\b.*\b(rule|score|status|record|case|threshold)", "mutation"),
]


def parse_timeframe(ql: str) -> Optional[str]:
    for phrase, (key, _) in TIMEFRAMES.items():
        if phrase in ql:
            return key
    return None


def timeframe_cutoff(key: Optional[str]):
    if not key or key == "all_time":
        return None
    delta = next((d for _, (k, d) in TIMEFRAMES.items() if k == key and d), timedelta(days=7))
    return datetime.now(timezone.utc).replace(tzinfo=None) - delta


def parse_limit(ql: str, default: int = 10) -> int:
    m = re.search(r"\btop (\d{1,2})\b", ql) or re.search(r"\b(\d{1,2}) (?:merchants|rules|cases|transactions|results)\b", ql)
    return min(int(m.group(1)), 25) if m else default


def _direction(ql: str) -> str:
    return "asc" if any(w in ql for w in ASCENDING_WORDS) else "desc"


def _word(ql: str, *words: str) -> bool:
    return any(re.search(rf"\b{w}\b", ql) for w in words)


# ---------------------------------------------------------------- intent router

def classify_intent(q: str) -> tuple:
    """Returns (intent, params). params always includes 'confidence'."""
    ql = q.lower()

    # 0. safety gate — before anything else
    for pattern, category in UNSAFE_PATTERNS:
        if re.search(pattern, ql):
            return "unsafe_destructive_request", {"category": category, "confidence": "high"}

    txn = re.search(r"txn_\d+", ql)
    inv = re.search(r"inv_\d+", ql)
    timeframe = parse_timeframe(ql)
    base = {"confidence": "high"}
    if timeframe:
        base["timeframe"] = timeframe

    # 1. ID-anchored lookups
    if txn and _word(ql, "audit", "events", "history", "trail"):
        return "audit_log_search", {**base, "transaction_id": txn.group()}
    if txn:
        return "transaction_lookup", {**base, "transaction_id": txn.group(),
                                      "explain_routing": _word(ql, "why", "routed", "routing", "approved", "held", "escalated")}
    if inv:
        return "audit_log_search", {**base, "investigation_id": inv.group()}

    # 2. rule quality
    if "false positive" in ql or _word(ql, "noisy", "noisiest", "fp"):
        return "false_positive_analysis", {**base, "direction": _direction(ql), "limit": parse_limit(ql)}

    # 3. reviewer vs AI disagreement (humans), model vs rules (ML)
    if _word(ql, "ml", "model") and _word(ql, "disagree", "disagreed", "agreement", "agree", "rules", "recall",
                                          "precision", "accuracy", "roc", "auc", "f1", "performance", "drift"):
        return "model_performance_question", {**base}
    if _word(ql, "disagree", "disagreed") or ("cleared" in ql and _word(ql, "ai", "hold", "recommended")):
        return "reviewer_outcome_analysis", {**base}

    # 4. notifications / SMS
    if _word(ql, "sms", "notification", "notifications", "twilio", "texts"):
        status = "failed" if _word(ql, "fail", "failed", "failures", "failing") \
            else "sent" if _word(ql, "sent", "delivered") \
            else "queued" if _word(ql, "queued", "pending") else None
        return "notification_status_question", {**base, "status": status, "limit": parse_limit(ql)}

    # 5. automation / orchestrator metrics
    if _word(ql, "automated", "automation", "automatically") or "human review" in ql or \
       "verification required" in ql or _word(ql, "held") and _word(ql, "many", "count", "number"):
        return "automation_metrics_question", {**base}

    # 6. model performance (no explicit "ml" word)
    if _word(ql, "recall", "precision", "roc", "auc", "f1", "confusion"):
        return "model_performance_question", {**base}

    # 7. rankings
    if _word(ql, "merchant", "merchants"):
        return "merchant_risk_ranking", {**base, "direction": _direction(ql), "limit": parse_limit(ql, 8)}
    if _word(ql, "rule", "rules", "detector", "detectors"):
        return "rule_performance", {**base, "direction": _direction(ql), "limit": parse_limit(ql)}

    # 8. case / investigation search
    if _word(ql, "case", "cases", "investigation", "investigations") or \
       (_word(ql, "critical", "flagged") and not _word(ql, "summary", "summarize")):
        params = {**base, "limit": parse_limit(ql)}
        for word, status in STATUS_WORDS.items():
            if _word(ql, word):
                params["status"] = status
                break
        for word, tier in TIER_WORDS.items():
            if _word(ql, word) or f"{word}-risk" in ql:
                params["risk_tier"] = tier
                break
        return "investigation_search", params

    # 9. operations summary
    if _word(ql, "summary", "summarize", "overview", "recap", "report") or "what happened" in ql or \
       _word(ql, "pattern", "patterns"):
        return "operations_summary", {**base, "timeframe": timeframe or "last_7_days",
                                      "timeframe_explicit": timeframe is not None}

    # 10. transaction search
    if _word(ql, "transaction", "transactions"):
        params = {**base, "limit": parse_limit(ql)}
        for word, tier in TIER_WORDS.items():
            if _word(ql, word):
                params["risk_tier"] = tier
                break
        return "transaction_search", params

    # 11. related-but-unmatched: clarify instead of failing
    if _word(ql, "fraud", "risk", "risky", "score", "scores", "alert", "alerts", "flag", "review", "customer", "spend"):
        return "related_clarification", {"confidence": "low"}

    return "unknown", {"confidence": "low"}


# ---------------------------------------------------------------- retrieval

def _windowed_summary(db: Session, cutoff) -> dict:
    tq = db.query(models.Transaction)
    iq = db.query(models.Investigation)
    dq = db.query(models.ReviewerDecision)
    if cutoff:
        tq = tq.filter(models.Transaction.timestamp >= cutoff)
        iq = iq.filter(models.Investigation.created_at >= cutoff)
        dq = dq.filter(models.ReviewerDecision.created_at >= cutoff)
    txns = tq.all()
    invs = iq.all()
    decisions = dq.all()
    resolved = [d for d in decisions if d.outcome in ("true_positive", "false_positive")]
    fp = sum(1 for d in resolved if d.outcome == "false_positive")
    automated = sum(1 for t in txns if not t.human_review_required)
    return {
        "transactions": len(txns),
        "flagged": len(invs),
        "critical": sum(1 for i in invs if i.risk_level == "Critical"),
        "confirmed_fraud": sum(1 for d in decisions if d.outcome == "true_positive"),
        "cleared": fp,
        "false_positive_rate": (fp / len(resolved)) if resolved else 0.0,
        "automated": automated,
        "automation_rate": (automated / len(txns)) if txns else 0.0,
        "pending_verification": sum(1 for t in txns if t.verification_status == "pending_verification"),
        "escalated_to_humans": sum(1 for t in txns if t.human_review_required),
    }


def retrieve(db: Session, intent: str, params: dict) -> tuple:
    """Returns (records_for_llm, source_links). Deterministic; the LLM never queries."""
    if intent == "transaction_lookup":
        rs = db.query(models.RiskScore).filter_by(transaction_id=params["transaction_id"]).first()
        if not rs:
            return [], []
        txn = db.get(models.Transaction, rs.transaction_id)
        inv = db.query(models.Investigation).filter_by(transaction_id=rs.transaction_id).first()
        rec = {"transaction_id": rs.transaction_id, "score": rs.score, "risk_level": rs.risk_level,
               "hybrid_score": rs.hybrid_score, "ml_fraud_probability": rs.ml_fraud_probability,
               "rules_triggered": rs.rules_triggered, "recommended_action": rs.recommended_action,
               "automation_decision": txn.automation_decision if txn else None,
               "verification_status": txn.verification_status if txn else None,
               "human_review_required": txn.human_review_required if txn else None,
               "investigation_id": inv.id if inv else None}
        src = [{"type": "transaction", "id": rs.transaction_id}]
        if inv:
            src.append({"type": "investigation", "id": inv.id})
        return [rec], src

    if intent in ("false_positive_analysis", "rule_performance"):
        names = {r.rule_code: r.name for r in db.query(models.FraudRule).all()}
        sort_key = "false_positives" if intent == "false_positive_analysis" else "trigger_count"
        ascending = params.get("direction") == "asc"
        recs = sorted(({"rule_code": c, "name": names.get(c, c), **s} for c, s in rule_stats(db).items()),
                      key=lambda r: r[sort_key], reverse=not ascending)[:params.get("limit", 10)]
        return recs, [{"type": "rule", "id": r["rule_code"]} for r in recs[:5]]

    if intent == "merchant_risk_ranking":
        from collections import defaultdict
        agg = defaultdict(lambda: {"total": 0, "n": 0})
        for rs in db.query(models.RiskScore).all():
            t = db.get(models.Transaction, rs.transaction_id)
            m = db.get(models.Merchant, t.merchant_id)
            agg[(m.id, m.name)]["total"] += rs.score
            agg[(m.id, m.name)]["n"] += 1
        ascending = params.get("direction") == "asc"
        recs = sorted(({"merchant_id": k[0], "name": k[1], "avg_risk_score": v["total"] / v["n"], "transactions": v["n"]}
                       for k, v in agg.items() if v["n"] >= 3),
                      key=lambda x: x["avg_risk_score"], reverse=not ascending)[:params.get("limit", 8)]
        return recs, [{"type": "merchant", "id": r["merchant_id"]} for r in recs]

    if intent == "reviewer_outcome_analysis":
        recs = []
        for d in db.query(models.ReviewerDecision).filter_by(decision="clear").all():
            inv = db.get(models.Investigation, d.investigation_id)
            if inv and inv.recommended_action.lower() != "approve":
                recs.append({"investigation_id": inv.id, "transaction_id": inv.transaction_id,
                             "risk_score": inv.risk_score, "ai_recommendation": inv.recommended_action,
                             "reviewer_decision": "clear", "outcome": d.outcome})
        return recs, [{"type": "investigation", "id": r["investigation_id"]} for r in recs[:10]]

    if intent == "investigation_search":
        q = db.query(models.Investigation).order_by(models.Investigation.created_at.desc())
        if params.get("status"):
            q = q.filter(models.Investigation.status == params["status"])
        if params.get("risk_tier"):
            q = q.filter(models.Investigation.risk_level == params["risk_tier"])
        cutoff = timeframe_cutoff(params.get("timeframe"))
        if cutoff:
            q = q.filter(models.Investigation.created_at >= cutoff)
        invs = q.limit(params.get("limit", 10)).all()
        recs = [{"investigation_id": i.id, "transaction_id": i.transaction_id, "risk_score": i.risk_score,
                 "risk_level": i.risk_level, "status": i.status, "created_at": i.created_at.isoformat()}
                for i in invs]
        return recs, [{"type": "investigation", "id": r["investigation_id"]} for r in recs]

    if intent == "transaction_search":
        q = (db.query(models.RiskScore).join(models.Transaction,
                                             models.RiskScore.transaction_id == models.Transaction.id)
             .order_by(models.Transaction.timestamp.desc()))
        if params.get("risk_tier"):
            q = q.filter(models.RiskScore.risk_level == params["risk_tier"])
        rows = q.limit(params.get("limit", 10)).all()
        recs = []
        for rs in rows:
            t = db.get(models.Transaction, rs.transaction_id)
            recs.append({"transaction_id": t.id, "amount": t.amount, "status": t.status,
                         "rule_score": rs.score, "hybrid_score": rs.hybrid_score,
                         "automation_decision": t.automation_decision})
        return recs, [{"type": "transaction", "id": r["transaction_id"]} for r in recs[:10]]

    if intent == "automation_metrics_question":
        ov = compute_overview(db)
        rec = {k: ov[k] for k in ("automation_rate", "human_review_required", "human_review_avoided",
                                  "verification_required", "held_transactions", "critical_escalations",
                                  "transactions_processed")}
        return [rec], [{"type": "metrics", "id": "overview"}]

    if intent == "model_performance_question":
        from ..ml_model import get_model_metadata
        meta = get_model_metadata()
        scored = db.query(models.RiskScore).filter(models.RiskScore.ml_fraud_probability.isnot(None)).all()
        rec = {"model_available": meta is not None}
        if meta:
            rec.update({"model_name": meta.get("model_name"), "metrics": meta.get("metrics")})
        if scored:
            from collections import Counter
            agreement = Counter(rs.model_rule_agreement for rs in scored)
            rec["live_agreement"] = {k: agreement.get(k, 0) for k in ("high", "medium", "low")}
            rec["transactions_scored_by_ml"] = len(scored)
        return [rec], [{"type": "metrics", "id": "model"}]

    if intent == "notification_status_question":
        q = db.query(models.NotificationEvent).order_by(models.NotificationEvent.created_at.desc())
        if params.get("status"):
            q = q.filter(models.NotificationEvent.status == params["status"])
        rows = q.limit(params.get("limit", 10)).all()
        recs = [{"notification_id": n.id, "transaction_id": n.transaction_id, "channel": n.channel,
                 "status": n.status, "to": n.to_phone_masked, "created_at": n.created_at.isoformat(),
                 "reason": (n.meta or {}).get("reason") or (n.meta or {}).get("error")}
                for n in rows]
        return recs, [{"type": "transaction", "id": r["transaction_id"]} for r in recs[:10]]

    if intent == "audit_log_search":
        q = db.query(models.AuditLog).options(joinedload(models.AuditLog.actor)).order_by(models.AuditLog.created_at.desc())
        if params.get("investigation_id"):
            q = q.filter(models.AuditLog.investigation_id == params["investigation_id"])
        if params.get("transaction_id"):
            q = q.filter(models.AuditLog.transaction_id == params["transaction_id"])
        rows = q.limit(12).all()
        return [audit_row(a) for a in rows], [{"type": "audit", "id": str(a.id)} for a in rows[:8]]

    # operations_summary
    tf = params.get("timeframe", "last_7_days")
    rec = {"timeframe": tf, **_windowed_summary(db, timeframe_cutoff(tf))}
    return [rec], [{"type": "metrics", "id": "overview"}]


# ---------------------------------------------------------------- endpoint

class QueryRequest(BaseModel):
    question: str = Field(min_length=2, max_length=500)


@router.get("/suggestions")
def suggestions(user=Depends(require("intelligence"))):
    return SUGGESTED


@router.post("/query")
def query(body: QueryRequest, db: Session = Depends(get_db), user=Depends(require("intelligence"))):
    intent, params = classify_intent(body.question)
    public_params = {k: v for k, v in params.items() if k != "confidence"}
    confidence = params.get("confidence", "high")

    if intent == "unsafe_destructive_request":
        answer = ("I can't perform destructive actions, bulk changes, outbound messaging, or expose "
                  "sensitive data from Risk Intelligence — it is a read-only query layer. "
                  "I can help you search, summarize, or audit fraud cases instead.")
        log(db, "risk_intelligence_query", actor_id=user.id, actor_role=user.role,
            message=f"Risk Intelligence BLOCKED unsafe request ({params.get('category')}): {body.question[:120]}",
            meta={"intent": intent, "category": params.get("category")})
        db.commit()
        return {"intent": intent, "params": public_params, "confidence": confidence, "blocked": True,
                "answer": answer, "alternatives": SAFE_ALTERNATIVES, "sources": [], "records": [], "provider": None}

    if intent in ("related_clarification", "unknown"):
        if intent == "related_clarification":
            answer = ("I can answer this a few ways — pick the closest safe question, or rephrase with a "
                      "transaction ID, merchant, rule, case status, or timeframe.")
        else:
            answer = ("I couldn't map that question to one of my safe query intents. Try one of these:\n"
                      + "\n".join(f"• {s}" for s in SUGGESTED))
        log(db, "risk_intelligence_query", actor_id=user.id, actor_role=user.role,
            message=f"Risk Intelligence query (unclassified): {body.question[:120]}", meta={"intent": intent})
        db.commit()
        return {"intent": intent, "params": public_params, "confidence": confidence, "blocked": False,
                "answer": answer, "alternatives": SUGGESTED[:4], "sources": [], "records": [], "provider": None}

    records, sources = retrieve(db, intent, params)
    answer, provider = summarize_intelligence(body.question, intent, records, params=public_params)
    db.add(models.QueryHistory(user_id=user.id, query_text=body.question, query_intent=intent,
                               response_summary=answer, source_records=sources))
    log(db, "risk_intelligence_query", actor_id=user.id, actor_role=user.role,
        message=f"Risk Intelligence query ({intent}): {body.question[:120]}",
        meta={"intent": intent, "params": public_params})
    db.commit()
    return {"intent": intent, "params": public_params, "confidence": confidence, "blocked": False,
            "answer": answer, "sources": sources, "records": records[:10], "provider": provider}
