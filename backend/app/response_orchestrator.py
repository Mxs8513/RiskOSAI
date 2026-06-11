"""Automated Response Orchestrator (rollout Phase 1).

Routes each scored transaction to an automated response so only the right
cases need a human. The risk *score* still comes exclusively from the
deterministic rule engine; this layer only decides what happens next.

Response tiers (score-based) are more granular than the engine's display
bands — they split the engine's High band (70–84) into Elevated (60–74,
customer verification, no hold) and High (75–84, hold + verification):

    0–39   Low       -> approve automatically
    40–59  Medium    -> approve + monitor
    60–74  Elevated  -> require customer verification
    75–84  High      -> hold transaction + require customer verification
    85–100 Critical  -> hold + escalate to human review immediately

Only Critical tier requires a human investigation. Elevated/High cases are
parked on customer verification first; humans get involved only if the
customer reports fraud or verification expires (later rollout phases).
"""

RESPONSE_TIERS = [(85, "Critical"), (75, "High"), (60, "Elevated"), (40, "Medium"), (0, "Low")]

# automation_decision values
APPROVED = "approved"
MONITORED = "monitored"
VERIFICATION_REQUIRED = "verification_required"
HELD_FOR_VERIFICATION = "held_for_verification"
ESCALATED_TO_HUMAN = "escalated_to_human_review"

# verification_status values
VERIFICATION_NOT_REQUIRED = "not_required"
VERIFICATION_PENDING = "pending_verification"
VERIFICATION_CONFIRMED = "confirmed_legitimate"
VERIFICATION_FRAUD = "reported_fraud"
VERIFICATION_EXPIRED = "expired"
VERIFICATION_ESCALATED = "escalated"

# txn.status shown in the UI for each automation decision
STATUS_BY_DECISION = {
    APPROVED: "Approved",
    MONITORED: "Monitoring",
    VERIFICATION_REQUIRED: "Pending Verification",
    HELD_FOR_VERIFICATION: "Held for Verification",
    ESCALATED_TO_HUMAN: "Escalated",
}

AUDIT_EVENT_BY_DECISION = {
    APPROVED: "transaction_auto_approved",
    MONITORED: "transaction_monitored",
    VERIFICATION_REQUIRED: "verification_required",
    HELD_FOR_VERIFICATION: "transaction_held_for_verification",
    ESCALATED_TO_HUMAN: "critical_escalation",
}


def response_tier(score: int) -> str:
    return next(label for floor, label in RESPONSE_TIERS if score >= floor)


def decide_response(*, risk_score: int, risk_level: str, rules_triggered: list) -> dict:
    """Decide the automated response for a scored transaction.

    Returns automation_decision, verification_status, human_review_required,
    hold_status, escalation_reason, customer_action_required, response_tier.
    """
    tier = response_tier(risk_score)
    rule_codes = ", ".join(r["code"] for r in rules_triggered) or "none"

    if tier == "Low":
        decision, verification, human, hold, reason, customer = (
            APPROVED, VERIFICATION_NOT_REQUIRED, False, False, None, False)
    elif tier == "Medium":
        decision, verification, human, hold, reason, customer = (
            MONITORED, VERIFICATION_NOT_REQUIRED, False, False, None, False)
    elif tier == "Elevated":
        decision, verification, human, hold, reason, customer = (
            VERIFICATION_REQUIRED, VERIFICATION_PENDING, False, False, None, True)
    elif tier == "High":
        decision, verification, human, hold, reason, customer = (
            HELD_FOR_VERIFICATION, VERIFICATION_PENDING, False, True, None, True)
    else:  # Critical
        decision, verification, human, hold, customer = (
            ESCALATED_TO_HUMAN, VERIFICATION_ESCALATED, True, True, False)
        reason = (f"Risk score {risk_score}/100 is in the Critical band (≥85); "
                  f"rules triggered: {rule_codes}. Routed directly to human review.")

    return {
        "automation_decision": decision,
        "verification_status": verification,
        "human_review_required": human,
        "hold_status": hold,
        "escalation_reason": reason,
        "customer_action_required": customer,
        "response_tier": tier,
    }
