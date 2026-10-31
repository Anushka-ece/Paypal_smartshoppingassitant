from datetime import datetime
import enum
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class AccountType(str, enum.Enum):
    PARENT_WALLET = "PARENT_WALLET"
    CHILD_VIRTUAL = "CHILD_VIRTUAL"
    PAYPAL_LINKED = "PAYPAL_LINKED"


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    family_id = Column(Integer, ForeignKey("families.id", ondelete="CASCADE"), nullable=True)
    account_type = Column(String(50), default=AccountType.PARENT_WALLET.value, nullable=False)
    balance = Column(Float, default=0.0, nullable=False)
    currency = Column(String(3), default="USD", nullable=False)
    paypal_account_id = Column(String(255), nullable=True, index=True)
    paypal_encrypted_token = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="accounts")
    family = relationship("Family", back_populates="accounts")
    transactions = relationship("Transaction", back_populates="account", cascade="all, delete-orphan")
    debit_ledger_entries = relationship("LedgerEntry", back_populates="debit_account", foreign_keys="LedgerEntry.debit_account_id")
    credit_ledger_entries = relationship("LedgerEntry", back_populates="credit_account", foreign_keys="LedgerEntry.credit_account_id")

    def __init__(self, **kwargs):
        if "balance" not in kwargs:
            kwargs["balance"] = 0.0
        if "currency" not in kwargs:
            kwargs["currency"] = "USD"
        if "is_active" not in kwargs:
            kwargs["is_active"] = True
        if "account_type" not in kwargs:
            kwargs["account_type"] = AccountType.PARENT_WALLET.value
        if "created_at" not in kwargs:
            kwargs["created_at"] = datetime.utcnow()
        if "updated_at" not in kwargs:
            kwargs["updated_at"] = datetime.utcnow()
        super().__init__(**kwargs)
