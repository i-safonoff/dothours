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

## What's not here yet

- External channels (email/push) — the decision was to start with in-app
  only; `payload` already carries enough for a channel to assemble a
  message without looking anything up in the database. In-app delivery
  itself is already realtime: every notification also fires a
  `notification.created` WebSocket event — see [REALTIME.md](REALTIME.md).
