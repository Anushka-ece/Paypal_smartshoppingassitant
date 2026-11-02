from datetime import datetime

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
from app.models.account import Account, AccountType
from app.models.allowance import AllowanceSchedule
from app.api.allowances import (
    generate_payout_idempotency_key,
    should_execute_allowance,
    disburse_allowance_schedule,
)
from app.api import allowances as allowance_api
from fastapi import HTTPException

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
async def test_disburse_allowance_records_only_confirmed_payout(db_session):
    family = Family(name="Payout Family")
    db_session.add(family)
    db_session.commit()
    child = User(name="Timmy", email="timmy@example.com", role=UserRole.CHILD.value, family_id=family.id)
    db_session.add(child)
    db_session.commit()
    account = Account(
        user_id=child.id,
        family_id=family.id,
        account_type=AccountType.CHILD_VIRTUAL.value,
        balance=5.0,
    )
    schedule = AllowanceSchedule(
        family_id=family.id,
        child_id=child.id,
        amount=15.0,
        currency="USD",
    )
    db_session.add_all([account, schedule])
    db_session.commit()

    confirmed_service = AsyncMock()
    confirmed_service.execute_payout.return_value = {
        "batch_id": "PAYOUT-123",
        "status": "SUCCESS",
    }
    result = disburse_allowance_schedule(schedule.id, db_session, confirmed_service)
    assert result["status"] == "SUCCESS"
    assert account.balance == 20.0
    assert schedule.last_payout_status == "SUCCESS"
    assert schedule.last_payout_batch_id == "PAYOUT-123"
    assert schedule.last_payout_date is not None

    failing_service = AsyncMock()
    failing_service.execute_payout.side_effect = RuntimeError("PayPal unavailable")
    schedule.last_payout_date = None
    db_session.commit()
    with pytest.raises(HTTPException) as exc_info:
        disburse_allowance_schedule(schedule.id, db_session, failing_service)
    assert exc_info.value.status_code == 502
    db_session.refresh(account)
    db_session.refresh(schedule)
    assert account.balance == 20.0
    assert schedule.last_payout_status == "FAILED"
    assert schedule.last_payout_date is None
    assert "PayPal unavailable" in schedule.last_payout_error

    pending_service = AsyncMock()
    pending_service.execute_payout.return_value = {
        "batch_id": "PAYOUT-PENDING",
        "status": "PENDING",
    }
    pending = disburse_allowance_schedule(schedule.id, db_session, pending_service)
    db_session.refresh(account)
    db_session.refresh(schedule)
    assert pending["status"] == "PENDING"
    assert account.balance == 20.0
    assert schedule.last_payout_status == "PENDING"
    assert schedule.last_payout_date is None

    schedule.last_payout_status = "PROCESSING"
    schedule.last_payout_attempt_at = datetime.utcnow()
    db_session.commit()
    already_processing = AsyncMock()
    with pytest.raises(HTTPException) as exc_info:
        disburse_allowance_schedule(schedule.id, db_session, already_processing)
    assert exc_info.value.status_code == 409
    already_processing.execute_payout.assert_not_awaited()


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

        # Now disbursement succeeds only after an explicit PayPal success response.
        confirmed_service = AsyncMock()
        confirmed_service.execute_payout.return_value = {
            "batch_id": "PAYOUT-CONFIRMED",
            "status": "SUCCESS",
        }
        app.dependency_overrides[allowance_api.get_paypal_service] = lambda: confirmed_service
        disburse_success = client.post(f"/api/allowances/{data['id']}/disburse")
        assert disburse_success.status_code == 200
        assert disburse_success.json()["status"] == "SUCCESS"
    finally:
        app.dependency_overrides.pop(allowance_api.get_paypal_service, None)
        app.dependency_overrides.pop(get_db, None)
