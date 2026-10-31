import secrets
from datetime import datetime, timedelta
from typing import Optional, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.models.family import Family
from app.models.invite import FamilyInvite
from app.security.auth import get_current_user, require_parent

router = APIRouter(prefix="/family", tags=["Family"])


class InviteRequest(BaseModel):
    email: EmailStr
    role: Literal["parent", "co_parent", "child"]
    family_id: Optional[int] = None


@router.get("/members")
def list_family_members(
    family_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """List members of a family."""
    query = db.query(User)
    if family_id:
        query = query.filter(User.family_id == family_id)
    members = query.all()
    return [
        {
            "id": m.id,
            "name": m.name,
            "email": m.email,
            "role": m.role,
            "family_id": m.family_id,
            "is_verified": getattr(m, "is_verified", False),
            "coppa_consent_status": getattr(m, "coppa_consent_status", "NOT_REQUIRED"),
        }
        for m in members
    ]


@router.post("/invitations", status_code=201)
def create_family_invitation(
    payload: InviteRequest,
    db: Session = Depends(get_db),
):
    """Create a family invitation token."""
    target_family_id = payload.family_id
    if not target_family_id:
        raise HTTPException(status_code=400, detail="family_id is required.")

    family = db.query(Family).filter(Family.id == target_family_id).first()
    if not family:
        raise HTTPException(status_code=404, detail="Family not found.")

    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(days=7)

    invite = FamilyInvite(
        family_id=family.id,
        email=str(payload.email).lower(),
        role=payload.role.upper(),
        token=token,
        expires_at=expires_at,
        is_accepted=False,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    return {
        "id": invite.id,
        "email": invite.email,
        "role": invite.role,
        "family_id": invite.family_id,
        "token": invite.token,
        "expires_at": invite.expires_at.isoformat(),
        "is_accepted": invite.is_accepted,
    }
