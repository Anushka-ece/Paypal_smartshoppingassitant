import pytest
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
        app.dependency_overrides.pop(get_db, None)
