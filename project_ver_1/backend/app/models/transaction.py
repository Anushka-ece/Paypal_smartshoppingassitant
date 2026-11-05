from datetime import datetime
import enum
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class TransactionStatus(str, enum.Enum):
    COMPLETED = "COMPLETED"
    FLAGGED = "FLAGGED"
    REFUNDED = "REFUNDED"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"
    DISPUTED = "DISPUTED"


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
    family_id = Column(Integer, ForeignKey("families.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    paypal_transaction_id = Column(String(255), unique=True, index=True, nullable=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="USD", nullable=False)
    status = Column(String(50), default=TransactionStatus.COMPLETED.value, nullable=False)
    merchant_name = Column(String(255), nullable=False, default="Unknown merchant")
    clean_merchant_name = Column(String(255), nullable=True)
    category = Column(String(100), nullable=True)
    subcategory = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    risk_level = Column(String(20), default="LOW", nullable=False)
    is_flagged = Column(Boolean, default=False, nullable=False)
    flagged_reason = Column(Text, nullable=True)
    parent_payment_id = Column(String(255), nullable=True, index=True)
    refund_id = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    account = relationship("Account", back_populates="transactions")
    ledger_entries = relationship("LedgerEntry", back_populates="transaction")

    def __init__(self, **kwargs):
        if "currency" not in kwargs:
            kwargs["currency"] = "USD"
        if "status" not in kwargs:
            kwargs["status"] = TransactionStatus.COMPLETED.value
        if "is_flagged" not in kwargs:
            kwargs["is_flagged"] = False
        if "created_at" not in kwargs:
            kwargs["created_at"] = datetime.utcnow()
        if "updated_at" not in kwargs:
            kwargs["updated_at"] = datetime.utcnow()
        super().__init__(**kwargs)
