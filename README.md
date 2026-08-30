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
alembic/           migrations
tests/             pytest suite, one file per resource
docs/API_SPEC.md   full staged API spec — this repo implements Stages 1–6 and 8
```

## What's implemented (Stages 1–6, 8)

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

The isometric city layout (Stage 7) is documented but not yet implemented —
see the spec for why it's sequenced later.
