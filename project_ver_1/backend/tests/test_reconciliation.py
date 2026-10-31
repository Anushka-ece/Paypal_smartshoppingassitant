import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models.family import Family
from app.models.user import User, UserRole
from app.models.account import Account, AccountType
from app.models.transaction import Transaction, TransactionStatus
from app.models.budget import BudgetEnvelope
from app.api.budgets import apply_refund_to_envelope, reconcile_refund

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
            BudgetEnvelope.__table__,
        ],
    )

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        test_engine.dispose()


def test_full_refund_envelope_balance_restoration():
    envelope = {"name": "Gaming", "allocated": 50.00, "spent": 40.00}
    updated = apply_refund_to_envelope(envelope, refund_amount=40.00)
    assert updated["spent"] == 0.00
    assert updated["remaining"] == 50.00


def test_partial_refund_envelope_balance():
    envelope = {"name": "Gaming", "allocated": 50.00, "spent": 40.00}
    updated = apply_refund_to_envelope(envelope, refund_amount=15.00)
    assert updated["spent"] == 25.00
    assert updated["remaining"] == 25.00


def test_refund_reconciliation_full(db_session):
    family = Family(name="Budget Family")
    db_session.add(family)
    db_session.commit()

    user = User(name="Alex Parent", email="alex@example.com", role=UserRole.PARENT.value, family_id=family.id)
    db_session.add(user)
    db_session.commit()

    account = Account(user_id=user.id, family_id=family.id, balance=200.0)
    db_session.add(account)
    db_session.commit()

    # Create envelope
    envelope = BudgetEnvelope(
        family_id=family.id,
        name="Gaming",
        allocated_amount=100.00,
        current_spent=50.00,
    )
    db_session.add(envelope)

    # Create original transaction
    tx = Transaction(
        account_id=account.id,
        paypal_transaction_id="TX-CAPTURE-999",
        amount=50.00,
        merchant_name="Steam",
        category="Gaming",
        status=TransactionStatus.COMPLETED.value,
    )
    db_session.add(tx)
    db_session.commit()

    refund_payload = {
        "id": "REFUND-111",
        "parent_payment_id": "TX-CAPTURE-999",
        "amount": {"value": "50.00", "currency_code": "USD"},
    }

    result = reconcile_refund(refund_payload=refund_payload, db=db_session)
    assert result["success"] is True
    assert result["transaction_status"] == TransactionStatus.REFUNDED.value

    db_session.refresh(tx)
    assert tx.status == TransactionStatus.REFUNDED.value
    assert tx.refund_id == "REFUND-111"

    db_session.refresh(envelope)
    assert envelope.current_spent == 0.00


def test_refund_reconciliation_partial(db_session):
    family = Family(name="Partial Family")
    db_session.add(family)
    db_session.commit()

    user = User(name="Sam Parent", email="sam@example.com", role=UserRole.PARENT.value, family_id=family.id)
    db_session.add(user)
    db_session.commit()

    account = Account(user_id=user.id, family_id=family.id, balance=200.0)
    db_session.add(account)
    db_session.commit()

    envelope = BudgetEnvelope(
        family_id=family.id,
        name="Electronics",
        allocated_amount=200.00,
        current_spent=150.00,
    )
    db_session.add(envelope)

    tx = Transaction(
        account_id=account.id,
        paypal_transaction_id="TX-CAPTURE-PARTIAL",
        amount=150.00,
        merchant_name="Apple Store",
        category="Electronics",
        status=TransactionStatus.COMPLETED.value,
    )
    db_session.add(tx)
    db_session.commit()

    # Partial refund of $50 out of $150
    refund_payload = {
        "id": "REFUND-PART-222",
        "parent_payment_id": "TX-CAPTURE-PARTIAL",
        "amount": {"value": "50.00", "currency_code": "USD"},
    }

    result = reconcile_refund(refund_payload=refund_payload, db=db_session)
    assert result["success"] is True
    assert result["transaction_status"] == TransactionStatus.PARTIALLY_REFUNDED.value

    db_session.refresh(tx)
    assert tx.status == TransactionStatus.PARTIALLY_REFUNDED.value

    db_session.refresh(envelope)
    assert envelope.current_spent == 100.00


def test_budget_envelope_api_endpoints(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        family = Family(name="Envelope Family")
        db_session.add(family)
        db_session.commit()

        # Create envelope
        create_resp = client.post(
            "/api/budgets/envelopes",
            json={
                "family_id": family.id,
                "name": "Food & Dining",
                "allocated_amount": 150.0,
            },
        )
        assert create_resp.status_code == 200
        env_data = create_resp.json()
        assert env_data["name"] == "Food & Dining"
        assert env_data["allocated_amount"] == 150.0
        assert env_data["current_spent"] == 0.0

        # List envelopes
        list_resp = client.get(f"/api/budgets/envelopes?family_id={family.id}")
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 1

        # Update envelope
        update_resp = client.put(
            f"/api/budgets/envelopes/{env_data['id']}",
            json={"allocated_amount": 180.0},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["allocated_amount"] == 180.0

        # Delete envelope
        del_resp = client.delete(f"/api/budgets/envelopes/{env_data['id']}")
        assert del_resp.status_code == 200
    finally:
        app.dependency_overrides.pop(get_db, None)
