import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import redis

from app.database import get_db
from app.config import REDIS_URL
from app.models.transaction import Transaction, TransactionStatus
from app.models.account import Account
from app.models.purchase_request import PurchaseRequest, PurchaseRequestStatus
from app.models.webhook_event import ProcessedWebhookEvent
from app.services.paypal_service import PayPalService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["PayPal Webhooks"])

REQUIRED_HEADERS = [
    "paypal-auth-algo",
    "paypal-cert-url",
    "paypal-transmission-id",
    "paypal-transmission-sig",
    "paypal-transmission-time",
]

_redis_client: Optional[redis.Redis] = None
_redis_available: bool = True


def get_redis_client() -> Optional[redis.Redis]:
    global _redis_client, _redis_available
    if not _redis_available:
        return None
    if _redis_client is None and REDIS_URL:
        try:
            client = redis.Redis.from_url(
                REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=0.2,
                socket_timeout=0.2,
                retry_on_timeout=False,
            )
            client.ping()
            _redis_client = client
        except Exception:
            _redis_available = False
            _redis_client = None
    return _redis_client



def get_paypal_service() -> PayPalService:
    return PayPalService()


def is_event_already_processed(event_id: str, db: Optional[Session] = None) -> bool:
    """Checks the persistent event record; Redis is not authoritative for deduplication."""
    if db is not None:
        event = (
            db.query(ProcessedWebhookEvent)
            .filter(ProcessedWebhookEvent.event_id == event_id)
            .first()
        )
        return bool(event and event.status != "FAILED")
    return False


def claim_webhook_event(
    event_id: str,
    event_type: str,
    resource_type: Optional[str],
    resource_id: Optional[str],
    db: Session,
) -> bool:
    """Atomically claims an event using its unique database key before handling it."""
    event = ProcessedWebhookEvent(
        event_id=event_id,
        event_type=event_type,
        resource_type=resource_type,
        resource_id=resource_id,
        status="PROCESSING",
    )
    db.add(event)
    try:
        db.commit()
        return True
    except IntegrityError:
        db.rollback()

    existing = (
        db.query(ProcessedWebhookEvent)
        .filter(ProcessedWebhookEvent.event_id == event_id)
        .first()
    )
    if existing is None:
        raise RuntimeError(f"Unable to claim PayPal webhook event {event_id}.")

    stale_before = datetime.utcnow() - timedelta(minutes=5)
    reclaimable = (
        (ProcessedWebhookEvent.status == "FAILED")
        | (
            (ProcessedWebhookEvent.status == "PROCESSING")
            & (ProcessedWebhookEvent.created_at < stale_before)
        )
    )
    updated = (
        db.query(ProcessedWebhookEvent)
        .filter(
            ProcessedWebhookEvent.id == existing.id,
            reclaimable,
        )
        .update(
            {
                ProcessedWebhookEvent.status: "PROCESSING",
                ProcessedWebhookEvent.created_at: datetime.utcnow(),
                ProcessedWebhookEvent.event_type: event_type,
                ProcessedWebhookEvent.resource_type: resource_type,
                ProcessedWebhookEvent.resource_id: resource_id,
            },
            synchronize_session=False,
        )
    )
    db.commit()
    return updated == 1


def record_processed_event(
    event_id: str,
    event_type: str,
    status: str = "PROCESSED",
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    summary: Optional[str] = None,
    db: Optional[Session] = None,
) -> None:
    """Persists the final processing state for a previously claimed event."""
    if db is None:
        raise RuntimeError("A database session is required to persist PayPal webhook events.")
    entry = (
        db.query(ProcessedWebhookEvent)
        .filter(ProcessedWebhookEvent.event_id == event_id)
        .first()
    )
    if entry is None:
        entry = ProcessedWebhookEvent(event_id=event_id, event_type=event_type)
        db.add(entry)
    entry.event_type = event_type
    entry.resource_type = resource_type
    entry.resource_id = resource_id
    entry.status = status
    entry.summary = summary
    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to persist PayPal webhook event %s", event_id)
        raise


def handle_capture_completed(
    resource: Dict[str, Any],
    event: Dict[str, Any],
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """Handles PAYMENT.CAPTURE.COMPLETED events and records transactions."""
    capture_id = resource.get("id")
    amount_info = resource.get("amount", {})
    amount = float(amount_info.get("value", 0.0))
    currency = amount_info.get("currency_code", "USD")
    parent_payment = resource.get("parent_payment")
    merchant_name = (
        resource.get("seller_receivable_breakdown", {}).get("merchant_name")
        or resource.get("payee", {}).get("email_address")
        or "PayPal Merchant"
    )
    summary = event.get("summary") or "Payment capture completed"

    tx = None
    purchase_request = None
    if db is not None:
        # Find matching account
        account = None
        custom_id = resource.get("custom_id")
        if isinstance(custom_id, str) and custom_id.startswith("purchase-request-"):
            request_id = custom_id.removeprefix("purchase-request-")
            if request_id.isdigit():
                purchase_request = (
                    db.query(PurchaseRequest)
                    .filter_by(id=int(request_id))
                    .first()
                )
                if purchase_request:
                    account = (
                        db.query(Account)
                        .filter_by(
                            user_id=purchase_request.child_id,
                            family_id=purchase_request.family_id,
                        )
                        .first()
                    )
        elif custom_id and str(custom_id).isdigit():
            account = db.query(Account).filter_by(id=int(custom_id)).first()

        if not account:
            payee_id = resource.get("payee", {}).get("merchant_id")
            if payee_id:
                account = db.query(Account).filter_by(paypal_account_id=payee_id).first()

        if not account:
            account = db.query(Account).first()

        # Check existing transaction
        if capture_id:
            tx = db.query(Transaction).filter_by(paypal_transaction_id=capture_id).first()

        if not tx and account:
            tx = Transaction(
                account_id=account.id,
                family_id=account.family_id,
                user_id=account.user_id,
                paypal_transaction_id=capture_id,
                amount=amount,
                currency=currency,
                status=TransactionStatus.COMPLETED.value,
                merchant_name=merchant_name,
                parent_payment_id=parent_payment,
                description=summary,
            )
            db.add(tx)
            db.commit()
            db.refresh(tx)

        supplementary_data = resource.get("supplementary_data")
        if not isinstance(supplementary_data, dict):
            supplementary_data = {}
        related_ids = supplementary_data.get("related_ids", {})
        order_id = related_ids.get("order_id") if isinstance(related_ids, dict) else None
        if not purchase_request and order_id:
            purchase_request = (
                db.query(PurchaseRequest)
                .filter_by(paypal_order_id=order_id)
                .first()
            )
        if purchase_request:
            paypal_status = resource.get("status") or "COMPLETED"
            if paypal_status == "COMPLETED":
                purchase_request.paypal_capture_id = capture_id
                purchase_request.paypal_payment_status = paypal_status
                purchase_request.status = PurchaseRequestStatus.EXECUTED.value
                db.commit()

    return {
        "action": "capture_processed",
        "capture_id": capture_id,
        "amount": amount,
        "currency": currency,
        "transaction_id": tx.id if tx else None,
        "purchase_request_id": purchase_request.id if purchase_request else None,
    }


def handle_refund(
    resource: Dict[str, Any],
    event: Dict[str, Any],
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """Handles PAYMENT.CAPTURE.REFUNDED and PAYMENT.SALE.REFUNDED events."""
    refund_id = resource.get("id")
    amount_info = resource.get("amount", {})
    refund_amount = float(amount_info.get("value", 0.0))
    parent_id = (
        resource.get("parent_payment")
        or resource.get("capture_id")
        or resource.get("sale_id")
    )

    tx = None
    new_status = "REFUNDED"
    if db is not None:
        from app.api.budgets import reconcile_refund
        if refund_id and parent_id:
            tx = (
                db.query(Transaction)
                .filter(
                    (Transaction.paypal_transaction_id == parent_id)
                    | (Transaction.parent_payment_id == parent_id)
                )
                .first()
            )
            if tx and tx.refund_id == refund_id:
                return {
                    "action": "refund_already_reconciled",
                    "refund_id": refund_id,
                    "transaction_id": tx.id,
                    "status": tx.status,
                }
        # Ensure parent_payment_id is populated on resource if present under alias
        if not resource.get("parent_payment_id") and parent_id:
            resource["parent_payment_id"] = parent_id
        reconcile_res = reconcile_refund(resource, db=db)
        if parent_id:
            tx = (
                db.query(Transaction)
                .filter(
                    (Transaction.paypal_transaction_id == parent_id)
                    | (Transaction.parent_payment_id == parent_id)
                )
                .first()
            )
            if tx:
                new_status = tx.status

    return {
        "action": "refund_reconciled",
        "refund_id": refund_id,
        "transaction_id": tx.id if tx else None,
        "status": new_status,
    }


def handle_dispute_resolved(
    resource: Dict[str, Any],
    event: Dict[str, Any],
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """Handles CUSTOMER.DISPUTE.RESOLVED events."""
    dispute_id = resource.get("dispute_id")
    disputed_transactions = resource.get("disputed_transactions", [])
    outcome = resource.get("dispute_outcome", {}).get("outcome_code", "RESOLVED")

    updated_tx_ids = []
    if db is not None:
        for item in disputed_transactions:
            seller_tx_id = item.get("seller_transaction_id")
            if seller_tx_id:
                tx = (
                    db.query(Transaction)
                    .filter_by(paypal_transaction_id=seller_tx_id)
                    .first()
                )
                if tx:
                    tx.status = TransactionStatus.DISPUTED.value
                    tx.is_flagged = True
                    tx.flagged_reason = f"Dispute {dispute_id} resolved: {outcome}"
                    db.commit()
                    updated_tx_ids.append(tx.id)

    return {
        "action": "dispute_resolved",
        "dispute_id": dispute_id,
        "status": "RESOLVED",
        "updated_transactions": updated_tx_ids,
    }


def route_webhook_event(
    event: Dict[str, Any],
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """Routes supported PayPal webhook events to appropriate handlers."""
    event_type = event.get("event_type")
    resource = event.get("resource", {})

    if event_type == "PAYMENT.CAPTURE.COMPLETED":
        return handle_capture_completed(resource, event, db=db)
    elif event_type in ("PAYMENT.CAPTURE.REFUNDED", "PAYMENT.SALE.REFUNDED"):
        return handle_refund(resource, event, db=db)
    elif event_type == "CUSTOMER.DISPUTE.RESOLVED":
        return handle_dispute_resolved(resource, event, db=db)
    else:
        return {"action": "unhandled", "event_type": event_type}


@router.post("/paypal")
async def handle_paypal_webhook(
    request: Request,
    db: Session = Depends(get_db),
    service: PayPalService = Depends(get_paypal_service),
):
    body_bytes = await request.body()
    headers_lower = {str(k).lower(): str(v) for k, v in request.headers.items()}

    # 1. Header Validation
    missing_headers = [h for h in REQUIRED_HEADERS if not headers_lower.get(h)]
    if missing_headers:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required PayPal signature headers: {', '.join(missing_headers)}",
        )

    # 2. Signature Verification
    is_valid = await service.verify_webhook_signature(headers_lower, body_bytes)
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    # 3. Parse JSON Body
    try:
        payload = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_id = payload.get("id") or headers_lower.get("paypal-transmission-id")
    event_type = payload.get("event_type", "")
    resource_type = payload.get("resource_type")
    resource = payload.get("resource", {})
    resource_id = resource.get("id")

    if not event_id:
        raise HTTPException(status_code=400, detail="PayPal webhook event ID is missing.")

    # 4. Atomically claim the event before running payment side effects.
    if not claim_webhook_event(
        event_id=event_id,
        event_type=event_type,
        resource_type=resource_type,
        resource_id=resource_id,
        db=db,
    ):
        return {
            "status": "already_processed",
            "event_id": event_id,
            "message": "Duplicate event ignored",
        }

    # 5. Supported Event Filtering
    if not service.is_event_supported(event_type):
        record_processed_event(
            event_id=event_id,
            event_type=event_type,
            status="IGNORED",
            resource_type=resource_type,
            resource_id=resource_id,
            summary=payload.get("summary"),
            db=db,
        )
        return {
            "status": "ignored",
            "event_id": event_id,
            "message": f"Unsupported event type: {event_type}",
        }

    # 6. Route to Appropriate Handler
    try:
        result = route_webhook_event(payload, db=db)
    except Exception as exc:
        db.rollback()
        record_processed_event(
            event_id=event_id,
            event_type=event_type,
            status="FAILED",
            resource_type=resource_type,
            resource_id=resource_id,
            summary=payload.get("summary"),
            db=db,
        )
        logger.exception("PayPal webhook event %s failed during handling", event_id)
        raise HTTPException(status_code=500, detail="PayPal webhook event processing failed.") from exc

    # 7. Record as Processed
    record_processed_event(
        event_id=event_id,
        event_type=event_type,
        status="PROCESSED",
        resource_type=resource_type,
        resource_id=resource_id,
        summary=payload.get("summary"),
        db=db,
    )

    return {
        "status": "processed",
        "event_id": event_id,
        "event_type": event_type,
        "result": result,
    }
