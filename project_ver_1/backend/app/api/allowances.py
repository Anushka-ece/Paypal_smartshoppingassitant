from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import AllowanceSchedule, BudgetEnvelope, User
from app.security.auth import get_current_user, require_parent

router = APIRouter(prefix="/allowances", tags=["Allowances & Budgets"])


class BudgetCreate(BaseModel):
    child_user_id: int | None = None
    category_name: str = Field(min_length=1, max_length=80)
    allocated_amount: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    currency: Literal["USD"] = "USD"


class AllowanceScheduleCreate(BaseModel):
    child_user_id: int
    recipient_email: str = Field(min_length=3, max_length=320)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    frequency: Literal["weekly", "biweekly", "monthly"]
    next_run_at: datetime
    currency: Literal["USD"] = "USD"


@router.get("/")
def get_allowances(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(BudgetEnvelope).filter(BudgetEnvelope.family_id == current_user.family_id)
    if current_user.role == "child":
        query = query.filter(BudgetEnvelope.user_id == current_user.id)
    return query.all()


@router.post("/budgets", status_code=201)
def create_or_update_budget(
    payload: BudgetCreate,
    db: Session = Depends(get_db),
    parent: User = Depends(require_parent),
):
    if not parent.is_verified:
        raise HTTPException(status_code=403, detail="Parent account must complete verification before configuring family budgets.")
    if payload.child_user_id is not None:
        child = db.query(User).filter(
            User.id == payload.child_user_id,
            User.family_id == parent.family_id,
            User.role == "child",
        ).first()
        if child is None:
            raise HTTPException(status_code=404, detail="Child account was not found in this family.")
    envelope = db.query(BudgetEnvelope).filter(
        BudgetEnvelope.family_id == parent.family_id,
        BudgetEnvelope.user_id == payload.child_user_id,
        BudgetEnvelope.category_name == payload.category_name.strip(),
    ).first()
    if envelope is None:
        envelope = BudgetEnvelope(
            family_id=parent.family_id,
            user_id=payload.child_user_id,
            category_name=payload.category_name.strip(),
            allocated_amount=payload.allocated_amount,
            spent_amount=Decimal("0.00"),
            currency="USD",
        )
        db.add(envelope)
    else:
        envelope.allocated_amount = payload.allocated_amount
    db.commit()
    db.refresh(envelope)
    return envelope


@router.get("/schedules")
def list_allowance_schedules(
    db: Session = Depends(get_db),
    parent: User = Depends(require_parent),
):
    return db.query(AllowanceSchedule).filter(AllowanceSchedule.family_id == parent.family_id).all()


@router.post("/schedules", status_code=201)
def create_allowance_schedule(
    payload: AllowanceScheduleCreate,
    db: Session = Depends(get_db),
    parent: User = Depends(require_parent),
):
    if not parent.is_verified:
        raise HTTPException(status_code=403, detail="Parent account must complete verification before scheduling payouts.")
    if not db.query(BudgetEnvelope).filter(
        BudgetEnvelope.family_id == parent.family_id,
        BudgetEnvelope.user_id == payload.child_user_id,
    ).first():
        raise HTTPException(status_code=422, detail="Create at least one child budget envelope before scheduling an allowance payout.")
    child = db.query(User).filter(
        User.id == payload.child_user_id,
        User.family_id == parent.family_id,
        User.role == "child",
    ).first()
    if child is None:
        raise HTTPException(status_code=404, detail="Child account was not found in this family.")
    run_at = payload.next_run_at
    if run_at.tzinfo is not None:
        run_at = run_at.astimezone(timezone.utc).replace(tzinfo=None)
    if run_at <= datetime.utcnow():
        raise HTTPException(status_code=422, detail="next_run_at must be in the future.")
    schedule = AllowanceSchedule(
        family_id=parent.family_id,
        child_user_id=child.id,
        recipient_email=payload.recipient_email.strip(),
        amount=payload.amount,
        currency="USD",
        frequency=payload.frequency,
        next_run_at=run_at,
        active=True,
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule
