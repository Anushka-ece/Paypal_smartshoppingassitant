import pytest
from fastapi import HTTPException

from app.security.token_vault import decrypt_token, encrypt_token


def test_encrypt_decrypt_roundtrip(monkeypatch):
    from cryptography.fernet import Fernet
    import app.security.token_vault as token_vault

    monkeypatch.setattr(token_vault, "TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    value = "paypal-access-token-do-not-log"
    encrypted = encrypt_token(value)
    assert encrypted != value
    assert decrypt_token(encrypted) == value


def test_missing_token_key_fails_closed(monkeypatch):
    import app.security.token_vault as token_vault

    monkeypatch.setattr(token_vault, "TOKEN_ENCRYPTION_KEY", "")
    with pytest.raises(HTTPException) as exc:
        encrypt_token("secret")
    assert exc.value.status_code == 503
