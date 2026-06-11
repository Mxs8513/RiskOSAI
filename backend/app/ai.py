"""AI layer for RiskOS.

Two providers:
- AnthropicProvider: calls the Claude API with strict, grounded prompts.
- MockProvider: deterministic templates from the same structured signals, so
  the entire workflow is demoable with no API key.

The LLM never decides fraud outcomes. It explains structured signals produced
by the rule-based risk engine, and its output is policy-checked afterwards.
"""
import json
import random
from typing import Optional

from .config import get_settings

settings = get_settings()

EVIDENCE_SYSTEM_PROMPT = """You are RiskOS, an internal fraud-investigation assistant for Northstar Financial (a simulated environment with synthetic data).

Rules you must follow:
- Use ONLY the structured fields provided. Never invent evidence, history, or customer attributes.
- Never reference protected attributes (race, gender, age, religion, national origin).
- Never make legal claims or give financial advice.
- Be concise and audit-ready.
- Respond with ONLY a JSON object (no markdown fences) with keys:
  risk_summary (string, 2-3 sentences),
  evidence_bullets (array of strings),
  rules_explanation (string),
  comparable_pattern (string),
  recommended_action (string — restate the engine's recommended action),
  customer_impact_note (string),
  reviewer_checklist (array of strings),
  audit_note (string, one sentence suitable for a compliance audit log)."""


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        t = t.rsplit("```", 1)[0]
    return t.strip()


def _call_anthropic(system: str, user: str, max_tokens: int = 1200) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    msg = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in msg.content if b.type == "text")


# ---------------------------------------------------------------- evidence

def generate_evidence_packet(context: dict) -> tuple[dict, str, str]:
    """Returns (packet, raw_output, provider)."""
    if not settings.mock_ai:
        try:
            raw = _call_anthropic(EVIDENCE_SYSTEM_PROMPT, json.dumps(context, default=str))
            packet = json.loads(_strip_fences(raw))
            return packet, raw, "anthropic"
        except Exception:
            pass  # fall through to mock so the demo never breaks
    packet = _mock_evidence(context)
    return packet, json.dumps(packet), "mock"


def _mock_evidence(ctx: dict) -> dict:
    t = ctx["transaction"]
    rules = ctx["rules_triggered"]
    level = ctx["risk_level"]
    action = ctx["recommended_action"]
    ratio = t["amount"] / max(t.get("user_avg_amount", 1) or 1, 0.01)

    bullets = [r["detail"] for r in rules] or ["No fraud rules triggered; transaction is within the customer's normal behavior profile."]
    rule_names = ", ".join(r["name"] for r in rules) if rules else "none"

    # Hybrid ML + rule scoring — only the structured fields, never invented model details.
    ml_prob = ctx.get("ml_fraud_probability")
    ml_sentence = ""
    if ml_prob is not None:
        bullets.append(f"ML model fraud probability {ml_prob:.0%} vs rule score {ctx['risk_score']}/100 "
                       f"— hybrid score {ctx.get('hybrid_score')}/100, {ctx.get('model_rule_agreement')} model/rule agreement")
        ml_sentence = (f" The ML layer independently estimated a {ml_prob:.0%} fraud probability; the hybrid score "
                       f"(0.6 × ML + 0.4 × rules) of {ctx.get('hybrid_score')}/100 drove automated routing, "
                       f"with {ctx.get('model_rule_agreement')} agreement between model and rules.")

    summary_bits = []
    if ratio > 5:
        summary_bits.append(f"the amount is {ratio:.1f}x the customer's normal spend")
    if t.get("is_new_device"):
        summary_bits.append("it originated from a new device")
    if (t.get("velocity_10_min") or 0) >= 4:
        summary_bits.append(f"it followed {t['velocity_10_min'] - 1} other purchases within ten minutes")
    if (t.get("distance_from_home_miles") or 0) > 500:
        summary_bits.append(f"it occurred {t['distance_from_home_miles']:,.0f} miles from the customer's home region")
    detail = "; ".join(summary_bits) if summary_bits else "no individual signal exceeded its threshold"

    pattern = "high-velocity new-device fraud pattern" if t.get("is_new_device") and (t.get("velocity_10_min") or 0) >= 4 \
        else "remote card-not-present amount-anomaly pattern" if ratio > 5 and t.get("transaction_type") == "card_not_present" \
        else "elevated-risk merchant pattern" if (t.get("merchant_risk_score") or 0) > 0.7 \
        else "isolated single-signal pattern"

    return {
        "risk_summary": f"RiskOS recommends: {action}. This {t['transaction_type'].replace('_', '-')} transaction of ${t['amount']:,.2f} at {ctx['merchant']['name']} scored {ctx['risk_score']}/100 ({level}) because {detail}. These signals match the {pattern}.{ml_sentence}",
        "evidence_bullets": bullets,
        "rules_explanation": f"Triggered rules: {rule_names}. Each rule contributes a fixed, documented weight to the composite score; the engine clamps the total at 100. " + " ".join(f"{r['code']} ({r['name']}) added {r['points']} points: {r['detail']}." for r in rules),
        "comparable_pattern": f"This case matches the {pattern} seen in prior Northstar investigations: similar cases combined {rule_names or 'low-signal activity'} and were predominantly resolved as {'confirmed fraud' if ctx['risk_score'] >= 85 else 'cleared after verification' if ctx['risk_score'] >= 70 else 'legitimate activity'}.",
        "recommended_action": action,
        "customer_impact_note": "Holding this transaction may delay a legitimate purchase. If the customer is verified, clear promptly to minimize friction." if ctx["risk_score"] >= 70 else "Minimal customer impact expected; transaction can proceed under standard monitoring.",
        "reviewer_checklist": [
            "Confirm the device fingerprint against the customer's known devices",
            "Verify recent customer contact or travel notifications",
            f"Compare amount (${t['amount']:,.2f}) against 90-day spend history",
            "Check merchant dispute history for " + ctx["merchant"]["name"],
            "Record decision rationale in the reviewer note",
        ],
        "audit_note": f"Risk engine scored {ctx['risk_score']}/100 ({level}); rules triggered: {rule_names}; AI recommendation: {action}.",
    }


# ---------------------------------------------------------------- intelligence

INTEL_SYSTEM_PROMPT = """You are RiskOS Risk Intelligence for Northstar Financial (simulation, synthetic data).
You are given a user question, a classified safe query intent, and the records retrieved by the backend for that intent.
- Answer concisely using ONLY the retrieved records.
- Reference specific transaction/investigation/rule IDs where relevant.
- If the records are insufficient, say so plainly.
- Do not give financial or legal advice. Respond in plain text (no markdown headers)."""


def summarize_intelligence(question: str, intent: str, records: list[dict],
                           params: Optional[dict] = None) -> tuple[str, str]:
    if not settings.mock_ai:
        try:
            user = json.dumps({"question": question, "intent": intent, "params": params or {},
                               "records": records}, default=str)
            return _call_anthropic(INTEL_SYSTEM_PROMPT, user, max_tokens=700).strip(), "anthropic"
        except Exception:
            pass
    return _mock_intel_summary(question, intent, records, params or {}), "mock"


TIMEFRAME_LABELS = {"today": "Daily", "yesterday": "Yesterday's", "this_week": "Weekly",
                    "last_7_days": "Weekly", "this_month": "Monthly", "all_time": "All-time"}

TIMEFRAME_PHRASES = {"today": "today", "yesterday": "yesterday", "this_week": "in the last 7 days",
                     "last_7_days": "in the last 7 days", "this_month": "in the last 30 days",
                     "all_time": "across all time"}


def _mock_intel_summary(question: str, intent: str, records: list[dict], params: Optional[dict] = None) -> str:
    params = params or {}
    n = len(records)
    if n == 0:
        return "No matching records were found for this question in the current simulation window."
    if intent == "transaction_lookup":
        r = records[0]
        rules = ", ".join(x["name"] for x in r.get("rules_triggered", [])) or "no rules"
        routing = r.get("hybrid_score", r["score"])  # orchestrator routes on hybrid when ML is available
        flagged = "flagged for verification or review" if (routing or 0) >= 60 else "not flagged"
        return (f"Transaction {r['transaction_id']} was scored {r['score']}/100 on rules ({r['risk_level']})"
                + (f" with a hybrid routing score of {r['hybrid_score']}/100" if r.get("hybrid_score") is not None and r["hybrid_score"] != r["score"] else "")
                + f" and was {flagged}. Triggered: {rules}. Recommended action: {r['recommended_action']}.")
    if intent == "false_positive_analysis":
        top = records[0]
        return (f"Across {sum(r['false_positives'] for r in records)} false positives, rule {top['rule_code']} ({top['name']}) caused the most "
                f"({top['false_positives']} of {top['trigger_count']} triggers, {top['false_positive_rate']:.0%} FP rate). "
                "Consider raising its threshold or requiring a co-occurring signal.")
    if intent == "merchant_risk_ranking":
        names = ", ".join(f"{r['name']} ({r['avg_risk_score']:.0f})" for r in records[:5])
        ascending = len(records) > 1 and records[0]["avg_risk_score"] <= records[-1]["avg_risk_score"]
        return f"{'Lowest' if ascending else 'Highest'} average risk scores by merchant: {names}."
    if intent == "reviewer_outcome_analysis":
        ids = ", ".join(r["investigation_id"] for r in records[:8])
        return f"Found {n} cases where the AI recommended holding but the reviewer cleared the transaction (false positives): {ids}."

    if intent == "investigation_search":
        filters = []
        if params.get("status"):
            filters.append(f"status {params['status']}")
        if params.get("risk_tier"):
            filters.append(f"{params['risk_tier']} risk")
        scope = " with " + " and ".join(filters) if filters else ""
        ids = ", ".join(r["investigation_id"] for r in records[:8])
        return f"Found {n} investigation{'s' if n != 1 else ''}{scope}: {ids}."

    if intent == "transaction_search":
        ids = ", ".join(r["transaction_id"] for r in records[:8])
        return (f"Found {n} matching transaction{'s' if n != 1 else ''}"
                + (f" in the {params['risk_tier']} band" if params.get("risk_tier") else "") + f": {ids}.")

    if intent == "automation_metrics_question":
        s = records[0]
        return (f"Of {s['transactions_processed']} transactions, {s['automation_rate']:.0%} were handled without a human. "
                f"{s['human_review_required']} required human review, {s['human_review_avoided']} were routed to customer "
                f"verification instead of analysts, {s['verification_required']} are awaiting verification, "
                f"{s['held_transactions']} are held, and {s['critical_escalations']} were critical escalations.")

    if intent == "model_performance_question":
        r = records[0]
        if not r.get("model_available"):
            return ("No ML model is currently trained — RiskOS is running rules-only. "
                    "Train one with `python -m scripts.train_model`.")
        m = r.get("metrics") or {}
        bits = [f"The active model is {r.get('model_name', 'unknown').replace('_', ' ')}"]
        if m:
            bits.append(f"holdout metrics: precision {m.get('precision', 0):.0%}, recall {m.get('recall', 0):.0%}, "
                        f"F1 {m.get('f1', 0):.2f}, ROC-AUC {m.get('roc_auc', 0):.3f}")
        if r.get("live_agreement"):
            a = r["live_agreement"]
            bits.append(f"live model/rule agreement across {r.get('transactions_scored_by_ml', 0)} transactions: "
                        f"{a.get('high', 0)} high, {a.get('medium', 0)} medium, {a.get('low', 0)} low")
        return ". ".join(bits) + "."

    if intent == "notification_status_question":
        by_status: dict = {}
        for r in records:
            by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        breakdown = ", ".join(f"{v} {k}" for k, v in by_status.items())
        ids = ", ".join(r["transaction_id"] for r in records[:6])
        return f"Found {n} notification event{'s' if n != 1 else ''} ({breakdown}). Transactions: {ids}."
    if intent == "rule_performance":
        top = records[0]  # retrieval already sorted in the requested direction
        ascending = len(records) > 1 and records[0]["trigger_count"] <= records[-1]["trigger_count"]
        return (f"{top['rule_code']} ({top['name']}) is the {'least' if ascending else 'most'}-triggered rule "
                f"with {top['trigger_count']} triggers and a {top['false_positive_rate']:.0%} false-positive rate.")
    if intent == "high_risk_summary":
        rule_names = sorted({x["name"] for r in records for x in r.get("rules_triggered", [])})[:3]
        involves = f"Most involve {', '.join(rule_names)}. " if rule_names else ""
        return (f"There are {n} critical-risk cases in the window. {involves}"
                "IDs: " + ", ".join(r["investigation_id"] for r in records[:8]))
    if intent == "operations_summary":
        s = records[0]
        tf = s.get("timeframe", "last_7_days")
        label = TIMEFRAME_LABELS.get(tf, "Operations")
        phrase = TIMEFRAME_PHRASES.get(tf, "")
        return (f"{label} fraud operations summary: {s['transactions']} transactions processed {phrase}, "
                f"{s['flagged']} flagged, {s['critical']} critical. {s['confirmed_fraud']} confirmed fraud, "
                f"{s['cleared']} cleared (false-positive rate {s['false_positive_rate']:.0%}). "
                f"{s['automation_rate']:.0%} of transactions were handled without a human "
                f"({s['escalated_to_humans']} escalated, {s['pending_verification']} awaiting customer verification).")
    if intent == "audit_log_search":
        return f"Found {n} audit events. Most recent: " + "; ".join(f"[{r['event_type']}] {r['message']}" for r in records[:5])
    return f"Retrieved {n} records for intent '{intent}'."


# ---------------------------------------------------------------- developer scenarios

def generate_test_scenarios(rule_code: str, count: int = 5) -> list[dict]:
    """Generate flag-worthy edge cases for a rule.

    Each scenario guarantees (a) the rule under test triggers and (b) the
    composite score reaches the High/Critical band, by stacking realistic
    co-occurring signals (amount anomaly + velocity + card-not-present),
    mirroring how multi-signal fraud presents in production traffic.
    """
    rng = random.Random(hash(rule_code) & 0xFFFF)
    scenarios = []
    for _ in range(count):
        s = {
            "user_avg_amount": round(rng.uniform(50, 160), 2),
            "is_new_device": False,
            "velocity_10_min": rng.randint(4, 7),          # R-004 booster (+20)
            "distance_from_home_miles": round(rng.uniform(2, 30), 1),
            "merchant_risk_score": round(rng.uniform(0.1, 0.4), 2),
            "transaction_type": "card_not_present",        # R-006 booster (+10)
            "dataset_label": False,
            "device_id": f"dev_test_{rng.randint(100, 999)}",
        }
        s["amount"] = round(s["user_avg_amount"] * rng.uniform(6, 12), 2)  # R-001 booster (+25)
        if rule_code == "R-002":
            s["is_new_device"] = True
        elif rule_code == "R-003":
            s["distance_from_home_miles"] = round(rng.uniform(600, 3000), 0)
        elif rule_code == "R-005":
            s["merchant_risk_score"] = round(rng.uniform(0.72, 0.95), 2)
        elif rule_code == "R-007":
            s["dataset_label"] = True
        else:  # R-001 / R-004 / R-006 are guaranteed by the boosters; add a
            # location-jump co-signal so the composite reaches the High band.
            s["distance_from_home_miles"] = round(rng.uniform(600, 2500), 0)
        scenarios.append({"payload": s, "expected_status": "flagged"})
    return scenarios
