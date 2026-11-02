import pytest
from fastapi import HTTPException

import app.config as app_config
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


def test_production_config_rejects_default_jwt_secret(monkeypatch):
    monkeypatch.setattr(app_config, "APP_ENV", "production")
    monkeypatch.setattr(
        app_config,
        "APP_JWT_SECRET",
        "default-dev-jwt-secret-key-change-in-production-32b",
    )

    with pytest.raises(RuntimeError, match="APP_JWT_SECRET"):
        app_config.validate_production_config()


def test_production_config_rejects_placeholder_paypal_credentials(monkeypatch):
    monkeypatch.setattr(app_config, "APP_ENV", "production")
    monkeypatch.setattr(app_config, "APP_JWT_SECRET", "secure-jwt-secret-" + "x" * 40)
    monkeypatch.setattr(app_config, "TOKEN_ENCRYPTION_KEY", "secure-encryption-key-" + "x" * 20)
    monkeypatch.setattr(app_config, "PAYPAL_WEBHOOK_ID", "configured-webhook-id")
    monkeypatch.setattr(app_config, "PAYPAL_CLIENT_ID", "your_paypal_client_id_here")
    monkeypatch.setattr(app_config, "PAYPAL_CLIENT_SECRET", "configured-secret")
    monkeypatch.setattr(app_config, "GEMINI_API_KEY", "")

    with pytest.raises(RuntimeError, match="PayPal app credentials"):
        app_config.validate_production_config()


def test_production_config_accepts_configured_sandbox_credentials(monkeypatch):
    monkeypatch.setattr(app_config, "APP_ENV", "production")
    monkeypatch.setattr(app_config, "APP_JWT_SECRET", "secure-jwt-secret-" + "x" * 40)
    monkeypatch.setattr(app_config, "TOKEN_ENCRYPTION_KEY", "secure-encryption-key-" + "x" * 20)
    monkeypatch.setattr(app_config, "PAYPAL_WEBHOOK_ID", "configured-webhook-id")
    monkeypatch.setattr(app_config, "PAYPAL_CLIENT_ID", "sandbox-client-id")
    monkeypatch.setattr(app_config, "PAYPAL_CLIENT_SECRET", "sandbox-client-secret")
    monkeypatch.setattr(app_config, "PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com")
    monkeypatch.setattr(app_config, "GEMINI_API_KEY", "")

    app_config.validate_production_config()


def test_production_config_rejects_live_paypal_endpoint(monkeypatch):
    monkeypatch.setattr(app_config, "APP_ENV", "production")
    monkeypatch.setattr(app_config, "APP_JWT_SECRET", "secure-jwt-secret-" + "x" * 40)
    monkeypatch.setattr(app_config, "TOKEN_ENCRYPTION_KEY", "secure-encryption-key-" + "x" * 20)
    monkeypatch.setattr(app_config, "PAYPAL_WEBHOOK_ID", "configured-webhook-id")
    monkeypatch.setattr(app_config, "PAYPAL_CLIENT_ID", "sandbox-client-id")
    monkeypatch.setattr(app_config, "PAYPAL_CLIENT_SECRET", "sandbox-client-secret")
    monkeypatch.setattr(app_config, "PAYPAL_BASE_URL", "https://api-m.paypal.com")
    monkeypatch.setattr(app_config, "GEMINI_API_KEY", "")

    with pytest.raises(RuntimeError, match="restricted to the sandbox API"):
        app_config.validate_production_config()
