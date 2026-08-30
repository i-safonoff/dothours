import re

import pytest
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY, generate_latest
from sqlalchemy.orm import Session

from tests.conftest import auth_headers, register_and_login
from tests.test_categories import create_category


def metric_value(body: str, name: str, labels: str = "") -> float:
    """Read a single sample out of the Prometheus text exposition format."""
    pattern = rf"^{re.escape(name + labels)} (\S+)$"
    match = re.search(pattern, body, flags=re.MULTILINE)
    return float(match.group(1)) if match else 0.0


def test_metrics_endpoint_exposes_http_and_domain_metrics(client: TestClient) -> None:
    client.get("/health")
    response = client.get("/metrics")

    assert response.status_code == 200
    body = response.text
    assert "http_request_duration_seconds" in body
    assert "dothours_registrations_total" in body
    assert "dothours_active_timers" in body


def test_registration_and_timer_metrics_move(client: TestClient) -> None:
    before = client.get("/metrics").text
    registrations_before = metric_value(before, "dothours_registrations_total")
    active_before = metric_value(before, "dothours_active_timers")

    session = register_and_login(client)
    category = create_category(client, session["token"], building_family="sport")

    started = client.post(
        "/api/v1/time-entries/start",
        json={"category_id": category["id"]},
        headers=auth_headers(session["token"]),
    )
    assert started.status_code == 201

    during = client.get("/metrics").text
    assert metric_value(during, "dothours_registrations_total") == registrations_before + 1
    assert metric_value(during, "dothours_active_timers") == active_before + 1

    stopped = client.post(f"/api/v1/time-entries/{started.json()['id']}/stop", headers=auth_headers(session["token"]))
    assert stopped.status_code == 200

    after = client.get("/metrics").text
    assert metric_value(after, "dothours_active_timers") == active_before


def test_manual_entry_counts_tracked_minutes_and_level_ups(client: TestClient) -> None:
    from datetime import UTC, datetime, timedelta

    labels = '{building_family="study",source="manual"}'
    before = metric_value(client.get("/metrics").text, "dothours_minutes_tracked_total", labels)

    session = register_and_login(client)
    category = create_category(client, session["token"], building_family="study", shape="square")
    started_at = datetime.now(UTC)
    response = client.post(
        "/api/v1/time-entries",
        json={
            "category_id": category["id"],
            "started_at": started_at.isoformat(),
            "ended_at": (started_at + timedelta(minutes=60 * 12)).isoformat(),
        },
        headers=auth_headers(session["token"]),
    )
    assert response.status_code == 201

    body = client.get("/metrics").text
    assert metric_value(body, "dothours_minutes_tracked_total", labels) == before + 60 * 12
    # 12 часов переводят здание со 2-го уровня, поэтому счётчик апгрейдов сработал
    assert (
        metric_value(body, "dothours_buildings_level_up_total", '{building_family="study",level="2",owner_type="user"}')
        >= 1
    )


def test_every_response_carries_a_request_id(client: TestClient) -> None:
    response = client.get("/health")
    assert response.headers["X-Request-ID"]

    echoed = client.get("/health", headers={"X-Request-ID": "abc123"})
    assert echoed.headers["X-Request-ID"] == "abc123"


def test_realtime_and_notification_metrics_move(client: TestClient, db_session: Session) -> None:
    from app.models.enums import NotificationKind
    from app.services.notifications import create_notification
    from tests.test_notifications import get_user

    before = client.get("/metrics").text
    events_before = metric_value(before, "dothours_events_published_total", '{event="notification.created"}')
    created_before = metric_value(before, "dothours_notifications_created_total", '{kind="streak_at_risk"}')

    register_and_login(client, email="ann@example.com", name="Ann")
    ann = get_user(db_session, "ann@example.com")
    create_notification(db_session, ann.id, NotificationKind.streak_at_risk, "Стрик")
    db_session.commit()

    after = client.get("/metrics").text
    assert metric_value(after, "dothours_events_published_total", '{event="notification.created"}') == events_before + 1
    assert metric_value(after, "dothours_notifications_created_total", '{kind="streak_at_risk"}') == created_before + 1


def test_websocket_connection_gauge_tracks_open_sockets(client: TestClient) -> None:
    session = register_and_login(client)
    before = metric_value(client.get("/metrics").text, "dothours_ws_connections")

    with client.websocket_connect(f"/api/v1/ws?token={session['token']}"):
        during = metric_value(client.get("/metrics").text, "dothours_ws_connections")
        assert during == before + 1

    assert metric_value(client.get("/metrics").text, "dothours_ws_connections") == before


def test_background_task_metrics_record_success_and_failure(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.worker import tasks

    before = metric_value(
        _metrics_text(), "dothours_background_task_runs_total", '{outcome="success",task="cleanup_read_notifications"}'
    )
    monkeypatch.setattr(tasks, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(tasks.jobs, "cleanup_read_notifications", lambda db: 0)
    tasks.cleanup_read_notifications()

    assert (
        metric_value(
            _metrics_text(),
            "dothours_background_task_runs_total",
            '{outcome="success",task="cleanup_read_notifications"}',
        )
        == before + 1
    )

    def boom(db: Session) -> int:
        raise RuntimeError("job exploded")

    monkeypatch.setattr(tasks.jobs, "cleanup_read_notifications", boom)
    with pytest.raises(RuntimeError):
        tasks.cleanup_read_notifications()

    assert (
        metric_value(
            _metrics_text(),
            "dothours_background_task_runs_total",
            '{outcome="failure",task="cleanup_read_notifications"}',
        )
        == 1
    )


def _metrics_text() -> str:
    """Scrape the default registry directly — this test has no HTTP client."""
    return generate_latest(REGISTRY).decode()
