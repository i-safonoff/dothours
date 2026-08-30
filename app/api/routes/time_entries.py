import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.metrics import active_timers, minutes_tracked_total, timers_started_total, timers_stopped_total
from app.events import types
from app.events.bus import bus, user_channel
from app.models.category import Category
from app.models.enums import TimeEntrySource
from app.models.time_entry import TimeEntry
from app.models.user import User
from app.schemas.time_entry import TimeEntryManualCreate, TimeEntryOut, TimeEntryStart, TimeEntrySummary
from app.services.tracking import apply_completed_entry

router = APIRouter(prefix="/time-entries", tags=["time-entries"])


def _as_utc(value: datetime) -> datetime:
    """SQLite drops tzinfo on round-trip; Postgres keeps it. Normalize either way."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _get_owned_category(db: Session, current_user: User, category_id: uuid.UUID) -> Category:
    category = db.get(Category, category_id)
    if category is None or category.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return category


def _get_owned_entry(db: Session, current_user: User, entry_id: uuid.UUID) -> TimeEntry:
    entry = db.get(TimeEntry, entry_id)
    if entry is None or entry.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Time entry not found")
    return entry


@router.post("/start", response_model=TimeEntryOut, status_code=status.HTTP_201_CREATED)
def start_entry(
    payload: TimeEntryStart,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TimeEntryOut:
    active = db.scalar(select(TimeEntry).where(TimeEntry.user_id == current_user.id, TimeEntry.ended_at.is_(None)))
    if active is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A timer is already running")

    _get_owned_category(db, current_user, payload.category_id)

    entry = TimeEntry(
        user_id=current_user.id,
        category_id=payload.category_id,
        paired_task_id=payload.paired_task_id,
        started_at=datetime.now(UTC),
        source=TimeEntrySource.timer,
        note=payload.note,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    timers_started_total.inc()
    active_timers.inc()
    bus.publish(user_channel(current_user.id), types.TIMER_STARTED, {"entry_id": str(entry.id)})
    return TimeEntryOut.model_validate(entry)


@router.post("/{entry_id}/stop", response_model=TimeEntryOut)
def stop_entry(
    entry_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TimeEntryOut:
    entry = _get_owned_entry(db, current_user, entry_id)
    if entry.ended_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Time entry already stopped")

    entry.ended_at = datetime.now(UTC)
    entry.duration_seconds = int((entry.ended_at - _as_utc(entry.started_at)).total_seconds())

    category = db.get(Category, entry.category_id)
    minutes = entry.duration_seconds // 60
    if minutes > 0:
        apply_completed_entry(
            db,
            current_user,
            category.building_family.value,
            _as_utc(entry.started_at).date(),
            minutes,
            paired_task_id=entry.paired_task_id,
        )
        minutes_tracked_total.labels(category.building_family.value, TimeEntrySource.timer.value).inc(minutes)

    db.commit()
    db.refresh(entry)

    timers_stopped_total.inc()
    active_timers.dec()
    bus.publish(
        user_channel(current_user.id),
        types.TIMER_STOPPED,
        {"entry_id": str(entry.id), "minutes": minutes},
    )
    return TimeEntryOut.model_validate(entry)


@router.get("/active", response_model=TimeEntryOut | None)
def get_active_entry(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TimeEntryOut | None:
    entry = db.scalar(select(TimeEntry).where(TimeEntry.user_id == current_user.id, TimeEntry.ended_at.is_(None)))
    return TimeEntryOut.model_validate(entry) if entry else None


@router.post("", response_model=TimeEntryOut, status_code=status.HTTP_201_CREATED)
def create_manual_entry(
    payload: TimeEntryManualCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TimeEntryOut:
    category = _get_owned_category(db, current_user, payload.category_id)

    duration_seconds = int((payload.ended_at - payload.started_at).total_seconds())
    entry = TimeEntry(
        user_id=current_user.id,
        category_id=payload.category_id,
        paired_task_id=payload.paired_task_id,
        started_at=payload.started_at,
        ended_at=payload.ended_at,
        duration_seconds=duration_seconds,
        source=TimeEntrySource.manual,
        note=payload.note,
    )
    db.add(entry)

    minutes = duration_seconds // 60
    if minutes > 0:
        apply_completed_entry(
            db,
            current_user,
            category.building_family.value,
            payload.started_at.date(),
            minutes,
            paired_task_id=payload.paired_task_id,
        )
        minutes_tracked_total.labels(category.building_family.value, TimeEntrySource.manual.value).inc(minutes)

    db.commit()
    db.refresh(entry)
    return TimeEntryOut.model_validate(entry)


@router.get("", response_model=list[TimeEntryOut])
def list_entries(
    date_from: datetime | None = Query(default=None, alias="from"),
    date_to: datetime | None = Query(default=None, alias="to"),
    category_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TimeEntryOut]:
    stmt = select(TimeEntry).where(TimeEntry.user_id == current_user.id)
    if date_from is not None:
        stmt = stmt.where(TimeEntry.started_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(TimeEntry.started_at <= date_to)
    if category_id is not None:
        stmt = stmt.where(TimeEntry.category_id == category_id)

    entries = db.scalars(stmt.order_by(TimeEntry.started_at.desc())).all()
    return [TimeEntryOut.model_validate(e) for e in entries]


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(
    entry_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    entry = _get_owned_entry(db, current_user, entry_id)
    was_running = entry.ended_at is None
    db.delete(entry)
    db.commit()

    if was_running:
        active_timers.dec()


@router.get("/summary", response_model=TimeEntrySummary)
def get_summary(
    entry_date: date = Query(default_factory=date.today, alias="date"),
    period: str = Query(default="day", pattern="^(day)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TimeEntrySummary:
    day_start = datetime.combine(entry_date, datetime.min.time(), tzinfo=UTC)
    day_end = datetime.combine(entry_date, datetime.max.time(), tzinfo=UTC)

    entries = db.scalars(
        select(TimeEntry).where(
            TimeEntry.user_id == current_user.id,
            TimeEntry.started_at >= day_start,
            TimeEntry.started_at <= day_end,
            TimeEntry.ended_at.is_not(None),
        )
    ).all()

    by_category: dict[uuid.UUID, int] = {}
    for entry in entries:
        by_category[entry.category_id] = by_category.get(entry.category_id, 0) + (entry.duration_seconds or 0) // 60

    return TimeEntrySummary(
        period=period,
        date=entry_date.isoformat(),
        total_minutes=sum(by_category.values()),
        by_category=by_category,
    )
