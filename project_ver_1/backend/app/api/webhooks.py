from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import PAYPAL_WEBHOOK_ID
from app.database import get_db
from app.models.models import BudgetEnvelope, Family, LedgerEntry, PolicyRule, Transaction, User, WebhookEvent
from app.services.gemini_service import classify_transaction, evaluate_policy
from app.services.paypal_service import verify_webhook_signature

router = APIRouter(prefix="/webhooks", tags=["PayPal Webhooks"])
SUPPORTED_EVENTS = {"PAYMENT.CAPTURE.COMPLETED", "PAYMENT.CAPTURE.REFUNDED", "PAYMENT.SALE.REFUNDED", "CUSTOMER.DISPUTE.RESOLVED"}


def _decimal_amount(value: object) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid amount in PayPal event.") from exc
    if not amount.is_finite() or amount <= 0:
        raise HTTPException(status_code=400, detail="PayPal event amount must be positive and finite.")
    return amount.quantize(Decimal("0.01"))


def _resolve_family_user(custom_id: object, db: Session) -> tuple[Family, User] | None:
    """Our checkout integration must set custom_id to `family_id:user_id`; never guess ownership."""
    if not isinstance(custom_id, str) or ":" not in custom_id:
        return None
    try:
        family_id, user_id = (int(value) for value in custom_id.split(":", maxsplit=1))
    except ValueError:
        return None
    user = db.query(User).filter(User.id == user_id, User.family_id == family_id).first()
    family = db.query(Family).filter(Family.id == family_id).first()
    if user is None or family is None:
        return None
    return family, user


def _add_capture_ledger_entries(db: Session, transaction: Transaction) -> None:
    amount = transaction.amount
    category = transaction.category or "Uncategorized"
    db.add_all([
        LedgerEntry(transaction_id=transaction.id, account_code=f"expense:{category}", debit=amount, credit=Decimal("0.00")),
        LedgerEntry(transaction_id=transaction.id, account_code="paypal:family-wallet", debit=Decimal("0.00"), credit=amount),
    ])


@router.post("/paypal")
async def handle_paypal_webhook(request: Request, db: Session = Depends(get_db)):
    """Verify and process PayPal's at-least-once webhook delivery."""
    if not PAYPAL_WEBHOOK_ID:
        raise HTTPException(status_code=503, detail="PAYPAL_WEBHOOK_ID is required before accepting PayPal webhooks.")
    body = await request.json()
    if not verify_webhook_signature(dict(request.headers), body, PAYPAL_WEBHOOK_ID):
        raise HTTPException(status_code=400, detail="PayPal webhook signature verification failed.")

    event_id = body.get("id")
    event_type = body.get("event_type")
    if not isinstance(event_id, str) or not event_id:
        raise HTTPException(status_code=400, detail="PayPal webhook event is missing its id.")
    existing = db.query(WebhookEvent).filter(WebhookEvent.paypal_event_id == event_id).first()
    if existing:
        return {"status": "duplicate", "event_id": event_id}

    event = WebhookEvent(paypal_event_id=event_id, event_type=str(event_type or "unknown"))
    db.add(event)
    try:
        db.flush()
        resource = body.get("resource") or {}

        if event_type == "PAYMENT.CAPTURE.COMPLETED":
            capture_id = resource.get("id")
            resolved = _resolve_family_user(resource.get("custom_id"), db)
            if not isinstance(capture_id, str) or not capture_id:
                raise HTTPException(status_code=400, detail="Capture event is missing the capture id.")
            if resolved is None:
                event.processing_status = "ignored_unmatched"
                db.commit()
                return {"status": "ignored", "reason": "Event has no valid application family/user custom_id."}
            family, user = resolved
            amount_data = resource.get("amount") or {}
            currency = amount_data.get("currency_code")
            if currency != "USD":
                event.processing_status = "ignored_currency"
                db.commit()
                return {"status": "ignored", "reason": "Version 1 ledger supports USD only."}
            amount = _decimal_amount(amount_data.get("value"))
            payee = resource.get("payee") or {}
            merchant_name = payee.get("email_address") or payee.get("merchant_id") or "Unknown merchant"
            classification = classify_transaction(str(merchant_name), str(resource.get("description") or ""), float(amount))
            rules = db.query(PolicyRule).filter(
                PolicyRule.family_id == family.id,
                PolicyRule.is_active.is_(True),
            ).all()
            policy_result = evaluate_policy(
                [rule.rule_text for rule in rules],
                {"merchant": merchant_name, "amount": str(amount), "category": classification.get("category"), "currency": currency},
            )
            transaction = Transaction(
                family_id=family.id,
                user_id=user.id,
                paypal_transaction_id=capture_id,
                merchant_name=str(merchant_name),
                clean_merchant_name=classification.get("clean_name"),
                amount=amount,
                currency=currency,
                category=classification.get("category"),
                subcategory=classification.get("subcategory"),
                status="flagged" if policy_result.get("is_flagged") else "completed",
                is_flagged=bool(policy_result.get("is_flagged")),
                risk_level=policy_result.get("risk_level", "LOW"),
                matched_rules=policy_result.get("matched_rules", []),
            )
            db.add(transaction)
            db.flush()
            _add_capture_ledger_entries(db, transaction)
            envelope = db.query(BudgetEnvelope).filter(
                BudgetEnvelope.family_id == family.id,
                BudgetEnvelope.user_id == user.id,
                BudgetEnvelope.category_name == transaction.category,
            ).first()
            if envelope:
                envelope.spent_amount = Decimal(envelope.spent_amount or 0) + amount

        elif event_type in {"PAYMENT.CAPTURE.REFUNDED", "PAYMENT.SALE.REFUNDED"}:
            resource_ids = (resource.get("supplementary_data") or {}).get("related_ids") or {}
            capture_id = resource_ids.get("capture_id") or resource.get("capture_id")
            if not capture_id:
                event.processing_status = "ignored_unmatched"
                db.commit()
                return {"status": "ignored", "reason": "Refund does not identify its original capture."}
            transaction = db.query(Transaction).filter(Transaction.paypal_transaction_id == capture_id).with_for_update().first()
            if transaction is None:
                event.processing_status = "ignored_unmatched"
                db.commit()
                return {"status": "ignored", "reason": "Original capture is not present in the application ledger."}
            refund_amount = _decimal_amount((resource.get("amount") or {}).get("value"))
            remaining = transaction.amount - Decimal(transaction.refunded_amount or 0)
            applied = min(refund_amount, remaining)
            if applied <= 0:
                event.processing_status = "ignored_duplicate_refund"
                db.commit()
                return {"status": "ignored", "reason": "Capture was already fully refunded."}
            transaction.refunded_amount = Decimal(transaction.refunded_amount or 0) + applied
            transaction.status = "refunded" if transaction.refunded_amount >= transaction.amount else "partially_refunded"
            # Reverse the original ledger effect with a new pair of immutable lines.
            db.add_all([
                LedgerEntry(transaction_id=transaction.id, account_code=f"expense:{transaction.category or 'Uncategorized'}", debit=Decimal("0.00"), credit=applied),
                LedgerEntry(transaction_id=transaction.id, account_code="paypal:family-wallet", debit=applied, credit=Decimal("0.00")),
            ])
            envelope = db.query(BudgetEnvelope).filter(
                BudgetEnvelope.family_id == transaction.family_id,
                BudgetEnvelope.user_id == transaction.user_id,
                BudgetEnvelope.category_name == transaction.category,
            ).first()
            if envelope:
                envelope.spent_amount = max(Decimal("0.00"), Decimal(envelope.spent_amount or 0) - applied)

        elif event_type == "CUSTOMER.DISPUTE.RESOLVED":
            dispute_id = resource.get("dispute_id") or resource.get("id")
            disputed_transactions = resource.get("disputed_transactions") or []
            seller_transaction_id = next(
                (item.get("seller_transaction_id") for item in disputed_transactions if item.get("seller_transaction_id")),
                None,
            )
            transaction = db.query(Transaction).filter(
                Transaction.paypal_transaction_id == seller_transaction_id,
            ).with_for_update().first() if seller_transaction_id else None
            if transaction is None:
                event.processing_status = "ignored_unmatched"
                db.commit()
                return {"status": "ignored", "reason": "Dispute event does not map to a known application transaction."}
            transaction.dispute_id = str(dispute_id) if dispute_id else None
            transaction.dispute_status = str(resource.get("status", "RESOLVED"))
            transaction.status = "dispute_resolved"

        elif event_type not in SUPPORTED_EVENTS:
            event.processing_status = "ignored_unsupported"
            db.commit()
            return {"status": "ignored", "event_type": event_type}

        event.processing_status = "processed"
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"status": "duplicate", "event_id": event_id}
    except Exception:
        db.rollback()
        raise

    return {"status": "processed", "event_id": event_id, "event_type": event_type}
