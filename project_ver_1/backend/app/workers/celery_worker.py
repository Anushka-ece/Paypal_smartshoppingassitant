import logging
from datetime import datetime
from typing import Optional, Dict, Any
from celery import Celery
from sqlalchemy.orm import Session

from app.config import REDIS_URL
from app.database import SessionLocal
from app.models.account import Account, AccountType
from app.models.transaction import Transaction, TransactionStatus
from app.models.ledger import LedgerEntry, LedgerStatus
from app.services.paypal_service import PayPalService
from app.security.crypto import decrypt_token

logger = logging.getLogger(__name__)

celery_app = Celery("tasks", broker=REDIS_URL, backend=REDIS_URL)
celery_app.conf.update(
    broker_connection_retry_on_startup=False,
    broker_connection_max_retries=1,
    broker_transport_options={"socket_timeout": 0.5, "socket_connect_timeout": 0.5},
)


@celery_app.task
def process_allowance_payouts():
    # Background worker for recurring allowance payouts
    pass


@celery_app.task(name="app.workers.celery_worker.sync_historical_transactions_task")
def sync_historical_transactions_task(account_id: int, db: Optional[Session] = None) -> Dict[str, Any]:
    """
    Background Celery task that ingests historical PayPal transactions for an account:
    1. Loads Account from DB and decrypts the PayPal OAuth token.
    2. Calls PayPalService.fetch_historical_transactions.
    3. Idempotently creates Transaction records.
    4. Writes double-entry LedgerEntry records (debit != credit, amount > 0).
    5. Returns summary of synced records.
    """
    should_close_db = False
    if db is None:
        db = SessionLocal()
        should_close_db = True

    try:
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            return {
                "status": "error",
                "account_id": account_id,
                "message": f"Account with ID {account_id} not found",
                "synced_count": 0,
                "transaction_ids": [],
            }

        # Decrypt PayPal token
        token = None
        if account.paypal_encrypted_token:
            try:
                token = decrypt_token(account.paypal_encrypted_token)
            except Exception:
                token = account.paypal_encrypted_token
        token = token or "mock_access_token"

        service = PayPalService()
        try:
            records = service.fetch_historical_transactions(access_token=token)
        except Exception as e:
            logger.error(f"Failed to fetch historical transactions for account {account_id}: {e}")
            return {
                "status": "error",
                "account_id": account_id,
                "message": f"Failed to fetch transactions from PayPal: {str(e)}",
                "synced_count": 0,
                "transaction_ids": [],
            }

        # Find or create counterparty account for double-entry bookkeeping
        counter_account = (
            db.query(Account)
            .filter(Account.family_id == account.family_id, Account.id != account.id)
            .first()
        )
        if not counter_account:
            counter_account = db.query(Account).filter(Account.id != account.id).first()

        if not counter_account:
            # Create a virtual counterparty clearing account
            counter_type = (
                AccountType.PARENT_WALLET.value
                if account.account_type != AccountType.PARENT_WALLET.value
                else AccountType.CHILD_VIRTUAL.value
            )
            counter_account = Account(
                user_id=account.user_id,
                family_id=account.family_id,
                account_type=counter_type,
                balance=0.0,
                currency=account.currency or "USD",
                is_active=True,
            )
            db.add(counter_account)
            db.commit()
            db.refresh(counter_account)

        synced_transactions = []
        for raw_tx in records:
            tx_data = service.parse_transaction_record(raw_tx)
            paypal_tx_id = tx_data.get("transaction_id")
            amount = tx_data.get("amount", 0.0)
            currency = tx_data.get("currency", "USD")
            merchant_name = tx_data.get("merchant_name")
            tx_status = tx_data.get("status", TransactionStatus.COMPLETED.value)
            description = tx_data.get("description")

            # Check for existing transaction (Idempotency)
            existing_tx = None
            if paypal_tx_id:
                existing_tx = (
                    db.query(Transaction)
                    .filter(Transaction.paypal_transaction_id == paypal_tx_id)
                    .first()
                )

            if existing_tx:
                # Already ingested, skip
                continue

            # Parse datetime
            initiation_str = tx_data.get("initiation_date")
            created_at_dt = None
            if initiation_str:
                try:
                    clean_iso = initiation_str.replace("Z", "+00:00")
                    created_at_dt = datetime.fromisoformat(clean_iso)
                except Exception:
                    created_at_dt = datetime.utcnow()
            else:
                created_at_dt = datetime.utcnow()

            # Create Transaction
            new_tx = Transaction(
                account_id=account.id,
                paypal_transaction_id=paypal_tx_id,
                amount=amount,
                currency=currency,
                status=tx_status,
                merchant_name=merchant_name,
                description=description,
                created_at=created_at_dt,
            )
            db.add(new_tx)
            db.commit()
            db.refresh(new_tx)

            # Create Double-Entry Ledger Entry
            if amount > 0 and counter_account and counter_account.id != account.id:
                existing_ledger = (
                    db.query(LedgerEntry)
                    .filter(LedgerEntry.transaction_id == new_tx.id)
                    .first()
                )
                if not existing_ledger:
                    # Expense: Debit Counter/Clearing account, Credit Account
                    ledger_entry = LedgerEntry(
                        debit_account_id=counter_account.id,
                        credit_account_id=account.id,
                        amount=amount,
                        currency=currency,
                        status=LedgerStatus.COMPLETED.value,
                        transaction_id=new_tx.id,
                        description=f"Historical sync: {merchant_name or 'Transaction'}",
                        created_at=created_at_dt,
                    )
                    db.add(ledger_entry)
                    db.commit()

            synced_transactions.append(new_tx.id)

        return {
            "status": "success",
            "account_id": account.id,
            "synced_count": len(synced_transactions),
            "transaction_ids": synced_transactions,
        }
    finally:
        if should_close_db:
            db.close()
