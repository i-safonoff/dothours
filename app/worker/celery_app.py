"""Celery app and beat schedule.

The hourly cadence of the two nudges is deliberate: each run picks the users
for whom it is currently the right *local* hour, so one timezone-correct
notification per user per day without a per-user schedule.
"""

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "dothours",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.worker.tasks"],
)

celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_time_limit=300,
    task_soft_time_limit=240,
    worker_max_tasks_per_child=200,
    timezone="UTC",
    beat_schedule={
        "daily-reminders": {
            "task": "app.worker.tasks.send_daily_reminders",
            "schedule": crontab(minute=0),
        },
        "streak-warnings": {
            "task": "app.worker.tasks.warn_streaks_at_risk",
            "schedule": crontab(minute=5),
        },
        "expire-paired-tasks": {
            "task": "app.worker.tasks.expire_overdue_paired_tasks",
            "schedule": crontab(minute=15),
        },
        "cleanup-notifications": {
            "task": "app.worker.tasks.cleanup_read_notifications",
            "schedule": crontab(hour=3, minute=30, day_of_week=1),
        },
    },
)
