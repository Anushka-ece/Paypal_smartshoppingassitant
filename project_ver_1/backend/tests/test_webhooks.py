from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.models import BudgetEnvelope, Family, LedgerEntry, Transaction, User, WebhookEvent

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def setup_function():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    family = Family(name="Test family")
    db.add(family)
    db.flush()
    user = User(family_id=family.id, email="parent@example.com", hashed_password="", role="parent", is_verified=True)
    db.add(user)
    db.commit()
    db.refresh(family)
    db.refresh(user)
    global TEST_FAMILY_ID, TEST_USER_ID
    TEST_FAMILY_ID, TEST_USER_ID = family.id, user.id
    db.close()


def test_invalid_webhook_signature_is_rejected(monkeypatch):
    monkeypatch.setattr("app.api.webhooks.PAYPAL_WEBHOOK_ID", "webhook-id")
    with patch("app.api.webhooks.verify_webhook_signature", return_value=False):
        response = client.post("/webhooks/paypal", json={"id": "evt", "event_type": "PAYMENT.CAPTURE.COMPLETED"})
    assert response.status_code == 400


def test_capture_is_idempotent_by_event_and_maps_no_guessing(monkeypatch):
    monkeypatch.setattr("app.api.webhooks.PAYPAL_WEBHOOK_ID", "webhook-id")
    monkeypatch.setattr("app.api.webhooks.verify_webhook_signature", lambda *_args: True)
    event = {"id": "evt-unmatched", "event_type": "PAYMENT.CAPTURE.COMPLETED", "resource": {"id": "cap-x", "amount": {"value": "12.00", "currency_code": "USD"}}}
    first = client.post("/webhooks/paypal", json=event)
    second = client.post("/webhooks/paypal", json=event)
    assert first.status_code == 200 and first.json()["status"] == "ignored"
    assert second.status_code == 200 and second.json()["status"] == "duplicate"
    db = TestingSessionLocal()
    assert db.query(Transaction).count() == 0
    assert db.query(WebhookEvent).count() == 1
    db.close()


def test_capture_records_balanced_ledger_and_refund_restores_envelope(monkeypatch):
    monkeypatch.setattr("app.api.webhooks.PAYPAL_WEBHOOK_ID", "webhook-id")
    monkeypatch.setattr("app.api.webhooks.verify_webhook_signature", lambda *_args: True)
    monkeypatch.setattr("app.api.webhooks.classify_transaction", lambda *_args: {"category": "Gaming", "subcategory": "Games", "clean_name": "Game Store"})
    monkeypatch.setattr("app.api.webhooks.evaluate_policy", lambda *_args: {"is_flagged": False, "risk_level": "LOW", "matched_rules": []})
    db = TestingSessionLocal()
    db.add(BudgetEnvelope(family_id=TEST_FAMILY_ID, user_id=TEST_USER_ID, category_name="Gaming", allocated_amount=100, spent_amount=0))
    db.commit()
    db.close()

    capture = {"id": "evt-capture", "event_type": "PAYMENT.CAPTURE.COMPLETED", "resource": {"id": "cap-1", "custom_id": f"{TEST_FAMILY_ID}:{TEST_USER_ID}", "description": "digital game", "amount": {"value": "40.00", "currency_code": "USD"}}}
    response = client.post("/webhooks/paypal", json=capture)
    assert response.status_code == 200
    db = TestingSessionLocal()
    transaction = db.query(Transaction).filter_by(paypal_transaction_id="cap-1").one()
    assert float(transaction.amount) == 40
    assert db.query(BudgetEnvelope).one().spent_amount == 40
    entries = db.query(LedgerEntry).filter_by(transaction_id=transaction.id).all()
    assert sum(float(line.debit) for line in entries) == sum(float(line.credit) for line in entries)
    db.close()

    refund = {"id": "evt-refund", "event_type": "PAYMENT.CAPTURE.REFUNDED", "resource": {"id": "refund-1", "supplementary_data": {"related_ids": {"capture_id": "cap-1"}}, "amount": {"value": "40.00", "currency_code": "USD"}}}
    response = client.post("/webhooks/paypal", json=refund)
    assert response.status_code == 200
    db = TestingSessionLocal()
    assert db.query(BudgetEnvelope).one().spent_amount == 0
    assert db.query(Transaction).filter_by(paypal_transaction_id="cap-1").one().status == "refunded"
    db.close()


def test_dispute_resolution_updates_mapped_transaction(monkeypatch):
    monkeypatch.setattr("app.api.webhooks.PAYPAL_WEBHOOK_ID", "webhook-id")
    monkeypatch.setattr("app.api.webhooks.verify_webhook_signature", lambda *_args: True)
    db = TestingSessionLocal()
    db.add(Transaction(
        family_id=TEST_FAMILY_ID,
        user_id=TEST_USER_ID,
        paypal_transaction_id="capture-disputed",
        merchant_name="Example store",
        amount=25,
        currency="USD",
        status="completed",
    ))
    db.commit()
    db.close()

    event = {"id": "evt-dispute-resolved", "event_type": "CUSTOMER.DISPUTE.RESOLVED", "resource": {
        "dispute_id": "PP-D-123",
        "status": "RESOLVED",
        "disputed_transactions": [{"seller_transaction_id": "capture-disputed"}],
    }}
    response = client.post("/webhooks/paypal", json=event)
    assert response.status_code == 200
    db = TestingSessionLocal()
    transaction = db.query(Transaction).filter_by(paypal_transaction_id="capture-disputed").one()
    assert transaction.status == "dispute_resolved"
    assert transaction.dispute_id == "PP-D-123"
    assert transaction.dispute_status == "RESOLVED"
    db.close()
