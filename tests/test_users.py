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
