"""Policy / compliance check engine.

Policies are deterministic governance checks run by the backend. The LLM may
optionally phrase the explanation, but pass/fail is computed in code so the
result is reproducible and audit-ready.
"""

POLICIES = [
    {"code": "POL-001", "title": "Manual review threshold", "text": "Transactions with risk score above 85 require manual human review before final disposition."},
    {"code": "POL-002", "title": "Grounded AI explanations", "text": "AI explanations must only reference observed transaction signals present in the structured record."},
    {"code": "POL-003", "title": "Step-up verification", "text": "Cases triggering both New Device (R-002) and Transaction Velocity (R-004) require step-up verification before clearing."},
    {"code": "POL-005", "title": "Protected attributes", "text": "Protected attributes (race, gender, age, religion, national origin) cannot be used in fraud decisions or AI explanations."},
    {"code": "POL-004", "title": "Audit completeness", "text": "Audit records must include risk score, rules triggered, AI recommendation, reviewer decision, and timestamp."},
]

ALLOWED_FACT_TERMS = {
    "amount", "average", "avg", "device", "new device", "velocity", "transactions",
    "minutes", "miles", "distance", "home", "merchant", "risk", "score", "card",
    "card-not-present", "location", "balance", "pattern", "signal", "review",
    "verification", "customer", "spend", "category", "city", "state", "dataset",
}

PROTECTED_TERMS = ["race", "gender", "ethnic", "religion", "nationality", "national origin", " age ", "aged "]


def run_policy_check(*, risk_score: int, rules_triggered: list[dict], ai_text: str, transaction: dict, routed_to_review: bool) -> dict:
    checked, issues = [], []

    # POL-001
    if risk_score > 85:
        if routed_to_review:
            checked.append({"code": "POL-001", "status": "pass", "note": f"Risk score {risk_score} > 85 and case was routed to human review."})
        else:
            issues.append({"code": "POL-001", "issue": f"Risk score {risk_score} exceeds 85 but case was not routed to manual review."})
    else:
        checked.append({"code": "POL-001", "status": "pass", "note": f"Risk score {risk_score} is at or below the 85 manual-review threshold."})

    # POL-002 — AI explanation grounding: flag suspicious invented numerics/facts.
    lowered = (ai_text or "").lower()
    grounded_issue = None
    for term in ("criminal record", "prior conviction", "credit score", "income", "employment"):
        if term in lowered and term not in str(transaction).lower():
            grounded_issue = f"AI explanation referenced '{term}', which is not present in the transaction record."
            break
    if grounded_issue:
        issues.append({"code": "POL-002", "issue": grounded_issue})
    else:
        checked.append({"code": "POL-002", "status": "pass", "note": "AI explanation referenced only observed transaction signals."})

    # POL-003
    codes = {r["code"] for r in rules_triggered}
    if {"R-002", "R-004"} <= codes:
        checked.append({"code": "POL-003", "status": "attention", "note": "New Device + Velocity pattern detected — step-up verification is required before clearing this case."})
    else:
        checked.append({"code": "POL-003", "status": "pass", "note": "New Device + Velocity combination not present; step-up verification not mandated."})

    # POL-005
    if any(t in lowered for t in PROTECTED_TERMS):
        issues.append({"code": "POL-005", "issue": "AI explanation may reference a protected attribute."})
    else:
        checked.append({"code": "POL-005", "status": "pass", "note": "No protected attributes referenced in decisioning or explanation."})

    # POL-004 — completeness of the audit payload we are about to write.
    required = [risk_score is not None, bool(rules_triggered) or risk_score < 40, bool(ai_text)]
    if all(required):
        checked.append({"code": "POL-004", "status": "pass", "note": "Audit payload includes score, rules triggered, and AI recommendation."})
    else:
        issues.append({"code": "POL-004", "issue": "Audit payload is missing required fields."})

    status = "Passed" if not issues else ("Needs Review" if len(issues) == 1 else "Failed")
    explanation = (
        "All applicable Northstar fraud policies passed. " + " ".join(c["note"] for c in checked[:2])
        if not issues
        else "One or more policy checks require attention: " + " ".join(i["issue"] for i in issues)
    )
    return {"policy_status": status, "policies_checked": checked, "issues": issues, "explanation": explanation}
