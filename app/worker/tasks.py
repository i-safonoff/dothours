"""Celery tasks — thin wrappers that own a session around a function in jobs.py."""

import logging
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.worker import jobs
from app.worker.celery_app import celery_app

logger = logging.getLogger("dothours.tasks")


def _run(name: str, job: Callable[[Session], int]) -> int:
    with SessionLocal() as db:
        try:
            affected = job(db)
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Task %s failed", name)
            raise
    logger.info("Task %s affected %s rows", name, affected)
    return affected


@celery_app.task(name="app.worker.tasks.send_daily_reminders")
def send_daily_reminders() -> int:
    return _run("send_daily_reminders", jobs.send_daily_reminders)


@celery_app.task(name="app.worker.tasks.warn_streaks_at_risk")
def warn_streaks_at_risk() -> int:
    return _run("warn_streaks_at_risk", jobs.warn_streaks_at_risk)


@celery_app.task(name="app.worker.tasks.expire_overdue_paired_tasks")
def expire_overdue_paired_tasks() -> int:
    return _run("expire_overdue_paired_tasks", jobs.expire_overdue_paired_tasks)


@celery_app.task(name="app.worker.tasks.cleanup_read_notifications")
def cleanup_read_notifications() -> int:
    return _run("cleanup_read_notifications", jobs.cleanup_read_notifications)
