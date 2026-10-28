from datetime import datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import PurchaseRequest, User
from app.security.auth import get_current_user, require_parent

router = APIRouter(prefix="/family", tags=["Family"])


class NewPurchaseRequest(BaseModel):
    merchant: str = Field(min_length=1, max_length=255)
    item_url: str | None = Field(default=None, max_length=2000)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: Literal["USD"] = "USD"
    note: str | None = Field(default=None, max_length=1000)


class PurchaseDecision(BaseModel):
    action: Literal["approve", "decline"]


class FamilyInvite(BaseModel):
    email: EmailStr
    role: Literal["parent", "child"]




@router.get("/members")
def list_family_members(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    members = db.query(User).filter(User.family_id == current_user.family_id).all()
    return [{"id": member.id, "email": member.email, "role": member.role, "is_verified": member.is_verified} for member in members]


@router.post("/invitations", status_code=201)
def create_family_invitation(
    payload: FamilyInvite,
    db: Session = Depends(get_db),
    parent: User = Depends(require_parent),
):
    if not parent.is_verified:
        raise HTTPException(status_code=403, detail="A verified parent is required to invite family members.")
    if payload.role == "child":
        raise HTTPException(status_code=501, detail="Child invitations are disabled pending implementation of an approved verifiable parental-consent flow.")
    raise HTTPException(status_code=501, detail="Co-parent email delivery is not configured; no invitation was created.")


@router.post("/purchase-requests", status_code=201)
def create_purchase_request(
    payload: NewPurchaseRequest,
    db: Session = Depends(get_db),
    child: User = Depends(get_current_user),
):
    if child.role != "child":
        raise HTTPException(status_code=403, detail="Only a child account may submit a purchase request.")
    if payload.item_url and not payload.item_url.lower().startswith("https://"):
        raise HTTPException(status_code=422, detail="Product links must use https.")
    request = PurchaseRequest(
        family_id=child.family_id,
        child_user_id=child.id,
        merchant=payload.merchant.strip(),
        item_url=payload.item_url,
        amount=payload.amount,
        currency="USD",
        note=payload.note,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


@router.get("/purchase-requests")
def list_purchase_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(PurchaseRequest).filter(PurchaseRequest.family_id == current_user.family_id)
    if current_user.role == "child":
        query = query.filter(PurchaseRequest.child_user_id == current_user.id)
    return query.order_by(PurchaseRequest.created_at.desc()).all()


@router.post("/purchase-requests/{request_id}/decision")
def decide_purchase_request(
    request_id: int,
    payload: PurchaseDecision,
    db: Session = Depends(get_db),
    parent: User = Depends(require_parent),
):
    request = db.query(PurchaseRequest).filter(
        PurchaseRequest.id == request_id,
        PurchaseRequest.family_id == parent.family_id,
        PurchaseRequest.status == "pending",
    ).first()
    if request is None:
        raise HTTPException(status_code=404, detail="Pending request not found in this family.")
    request.status = "approved" if payload.action == "approve" else "declined"
    request.decided_by = parent.id
    request.decided_at = datetime.utcnow()
    db.commit()
    return {"id": request.id, "status": request.status, "paypal_payment_created": False}
