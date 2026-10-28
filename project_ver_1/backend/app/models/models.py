from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class Family(Base):
    __tablename__ = "families"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    users = relationship("User", back_populates="family")
    transactions = relationship("Transaction", back_populates="family")
    budgets = relationship("BudgetEnvelope", back_populates="family")
    policies = relationship("PolicyRule", back_populates="family")
    allowance_schedules = relationship("AllowanceSchedule", back_populates="family")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    family_id = Column(Integer, ForeignKey("families.id"), nullable=False, index=True)
    email = Column(String(320), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False, default="")
    role = Column(String(20), nullable=False)  # parent or child
    paypal_payer_id = Column(String(128), nullable=True, index=True)
    is_verified = Column(Boolean, default=False, nullable=False)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    family = relationship("Family", back_populates="users")
    accounts = relationship("Account", back_populates="user")
    transactions = relationship("Transaction", back_populates="user", foreign_keys="Transaction.user_id")


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("user_id", "paypal_payer_id", name="uq_user_paypal_account"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    paypal_payer_id = Column(String(128), nullable=True, index=True)
    encrypted_access_token = Column(Text, nullable=True)
    encrypted_refresh_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="accounts")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    family_id = Column(Integer, ForeignKey("families.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    paypal_transaction_id = Column(String(128), unique=True, index=True, nullable=False)
    merchant_name = Column(String(255), nullable=False, default="Unknown merchant")
    clean_merchant_name = Column(String(255), nullable=True)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), default="USD", nullable=False)
    category = Column(String(80), nullable=True)
    subcategory = Column(String(100), nullable=True)
    status = Column(String(30), default="completed", nullable=False)
    is_flagged = Column(Boolean, default=False, nullable=False)
    risk_level = Column(String(10), default="LOW", nullable=False)
    matched_rules = Column(JSON, nullable=True)
    refunded_amount = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    dispute_id = Column(String(128), nullable=True, index=True)
    dispute_status = Column(String(40), nullable=True)
    review_decision = Column(String(30), nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    family = relationship("Family", back_populates="transactions")
    user = relationship("User", back_populates="transactions", foreign_keys=[user_id])


class LedgerEntry(Base):
    """Immutable double-entry lines; one transaction's debits must equal its credits."""
    __tablename__ = "ledger_entries"

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=False, index=True)
    account_code = Column(String(80), nullable=False)
    debit = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    credit = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    currency = Column(String(3), default="USD", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class BudgetEnvelope(Base):
    __tablename__ = "budget_envelopes"
    __table_args__ = (UniqueConstraint("family_id", "user_id", "category_name", name="uq_family_user_envelope"),)

    id = Column(Integer, primary_key=True, index=True)
    family_id = Column(Integer, ForeignKey("families.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    category_name = Column(String(80), nullable=False)
    allocated_amount = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    spent_amount = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    currency = Column(String(3), default="USD", nullable=False)

    family = relationship("Family", back_populates="budgets")


class PolicyRule(Base):
    __tablename__ = "policy_rules"

    id = Column(Integer, primary_key=True, index=True)
    family_id = Column(Integer, ForeignKey("families.id"), nullable=False, index=True)
    parent_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    rule_text = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    family = relationship("Family", back_populates="policies")


class WebhookEvent(Base):
    """Deduplication ledger for PayPal's at-least-once webhook delivery."""
    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True, index=True)
    paypal_event_id = Column(String(128), unique=True, index=True, nullable=False)
    event_type = Column(String(160), nullable=False)
    processing_status = Column(String(20), default="received", nullable=False)
    received_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AllowanceSchedule(Base):
    __tablename__ = "allowance_schedules"

    id = Column(Integer, primary_key=True, index=True)
    family_id = Column(Integer, ForeignKey("families.id"), nullable=False, index=True)
    child_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    recipient_email = Column(String(320), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), default="USD", nullable=False)
    frequency = Column(String(20), nullable=False)  # weekly, biweekly, monthly
    next_run_at = Column(DateTime, nullable=False, index=True)
    active = Column(Boolean, default=True, nullable=False)
    last_payout_request_id = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    family = relationship("Family", back_populates="allowance_schedules")


class AllowancePayout(Base):
    __tablename__ = "allowance_payouts"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_allowance_payout_idempotency_key"),)

    id = Column(Integer, primary_key=True, index=True)
    schedule_id = Column(Integer, ForeignKey("allowance_schedules.id"), nullable=False, index=True)
    idempotency_key = Column(String(128), nullable=False)
    scheduled_for = Column(DateTime, nullable=False)
    status = Column(String(24), default="pending", nullable=False)
    paypal_batch_id = Column(String(128), nullable=True)
    response_json = Column(JSON, nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PurchaseRequest(Base):
    __tablename__ = "purchase_requests"

    id = Column(Integer, primary_key=True, index=True)
    family_id = Column(Integer, ForeignKey("families.id"), nullable=False, index=True)
    child_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    merchant = Column(String(255), nullable=False)
    item_url = Column(Text, nullable=True)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), default="USD", nullable=False)
    note = Column(Text, nullable=True)
    status = Column(String(20), default="pending", nullable=False)
    decided_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    decided_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


