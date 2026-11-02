import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import APP_JWT_ISSUER, APP_JWT_SECRET
from app.database import get_db
from app.models.user import User

_bearer = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
_password_hasher = PasswordHasher()


def _jwt_secret_is_configured() -> bool:
    return bool(
        APP_JWT_SECRET
        and len(APP_JWT_SECRET.encode("utf-8")) >= 32
        and not APP_JWT_SECRET.startswith(("replace-with-", "default-dev", "your_", "change-me"))
    )


def _scrypt_kdf(password: bytes, salt: bytes, n: int = 2**14, r: int = 8, p: int = 1, length: int = 64) -> bytes:
    if hasattr(hashlib, "scrypt"):
        return hashlib.scrypt(password, salt=salt, n=n, r=r, p=p, dklen=length)
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    kdf = Scrypt(salt=salt, length=length, n=n, r=r, p=p)
    return kdf.derive(password)


def hash_password(password: str) -> str:
    if len(password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters.")
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    if not password or not password_hash:
        return False
    if password_hash.startswith("$argon2"):
        try:
            return _password_hasher.verify(password_hash, password)
        except (VerifyMismatchError, InvalidHashError, VerificationError):
            return False
    try:
        if not password_hash or "$" not in password_hash:
            return False
        algorithm, n, r, p, salt_hex, digest_hex = password_hash.split("$")
        if algorithm != "scrypt":
            return False
        expected = bytes.fromhex(digest_hex)
        actual = _scrypt_kdf(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=int(n), r=int(r), p=int(p), length=len(expected),
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def create_access_token(user: User, expires_minutes: int = 30) -> str:
    if not _jwt_secret_is_configured():
        raise HTTPException(status_code=503, detail="Configure APP_JWT_SECRET with at least 32 bytes.")
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user.id),
            "family_id": user.family_id,
            "role": user.role,
            "ver": user.auth_token_version or 0,
            "iss": APP_JWT_ISSUER,
            "iat": now,
            "exp": now + timedelta(minutes=expires_minutes),
        },
        APP_JWT_SECRET,
        algorithm="HS256",
    )


def get_current_user(
    token: Annotated[str, Depends(_bearer)],
    db: Session = Depends(get_db),
) -> User:
    if not _jwt_secret_is_configured():
        raise HTTPException(status_code=503, detail="Authentication is not configured.")
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        claims = jwt.decode(token, APP_JWT_SECRET, algorithms=["HS256"], issuer=APP_JWT_ISSUER)
        user_id = int(claims["sub"])
        token_version = int(claims["ver"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise unauthorized from exc
    user = db.query(User).filter(User.id == user_id).first()
    if user is None or token_version != (user.auth_token_version or 0):
        raise unauthorized
    return user


def require_parent(user: Annotated[User, Depends(get_current_user)]) -> User:
    role = str(user.role).upper()
    if role not in ["PARENT", "CO_PARENT"]:
        raise HTTPException(status_code=403, detail="Parent role required.")
    return user


def require_family_member(user: User, family_id: int) -> User:
    if user.family_id is None or user.family_id != family_id:
        raise HTTPException(status_code=404, detail="Family not found.")
    return user


def require_family_parent(user: User, family_id: int) -> User:
    require_family_member(user, family_id)
    if str(user.role).upper() not in ("PARENT", "CO_PARENT"):
        raise HTTPException(status_code=403, detail="Parent role required.")
    return user
