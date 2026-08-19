from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from tests.conftest import auth_headers, register_and_login
from tests.test_categories import create_category


def test_start_stop_timer_flow(client: TestClient) -> None:
    session = register_and_login(client)
    headers = auth_headers(session["token"])
    category = create_category(client, session["token"])

    start_response = client.post("/api/v1/time-entries/start", json={"category_id": category["id"]}, headers=headers)
    assert start_response.status_code == 201
    entry = start_response.json()
    assert entry["ended_at"] is None

    second_start = client.post("/api/v1/time-entries/start", json={"category_id": category["id"]}, headers=headers)
    assert second_start.status_code == 409

    active_response = client.get("/api/v1/time-entries/active", headers=headers)
    assert active_response.json()["id"] == entry["id"]

    stop_response = client.post(f"/api/v1/time-entries/{entry['id']}/stop", headers=headers)
    assert stop_response.status_code == 200
    assert stop_response.json()["ended_at"] is not None

    assert client.get("/api/v1/time-entries/active", headers=headers).json() is None


def test_manual_entry_builds_city_and_daily_progress(client: TestClient) -> None:
    session = register_and_login(client)
    headers = auth_headers(session["token"])
    category = create_category(client, session["token"], minutes_per_day_target=30)

    started_at = datetime.now(UTC).replace(hour=8, minute=0, second=0, microsecond=0)
    manual_response = client.post(
        "/api/v1/time-entries",
        json={
            "category_id": category["id"],
            "started_at": started_at.isoformat(),
            "ended_at": (started_at + timedelta(hours=11)).isoformat(),
        },
        headers=headers,
    )
    assert manual_response.status_code == 201, manual_response.text

    city_response = client.get("/api/v1/city/me", headers=headers)
    buildings = city_response.json()["buildings"]
    assert len(buildings) == 1
    assert buildings[0]["building_family"] == "sport"
    assert buildings[0]["total_minutes"] == 660
    assert buildings[0]["level"] == 2  # 11h crosses the 10h threshold, not yet the 30h one

    stats_response = client.get("/api/v1/users/me/stats", headers=headers)
    stats = stats_response.json()
    assert stats["today_minutes"] == 660
    assert stats["streak"] == 1


def test_manual_entry_rejects_inverted_range(client: TestClient) -> None:
    session = register_and_login(client)
    headers = auth_headers(session["token"])
    category = create_category(client, session["token"])

    now = datetime.now(UTC)
    response = client.post(
        "/api/v1/time-entries",
        json={
            "category_id": category["id"],
            "started_at": now.isoformat(),
            "ended_at": (now - timedelta(minutes=5)).isoformat(),
        },
        headers=headers,
    )
    assert response.status_code == 422
