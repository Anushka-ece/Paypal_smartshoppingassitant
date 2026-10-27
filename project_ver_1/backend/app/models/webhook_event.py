from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.database import Base


class ProcessedWebhookEvent(Base):
    __tablename__ = "processed_webhook_events"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String(255), unique=True, index=True, nullable=False)
    event_type = Column(String(100), nullable=False)
    resource_type = Column(String(100), nullable=True)
    resource_id = Column(String(255), nullable=True, index=True)
    status = Column(String(50), default="PROCESSED", nullable=False)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    def __init__(self, **kwargs):
        if "status" not in kwargs:
            kwargs["status"] = "PROCESSED"
        if "created_at" not in kwargs:
            kwargs["created_at"] = datetime.utcnow()
        super().__init__(**kwargs)
