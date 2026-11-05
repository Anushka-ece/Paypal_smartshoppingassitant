import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.account import Account, AccountType
from app.models.budget import BudgetEnvelope
from app.models.transaction import Transaction, TransactionStatus
from app.models.user import User
from app.security.auth import get_current_user, require_family_member, require_family_parent
from app.services.embedding_service import Tier1Classifier

logger = logging.getLogger(__name__)

tier1_classifier = Tier1Classifier()

router = APIRouter(prefix="/transactions", tags=["Transactions & LLM Categorization"])


class ReclassifyRequest(BaseModel):
    category: str
    subcategory: Optional[str] = None
    merchant_clean_name: Optional[str] = None
    notes: Optional[str] = None


class ExpenseCreate(BaseModel):
    merchant_name: str = Field(min_length=1, max_length=255)
    amount: float = Field(gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3, pattern="^[A-Za-z]{3}$")
    category: str = Field(min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=1000)


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    paypal_transaction_id: Optional[str] = None
    refund_id: Optional[str] = None
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


@router.post("", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_expense(
    payload: ExpenseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Record a family expense and update a matching category envelope."""
    if current_user.family_id is None:
        raise HTTPException(status_code=404, detail="Family not found.")
    require_family_parent(current_user, current_user.family_id)

    merchant_name = payload.merchant_name.strip()
    category = payload.category.strip()
    if not merchant_name or not category:
        raise HTTPException(status_code=422, detail="Merchant and category are required.")

    account = (
        db.query(Account)
        .filter(
            Account.user_id == current_user.id,
            Account.family_id == current_user.family_id,
            Account.account_type == AccountType.PARENT_WALLET.value,
        )
        .first()
    )
    if account is None:
        account = Account(
            user_id=current_user.id,
            family_id=current_user.family_id,
            account_type=AccountType.PARENT_WALLET.value,
            balance=0.0,
            currency=payload.currency.upper(),
        )
        db.add(account)
        db.flush()

    transaction = Transaction(
        account_id=account.id,
        family_id=current_user.family_id,
        user_id=current_user.id,
        amount=payload.amount,
        currency=payload.currency.upper(),
        status=TransactionStatus.COMPLETED.value,
        merchant_name=merchant_name,
        clean_merchant_name=merchant_name,
        category=category,
        description=payload.description.strip() if payload.description else None,
    )
    db.add(transaction)

    envelope = (
        db.query(BudgetEnvelope)
        .filter(
            BudgetEnvelope.family_id == current_user.family_id,
            BudgetEnvelope.name.ilike(category),
        )
        .first()
    )
    if envelope:
        envelope.current_spent += payload.amount

    db.commit()
    db.refresh(transaction)
    return transaction


@router.get("", response_model=List[TransactionResponse])
@router.get("/", response_model=List[TransactionResponse])
def get_transactions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    account_id: Optional[int] = Query(None),
    family_id: Optional[int] = Query(None),
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List transactions with filtering by account_id, family_id, and category.
    """
    if current_user.family_id is None:
        return []
    if family_id is not None:
        require_family_member(current_user, family_id)
    query = db.query(Transaction).join(Account, Transaction.account_id == Account.id).filter(
        Account.family_id == current_user.family_id
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
    current_user: User = Depends(get_current_user),
):
    """
    Reclassifies an expense and persists the custom override into the family learning cache.
    """
    tx = (
        db.query(Transaction)
        .join(Account, Transaction.account_id == Account.id)
        .filter(Transaction.id == transaction_id, Account.family_id == current_user.family_id)
        .first()
    )
    if not tx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction {transaction_id} not found",
        )
    account = db.query(Account).filter(Account.id == tx.account_id).first()
    if account is None:
        raise HTTPException(status_code=404, detail=f"Transaction {transaction_id} not found")
    require_family_parent(current_user, account.family_id)

    # 1. Update database transaction record
    tx.category = payload.category
    if payload.subcategory is not None:
        tx.subcategory = payload.subcategory
    if payload.merchant_clean_name is not None:
        tx.clean_merchant_name = payload.merchant_clean_name

    db.commit()
    db.refresh(tx)

    # 2. Persist custom override in family learning cache
    family_id = account.family_id

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
