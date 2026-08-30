# Contributing

🇬🇧 **English** · [🇷🇺 Русский](CONTRIBUTING.ru.md)

## Setup

```bash
make install
cp .env.example .env
poetry run pre-commit install
docker compose up -d db redis   # skip this if you'd rather bring up the whole stack
make migrate
```

## Workflow

1. Branch off `main`: `feat/…`, `fix/…`, `docs/…`, `chore/…`.
2. Before pushing: `make lint` and `make test`.
3. Open a PR following the template — what, why, and how to check it.

## Code conventions

**The route owns the transaction, the service doesn't.** Services `flush()`
but never `commit()`, so the same logic is callable from an HTTP handler, a
Celery task, and a test — each owning its own transaction.

**A cache updates at the moment of the event, not on read.** `CityBuilding`,
`DailyProgress`, like counters — this is materialized state. If you're
tempted to compute an aggregate on the fly, picture it on a user with a year
of history first.

**Product config lives in code, not in a table.** Building levels and city
districts are product configuration, not user data.

**A comment explains "why," not "what."** The code already says what it
does; what's worth writing down is why this particular option was chosen and
what was rejected.

**A deliberate simplification gets said out loud.** If something is "kept
simple for now," say in a comment what condition would force it to change.

## Models and migrations

Changed a model? Make a migration:

```bash
make migration m="add something"
make migrate
poetry run alembic check    # should say "No new upgrade operations detected"
```

Two things that are easy to get burned by:

- **Reusing an existing enum type.** If the type was already created by an
  earlier revision, declare the column as
  `postgresql.ENUM(..., name="...", create_type=False)`. Otherwise the
  revision passes on a clean database and fails on any existing one.
- **Multiple heads.** Branching gives you two entries in `alembic heads`.
  Fix it before merging: re-point `down_revision` or run `alembic merge`.

CI checks both: it applies migrations one revision at a time against a real
PostgreSQL and runs a full downgrade/upgrade cycle.

## Tests

Tests run on an in-memory SQLite — no external services needed, the whole
run takes seconds.

- Background jobs are tested by calling functions from `app/worker/jobs.py`
  directly, with a stubbed "now." No broker, no Celery eager mode.
- Realtime is tested against the in-process bus (`WS_BACKEND=memory`).
- Metrics are global to the process, so assert on the delta, not the
  absolute value.

A test should fail for a reason: describe behavior, not implementation. The
name is a sentence about what's guaranteed
(`test_owner_cannot_leave_before_handover`).

## Documentation

- Changed the API contract — update [`docs/API_SPEC.md`](docs/API_SPEC.md).
- Made a decision that isn't obvious from the code — write it down there or
  in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). A month from now, "why
  it's like this" can't be recovered from the diff.
