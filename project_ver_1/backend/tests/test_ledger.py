import pytest
from app.database import get_db, init_timescaledb, Base
from app.models.user import User, UserRole
from app.models.family import Family
from app.models.invite import FamilyInvite
from app.models.account import Account, AccountType
from app.models.transaction import Transaction, TransactionStatus
from app.models.ledger import LedgerEntry, LedgerStatus


def test_ledger_double_entry_balance():
    entry = LedgerEntry(
        debit_account_id=1,
        credit_account_id=2,
        amount=25.00,
        currency="USD",
        status="COMPLETED"
    )
    assert entry.debit_account_id != entry.credit_account_id
    assert entry.amount > 0
    assert entry.currency == "USD"


def test_ledger_double_entry_validation():
    # Identical debit and credit account IDs must be rejected
    with pytest.raises(ValueError, match="distinct"):
        LedgerEntry(
            debit_account_id=1,
            credit_account_id=1,
            amount=50.00
        )

    # Non-positive amounts must be rejected
    with pytest.raises(ValueError, match="greater than zero"):
        LedgerEntry(
            debit_account_id=1,
            credit_account_id=2,
            amount=0.00
        )

    with pytest.raises(ValueError, match="greater than zero"):
        LedgerEntry(
            debit_account_id=1,
            credit_account_id=2,
            amount=-10.00
        )


def test_ledger_default_values():
    entry = LedgerEntry(
        debit_account_id=10,
        credit_account_id=20,
        amount=15.50
    )
    assert entry.currency == "USD"
    assert entry.status == LedgerStatus.COMPLETED.value
    assert entry.created_at is not None


def test_models_instantiation():
    user = User(
        email="parent@paypal.example.com",
        name="Jane Parent",
        role=UserRole.PARENT.value,
        coppa_consent_status="APPROVED"
    )
    assert user.email == "parent@paypal.example.com"
    assert user.role == "PARENT"

    family = Family(name="Doe Family", created_by_user_id=1)
    assert family.name == "Doe Family"

    invite = FamilyInvite(
        family_id=1,
        invited_by_id=1,
        email="coparent@paypal.example.com",
        role=UserRole.CO_PARENT.value,
        invite_token="token_xyz123"
    )
    assert invite.role == "CO_PARENT"
    assert invite.is_accepted is False

    account = Account(
        user_id=1,
        family_id=1,
        account_type=AccountType.PARENT_WALLET.value,
        balance=100.0,
        currency="USD"
    )
    assert account.account_type == "PARENT_WALLET"
    assert account.balance == 100.0

    tx = Transaction(
        account_id=1,
        paypal_transaction_id="TX9988",
        amount=25.0,
        status=TransactionStatus.COMPLETED.value,
        merchant_name="Steam Games"
    )
    assert tx.status == "COMPLETED"
    assert tx.merchant_name == "Steam Games"


def test_database_init_timescaledb_graceful():
    # Must run without raising uncaught exceptions in environments without timescaledb
    init_timescaledb()
