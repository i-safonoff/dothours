from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from tests.conftest import auth_headers, register_and_login
from tests.test_categories import create_category


def create_company(client: TestClient, token: str, **overrides: object) -> dict:
    payload = {"name": "Утренние люди", "description": "Встаём в 6", **overrides}
    response = client.post("/api/v1/companies", json=payload, headers=auth_headers(token))
    assert response.status_code == 201, response.text
    return response.json()


def invite_and_join(client: TestClient, owner_token: str, company_id: str, joiner_token: str) -> dict:
    invite = client.post(f"/api/v1/companies/{company_id}/invites", json={}, headers=auth_headers(owner_token))
    assert invite.status_code == 201, invite.text
    response = client.post(
        "/api/v1/companies/join",
        json={"invite_code": invite.json()["code"]},
        headers=auth_headers(joiner_token),
    )
    assert response.status_code == 200, response.text
    return response.json()


def log_minutes(client: TestClient, token: str, category_id: str, minutes: int) -> None:
    started_at = datetime.now(UTC)
    response = client.post(
        "/api/v1/time-entries",
        json={
            "category_id": category_id,
            "started_at": started_at.isoformat(),
            "ended_at": (started_at + timedelta(minutes=minutes)).isoformat(),
        },
        headers=auth_headers(token),
    )
    assert response.status_code == 201, response.text


def test_create_company_makes_creator_the_owner(client: TestClient) -> None:
    ann = register_and_login(client)
    company = create_company(client, ann["token"])

    assert company["slug"]
    assert company["my_role"] == "owner"
    assert company["members_count"] == 1


def test_slug_conflict_is_rejected(client: TestClient) -> None:
    ann = register_and_login(client, email="ann@example.com", name="Ann")
    create_company(client, ann["token"], slug="early-birds")

    response = client.post(
        "/api/v1/companies",
        json={"name": "Другая", "slug": "early-birds"},
        headers=auth_headers(ann["token"]),
    )
    assert response.status_code == 409


def test_join_by_invite_and_list_members(client: TestClient) -> None:
    ann = register_and_login(client, email="ann@example.com", name="Ann")
    bob = register_and_login(client, email="bob@example.com", name="Bob")
    company = create_company(client, ann["token"])

    joined = invite_and_join(client, ann["token"], company["id"], bob["token"])
    assert joined["my_role"] == "member"
    assert joined["members_count"] == 2

    members = client.get(f"/api/v1/companies/{company['id']}/members", headers=auth_headers(bob["token"]))
    assert members.status_code == 200
    assert {m["name"] for m in members.json()} == {"Ann", "Bob"}


def test_join_twice_conflicts(client: TestClient) -> None:
    ann = register_and_login(client, email="ann@example.com", name="Ann")
    bob = register_and_login(client, email="bob@example.com", name="Bob")
    company = create_company(client, ann["token"])

    invite = client.post(
        f"/api/v1/companies/{company['id']}/invites", json={}, headers=auth_headers(ann["token"])
    ).json()
    client.post("/api/v1/companies/join", json={"invite_code": invite["code"]}, headers=auth_headers(bob["token"]))
    again = client.post(
        "/api/v1/companies/join", json={"invite_code": invite["code"]}, headers=auth_headers(bob["token"])
    )
    assert again.status_code == 409


def test_used_up_invite_is_gone(client: TestClient) -> None:
    ann = register_and_login(client, email="ann@example.com", name="Ann")
    bob = register_and_login(client, email="bob@example.com", name="Bob")
    carl = register_and_login(client, email="carl@example.com", name="Carl")
    company = create_company(client, ann["token"])

    invite = client.post(
        f"/api/v1/companies/{company['id']}/invites",
        json={"max_uses": 1},
        headers=auth_headers(ann["token"]),
    ).json()
    client.post("/api/v1/companies/join", json={"invite_code": invite["code"]}, headers=auth_headers(bob["token"]))
    response = client.post(
        "/api/v1/companies/join", json={"invite_code": invite["code"]}, headers=auth_headers(carl["token"])
    )
    assert response.status_code == 410


def test_private_company_is_invisible_to_outsiders(client: TestClient) -> None:
    ann = register_and_login(client, email="ann@example.com", name="Ann")
    stranger = register_and_login(client, email="stranger@example.com", name="Stranger")
    company = create_company(client, ann["token"])

    response = client.get(f"/api/v1/companies/{company['id']}", headers=auth_headers(stranger["token"]))
    assert response.status_code == 404

    public = create_company(client, ann["token"], name="Открытая", is_public=True)
    response = client.get(f"/api/v1/companies/{public['id']}", headers=auth_headers(stranger["token"]))
    assert response.status_code == 200
    assert response.json()["my_role"] is None


def test_list_companies_mine_and_public(client: TestClient) -> None:
    ann = register_and_login(client, email="ann@example.com", name="Ann")
    stranger = register_and_login(client, email="stranger@example.com", name="Stranger")
    create_company(client, ann["token"], name="Открытая", is_public=True)
    create_company(client, stranger["token"], name="Своя")

    mine = client.get("/api/v1/companies", headers=auth_headers(stranger["token"]))
    assert [c["name"] for c in mine.json()] == ["Своя"]

    discoverable = client.get("/api/v1/companies", params={"mine": "false"}, headers=auth_headers(stranger["token"]))
    assert {c["name"] for c in discoverable.json()} == {"Своя", "Открытая"}


def test_member_cannot_edit_or_delete_company(client: TestClient) -> None:
    ann = register_and_login(client, email="ann@example.com", name="Ann")
    bob = register_and_login(client, email="bob@example.com", name="Bob")
    company = create_company(client, ann["token"])
    invite_and_join(client, ann["token"], company["id"], bob["token"])

    patched = client.patch(
        f"/api/v1/companies/{company['id']}", json={"name": "Взломано"}, headers=auth_headers(bob["token"])
    )
    assert patched.status_code == 403

    deleted = client.delete(f"/api/v1/companies/{company['id']}", headers=auth_headers(bob["token"]))
    assert deleted.status_code == 403


def test_owner_promotes_member_who_then_edits(client: TestClient) -> None:
    ann = register_and_login(client, email="ann@example.com", name="Ann")
    bob = register_and_login(client, email="bob@example.com", name="Bob")
    company = create_company(client, ann["token"])
    invite_and_join(client, ann["token"], company["id"], bob["token"])

    promoted = client.patch(
        f"/api/v1/companies/{company['id']}/members/{bob['user']['id']}",
        json={"role": "admin"},
        headers=auth_headers(ann["token"]),
    )
    assert promoted.status_code == 200
    assert promoted.json()["role"] == "admin"

    patched = client.patch(
        f"/api/v1/companies/{company['id']}", json={"name": "Ранние пташки"}, headers=auth_headers(bob["token"])
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "Ранние пташки"


def test_owner_cannot_leave_before_handover(client: TestClient) -> None:
    ann = register_and_login(client)
    company = create_company(client, ann["token"])

    response = client.delete(
        f"/api/v1/companies/{company['id']}/members/{ann['user']['id']}", headers=auth_headers(ann["token"])
    )
    assert response.status_code == 400


def test_member_can_leave(client: TestClient) -> None:
    ann = register_and_login(client, email="ann@example.com", name="Ann")
    bob = register_and_login(client, email="bob@example.com", name="Bob")
    company = create_company(client, ann["token"])
    invite_and_join(client, ann["token"], company["id"], bob["token"])

    left = client.delete(
        f"/api/v1/companies/{company['id']}/members/{bob['user']['id']}", headers=auth_headers(bob["token"])
    )
    assert left.status_code == 204
    assert client.get(f"/api/v1/companies/{company['id']}", headers=auth_headers(bob["token"])).status_code == 404


def test_company_city_grows_from_member_minutes(client: TestClient) -> None:
    ann = register_and_login(client, email="ann@example.com", name="Ann")
    bob = register_and_login(client, email="bob@example.com", name="Bob")
    company = create_company(client, ann["token"])
    invite_and_join(client, ann["token"], company["id"], bob["token"])

    ann_category = create_category(client, ann["token"], building_family="sport")
    bob_category = create_category(client, bob["token"], building_family="sport")
    log_minutes(client, ann["token"], ann_category["id"], 400)
    log_minutes(client, bob["token"], bob_category["id"], 300)

    city = client.get(f"/api/v1/companies/{company['id']}/city", headers=auth_headers(ann["token"]))
    assert city.status_code == 200
    buildings = city.json()["buildings"]
    assert len(buildings) == 1
    assert buildings[0]["building_family"] == "sport"
    assert buildings[0]["total_minutes"] == 700
    assert buildings[0]["level"] == 2  # 700 минут ≈ 11.7 ч → второй уровень

    members = client.get(f"/api/v1/companies/{company['id']}/members", headers=auth_headers(ann["token"])).json()
    contributions = {m["name"]: m["contribution_minutes_total"] for m in members}
    assert contributions == {"Ann": 400, "Bob": 300}


def test_minutes_logged_before_joining_do_not_backfill(client: TestClient) -> None:
    ann = register_and_login(client, email="ann@example.com", name="Ann")
    bob = register_and_login(client, email="bob@example.com", name="Bob")
    bob_category = create_category(client, bob["token"], building_family="study")
    log_minutes(client, bob["token"], bob_category["id"], 120)

    company = create_company(client, ann["token"])
    invite_and_join(client, ann["token"], company["id"], bob["token"])

    city = client.get(f"/api/v1/companies/{company['id']}/city", headers=auth_headers(ann["token"]))
    assert city.json()["buildings"] == []


def test_delete_company_removes_it_for_members(client: TestClient) -> None:
    ann = register_and_login(client, email="ann@example.com", name="Ann")
    bob = register_and_login(client, email="bob@example.com", name="Bob")
    company = create_company(client, ann["token"])
    invite_and_join(client, ann["token"], company["id"], bob["token"])

    deleted = client.delete(f"/api/v1/companies/{company['id']}", headers=auth_headers(ann["token"]))
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/companies/{company['id']}", headers=auth_headers(bob["token"])).status_code == 404
    assert client.get("/api/v1/companies", headers=auth_headers(bob["token"])).json() == []


def test_invite_requires_admin(client: TestClient) -> None:
    ann = register_and_login(client, email="ann@example.com", name="Ann")
    bob = register_and_login(client, email="bob@example.com", name="Bob")
    company = create_company(client, ann["token"])
    invite_and_join(client, ann["token"], company["id"], bob["token"])

    response = client.post(f"/api/v1/companies/{company['id']}/invites", json={}, headers=auth_headers(bob["token"]))
    assert response.status_code == 403


def test_cyrillic_names_get_a_readable_slug(client: TestClient) -> None:
    ann = register_and_login(client)

    company = create_company(client, ann["token"], name="Утренние люди")
    assert company["slug"] == "utrennie-lyudi"

    mixed = create_company(client, ann["token"], name="Бег 5 km!")
    assert mixed["slug"] == "beg-5-km"


def test_names_with_no_usable_characters_still_get_a_unique_slug(client: TestClient) -> None:
    ann = register_and_login(client)

    first = create_company(client, ann["token"], name="🔥🔥🔥")
    second = create_company(client, ann["token"], name="🌟")

    assert first["slug"] == "company"
    assert second["slug"].startswith("company-")  # коллизия разводится суффиксом
    assert first["slug"] != second["slug"]
