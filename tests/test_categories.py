from fastapi.testclient import TestClient

from tests.conftest import auth_headers, register_and_login

CATEGORY_PAYLOAD = {
    "title": "Спорт",
    "color": "#FF5A45",
    "shape": "circle",
    "building_family": "sport",
    "minutes_per_day_target": 45,
}


def create_category(client: TestClient, token: str, **overrides: object) -> dict:
    payload = {**CATEGORY_PAYLOAD, **overrides}
    response = client.post("/api/v1/categories", json=payload, headers=auth_headers(token))
    assert response.status_code == 201, response.text
    return response.json()


def test_create_and_list_categories(client: TestClient) -> None:
    session = register_and_login(client)
    create_category(client, session["token"])

    response = client.get("/api/v1/categories", headers=auth_headers(session["token"]))
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["title"] == "Спорт"


def test_archived_categories_hidden_by_default(client: TestClient) -> None:
    session = register_and_login(client)
    category = create_category(client, session["token"])

    delete_response = client.delete(f"/api/v1/categories/{category['id']}", headers=auth_headers(session["token"]))
    assert delete_response.status_code == 204

    response = client.get("/api/v1/categories", headers=auth_headers(session["token"]))
    assert response.json() == []

    response = client.get(
        "/api/v1/categories", params={"include_archived": True}, headers=auth_headers(session["token"])
    )
    assert len(response.json()) == 1
    assert response.json()[0]["archived"] is True


def test_cannot_access_another_users_category(client: TestClient) -> None:
    owner = register_and_login(client, email="owner@example.com")
    other = register_and_login(client, email="other@example.com")
    category = create_category(client, owner["token"])

    response = client.patch(
        f"/api/v1/categories/{category['id']}",
        json={"title": "Hacked"},
        headers=auth_headers(other["token"]),
    )
    assert response.status_code == 404
