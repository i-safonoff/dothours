"""Whether create_notification dispatches the email task -- not whether
the task actually sends anything, which needs a real SMTP server and
lives in tests/test_email_delivery.py behind the smtp marker instead.
Both send_notification_email.delay and get_settings are patched at the
name app.services.notifications imported them under, so neither test
touches the process-wide lru_cache on get_settings or a real broker.
"""

from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.models.enums import NotificationKind
from app.models.user import User
from app.services.notifications import create_notification
from tests.conftest import register_and_login


def _get_user(db: Session) -> User:
    return db.query(User).one()


def test_no_dispatch_when_email_delivery_is_disabled(client, db_session: Session) -> None:
    register_and_login(client)
    user = _get_user(db_session)

    with (
        patch("app.services.notifications.get_settings") as mock_settings,
        patch("app.services.notifications.send_notification_email") as mock_task,
    ):
        mock_settings.return_value.email_delivery_enabled = False
        create_notification(db_session, user.id, NotificationKind.daily_reminder, "Title", "Body")

    mock_task.delay.assert_not_called()


def test_no_dispatch_when_the_user_opted_out(client, db_session: Session) -> None:
    register_and_login(client)
    user = _get_user(db_session)
    user.email_notifications_enabled = False
    db_session.flush()

    with (
        patch("app.services.notifications.get_settings") as mock_settings,
        patch("app.services.notifications.send_notification_email") as mock_task,
    ):
        mock_settings.return_value.email_delivery_enabled = True
        create_notification(db_session, user.id, NotificationKind.daily_reminder, "Title", "Body")

    mock_task.delay.assert_not_called()


def test_dispatches_with_the_notifications_own_title_and_body(client, db_session: Session) -> None:
    register_and_login(client)
    user = _get_user(db_session)
    assert user.email_notifications_enabled is True  # the default this test relies on

    with (
        patch("app.services.notifications.get_settings") as mock_settings,
        patch("app.services.notifications.send_notification_email") as mock_task,
    ):
        mock_settings.return_value.email_delivery_enabled = True
        mock_task.delay = MagicMock()
        create_notification(
            db_session, user.id, NotificationKind.streak_at_risk, "Стрик под угрозой", "Осталось мало времени"
        )

    mock_task.delay.assert_called_once_with(user.email, "Стрик под угрозой", "Осталось мало времени")
