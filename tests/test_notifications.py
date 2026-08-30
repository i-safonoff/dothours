from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.city import DailyProgress
from app.models.enums import NotificationKind
from app.models.notification import Notification
from app.models.user import User
from app.services.notifications import create_notification
from app.worker.jobs import (
    cleanup_read_notifications,
    expire_overdue_paired_tasks,
    send_daily_reminders,
    warn_streaks_at_risk,
)
from tests.conftest import auth_headers, register_and_login


def get_user(db: Session, email: str) -> User:
    return db.query(User).filter(User.email == email).one()


def set_progress(db: Session, user: User, on_date: date, minutes: int, goal_met: bool) -> None:
    db.add(
        DailyProgress(
            user_id=user.id,
            date=on_date,
            total_minutes=minutes,
            goal_minutes=user.daily_goal_minutes,
            goal_met=goal_met,
        )
    )
    db.commit()


def at_local_hour(timezone_name: str, hour: int) -> datetime:
    """A UTC instant that is `hour` o'clock in the given timezone."""
    local = datetime.now(ZoneInfo(timezone_name)).replace(hour=hour, minute=0, second=0, microsecond=0)
    return local.astimezone(UTC)


def local_date(moment: datetime, timezone_name: str) -> date:
    return moment.astimezone(ZoneInfo(timezone_name)).date()


def test_daily_reminder_fires_at_the_users_local_evening(client: TestClient, db_session: Session) -> None:
    register_and_login(client, email="ann@example.com", name="Ann")
    ann = get_user(db_session, "ann@example.com")
    ann.timezone = "Europe/Moscow"
    db_session.commit()

    morning = at_local_hour("Europe/Moscow", 9)
    assert send_daily_reminders(db_session, morning) == 0

    evening = at_local_hour("Europe/Moscow", 19)
    assert send_daily_reminders(db_session, evening) == 1
    db_session.commit()

    notification = db_session.query(Notification).one()
    assert notification.kind == NotificationKind.daily_reminder
    assert notification.payload["goal_minutes"] == ann.daily_goal_minutes


def test_daily_reminder_is_not_sent_twice_or_to_users_who_met_the_goal(client: TestClient, db_session: Session) -> None:
    register_and_login(client, email="ann@example.com", name="Ann")
    register_and_login(client, email="bob@example.com", name="Bob")
    ann = get_user(db_session, "ann@example.com")
    bob = get_user(db_session, "bob@example.com")
    ann.timezone = bob.timezone = "Europe/Moscow"
    db_session.commit()

    evening = at_local_hour("Europe/Moscow", 19)
    set_progress(db_session, bob, local_date(evening, "Europe/Moscow"), 200, True)

    assert send_daily_reminders(db_session, evening) == 1  # только Ann
    db_session.commit()
    assert send_daily_reminders(db_session, evening) == 0  # повторный запуск часа ничего не шлёт
    db_session.commit()

    assert db_session.query(Notification).count() == 1


def test_streak_warning_only_for_users_with_something_to_lose(client: TestClient, db_session: Session) -> None:
    register_and_login(client, email="ann@example.com", name="Ann")
    register_and_login(client, email="bob@example.com", name="Bob")
    ann = get_user(db_session, "ann@example.com")
    bob = get_user(db_session, "bob@example.com")
    ann.timezone = bob.timezone = "Europe/Moscow"
    db_session.commit()

    late = at_local_hour("Europe/Moscow", 21)
    local_today = local_date(late, "Europe/Moscow")
    set_progress(db_session, ann, local_today - timedelta(days=1), 200, True)  # у Ann есть серия

    assert warn_streaks_at_risk(db_session, late) == 1
    db_session.commit()

    notification = db_session.query(Notification).one()
    assert notification.user_id == ann.id
    assert notification.kind == NotificationKind.streak_at_risk


def test_streak_warning_skipped_when_goal_already_met(client: TestClient, db_session: Session) -> None:
    register_and_login(client, email="ann@example.com", name="Ann")
    ann = get_user(db_session, "ann@example.com")
    ann.timezone = "Europe/Moscow"
    db_session.commit()

    late = at_local_hour("Europe/Moscow", 21)
    local_today = local_date(late, "Europe/Moscow")
    set_progress(db_session, ann, local_today - timedelta(days=1), 200, True)
    set_progress(db_session, ann, local_today, 200, True)

    assert warn_streaks_at_risk(db_session, late) == 0


def test_unknown_timezone_falls_back_to_utc(client: TestClient, db_session: Session) -> None:
    register_and_login(client, email="ann@example.com", name="Ann")
    ann = get_user(db_session, "ann@example.com")
    ann.timezone = "Mars/Olympus"  # мусор в БД не должен ронять батч
    db_session.commit()

    utc_evening = datetime.now(UTC).replace(hour=19, minute=0, second=0, microsecond=0)
    assert send_daily_reminders(db_session, utc_evening) == 1


def test_overdue_paired_task_expires_and_notifies_participants(client: TestClient, db_session: Session) -> None:
    from tests.test_friends import make_friends

    ann, bob = make_friends(client)
    task = client.post(
        "/api/v1/paired-tasks",
        json={
            "title": "Английский",
            "building_family": "study",
            "target_minutes": 600,
            "target_type": "combined",
            "due_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
            "participant_user_ids": [bob["user"]["id"]],
        },
        headers=auth_headers(ann["token"]),
    ).json()

    assert expire_overdue_paired_tasks(db_session, datetime.now(UTC)) == 0

    later = datetime.now(UTC) + timedelta(days=2)
    assert expire_overdue_paired_tasks(db_session, later) == 1
    db_session.commit()

    assert db_session.query(Notification).count() == 2
    detail = client.get(f"/api/v1/paired-tasks/{task['id']}", headers=auth_headers(ann["token"])).json()
    assert detail["status"] == "expired"


def test_cleanup_drops_only_old_read_notifications(client: TestClient, db_session: Session) -> None:
    register_and_login(client, email="ann@example.com", name="Ann")
    ann = get_user(db_session, "ann@example.com")

    old_read = create_notification(db_session, ann.id, NotificationKind.daily_reminder, "Старое")
    old_read.read_at = datetime.now(UTC) - timedelta(days=40)
    recent_read = create_notification(db_session, ann.id, NotificationKind.daily_reminder, "Недавнее")
    recent_read.read_at = datetime.now(UTC) - timedelta(days=2)
    create_notification(db_session, ann.id, NotificationKind.daily_reminder, "Непрочитанное")
    db_session.commit()

    assert cleanup_read_notifications(db_session) == 1
    db_session.commit()
    assert {n.title for n in db_session.query(Notification).all()} == {"Недавнее", "Непрочитанное"}


def test_notifications_api_lists_marks_and_counts(client: TestClient, db_session: Session) -> None:
    session = register_and_login(client, email="ann@example.com", name="Ann")
    ann = get_user(db_session, "ann@example.com")
    create_notification(db_session, ann.id, NotificationKind.daily_reminder, "Первое")
    create_notification(db_session, ann.id, NotificationKind.streak_at_risk, "Второе")
    db_session.commit()

    page = client.get("/api/v1/notifications", headers=auth_headers(session["token"])).json()
    assert page["unread_count"] == 2
    assert {item["title"] for item in page["items"]} == {"Первое", "Второе"}

    first_id = page["items"][0]["id"]
    marked = client.post(f"/api/v1/notifications/{first_id}/read", headers=auth_headers(session["token"]))
    assert marked.status_code == 200
    assert marked.json()["read_at"] is not None

    count = client.get("/api/v1/notifications/unread-count", headers=auth_headers(session["token"])).json()
    assert count["unread_count"] == 1

    unread = client.get(
        "/api/v1/notifications", params={"unread_only": "true"}, headers=auth_headers(session["token"])
    ).json()
    assert len(unread["items"]) == 1

    assert client.post("/api/v1/notifications/read-all", headers=auth_headers(session["token"])).json() == {
        "unread_count": 0
    }


def test_notifications_are_private(client: TestClient, db_session: Session) -> None:
    register_and_login(client, email="ann@example.com", name="Ann")
    bob = register_and_login(client, email="bob@example.com", name="Bob")
    ann = get_user(db_session, "ann@example.com")
    notification = create_notification(db_session, ann.id, NotificationKind.daily_reminder, "Личное")
    db_session.commit()

    assert client.get("/api/v1/notifications", headers=auth_headers(bob["token"])).json()["items"] == []
    stolen = client.post(f"/api/v1/notifications/{notification.id}/read", headers=auth_headers(bob["token"]))
    assert stolen.status_code == 404


def test_profile_timezone_round_trip_and_validation(client: TestClient) -> None:
    session = register_and_login(client)

    assert client.get("/api/v1/users/me", headers=auth_headers(session["token"])).json()["timezone"] == "UTC"

    updated = client.patch(
        "/api/v1/users/me", json={"timezone": "Europe/Moscow"}, headers=auth_headers(session["token"])
    )
    assert updated.status_code == 200
    assert updated.json()["timezone"] == "Europe/Moscow"

    rejected = client.patch(
        "/api/v1/users/me", json={"timezone": "Mars/Olympus"}, headers=auth_headers(session["token"])
    )
    assert rejected.status_code == 400
