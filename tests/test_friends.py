from fastapi.testclient import TestClient

from tests.conftest import auth_headers, register_and_login


def make_friends(client: TestClient) -> tuple[dict, dict]:
    ann = register_and_login(client, email="ann@example.com", name="Ann")
    bob = register_and_login(client, email="bob@example.com", name="Bob")

    request_response = client.post(
        "/api/v1/friends/requests",
        json={"to_user_id": bob["user"]["id"]},
        headers=auth_headers(ann["token"]),
    )
    assert request_response.status_code == 201
    request_id = request_response.json()["id"]

    accept_response = client.post(f"/api/v1/friends/requests/{request_id}/accept", headers=auth_headers(bob["token"]))
    assert accept_response.status_code == 200
    return ann, bob


def test_friend_request_flow(client: TestClient) -> None:
    ann, bob = make_friends(client)

    ann_friends = client.get("/api/v1/friends", headers=auth_headers(ann["token"])).json()
    assert len(ann_friends) == 1
    assert ann_friends[0]["name"] == "Bob"

    bob_friends = client.get("/api/v1/friends", headers=auth_headers(bob["token"])).json()
    assert bob_friends[0]["name"] == "Ann"


def test_duplicate_friend_request_rejected(client: TestClient) -> None:
    ann, bob = make_friends(client)
    response = client.post(
        "/api/v1/friends/requests",
        json={"to_user_id": bob["user"]["id"]},
        headers=auth_headers(ann["token"]),
    )
    assert response.status_code == 409


def test_remove_friend(client: TestClient) -> None:
    ann, bob = make_friends(client)
    response = client.delete(f"/api/v1/friends/{bob['user']['id']}", headers=auth_headers(ann["token"]))
    assert response.status_code == 204
    assert client.get("/api/v1/friends", headers=auth_headers(ann["token"])).json() == []
