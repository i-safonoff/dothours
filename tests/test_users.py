from fastapi.testclient import TestClient

from tests.conftest import auth_headers, register_and_login


def test_search_user_by_email(client: TestClient) -> None:
    me = register_and_login(client, email="ann@example.com", name="Ann")
    other = register_and_login(client, email="bob@example.com", name="Bob")

    response = client.get(
        "/api/v1/users/search", params={"email": "bob@example.com"}, headers=auth_headers(me["token"])
    )
    assert response.status_code == 200
    assert response.json()["id"] == other["user"]["id"]


def test_search_user_by_email_not_found(client: TestClient) -> None:
    me = register_and_login(client)
    response = client.get(
        "/api/v1/users/search", params={"email": "nobody@example.com"}, headers=auth_headers(me["token"])
    )
    assert response.status_code == 404


def test_register_assigns_avatar_color(client: TestClient) -> None:
    me = register_and_login(client)
    assert me["user"]["email"]  # sanity: private view has email
    response = client.get("/api/v1/users/me", headers=auth_headers(me["token"]))
    body = response.json()
    assert body["avatar_color"].startswith("#")
    assert body["status"] == ""


def test_update_profile_status_and_avatar(client: TestClient) -> None:
    me = register_and_login(client)
    response = client.patch(
        "/api/v1/users/me",
        json={"status": "building a city out of hours", "avatar_color": "#123456"},
        headers=auth_headers(me["token"]),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "building a city out of hours"
    assert body["avatar_color"] == "#123456"


def test_public_profile_hides_email(client: TestClient) -> None:
    me = register_and_login(client, email="ann@example.com", name="Ann")
    other = register_and_login(client, email="bob@example.com", name="Bob")

    response = client.get(f"/api/v1/users/{other['user']['id']}", headers=auth_headers(me["token"]))
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Bob"
    assert "email" not in body
