"""RiskOS AI database schema (SQLAlchemy 2.x typed ORM)."""
from __future__ import annotations

from typing import Optional
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(40))  # fraud_analyst | risk_manager | developer | admin
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[str] = mapped_column(String(20), primary_key=True)  # usr_1042
    home_city: Mapped[str] = mapped_column(String(80))
    home_state: Mapped[str] = mapped_column(String(2))
    avg_transaction_amount: Mapped[float] = mapped_column(Float)
    risk_profile: Mapped[str] = mapped_column(String(20), default="standard")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Merchant(Base):
    __tablename__ = "merchants"
    id: Mapped[str] = mapped_column(String(20), primary_key=True)  # mer_0001
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(60), index=True)
    city: Mapped[str] = mapped_column(String(80))
    state: Mapped[str] = mapped_column(String(2))
    merchant_risk_score: Mapped[float] = mapped_column(Float)  # 0..1
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Transaction(Base):
    __tablename__ = "transactions"
    id: Mapped[str] = mapped_column(String(24), primary_key=True)  # txn_839201
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), index=True)
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    city: Mapped[str] = mapped_column(String(80))
    state: Mapped[str] = mapped_column(String(2))
    device_id: Mapped[str] = mapped_column(String(40))
    transaction_type: Mapped[str] = mapped_column(String(30))  # card_present | card_not_present
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    is_new_device: Mapped[bool] = mapped_column(Boolean, default=False)
    velocity_10_min: Mapped[int] = mapped_column(Integer, default=1)
    distance_from_home_miles: Mapped[float] = mapped_column(Float, default=0)
    merchant_risk_score: Mapped[float] = mapped_column(Float, default=0.1)
    dataset_label: Mapped[bool] = mapped_column(Boolean, default=False)  # PaySim-style isFraud label
    status: Mapped[str] = mapped_column(String(30), default="Approved", index=True)
    # Automated Response Orchestrator (Phase 1)
    automation_decision: Mapped[Optional[str]] = mapped_column(String(40), nullable=True, index=True)
    verification_status: Mapped[str] = mapped_column(String(30), default="not_required")
    human_review_required: Mapped[bool] = mapped_column(Boolean, default=False)
    hold_status: Mapped[bool] = mapped_column(Boolean, default=False)
    escalation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    customer: Mapped[Customer] = relationship()
    merchant: Mapped[Merchant] = relationship()
    risk_score: Mapped["RiskScore"] = relationship(back_populates="transaction", uselist=False)


class FraudRule(Base):
    __tablename__ = "fraud_rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    rule_code: Mapped[str] = mapped_column(String(10), unique=True)  # R-001
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text)
    threshold: Mapped[str] = mapped_column(String(120))
    weight: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class RiskScore(Base):
    __tablename__ = "risk_scores"
    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.id"), unique=True, index=True)
    score: Mapped[int] = mapped_column(Integer)  # deterministic RULE score (explainability layer)
    risk_level: Mapped[str] = mapped_column(String(20))  # Low | Medium | High | Critical (rule bands)
    rules_triggered: Mapped[list] = mapped_column(JSON, default=list)  # [{code, name, points, detail}]
    recommended_action: Mapped[str] = mapped_column(String(60))
    # Hybrid ML + rule scoring (ML fields null when no model artifact exists)
    ml_fraud_probability: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    hybrid_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    model_rule_agreement: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # high | medium | low
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    transaction: Mapped[Transaction] = relationship(back_populates="risk_score")


class Investigation(Base):
    __tablename__ = "investigations"
    id: Mapped[str] = mapped_column(String(24), primary_key=True)  # inv_000123
    transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.id"), index=True)
    risk_score: Mapped[int] = mapped_column(Integer)
    risk_level: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(40), default="Open", index=True)
    assigned_to: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    ai_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommended_action: Mapped[str] = mapped_column(String(60))
    policy_check_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    transaction: Mapped[Transaction] = relationship()
    assignee: Mapped[Optional[User]] = relationship()
    ai_report: Mapped["AIReport"] = relationship(back_populates="investigation", uselist=False)
    decision: Mapped["ReviewerDecision"] = relationship(back_populates="investigation", uselist=False)


class AIReport(Base):
    __tablename__ = "ai_reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), unique=True, index=True)
    risk_summary: Mapped[str] = mapped_column(Text)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    rules_explanation: Mapped[str] = mapped_column(Text)
    comparable_pattern: Mapped[str] = mapped_column(Text)
    recommended_action: Mapped[str] = mapped_column(String(80))
    customer_impact_note: Mapped[str] = mapped_column(Text)
    reviewer_checklist: Mapped[list] = mapped_column(JSON, default=list)
    audit_note: Mapped[str] = mapped_column(Text)
    raw_model_output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    generated_by: Mapped[str] = mapped_column(String(40), default="mock")  # mock | anthropic
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    investigation: Mapped[Investigation] = relationship(back_populates="ai_report")


class PolicyCheck(Base):
    __tablename__ = "policy_checks"
    id: Mapped[int] = mapped_column(primary_key=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), index=True)
    policy_status: Mapped[str] = mapped_column(String(30))  # Passed | Needs Review | Failed
    policies_checked: Mapped[list] = mapped_column(JSON, default=list)
    issues: Mapped[list] = mapped_column(JSON, default=list)
    explanation: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ReviewerDecision(Base):
    __tablename__ = "reviewer_decisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), unique=True, index=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(40))  # confirm_fraud | clear | step_up | escalate
    reviewer_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    review_time_seconds: Mapped[int] = mapped_column(Integer, default=0)
    ai_agreed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    outcome: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)  # true_positive | false_positive | escalated | pending_verification
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    investigation: Mapped[Investigation] = relationship(back_populates="decision")
    reviewer: Mapped[User] = relationship()


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(60), index=True)
    actor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    actor_role: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    transaction_id: Mapped[Optional[str]] = mapped_column(String(24), nullable=True, index=True)
    investigation_id: Mapped[Optional[str]] = mapped_column(String(24), nullable=True, index=True)
    message: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    actor: Mapped[Optional[User]] = relationship()


class NotificationEvent(Base):
    """Outbound customer notification (Phase 2: SMS verification).

    Only the masked phone number is ever persisted — raw numbers never touch
    the database or API responses.
    """
    __tablename__ = "notification_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.id"), index=True)
    investigation_id: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    channel: Mapped[str] = mapped_column(String(20), default="sms")
    provider: Mapped[str] = mapped_column(String(20), default="twilio")
    to_phone_masked: Mapped[str] = mapped_column(String(20))
    message_body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)  # queued | sent | failed
    provider_message_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class EvidenceDocument(Base):
    """Customer/analyst-submitted document evidence (Evidence Intake & Cross-Check).

    The extraction comes from the vision model (or mock); the cross-check
    verdict is computed deterministically against the transaction record.
    """
    __tablename__ = "evidence_documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), index=True)
    transaction_id: Mapped[str] = mapped_column(String(24), index=True)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(40))
    stored_path: Mapped[str] = mapped_column(String(500))
    document_type: Mapped[str] = mapped_column(String(30), default="other")
    extraction: Mapped[dict] = mapped_column(JSON, default=dict)
    claim_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    verdict: Mapped[str] = mapped_column(String(30))  # consistent | partially_consistent | inconsistent | unverifiable
    checks: Mapped[list] = mapped_column(JSON, default=list)
    mismatches: Mapped[list] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    provider: Mapped[str] = mapped_column(String(20), default="mock")  # anthropic | mock
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    uploader: Mapped[User] = relationship()


class QueryHistory(Base):
    __tablename__ = "query_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    query_text: Mapped[str] = mapped_column(Text)
    query_intent: Mapped[str] = mapped_column(String(60))
    response_summary: Mapped[str] = mapped_column(Text)
    source_records: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class TestScenario(Base):
    __tablename__ = "test_scenarios"
    id: Mapped[int] = mapped_column(primary_key=True)
    generated_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    rule_code: Mapped[str] = mapped_column(String(10))
    scenario_payload: Mapped[dict] = mapped_column(JSON)
    expected_result: Mapped[str] = mapped_column(String(40))
    actual_result: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    passed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
