import os

# Must run before anything below imports app.main (which reaches
# app.core.config.get_settings() through app.services.notifications ->
# app.core.email -> app.worker.celery_app at module import time, and
# get_settings is @lru_cache'd -- once that first call reads Settings(),
# every test in the process is stuck with whatever it saw). A real .env
# with EMAIL_DELIVERY_ENABLED=true, left over from testing the feature
# manually against a real Mailpit, is exactly how this was found: not
# read here, and the whole suite quietly tried to dispatch real Celery
# tasks against a broker no test ever starts, some tests taking minutes
# instead of milliseconds before failing. This line is what makes "no
# external services needed" (README.md) actually true regardless of
# whatever a developer's own .env happens to contain, rather than true
# by accident because nothing had read a settings field with a
# real-world side effect until now.
os.environ["EMAIL_DELIVERY_ENABLED"] = "false"

from collections.abc import Generator  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.api.deps import get_db  # noqa: E402
from app.core.database import Base  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = testing_session_local()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def _get_db_override() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = _get_db_override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def register_and_login(client: TestClient, email: str = "ann@example.com", name: str = "Ann") -> dict:
    response = client.post("/api/v1/auth/register", json={"email": email, "password": "password123", "name": name})
    assert response.status_code == 201, response.text
    body = response.json()
    return {"token": body["access_token"], "user": body["user"]}


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
