import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.building_families import level_for_hours
from app.models.city import CityBuilding, DailyProgress
from app.models.company import CompanyMembership
from app.models.enums import OwnerType, PairedTaskStatus, PairedTaskTargetType
from app.models.paired_task import PairedTask, PairedTaskParticipant
from app.models.user import User


def apply_completed_entry(
    db: Session,
    user: User,
    building_family: str,
    entry_date: date,
    minutes: int,
    paired_task_id: uuid.UUID | None = None,
) -> None:
    """Update the daily progress and city-building caches after a time entry stops."""
    _upsert_daily_progress(db, user, entry_date, minutes)
    _increment_city_building(db, OwnerType.user, user.id, building_family, minutes)
    _apply_company_minutes(db, user.id, building_family, minutes)
    if paired_task_id is not None:
        _apply_paired_task_minutes(db, paired_task_id, user.id, minutes)


def _apply_company_minutes(db: Session, user_id: uuid.UUID, building_family: str, minutes: int) -> None:
    """The same minutes grow the city of every company the user belongs to."""
    memberships = db.scalars(select(CompanyMembership).where(CompanyMembership.user_id == user_id)).all()
    for membership in memberships:
        membership.contribution_minutes_total += minutes
        _increment_city_building(db, OwnerType.company, membership.company_id, building_family, minutes)


def _apply_paired_task_minutes(db: Session, paired_task_id: uuid.UUID, user_id: uuid.UUID, minutes: int) -> None:
    task = db.get(PairedTask, paired_task_id)
    if task is None or task.status != PairedTaskStatus.active:
        return

    participant = db.scalar(
        select(PairedTaskParticipant).where(
            PairedTaskParticipant.paired_task_id == paired_task_id, PairedTaskParticipant.user_id == user_id
        )
    )
    if participant is None:
        return

    participant.minutes_logged += minutes
    db.flush()

    all_participants = db.scalars(
        select(PairedTaskParticipant).where(PairedTaskParticipant.paired_task_id == paired_task_id)
    ).all()

    if task.target_type == PairedTaskTargetType.combined:
        reached = sum(p.minutes_logged for p in all_participants) >= task.target_minutes
    else:
        reached = all(p.minutes_logged >= task.target_minutes for p in all_participants)

    if reached:
        task.status = PairedTaskStatus.completed
        task.completed_at = datetime.now(UTC)
        db.flush()


def _upsert_daily_progress(db: Session, user: User, entry_date: date, minutes: int) -> DailyProgress:
    progress = db.scalar(
        select(DailyProgress).where(DailyProgress.user_id == user.id, DailyProgress.date == entry_date)
    )
    if progress is None:
        progress = DailyProgress(
            user_id=user.id,
            date=entry_date,
            total_minutes=0,
            goal_minutes=user.daily_goal_minutes,
        )
        db.add(progress)

    progress.total_minutes += minutes
    progress.goal_minutes = user.daily_goal_minutes
    progress.goal_met = progress.total_minutes >= progress.goal_minutes
    db.flush()
    return progress


def _increment_city_building(
    db: Session, owner_type: OwnerType, owner_id: uuid.UUID, building_family: str, minutes: int
) -> CityBuilding:
    building = db.scalar(
        select(CityBuilding).where(
            CityBuilding.owner_type == owner_type,
            CityBuilding.owner_id == owner_id,
            CityBuilding.building_family == building_family,
        )
    )
    if building is None:
        building = CityBuilding(
            owner_type=owner_type,
            owner_id=owner_id,
            building_family=building_family,
            total_minutes=0,
            level=1,
        )
        db.add(building)

    building.total_minutes += minutes
    building.level = level_for_hours(building_family, building.total_minutes / 60)
    db.flush()
    return building


def compute_streak(db: Session, user_id: uuid.UUID) -> tuple[int, int]:
    """(current_streak, longest_streak) in consecutive goal-met days.

    Computed on read rather than cached — fine at this scale; a background
    worker recomputing a cached value would be the next step if this ever
    shows up in profiling.
    """
    rows = db.scalars(select(DailyProgress).where(DailyProgress.user_id == user_id).order_by(DailyProgress.date)).all()
    by_date = {row.date: row for row in rows}

    today = date.today()
    cursor = today
    if cursor not in by_date or not by_date[cursor].goal_met:
        cursor -= timedelta(days=1)

    current = 0
    while cursor in by_date and by_date[cursor].goal_met:
        current += 1
        cursor -= timedelta(days=1)

    longest = 0
    streak = 0
    prev_date: date | None = None
    for row in rows:
        if row.goal_met:
            streak = streak + 1 if prev_date == row.date - timedelta(days=1) else 1
            longest = max(longest, streak)
        else:
            streak = 0
        prev_date = row.date

    return current, longest
