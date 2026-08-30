# .hours

A time tracker that turns tracked hours into a city. Every category you log
time in grows a matching building — study grows schools and libraries, sport
grows gyms and stadiums — and friends push each other through shared goals.

This repository is the backend API. It implements the "core" slice of the
product (see [`docs/API_SPEC.md`](docs/API_SPEC.md) for the full staged plan):
auth, categories, a start/stop timer, a personal city that levels up from
tracked hours, friends, and paired (co-op) challenges.

## Stack

- **FastAPI** + **SQLAlchemy 2.0** (sync) + **PostgreSQL**
- **Alembic** for migrations
- **JWT** bearer auth (PyJWT + bcrypt)
- **Celery** + **Redis** for scheduled notifications and realtime fan-out
- **pytest** (SQLite in-memory for tests, no external DB needed)
- **Docker Compose** for a one-command local stack

## Quickstart (Docker)

```bash
cp .env.example .env
docker compose up --build
```

The API comes up on `http://localhost:8000`, runs pending Alembic migrations
on boot, and serves interactive docs at `http://localhost:8000/docs`.

## Local development (without Docker)

Requires Python 3.11+, [Poetry](https://python-poetry.org/), and a running
Postgres (or point `DATABASE_URL` at any Postgres instance, e.g. one from
`docker compose up -d db`).

```bash
poetry install
cp .env.example .env  # edit DATABASE_URL to point at localhost, not `db`
poetry run alembic upgrade head
poetry run uvicorn app.main:app --reload
```

### Monitoring

```bash
docker compose -f docker-compose.yml -f docker-compose.observability.yml up --build
```

Prometheus on `:9090`, Grafana on `:3000` with the ".hours API" dashboard
already provisioned. See [`docs/OBSERVABILITY.md`](docs/OBSERVABILITY.md).

### Tests & linting

```bash
poetry run pytest        # runs against an in-memory SQLite DB, no setup needed
poetry run ruff check .
poetry run ruff format .
```

## Project layout

```
app/
  core/            settings, DB session, JWT/password hashing
  models/          SQLAlchemy ORM models
  schemas/         Pydantic request/response models
  api/routes/      one module per resource (auth, users, categories, ...)
  services/        business logic (streaks, city-building leveling)
  building_families.py  static building-level catalog (not a DB table)
  city_districts.py     static district catalog, synced into city_districts
  worker/          Celery app, beat schedule, and the jobs behind the tasks
  events/          realtime event bus (Redis pub/sub or in-process)
ops/               Prometheus config and provisioned Grafana dashboards
alembic/           migrations
tests/             pytest suite, one file per resource
docs/API_SPEC.md   full staged API spec — all stages are implemented
```

## What's implemented (all stages)

- **Auth** — register / login / JWT
- **Categories** — CRUD, each tied to a `building_family`
- **Time entries** — start/stop timer, manual entries, daily summary
- **Personal city** — `CityBuilding` levels up automatically from tracked
  hours per category (see `docs/API_SPEC.md`, Приложение А, for the level
  table)
- **Streaks** — computed from daily goal completion
- **Friends** — requests, accept/decline, friends list
- **Paired tasks** — co-op challenges between friends; a building only
  "completes" once the combined (or per-participant) target is reached
- **Feed & profiles** — posts, likes, comments, public user view
- **Companies** — groups with roles (`owner`/`admin`/`member`), invite codes,
  and a shared city that grows from every member's tracked minutes
- **World leaderboard** — cached `all_time`/`weekly`/`monthly` city scores for
  public companies, refreshed lazily on read
- **Isometric layout** — districts and a deterministic tile, rotation and
  variant per building, so a city renders the same everywhere
- **Notifications** — in-app inbox fed by Celery beat: daily reminders and
  streak warnings in the user's own timezone, expiry of overdue co-op tasks
  (see [`docs/NOTIFICATIONS.md`](docs/NOTIFICATIONS.md))
- **Realtime** — `GET /api/v1/ws?token=` pushes timer, city, friend, co-op and
  notification events (see [`docs/REALTIME.md`](docs/REALTIME.md))

Every stage of the spec is now implemented.
