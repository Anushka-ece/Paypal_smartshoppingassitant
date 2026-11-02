import json
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
from app.models.account import Account, AccountType
from app.models.family import Family
from app.models.purchase_request import PurchaseRequest, PurchaseRequestStatus
from app.models.transaction import Transaction, TransactionStatus
from app.models.webhook_event import ProcessedWebhookEvent
from app.services.paypal_service import PayPalService

client = TestClient(app)


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
    Base.metadata.create_all(
        bind=test_engine,
        tables=[
            Family.__table__,
            User.__table__,
            Account.__table__,
            Transaction.__table__,
            ProcessedWebhookEvent.__table__,
            PurchaseRequest.__table__,
        ],
    )

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        test_engine.dispose()


@pytest.fixture
def valid_headers(monkeypatch):
    monkeypatch.setattr("app.services.paypal_service.APP_ENV", "test")
    monkeypatch.setattr("app.services.paypal_service.PAYPAL_ALLOW_MOCK_WEBHOOKS", True)
    return {
        "PAYPAL-AUTH-ALGO": "SHA256withRSA",
        "PAYPAL-CERT-URL": "https://api.sandbox.paypal.com/cert",
        "PAYPAL-TRANSMISSION-ID": "trans-mock-123",
        "PAYPAL-TRANSMISSION-SIG": "mock-valid-signature",
        "PAYPAL-TRANSMISSION-TIME": "2026-10-27T18:00:00Z",
    }


# ----------------------------------------------------------------------
# 1. Event Filtering & Signature Verification Unit Tests
# ----------------------------------------------------------------------

def test_webhook_event_filtering():
    service = PayPalService()
    supported = [
        "PAYMENT.CAPTURE.COMPLETED",
        "PAYMENT.CAPTURE.REFUNDED",
        "PAYMENT.SALE.REFUNDED",
        "CUSTOMER.DISPUTE.RESOLVED",
    ]
    for event_type in supported:
        assert service.is_event_supported(event_type) is True
    assert service.is_event_supported("UNKNOWN.EVENT") is False
    assert service.is_event_supported("BILLING.SUBSCRIPTION.CREATED") is False


@pytest.mark.anyio
async def test_verify_webhook_signature_missing_headers():
    service = PayPalService(webhook_id="mock_webhook_id")
    body = json.dumps({"id": "WH-123", "event_type": "PAYMENT.CAPTURE.COMPLETED"}).encode("utf-8")

    # Empty headers must fail verification
    assert await service.verify_webhook_signature({}, body) is False

    # Incomplete headers must fail verification
    partial_headers = {
        "PAYPAL-AUTH-ALGO": "SHA256withRSA",
        "PAYPAL-CERT-URL": "https://api.sandbox.paypal.com/cert",
    }
    assert await service.verify_webhook_signature(partial_headers, body) is False


@pytest.mark.anyio
async def test_verify_webhook_signature_mock_success_and_failure(monkeypatch):
    monkeypatch.setattr("app.services.paypal_service.APP_ENV", "test")
    monkeypatch.setattr("app.services.paypal_service.PAYPAL_ALLOW_MOCK_WEBHOOKS", True)
    service = PayPalService(webhook_id="mock_webhook_id")
    body = json.dumps({"id": "WH-123", "event_type": "PAYMENT.CAPTURE.COMPLETED"}).encode("utf-8")

    valid_headers = {
        "PAYPAL-AUTH-ALGO": "SHA256withRSA",
        "PAYPAL-CERT-URL": "https://api.sandbox.paypal.com/cert",
        "PAYPAL-TRANSMISSION-ID": "trans-12345",
        "PAYPAL-TRANSMISSION-SIG": "mock-valid-sig-1234",
        "PAYPAL-TRANSMISSION-TIME": "2026-10-27T18:00:00Z",
    }
    assert await service.verify_webhook_signature(valid_headers, body) is True

    invalid_headers = dict(valid_headers)
    invalid_headers["PAYPAL-TRANSMISSION-SIG"] = "mock-invalid"
    assert await service.verify_webhook_signature(invalid_headers, body) is False


@pytest.mark.anyio
async def test_verify_webhook_signature_via_paypal_api_success():
    service = PayPalService(
        client_id="test_client_id",
        client_secret="test_secret",
        webhook_id="WH-LIVE-CONFIGURED-ID",
    )
    body = json.dumps({"id": "WH-999", "event_type": "PAYMENT.CAPTURE.COMPLETED"}).encode("utf-8")
    headers = {
        "PAYPAL-AUTH-ALGO": "SHA256withRSA",
        "PAYPAL-CERT-URL": "https://api.sandbox.paypal.com/cert",
        "PAYPAL-TRANSMISSION-ID": "trans-live-1",
        "PAYPAL-TRANSMISSION-SIG": "live-crypto-sig-abc",
        "PAYPAL-TRANSMISSION-TIME": "2026-10-27T18:00:00Z",
    }

    mock_resp = httpx.Response(
        status_code=200,
        json={"verification_status": "SUCCESS"},
        request=httpx.Request("POST", "https://api-m.sandbox.paypal.com/v1/notifications/verify-webhook-signature"),
    )

    with patch.object(service, "get_app_access_token", new_callable=AsyncMock) as mock_token:
        mock_token.return_value = "mock_access_token_777"
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            is_valid = await service.verify_webhook_signature(headers, body)
            assert is_valid is True
            assert mock_post.called
            called_payload = mock_post.call_args[1]["json"]
            assert called_payload["webhook_id"] == "WH-LIVE-CONFIGURED-ID"
            assert called_payload["transmission_id"] == "trans-live-1"


@pytest.mark.anyio
async def test_verify_webhook_signature_via_paypal_api_failure():
    service = PayPalService(
        client_id="test_client_id",
        client_secret="test_secret",
        webhook_id="WH-LIVE-CONFIGURED-ID",
    )
    body = json.dumps({"id": "WH-999", "event_type": "PAYMENT.CAPTURE.COMPLETED"}).encode("utf-8")
    headers = {
        "PAYPAL-AUTH-ALGO": "SHA256withRSA",
        "PAYPAL-CERT-URL": "https://api.sandbox.paypal.com/cert",
        "PAYPAL-TRANSMISSION-ID": "trans-live-1",
        "PAYPAL-TRANSMISSION-SIG": "bad-sig",
        "PAYPAL-TRANSMISSION-TIME": "2026-10-27T18:00:00Z",
    }

    mock_resp = httpx.Response(
        status_code=200,
        json={"verification_status": "FAILURE"},
        request=httpx.Request("POST", "https://api-m.sandbox.paypal.com/v1/notifications/verify-webhook-signature"),
    )

    with patch.object(service, "get_app_access_token", new_callable=AsyncMock) as mock_token:
        mock_token.return_value = "mock_access_token_777"
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp
            is_valid = await service.verify_webhook_signature(headers, body)
            assert is_valid is False


# ----------------------------------------------------------------------
# 2. Webhook API Endpoint & Header Validation Tests
# ----------------------------------------------------------------------

def test_api_webhook_missing_headers_returns_400():
    payload = {"id": "WH-001", "event_type": "PAYMENT.CAPTURE.COMPLETED"}
    response = client.post("/api/webhooks/paypal", json=payload)
    assert response.status_code == 400
    assert "headers" in response.json().get("detail", "").lower()


def test_api_webhook_invalid_signature_returns_400():
    payload = {"id": "WH-002", "event_type": "PAYMENT.CAPTURE.COMPLETED"}
    headers = {
        "PAYPAL-AUTH-ALGO": "SHA256withRSA",
        "PAYPAL-CERT-URL": "https://api.sandbox.paypal.com/cert",
        "PAYPAL-TRANSMISSION-ID": "trans-002",
        "PAYPAL-TRANSMISSION-SIG": "mock-invalid",
        "PAYPAL-TRANSMISSION-TIME": "2026-10-27T18:00:00Z",
    }
    response = client.post("/api/webhooks/paypal", json=payload, headers=headers)
    assert response.status_code == 400
    assert "signature" in response.json().get("detail", "").lower()


# ----------------------------------------------------------------------
# 3. Webhook Routing & Idempotency Tests
# ----------------------------------------------------------------------

def test_webhook_routing_capture_completed(db_session, valid_headers):
    # Setup account in DB
    user = User(email="parent_wh@example.com", name="WH Parent", role=UserRole.PARENT.value)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    account = Account(
        user_id=user.id,
        account_type=AccountType.PAYPAL_LINKED.value,
        paypal_account_id="ACC_PAYEE_123",
        balance=100.0,
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)

    app.dependency_overrides[get_db] = lambda: db_session

    event_payload = {
        "id": "WH-EVT-CAPTURE-1",
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource_type": "capture",
        "summary": "Payment capture completed",
        "resource": {
            "id": "CAP-10001",
            "status": "COMPLETED",
            "amount": {"value": "45.50", "currency_code": "USD"},
            "custom_id": str(account.id),
            "parent_payment": "ORDER-99901",
            "payee": {"merchant_id": "ACC_PAYEE_123", "email_address": "merchant@store.com"},
            "seller_receivable_breakdown": {"merchant_name": "Target Store"},
        },
    }

    try:
        response = client.post("/api/webhooks/paypal", json=event_payload, headers=valid_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processed"
        assert data["event_type"] == "PAYMENT.CAPTURE.COMPLETED"

        # Check transaction created in DB
        tx = db_session.query(Transaction).filter_by(paypal_transaction_id="CAP-10001").first()
        assert tx is not None
        assert tx.amount == 45.50
        assert tx.currency == "USD"
        assert tx.status == TransactionStatus.COMPLETED.value
        assert tx.account_id == account.id
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_capture_webhook_completes_linked_purchase_request(db_session, valid_headers):
    family = Family(name="Webhook Checkout Family")
    db_session.add(family)
    db_session.commit()
    user = User(email="webhook-checkout@example.com", name="Webhook Child", role=UserRole.CHILD.value, family_id=family.id)
    db_session.add(user)
    db_session.commit()
    account = Account(user_id=user.id, family_id=family.id, account_type=AccountType.CHILD_VIRTUAL.value)
    db_session.add(account)
    request = PurchaseRequest(
        family_id=family.id,
        child_id=user.id,
        item_name="Music book",
        store_url="https://music.example/book",
        amount=12.0,
        status=PurchaseRequestStatus.APPROVED.value,
        paypal_order_id="ORDER-WEBHOOK-1",
    )
    db_session.add_all([account, request])
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    payload = {
        "id": "WH-EVT-CHECKOUT-CAPTURE",
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource": {
            "id": "CAP-CHECKOUT-1",
            "status": "COMPLETED",
            "amount": {"value": "12.00", "currency_code": "USD"},
            "custom_id": f"purchase-request-{request.id}",
            "supplementary_data": {"related_ids": {"order_id": "ORDER-WEBHOOK-1"}},
        },
    }
    try:
        response = client.post("/api/webhooks/paypal", json=payload, headers=valid_headers)
        assert response.status_code == 200
        db_session.refresh(request)
        assert request.status == PurchaseRequestStatus.EXECUTED.value
        assert request.paypal_capture_id == "CAP-CHECKOUT-1"
        assert request.paypal_payment_status == "COMPLETED"
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_webhook_idempotency_duplicate_event_returns_200_without_reprocessing(db_session, valid_headers):
    # Setup account
    user = User(email="idemp@example.com", name="Idemp User", role=UserRole.PARENT.value)
    db_session.add(user)
    db_session.commit()
    account = Account(user_id=user.id, account_type=AccountType.PAYPAL_LINKED.value, balance=50.0)
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)

    app.dependency_overrides[get_db] = lambda: db_session

    event_payload = {
        "id": "WH-EVT-DUPLICATE-99",
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource_type": "capture",
        "resource": {
            "id": "CAP-DUPLICATE-99",
            "status": "COMPLETED",
            "amount": {"value": "20.00", "currency_code": "USD"},
            "custom_id": str(account.id),
        },
    }

    try:
        # First delivery: processed
        res1 = client.post("/api/webhooks/paypal", json=event_payload, headers=valid_headers)
        assert res1.status_code == 200
        assert res1.json()["status"] == "processed"

        tx_count_1 = db_session.query(Transaction).filter_by(paypal_transaction_id="CAP-DUPLICATE-99").count()
        assert tx_count_1 == 1

        # Second delivery (Duplicate): must return 200 OK without re-processing
        res2 = client.post("/api/webhooks/paypal", json=event_payload, headers=valid_headers)
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["status"] == "already_processed"
        assert data2["event_id"] == "WH-EVT-DUPLICATE-99"

        # Ensure no duplicate transaction was created
        tx_count_2 = db_session.query(Transaction).filter_by(paypal_transaction_id="CAP-DUPLICATE-99").count()
        assert tx_count_2 == 1
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_webhook_routing_refund(db_session, valid_headers):
    # Setup account and original transaction
    user = User(email="refund@example.com", name="Refund User", role=UserRole.PARENT.value)
    db_session.add(user)
    db_session.commit()
    account = Account(user_id=user.id, account_type=AccountType.PAYPAL_LINKED.value)
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)

    original_tx = Transaction(
        account_id=account.id,
        paypal_transaction_id="CAP-ORIG-REFUND",
        amount=60.00,
        currency="USD",
        status=TransactionStatus.COMPLETED.value,
        parent_payment_id="ORDER-REFUND-1",
    )
    db_session.add(original_tx)
    db_session.commit()
    db_session.refresh(original_tx)

    app.dependency_overrides[get_db] = lambda: db_session

    # 1. Partial refund test
    partial_refund_payload = {
        "id": "WH-EVT-REFUND-PARTIAL",
        "event_type": "PAYMENT.CAPTURE.REFUNDED",
        "resource_type": "refund",
        "resource": {
            "id": "REF-PARTIAL-1",
            "amount": {"value": "20.00", "currency_code": "USD"},
            "parent_payment": "CAP-ORIG-REFUND",
        },
    }

    try:
        resp_partial = client.post("/api/webhooks/paypal", json=partial_refund_payload, headers=valid_headers)
        assert resp_partial.status_code == 200
        assert resp_partial.json()["status"] == "processed"

        db_session.refresh(original_tx)
        assert original_tx.status == TransactionStatus.PARTIALLY_REFUNDED.value
        assert original_tx.refund_id == "REF-PARTIAL-1"

        # 2. Full refund via PAYMENT.SALE.REFUNDED
        full_refund_payload = {
            "id": "WH-EVT-REFUND-FULL",
            "event_type": "PAYMENT.SALE.REFUNDED",
            "resource_type": "refund",
            "resource": {
                "id": "REF-FULL-2",
                "amount": {"value": "60.00", "currency_code": "USD"},
                "sale_id": "CAP-ORIG-REFUND",
            },
        }
        resp_full = client.post("/api/webhooks/paypal", json=full_refund_payload, headers=valid_headers)
        assert resp_full.status_code == 200
        assert resp_full.json()["status"] == "processed"

        db_session.refresh(original_tx)
        assert original_tx.status == TransactionStatus.REFUNDED.value
        assert original_tx.refund_id == "REF-FULL-2"
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_webhook_routing_dispute_resolved(db_session, valid_headers):
    user = User(email="dispute@example.com", name="Dispute User", role=UserRole.PARENT.value)
    db_session.add(user)
    db_session.commit()
    account = Account(user_id=user.id, account_type=AccountType.PAYPAL_LINKED.value)
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)

    tx = Transaction(
        account_id=account.id,
        paypal_transaction_id="CAP-DISPUTED-TX",
        amount=99.99,
        currency="USD",
        status=TransactionStatus.COMPLETED.value,
    )
    db_session.add(tx)
    db_session.commit()
    db_session.refresh(tx)

    app.dependency_overrides[get_db] = lambda: db_session

    dispute_payload = {
        "id": "WH-EVT-DISPUTE-1",
        "event_type": "CUSTOMER.DISPUTE.RESOLVED",
        "resource_type": "dispute",
        "resource": {
            "dispute_id": "PP-D-54321",
            "status": "RESOLVED",
            "disputed_transactions": [{"seller_transaction_id": "CAP-DISPUTED-TX"}],
            "dispute_outcome": {"outcome_code": "RESOLVED_BUYER_FAVOUR"},
        },
    }

    try:
        resp = client.post("/api/webhooks/paypal", json=dispute_payload, headers=valid_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "processed"

        db_session.refresh(tx)
        assert tx.status == TransactionStatus.DISPUTED.value
        assert tx.is_flagged is True
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_webhook_unsupported_event_returns_200_ignored(db_session, valid_headers):
    app.dependency_overrides[get_db] = lambda: db_session
    payload = {
        "id": "WH-EVT-UNSUPPORTED",
        "event_type": "INVOICING.INVOICE.PAID",
        "resource": {},
    }
    try:
        response = client.post("/api/webhooks/paypal", json=payload, headers=valid_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "ignored"
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_webhook_route_mounted_at_both_paths(db_session, valid_headers):
    app.dependency_overrides[get_db] = lambda: db_session
    payload1 = {"id": "WH-PATH-1", "event_type": "INVOICING.INVOICE.PAID"}
    payload2 = {"id": "WH-PATH-2", "event_type": "INVOICING.INVOICE.PAID"}

    try:
        res_api = client.post("/api/webhooks/paypal", json=payload1, headers=valid_headers)
        res_direct = client.post("/webhooks/paypal", json=payload2, headers=valid_headers)
        assert res_api.status_code == 200
        assert res_direct.status_code == 200
        assert res_api.json()["status"] == "ignored"
        assert res_direct.json()["status"] == "ignored"
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_webhook_database_claim_prevents_duplicate_processing(db_session, valid_headers):
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        payload = {"id": "WH-DATABASE-CLAIM-01", "event_type": "INVOICING.INVOICE.PAID"}
        first = client.post("/api/webhooks/paypal", json=payload, headers=valid_headers)
        assert first.status_code == 200
        assert first.json()["status"] == "ignored"

        repeated = client.post("/api/webhooks/paypal", json=payload, headers=valid_headers)
        assert repeated.status_code == 200
        assert repeated.json()["status"] == "already_processed"
        assert repeated.json()["event_id"] == "WH-DATABASE-CLAIM-01"
        assert (
            db_session.query(ProcessedWebhookEvent)
            .filter_by(event_id="WH-DATABASE-CLAIM-01")
            .count()
            == 1
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
