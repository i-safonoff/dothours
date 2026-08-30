"""Guards for the Celery wiring itself — a typo in a beat entry fails silently otherwise."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.worker import tasks
from app.worker.celery_app import celery_app
from tests.conftest import register_and_login


def test_every_beat_entry_points_at_a_registered_task() -> None:
    scheduled = {entry["task"] for entry in celery_app.conf.beat_schedule.values()}
    assert scheduled, "beat schedule is empty"
    assert scheduled <= set(celery_app.tasks)


def test_beat_covers_all_worker_jobs() -> None:
    scheduled = {entry["task"].rsplit(".", 1)[-1] for entry in celery_app.conf.beat_schedule.values()}
    assert scheduled == {
        "send_daily_reminders",
        "warn_streaks_at_risk",
        "expire_overdue_paired_tasks",
        "cleanup_read_notifications",
    }


def test_task_wrapper_commits_its_work(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    register_and_login(client, email="ann@example.com", name="Ann")

    # Пользователь в UTC — сдвигаем «час напоминания» на текущий, чтобы джоба сработала сейчас.
    monkeypatch.setattr(tasks.jobs, "REMINDER_LOCAL_HOUR", datetime.now(UTC).hour)
    monkeypatch.setattr(tasks, "SessionLocal", lambda: db_session)

    assert tasks.send_daily_reminders() == 1
    assert db_session.query(Notification).count() == 1


def test_task_wrapper_rolls_back_on_failure(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(db: Session) -> int:
        raise RuntimeError("job exploded")

    monkeypatch.setattr(tasks, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(tasks.jobs, "cleanup_read_notifications", boom)

    with pytest.raises(RuntimeError, match="job exploded"):
        tasks.cleanup_read_notifications()
