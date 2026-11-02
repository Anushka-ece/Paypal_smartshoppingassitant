import asyncio
import concurrent.futures
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.account import Account, AccountType
from app.models.allowance import AllowanceSchedule
from app.models.user import User
from app.services.paypal_service import PayPalService
from app.security.auth import get_current_user, require_family_member, require_family_parent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/allowances", tags=["Automated Allowances & Payouts"])


def get_paypal_service() -> PayPalService:
    return PayPalService()


def generate_payout_idempotency_key(
    family_id: int, child_id: int, date: str, allowance_id: int
) -> str:
    """Generates a deterministic idempotency key for allowance payouts."""
    return f"payout-{family_id}-{child_id}-{allowance_id}-{date}"


def should_execute_allowance(schedule: Dict[str, Any]) -> bool:
    """Verifies that an allowance is active and not frozen."""
    is_frozen = schedule.get("is_frozen", False)
    is_active = schedule.get("is_active", True)
    return is_active and not is_frozen


def disburse_allowance_schedule(
    schedule_id: int, db: Session, service: Optional[PayPalService] = None
) -> Dict[str, Any]:
    """Disburses scheduled allowance funds to child wallet/PayPal."""
    sched = db.query(AllowanceSchedule).filter(AllowanceSchedule.id == schedule_id).first()
    if not sched:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Allowance schedule {schedule_id} not found",
        )

    if sched.is_frozen:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Allowance schedule is frozen: {sched.freeze_reason or 'Parental hold'}",
        )

    if not sched.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Allowance schedule is inactive.",
        )

    child = db.query(User).filter(User.id == sched.child_id).first()
    if not child:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Allowance child account was not found.",
        )
    receiver_email = child.email

    now_date = datetime.utcnow().strftime("%Y-%m-%d")
    idempotency_key = generate_payout_idempotency_key(
        family_id=sched.family_id,
        child_id=sched.child_id,
        date=now_date,
        allowance_id=sched.id,
    )

    if (
        sched.last_payout_date
        and sched.last_payout_date.date().isoformat() == now_date
        and sched.last_payout_status == "SUCCESS"
    ):
        return {
            "status": "SUCCESS",
            "batch_id": sched.last_payout_batch_id,
            "amount": sched.amount,
            "currency": sched.currency,
            "receiver_email": receiver_email,
            "idempotency_key": idempotency_key,
        }

    attempt_time = datetime.utcnow()
    claim = (
        db.query(AllowanceSchedule)
        .filter(
            AllowanceSchedule.id == sched.id,
            or_(
                AllowanceSchedule.last_payout_status.is_(None),
                AllowanceSchedule.last_payout_status != "PROCESSING",
                AllowanceSchedule.last_payout_attempt_at
                < attempt_time - timedelta(minutes=5),
            ),
        )
        .update(
            {
                AllowanceSchedule.last_payout_status: "PROCESSING",
                AllowanceSchedule.last_payout_attempt_at: attempt_time,
                AllowanceSchedule.last_payout_error: None,
            },
            synchronize_session=False,
        )
    )
    db.commit()
    if claim != 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A PayPal payout is already in progress for this allowance.",
        )
    db.refresh(sched)

    paypal_svc = service or PayPalService()
    try:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            payout_res = asyncio.run(
                paypal_svc.execute_payout(
                    receiver_email=receiver_email,
                    amount=sched.amount,
                    idempotency_key=idempotency_key,
                    currency=sched.currency,
                )
            )
        else:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                payout_res = executor.submit(
                    asyncio.run,
                    paypal_svc.execute_payout(
                        receiver_email=receiver_email,
                        amount=sched.amount,
                        idempotency_key=idempotency_key,
                        currency=sched.currency,
                    ),
                ).result()
    except Exception as exc:
        sched.last_payout_status = "FAILED"
        sched.last_payout_error = str(exc)[:1000]
        db.commit()
        logger.exception("PayPal payout failed for allowance schedule %s", sched.id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="PayPal payout failed. No allowance funds were credited.",
        ) from exc

    payout_status = str(payout_res.get("status", "UNKNOWN")).upper()
    sched.last_payout_status = payout_status
    sched.last_payout_batch_id = payout_res.get("batch_id")
    if payout_status == "SUCCESS" and not sched.last_payout_batch_id:
        sched.last_payout_status = "FAILED"
        sched.last_payout_error = "PayPal confirmed success without a payout batch ID."
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="PayPal returned an invalid success response. No allowance funds were credited.",
        )
    sched.last_payout_error = None if payout_status == "SUCCESS" else f"PayPal payout status: {payout_status}"
    if payout_status != "SUCCESS":
        db.commit()
        if payout_status in ("PENDING", "PROCESSING"):
            return {
                "status": payout_status,
                "batch_id": sched.last_payout_batch_id,
                "amount": sched.amount,
                "currency": sched.currency,
                "receiver_email": receiver_email,
                "idempotency_key": idempotency_key,
            }
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"PayPal did not confirm payout success (status: {payout_status}). No allowance funds were credited.",
        )

    # Update account balance if child has a virtual account
    child_account = (
        db.query(Account)
        .filter(Account.user_id == sched.child_id, Account.family_id == sched.family_id)
        .first()
    )
    if child_account:
        child_account.balance += sched.amount

    sched.last_payout_date = datetime.utcnow()
    sched.last_payout_error = None
    db.commit()

    return {
        "status": payout_status,
        "batch_id": sched.last_payout_batch_id,
        "amount": sched.amount,
        "currency": sched.currency,
        "receiver_email": receiver_email,
        "idempotency_key": idempotency_key,
    }


class ScheduleCreate(BaseModel):
    family_id: int
    child_id: int
    amount: float = Field(gt=0)
    currency: Optional[str] = Field(default="USD", min_length=3, max_length=3, pattern="^[A-Za-z]{3}$")
    frequency: Optional[str] = "WEEKLY"


class FreezeRequest(BaseModel):
    reason: Optional[str] = "Parental dispute or security review"


class ScheduleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    family_id: int
    child_id: int
    amount: float
    currency: str
    frequency: str
    is_active: bool
    is_frozen: bool
    freeze_reason: Optional[str] = None
    last_payout_date: Optional[datetime] = None
    last_payout_status: Optional[str] = None
    last_payout_attempt_at: Optional[datetime] = None
    last_payout_batch_id: Optional[str] = None
    last_payout_error: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@router.get("", response_model=List[ScheduleResponse])
@router.get("/", response_model=List[ScheduleResponse])
def list_allowances(
    family_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List allowance schedules for a family."""
    require_family_member(current_user, family_id)
    schedules = (
        db.query(AllowanceSchedule)
        .filter(AllowanceSchedule.family_id == family_id)
        .all()
    )
    return schedules


@router.post("", response_model=ScheduleResponse)
@router.post("/", response_model=ScheduleResponse)
def create_allowance(
    payload: ScheduleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new recurring allowance schedule."""
    require_family_parent(current_user, payload.family_id)
    child = (
        db.query(User)
        .filter(User.id == payload.child_id, User.family_id == payload.family_id, User.role == "CHILD")
        .first()
    )
    if child is None:
        raise HTTPException(status_code=404, detail="Allowance child account was not found.")
    sched = AllowanceSchedule(
        family_id=payload.family_id,
        child_id=payload.child_id,
        amount=payload.amount,
        currency=(payload.currency or "USD").upper(),
        frequency=payload.frequency or "WEEKLY",
        is_active=True,
        is_frozen=False,
    )
    db.add(sched)
    db.commit()
    db.refresh(sched)
    return sched


@router.post("/{schedule_id}/freeze", response_model=ScheduleResponse)
def freeze_allowance(
    schedule_id: int,
    payload: FreezeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Freezes allowance payouts due to suspicious activity, disputed charge, or disciplinary hold."""
    sched = (
        db.query(AllowanceSchedule)
        .filter(AllowanceSchedule.id == schedule_id, AllowanceSchedule.family_id == current_user.family_id)
        .first()
    )
    if not sched:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Allowance schedule {schedule_id} not found",
        )
    require_family_parent(current_user, sched.family_id)
    sched.is_frozen = True
    sched.freeze_reason = payload.reason or "Parental hold"
    db.commit()
    db.refresh(sched)
    return sched


@router.post("/{schedule_id}/unfreeze", response_model=ScheduleResponse)
def unfreeze_allowance(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Unfreezes allowance payouts once dispute or review is resolved."""
    sched = (
        db.query(AllowanceSchedule)
        .filter(AllowanceSchedule.id == schedule_id, AllowanceSchedule.family_id == current_user.family_id)
        .first()
    )
    if not sched:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Allowance schedule {schedule_id} not found",
        )
    require_family_parent(current_user, sched.family_id)
    sched.is_frozen = False
    sched.freeze_reason = None
    db.commit()
    db.refresh(sched)
    return sched


@router.post("/{schedule_id}/disburse")
def disburse_allowance(
    schedule_id: int,
    db: Session = Depends(get_db),
    service: PayPalService = Depends(get_paypal_service),
    current_user: User = Depends(get_current_user),
):
    """Executes an allowance payout with idempotency key."""
    sched = (
        db.query(AllowanceSchedule)
        .filter(AllowanceSchedule.id == schedule_id, AllowanceSchedule.family_id == current_user.family_id)
        .first()
    )
    if sched is None:
        raise HTTPException(status_code=404, detail=f"Allowance schedule {schedule_id} not found")
    require_family_parent(current_user, sched.family_id)
    return disburse_allowance_schedule(schedule_id=schedule_id, db=db, service=service)
