"""Rule-based risk scoring engine.

The score is produced by deterministic, explainable rules — never the LLM.
The LLM only explains structured signals downstream.
"""
from __future__ import annotations

from typing import Optional
from dataclasses import dataclass


@dataclass
class TriggeredRule:
    code: str
    name: str
    points: int
    detail: str


RULES_CATALOG = [
    {"rule_code": "R-001", "name": "Amount Anomaly", "description": "Transaction amount exceeds 5x the customer's average spend.", "threshold": "amount > 5x user average", "weight": 25},
    {"rule_code": "R-002", "name": "New Device", "description": "Transaction originated from a device not previously seen for this customer.", "threshold": "is_new_device = true", "weight": 20},
    {"rule_code": "R-003", "name": "Location Jump", "description": "Transaction occurred far from the customer's home region.", "threshold": "distance_from_home > 500 miles", "weight": 20},
    {"rule_code": "R-004", "name": "Transaction Velocity", "description": "Multiple transactions in a short window suggest automated or rushed activity.", "threshold": "velocity_10_min >= 4", "weight": 20},
    {"rule_code": "R-005", "name": "Merchant Risk", "description": "Merchant has an elevated historical risk score.", "threshold": "merchant_risk_score > 0.7", "weight": 15},
    {"rule_code": "R-006", "name": "Card-Not-Present Risk", "description": "Card-not-present transactions carry elevated baseline fraud risk.", "threshold": "transaction_type = card_not_present", "weight": 10},
    {"rule_code": "R-007", "name": "Dataset Risk Signal", "description": "Balance inconsistency / fraud pattern flagged in the PaySim-derived dataset signal.", "threshold": "dataset_label = true", "weight": 20},
]

RISK_BANDS = [(85, "Critical"), (70, "High"), (40, "Medium"), (0, "Low")]

ACTIONS = {
    "Low": "Approve",
    "Medium": "Monitor",
    "High": "Hold for review",
    "Critical": "Escalate / require step-up verification",
}

STATUS_BY_LEVEL = {
    "Low": "Approved",
    "Medium": "Monitoring",
    "High": "Hold for Review",
    "Critical": "Escalated",
}


def band_for_score(score: int) -> str:
    return next(label for floor, label in RISK_BANDS if score >= floor)


def score_transaction(txn: dict, active_rule_codes: Optional[set[str]] = None) -> dict:
    """Score a transaction-like dict. Returns score, level, action, triggered rules.

    `txn` needs: amount, user_avg_amount, is_new_device, distance_from_home_miles,
    velocity_10_min, merchant_risk_score, transaction_type, dataset_label.
    """
    triggered: list[TriggeredRule] = []

    def active(code: str) -> bool:
        return active_rule_codes is None or code in active_rule_codes

    avg = max(txn.get("user_avg_amount", 0) or 0, 0.01)
    ratio = txn["amount"] / avg
    if active("R-001") and ratio > 5:
        triggered.append(TriggeredRule("R-001", "Amount Anomaly", 25, f"Amount is {ratio:.1f}x the customer's average of ${avg:,.2f}"))
    if active("R-002") and txn.get("is_new_device"):
        triggered.append(TriggeredRule("R-002", "New Device", 20, f"First transaction from device {txn.get('device_id', 'unknown')}"))
    if active("R-003") and (txn.get("distance_from_home_miles") or 0) > 500:
        triggered.append(TriggeredRule("R-003", "Location Jump", 20, f"{txn['distance_from_home_miles']:,.0f} miles from home region"))
    if active("R-004") and (txn.get("velocity_10_min") or 0) >= 4:
        triggered.append(TriggeredRule("R-004", "Transaction Velocity", 20, f"{txn['velocity_10_min']} transactions in the last 10 minutes"))
    if active("R-005") and (txn.get("merchant_risk_score") or 0) > 0.7:
        triggered.append(TriggeredRule("R-005", "Merchant Risk", 15, f"Merchant risk score {txn['merchant_risk_score']:.2f}"))
    if active("R-006") and txn.get("transaction_type") == "card_not_present":
        triggered.append(TriggeredRule("R-006", "Card-Not-Present Risk", 10, "Card-not-present channel"))
    if active("R-007") and txn.get("dataset_label"):
        triggered.append(TriggeredRule("R-007", "Dataset Risk Signal", 20, "PaySim-derived balance inconsistency signal"))

    score = min(100, sum(r.points for r in triggered))
    level = band_for_score(score)
    return {
        "score": score,
        "risk_level": level,
        "recommended_action": ACTIONS[level],
        "suggested_status": STATUS_BY_LEVEL[level],
        "rules_triggered": [r.__dict__ for r in triggered],
    }
