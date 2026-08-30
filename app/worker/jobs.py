"""The actual work behind the Celery tasks, as plain functions over a Session.

Kept free of Celery on purpose: the tests call these directly, and a task in
app/worker/tasks.py is a three-line wrapper that opens a session. Nothing here
commits — the caller owns the transaction.
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timezones import local_now
from app.models.city import DailyProgress
from app.models.enums import NotificationKind, PairedTaskStatus
from app.models.notification import Notification
from app.models.paired_task import PairedTask, PairedTaskParticipant
from app.models.user import User
from app.services.notifications import already_notified_since, create_notification

logger = logging.getLogger("dothours.jobs")

REMINDER_LOCAL_HOUR = 19
STREAK_WARNING_LOCAL_HOUR = 21
READ_NOTIFICATION_TTL_DAYS = 30


def _progress_for(db: Session, user: User, on_date) -> DailyProgress | None:
    return db.scalar(select(DailyProgress).where(DailyProgress.user_id == user.id, DailyProgress.date == on_date))


def send_daily_reminders(db: Session, now: datetime | None = None) -> int:
    """Nudge users who have not met today's goal, at 19:00 *their* time.

    Meant to run hourly: each run picks exactly the users for whom it is now
    the reminder hour, so one nudge per user per day regardless of timezone.
    """
    now = now or datetime.now(UTC)
    sent = 0

    for user in db.scalars(select(User)).all():
        user_now = local_now(user.timezone, now)
        if user_now.hour != REMINDER_LOCAL_HOUR:
            continue

        progress = _progress_for(db, user, user_now.date())
        if progress is not None and progress.goal_met:
            continue
        if already_notified_since(db, user.id, NotificationKind.daily_reminder, now - timedelta(hours=12)):
            continue

        tracked = progress.total_minutes if progress else 0
        left = max(user.daily_goal_minutes - tracked, 0)
        create_notification(
            db,
            user.id,
            NotificationKind.daily_reminder,
            title="Город ждёт стройку",
            body=f"Сегодня натрекано {tracked} мин. До дневной цели осталось {left} мин.",
            payload={"today_minutes": tracked, "goal_minutes": user.daily_goal_minutes},
        )
        sent += 1

    return sent


def warn_streaks_at_risk(db: Session, now: datetime | None = None) -> int:
    """Late-evening warning for users who closed the goal yesterday but not today."""
    now = now or datetime.now(UTC)
    sent = 0

    for user in db.scalars(select(User)).all():
        user_now = local_now(user.timezone, now)
        if user_now.hour != STREAK_WARNING_LOCAL_HOUR:
            continue

        today = _progress_for(db, user, user_now.date())
        if today is not None and today.goal_met:
            continue

        yesterday = _progress_for(db, user, user_now.date() - timedelta(days=1))
        if yesterday is None or not yesterday.goal_met:
            continue  # no streak to protect

        if already_notified_since(db, user.id, NotificationKind.streak_at_risk, now - timedelta(hours=12)):
            continue

        tracked = today.total_minutes if today else 0
        create_notification(
            db,
            user.id,
            NotificationKind.streak_at_risk,
            title="Стрик под угрозой",
            body=f"До полуночи осталось {max(user.daily_goal_minutes - tracked, 0)} мин, чтобы не потерять серию.",
            payload={"today_minutes": tracked, "goal_minutes": user.daily_goal_minutes},
        )
        sent += 1

    return sent


def expire_overdue_paired_tasks(db: Session, now: datetime | None = None) -> int:
    """Close co-op tasks past their due date and tell the participants."""
    now = now or datetime.now(UTC)
    expired = 0

    tasks = db.scalars(select(PairedTask).where(PairedTask.status == PairedTaskStatus.active)).all()
    for task in tasks:
        due_at = task.due_at if task.due_at.tzinfo else task.due_at.replace(tzinfo=UTC)
        if due_at > now:
            continue

        task.status = PairedTaskStatus.expired
        participants = db.scalars(
            select(PairedTaskParticipant).where(PairedTaskParticipant.paired_task_id == task.id)
        ).all()
        for participant in participants:
            create_notification(
                db,
                participant.user_id,
                NotificationKind.paired_task_expired,
                title="Задание истекло",
                body=f"«{task.title}» закрылось по сроку.",
                payload={"paired_task_id": str(task.id)},
            )
        expired += 1

    return expired


def cleanup_read_notifications(db: Session, now: datetime | None = None) -> int:
    """Read notifications are history, not data — drop them after a month."""
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(days=READ_NOTIFICATION_TTL_DAYS)

    stale = db.scalars(
        select(Notification).where(Notification.read_at.is_not(None), Notification.read_at < cutoff)
    ).all()
    for notification in stale:
        db.delete(notification)
    return len(stale)
