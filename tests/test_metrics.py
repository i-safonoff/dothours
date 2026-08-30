import re

from fastapi.testclient import TestClient

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
