"""City scores for the world leaderboard (Этап 6).

`weekly` / `monthly` are *slices over the same city*, not a reset: a company's
buildings keep growing forever, while a period score is computed from the
minutes its members logged inside that period. So a young company can win a
week without ever catching up on `all_time`.

Scores are cached in `city_scores` and refreshed lazily on read once they go
stale (`settings.leaderboard_ttl_seconds`). `recompute_scores` is deliberately
a plain function so a Celery beat job can call it directly later.
"""

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.building_families import FAMILY_WEIGHTS, level_for_hours
from app.core.config import get_settings
from app.models.category import Category
from app.models.city import CityBuilding, DailyProgress
from app.models.company import Company, CompanyMembership
from app.models.enums import LeaderboardPeriod, OwnerType, PairedTaskStatus
from app.models.leaderboard import CityScore
from app.models.paired_task import PairedTask, PairedTaskParticipant
from app.models.time_entry import TimeEntry
from app.services.tracking import compute_streak

PAIRED_TASK_POINTS = 50
STREAK_POINTS = 2


def period_key(period: LeaderboardPeriod, today: date | None = None) -> str:
    today = today or date.today()
    if period == LeaderboardPeriod.weekly:
        iso_year, iso_week, _ = today.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"
    if period == LeaderboardPeriod.monthly:
        return f"{today:%Y-%m}"
    return "all"


def period_range(period: LeaderboardPeriod, today: date | None = None) -> tuple[datetime, datetime] | None:
    """Half-open [start, end) bounds of the current period, or None for all-time."""
    today = today or date.today()
    if period == LeaderboardPeriod.weekly:
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=7)
    elif period == LeaderboardPeriod.monthly:
        start_date = today.replace(day=1)
        end_date = (start_date + timedelta(days=32)).replace(day=1)
    else:
        return None
    return (
        datetime.combine(start_date, datetime.min.time(), tzinfo=UTC),
        datetime.combine(end_date, datetime.min.time(), tzinfo=UTC),
    )


def _member_ids(db: Session, company_id: uuid.UUID) -> list[uuid.UUID]:
    return list(db.scalars(select(CompanyMembership.user_id).where(CompanyMembership.company_id == company_id)).all())


def _building_points_all_time(db: Session, company_id: uuid.UUID) -> float:
    buildings = db.scalars(
        select(CityBuilding).where(CityBuilding.owner_type == OwnerType.company, CityBuilding.owner_id == company_id)
    ).all()
    return sum(b.level**1.5 * FAMILY_WEIGHTS[b.building_family.value] for b in buildings)


def _building_points_for_range(db: Session, member_ids: list[uuid.UUID], window: tuple[datetime, datetime]) -> float:
    """Levels a company would have if only this period's minutes counted."""
    start, end = window
    rows = db.execute(
        select(Category.building_family, func.sum(TimeEntry.duration_seconds))
        .join(Category, Category.id == TimeEntry.category_id)
        .where(
            TimeEntry.user_id.in_(member_ids),
            TimeEntry.ended_at.is_not(None),
            TimeEntry.started_at >= start,
            TimeEntry.started_at < end,
        )
        .group_by(Category.building_family)
    ).all()

    points = 0.0
    for building_family, total_seconds in rows:
        key = building_family.value if hasattr(building_family, "value") else str(building_family)
        level = level_for_hours(key, (total_seconds or 0) / 3600)
        points += level**1.5 * FAMILY_WEIGHTS[key]
    return points


def _paired_task_points(db: Session, member_ids: list[uuid.UUID], window: tuple[datetime, datetime] | None) -> float:
    """Completed co-op tasks whose participants are all members of this company."""
    if not member_ids:
        return 0.0

    stmt = select(PairedTask).where(PairedTask.status == PairedTaskStatus.completed)
    if window is not None:
        start, end = window
        stmt = stmt.where(
            PairedTask.completed_at.is_not(None), PairedTask.completed_at >= start, PairedTask.completed_at < end
        )

    member_set = set(member_ids)
    count = 0
    for task in db.scalars(stmt).all():
        participants = set(
            db.scalars(
                select(PairedTaskParticipant.user_id).where(PairedTaskParticipant.paired_task_id == task.id)
            ).all()
        )
        if participants and participants <= member_set:
            count += 1
    return count * PAIRED_TASK_POINTS


def _streak_points(db: Session, member_ids: list[uuid.UUID], window: tuple[datetime, datetime] | None) -> float:
    if not member_ids:
        return 0.0

    if window is None:
        return sum(compute_streak(db, user_id)[1] for user_id in member_ids) * STREAK_POINTS

    start, end = window
    goal_met_days = (
        db.scalar(
            select(func.count())
            .select_from(DailyProgress)
            .where(
                DailyProgress.user_id.in_(member_ids),
                DailyProgress.goal_met.is_(True),
                DailyProgress.date >= start.date(),
                DailyProgress.date < end.date(),
            )
        )
        or 0
    )
    return goal_met_days * STREAK_POINTS


def compute_company_score(db: Session, company_id: uuid.UUID, period: LeaderboardPeriod) -> float:
    window = period_range(period)
    member_ids = _member_ids(db, company_id)

    if window is None:
        building_points = _building_points_all_time(db, company_id)
    else:
        building_points = _building_points_for_range(db, member_ids, window) if member_ids else 0.0

    return round(
        building_points + _paired_task_points(db, member_ids, window) + _streak_points(db, member_ids, window), 2
    )


def recompute_scores(db: Session, period: LeaderboardPeriod) -> list[CityScore]:
    """Rescore every public company for `period` and renumber the ranks."""
    key = period_key(period)
    companies = db.scalars(select(Company).where(Company.is_public.is_(True))).all()

    scored = sorted(
        ((company, compute_company_score(db, company.id, period)) for company in companies),
        key=lambda pair: pair[1],
        reverse=True,
    )

    existing = {
        row.company_id: row
        for row in db.scalars(select(CityScore).where(CityScore.period == period, CityScore.period_key == key)).all()
    }

    rows: list[CityScore] = []
    for rank, (company, score) in enumerate(scored, start=1):
        row = existing.pop(company.id, None)
        if row is None:
            row = CityScore(company_id=company.id, period=period, period_key=key)
            db.add(row)
        row.score = score
        row.rank = rank
        row.computed_at = datetime.now(UTC)
        rows.append(row)

    for stale in existing.values():  # company went private or was deleted
        db.delete(stale)

    db.commit()
    return rows


def ensure_fresh_scores(db: Session, period: LeaderboardPeriod) -> None:
    """Recompute if the cached rows for this period are missing or past their TTL."""
    key = period_key(period)
    newest = db.scalar(
        select(func.max(CityScore.computed_at)).where(CityScore.period == period, CityScore.period_key == key)
    )
    if newest is not None:
        computed_at = newest if newest.tzinfo else newest.replace(tzinfo=UTC)
        ttl = timedelta(seconds=get_settings().leaderboard_ttl_seconds)
        if datetime.now(UTC) - computed_at < ttl:
            return
    recompute_scores(db, period)
