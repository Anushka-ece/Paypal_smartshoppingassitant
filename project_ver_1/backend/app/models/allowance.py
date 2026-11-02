from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class AllowanceSchedule(Base):
    __tablename__ = "allowance_schedules"

    id = Column(Integer, primary_key=True, index=True)
    family_id = Column(Integer, ForeignKey("families.id", ondelete="CASCADE"), nullable=False)
    child_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="USD", nullable=False)
    frequency = Column(String(20), default="WEEKLY", nullable=False)  # WEEKLY, BI_WEEKLY, MONTHLY
    is_active = Column(Boolean, default=True, nullable=False)
    is_frozen = Column(Boolean, default=False, nullable=False)
    freeze_reason = Column(Text, nullable=True)
    last_payout_date = Column(DateTime(timezone=True), nullable=True)
    last_payout_attempt_at = Column(DateTime(timezone=True), nullable=True)
    last_payout_status = Column(String(50), nullable=True)
    last_payout_batch_id = Column(String(255), nullable=True)
    last_payout_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    family = relationship("Family", backref="allowance_schedules")
    child = relationship("User", foreign_keys=[child_id], backref="allowances")

    def __init__(self, **kwargs):
        if "currency" not in kwargs:
            kwargs["currency"] = "USD"
        if "frequency" not in kwargs:
            kwargs["frequency"] = "WEEKLY"
        if "is_active" not in kwargs:
            kwargs["is_active"] = True
        if "is_frozen" not in kwargs:
            kwargs["is_frozen"] = False
        if "created_at" not in kwargs:
            kwargs["created_at"] = datetime.utcnow()
        if "updated_at" not in kwargs:
            kwargs["updated_at"] = datetime.utcnow()
        super().__init__(**kwargs)
