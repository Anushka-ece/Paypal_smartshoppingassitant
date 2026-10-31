from datetime import datetime
import enum
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class PurchaseRequestStatus(str, enum.Enum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"


class PurchaseRequest(Base):
    __tablename__ = "purchase_requests"

    id = Column(Integer, primary_key=True, index=True)
    family_id = Column(Integer, ForeignKey("families.id", ondelete="CASCADE"), nullable=False)
    child_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    item_name = Column(String(255), nullable=False)
    store_url = Column(Text, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="USD", nullable=False)
    status = Column(String(50), default=PurchaseRequestStatus.PENDING_APPROVAL.value, nullable=False)
    ai_risk_assessment = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    paypal_order_id = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    family = relationship("Family", backref="purchase_requests")
    child = relationship("User", foreign_keys=[child_id], backref="purchase_requests")

    def __init__(self, **kwargs):
        if "currency" not in kwargs:
            kwargs["currency"] = "USD"
        if "status" not in kwargs:
            kwargs["status"] = PurchaseRequestStatus.PENDING_APPROVAL.value
        if "created_at" not in kwargs:
            kwargs["created_at"] = datetime.utcnow()
        if "updated_at" not in kwargs:
            kwargs["updated_at"] = datetime.utcnow()
        super().__init__(**kwargs)
