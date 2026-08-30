from datetime import UTC, date, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import LeaderboardPeriod
from app.models.leaderboard import CityScore
from app.services.scoring import period_key, period_range, recompute_scores
from tests.conftest import auth_headers, register_and_login
from tests.test_categories import create_category
from tests.test_companies import create_company, invite_and_join, log_minutes


def test_period_key_and_range() -> None:
    day = date(2026, 8, 30)  # воскресенье 35-й ISO-недели
    assert period_key(LeaderboardPeriod.all_time, day) == "all"
    assert period_key(LeaderboardPeriod.weekly, day) == "2026-W35"
    assert period_key(LeaderboardPeriod.monthly, day) == "2026-08"

    assert period_range(LeaderboardPeriod.all_time, day) is None

    week_start, week_end = period_range(LeaderboardPeriod.weekly, day)
    assert week_start.date() == date(2026, 8, 24)
    assert week_end.date() == date(2026, 8, 31)

    month_start, month_end = period_range(LeaderboardPeriod.monthly, day)
    assert month_start.date() == date(2026, 8, 1)
    assert month_end.date() == date(2026, 9, 1)


def test_leaderboard_ranks_public_companies_by_score(client: TestClient) -> None:
    ann = register_and_login(client, email="ann@example.com", name="Ann")
    bob = register_and_login(client, email="bob@example.com", name="Bob")

    big = create_company(client, ann["token"], name="Большие", is_public=True)
    small = create_company(client, bob["token"], name="Маленькие", is_public=True)

    ann_category = create_category(client, ann["token"], building_family="sport")
    bob_category = create_category(client, bob["token"], building_family="sport")
    log_minutes(client, ann["token"], ann_category["id"], 60 * 40)  # 40 ч → уровень 3
    log_minutes(client, bob["token"], bob_category["id"], 60 * 2)  # 2 ч → уровень 1

    response = client.get("/api/v1/leaderboard/companies", headers=auth_headers(ann["token"]))
    assert response.status_code == 200
    body = response.json()
    assert body["period"] == "all_time"
    assert body["period_key"] == "all"
    assert body["total"] == 2

    names = [e["name"] for e in body["entries"]]
    assert names == ["Большие", "Маленькие"]
    assert [e["rank"] for e in body["entries"]] == [1, 2]
    assert body["entries"][0]["score"] > body["entries"][1]["score"]
    assert body["entries"][0]["members_count"] == 1
    assert body["entries"][0]["company_id"] == big["id"]
    assert body["entries"][1]["company_id"] == small["id"]


def test_private_companies_are_excluded(client: TestClient) -> None:
    ann = register_and_login(client, email="ann@example.com", name="Ann")
    private = create_company(client, ann["token"], name="Приватные")

    page = client.get("/api/v1/leaderboard/companies", headers=auth_headers(ann["token"])).json()
    assert page["total"] == 0

    rank = client.get(f"/api/v1/leaderboard/companies/{private['id']}", headers=auth_headers(ann["token"]))
    assert rank.status_code == 404


def test_company_rank_returns_neighbors(client: TestClient) -> None:
    ann = register_and_login(client, email="ann@example.com", name="Ann")
    category = create_category(client, ann["token"], building_family="study")
    log_minutes(client, ann["token"], category["id"], 60 * 40)

    ranked = [create_company(client, ann["token"], name=f"Компания {i}", is_public=True) for i in range(6)]
    target = ranked[3]

    response = client.get(f"/api/v1/leaderboard/companies/{target['id']}", headers=auth_headers(ann["token"]))
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 6
    assert 1 <= body["rank"] <= 6
    assert any(n["company_id"] == target["id"] for n in body["neighbors"])
    assert len(body["neighbors"]) <= 5


def test_weekly_slice_counts_only_this_weeks_minutes(client: TestClient, db_session: Session) -> None:
    ann = register_and_login(client, email="ann@example.com", name="Ann")
    company = create_company(client, ann["token"], name="Спринтеры", is_public=True)
    category = create_category(client, ann["token"], building_family="work")

    long_ago = datetime.now(UTC) - timedelta(days=90)
    old_entry = client.post(
        "/api/v1/time-entries",
        json={
            "category_id": category["id"],
            "started_at": long_ago.isoformat(),
            "ended_at": (long_ago + timedelta(minutes=60 * 40)).isoformat(),
        },
        headers=auth_headers(ann["token"]),
    )
    assert old_entry.status_code == 201

    all_time = client.get(
        "/api/v1/leaderboard/companies", params={"period": "all_time"}, headers=auth_headers(ann["token"])
    ).json()
    assert all_time["entries"][0]["score"] > 0

    weekly = client.get(
        "/api/v1/leaderboard/companies", params={"period": "weekly"}, headers=auth_headers(ann["token"])
    ).json()
    assert weekly["period_key"] == period_key(LeaderboardPeriod.weekly)
    assert weekly["entries"][0]["score"] == 0

    log_minutes(client, ann["token"], category["id"], 60 * 12)
    recompute_scores(db_session, LeaderboardPeriod.weekly)
    weekly = client.get(
        "/api/v1/leaderboard/companies", params={"period": "weekly"}, headers=auth_headers(ann["token"])
    ).json()
    assert weekly["entries"][0]["score"] > 0
    assert weekly["entries"][0]["company_id"] == company["id"]


def test_cached_scores_are_reused_within_ttl(client: TestClient, db_session: Session) -> None:
    ann = register_and_login(client, email="ann@example.com", name="Ann")
    create_company(client, ann["token"], name="Кэш", is_public=True)
    category = create_category(client, ann["token"], building_family="reading")

    first = client.get("/api/v1/leaderboard/companies", headers=auth_headers(ann["token"])).json()
    computed_at = db_session.query(CityScore).one().computed_at

    log_minutes(client, ann["token"], category["id"], 60 * 40)
    second = client.get("/api/v1/leaderboard/companies", headers=auth_headers(ann["token"])).json()

    assert second["entries"][0]["score"] == first["entries"][0]["score"]
    assert db_session.query(CityScore).one().computed_at == computed_at

    recompute_scores(db_session, LeaderboardPeriod.all_time)
    third = client.get("/api/v1/leaderboard/companies", headers=auth_headers(ann["token"])).json()
    assert third["entries"][0]["score"] > first["entries"][0]["score"]


def test_going_private_drops_the_company_from_the_ranking(client: TestClient, db_session: Session) -> None:
    ann = register_and_login(client, email="ann@example.com", name="Ann")
    company = create_company(client, ann["token"], name="Ушли в тень", is_public=True)

    assert client.get("/api/v1/leaderboard/companies", headers=auth_headers(ann["token"])).json()["total"] == 1

    client.patch(f"/api/v1/companies/{company['id']}", json={"is_public": False}, headers=auth_headers(ann["token"]))
    recompute_scores(db_session, LeaderboardPeriod.all_time)

    page = client.get("/api/v1/leaderboard/companies", headers=auth_headers(ann["token"])).json()
    assert page["total"] == 0


def test_streaks_of_members_add_to_the_score(client: TestClient, db_session: Session) -> None:
    ann = register_and_login(client, email="ann@example.com", name="Ann")
    bob = register_and_login(client, email="bob@example.com", name="Bob")
    company = create_company(client, ann["token"], name="Стрикеры", is_public=True)
    invite_and_join(client, ann["token"], company["id"], bob["token"])

    before = client.get("/api/v1/leaderboard/companies", headers=auth_headers(ann["token"])).json()
    baseline = before["entries"][0]["score"]

    # Дневная цель по умолчанию 120 минут — этого хватает, чтобы закрыть её сегодня.
    bob_category = create_category(client, bob["token"], building_family="meditation")
    log_minutes(client, bob["token"], bob_category["id"], 150)

    recompute_scores(db_session, LeaderboardPeriod.all_time)
    after = client.get("/api/v1/leaderboard/companies", headers=auth_headers(ann["token"])).json()
    assert after["entries"][0]["score"] > baseline


def test_completed_paired_task_adds_points_when_both_are_members(client: TestClient, db_session: Session) -> None:
    from tests.test_friends import make_friends

    ann, bob = make_friends(client)
    company = create_company(client, ann["token"], name="Напарники", is_public=True)
    invite_and_join(client, ann["token"], company["id"], bob["token"])

    before = client.get("/api/v1/leaderboard/companies", headers=auth_headers(ann["token"])).json()
    baseline = before["entries"][0]["score"]

    task = client.post(
        "/api/v1/paired-tasks",
        json={
            "title": "Английский",
            "building_family": "study",
            "target_minutes": 60,
            "target_type": "combined",
            "due_at": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
            "participant_user_ids": [bob["user"]["id"]],
        },
        headers=auth_headers(ann["token"]),
    ).json()

    ann_category = create_category(client, ann["token"], building_family="study")
    started_at = datetime.now(UTC)
    client.post(
        "/api/v1/time-entries",
        json={
            "category_id": ann_category["id"],
            "started_at": started_at.isoformat(),
            "ended_at": (started_at + timedelta(minutes=90)).isoformat(),
            "paired_task_id": task["id"],
        },
        headers=auth_headers(ann["token"]),
    )
    assert (
        client.get(f"/api/v1/paired-tasks/{task['id']}", headers=auth_headers(ann["token"])).json()["status"]
        == "completed"
    )

    recompute_scores(db_session, LeaderboardPeriod.all_time)
    after = client.get("/api/v1/leaderboard/companies", headers=auth_headers(ann["token"])).json()
    assert after["entries"][0]["score"] >= baseline + 50

    weekly = client.get(
        "/api/v1/leaderboard/companies", params={"period": "weekly"}, headers=auth_headers(ann["token"])
    ).json()
    assert weekly["entries"][0]["score"] >= 50  # completed_at попал в текущую неделю
