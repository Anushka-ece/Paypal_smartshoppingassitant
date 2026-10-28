from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import AllowanceSchedule, Transaction, User
from app.security.auth import get_current_user, require_parent

router = APIRouter(prefix="/transactions", tags=["Transactions & LLM Categorization"])


class TransactionDecision(BaseModel):
    action: Literal["approve", "review", "freeze_allowance"]


@router.get("/")
def get_transactions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List family transactions for parents or only the caller's own transactions for children."""
    query = db.query(Transaction).filter(Transaction.family_id == current_user.family_id)
    if current_user.role == "child":
        query = query.filter(Transaction.user_id == current_user.id)
    return query.order_by(Transaction.created_at.desc()).all()


@router.post("/sync-paypal", status_code=501)
def sync_paypal_transactions(parent: User = Depends(require_parent)):
    """Blocked until PayPal reporting permissions and per-family account ownership are established."""
    raise HTTPException(
        status_code=501,
        detail=(
            "Transaction Search uses app-level reporting access and can expose merchant-account records; "
            "it is not a consumer wallet history endpoint. Configure approved PayPal reporting permissions "
            "and a verified account-ownership mapping before enabling sync."
        ),
    )


@router.post("/{transaction_id}/decision")
def decide_transaction(
    transaction_id: int,
    payload: TransactionDecision,
    db: Session = Depends(get_db),
    parent: User = Depends(require_parent),
):
    transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.family_id == parent.family_id,
    ).first()
    if not parent.is_verified:
        raise HTTPException(status_code=403, detail="A verified parent is required to decide transaction reviews.")
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found in this family.")
    if payload.action == "freeze_allowance":
        db.query(AllowanceSchedule).filter(
            AllowanceSchedule.family_id == parent.family_id,
            AllowanceSchedule.active.is_(True),
        ).update({AllowanceSchedule.active: False}, synchronize_session=False)
        transaction.review_decision = "allowances_frozen"
    elif payload.action == "approve":
        transaction.is_flagged = False
        transaction.status = "approved"
        transaction.review_decision = "approved"
        transaction.reviewed_by = parent.id
        transaction.reviewed_at = datetime.utcnow()
    else:
        transaction.status = "under_review"
        transaction.review_decision = "review_requested"
        transaction.reviewed_by = parent.id
        transaction.reviewed_at = datetime.utcnow()
    db.commit()
    return {
        "status": "updated",
        "action": payload.action,
        "paypal_payment_changed": False,
        "message": "This updates the family app only; captured PayPal payments must be managed through PayPal.",
    }
