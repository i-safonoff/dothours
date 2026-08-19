from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from tests.conftest import auth_headers, register_and_login
from tests.test_categories import create_category
from tests.test_friends import make_friends


def test_paired_task_requires_friendship(client: TestClient) -> None:
    ann = register_and_login(client, email="ann@example.com", name="Ann")
    stranger = register_and_login(client, email="stranger@example.com", name="Stranger")

    response = client.post(
        "/api/v1/paired-tasks",
        json={
            "title": "Английский",
            "building_family": "study",
            "target_minutes": 60,
            "target_type": "combined",
            "due_at": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
            "participant_user_ids": [stranger["user"]["id"]],
        },
        headers=auth_headers(ann["token"]),
    )
    assert response.status_code == 400


def test_paired_task_completes_when_combined_target_reached(client: TestClient) -> None:
    ann, bob = make_friends(client)
    ann_category = create_category(client, ann["token"], building_family="study", shape="square")
    bob_category = create_category(client, bob["token"], building_family="study", shape="square")

    create_response = client.post(
        "/api/v1/paired-tasks",
        json={
            "title": "Английский",
            "building_family": "study",
            "target_minutes": 100,
            "target_type": "combined",
            "due_at": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
            "participant_user_ids": [bob["user"]["id"]],
        },
        headers=auth_headers(ann["token"]),
    )
    assert create_response.status_code == 201
    task = create_response.json()
    assert {p["user_id"] for p in task["participants"]} == {ann["user"]["id"], bob["user"]["id"]}

    def log_minutes(token: str, category_id: str, minutes: int) -> None:
        started_at = datetime.now(UTC)
        client.post(
            "/api/v1/time-entries",
            json={
                "category_id": category_id,
                "started_at": started_at.isoformat(),
                "ended_at": (started_at + timedelta(minutes=minutes)).isoformat(),
                "paired_task_id": task["id"],
            },
            headers=auth_headers(token),
        )

    log_minutes(ann["token"], ann_category["id"], 40)
    mid_response = client.get(f"/api/v1/paired-tasks/{task['id']}", headers=auth_headers(ann["token"]))
    assert mid_response.json()["status"] == "active"

    log_minutes(bob["token"], bob_category["id"], 65)
    final_response = client.get(f"/api/v1/paired-tasks/{task['id']}", headers=auth_headers(bob["token"]))
    assert final_response.json()["status"] == "completed"
