from datetime import datetime
import enum
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    CheckConstraint,
    PrimaryKeyConstraint,
)
from sqlalchemy.orm import relationship
from app.database import Base


class LedgerStatus(str, enum.Enum):
    COMPLETED = "COMPLETED"
    FLAGGED = "FLAGGED"
    REFUNDED = "REFUNDED"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"
    DISPUTED = "DISPUTED"


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    __table_args__ = (
        PrimaryKeyConstraint("id", "created_at"),
        CheckConstraint("debit_account_id != credit_account_id", name="ck_ledger_distinct_accounts"),
        CheckConstraint("amount > 0", name="ck_ledger_positive_amount"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), primary_key=True, default=datetime.utcnow, nullable=False)
    debit_account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    credit_account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="USD", nullable=False)
    status = Column(String(50), default=LedgerStatus.COMPLETED.value, nullable=False)
    transaction_id = Column(Integer, ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True)
    refund_id = Column(String(255), nullable=True)
    description = Column(String(255), nullable=True)

    debit_account = relationship("Account", foreign_keys=[debit_account_id], back_populates="debit_ledger_entries")
    credit_account = relationship("Account", foreign_keys=[credit_account_id], back_populates="credit_ledger_entries")
    transaction = relationship("Transaction", back_populates="ledger_entries")

    def __init__(self, **kwargs):
        if "currency" not in kwargs:
            kwargs["currency"] = "USD"
        if "status" not in kwargs:
            kwargs["status"] = LedgerStatus.COMPLETED.value
        if "created_at" not in kwargs:
            kwargs["created_at"] = datetime.utcnow()
        super().__init__(**kwargs)
        if self.debit_account_id is not None and self.credit_account_id is not None:
            if self.debit_account_id == self.credit_account_id:
                raise ValueError("Debit and credit accounts must be distinct in a double-entry ledger.")
        if self.amount is not None and self.amount <= 0:
            raise ValueError("Ledger entry amount must be greater than zero.")
