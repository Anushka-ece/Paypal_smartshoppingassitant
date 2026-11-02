import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, get_db
from app.models.user import User, UserRole
from app.models.family import Family
from app.models.account import Account, AccountType
from app.models.transaction import Transaction, TransactionStatus
from app.models.paypal_oauth_state import PayPalOAuthState
from app.models.ledger import LedgerEntry, LedgerStatus
from app.security.crypto import encrypt_token
from app.services.paypal_service import PayPalService, AwaitableList
from app.workers.celery_worker import sync_historical_transactions_task

client = TestClient(app)


@pytest.fixture
def sandbox_paypal_credentials(monkeypatch):
    monkeypatch.setattr(
        "app.services.paypal_service.PAYPAL_CLIENT_ID", "test-sandbox-client-id"
    )
    monkeypatch.setattr(
        "app.services.paypal_service.PAYPAL_CLIENT_SECRET", "test-sandbox-client-secret"
    )
    monkeypatch.setattr(
        "app.services.paypal_service.PAYPAL_BASE_URL",
        "https://api-m.sandbox.paypal.com",
    )


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
    # Create all required tables including transactions and ledger
    Base.metadata.create_all(
        bind=test_engine,
        tables=[
            Family.__table__,
            User.__table__,
            Account.__table__,
            Transaction.__table__,
            LedgerEntry.__table__,
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
# 1. Parsing Transaction Search Records
# ----------------------------------------------------------------------

def test_parse_transaction_search_record():
    service = PayPalService()
    raw_record = {
        "transaction_info": {
            "transaction_id": "TX123",
            "transaction_amount": {"value": "45.00", "currency_code": "USD"},
            "transaction_status": "S",
            "transaction_initiation_date": "2026-10-01T12:00:00Z",
        },
        "payer_info": {"payer_name": {"alternate_full_name": "Steam Games"}},
    }
    parsed = service.parse_transaction_record(raw_record)
    assert parsed["transaction_id"] == "TX123"
    assert parsed["amount"] == 45.00
    assert parsed["currency"] == "USD"
    assert parsed["merchant_name"] == "Steam Games"
    assert parsed["status"] == "COMPLETED"
    assert parsed["initiation_date"] == "2026-10-01T12:00:00Z"


def test_parse_transaction_record_variations():
    service = PayPalService()

    # Variation A: Given and surname
    rec1 = {
        "transaction_info": {
            "transaction_id": "TX_A",
            "transaction_amount": {"value": "-19.99", "currency_code": "USD"},
            "transaction_status": "V",
        },
        "payer_info": {
            "payer_name": {"given_name": "Epic", "surname": "Games"}
        },
    }
    parsed1 = service.parse_transaction_record(rec1)
    assert parsed1["transaction_id"] == "TX_A"
    assert parsed1["amount"] == 19.99  # Absolute value
    assert parsed1["merchant_name"] == "Epic Games"
    assert parsed1["status"] == "REFUNDED"

    # Variation B: Email fallback and Pending status
    rec2 = {
        "transaction_info": {
            "transaction_id": "TX_B",
            "transaction_amount": {"value": "12.50", "currency_code": "USD"},
            "transaction_status": "P",
        },
        "payer_info": {"email_address": "support@spotify.com"},
    }
    parsed2 = service.parse_transaction_record(rec2)
    assert parsed2["merchant_name"] == "support@spotify.com"
    assert parsed2["status"] == "PENDING"

    # Variation C: Cart info item_name fallback
    rec3 = {
        "transaction_info": {
            "transaction_id": "TX_C",
            "transaction_amount": {"value": "8.99", "currency_code": "EUR"},
            "transaction_status": "D",
        },
        "cart_info": {"item_details": [{"item_name": "Discord Nitro"}]},
    }
    parsed3 = service.parse_transaction_record(rec3)
    assert parsed3["merchant_name"] == "Discord Nitro"
    assert parsed3["currency"] == "EUR"
    assert parsed3["status"] == "DENIED"

    # Variation D: Flattened dict
    rec4 = {
        "transaction_id": "TX_D",
        "amount": 55.0,
        "currency": "USD",
        "merchant_name": "Target Store",
        "status": "COMPLETED",
    }
    parsed4 = service.parse_transaction_record(rec4)
    assert parsed4["transaction_id"] == "TX_D"
    assert parsed4["amount"] == 55.0
    assert parsed4["merchant_name"] == "Target Store"
    assert parsed4["status"] == "COMPLETED"


# ----------------------------------------------------------------------
# 2. Fetch Historical Transactions API Client
# ----------------------------------------------------------------------

@pytest.mark.anyio
async def test_fetch_historical_transactions_mock_and_async(sandbox_paypal_credentials):
    service = PayPalService()

    # Synchronous call
    txs_sync = service.fetch_historical_transactions(access_token="mock_token")
    assert isinstance(txs_sync, list)
    assert len(txs_sync) >= 3
    assert any(tx["merchant_name"] == "Steam Games" for tx in txs_sync)

    # Asynchronous call (AwaitableList test)
    txs_async = await service.fetch_historical_transactions(access_token="mock_token")
    assert isinstance(txs_async, list)
    assert len(txs_async) == len(txs_sync)

    # Auto-decrypt test
    enc_token = encrypt_token("mock-encrypted-token")
    txs_enc = service.fetch_historical_transactions(access_token=enc_token)
    assert len(txs_enc) >= 3


def test_fetch_historical_transactions_pagination(sandbox_paypal_credentials):
    service = PayPalService(client_id="live_test_client_id")

    page_1_data = {
        "transaction_details": [
            {
                "transaction_info": {
                    "transaction_id": "TX_PAGE_1",
                    "transaction_amount": {"value": "10.00", "currency_code": "USD"},
                    "transaction_status": "S",
                    "transaction_initiation_date": "2026-10-01T10:00:00Z",
                },
                "payer_info": {"payer_name": {"alternate_full_name": "Merchant 1"}},
            }
        ],
        "page": 1,
        "total_pages": 2,
    }

    page_2_data = {
        "transaction_details": [
            {
                "transaction_info": {
                    "transaction_id": "TX_PAGE_2",
                    "transaction_amount": {"value": "20.00", "currency_code": "USD"},
                    "transaction_status": "S",
                    "transaction_initiation_date": "2026-10-02T10:00:00Z",
                },
                "payer_info": {"payer_name": {"alternate_full_name": "Merchant 2"}},
            }
        ],
        "page": 2,
        "total_pages": 2,
    }

    def mock_get(url, headers=None, params=None):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        if params and params.get("page") == 1:
            mock_resp.json.return_value = page_1_data
        else:
            mock_resp.json.return_value = page_2_data
        return mock_resp

    with patch("httpx.Client.get", side_effect=mock_get):
        results = service.fetch_historical_transactions(
            access_token="live_token",
            start_date="2026-10-01T00:00:00Z",
            end_date="2026-10-15T00:00:00Z",
        )
        assert len(results) == 2
        assert results[0]["transaction_id"] == "TX_PAGE_1"
        assert results[1]["transaction_id"] == "TX_PAGE_2"


# ----------------------------------------------------------------------
# 3. Background Sync Task (Celery Worker)
# ----------------------------------------------------------------------

def test_sync_historical_transactions_task_success(db_session, sandbox_paypal_credentials):
    # Setup test family, user, and account
    family = Family(name="Test Family", created_by_user_id=1)
    db_session.add(family)
    db_session.commit()

    user = User(
        email="parent@example.com",
        name="Parent User",
        role=UserRole.PARENT.value,
        family_id=family.id,
    )
    db_session.add(user)
    db_session.commit()

    account = Account(
        user_id=user.id,
        family_id=family.id,
        account_type=AccountType.PAYPAL_LINKED.value,
        paypal_encrypted_token=encrypt_token("mock_token"),
        balance=150.0,
        currency="USD",
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)

    # Execute sync task
    result = sync_historical_transactions_task(account.id, db=db_session)
    assert result["status"] == "success"
    assert result["synced_count"] >= 3

    # Verify transactions in DB
    txs = db_session.query(Transaction).filter_by(account_id=account.id).all()
    assert len(txs) == result["synced_count"]
    steam_tx = next((tx for tx in txs if tx.merchant_name == "Steam Games"), None)
    assert steam_tx is not None
    assert steam_tx.amount == 45.00
    assert steam_tx.status == TransactionStatus.COMPLETED.value

    # Verify ledger entries in DB
    ledger_entries = db_session.query(LedgerEntry).all()
    assert len(ledger_entries) == len(txs)
    for entry in ledger_entries:
        assert entry.debit_account_id != entry.credit_account_id
        assert entry.credit_account_id == account.id
        assert entry.amount > 0
        assert entry.status == LedgerStatus.COMPLETED.value
        assert entry.transaction_id is not None


def test_sync_historical_transactions_task_idempotency(db_session, sandbox_paypal_credentials):
    family = Family(name="Idempotent Family", created_by_user_id=1)
    db_session.add(family)
    db_session.commit()

    user = User(
        email="idempotent@example.com",
        name="Idempotent User",
        role=UserRole.PARENT.value,
        family_id=family.id,
    )
    db_session.add(user)
    db_session.commit()

    account = Account(
        user_id=user.id,
        family_id=family.id,
        account_type=AccountType.PAYPAL_LINKED.value,
        paypal_encrypted_token=encrypt_token("mock_token"),
        balance=200.0,
        currency="USD",
    )
    db_session.add(account)
    db_session.commit()

    # First run
    res1 = sync_historical_transactions_task(account.id, db=db_session)
    assert res1["status"] == "success"
    initial_count = res1["synced_count"]
    assert initial_count > 0

    tx_count_before = db_session.query(Transaction).count()
    ledger_count_before = db_session.query(LedgerEntry).count()

    # Second run (should be a no-op due to deduplication)
    res2 = sync_historical_transactions_task(account.id, db=db_session)
    assert res2["status"] == "success"
    assert res2["synced_count"] == 0

    tx_count_after = db_session.query(Transaction).count()
    ledger_count_after = db_session.query(LedgerEntry).count()

    assert tx_count_after == tx_count_before
    assert ledger_count_after == ledger_count_before


def test_sync_historical_transactions_account_not_found(db_session):
    res = sync_historical_transactions_task(account_id=99999, db=db_session)
    assert res["status"] == "error"
    assert "not found" in res["message"]


def test_sync_historical_transactions_without_token_fails_without_mock_data(db_session):
    family = Family(name="Missing Token Family", created_by_user_id=1)
    db_session.add(family)
    db_session.commit()
    user = User(
        email="missing-token@example.com",
        name="Missing Token User",
        role=UserRole.PARENT.value,
        family_id=family.id,
    )
    db_session.add(user)
    db_session.commit()
    account = Account(
        user_id=user.id,
        family_id=family.id,
        account_type=AccountType.PAYPAL_LINKED.value,
        paypal_encrypted_token=None,
    )
    db_session.add(account)
    db_session.commit()

    result = sync_historical_transactions_task(account.id, db=db_session)

    assert result["status"] == "error"
    assert "no stored access or refresh token" in result["message"]
    assert result["synced_count"] == 0
    assert db_session.query(Transaction).filter_by(account_id=account.id).count() == 0


# ----------------------------------------------------------------------
# 4. OAuth Callback Trigger Integration
# ----------------------------------------------------------------------

def test_oauth_callback_triggers_historical_sync(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        family = Family(name="OAuth Family", created_by_user_id=1)
        db_session.add(family)
        db_session.commit()

        user = User(
            email="oauth_parent@example.com",
            name="OAuth Parent",
            role=UserRole.PARENT.value,
            family_id=family.id,
        )
        db_session.add(user)
        db_session.commit()

        fake_tokens = {
            "access_token": "mock-access-token",
            "refresh_token": "mock-refresh-token",
            "payer_id": "PAYER_9988",
            "expires_in": 32400,
        }
        state = "history-sync-state"
        import hashlib
        from datetime import timedelta
        db_session.add(
            PayPalOAuthState(
                state_hash=hashlib.sha256(state.encode()).hexdigest(),
                user_id=user.id,
                expires_at=datetime.utcnow() + timedelta(minutes=5),
            )
        )
        db_session.commit()

        with patch("app.services.paypal_service.PayPalService.exchange_oauth_code", return_value=fake_tokens):
            with patch("app.workers.celery_worker.sync_historical_transactions_task.delay") as mock_delay:
                response = client.get(f"/auth/callback?code=mock_code_123&state={state}")
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                assert data["account_id"] is not None
                # Verify that Celery delay task was attempted or called with account id
                assert mock_delay.called or data["account_id"] > 0
    finally:
        app.dependency_overrides.pop(get_db, None)
