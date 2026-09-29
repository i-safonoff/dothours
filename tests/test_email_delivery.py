"""Against a real SMTP server, not a mock -- does the message that
Mailpit actually received have the subject and recipient it was told
to send, byte for byte, no assumption about what smtplib did with them.

    docker run -d -p 1026:1025 -p 8026:8025 axllent/mailpit

Deselected by default (see the `smtp` marker in pyproject.toml); the
dispatch-gating logic in create_notification is covered without any of
this in tests/test_email_notifications.py.
"""

import os

import httpx
import pytest

from app.core.config import get_settings
from app.core.email import send_notification_email

pytestmark = pytest.mark.smtp

MAILPIT_API = os.environ.get("MAILPIT_API_URL", "http://localhost:8026")


@pytest.fixture(autouse=True)
def _point_settings_at_mailpit():
    get_settings.cache_clear()
    os.environ["SMTP_HOST"] = "localhost"
    os.environ["SMTP_PORT"] = "1026"
    yield
    del os.environ["SMTP_HOST"]
    del os.environ["SMTP_PORT"]
    get_settings.cache_clear()


def _latest_message() -> dict:
    response = httpx.get(f"{MAILPIT_API}/api/v1/messages", params={"limit": 1})
    response.raise_for_status()
    messages = response.json()["messages"]
    assert messages, "mailpit received nothing"
    return messages[0]


def test_a_notification_email_actually_arrives():
    # send_notification_email.run() bypasses the Celery broker entirely and
    # calls the task body directly -- this test is about whether the SMTP
    # conversation with a real server succeeds, not about Celery dispatch,
    # which tests/test_email_notifications.py already covers with mocks.
    send_notification_email.run("someone@example.com", "Стрик под угрозой", "Осталось мало времени")

    message = _latest_message()
    assert message["Subject"] == "Стрик под угрозой"
    assert message["To"][0]["Address"] == "someone@example.com"
    assert "Осталось мало времени" in message["Snippet"]


def test_an_empty_body_falls_back_to_the_title():
    send_notification_email.run("someone@example.com", "Only a title", "")

    message = _latest_message()
    assert message["Subject"] == "Only a title"
    assert "Only a title" in message["Snippet"]
