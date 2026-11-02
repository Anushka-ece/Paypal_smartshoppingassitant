from datetime import datetime
import enum
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.database import Base


class UserRole(str, enum.Enum):
    PARENT = "PARENT"
    CO_PARENT = "CO_PARENT"
    CHILD = "CHILD"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False, default="")
    hashed_password = Column(String(255), nullable=False, default="")
    role = Column(String(50), default=UserRole.CHILD.value, nullable=False)
    family_id = Column(Integer, ForeignKey("families.id", ondelete="SET NULL"), nullable=True)
    age = Column(Integer, nullable=True)
    paypal_payer_id = Column(String(128), nullable=True, index=True)
    is_verified = Column(Boolean, default=False, nullable=False)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, nullable=True)
    auth_token_version = Column(Integer, default=0, nullable=False)
    coppa_consent_status = Column(String(50), default="NOT_REQUIRED", nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    family = relationship("Family", back_populates="members", foreign_keys=[family_id])
    accounts = relationship("Account", back_populates="user", cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        if "role" not in kwargs:
            kwargs["role"] = UserRole.CHILD.value
        if "name" not in kwargs and "email" in kwargs:
            kwargs["name"] = kwargs["email"].split("@")[0]
        if "is_verified" not in kwargs:
            kwargs["is_verified"] = False
        if "failed_login_attempts" not in kwargs:
            kwargs["failed_login_attempts"] = 0
        if "auth_token_version" not in kwargs:
            kwargs["auth_token_version"] = 0
        if "coppa_consent_status" not in kwargs:
            kwargs["coppa_consent_status"] = "NOT_REQUIRED"
        if "created_at" not in kwargs:
            kwargs["created_at"] = datetime.utcnow()
        if "updated_at" not in kwargs:
            kwargs["updated_at"] = datetime.utcnow()
        super().__init__(**kwargs)
