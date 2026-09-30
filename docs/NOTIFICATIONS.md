# Notifications and background jobs

🇬🇧 **English** · [🇷🇺 Русский](NOTIFICATIONS.ru.md)

## Model

A notification is a row in `notifications`, not a "send." A delivery
channel (email, push, WebSocket) is just a way to announce a row that
already exists. That's why the API is the source of truth, and the jobs
are testable with no transport at all.

`Notification`: `user_id`, `kind`, `title`, `body`, `payload` (JSON), `read_at`.

Kinds (`NotificationKind`): `daily_reminder`, `streak_at_risk`,
`paired_task_expired`, `paired_task_completed`, `friend_request`.

## Endpoints

- `GET /notifications?unread_only=&limit=&offset=` → `{unread_count, items}`
- `GET /notifications/unread-count`
- `POST /notifications/{id}/read`
- `POST /notifications/read-all`

Someone else's notification returns 404, not 403 — its existence isn't
confirmed.

## Jobs

| Job | Schedule (UTC) | What it does |
|---|---|---|
| `send_daily_reminders` | every hour, :00 | Reminds anyone who hasn't met today's goal |
| `warn_streaks_at_risk` | every hour, :05 | Warns about a streak about to be lost |
| `expire_overdue_paired_tasks` | every hour, :15 | Overdue paired tasks → `expired` + notifications |
| `cleanup_read_notifications` | Mondays, 03:30 | Deletes read notifications older than 30 days |

### Why hourly instead of "at 19:00"

`User` gained a `timezone` field. The job runs every hour and picks exactly
the users for whom it's **currently** 19:00 locally (or 21:00 for the
streak warning). That way a reminder lands in the user's own evening, not
UTC's — with no per-user schedule needed. A re-run of the same hour can't
double-send: before sending, it checks whether the same notification
already went out in the last 12 hours.

An unknown timezone in the database doesn't crash the batch —
`app/core/timezones.zone_for` silently falls back to UTC.

## Code layout

```
app/worker/celery_app.py   Celery + the beat schedule
app/worker/tasks.py        task wrappers: open a session, call the job, commit
app/worker/jobs.py         the actual logic — plain functions over a Session, no Celery
app/services/notifications.py  create/read notifications
app/core/email.py          the email delivery channel — see below for why it isn't in tasks.py
```

Jobs never commit anything themselves — the caller owns the transaction.
That's why tests call `jobs.send_daily_reminders(db, now)` directly with a
stubbed "now," with no Celery eager mode and no broker.

## Running it

Redis, `worker`, and `beat` are wired into `docker-compose.yml`:

```bash
docker compose up --build
```

Locally, without Docker:

```bash
poetry run celery -A app.worker.celery_app.celery_app worker --loglevel=info
poetry run celery -A app.worker.celery_app.celery_app beat --loglevel=info
```

## Email

Off by default (`EMAIL_DELIVERY_ENABLED=false`) — a fresh checkout has no
SMTP relay to send through. Once it's on, `create_notification` sends
`title` and `body` to `send_notification_email.delay()` after writing the
row and publishing the WebSocket event, the same "no extra lookups"
contract the model description above already promises: the task never
queries the database, so it has nothing left to fail if the row it's
about hasn't committed yet.

A per-user `email_notifications_enabled` column (default `true`, toggled
via `PATCH /users/me`) gates it independently of the global setting —
both have to say yes.

`app/core/email.py` holds the Celery task, not `app/worker/tasks.py`
where every other task lives: `tasks.py` imports `app.worker.jobs`, which
imports `app.services.notifications` — the module that has to trigger
this one. Putting the task in `tasks.py` would close that into an import
cycle.

```bash
docker compose -f docker-compose.yml -f docker-compose.mail.yml up --build
```

brings up [Mailpit](https://mailpit.axllent.org/) alongside the rest of
the stack — `http://localhost:8025` shows what was "sent," and nothing
leaves the machine.

## What's not here yet

- **Push notifications.** Email is the first external channel; push would
  be a second `.delay()` call in the same place, once there's a device
  token to send it to. In-app delivery is already realtime regardless of
  either: every notification fires a `notification.created` WebSocket
  event — see [REALTIME.md](REALTIME.md).
