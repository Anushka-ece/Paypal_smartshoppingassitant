from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class BudgetEnvelope(Base):
    __tablename__ = "budget_envelopes"

    id = Column(Integer, primary_key=True, index=True)
    family_id = Column(Integer, ForeignKey("families.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)  # e.g., Gaming, Food & Dining, Shopping, Transport
    allocated_amount = Column(Float, default=0.0, nullable=False)
    current_spent = Column(Float, default=0.0, nullable=False)
    currency = Column(String(3), default="USD", nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    family = relationship("Family", backref="budget_envelopes")

    def __init__(self, **kwargs):
        if "allocated_amount" not in kwargs:
            kwargs["allocated_amount"] = 0.0
        if "current_spent" not in kwargs:
            kwargs["current_spent"] = 0.0
        if "currency" not in kwargs:
            kwargs["currency"] = "USD"
        if "created_at" not in kwargs:
            kwargs["created_at"] = datetime.utcnow()
        if "updated_at" not in kwargs:
            kwargs["updated_at"] = datetime.utcnow()
        super().__init__(**kwargs)
