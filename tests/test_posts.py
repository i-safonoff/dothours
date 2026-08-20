import time

from fastapi.testclient import TestClient

from tests.conftest import auth_headers, register_and_login


def create_post(client: TestClient, token: str, text: str = "Hello world") -> dict:
    response = client.post("/api/v1/posts", json={"text": text}, headers=auth_headers(token))
    assert response.status_code == 201, response.text
    return response.json()


def test_create_and_read_post(client: TestClient) -> None:
    session = register_and_login(client)
    post = create_post(client, session["token"], "First post")

    assert post["text"] == "First post"
    assert post["likes_count"] == 0
    assert post["comments_count"] == 0
    assert post["liked_by_me"] is False
    assert post["author"]["id"] == session["user"]["id"]
    assert "email" not in post["author"]

    response = client.get(f"/api/v1/posts/{post['id']}", headers=auth_headers(session["token"]))
    assert response.status_code == 200
    assert response.json()["text"] == "First post"


def test_feed_shows_posts_from_everyone_newest_first(client: TestClient) -> None:
    ann = register_and_login(client, email="ann@example.com", name="Ann")
    bob = register_and_login(client, email="bob@example.com", name="Bob")
    create_post(client, ann["token"], "Ann's post")
    time.sleep(1.1)  # SQLite's created_at default has second resolution
    create_post(client, bob["token"], "Bob's post")

    feed = client.get("/api/v1/posts", headers=auth_headers(ann["token"])).json()
    assert [p["text"] for p in feed] == ["Bob's post", "Ann's post"]


def test_filter_posts_by_author_for_profile_page(client: TestClient) -> None:
    ann = register_and_login(client, email="ann@example.com", name="Ann")
    bob = register_and_login(client, email="bob@example.com", name="Bob")
    create_post(client, ann["token"], "Ann's post")
    create_post(client, bob["token"], "Bob's post")

    ann_posts = client.get(
        "/api/v1/posts", params={"author_id": ann["user"]["id"]}, headers=auth_headers(bob["token"])
    ).json()
    assert len(ann_posts) == 1
    assert ann_posts[0]["text"] == "Ann's post"


def test_like_and_unlike_post(client: TestClient) -> None:
    ann = register_and_login(client, email="ann@example.com", name="Ann")
    bob = register_and_login(client, email="bob@example.com", name="Bob")
    post = create_post(client, ann["token"], "Like me")

    like_response = client.post(f"/api/v1/posts/{post['id']}/like", headers=auth_headers(bob["token"]))
    assert like_response.status_code == 201
    assert like_response.json()["likes_count"] == 1
    assert like_response.json()["liked_by_me"] is True

    duplicate = client.post(f"/api/v1/posts/{post['id']}/like", headers=auth_headers(bob["token"]))
    assert duplicate.status_code == 409

    unlike_response = client.request("DELETE", f"/api/v1/posts/{post['id']}/like", headers=auth_headers(bob["token"]))
    assert unlike_response.status_code == 200
    assert unlike_response.json()["likes_count"] == 0

    unlike_again = client.request("DELETE", f"/api/v1/posts/{post['id']}/like", headers=auth_headers(bob["token"]))
    assert unlike_again.status_code == 404


def test_comment_flow_and_permissions(client: TestClient) -> None:
    ann = register_and_login(client, email="ann@example.com", name="Ann")
    bob = register_and_login(client, email="bob@example.com", name="Bob")
    post = create_post(client, ann["token"], "Comment on me")

    comment_response = client.post(
        f"/api/v1/posts/{post['id']}/comments", json={"text": "Nice!"}, headers=auth_headers(bob["token"])
    )
    assert comment_response.status_code == 201
    comment = comment_response.json()
    assert comment["author"]["id"] == bob["user"]["id"]

    listed = client.get(f"/api/v1/posts/{post['id']}/comments", headers=auth_headers(ann["token"])).json()
    assert len(listed) == 1

    post_after = client.get(f"/api/v1/posts/{post['id']}", headers=auth_headers(ann["token"])).json()
    assert post_after["comments_count"] == 1

    forbidden = client.delete(f"/api/v1/comments/{comment['id']}", headers=auth_headers(ann["token"]))
    assert forbidden.status_code == 403

    allowed = client.delete(f"/api/v1/comments/{comment['id']}", headers=auth_headers(bob["token"]))
    assert allowed.status_code == 204

    post_after_delete = client.get(f"/api/v1/posts/{post['id']}", headers=auth_headers(ann["token"])).json()
    assert post_after_delete["comments_count"] == 0


def test_only_author_can_delete_post(client: TestClient) -> None:
    ann = register_and_login(client, email="ann@example.com", name="Ann")
    bob = register_and_login(client, email="bob@example.com", name="Bob")
    post = create_post(client, ann["token"], "Mine")

    forbidden = client.delete(f"/api/v1/posts/{post['id']}", headers=auth_headers(bob["token"]))
    assert forbidden.status_code == 403

    allowed = client.delete(f"/api/v1/posts/{post['id']}", headers=auth_headers(ann["token"]))
    assert allowed.status_code == 204
