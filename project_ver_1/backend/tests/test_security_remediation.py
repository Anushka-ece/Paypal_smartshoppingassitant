import hashlib
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.api import auth as auth_api
from app.models.account import Account, AccountType
from app.models.budget import BudgetEnvelope
from app.models.family import Family
from app.models.paypal_oauth_state import PayPalOAuthState
from app.models.purchase_request import PurchaseRequest, PurchaseRequestStatus
from app.models.transaction import Transaction, TransactionStatus
from app.models.user import User, UserRole
from app.security.auth import create_access_token
from app.security.crypto import decrypt_token, encrypt_token
from app.services.paypal_service import PayPalService

pytestmark = pytest.mark.auth_security


@pytest.fixture
def security_context():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = testing_session()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[auth_api.get_paypal_service] = lambda: PayPalService(
        client_id="sandbox-test-client",
        client_secret="sandbox-test-secret",
        base_url="https://api-m.sandbox.paypal.com",
    )
    try:
        yield db, TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(auth_api.get_paypal_service, None)
        db.close()
        engine.dispose()


def create_family_and_user(db, name: str, email: str, role=UserRole.PARENT.value):
    family = Family(name=name)
    db.add(family)
    db.flush()
    user = User(
        family_id=family.id,
        email=email,
        name=name,
        role=role,
        hashed_password="test-hash-not-used-for-login",
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return family, user


def auth_headers(user):
    return {"Authorization": f"Bearer {create_access_token(user)}"}


def test_unauthed_invalid_and_expired_tokens_are_rejected(security_context):
    _, client = security_context
    assert client.get("/api/transactions").status_code == 401
    assert client.get(
        "/api/transactions",
        headers={"Authorization": "Bearer not-a-jwt"},
    ).status_code == 401

    _, user = create_family_and_user(security_context[0], "Expired", "expired@example.test")
    expired_token = create_access_token(user, expires_minutes=-1)
    assert client.get(
        "/api/transactions",
        headers={"Authorization": f"Bearer {expired_token}"},
    ).status_code == 401


def test_logout_invalidates_previously_issued_access_token(security_context):
    db, client = security_context
    _, user = create_family_and_user(db, "Logout", "logout@example.test")
    headers = auth_headers(user)

    assert client.post("/api/auth/logout", headers=headers).status_code == 200
    assert client.get("/api/transactions", headers=headers).status_code == 401


def test_child_cannot_start_paypal_account_linking(security_context):
    db, client = security_context
    _, child = create_family_and_user(db, "Child OAuth", "child-oauth@example.test", UserRole.CHILD.value)
    response = client.get("/api/auth/paypal/authorize", headers=auth_headers(child))
    assert response.status_code == 403


def test_paypal_token_encryption_requires_a_configured_key(monkeypatch):
    monkeypatch.setattr("app.security.crypto.TOKEN_ENCRYPTION_KEY", "")
    with pytest.raises(ValueError, match="TOKEN_ENCRYPTION_KEY"):
        encrypt_token("sandbox-token")


def test_family_transactions_refunds_and_purchases_are_scoped(security_context):
    db, client = security_context
    family_a, parent_a = create_family_and_user(db, "Family A", "a@example.test")
    family_b, parent_b = create_family_and_user(db, "Family B", "b@example.test")
    child_a = User(
        family_id=family_a.id,
        email="child-a@example.test",
        name="Child A",
        role=UserRole.CHILD.value,
        hashed_password="not-a-login-credential",
    )
    child_b = User(
        family_id=family_b.id,
        email="child-b@example.test",
        name="Child B",
        role=UserRole.CHILD.value,
        hashed_password="not-a-login-credential",
    )
    db.add_all([child_a, child_b])
    db.flush()
    account_a = Account(user_id=parent_a.id, family_id=family_a.id, account_type=AccountType.PARENT_WALLET.value)
    account_b = Account(user_id=parent_b.id, family_id=family_b.id, account_type=AccountType.PARENT_WALLET.value)
    db.add_all([account_a, account_b])
    db.flush()
    transaction_a = Transaction(
        account_id=account_a.id,
        family_id=family_a.id,
        user_id=parent_a.id,
        paypal_transaction_id="TX-FAMILY-A",
        amount=10,
        status=TransactionStatus.COMPLETED.value,
    )
    transaction_b = Transaction(
        account_id=account_b.id,
        family_id=family_b.id,
        user_id=parent_b.id,
        paypal_transaction_id="TX-FAMILY-B-REFUND",
        amount=50,
        status=TransactionStatus.REFUNDED.value,
        refund_id="REFUND-FAMILY-B",
    )
    purchase_b = PurchaseRequest(
        family_id=family_b.id,
        child_id=child_b.id,
        item_name="Private item",
        store_url="https://merchant.example/item",
        amount=45,
        status=PurchaseRequestStatus.PENDING_APPROVAL.value,
    )
    purchase_a = PurchaseRequest(
        family_id=family_a.id,
        child_id=child_a.id,
        item_name="Family A item",
        store_url="https://merchant.example/family-a",
        amount=15,
        status=PurchaseRequestStatus.PENDING_APPROVAL.value,
    )
    db.add_all([transaction_a, transaction_b, purchase_a, purchase_b])
    db.commit()
    headers = auth_headers(parent_a)

    own_family = client.get(f"/api/family/members?family_id={family_a.id}", headers=headers)
    assert own_family.status_code == 200
    assert all(member["family_id"] == family_a.id for member in own_family.json())
    assert client.get(f"/api/family/members?family_id={family_b.id}", headers=headers).status_code == 404

    own_transactions = client.get(
        f"/api/transactions?family_id={family_a.id}",
        headers=headers,
    )
    assert own_transactions.status_code == 200
    assert [tx["paypal_transaction_id"] for tx in own_transactions.json()] == ["TX-FAMILY-A"]
    assert client.get(
        f"/api/transactions?family_id={family_b.id}",
        headers=headers,
    ).status_code == 404
    assert client.get(
        f"/api/transactions?account_id={account_b.id}",
        headers=headers,
    ).json() == []

    family_purchases = client.get(
        f"/api/purchase-requests?family_id={family_a.id}",
        headers=headers,
    )
    assert family_purchases.status_code == 200
    assert [item["id"] for item in family_purchases.json()] == [purchase_a.id]
    own_modify = client.post(
        f"/api/purchase-requests/{purchase_a.id}/reject",
        headers=headers,
        json={"reason": "Within my family"},
    )
    assert own_modify.status_code == 200
    modify_other_purchase = client.post(
        f"/api/purchase-requests/{purchase_b.id}/reject",
        headers=headers,
        json={"reason": "Not authorized"},
    )
    assert modify_other_purchase.status_code == 404
    db.refresh(purchase_b)
    assert purchase_b.status == PurchaseRequestStatus.PENDING_APPROVAL.value


def test_invalid_paypal_oauth_state_is_rejected_before_code_exchange(security_context):
    _, client = security_context
    with patch.object(PayPalService, "exchange_oauth_code", new_callable=AsyncMock) as exchange:
        response = client.get("/api/auth/paypal/callback?code=code&state=invalid")
    assert response.status_code == 400
    exchange.assert_not_awaited()


def test_paypal_oauth_state_binds_user_and_prevents_duplicate_account_link(security_context):
    db, client = security_context
    _, user_a = create_family_and_user(db, "OAuth A", "oauth-a@example.test")
    _, user_b = create_family_and_user(db, "OAuth B", "oauth-b@example.test")

    def authorize(user):
        response = client.get("/api/auth/paypal/authorize", headers=auth_headers(user))
        assert response.status_code == 200
        return parse_qs(urlparse(response.json()["auth_url"]).query)["state"][0]

    state_a = authorize(user_a)
    state_b = authorize(user_b)
    tokens = {
        "access_token": "sandbox-access-token",
        "refresh_token": "sandbox-refresh-token",
        "expires_in": 32400,
        "payer_id": "SANDBOX-PAYER-UNIQUE",
    }
    with (
        patch.object(PayPalService, "exchange_oauth_code", new_callable=AsyncMock, return_value=tokens),
        patch("app.workers.celery_worker.sync_historical_transactions_task.delay"),
    ):
        linked = client.get(f"/api/auth/paypal/callback?code=first-code&state={state_a}")
        assert linked.status_code == 200
        assert linked.json()["user_id"] == user_a.id
        assert client.get(f"/api/auth/paypal/callback?code=second-code&state={state_b}").status_code == 409

    accounts = db.query(Account).filter(Account.paypal_account_id == "SANDBOX-PAYER-UNIQUE").all()
    assert len(accounts) == 1
    assert accounts[0].user_id == user_a.id
    assert decrypt_token(accounts[0].paypal_encrypted_token) == "sandbox-access-token"
    assert decrypt_token(accounts[0].paypal_encrypted_refresh_token) == "sandbox-refresh-token"


def make_expired_linked_account(db, refresh_token="valid-refresh-token"):
    family, user = create_family_and_user(db, "Token Family", "token@example.test")
    account = Account(
        user_id=user.id,
        family_id=family.id,
        account_type=AccountType.PAYPAL_LINKED.value,
        paypal_encrypted_token=encrypt_token("expired-access-token"),
        paypal_encrypted_refresh_token=encrypt_token(refresh_token) if refresh_token else None,
        paypal_access_token_expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def test_expired_paypal_access_token_refreshes_and_persists_rotation(security_context):
    db, _ = security_context
    account = make_expired_linked_account(db)
    service = MagicMock()
    service.refresh_access_token = AsyncMock(
        return_value={
            "access_token": "new-access-token",
            "refresh_token": "rotated-refresh-token",
            "expires_in": 3600,
        }
    )
    service.fetch_historical_transactions.return_value = []
    with patch("app.workers.celery_worker.PayPalService", return_value=service):
        from app.workers.celery_worker import sync_historical_transactions_task

        result = sync_historical_transactions_task(account.id, db=db)

    assert result["status"] == "success"
    service.refresh_access_token.assert_awaited_once_with("valid-refresh-token")
    service.fetch_historical_transactions.assert_called_once_with(access_token="new-access-token")
    db.refresh(account)
    assert decrypt_token(account.paypal_encrypted_token) == "new-access-token"
    assert decrypt_token(account.paypal_encrypted_refresh_token) == "rotated-refresh-token"
    persisted_expiry = account.paypal_access_token_expires_at
    if persisted_expiry.tzinfo is None:
        persisted_expiry = persisted_expiry.replace(tzinfo=timezone.utc)
    assert persisted_expiry > datetime.now(timezone.utc)


@pytest.mark.parametrize(
    ("refresh_token", "expected_message"),
    [
        (None, "reconnect"),
        ("not-an-encrypted-token", "reconnect"),
    ],
)
def test_expired_paypal_access_token_fails_closed_without_valid_refresh_token(
    security_context, refresh_token, expected_message
):
    db, _ = security_context
    account = make_expired_linked_account(db, refresh_token=refresh_token)
    if refresh_token == "not-an-encrypted-token":
        account.paypal_encrypted_refresh_token = refresh_token
        db.commit()
    service = MagicMock()
    service.refresh_access_token = AsyncMock()
    with patch("app.workers.celery_worker.PayPalService", return_value=service):
        from app.workers.celery_worker import sync_historical_transactions_task

        result = sync_historical_transactions_task(account.id, db=db)

    assert result["status"] == "error"
    assert expected_message in result["message"].lower()
    service.refresh_access_token.assert_not_awaited()
    service.fetch_historical_transactions.assert_not_called()


def test_paypal_refresh_failure_does_not_use_expired_token(security_context):
    db, _ = security_context
    account = make_expired_linked_account(db)
    service = MagicMock()
    service.refresh_access_token = AsyncMock(side_effect=RuntimeError("refresh rejected"))
    service.fetch_historical_transactions.return_value = []
    with patch("app.workers.celery_worker.PayPalService", return_value=service):
        from app.workers.celery_worker import sync_historical_transactions_task

        result = sync_historical_transactions_task(account.id, db=db)

    assert result["status"] == "error"
    assert "reconnect" in result["message"].lower()
    service.fetch_historical_transactions.assert_not_called()


def test_oauth_state_is_single_use_and_expiration_is_enforced(security_context):
    db, client = security_context
    _, user = create_family_and_user(db, "OAuth Expiration", "oauth-expiry@example.test")
    state_response = client.get("/api/auth/paypal/authorize", headers=auth_headers(user))
    state = parse_qs(urlparse(state_response.json()["auth_url"]).query)["state"][0]
    with patch.object(
        PayPalService,
        "exchange_oauth_code",
        new_callable=AsyncMock,
        return_value={
            "access_token": "access",
            "expires_in": 1000,
            "payer_id": "ONE-TIME-PAYER",
        },
    ), patch("app.workers.celery_worker.sync_historical_transactions_task.delay"):
        first = client.get(f"/api/auth/paypal/callback?code=one&state={state}")
        assert first.status_code == 200
        replay = client.get(f"/api/auth/paypal/callback?code=two&state={state}")
        assert replay.status_code == 400

    expired_state = "expired-state"
    db.add(
        PayPalOAuthState(
            state_hash=hashlib.sha256(expired_state.encode()).hexdigest(),
            user_id=user.id,
            expires_at=datetime.utcnow() - timedelta(seconds=1),
        )
    )
    db.commit()
    with patch.object(PayPalService, "exchange_oauth_code", new_callable=AsyncMock) as exchange:
        expired = client.get(f"/api/auth/paypal/callback?code=expired&state={expired_state}")
    assert expired.status_code == 400
    exchange.assert_not_awaited()


def test_parent_can_record_family_expense_and_update_matching_budget(security_context):
    db, client = security_context
    family, parent = create_family_and_user(db, "Expense Demo", "expense-demo@example.test")
    envelope = BudgetEnvelope(
        family_id=family.id,
        name="Food & Dining",
        allocated_amount=200,
        current_spent=10,
    )
    db.add(envelope)
    db.commit()

    response = client.post(
        "/api/transactions",
        headers=auth_headers(parent),
        json={
            "merchant_name": "Neighborhood Market",
            "amount": 24.5,
            "currency": "USD",
            "category": "Food & Dining",
            "description": "Family groceries",
        },
    )

    assert response.status_code == 201
    assert response.json()["merchant_name"] == "Neighborhood Market"
    assert response.json()["amount"] == 24.5
    db.refresh(envelope)
    assert envelope.current_spent == 34.5

    family_transactions = client.get(
        f"/api/transactions?family_id={family.id}",
        headers=auth_headers(parent),
    )
    assert family_transactions.status_code == 200
    assert len(family_transactions.json()) == 1


def test_budget_created_after_expense_includes_existing_category_spend(security_context):
    db, client = security_context
    family, parent = create_family_and_user(db, "Historical Spend", "historical-spend@example.test")
    headers = auth_headers(parent)
    expense = client.post(
        "/api/transactions",
        headers=headers,
        json={
            "merchant_name": "Neighborhood Market",
            "amount": 24.5,
            "currency": "USD",
            "category": "Groceries",
        },
    )
    assert expense.status_code == 201

    budget = client.post(
        "/api/budgets/envelopes",
        headers=headers,
        json={
            "family_id": family.id,
            "name": "Groceries",
            "allocated_amount": 100,
            "currency": "USD",
        },
    )
    assert budget.status_code == 200
    assert budget.json()["current_spent"] == 24.5


def test_child_cannot_create_family_expense(security_context):
    db, client = security_context
    family, child = create_family_and_user(
        db,
        "Child Expense",
        "child-expense@example.test",
        UserRole.CHILD.value,
    )
    response = client.post(
        "/api/transactions",
        headers=auth_headers(child),
        json={
            "merchant_name": "Online Store",
            "amount": 12,
            "currency": "USD",
            "category": "Shopping",
        },
    )
    assert response.status_code == 403
    assert db.query(Transaction).count() == 0
