# Monitoring

🇬🇧 **English** · [🇷🇺 Русский](OBSERVABILITY.ru.md)

The API exposes Prometheus metrics at `GET /metrics` (no auth — the
endpoint is meant to sit behind a closed perimeter; don't expose it
publicly). Turn it off with `METRICS_ENABLED=false`.

## Running the stack

```bash
docker compose -f docker-compose.yml -f docker-compose.observability.yml up --build
```

- Prometheus — http://localhost:9090
- Grafana — http://localhost:3000 (login/password from `GRAFANA_USER` /
  `GRAFANA_PASSWORD`, `admin` / `admin` by default)

The datasource and the ".hours API" dashboard are provisioned automatically
from `ops/grafana/provisioning` and `ops/grafana/dashboards` — nothing to
configure by hand in the UI.

## What's collected

**HTTP (prometheus-fastapi-instrumentator)** — `http_requests_total`,
`http_request_duration_seconds` with `handler`, `method`, `status` labels.
Status codes aren't grouped, so `429` and `409` are visible separately.

**Domain metrics** (`app/core/metrics.py`) — about the product, not about
requests:

| Metric | Type | Labels | Meaning |
|---|---|---|---|
| `dothours_registrations_total` | counter | — | completed registrations |
| `dothours_timers_started_total` | counter | — | timers started |
| `dothours_timers_stopped_total` | counter | — | timers stopped |
| `dothours_minutes_tracked_total` | counter | `building_family`, `source` | minutes credited to a city |
| `dothours_buildings_level_up_total` | counter | `building_family`, `owner_type`, `level` | building upgrades |
| `dothours_active_timers` | gauge | — | timers running right now |
| `dothours_notifications_created_total` | counter | `kind` | notifications created |
| `dothours_events_published_total` | counter | `event` | events handed to the bus |
| `dothours_ws_connections` | gauge | — | open WebSocket connections on this process |
| `dothours_background_task_runs_total` | counter | `task`, `outcome` | Celery task runs |
| `dothours_background_task_duration_seconds` | histogram | `task` | Celery task duration |

`dothours_ws_connections` is a per-process gauge: with several workers, sum
across instances (`sum(dothours_ws_connections)`), same as the dashboard
does.

`dothours_active_timers` increments on start and decrements on stop/delete,
and is re-synced from the database on app startup — otherwise the gauge
drifts after a restart. If the database is unreachable, the app still
boots: a metric must never block startup.

**Postgres** — through `postgres-exporter` (`pg_stat_database_*`,
`pg_stat_activity_*`).

## Logs

Every response carries an `X-Request-ID` header (an incoming one is
reused, otherwise generated), and every request writes one JSON log line
with `status_code` and `duration_ms`. That makes the log fit for
Loki/ELK and lets a spike on a graph be traced back to concrete requests.

## What's deliberately not here

- Alerts — the rules need real SLOs to be written against, and there aren't
  any yet.
- Tracing (OpenTelemetry) — at the service's current size, metrics and logs
  are enough.
- A Redis exporter — the broker isn't a bottleneck yet; it's a one-line
  addition to `docker-compose.observability.yml` when it becomes one.
