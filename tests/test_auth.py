from fastapi.testclient import TestClient

from tests.conftest import auth_headers, register_and_login


def test_register_creates_user_and_returns_token(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "ann@example.com", "password": "password123", "name": "Ann"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "ann@example.com"
    assert body["user"]["initials"] == "A"
    assert body["access_token"]


def test_register_rejects_duplicate_email(client: TestClient) -> None:
    register_and_login(client)
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "ann@example.com", "password": "password123", "name": "Ann"},
    )
    assert response.status_code == 409


def test_login_with_wrong_password_fails(client: TestClient) -> None:
    register_and_login(client)
    response = client.post("/api/v1/auth/login", json={"email": "ann@example.com", "password": "wrong-password"})
    assert response.status_code == 401


def test_me_requires_token(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_me_returns_current_user(client: TestClient) -> None:
    session = register_and_login(client)
    response = client.get("/api/v1/auth/me", headers=auth_headers(session["token"]))
    assert response.status_code == 200
    assert response.json()["email"] == "ann@example.com"
