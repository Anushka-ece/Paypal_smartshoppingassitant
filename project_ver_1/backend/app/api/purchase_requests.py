import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.purchase_request import PurchaseRequest, PurchaseRequestStatus
from app.services.reputation_service import ReputationService
from app.services.gemini_service import evaluate_policy
from app.services.paypal_service import PayPalService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/purchase-requests", tags=["Pre-Purchase Requests & Store Approvals"])

reputation_service = ReputationService()


def get_paypal_service() -> PayPalService:
    return PayPalService()


class PurchaseRequestCreate(BaseModel):
    family_id: int
    child_id: int
    item_name: str
    store_url: str
    amount: float
    currency: Optional[str] = "USD"


class RejectPayload(BaseModel):
    reason: str


class PurchaseRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    family_id: int
    child_id: int
    item_name: str
    store_url: str
    amount: float
    currency: str
    status: str
    ai_risk_assessment: Optional[str] = None
    rejection_reason: Optional[str] = None
    paypal_order_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@router.get("", response_model=List[PurchaseRequestResponse])
@router.get("/", response_model=List[PurchaseRequestResponse])
def list_purchase_requests(
    family_id: int = Query(...),
    child_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """List child pre-purchase requests."""
    query = db.query(PurchaseRequest).filter(PurchaseRequest.family_id == family_id)
    if child_id is not None:
        query = query.filter(PurchaseRequest.child_id == child_id)
    if status_filter is not None:
        query = query.filter(PurchaseRequest.status == status_filter)

    return query.order_by(PurchaseRequest.created_at.desc()).all()


@router.post("", response_model=PurchaseRequestResponse)
@router.post("/", response_model=PurchaseRequestResponse)
def create_purchase_request(
    payload: PurchaseRequestCreate, db: Session = Depends(get_db)
):
    """Child creates a pre-purchase approval request; system runs AI safety scan on the store."""
    threat = reputation_service.check_merchant(payload.store_url)
    ai_summary = None
    if threat["is_high_risk"]:
        ai_summary = f"Flagged by threat scan: {threat['reason']}"

    req = PurchaseRequest(
        family_id=payload.family_id,
        child_id=payload.child_id,
        item_name=payload.item_name.strip(),
        store_url=payload.store_url.strip(),
        amount=payload.amount,
        currency=payload.currency or "USD",
        status=PurchaseRequestStatus.PENDING_APPROVAL.value,
        ai_risk_assessment=ai_summary,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


@router.post("/{request_id}/approve", response_model=PurchaseRequestResponse)
def approve_purchase_request(
    request_id: int,
    db: Session = Depends(get_db),
    paypal_svc: PayPalService = Depends(get_paypal_service),
):
    """Parent approves child pre-purchase request."""
    req = db.query(PurchaseRequest).filter(PurchaseRequest.id == request_id).first()
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Purchase request {request_id} not found",
        )

    req.status = PurchaseRequestStatus.APPROVED.value
    req.paypal_order_id = f"ORDER-{req.id}-{int(datetime.utcnow().timestamp())}"
    db.commit()
    db.refresh(req)
    return req


@router.post("/{request_id}/reject", response_model=PurchaseRequestResponse)
def reject_purchase_request(
    request_id: int, payload: RejectPayload, db: Session = Depends(get_db)
):
    """Parent rejects child pre-purchase request with explanation."""
    req = db.query(PurchaseRequest).filter(PurchaseRequest.id == request_id).first()
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Purchase request {request_id} not found",
        )

    req.status = PurchaseRequestStatus.REJECTED.value
    req.rejection_reason = payload.reason.strip()
    db.commit()
    db.refresh(req)
    return req
