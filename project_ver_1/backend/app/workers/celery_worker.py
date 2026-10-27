from celery import Celery
from app.config import REDIS_URL

celery_app = Celery("tasks", broker=REDIS_URL, backend=REDIS_URL)

@celery_app.task
def process_allowance_payouts():
    # Background worker for recurring allowance payouts
    pass
