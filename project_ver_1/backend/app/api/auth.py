import json
import logging
import urllib.parse
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
import httpx

from app.database import get_db
from app.models.user import User
from app.models.account import Account, AccountType
from app.services.paypal_service import PayPalService
from app.security.crypto import encrypt_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication & PayPal OAuth"])


def get_paypal_service() -> PayPalService:
    return PayPalService()


class CallbackPayload(BaseModel):
    code: str
    state: Optional[str] = None
    user_id: Optional[int] = None


@router.get("/login")
def paypal_login(service: PayPalService = Depends(get_paypal_service)):
    """Legacy helper returning PayPal authorization URL."""
    return {"auth_url": service.get_authorization_url()}


@router.get("/paypal/authorize")
@router.get("/authorize")
def paypal_authorize(
    redirect_uri: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    scope: Optional[str] = Query(None),
    service: PayPalService = Depends(get_paypal_service),
):
    """
    Generates PayPal OAuth 2.0 authorization URL for connecting a PayPal account.
    """
    auth_url = service.get_authorization_url(
        redirect_uri=redirect_uri,
        state=state,
        scope=scope,
    )
    return {"auth_url": auth_url}


async def _handle_callback_logic(
    code: str,
    state: Optional[str],
    user_id: Optional[int],
    db: Session,
    service: PayPalService,
):
    try:
        tokens = await service.exchange_oauth_code(code=code)
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"PayPal token exchange failed: {e.response.text}",
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error exchanging PayPal code: {str(e)}",
        ) from e

    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")
    token_to_encrypt = refresh_token or access_token
    encrypted_token = encrypt_token(token_to_encrypt) if token_to_encrypt else None

    # Retrieve PayPal account / payer ID
    paypal_account_id = tokens.get("payer_id") or tokens.get("user_id")
    if not paypal_account_id and access_token:
        try:
            user_info = await service.get_user_info(access_token)
            paypal_account_id = user_info.get("user_id") or user_info.get("payer_id")
        except Exception:
            pass

    # Extract target user id from user_id parameter or state
    target_user_id = user_id
    if target_user_id is None and state:
        try:
            target_user_id = int(state)
        except ValueError:
            try:
                state_data = json.loads(state)
                if isinstance(state_data, dict) and "user_id" in state_data:
                    target_user_id = int(state_data["user_id"])
            except Exception:
                if "user_id=" in state:
                    parsed = urllib.parse.parse_qs(state)
                    if "user_id" in parsed:
                        target_user_id = int(parsed["user_id"][0])

    account = None
    if target_user_id is not None:
        user = db.query(User).filter(User.id == target_user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {target_user_id} not found",
            )

        # Look for existing PayPal linked account or parent wallet
        account = (
            db.query(Account)
            .filter(
                Account.user_id == user.id,
                Account.account_type.in_(
                    [AccountType.PAYPAL_LINKED.value, AccountType.PARENT_WALLET.value]
                ),
            )
            .first()
        )

        if account:
            account.paypal_encrypted_token = encrypted_token
            if paypal_account_id:
                account.paypal_account_id = paypal_account_id
            account.is_active = True
        else:
            account = Account(
                user_id=user.id,
                family_id=user.family_id,
                account_type=AccountType.PAYPAL_LINKED.value,
                paypal_account_id=paypal_account_id,
                paypal_encrypted_token=encrypted_token,
                balance=0.0,
                currency="USD",
                is_active=True,
            )
            db.add(account)

        db.commit()
        db.refresh(account)

        # Trigger historical transaction ingestion via Celery (or synchronous fallback)
        try:
            from app.workers.celery_worker import sync_historical_transactions_task
            from app.api.webhooks import get_redis_client

            is_broker_ready = bool(get_redis_client() is not None)
            if is_broker_ready:
                try:
                    sync_historical_transactions_task.delay(account.id)
                except Exception as celery_err:
                    logger.info(f"Celery delay failed ({celery_err}), falling back to sync: {celery_err}")
                    try:
                        sync_historical_transactions_task(account.id, db=db)
                    except Exception as sync_err:
                        logger.warning(f"Historical sync fallback failed: {sync_err}")
            else:
                try:
                    sync_historical_transactions_task(account.id, db=db)
                except Exception as sync_err:
                    logger.warning(f"Synchronous historical sync fallback failed: {sync_err}")
        except Exception as e:
            logger.warning(f"Could not trigger historical sync for account {account.id}: {e}")

    return {
        "status": "success",
        "message": "PayPal account linked successfully"
        if account
        else "Tokens exchanged successfully",
        "user_id": target_user_id,
        "account_id": account.id if account else None,
        "paypal_account_id": paypal_account_id,
        "encrypted_token_stored": bool(account and account.paypal_encrypted_token),
    }


@router.get("/paypal/callback")
@router.get("/callback")
async def paypal_callback_get(
    code: str = Query(..., description="Authorization code from PayPal OAuth redirect"),
    state: Optional[str] = Query(None, description="Optional OAuth state"),
    user_id: Optional[int] = Query(None, description="Optional User ID to link"),
    db: Session = Depends(get_db),
    service: PayPalService = Depends(get_paypal_service),
):
    """Handles GET callback from PayPal OAuth redirect."""
    return await _handle_callback_logic(
        code=code,
        state=state,
        user_id=user_id,
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
        user_id=payload.user_id,
        db=db,
        service=service,
    )
