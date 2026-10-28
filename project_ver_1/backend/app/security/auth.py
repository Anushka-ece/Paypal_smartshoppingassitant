import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import APP_JWT_ISSUER, APP_JWT_SECRET
from app.database import get_db
from app.models.models import User

_bearer = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise HTTPException(status_code=422, detail="Password must be at least 12 characters.")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=64)
    return f"scrypt$16384$8$1${salt.hex()}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, n, r, p, salt_hex, digest_hex = password_hash.split("$")
        if algorithm != "scrypt":
            return False
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=int(n), r=int(r), p=int(p), dklen=len(expected),
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def create_access_token(user: User, expires_minutes: int = 30) -> str:
    if not APP_JWT_SECRET or APP_JWT_SECRET.startswith("replace-with-") or len(APP_JWT_SECRET.encode("utf-8")) < 32:
        raise HTTPException(status_code=503, detail="Configure APP_JWT_SECRET with at least 32 characters.")
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": str(user.id), "family_id": user.family_id, "role": user.role,
         "iss": APP_JWT_ISSUER, "iat": now, "exp": now + timedelta(minutes=expires_minutes)},
        APP_JWT_SECRET,
        algorithm="HS256",
    )


def get_current_user(
    token: Annotated[str, Depends(_bearer)],
    db: Session = Depends(get_db),
) -> User:
    if not APP_JWT_SECRET or APP_JWT_SECRET.startswith("replace-with-") or len(APP_JWT_SECRET.encode("utf-8")) < 32:
        raise HTTPException(status_code=503, detail="Authentication is not configured.")
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        claims = jwt.decode(token, APP_JWT_SECRET, algorithms=["HS256"], issuer=APP_JWT_ISSUER)
        user_id = int(claims["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise unauthorized from exc
    user = db.query(User).filter(User.id == user_id, User.family_id == claims.get("family_id")).first()
    if user is None:
        raise unauthorized
    return user


def require_parent(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != "parent":
        raise HTTPException(status_code=403, detail="Parent role required.")
    return user
