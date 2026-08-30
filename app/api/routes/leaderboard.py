import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.company import Company, CompanyMembership
from app.models.enums import LeaderboardPeriod
from app.models.leaderboard import CityScore
from app.models.user import User
from app.schemas.leaderboard import CompanyRankOut, LeaderboardEntry, LeaderboardPage
from app.services.scoring import ensure_fresh_scores, period_key

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])

NEIGHBORS_RADIUS = 2


def _entries(db: Session, period: LeaderboardPeriod, key: str, limit: int, offset: int) -> list[LeaderboardEntry]:
    member_counts = (
        select(CompanyMembership.company_id, func.count().label("members_count"))
        .group_by(CompanyMembership.company_id)
        .subquery()
    )
    rows = db.execute(
        select(CityScore, Company, func.coalesce(member_counts.c.members_count, 0))
        .join(Company, Company.id == CityScore.company_id)
        .outerjoin(member_counts, member_counts.c.company_id == Company.id)
        .where(CityScore.period == period, CityScore.period_key == key)
        .order_by(CityScore.rank)
        .limit(limit)
        .offset(offset)
    ).all()
    return [
        LeaderboardEntry(
            rank=score.rank,
            score=score.score,
            company_id=company.id,
            name=company.name,
            slug=company.slug,
            avatar_color=company.avatar_color,
            members_count=members_count,
        )
        for score, company, members_count in rows
    ]


def _total(db: Session, period: LeaderboardPeriod, key: str) -> int:
    return (
        db.scalar(
            select(func.count()).select_from(CityScore).where(CityScore.period == period, CityScore.period_key == key)
        )
        or 0
    )


@router.get("/companies", response_model=LeaderboardPage)
def get_leaderboard(
    period: LeaderboardPeriod = LeaderboardPeriod.all_time,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LeaderboardPage:
    """Public companies only — a private city stays out of the world ranking."""
    ensure_fresh_scores(db, period)
    key = period_key(period)
    return LeaderboardPage(
        period=period,
        period_key=key,
        total=_total(db, period, key),
        entries=_entries(db, period, key, limit, offset),
    )


@router.get("/companies/{company_id}", response_model=CompanyRankOut)
def get_company_rank(
    company_id: uuid.UUID,
    period: LeaderboardPeriod = LeaderboardPeriod.all_time,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CompanyRankOut:
    company = db.get(Company, company_id)
    if company is None or not company.is_public:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Company is not ranked (private companies are excluded)"
        )

    ensure_fresh_scores(db, period)
    key = period_key(period)
    score = db.scalar(
        select(CityScore).where(
            CityScore.company_id == company_id, CityScore.period == period, CityScore.period_key == key
        )
    )
    if score is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company is not ranked")

    window_start = max(score.rank - NEIGHBORS_RADIUS, 1)
    neighbors = _entries(db, period, key, limit=NEIGHBORS_RADIUS * 2 + 1, offset=window_start - 1)
    return CompanyRankOut(
        period=period,
        period_key=key,
        rank=score.rank,
        score=score.score,
        total=_total(db, period, key),
        neighbors=neighbors,
    )
