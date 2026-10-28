import calendar
from datetime import datetime, timedelta
from decimal import Decimal

from celery import Celery
from celery.schedules import crontab
from sqlalchemy.exc import IntegrityError

from app.config import REDIS_URL
from app.database import SessionLocal
from app.models.models import AllowancePayout, AllowanceSchedule
from app.services.paypal_service import execute_payout

celery_app = Celery("tasks", broker=REDIS_URL, backend=REDIS_URL)
celery_app.conf.beat_schedule = {
    "process-due-allowance-payouts-every-minute": {
        "task": "app.workers.celery_worker.process_allowance_payouts",
        "schedule": crontab(minute="*/1"),
    },
}
celery_app.conf.timezone = "UTC"


def _next_due(current: datetime, frequency: str) -> datetime:
    if frequency == "weekly":
        return current + timedelta(days=7)
    if frequency == "biweekly":
        return current + timedelta(days=14)
    if frequency == "monthly":
        year, month = current.year, current.month + 1
        if month == 13:
            year, month = year + 1, 1
        day = min(current.day, calendar.monthrange(year, month)[1])
        return current.replace(year=year, month=month, day=day)
    raise ValueError(f"Unsupported allowance frequency: {frequency}")


@celery_app.task(name="app.workers.celery_worker.process_allowance_payouts")
def process_allowance_payouts() -> dict[str, int]:
    """Submit due family allowance transfers; PayPal request IDs protect retries from duplicates."""
    submitted = 0
    failed = 0
    db = SessionLocal()
    try:
        due_schedules = (
            db.query(AllowanceSchedule)
            .filter(AllowanceSchedule.active.is_(True), AllowanceSchedule.next_run_at <= datetime.utcnow())
            .with_for_update(skip_locked=True)
            .limit(50)
            .all()
        )
        for schedule in due_schedules:
            scheduled_for = schedule.next_run_at
            request_id = f"allowance-{schedule.id}-{scheduled_for.strftime('%Y%m%dT%H%M%S')}"
            attempt = db.query(AllowancePayout).filter(AllowancePayout.idempotency_key == request_id).first()
            if attempt is None:
                attempt = AllowancePayout(
                    schedule_id=schedule.id,
                    idempotency_key=request_id,
                    scheduled_for=scheduled_for,
                    status="submitting",
                )
                db.add(attempt)
                schedule.last_payout_request_id = request_id
                db.commit()
            elif attempt.status == "submitted":
                schedule.next_run_at = _next_due(scheduled_for, schedule.frequency)
                db.commit()
                continue
            else:
                attempt.status = "submitting"
                attempt.last_error = None
                db.commit()

            try:
                result = execute_payout(
                    recipient_email=schedule.recipient_email,
                    amount=Decimal(schedule.amount),
                    currency=schedule.currency,
                    idempotency_key=request_id,
                )
                attempt.status = "submitted"
                attempt.paypal_batch_id = result.get("batch_header", {}).get("payout_batch_id")
                attempt.response_json = result
                schedule.next_run_at = _next_due(scheduled_for, schedule.frequency)
                db.commit()
                submitted += 1
            except Exception as exc:
                attempt.status = "failed"
                attempt.last_error = str(exc)[:1000]
                db.commit()
                failed += 1
    finally:
        db.close()
    return {"submitted": submitted, "failed": failed}
