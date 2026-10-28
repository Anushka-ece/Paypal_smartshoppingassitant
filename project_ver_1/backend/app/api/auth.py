import secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode

import requests
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.config import APP_ENV, PAYPAL_AUTHORIZE_URL, PAYPAL_BASE_URL, PAYPAL_CLIENT_ID, PAYPAL_REDIRECT_URI
from app.database import get_db
from app.models.models import Account, Family, User
from app.security.auth import create_access_token, hash_password, verify_password
from app.security.token_vault import encrypt_token
from app.services.paypal_service import exchange_authorization_code

router = APIRouter(prefix="/auth", tags=["Authentication & PayPal OAuth"])
OAUTH_STATE_COOKIE = "paypal_oauth_state"


class ParentRegistration(BaseModel):
    family_name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/register", status_code=201)
def register_parent(payload: ParentRegistration, db: Session = Depends(get_db)):
    """Create an initial family and parent account; email/VPC verification remains pending."""
    normalized_email = str(payload.email).lower()
    if db.query(User).filter(User.email == normalized_email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    family = Family(name=payload.family_name.strip())
    db.add(family)
    db.flush()
    parent = User(
        family_id=family.id,
        email=normalized_email,
        hashed_password=hash_password(payload.password),
        role="parent",
        is_verified=False,
    )
    db.add(parent)
    db.commit()
    db.refresh(parent)
    return {"status": "pending_verification", "user_id": parent.id, "family_id": family.id}


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == str(payload.email).lower()).first()
    now = datetime.utcnow()
    if user is None:
        # Keep response behavior uniform for unknown addresses; do not reveal account existence.
        verify_password(payload.password, "scrypt$16384$8$1$00112233445566778899aabbccddeeff$" + "00" * 64)
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if user.locked_until and user.locked_until > now:
        raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")
    if not verify_password(payload.password, user.hashed_password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= 5:
            user.failed_login_attempts = 0
            user.locked_until = now + timedelta(minutes=15)
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()
    return {"access_token": create_access_token(user), "token_type": "bearer", "role": user.role}


@router.get("/login")
def paypal_login(response: Response):
    """Return the PayPal consent URL and set short-lived CSRF state in an HttpOnly cookie."""
    state = secrets.token_urlsafe(32)
    response.set_cookie(
        OAUTH_STATE_COOKIE,
        state,
        max_age=600,
        httponly=True,
        secure=APP_ENV == "production",
        samesite="lax",
    )
    query = urlencode({
        "client_id": PAYPAL_CLIENT_ID,
        "response_type": "code",
        "scope": "openid profile email",
        "redirect_uri": PAYPAL_REDIRECT_URI,
        "state": state,
    })
    return {"auth_url": f"{PAYPAL_AUTHORIZE_URL}?{query}"}


@router.get("/callback")
def paypal_oauth_callback(
    request: Request,
    response: Response,
    code: str,
    state: str,
    db: Session = Depends(get_db),
):
    """Complete PayPal consent, verify payer identity, and store encrypted tokens."""
    expected_state = request.cookies.get(OAUTH_STATE_COOKIE)
    response.delete_cookie(OAUTH_STATE_COOKIE, httponly=True, samesite="lax", secure=APP_ENV == "production")
    if not expected_state or not secrets.compare_digest(expected_state, state):
        raise HTTPException(status_code=400, detail="Invalid or expired PayPal OAuth state.")

    tokens = exchange_authorization_code(code, PAYPAL_REDIRECT_URI)
    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")
    if not access_token:
        raise HTTPException(status_code=502, detail="PayPal did not return an OAuth access token.")

    try:
        identity_response = requests.get(
            f"{PAYPAL_BASE_URL}/v1/identity/openidconnect/userinfo",
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
            timeout=10,
        )
        identity_response.raise_for_status()
        identity = identity_response.json()
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail="Unable to verify the PayPal account identity.") from exc

    payer_id = identity.get("user_id") or identity.get("sub")
    verified_email = identity.get("email", "").lower() if identity.get("email_verified") else None
    if not payer_id or not verified_email:
        raise HTTPException(status_code=403, detail="PayPal identity must provide a verified primary email and payer id.")

    parent = db.query(User).filter(User.email == verified_email, User.role == "parent", User.is_verified.is_(True)).first()
    if parent is None:
        raise HTTPException(status_code=403, detail="PayPal verified email must match an existing verified parent account.")

    account = db.query(Account).filter(Account.user_id == parent.id, Account.paypal_payer_id == payer_id).first()
    if account is None:
        account = Account(user_id=parent.id, paypal_payer_id=payer_id)
        db.add(account)
    account.encrypted_access_token = encrypt_token(access_token)
    account.encrypted_refresh_token = encrypt_token(refresh_token) if refresh_token else None
    expires_in = int(tokens.get("expires_in", 0))
    account.token_expires_at = datetime.utcnow() + timedelta(seconds=max(0, expires_in))
    db.commit()
    return {"status": "linked", "payer_id": payer_id}
