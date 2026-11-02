import logging
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.account import Account
from app.models.budget import BudgetEnvelope
from app.models.transaction import Transaction, TransactionStatus
from app.models.user import User
from app.security.auth import get_current_user, require_family_member, require_family_parent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/budgets", tags=["Category Budgeting & Virtual Envelopes"])


def apply_refund_to_envelope(envelope: dict, refund_amount: float) -> dict:
    """Calculates updated spent and remaining envelope balances after a refund."""
    spent = max(0.0, envelope.get("spent", 0.0) - refund_amount)
    allocated = envelope.get("allocated", 0.0)
    remaining = max(0.0, allocated - spent)
    return {
        "name": envelope.get("name"),
        "allocated": allocated,
        "spent": spent,
        "remaining": remaining,
    }


def reconcile_refund(refund_payload: dict, db: Session) -> dict:
    """
    Reconciles refund with original transaction and restores envelope balance.
    Handles PAYMENT.CAPTURE.REFUNDED and PAYMENT.SALE.REFUNDED webhooks.
    """
    refund_id = refund_payload.get("id")
    parent_payment_id = refund_payload.get("parent_payment_id")

    # Fallback to links for parent payment id if not top-level
    if not parent_payment_id and "links" in refund_payload:
        for link in refund_payload.get("links", []):
            if link.get("rel") in ["up", "capture", "parent_payment"]:
                href = link.get("href", "")
                parent_payment_id = href.rstrip("/").split("/")[-1]
                break

    amount_obj = refund_payload.get("amount", {})
    refund_amount = float(amount_obj.get("value", 0.0))

    if not parent_payment_id:
        return {"success": False, "reason": "No parent_payment_id found in refund payload"}

    # 1. Locate original transaction
    tx = db.query(Transaction).filter(Transaction.paypal_transaction_id == parent_payment_id).first()
    if not tx:
        return {"success": False, "reason": f"Original transaction {parent_payment_id} not found"}

    # 2. Determine new status: REFUNDED or PARTIALLY_REFUNDED
    if refund_amount >= tx.amount:
        tx.status = TransactionStatus.REFUNDED.value
    else:
        tx.status = TransactionStatus.PARTIALLY_REFUNDED.value

    tx.refund_id = refund_id

    # 3. Restore envelope balance for transaction family & category
    account = db.query(Account).filter(Account.id == tx.account_id).first()
    family_id = account.family_id if account else None

    if family_id and tx.category:
        envelope = (
            db.query(BudgetEnvelope)
            .filter(
                BudgetEnvelope.family_id == family_id,
                BudgetEnvelope.name.ilike(f"%{tx.category}%"),
            )
            .first()
        )
        if envelope:
            envelope.current_spent = max(0.0, envelope.current_spent - refund_amount)

    db.commit()
    db.refresh(tx)

    return {
        "success": True,
        "transaction_id": tx.id,
        "transaction_status": tx.status,
        "refund_id": tx.refund_id,
        "refund_amount": refund_amount,
    }


class EnvelopeCreate(BaseModel):
    family_id: int
    name: str
    allocated_amount: float
    currency: Optional[str] = "USD"


class EnvelopeUpdate(BaseModel):
    allocated_amount: Optional[float] = None
    name: Optional[str] = None


class EnvelopeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    family_id: int
    name: str
    allocated_amount: float
    current_spent: float
    currency: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@router.get("/envelopes", response_model=List[EnvelopeResponse])
def list_envelopes(
    family_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List virtual budget envelopes for a family."""
    require_family_member(current_user, family_id)
    envelopes = (
        db.query(BudgetEnvelope)
        .filter(BudgetEnvelope.family_id == family_id)
        .all()
    )
    return envelopes


@router.post("/envelopes", response_model=EnvelopeResponse)
def create_envelope(
    payload: EnvelopeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new virtual budget envelope."""
    require_family_parent(current_user, payload.family_id)
    envelope = BudgetEnvelope(
        family_id=payload.family_id,
        name=payload.name.strip(),
        allocated_amount=payload.allocated_amount,
        current_spent=0.0,
        currency=payload.currency or "USD",
    )
    db.add(envelope)
    db.commit()
    db.refresh(envelope)
    return envelope


@router.put("/envelopes/{envelope_id}", response_model=EnvelopeResponse)
def update_envelope(
    envelope_id: int,
    payload: EnvelopeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an existing virtual budget envelope."""
    envelope = (
        db.query(BudgetEnvelope)
        .filter(BudgetEnvelope.id == envelope_id, BudgetEnvelope.family_id == current_user.family_id)
        .first()
    )
    if not envelope:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Envelope {envelope_id} not found",
        )
    require_family_parent(current_user, envelope.family_id)
    if payload.allocated_amount is not None:
        envelope.allocated_amount = payload.allocated_amount
    if payload.name is not None:
        envelope.name = payload.name.strip()

    db.commit()
    db.refresh(envelope)
    return envelope


@router.delete("/envelopes/{envelope_id}")
def delete_envelope(
    envelope_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a budget envelope."""
    envelope = (
        db.query(BudgetEnvelope)
        .filter(BudgetEnvelope.id == envelope_id, BudgetEnvelope.family_id == current_user.family_id)
        .first()
    )
    if not envelope:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Envelope {envelope_id} not found",
        )
    require_family_parent(current_user, envelope.family_id)
    db.delete(envelope)
    db.commit()
    return {"message": f"Envelope {envelope_id} deleted successfully."}
