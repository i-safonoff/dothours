# Мониторинг

[🇬🇧 English](OBSERVABILITY.md) · 🇷🇺 **Русский**

API отдаёт метрики в формате Prometheus на `GET /metrics` (без авторизации —
эндпоинт рассчитан на закрытый периметр; наружу его выставлять не надо).
Отключается через `METRICS_ENABLED=false`.

## Запуск стека

```bash
docker compose -f docker-compose.yml -f docker-compose.observability.yml up --build
```

- Prometheus — http://localhost:9090
- Grafana — http://localhost:3000 (логин/пароль из `GRAFANA_USER` /
  `GRAFANA_PASSWORD`, по умолчанию `admin` / `admin`)

Датасорс и дашборд «.hours API» провижинятся автоматически из
`ops/grafana/provisioning` и `ops/grafana/dashboards` — руками в UI ничего
настраивать не нужно.

## Что снимается

**HTTP (prometheus-fastapi-instrumentator)** — `http_requests_total`,
`http_request_duration_seconds` с лейблами `handler`, `method`, `status`.
Коды статусов не группируются, поэтому `429` и `409` видно отдельно.

**Доменные метрики** (`app/core/metrics.py`) — про продукт, а не про запросы:

| Метрика | Тип | Лейблы | Смысл |
|---|---|---|---|
| `dothours_registrations_total` | counter | — | завершённые регистрации |
| `dothours_timers_started_total` | counter | — | стартов таймера |
| `dothours_timers_stopped_total` | counter | — | остановок таймера |
| `dothours_minutes_tracked_total` | counter | `building_family`, `source` | минуты, зачтённые в город |
| `dothours_buildings_level_up_total` | counter | `building_family`, `owner_type`, `level` | апгрейды зданий |
| `dothours_active_timers` | gauge | — | таймеры, идущие прямо сейчас |
| `dothours_notifications_created_total` | counter | `kind` | созданные уведомления |
| `dothours_events_published_total` | counter | `event` | события, отданные в шину |
| `dothours_ws_connections` | gauge | — | открытые WebSocket-соединения в этом процессе |
| `dothours_background_task_runs_total` | counter | `task`, `outcome` | запуски Celery-задач |
| `dothours_background_task_duration_seconds` | histogram | `task` | длительность Celery-задач |

`dothours_ws_connections` — процессный гейдж: при нескольких воркерах
суммируйте по инстансам (`sum(dothours_ws_connections)`), как и сделано в
дашборде.

`dothours_active_timers` инкрементится на старте и декрементится на
стопе/удалении записи, а на старте приложения синхронизируется с БД — иначе
после рестарта гейдж уезжает. Если БД недоступна, приложение всё равно
поднимается: метрика не должна блокировать старт.

**Postgres** — через `postgres-exporter` (`pg_stat_database_*`,
`pg_stat_activity_*`).

## Логи

Каждый ответ несёт заголовок `X-Request-ID` (входящий переиспользуется,
иначе генерируется), и на каждый запрос пишется одна JSON-строка со
`status_code` и `duration_ms`. Это делает лог пригодным для Loki/ELK и
позволяет связать всплеск на графике с конкретными запросами.

## Чего сознательно нет

- Алертов — правила нужно писать под реальные SLO, а их пока нет.
- Трейсинга (OpenTelemetry) — на текущем размере сервиса метрик и логов хватает.
- Экспортера Redis — брокер пока не бывает узким местом; добавляется одной
  строкой в `docker-compose.observability.yml`, когда понадобится.
