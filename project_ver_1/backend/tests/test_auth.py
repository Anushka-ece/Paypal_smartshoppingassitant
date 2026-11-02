import hashlib
from datetime import datetime, timedelta
import pytest
from unittest.mock import patch, AsyncMock
import httpx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models.user import User, UserRole
from app.models.family import Family
from app.models.account import Account, AccountType
from app.models.paypal_oauth_state import PayPalOAuthState
from app.api import auth as auth_api
from app.security.crypto import encrypt_token, decrypt_token
from app.security.auth import get_current_user
from app.services.paypal_service import PayPalService

client = TestClient(app)


def issue_oauth_state(db_session, user_id):
    state = "test-state-" + str(user_id) + "-" + str(db_session.query(PayPalOAuthState).count())
    db_session.add(
        PayPalOAuthState(
            state_hash=hashlib.sha256(state.encode()).hexdigest(),
            user_id=user_id,
            expires_at=datetime.utcnow() + timedelta(minutes=5),
        )
    )
    db_session.commit()
    return state


# Setup an in-memory SQLite database for isolated database integration tests
@pytest.fixture
def db_session():
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=test_engine
    )
    # Only create the tables required for auth & user-account testing
    Base.metadata.create_all(
        bind=test_engine,
        tables=[
            Family.__table__,
            User.__table__,
            Account.__table__,
            PayPalOAuthState.__table__,
        ],
    )

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        test_engine.dispose()


# ----------------------------------------------------------------------
# 1. AES-256 Token Encryption & Decryption Tests
# ----------------------------------------------------------------------

def test_token_encryption_roundtrip():
    token = "secret-paypal-oauth-refresh-token"
    encrypted = encrypt_token(token)
    assert encrypted != token
    assert decrypt_token(encrypted) == token


def test_token_encryption_nonce_randomness():
    token = "repeat-secret-token"
    enc1 = encrypt_token(token)
    enc2 = encrypt_token(token)
    # Different random nonces must produce different ciphertexts
    assert enc1 != enc2
    assert decrypt_token(enc1) == token
    assert decrypt_token(enc2) == token


def test_token_decryption_tampered_or_invalid():
    token = "secret-token"
    encrypted = encrypt_token(token)

    # Tamper with ciphertext
    tampered = encrypted[:-4] + "AAAA"
    with pytest.raises(ValueError, match="Decryption failed"):
        decrypt_token(tampered)

    # Completely invalid base64 or too short
    with pytest.raises(ValueError):
        decrypt_token("not-valid-base64!!!")

    with pytest.raises(ValueError, match="too short"):
        decrypt_token("AQID")  # only 3 bytes decoded, less than 12-byte nonce


def test_token_encryption_with_custom_key():
    token = "custom-key-token"
    custom_key = "my-very-secret-custom-key-12345"
    wrong_key = "wrong-secret-custom-key-67890"

    encrypted = encrypt_token(token, key=custom_key)
    assert decrypt_token(encrypted, key=custom_key) == token

    # Decrypting with wrong key must fail authentication
    with pytest.raises(ValueError, match="Decryption failed"):
        decrypt_token(encrypted, key=wrong_key)


# ----------------------------------------------------------------------
# 2. PayPalService Unit Tests
# ----------------------------------------------------------------------

def test_paypal_service_authorization_url():
    service = PayPalService(
        client_id="test_client_id_123",
        client_secret="test_secret_456",
        base_url="https://api-m.sandbox.paypal.com",
    )
    url = service.get_authorization_url(
        redirect_uri="http://localhost:8000/api/auth/paypal/callback",
        state="user_state_789",
    )
    assert "https://www.sandbox.paypal.com/signin/authorize?" in url
    assert "client_id=test_client_id_123" in url
    assert "response_type=code" in url
    assert "state=user_state_789" in url
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fapi%2Fauth%2Fpaypal%2Fcallback" in url


@pytest.mark.anyio
async def test_paypal_service_exchange_oauth_code():
    service = PayPalService(
        client_id="client123",
        client_secret="secret456",
        base_url="https://api-m.sandbox.paypal.com",
    )

    mock_response = {
        "access_token": "mock_access_token_abc",
        "refresh_token": "mock_refresh_token_xyz",
        "token_type": "Bearer",
        "expires_in": 32400,
        "scope": "openid email",
    }

    mock_resp = httpx.Response(
        status_code=200,
        json=mock_response,
        request=httpx.Request("POST", "https://api-m.sandbox.paypal.com/v1/oauth2/token"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        result = await service.exchange_oauth_code(code="test_auth_code_999")
        assert result == mock_response

        # Check call arguments
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "https://api-m.sandbox.paypal.com/v1/oauth2/token"
        assert kwargs["auth"] == ("client123", "secret456")
        assert kwargs["data"]["grant_type"] == "authorization_code"
        assert kwargs["data"]["code"] == "test_auth_code_999"


@pytest.mark.anyio
async def test_paypal_service_refresh_token_with_encrypted_and_raw():
    service = PayPalService(
        client_id="client123",
        client_secret="secret456",
        base_url="https://api-m.sandbox.paypal.com",
    )

    raw_refresh = "raw_refresh_token_value_555"
    encrypted_refresh = encrypt_token(raw_refresh)

    mock_refresh_response = {
        "access_token": "new_access_token_777",
        "token_type": "Bearer",
        "expires_in": 32400,
    }

    mock_resp = httpx.Response(
        status_code=200,
        json=mock_refresh_response,
        request=httpx.Request("POST", "https://api-m.sandbox.paypal.com/v1/oauth2/token"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        # Call with encrypted token
        res1 = await service.refresh_access_token(encrypted_refresh)
        assert res1["access_token"] == "new_access_token_777"
        args1, kwargs1 = mock_post.call_args
        assert kwargs1["data"]["grant_type"] == "refresh_token"
        assert kwargs1["data"]["refresh_token"] == raw_refresh

        # Call with raw token via alias refresh_token
        res2 = await service.refresh_token(raw_refresh)
        assert res2["access_token"] == "new_access_token_777"


def test_paypal_service_event_supported():
    service = PayPalService()
    assert service.is_event_supported("PAYMENT.CAPTURE.COMPLETED") is True
    assert service.is_event_supported("PAYMENT.CAPTURE.REFUNDED") is True
    assert service.is_event_supported("PAYMENT.SALE.REFUNDED") is True
    assert service.is_event_supported("CUSTOMER.DISPUTE.RESOLVED") is True
    assert service.is_event_supported("UNKNOWN.EVENT") is False


# ----------------------------------------------------------------------
# 3. Auth Endpoints Integration Tests (/authorize and /callback)
# ----------------------------------------------------------------------

def test_api_authorize_endpoint(db_session):
    family = Family(name="OAuth Family")
    db_session.add(family)
    db_session.commit()
    user = User(email="authorize@example.com", role=UserRole.PARENT.value, family_id=family.id)
    db_session.add(user)
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[auth_api.get_paypal_service] = lambda: PayPalService(
        client_id="sandbox-test-client",
        client_secret="sandbox-test-secret",
        base_url="https://api-m.sandbox.paypal.com",
    )
    try:
        response = client.get("/api/auth/paypal/authorize?state=attacker_state")
        assert response.status_code == 200
        data = response.json()
        assert "auth_url" in data
        assert "https://www.sandbox.paypal.com/signin/authorize?" in data["auth_url"]
        assert "state=attacker_state" not in data["auth_url"]
        assert "state=" in data["auth_url"]
        assert db_session.query(PayPalOAuthState).filter_by(user_id=user.id).count() == 1

        # Direct /auth/authorize alias also creates state bound to the session user.
        res_direct = client.get("/auth/authorize")
        assert res_direct.status_code == 200
        assert db_session.query(PayPalOAuthState).filter_by(user_id=user.id).count() == 2
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(auth_api.get_paypal_service, None)


def test_api_callback_get_links_user_and_encrypts_token(db_session):
    # Setup test user in database
    test_user = User(
        email="parent_oauth@example.com",
        name="OAuth Parent",
        role=UserRole.PARENT.value,
    )
    db_session.add(test_user)
    db_session.commit()
    db_session.refresh(test_user)

    mock_oauth_result = {
        "access_token": "access_token_mock_111",
        "refresh_token": "secret_refresh_token_from_paypal_222",
        "payer_id": "PAYPAL_ACC_9999",
        "token_type": "Bearer",
        "expires_in": 32400,
    }

    # Override get_db to use test SQLite session
    app.dependency_overrides[get_db] = lambda: db_session
    state = issue_oauth_state(db_session, test_user.id)

    try:
        with patch.object(
            PayPalService, "exchange_oauth_code", new_callable=AsyncMock
        ) as mock_exchange:
            mock_exchange.return_value = mock_oauth_result

            response = client.get(
                f"/api/auth/paypal/callback?code=mock_auth_code_123&state={state}"
            )
            assert response.status_code == 200
            resp_data = response.json()
            assert resp_data["status"] == "success"
            assert resp_data["user_id"] == test_user.id
            assert resp_data["paypal_account_id"] == "PAYPAL_ACC_9999"
            assert resp_data["encrypted_token_stored"] is True

            # Verify token stored in DB is encrypted and can be decrypted
            account = (
                db_session.query(Account)
                .filter(Account.user_id == test_user.id)
                .first()
            )
            assert account is not None
            assert account.paypal_account_id == "PAYPAL_ACC_9999"
            assert account.paypal_encrypted_token is not None
            assert account.paypal_encrypted_token != "access_token_mock_111"
            assert account.paypal_encrypted_refresh_token != "secret_refresh_token_from_paypal_222"

            assert decrypt_token(account.paypal_encrypted_token) == "access_token_mock_111"
            assert decrypt_token(account.paypal_encrypted_refresh_token) == "secret_refresh_token_from_paypal_222"
            assert account.paypal_access_token_expires_at is not None
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_api_callback_rejects_untrusted_state(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with patch.object(
            PayPalService, "exchange_oauth_code", new_callable=AsyncMock
        ) as mock_exchange:
            res = client.get(
                "/api/auth/paypal/callback?code=code_state_1&state=%7B%22user_id%22%3A1%7D"
            )
            assert res.status_code == 400
            mock_exchange.assert_not_awaited()
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_api_callback_post_endpoint(db_session):
    test_user = User(
        email="post_user@example.com",
        name="Post User",
        role=UserRole.PARENT.value,
    )
    db_session.add(test_user)
    db_session.commit()
    db_session.refresh(test_user)

    mock_oauth_result = {
        "access_token": "access_token_post",
        "refresh_token": "refresh_token_post",
        "payer_id": "POST_PAYPAL_ID",
        "expires_in": 32400,
    }

    app.dependency_overrides[get_db] = lambda: db_session
    state = issue_oauth_state(db_session, test_user.id)
    try:
        with patch.object(
            PayPalService, "exchange_oauth_code", new_callable=AsyncMock
        ) as mock_exchange:
            mock_exchange.return_value = mock_oauth_result

            res = client.post(
                "/api/auth/paypal/callback",
                json={"code": "code_post_1", "state": state},
            )
            assert res.status_code == 200
            assert res.json()["status"] == "success"
            assert res.json()["user_id"] == test_user.id
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_api_callback_state_for_missing_user_is_rejected(db_session):
    state = issue_oauth_state(db_session, 999999)
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with patch.object(
            PayPalService, "exchange_oauth_code", new_callable=AsyncMock
        ) as mock_exchange:
            res = client.get(f"/api/auth/paypal/callback?code=test_code&state={state}")
            assert res.status_code == 401
            mock_exchange.assert_not_awaited()
    finally:
        app.dependency_overrides.pop(get_db, None)


# ----------------------------------------------------------------------
# 5. User Registration, Scrypt Password Auth & JWT Login Tests
# ----------------------------------------------------------------------

def test_parent_registration_and_login_flow(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        # Register new parent
        reg_payload = {
            "family_name": "Simpson Family",
            "email": "marge@example.com",
            "password": "SuperSecretPassword123",
        }
        res = client.post("/api/auth/register", json=reg_payload)
        assert res.status_code == 201
        data = res.json()
        assert data["status"] == "pending_verification"
        assert "user_id" in data
        assert "family_id" in data
        registered_user = db_session.query(User).filter_by(email="marge@example.com").one()
        assert registered_user.hashed_password.startswith("$argon2")
        assert registered_user.hashed_password != reg_payload["password"]

        # Login with correct password
        login_res = client.post(
            "/api/auth/login",
            json={"email": "marge@example.com", "password": "SuperSecretPassword123"},
        )
        assert login_res.status_code == 200
        token_data = login_res.json()
        assert "access_token" in token_data
        assert token_data["token_type"] == "bearer"
        assert token_data["role"] == UserRole.PARENT.value

        # Login with wrong password
        fail_res = client.post(
            "/api/auth/login",
            json={"email": "marge@example.com", "password": "WrongPassword123"},
        )
        assert fail_res.status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_login_lockout_after_five_failed_attempts(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        client.post(
            "/api/auth/register",
            json={"family_name": "Lockout Test", "email": "homer@example.com", "password": "Password12345"},
        )
        for _ in range(5):
            res = client.post(
                "/api/auth/login",
                json={"email": "homer@example.com", "password": "WrongPassword!"},
            )
            assert res.status_code == 401

        # 6th attempt should be locked out with 429
        locked_res = client.post(
            "/api/auth/login",
            json={"email": "homer@example.com", "password": "Password12345"},
        )
        assert locked_res.status_code == 429
        assert "Too many attempts" in locked_res.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_registration_duplicate_email_rejected(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        payload = {
            "family_name": "Dup Family",
            "email": "duplicate@example.com",
            "password": "Password12345",
        }
        res1 = client.post("/api/auth/register", json=payload)
        assert res1.status_code == 201

        res2 = client.post("/api/auth/register", json=payload)
        assert res2.status_code == 409
        assert "already exists" in res2.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_db, None)
