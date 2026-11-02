import hashlib
import hmac
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.config import APP_JWT_SECRET, PAYPAL_CHECKOUT_CANCEL_URL, PAYPAL_CHECKOUT_RETURN_URL
from app.database import get_db
from app.models.purchase_request import PurchaseRequest, PurchaseRequestStatus
from app.models.user import User
from app.security.auth import get_current_user, require_family_member, require_family_parent
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
    item_name: str = Field(min_length=1, max_length=255)
    store_url: str = Field(min_length=1)
    amount: float = Field(gt=0)
    currency: Optional[str] = Field(default="USD", min_length=3, max_length=3, pattern="^[A-Za-z]{3}$")


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
    paypal_approval_url: Optional[str] = None
    paypal_capture_id: Optional[str] = None
    paypal_payment_status: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


def _checkout_state(request_id: int) -> str:
    issued_at = str(int(time.time()))
    message = f"{request_id}:{issued_at}".encode("utf-8")
    signature = hmac.new(APP_JWT_SECRET.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return f"{issued_at}.{signature}"


def _validate_checkout_state(request_id: int, state: str) -> None:
    try:
        issued_text, supplied_signature = state.split(".", 1)
        issued_at = int(issued_text)
    except (ValueError, AttributeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid or expired checkout state.") from exc
    if issued_at > int(time.time()) or issued_at < int(time.time()) - 3600:
        raise HTTPException(status_code=400, detail="Invalid or expired checkout state.")
    message = f"{request_id}:{issued_text}".encode("utf-8")
    expected_signature = hmac.new(APP_JWT_SECRET.encode("utf-8"), message, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(supplied_signature, expected_signature):
        raise HTTPException(status_code=400, detail="Invalid or expired checkout state.")


def _add_checkout_state(url: str, request_id: int) -> str:
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{urlencode({'checkout_state': _checkout_state(request_id)})}"


def _owned_request(db: Session, request_id: int, user: User) -> PurchaseRequest:
    query = db.query(PurchaseRequest).filter(PurchaseRequest.id == request_id)
    if user.family_id is None:
        query = query.filter(PurchaseRequest.id == -1)
    else:
        query = query.filter(PurchaseRequest.family_id == user.family_id)
    if str(user.role).upper() == "CHILD":
        query = query.filter(PurchaseRequest.child_id == user.id)
    request = query.first()
    if request is None:
        raise HTTPException(status_code=404, detail=f"Purchase request {request_id} not found")
    return request


@router.get("", response_model=List[PurchaseRequestResponse])
@router.get("/", response_model=List[PurchaseRequestResponse])
def list_purchase_requests(
    family_id: int = Query(...),
    child_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List child pre-purchase requests."""
    require_family_member(current_user, family_id)
    query = db.query(PurchaseRequest).filter(PurchaseRequest.family_id == current_user.family_id)
    if str(current_user.role).upper() == "CHILD":
        query = query.filter(PurchaseRequest.child_id == current_user.id)
    if child_id is not None:
        if str(current_user.role).upper() == "CHILD" and child_id != current_user.id:
            raise HTTPException(status_code=404, detail="Purchase request not found")
        query = query.filter(PurchaseRequest.child_id == child_id)
    if status_filter is not None:
        query = query.filter(PurchaseRequest.status == status_filter)

    return query.order_by(PurchaseRequest.created_at.desc()).all()


@router.post("", response_model=PurchaseRequestResponse)
@router.post("/", response_model=PurchaseRequestResponse)
def create_purchase_request(
    payload: PurchaseRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Child creates a pre-purchase approval request; system runs AI safety scan on the store."""
    require_family_member(current_user, payload.family_id)
    child = (
        db.query(User)
        .filter(
            User.id == payload.child_id,
            User.family_id == current_user.family_id,
            User.role == "CHILD",
        )
        .first()
    )
    if child is None or (
        str(current_user.role).upper() == "CHILD" and current_user.id != child.id
    ):
        raise HTTPException(status_code=404, detail="Purchase request child not found")
    threat = reputation_service.check_merchant(payload.store_url)
    ai_summary = None
    if threat["is_high_risk"]:
        ai_summary = f"Flagged by threat scan: {threat['reason']}"

    req = PurchaseRequest(
        family_id=current_user.family_id,
        child_id=child.id,
        item_name=payload.item_name.strip(),
        store_url=payload.store_url.strip(),
        amount=payload.amount,
        currency=(payload.currency or "USD").upper(),
        status=PurchaseRequestStatus.PENDING_APPROVAL.value,
        ai_risk_assessment=ai_summary,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


@router.post("/{request_id}/approve", response_model=PurchaseRequestResponse)
async def approve_purchase_request(
    request_id: int,
    db: Session = Depends(get_db),
    paypal_svc: PayPalService = Depends(get_paypal_service),
    current_user: User = Depends(get_current_user),
):
    """Create a PayPal order and return the URL the buyer must approve."""
    if current_user.family_id is None:
        raise HTTPException(status_code=404, detail=f"Purchase request {request_id} not found")
    require_family_parent(current_user, current_user.family_id)
    req = _owned_request(db, request_id, current_user)

    if req.status == PurchaseRequestStatus.APPROVED.value and req.paypal_order_id:
        return req
    if req.status not in (
        PurchaseRequestStatus.PENDING_APPROVAL.value,
        PurchaseRequestStatus.PAYMENT_FAILED.value,
    ):
        raise HTTPException(status_code=409, detail="This purchase request cannot be approved in its current state.")
    if req.paypal_order_id:
        raise HTTPException(
            status_code=409,
            detail="This request already has a PayPal order; complete or cancel that order.",
        )

    req.status = PurchaseRequestStatus.ORDER_CREATING.value
    db.commit()
    try:
        order = await paypal_svc.create_order_for_approval(
            amount=req.amount,
            currency=req.currency,
            description=req.item_name,
            request_id=req.id,
            return_url=_add_checkout_state(PAYPAL_CHECKOUT_RETURN_URL.format(request_id=req.id), req.id),
            cancel_url=_add_checkout_state(PAYPAL_CHECKOUT_CANCEL_URL.format(request_id=req.id), req.id),
        )
    except Exception as exc:
        db.refresh(req)
        req.status = PurchaseRequestStatus.PAYMENT_FAILED.value
        req.paypal_payment_status = "ORDER_CREATION_FAILED"
        db.commit()
        logger.exception("PayPal order creation failed for purchase request %s", req.id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="PayPal could not create the approval order. The request can be retried.",
        ) from exc

    if not isinstance(order, dict):
        order = {}
    links = order.get("links")
    if not isinstance(links, list):
        links = []
    approval_url = next(
        (
            link.get("href")
            for link in links
            if isinstance(link, dict)
            and link.get("rel") in ("approve", "payer-action")
            and link.get("href")
        ),
        None,
    )
    order_id = order.get("id")
    req.paypal_order_id = order_id if isinstance(order_id, str) else None
    req.paypal_approval_url = approval_url
    order_status = order.get("status")
    req.paypal_payment_status = order_status if isinstance(order_status, str) else None
    if not req.paypal_order_id or not approval_url:
        req.status = PurchaseRequestStatus.PAYMENT_FAILED.value
        req.paypal_payment_status = "ORDER_APPROVAL_LINK_MISSING"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="PayPal did not return an order ID and approval URL.",
        )

    req.status = PurchaseRequestStatus.APPROVED.value
    db.commit()
    db.refresh(req)
    return req


async def _capture_purchase_request(
    req: PurchaseRequest,
    db: Session,
    paypal_svc: PayPalService,
) -> PurchaseRequest:
    if req.status == PurchaseRequestStatus.EXECUTED.value:
        return req
    if req.status == PurchaseRequestStatus.CAPTURE_PENDING.value:
        raise HTTPException(status_code=409, detail="A PayPal capture is already in progress.")
    if req.status not in (
        PurchaseRequestStatus.APPROVED.value,
        PurchaseRequestStatus.PAYMENT_FAILED.value,
    ) or not req.paypal_order_id:
        raise HTTPException(status_code=409, detail="This purchase request has no capturable PayPal order.")
    if req.paypal_payment_status in ("ORDER_CREATION_FAILED", "ORDER_APPROVAL_LINK_MISSING"):
        raise HTTPException(status_code=409, detail="The PayPal order was not created successfully.")

    req.status = PurchaseRequestStatus.CAPTURE_PENDING.value
    req.paypal_payment_status = "APPROVED"
    db.commit()
    try:
        capture = await paypal_svc.capture_approved_order(
            req.paypal_order_id,
            request_id=req.id,
        )
    except Exception as exc:
        db.refresh(req)
        req.status = PurchaseRequestStatus.PAYMENT_FAILED.value
        req.paypal_payment_status = "CAPTURE_FAILED"
        db.commit()
        logger.exception("PayPal capture failed for purchase request %s", req.id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="PayPal could not capture this approved order. The request can be retried safely.",
        ) from exc

    if not isinstance(capture, dict):
        req.status = PurchaseRequestStatus.PAYMENT_FAILED.value
        req.paypal_payment_status = "CAPTURE_FAILED"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="PayPal returned an invalid capture response.",
        )

    capture_id = None
    purchase_units = capture.get("purchase_units")
    if not isinstance(purchase_units, list):
        purchase_units = []
    for purchase_unit in purchase_units:
        if not isinstance(purchase_unit, dict):
            continue
        payments = purchase_unit.get("payments")
        if not isinstance(payments, dict):
            continue
        captures = payments.get("captures")
        if not isinstance(captures, list):
            continue
        if captures:
            first_capture = captures[0]
            if isinstance(first_capture, dict):
                capture_id = first_capture.get("id")
                break
    capture_id = capture_id or capture.get("capture_id")
    if not isinstance(capture_id, str):
        capture_id = None
    paypal_status = capture.get("status")
    req.paypal_payment_status = paypal_status if isinstance(paypal_status, str) else None
    if paypal_status != "COMPLETED" or not capture_id:
        req.status = PurchaseRequestStatus.PAYMENT_FAILED.value
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"PayPal capture did not complete (status: {paypal_status or 'unknown'}).",
        )

    req.paypal_capture_id = capture_id
    req.status = PurchaseRequestStatus.EXECUTED.value
    db.commit()
    db.refresh(req)
    return req


@router.post("/{request_id}/capture", response_model=PurchaseRequestResponse)
async def capture_purchase_request(
    request_id: int,
    db: Session = Depends(get_db),
    paypal_svc: PayPalService = Depends(get_paypal_service),
    current_user: User = Depends(get_current_user),
):
    """Capture a buyer-approved PayPal order; repeated calls are idempotent."""
    req = _owned_request(db, request_id, current_user)
    return await _capture_purchase_request(req, db, paypal_svc)


@router.get("/{request_id}/paypal/return", response_model=PurchaseRequestResponse)
async def paypal_purchase_return(
    request_id: int,
    token: str = Query(..., description="PayPal order ID returned after buyer approval"),
    checkout_state: str = Query(...),
    db: Session = Depends(get_db),
    paypal_svc: PayPalService = Depends(get_paypal_service),
):
    _validate_checkout_state(request_id, checkout_state)
    req = db.query(PurchaseRequest).filter(PurchaseRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail=f"Purchase request {request_id} not found")
    if token != req.paypal_order_id:
        raise HTTPException(status_code=400, detail="PayPal returned an order that does not match this request.")
    return await _capture_purchase_request(req, db, paypal_svc)


@router.get("/{request_id}/paypal/cancel", response_model=PurchaseRequestResponse)
def paypal_purchase_cancel(
    request_id: int,
    token: Optional[str] = Query(None, description="PayPal order ID returned when buyer cancels"),
    checkout_state: str = Query(...),
    db: Session = Depends(get_db),
):
    _validate_checkout_state(request_id, checkout_state)
    req = db.query(PurchaseRequest).filter(PurchaseRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail=f"Purchase request {request_id} not found")
    if token and token != req.paypal_order_id:
        raise HTTPException(status_code=400, detail="PayPal returned an order that does not match this request.")
    if req.status == PurchaseRequestStatus.EXECUTED.value:
        return req
    if req.status == PurchaseRequestStatus.APPROVED.value:
        req.status = PurchaseRequestStatus.CANCELLED.value
        req.paypal_payment_status = "CANCELLED"
        db.commit()
        db.refresh(req)
    return req


@router.post("/{request_id}/reject", response_model=PurchaseRequestResponse)
def reject_purchase_request(
    request_id: int,
    payload: RejectPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Parent rejects child pre-purchase request with explanation."""
    if current_user.family_id is None:
        raise HTTPException(status_code=404, detail=f"Purchase request {request_id} not found")
    require_family_parent(current_user, current_user.family_id)
    req = _owned_request(db, request_id, current_user)
    if req.status != PurchaseRequestStatus.PENDING_APPROVAL.value:
        raise HTTPException(
            status_code=409,
            detail="Only requests that have not started PayPal checkout can be rejected.",
        )

    req.status = PurchaseRequestStatus.REJECTED.value
    req.rejection_reason = payload.reason.strip()
    db.commit()
    db.refresh(req)
    return req
