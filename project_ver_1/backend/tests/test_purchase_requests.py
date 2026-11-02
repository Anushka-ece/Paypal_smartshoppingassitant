import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models.family import Family
from app.models.user import User, UserRole
from app.models.account import Account
from app.models.purchase_request import PurchaseRequest, PurchaseRequestStatus
from app.api import purchase_requests as purchase_requests_api
from app.api.purchase_requests import _checkout_state

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
            PurchaseRequest.__table__,
        ],
    )

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        test_engine.dispose()


def test_purchase_request_initial_state():
    req = PurchaseRequest(
        family_id=1,
        child_id=2,
        item_name="Roblox Digital Code",
        store_url="https://store.example.com",
        amount=15.00,
        currency="USD",
        status=PurchaseRequestStatus.PENDING_APPROVAL.value,
    )
    assert req.status == PurchaseRequestStatus.PENDING_APPROVAL.value
    assert req.amount == 15.00


def test_purchase_request_crud_and_approval_flow(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        family = Family(name="Request Family")
        db_session.add(family)
        db_session.commit()
        paypal_service = AsyncMock()
        paypal_service.create_order_for_approval.return_value = {
            "id": "ORDER-SANDBOX-123",
            "status": "CREATED",
            "links": [{"rel": "approve", "href": "https://www.sandbox.paypal.com/checkoutnow?token=ORDER-SANDBOX-123"}],
        }
        app.dependency_overrides[purchase_requests_api.get_paypal_service] = lambda: paypal_service

        parent = User(name="Marge", email="marge@example.com", role=UserRole.PARENT.value, family_id=family.id)
        child = User(name="Lisa", email="lisa@example.com", role=UserRole.CHILD.value, family_id=family.id)
        db_session.add_all([parent, child])
        db_session.commit()

        # 1. Child creates purchase request
        create_resp = client.post(
            "/api/purchase-requests",
            json={
                "family_id": family.id,
                "child_id": child.id,
                "item_name": "Saxophone Reeds Pack",
                "store_url": "https://musicstore.example.com/reeds",
                "amount": 24.50,
            },
        )
        assert create_resp.status_code == 200
        req_data = create_resp.json()
        assert req_data["id"] is not None
        assert req_data["status"] == PurchaseRequestStatus.PENDING_APPROVAL.value
        assert req_data["amount"] == 24.50

        # 2. List purchase requests
        list_resp = client.get(f"/api/purchase-requests?family_id={family.id}")
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 1

        # 3. Parent approves request
        approve_resp = client.post(f"/api/purchase-requests/{req_data['id']}/approve")
        assert approve_resp.status_code == 200
        assert approve_resp.json()["status"] in [
            PurchaseRequestStatus.APPROVED.value,
            PurchaseRequestStatus.EXECUTED.value,
        ]
        assert approve_resp.json()["paypal_order_id"] == "ORDER-SANDBOX-123"
        assert approve_resp.json()["paypal_payment_status"] == "CREATED"
        assert approve_resp.json()["paypal_approval_url"].startswith("https://www.sandbox.paypal.com/")
        paypal_service.create_order_for_approval.assert_awaited_once()

        # 4. Another request rejected by parent
        create_resp2 = client.post(
            "/api/purchase-requests",
            json={
                "family_id": family.id,
                "child_id": child.id,
                "item_name": "Unverified Game Code",
                "store_url": "https://g2a.example.com",
                "amount": 40.00,
            },
        )
        req_data2 = create_resp2.json()

        reject_resp = client.post(
            f"/api/purchase-requests/{req_data2['id']}/reject",
            json={"reason": "Suspicious game key marketplace."},
        )
        assert reject_resp.status_code == 200
        assert reject_resp.json()["status"] == PurchaseRequestStatus.REJECTED.value
        assert "Suspicious" in reject_resp.json()["rejection_reason"]
    finally:
        app.dependency_overrides.pop(purchase_requests_api.get_paypal_service, None)
        app.dependency_overrides.pop(get_db, None)


def test_paypal_return_captures_order_once_and_persists_capture(db_session):
    family = Family(name="Checkout Family")
    db_session.add(family)
    db_session.commit()
    child = User(name="Lisa", email="lisa-checkout@example.com", role=UserRole.CHILD.value, family_id=family.id)
    db_session.add(child)
    db_session.commit()
    req = PurchaseRequest(
        family_id=family.id,
        child_id=child.id,
        item_name="Music book",
        store_url="https://music.example/book",
        amount=24.5,
        status=PurchaseRequestStatus.APPROVED.value,
        paypal_order_id="ORDER-APPROVED-1",
        paypal_approval_url="https://www.sandbox.paypal.com/checkoutnow?token=ORDER-APPROVED-1",
        paypal_payment_status="APPROVED",
    )
    db_session.add(req)
    db_session.commit()

    paypal_service = AsyncMock()
    paypal_service.capture_approved_order.return_value = {
        "id": "ORDER-APPROVED-1",
        "status": "COMPLETED",
        "purchase_units": [
            {"payments": {"captures": [{"id": "CAPTURE-123", "status": "COMPLETED"}]}}
        ],
    }
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[purchase_requests_api.get_paypal_service] = lambda: paypal_service
    try:
        response = client.get(
            f"/api/purchase-requests/{req.id}/paypal/return?token=ORDER-APPROVED-1"
            f"&checkout_state={_checkout_state(req.id)}"
        )
        assert response.status_code == 200
        assert response.json()["status"] == PurchaseRequestStatus.EXECUTED.value
        assert response.json()["paypal_payment_status"] == "COMPLETED"
        assert response.json()["paypal_capture_id"] == "CAPTURE-123"

        repeated = client.post(f"/api/purchase-requests/{req.id}/capture")
        assert repeated.status_code == 200
        assert repeated.json()["paypal_capture_id"] == "CAPTURE-123"
        paypal_service.capture_approved_order.assert_awaited_once_with(
            "ORDER-APPROVED-1",
            request_id=req.id,
        )
    finally:
        app.dependency_overrides.pop(purchase_requests_api.get_paypal_service, None)
        app.dependency_overrides.pop(get_db, None)


def test_paypal_order_creation_failure_is_persisted(db_session):
    family = Family(name="Failed Order Family")
    db_session.add(family)
    db_session.commit()
    child = User(name="Bart", email="bart-order@example.com", role=UserRole.CHILD.value, family_id=family.id)
    db_session.add(child)
    db_session.commit()
    req = PurchaseRequest(
        family_id=family.id,
        child_id=child.id,
        item_name="Game",
        store_url="https://games.example/item",
        amount=10,
    )
    db_session.add(req)
    db_session.commit()
    paypal_service = AsyncMock()
    paypal_service.create_order_for_approval.side_effect = RuntimeError("PayPal unavailable")
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[purchase_requests_api.get_paypal_service] = lambda: paypal_service
    try:
        response = client.post(f"/api/purchase-requests/{req.id}/approve")
        assert response.status_code == 502
        db_session.refresh(req)
        assert req.status == PurchaseRequestStatus.PAYMENT_FAILED.value
        assert req.paypal_payment_status == "ORDER_CREATION_FAILED"
    finally:
        app.dependency_overrides.pop(purchase_requests_api.get_paypal_service, None)
        app.dependency_overrides.pop(get_db, None)


def test_paypal_capture_failure_is_persisted_and_can_retry(db_session):
    family = Family(name="Failed Capture Family")
    db_session.add(family)
    db_session.commit()
    child = User(name="Bart", email="bart-capture@example.com", role=UserRole.CHILD.value, family_id=family.id)
    db_session.add(child)
    db_session.commit()
    req = PurchaseRequest(
        family_id=family.id,
        child_id=child.id,
        item_name="Game",
        store_url="https://games.example/item",
        amount=10,
        status=PurchaseRequestStatus.APPROVED.value,
        paypal_order_id="ORDER-RETRY-CAPTURE",
        paypal_payment_status="APPROVED",
    )
    db_session.add(req)
    db_session.commit()
    paypal_service = AsyncMock()
    paypal_service.capture_approved_order.side_effect = [
        RuntimeError("PayPal timeout"),
        {
            "id": "ORDER-RETRY-CAPTURE",
            "status": "COMPLETED",
            "purchase_units": [
                {"payments": {"captures": [{"id": "CAPTURE-RETRY"}]}}
            ],
        },
    ]
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[purchase_requests_api.get_paypal_service] = lambda: paypal_service
    try:
        failed = client.post(f"/api/purchase-requests/{req.id}/capture")
        assert failed.status_code == 502
        db_session.refresh(req)
        assert req.status == PurchaseRequestStatus.PAYMENT_FAILED.value
        assert req.paypal_payment_status == "CAPTURE_FAILED"

        retried = client.post(f"/api/purchase-requests/{req.id}/capture")
        assert retried.status_code == 200
        assert retried.json()["status"] == PurchaseRequestStatus.EXECUTED.value
        assert paypal_service.capture_approved_order.await_args_list[0].kwargs["request_id"] == req.id
        assert paypal_service.capture_approved_order.await_args_list[1].kwargs["request_id"] == req.id
    finally:
        app.dependency_overrides.pop(purchase_requests_api.get_paypal_service, None)
        app.dependency_overrides.pop(get_db, None)


def test_paypal_cancel_marks_order_cancelled(db_session):
    family = Family(name="Cancelled Order Family")
    db_session.add(family)
    db_session.commit()
    child = User(name="Bart", email="bart-cancel@example.com", role=UserRole.CHILD.value, family_id=family.id)
    db_session.add(child)
    db_session.commit()
    req = PurchaseRequest(
        family_id=family.id,
        child_id=child.id,
        item_name="Game",
        store_url="https://games.example/item",
        amount=10,
        status=PurchaseRequestStatus.APPROVED.value,
        paypal_order_id="ORDER-CANCELLED",
    )
    db_session.add(req)
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        response = client.get(
            f"/api/purchase-requests/{req.id}/paypal/cancel?token=ORDER-CANCELLED"
            f"&checkout_state={_checkout_state(req.id)}"
        )
        assert response.status_code == 200
        assert response.json()["status"] == PurchaseRequestStatus.CANCELLED.value
        assert response.json()["paypal_payment_status"] == "CANCELLED"
    finally:
        app.dependency_overrides.pop(get_db, None)
