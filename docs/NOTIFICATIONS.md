# Уведомления и фоновые задачи

## Модель

Уведомление — это строка в `notifications`, а не «отправка». Канал доставки
(почта, пуш, WebSocket) — способ объявить о строке, которая уже есть. Поэтому
API — источник правды, а джобы тестируются без транспорта вообще.

`Notification`: `user_id`, `kind`, `title`, `body`, `payload` (JSON), `read_at`.

Виды (`NotificationKind`): `daily_reminder`, `streak_at_risk`,
`paired_task_expired`, `paired_task_completed`, `friend_request`.

## Эндпоинты

- `GET /notifications?unread_only=&limit=&offset=` → `{unread_count, items}`
- `GET /notifications/unread-count`
- `POST /notifications/{id}/read`
- `POST /notifications/read-all`

Чужое уведомление отдаёт 404, а не 403 — не подтверждаем его существование.

## Задачи

| Задача | Расписание (UTC) | Что делает |
|---|---|---|
| `send_daily_reminders` | каждый час, :00 | Напоминание тем, кто не закрыл дневную цель |
| `warn_streaks_at_risk` | каждый час, :05 | Предупреждение о теряемой серии |
| `expire_overdue_paired_tasks` | каждый час, :15 | Просроченные парные задания → `expired` + уведомления |
| `cleanup_read_notifications` | по понедельникам 03:30 | Удаляет прочитанное старше 30 дней |

### Почему ежечасно, а не «в 19:00»

У `User` появилось поле `timezone`. Джоба запускается каждый час и берёт
ровно тех пользователей, у кого **сейчас** локальные 19:00 (или 21:00 для
стрика). Так напоминание приходит вечером у пользователя, а не вечером по
UTC — и при этом не нужно персональное расписание на каждого. Повторный
запуск того же часа ничего не дублирует: перед отправкой проверяется, не было
ли такого же уведомления за последние 12 часов.

Неизвестная таймзона в БД не роняет батч — `app/core/timezones.zone_for`
молча откатывается на UTC.

## Структура кода

```
app/worker/celery_app.py   Celery + beat schedule
app/worker/tasks.py        задачи-обёртки: открыть сессию, вызвать джобу, закоммитить
app/worker/jobs.py         сама логика — обычные функции над Session, без Celery
app/services/notifications.py  создание/чтение уведомлений
```

Джобы ничего не коммитят сами — транзакцией владеет вызывающий. Благодаря
этому тесты вызывают `jobs.send_daily_reminders(db, now)` напрямую с
подставленным «сейчас», без eager-режима Celery и без брокера.

## Запуск

Redis, `worker` и `beat` подняты в `docker-compose.yml`:

```bash
docker compose up --build
```

Локально, без Docker:

```bash
poetry run celery -A app.worker.celery_app.celery_app worker --loglevel=info
poetry run celery -A app.worker.celery_app.celery_app beat --loglevel=info
```

## Чего пока нет

- Внешних каналов (email/push) — решено начать с in-app; `payload` уже
  достаточно, чтобы канал собрал письмо, не заглядывая в БД.
- Пуша уведомления в реальном времени — приедет с веткой WebSocket: она
  подпишется на те же события.
