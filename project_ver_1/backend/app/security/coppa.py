from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.models import User


def require_verified_parent(parent: User) -> None:
    """Require verified adult account before actions affecting a minor's data or money."""
    if parent.role != "parent" or not parent.is_verified:
        raise HTTPException(status_code=403, detail="Verified parent/guardian authorization is required.")


def grant_parental_consent(db: Session, parent: User) -> None:
    """Record that a parent completed the deployment's approved verifiable-consent process.

    This must only be invoked after an independently verified consent ceremony, not a
    self-service checkbox or caller-controlled API flag. Production needs legal review.
    """
    require_verified_parent(parent)
    parent.is_verified = True
    db.add(parent)
    db.commit()


def consent_audit_record(parent_id: int) -> dict:
    return {"actor_parent_id": parent_id, "recorded_at": datetime.utcnow().isoformat() + "Z"}
