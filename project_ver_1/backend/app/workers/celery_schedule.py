import logging
from datetime import datetime
from celery.schedules import crontab
from app.workers.celery_worker import celery_app
from app.database import SessionLocal
from app.models.allowance import AllowanceSchedule
from app.api.allowances import disburse_allowance_schedule, should_execute_allowance

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.disburse_recurring_allowances")
def disburse_recurring_allowances():
    """
    Celery Beat task running periodically to evaluate and disburse scheduled family allowances.
    Respects frozen status and enforces idempotent payout execution.
    """
    db = SessionLocal()
    processed_count = 0
    try:
        active_schedules = (
            db.query(AllowanceSchedule)
            .filter(
                AllowanceSchedule.is_active.is_(True),
                AllowanceSchedule.is_frozen.is_(False),
            )
            .all()
        )

        for sched in active_schedules:
            sched_dict = {
                "allowance_id": sched.id,
                "is_frozen": sched.is_frozen,
                "is_active": sched.is_active,
                "amount": sched.amount,
            }
            if should_execute_allowance(sched_dict):
                try:
                    disburse_allowance_schedule(sched.id, db=db)
                    processed_count += 1
                except Exception as e:
                    logger.error(f"Error disbursing allowance {sched.id}: {e}")

        logger.info(f"Disbursed {processed_count} recurring family allowances.")
    finally:
        db.close()

    return {"processed": processed_count}


# Schedule configuration for Celery Beat
celery_app.conf.beat_schedule = {
    # Run every Sunday at midnight for weekly allowances
    "weekly-allowance-payouts": {
        "task": "tasks.disburse_recurring_allowances",
        "schedule": crontab(day_of_week="sunday", hour=0, minute=0),
    },
    # Run on 1st of every month for monthly allowances
    "monthly-allowance-payouts": {
        "task": "tasks.disburse_recurring_allowances",
        "schedule": crontab(day_of_month="1", hour=0, minute=0),
    },
}
