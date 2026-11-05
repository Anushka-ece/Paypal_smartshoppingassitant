import logging
import asyncio
import concurrent.futures
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from celery import Celery
import httpx
from sqlalchemy.orm import Session

from app.config import REDIS_URL
from app.database import SessionLocal
from app.models.account import Account, AccountType
from app.models.transaction import Transaction, TransactionStatus
from app.models.ledger import LedgerEntry, LedgerStatus
from app.services.paypal_service import PayPalService
from app.security.crypto import decrypt_token
from app.security.crypto import encrypt_token

logger = logging.getLogger(__name__)


def _run_async(coroutine):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coroutine).result()


def _refresh_account_access_token(account: Account, db: Session, service: PayPalService) -> str:
    if not account.paypal_encrypted_refresh_token:
        raise ValueError("PayPal access token expired and no refresh token is available; reconnect the account.")
    try:
        refresh_token = decrypt_token(account.paypal_encrypted_refresh_token)
    except ValueError as exc:
        raise ValueError("Stored PayPal refresh token is invalid; reconnect the account.") from exc

    refreshed = _run_async(service.refresh_access_token(refresh_token))
    access_token = refreshed.get("access_token")
    try:
        expires_in = int(refreshed["expires_in"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("PayPal returned an invalid refreshed token lifetime.") from exc
    if not isinstance(access_token, str) or not access_token or expires_in <= 0:
        raise ValueError("PayPal returned an invalid refreshed access token.")

    rotated_refresh_token = refreshed.get("refresh_token")
    if rotated_refresh_token is not None:
        if not isinstance(rotated_refresh_token, str) or not rotated_refresh_token:
            raise ValueError("PayPal returned an invalid rotated refresh token.")
        account.paypal_encrypted_refresh_token = encrypt_token(rotated_refresh_token)
    account.paypal_encrypted_token = encrypt_token(access_token)
    account.paypal_access_token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    db.commit()
    return access_token


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
        account = db.query(Account).filter(Account.id == account_id).with_for_update().first()
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
            except ValueError:
                logger.error("Stored PayPal access token cannot be decrypted for account %s", account_id)
                return {
                    "status": "error",
                    "account_id": account_id,
                    "message": "Stored PayPal access token is unavailable. Reconnect the PayPal account.",
                    "synced_count": 0,
                    "transaction_ids": [],
                }
        if not token:
            return {
                "status": "error",
                "account_id": account_id,
                "message": "PayPal account has no stored access or refresh token.",
                "synced_count": 0,
                "transaction_ids": [],
            }

        service = PayPalService()
        expires_at = account.paypal_access_token_expires_at
        if expires_at is not None:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= datetime.now(timezone.utc) + timedelta(seconds=60):
                try:
                    token = _refresh_account_access_token(account, db, service)
                except Exception:
                    logger.exception("PayPal access-token refresh failed for account %s", account_id)
                    return {
                        "status": "error",
                        "account_id": account_id,
                        "message": "PayPal access token could not be refreshed. Reconnect the PayPal account.",
                        "synced_count": 0,
                        "transaction_ids": [],
                    }
        try:
            records = service.fetch_historical_transactions(access_token=token)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 401 or not account.paypal_encrypted_refresh_token:
                logger.error("PayPal transaction history request failed for account %s", account_id)
                return {
                    "status": "error",
                    "account_id": account_id,
                    "message": "PayPal transaction history could not be retrieved.",
                    "synced_count": 0,
                    "transaction_ids": [],
                }
            try:
                token = _refresh_account_access_token(account, db, service)
                records = service.fetch_historical_transactions(access_token=token)
            except Exception:
                logger.exception("PayPal access-token refresh or retry failed for account %s", account_id)
                return {
                    "status": "error",
                    "account_id": account_id,
                    "message": "PayPal access token could not be refreshed. Reconnect the PayPal account.",
                    "synced_count": 0,
                    "transaction_ids": [],
                }
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
                family_id=account.family_id,
                user_id=account.user_id,
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
