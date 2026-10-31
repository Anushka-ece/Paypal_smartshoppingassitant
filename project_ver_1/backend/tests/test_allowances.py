import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models.family import Family
from app.models.user import User, UserRole
from app.models.account import Account, AccountType
from app.models.allowance import AllowanceSchedule
from app.api.allowances import (
    generate_payout_idempotency_key,
    should_execute_allowance,
    disburse_allowance_schedule,
)
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
            AllowanceSchedule.__table__,
        ],
    )

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        test_engine.dispose()


def test_idempotency_key_deterministic():
    key1 = generate_payout_idempotency_key(family_id=10, child_id=5, date="2026-11-01", allowance_id=1)
    key2 = generate_payout_idempotency_key(family_id=10, child_id=5, date="2026-11-01", allowance_id=1)
    assert key1 == key2
    assert "10-5-1-2026-11-01" in key1


def test_frozen_allowance_blocks_disbursement():
    schedule = {"allowance_id": 1, "is_frozen": True, "is_active": True, "amount": 20.00}
    assert should_execute_allowance(schedule) is False

    inactive_schedule = {"allowance_id": 2, "is_frozen": False, "is_active": False, "amount": 20.00}
    assert should_execute_allowance(inactive_schedule) is False

    valid_schedule = {"allowance_id": 3, "is_frozen": False, "is_active": True, "amount": 20.00}
    assert should_execute_allowance(valid_schedule) is True


@pytest.mark.anyio
async def test_paypal_service_execute_payout():
    service = PayPalService()
    # Test mock payout execution
    res = await service.execute_payout(
        receiver_email="kid@example.com",
        amount=15.00,
        idempotency_key="mock-key-12345",
    )
    assert res is not None
    assert res["status"] in ["SUCCESS", "PENDING"]
    assert res["batch_id"] is not None


def test_allowance_freeze_and_unfreeze_api(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        family = Family(name="Allowance Family")
        db_session.add(family)
        db_session.commit()

        child = User(name="Timmy", email="timmy@example.com", role=UserRole.CHILD.value, family_id=family.id)
        db_session.add(child)
        db_session.commit()

        # Create allowance schedule
        create_resp = client.post(
            "/api/allowances",
            json={
                "family_id": family.id,
                "child_id": child.id,
                "amount": 25.00,
                "frequency": "WEEKLY",
            },
        )
        assert create_resp.status_code == 200
        data = create_resp.json()
        assert data["id"] is not None
        assert data["amount"] == 25.00
        assert data["is_frozen"] is False

        # Freeze allowance
        freeze_resp = client.post(
            f"/api/allowances/{data['id']}/freeze",
            json={"reason": "Suspicious late night charge under investigation"},
        )
        assert freeze_resp.status_code == 200
        assert freeze_resp.json()["is_frozen"] is True
        assert "Suspicious" in freeze_resp.json()["freeze_reason"]

        # Attempt disbursement on frozen allowance -> blocks
        disburse_resp = client.post(f"/api/allowances/{data['id']}/disburse")
        assert disburse_resp.status_code == 400
        assert "frozen" in disburse_resp.json()["detail"].lower()

        # Unfreeze allowance
        unfreeze_resp = client.post(f"/api/allowances/{data['id']}/unfreeze")
        assert unfreeze_resp.status_code == 200
        assert unfreeze_resp.json()["is_frozen"] is False

        # Now disbursement succeeds
        disburse_success = client.post(f"/api/allowances/{data['id']}/disburse")
        assert disburse_success.status_code == 200
        assert disburse_success.json()["status"] == "SUCCESS"
    finally:
        app.dependency_overrides.pop(get_db, None)
