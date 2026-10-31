from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class FamilyInvite(Base):
    __tablename__ = "family_invites"

    id = Column(Integer, primary_key=True, index=True)
    family_id = Column(Integer, ForeignKey("families.id", ondelete="CASCADE"), nullable=False)
    invited_by_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    email = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)
    invite_token = Column(String(255), unique=True, index=True, nullable=False)
    is_accepted = Column(Boolean, default=False, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    family = relationship("Family", back_populates="invites")
    invited_by = relationship("User", foreign_keys=[invited_by_id])

    def __init__(self, **kwargs):
        if "is_accepted" not in kwargs:
            kwargs["is_accepted"] = False
        if "created_at" not in kwargs:
            kwargs["created_at"] = datetime.utcnow()
        super().__init__(**kwargs)
