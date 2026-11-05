import hashlib
import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
import httpx

from app.database import get_db
from app.models.user import User, UserRole
from app.models.family import Family
from app.models.account import Account, AccountType
from app.models.paypal_oauth_state import PayPalOAuthState
from app.config import PAYPAL_REDIRECT_URI
from app.services.paypal_service import PayPalService
from app.security.crypto import encrypt_token
from app.security.auth import create_access_token, get_current_user, hash_password, require_parent, verify_password

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication & PayPal OAuth"])


def get_paypal_service() -> PayPalService:
    return PayPalService()


class ParentRegistration(BaseModel):
    family_name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


@router.post("/register", status_code=201)
def register_parent(payload: ParentRegistration, db: Session = Depends(get_db)):
    """Create an initial family and parent account."""
    normalized_email = str(payload.email).lower()
    if db.query(User).filter(User.email == normalized_email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    family = Family(name=payload.family_name.strip())
    db.add(family)
    db.flush()
    parent = User(
        family_id=family.id,
        email=normalized_email,
        name=normalized_email.split("@")[0],
        hashed_password=hash_password(payload.password),
        role=UserRole.PARENT.value,
        is_verified=False,
    )
    db.add(parent)
    db.flush()
    family.created_by_user_id = parent.id
    db.add(
        Account(
            user_id=parent.id,
            family_id=family.id,
            account_type=AccountType.PARENT_WALLET.value,
            balance=0.0,
            currency="USD",
        )
    )
    db.commit()
    db.refresh(parent)
    return {"status": "pending_verification", "user_id": parent.id, "family_id": family.id}


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    normalized_email = str(payload.email).lower()
    user = db.query(User).filter(User.email == normalized_email).first()
    now = datetime.utcnow()
    if user is None:
        verify_password(payload.password, "scrypt$16384$8$1$00112233445566778899aabbccddeeff$" + "00" * 64)
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if user.locked_until and user.locked_until > now:
        raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")
    if not verify_password(payload.password, user.hashed_password):
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= 5:
            user.failed_login_attempts = 0
            user.locked_until = now + timedelta(minutes=15)
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    user.failed_login_attempts = 0
    user.locked_until = None
    if not user.hashed_password.startswith("$argon2"):
        user.hashed_password = hash_password(payload.password)
    db.commit()
    return {
        "access_token": create_access_token(user),
        "token_type": "bearer",
        "role": user.role,
        "user_id": user.id,
        "family_id": user.family_id,
    }


class CallbackPayload(BaseModel):
    code: str = Field(min_length=1, max_length=2048)
    state: Optional[str] = Field(default=None, max_length=256)


@router.post("/logout")
def logout(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.auth_token_version = (user.auth_token_version or 0) + 1
    db.commit()
    return {"status": "logged_out"}


def _create_paypal_authorization(user: User, db: Session, service: PayPalService):
    state = secrets.token_urlsafe(32)
    try:
        auth_url = service.get_authorization_url(redirect_uri=PAYPAL_REDIRECT_URI, state=state)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="PayPal Sandbox credentials are not configured.") from exc
    state_record = PayPalOAuthState(
        state_hash=hashlib.sha256(state.encode("utf-8")).hexdigest(),
        user_id=user.id,
        expires_at=datetime.utcnow() + timedelta(minutes=10),
    )
    db.add(state_record)
    db.commit()
    return {"auth_url": auth_url}


@router.get("/login")
def paypal_login(
    user: User = Depends(require_parent),
    db: Session = Depends(get_db),
    service: PayPalService = Depends(get_paypal_service),
):
    """Compatibility endpoint that starts an authenticated PayPal OAuth flow."""
    return _create_paypal_authorization(user, db, service)


@router.get("/paypal/authorize")
@router.get("/authorize")
def paypal_authorize(
    user: User = Depends(require_parent),
    db: Session = Depends(get_db),
    service: PayPalService = Depends(get_paypal_service),
):
    """Generate an authorization URL with a one-time state bound to the user."""
    return _create_paypal_authorization(user, db, service)


async def _handle_callback_logic(
    code: str,
    state: Optional[str],
    db: Session,
    service: PayPalService,
):
    if not state:
        raise HTTPException(status_code=400, detail="Invalid or expired PayPal OAuth state.")
    state_hash = hashlib.sha256(state.encode("utf-8")).hexdigest()
    now = datetime.utcnow()
    db.query(PayPalOAuthState).filter(PayPalOAuthState.expires_at <= now).delete(
        synchronize_session=False
    )
    consumed = db.execute(
        update(PayPalOAuthState)
        .where(
            PayPalOAuthState.state_hash == state_hash,
            PayPalOAuthState.consumed_at.is_(None),
            PayPalOAuthState.expires_at > now,
        )
        .values(consumed_at=now)
    )
    if consumed.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid or expired PayPal OAuth state.")
    state_record = db.query(PayPalOAuthState).filter(PayPalOAuthState.state_hash == state_hash).first()
    if state_record is None:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid or expired PayPal OAuth state.")
    user = db.query(User).filter(User.id == state_record.user_id).first()
    if user is None or str(user.role).upper() not in ("PARENT", "CO_PARENT"):
        db.rollback()
        raise HTTPException(status_code=401, detail="PayPal OAuth user is no longer authorized.")
    db.commit()

    try:
        tokens = await service.exchange_oauth_code(code=code, redirect_uri=PAYPAL_REDIRECT_URI)
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="PayPal authorization could not be completed.",
        ) from exc

    access_token = tokens.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise HTTPException(status_code=502, detail="PayPal did not return an access token.")
    try:
        expires_in = int(tokens["expires_in"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=502,
            detail="PayPal returned an invalid access-token lifetime.",
        ) from exc
    if expires_in <= 0:
        raise HTTPException(status_code=502, detail="PayPal returned an invalid access-token lifetime.")
    refresh_token = tokens.get("refresh_token")
    if refresh_token is not None and (not isinstance(refresh_token, str) or not refresh_token):
        raise HTTPException(status_code=502, detail="PayPal returned an invalid refresh token.")

    paypal_account_id = tokens.get("payer_id") or tokens.get("user_id")
    if not isinstance(paypal_account_id, str) or not paypal_account_id:
        try:
            user_info = await service.get_user_info(access_token)
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            raise HTTPException(status_code=502, detail="PayPal account identity could not be verified.") from exc
        paypal_account_id = user_info.get("user_id") or user_info.get("payer_id")
    if not isinstance(paypal_account_id, str) or not paypal_account_id:
        raise HTTPException(status_code=502, detail="PayPal did not provide a verifiable account identity.")

    existing_owner = (
        db.query(Account)
        .filter(Account.paypal_account_id == paypal_account_id)
        .first()
    )
    if existing_owner and existing_owner.user_id != user.id:
        raise HTTPException(status_code=409, detail="This PayPal account is already linked to another user.")

    account = existing_owner or (
        db.query(Account)
        .filter(
            Account.user_id == user.id,
            Account.account_type == AccountType.PAYPAL_LINKED.value,
        )
        .first()
    )
    if account and account.paypal_account_id not in (None, paypal_account_id):
        raise HTTPException(status_code=409, detail="A different PayPal account is already linked to this user.")
    if account is None:
        account = Account(
            user_id=user.id,
            family_id=user.family_id,
            account_type=AccountType.PAYPAL_LINKED.value,
            balance=0.0,
            currency="USD",
            is_active=True,
        )
        db.add(account)

    try:
        encrypted_access_token = encrypt_token(access_token)
        encrypted_refresh_token = encrypt_token(refresh_token) if refresh_token else None
    except ValueError as exc:
        raise HTTPException(
            status_code=503,
            detail="Configure a strong TOKEN_ENCRYPTION_KEY before linking PayPal.",
        ) from exc

    account.paypal_account_id = paypal_account_id
    account.paypal_encrypted_token = encrypted_access_token
    account.paypal_encrypted_refresh_token = encrypted_refresh_token
    account.paypal_access_token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
    account.is_active = True
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="This PayPal account is already linked.") from exc
    db.refresh(account)

    try:
        from app.workers.celery_worker import sync_historical_transactions_task
        from app.api.webhooks import get_redis_client

        if get_redis_client() is not None:
            sync_historical_transactions_task.delay(account.id)
        else:
            logger.info("Historical PayPal sync deferred because the task broker is unavailable.")
    except Exception as exc:
        logger.warning("Could not enqueue historical PayPal sync for account %s: %s", account.id, exc)

    return {
        "status": "success",
        "message": "PayPal account linked successfully",
        "user_id": user.id,
        "account_id": account.id,
        "paypal_account_id": paypal_account_id,
        "encrypted_token_stored": bool(account.paypal_encrypted_token),
        "refresh_token_available": bool(account.paypal_encrypted_refresh_token),
    }


@router.get("/paypal/callback")
@router.get("/callback")
async def paypal_callback_get(
    code: str = Query(..., min_length=1, max_length=2048, description="Authorization code from PayPal OAuth redirect"),
    state: Optional[str] = Query(None, max_length=256, description="One-time server-issued OAuth state"),
    db: Session = Depends(get_db),
    service: PayPalService = Depends(get_paypal_service),
):
    """Handles GET callback from PayPal OAuth redirect."""
    return await _handle_callback_logic(
        code=code,
        state=state,
        db=db,
        service=service,
    )


@router.post("/paypal/callback")
@router.post("/callback")
async def paypal_callback_post(
    payload: CallbackPayload = Body(...),
    db: Session = Depends(get_db),
    service: PayPalService = Depends(get_paypal_service),
):
    """Handles POST callback with JSON payload."""
    return await _handle_callback_logic(
        code=payload.code,
        state=payload.state,
        db=db,
        service=service,
    )
