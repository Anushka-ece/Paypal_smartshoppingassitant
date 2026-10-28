from datetime import datetime

from app.workers.celery_worker import _next_due


def test_monthly_schedule_clamps_end_of_month():
    assert _next_due(datetime(2026, 1, 31, 12, 0), "monthly") == datetime(2026, 2, 28, 12, 0)


def test_monthly_schedule_rolls_december_to_january():
    assert _next_due(datetime(2026, 12, 31, 8, 30), "monthly") == datetime(2027, 1, 31, 8, 30)


def test_biweekly_schedule_advances_fourteen_days():
    assert _next_due(datetime(2026, 10, 27, 8, 30), "biweekly") == datetime(2026, 11, 10, 8, 30)
