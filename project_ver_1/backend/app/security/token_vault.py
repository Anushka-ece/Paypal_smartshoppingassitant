from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException

from app.config import TOKEN_ENCRYPTION_KEY


def _fernet() -> Fernet:
    if not TOKEN_ENCRYPTION_KEY:
        raise HTTPException(status_code=503, detail="TOKEN_ENCRYPTION_KEY is required to link PayPal accounts.")
    try:
        return Fernet(TOKEN_ENCRYPTION_KEY.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise HTTPException(status_code=500, detail="TOKEN_ENCRYPTION_KEY must be a valid Fernet key.") from exc


def encrypt_token(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_token(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeEncodeError) as exc:
        raise HTTPException(status_code=500, detail="Stored PayPal token could not be decrypted.") from exc
