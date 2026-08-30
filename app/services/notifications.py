"""Creating and reading in-app notifications.

Every notification is a row first; a delivery channel (email, push) is only a
way to announce a row that already exists. That keeps the API the single
source of truth and makes the background jobs testable without any transport.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.metrics import notifications_created_total
from app.events import types
from app.events.bus import bus, user_channel
from app.models.enums import NotificationKind
from app.models.notification import Notification


def create_notification(
    db: Session,
    user_id: uuid.UUID,
    kind: NotificationKind,
    title: str,
    body: str = "",
    payload: dict[str, Any] | None = None,
) -> Notification:
    notification = Notification(
        user_id=user_id,
        kind=kind,
        title=title,
        body=body,
        payload=payload or {},
    )
    db.add(notification)
    db.flush()

    notifications_created_total.labels(kind.value).inc()
    bus.publish(
        user_channel(user_id),
        types.NOTIFICATION_CREATED,
        {"notification_id": str(notification.id), "kind": kind.value},
    )
    return notification


def already_notified_since(
    db: Session, user_id: uuid.UUID, kind: NotificationKind, since: datetime
) -> bool:
    """Guard against a re-run of an hourly job sending the same nudge twice."""
    existing = db.scalar(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.kind == kind,
            Notification.created_at >= since,
        )
    )
    return existing is not None


def unread_count(db: Session, user_id: uuid.UUID) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        )
        or 0
    )


def mark_all_read(db: Session, user_id: uuid.UUID) -> int:
    unread = db.scalars(
        select(Notification).where(Notification.user_id == user_id, Notification.read_at.is_(None))
    ).all()
    now = datetime.now(UTC)
    for notification in unread:
        notification.read_at = now
    return len(unread)
