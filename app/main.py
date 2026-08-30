import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import func, select

from app.api.router import api_router
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.logging import RequestContextMiddleware, configure_logging
from app.core.metrics import sync_active_timers
from app.models.time_entry import TimeEntry

settings = get_settings()
logger = logging.getLogger("dothours.startup")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    _sync_active_timer_gauge()
    yield


def _sync_active_timer_gauge() -> None:
    """Restore the gauge from the database — a restart must not leave it stale.

    Best effort on purpose: an unreachable database is the health check's
    problem, not a reason to refuse to boot.
    """
    try:
        with SessionLocal() as db:
            running = db.scalar(select(func.count()).select_from(TimeEntry).where(TimeEntry.ended_at.is_(None)))
        sync_active_timers(running or 0)
    except Exception as exc:  # noqa: BLE001 -- metrics must never block startup
        logger.warning("Could not sync the active-timer gauge on startup: %s", exc)


app = FastAPI(title=".hours API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestContextMiddleware)

app.include_router(api_router)

if settings.metrics_enabled:
    Instrumentator(
        should_group_status_codes=False,
        excluded_handlers=["/metrics", "/health"],
    ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
