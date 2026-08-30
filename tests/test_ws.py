"""Realtime tests run against the in-process bus — no Redis, no second worker."""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.enums import NotificationKind
from app.services.notifications import create_notification
from tests.conftest import auth_headers, register_and_login
from tests.test_categories import create_category
from tests.test_notifications import get_user


@pytest.fixture(autouse=True)
def memory_bus(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "ws_backend", "memory")


def receive_event(websocket) -> dict:
    return json.loads(websocket.receive_text())


def test_socket_rejects_a_missing_or_bad_token(client: TestClient) -> None:
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect) as without_token:  # noqa: SIM117
        with client.websocket_connect("/api/v1/ws"):
            pass
    assert without_token.value.code == 4401

    with pytest.raises(WebSocketDisconnect) as bad_token:  # noqa: SIM117
        with client.websocket_connect("/api/v1/ws?token=not-a-jwt"):
            pass
    assert bad_token.value.code == 4401


def test_socket_answers_a_ping(client: TestClient) -> None:
    session = register_and_login(client)
    with client.websocket_connect(f"/api/v1/ws?token={session['token']}") as websocket:
        websocket.send_text(json.dumps({"action": "ping"}))
        assert receive_event(websocket)["event"] == "pong"


def test_timer_start_and_stop_reach_the_socket(client: TestClient) -> None:
    session = register_and_login(client)
    category = create_category(client, session["token"], building_family="sport")

    with client.websocket_connect(f"/api/v1/ws?token={session['token']}") as websocket:
        started = client.post(
            "/api/v1/time-entries/start",
            json={"category_id": category["id"]},
            headers=auth_headers(session["token"]),
        )
        assert started.status_code == 201

        event = receive_event(websocket)
        assert event["event"] == "timer.started"
        assert event["data"]["entry_id"] == started.json()["id"]

        stopped = client.post(
            f"/api/v1/time-entries/{started.json()['id']}/stop", headers=auth_headers(session["token"])
        )
        assert stopped.status_code == 200
        assert receive_event(websocket)["event"] == "timer.stopped"


def test_new_notification_is_announced(client: TestClient, db_session: Session) -> None:
    session = register_and_login(client, email="ann@example.com", name="Ann")
    ann = get_user(db_session, "ann@example.com")

    with client.websocket_connect(f"/api/v1/ws?token={session['token']}") as websocket:
        notification = create_notification(db_session, ann.id, NotificationKind.streak_at_risk, "Стрик")
        db_session.commit()

        event = receive_event(websocket)
        assert event["event"] == "notification.created"
        assert event["data"]["notification_id"] == str(notification.id)
        assert event["data"]["kind"] == "streak_at_risk"


def test_friend_request_reaches_the_addressee_only(client: TestClient) -> None:
    ann = register_and_login(client, email="ann@example.com", name="Ann")
    bob = register_and_login(client, email="bob@example.com", name="Bob")

    with client.websocket_connect(f"/api/v1/ws?token={bob['token']}") as bob_socket:
        request = client.post(
            "/api/v1/friends/requests",
            json={"to_user_id": bob["user"]["id"]},
            headers=auth_headers(ann["token"]),
        )
        assert request.status_code == 201

        event = receive_event(bob_socket)
        assert event["event"] == "friend.request_received"
        assert event["data"]["from_user_id"] == ann["user"]["id"]

    with client.websocket_connect(f"/api/v1/ws?token={ann['token']}") as ann_socket:
        accepted = client.post(
            f"/api/v1/friends/requests/{request.json()['id']}/accept", headers=auth_headers(bob["token"])
        )
        assert accepted.status_code == 200
        assert receive_event(ann_socket)["event"] == "friend.request_accepted"


def test_building_level_up_is_announced(client: TestClient) -> None:
    from datetime import UTC, datetime, timedelta

    session = register_and_login(client)
    category = create_category(client, session["token"], building_family="study", shape="square")

    with client.websocket_connect(f"/api/v1/ws?token={session['token']}") as websocket:
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

        event = receive_event(websocket)
        assert event["event"] == "city.building_leveled_up"
        assert event["data"] == {"building_family": "study", "level": 2}


def test_events_do_not_leak_to_another_user(client: TestClient) -> None:
    ann = register_and_login(client, email="ann@example.com", name="Ann")
    bob = register_and_login(client, email="bob@example.com", name="Bob")
    ann_category = create_category(client, ann["token"], building_family="sport")

    with client.websocket_connect(f"/api/v1/ws?token={bob['token']}") as bob_socket:
        client.post(
            "/api/v1/time-entries/start",
            json={"category_id": ann_category["id"]},
            headers=auth_headers(ann["token"]),
        )

        bob_socket.send_text(json.dumps({"action": "ping"}))
        # Первое, что приходит Бобу, — его собственный pong: чужой таймер до него не долетел.
        assert receive_event(bob_socket)["event"] == "pong"
