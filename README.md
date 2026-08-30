# .hours

[![CI](https://github.com/i-safonoff/dothours/actions/workflows/ci.yml/badge.svg)](https://github.com/i-safonoff/dothours/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

🇬🇧 **English** · [🇷🇺 Русский](README.ru.md)

**A time tracker that turns hours you've logged into a city.**

Every category you track time in grows its own building: study grows schools
and libraries, sport grows gyms and stadiums. Friends push each other through
shared challenges, companies build a city together, and the best cities make
the world leaderboard. Gamification isn't decoration on top of the tracker —
it's the reason to open the app again tomorrow.

This is the backend: REST API + WebSocket. The full staged plan lives in
[`docs/API_SPEC.md`](docs/API_SPEC.md) — every stage is implemented.

---

## Contents

- [Features](#features)
- [Stack](#stack)
- [Quickstart](#quickstart)
- [Local development](#local-development)
- [API overview](#api-overview)
- [Monitoring](#monitoring)
- [Project layout](#project-layout)
- [Tests and quality](#tests-and-quality)
- [Documentation](#documentation)
- [What's next](#whats-next)

---

## Features

| What | How it works |
|---|---|
| **Auth** | Register, log in, JWT bearer; avatar color is assigned deterministically from the email |
| **Categories** | CRUD, each tied to a building family, a color, a shape, and a daily goal |
| **Tracker** | Start/stop timer, manual entries, a daily summary by category |
| **Personal city** | A building grows from tracked hours in its category and levels up against a threshold table |
| **Streaks** | Computed from the days a daily goal was met |
| **Friends** | Requests, accept/decline, a friends list with their minutes tracked today |
| **Paired tasks** | Co-op challenges, credited either by combined total or per participant |
| **Feed & profiles** | Posts, likes, comments, a public profile that never leaks an email |
| **Companies** | `owner`/`admin`/`member` roles, invite codes, a shared city grown from every member's minutes |
| **World leaderboard** | Cached city scores: `all_time`, `weekly`, `monthly` |
| **Isometric layout** | Districts and a deterministic tile, rotation and variant per building |
| **Notifications** | In-app inbox: reminders and streak warnings timed to the user's own timezone |
| **Realtime** | WebSocket events for the timer, the city, friends, tasks, and notifications |
| **Monitoring** | `/metrics` for Prometheus plus a ready-made Grafana dashboard |

## Stack

- **FastAPI** + **SQLAlchemy 2.0** (sync session) + **PostgreSQL**
- **Alembic** — migrations
- **JWT** (PyJWT + bcrypt) — authentication
- **Celery** + **Redis** — background jobs and realtime pub/sub
- **Prometheus** + **Grafana** — metrics and dashboards
- **pytest** — tests on an in-memory SQLite, no external services needed
- **ruff** — linting and formatting
- **Docker Compose** — the whole stack in one command

## Quickstart

```bash
git clone https://github.com/i-safonoff/dothours.git
cd dothours
cp .env.example .env
make up
```

This brings up the API, PostgreSQL, Redis, the Celery worker, and beat.
Migrations run automatically on startup.

- API — http://localhost:8000
- Interactive docs — http://localhost:8000/docs
- Liveness check — http://localhost:8000/health

With monitoring:

```bash
make stack-up
```

- Prometheus — http://localhost:9090
- Grafana — http://localhost:3000 (`admin` / `admin`, the ".hours API" dashboard is already there)

## Local development

You'll need Python 3.11+, [Poetry](https://python-poetry.org/), and a running
PostgreSQL and Redis (easiest: `docker compose up -d db redis`).

```bash
make install
cp .env.example .env        # point DATABASE_URL at localhost, not db
make migrate
make run                    # API with auto-reload
```

Background jobs, each in its own terminal:

```bash
make worker
make beat
```

All commands: `make help`. Worth installing the hooks before your first commit:

```bash
poetry run pre-commit install
```

### Environment variables

| Variable | Default | What it's for |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg2://…@db:5432/dothours` | Database connection |
| `JWT_SECRET_KEY` | — | Token signing key; **make sure to change this** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `10080` | Token lifetime |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | Allowed origins |
| `CELERY_BROKER_URL` | `redis://redis:6379/0` | Celery broker |
| `WS_BACKEND` | `memory` | `redis` — fan-out across processes, `memory` — inside one |
| `LEADERBOARD_TTL_SECONDS` | `300` | How long a cached leaderboard row is served |
| `METRICS_ENABLED` | `true` | Turns `/metrics` on |

## API overview

Everything lives under `/api/v1`; everything except `/auth/*` needs an
`Authorization: Bearer <token>` header.

| Group | Endpoints |
|---|---|
| Auth | `POST /auth/register`, `POST /auth/login`, `GET /auth/me` |
| Profile | `GET/PATCH /users/me`, `GET /users/me/stats`, `GET /users/search`, `GET /users/{id}` |
| Categories | `GET/POST /categories`, `PATCH/DELETE /categories/{id}` |
| Tracker | `POST /time-entries/start`, `POST /time-entries/{id}/stop`, `GET /time-entries`, `GET /time-entries/summary` |
| City | `GET /city/me`, `GET /city/districts`, `GET /building-families` |
| Friends | `GET /friends`, `POST /friends/requests`, `POST /friends/requests/{id}/accept` |
| Paired tasks | `POST /paired-tasks`, `GET /paired-tasks`, `GET /paired-tasks/{id}` |
| Feed | `POST/GET /posts`, `POST/DELETE /posts/{id}/like`, `GET/POST /posts/{id}/comments` |
| Companies | `POST/GET /companies`, `POST /companies/join`, `GET /companies/{id}/members`, `GET /companies/{id}/city` |
| Leaderboard | `GET /leaderboard/companies`, `GET /leaderboard/companies/{id}` |
| Notifications | `GET /notifications`, `POST /notifications/{id}/read`, `POST /notifications/read-all` |
| Realtime | `GET /ws?token=<JWT>` |

Full request/response bodies live in the OpenAPI docs at `/docs`.

## Monitoring

`GET /metrics` exposes Prometheus metrics: RED metrics over HTTP plus domain
counters — tracked minutes by building family, timer starts and stops,
building level-ups, open sockets, and Celery task runs and durations. Every
response carries `X-Request-ID`, and every request writes one JSON log line.

Details and the full metric table — [`docs/OBSERVABILITY.md`](docs/OBSERVABILITY.md).

## Project layout

```
app/
  api/routes/           HTTP handlers, one module per resource
  services/             business logic over a DB session
  models/                ORM models
  schemas/               Pydantic contracts
  worker/                Celery: jobs.py — logic, tasks.py — wrappers
  events/                the realtime event bus
  core/                  settings, DB, JWT, metrics, logs, timezones
  building_families.py   building-level catalog (config, not a table)
  city_districts.py      district catalog, synced into city_districts
alembic/                 migrations
ops/                     Prometheus config and Grafana provisioning
tests/                   pytest, one file per resource
docs/                    spec and architecture notes
```

## Tests and quality

```bash
make test     # pytest on an in-memory SQLite
make lint     # ruff check + format --check
make cov      # coverage with an HTML report
```

95 tests, ~94% coverage. No external services needed to run them: tests run
on an in-memory SQLite, background jobs are called directly with a stubbed
"now", and realtime goes through the in-process bus.

CI runs lint, tests, a Docker build, and a separate migrations check against
a real PostgreSQL on every PR: one revision at a time, plus `alembic check`
and a full downgrade/upgrade cycle. That catches bugs invisible on a clean
database — like a revision re-creating a type that already exists.

## Documentation

| Doc | About |
|---|---|
| [`docs/API_SPEC.md`](docs/API_SPEC.md) | The staged spec and the decisions made along the way |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System diagram, layers, key trade-offs |
| [`docs/REALTIME.md`](docs/REALTIME.md) | WebSocket: protocol, events, channels |
| [`docs/NOTIFICATIONS.md`](docs/NOTIFICATIONS.md) | Notifications and the background job schedule |
| [`docs/OBSERVABILITY.md`](docs/OBSERVABILITY.md) | Metrics, logs, Prometheus and Grafana |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | How to work in this repository |

## What's next

- External notification channels: email and push on top of the rows that already exist
- A streak cache, once reading it starts to cost something
- A Redis exporter and Prometheus alerts, once there are real SLOs to alert on
- Tracing (OpenTelemetry), if the service outgrows metrics and logs

## License

[MIT](LICENSE)
