"""Delivers a notification by email. Built purely from the notification's
own title and body -- no database lookup, matching the "a channel just
announces a row that already exists, with no extra lookups" contract
docs/NOTIFICATIONS.md holds every delivery channel to.

Lives here rather than in app/worker/tasks.py on purpose. tasks.py
imports app.worker.jobs, which imports app.services.notifications --
and notifications.py is what has to trigger this task. Putting the task
in tasks.py would close that into an import cycle
(notifications -> tasks -> jobs -> notifications). This module only
imports app.worker.celery_app, which only imports app.core.config, so
nothing loops back.
"""

import smtplib
from email.message import EmailMessage

from app.core.config import get_settings
from app.core.metrics import notification_emails_failed_total, notification_emails_sent_total
from app.worker.celery_app import celery_app


def _send(to_email: str, subject: str, body: str) -> None:
    settings = get_settings()
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from
    message["To"] = to_email
    message.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=5) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


@celery_app.task(
    name="app.core.email.send_notification_email",
    autoretry_for=(smtplib.SMTPException, OSError),
    retry_backoff=True,
    max_retries=3,
)
def send_notification_email(to_email: str, title: str, body: str) -> None:
    try:
        _send(to_email, subject=title, body=body or title)
    except (smtplib.SMTPException, OSError):
        notification_emails_failed_total.inc()
        raise
    notification_emails_sent_total.inc()
