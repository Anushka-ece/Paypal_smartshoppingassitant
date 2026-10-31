import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.account import Account
from app.models.transaction import Transaction
from app.services.gemini_service import tier1_classifier

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transactions", tags=["Transactions & LLM Categorization"])


class ReclassifyRequest(BaseModel):
    category: str
    subcategory: Optional[str] = None
    merchant_clean_name: Optional[str] = None
    notes: Optional[str] = None


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    paypal_transaction_id: Optional[str] = None
    amount: float
    currency: str
    status: str
    merchant_name: Optional[str] = None
    clean_merchant_name: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    description: Optional[str] = None
    risk_level: Optional[str] = None
    is_flagged: bool = False
    flagged_reason: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@router.get("", response_model=List[TransactionResponse])
@router.get("/", response_model=List[TransactionResponse])
def get_transactions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    account_id: Optional[int] = Query(None),
    family_id: Optional[int] = Query(None),
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    List transactions with filtering by account_id, family_id, and category.
    """
    query = db.query(Transaction)

    if family_id is not None:
        query = query.join(Account, Transaction.account_id == Account.id).filter(
            Account.family_id == family_id
        )

    if account_id is not None:
        query = query.filter(Transaction.account_id == account_id)

    if category is not None:
        query = query.filter(Transaction.category == category)

    transactions = (
        query.order_by(Transaction.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return transactions


@router.post("/{transaction_id}/reclassify", response_model=TransactionResponse)
def reclassify_transaction(
    transaction_id: int,
    payload: ReclassifyRequest,
    db: Session = Depends(get_db),
):
    """
    Reclassifies an expense and persists the custom override into the family learning cache.
    """
    tx = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not tx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction {transaction_id} not found",
        )

    # 1. Update database transaction record
    tx.category = payload.category
    if payload.subcategory is not None:
        tx.subcategory = payload.subcategory
    if payload.merchant_clean_name is not None:
        tx.clean_merchant_name = payload.merchant_clean_name

    db.commit()
    db.refresh(tx)

    # 2. Persist custom override in family learning cache
    account = db.query(Account).filter(Account.id == tx.account_id).first()
    family_id = account.family_id if account else None

    merchant_to_learn = tx.merchant_name or tx.clean_merchant_name
    if family_id and merchant_to_learn:
        tier1_classifier.save_family_override(
            family_id=family_id,
            merchant_name=merchant_to_learn,
            category=payload.category,
            subcategory=payload.subcategory,
            merchant_clean_name=payload.merchant_clean_name or tx.clean_merchant_name,
            notes=payload.notes,
        )

    return tx
