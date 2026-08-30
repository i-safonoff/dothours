import uuid

from pydantic import BaseModel

from app.models.enums import LeaderboardPeriod


class LeaderboardEntry(BaseModel):
    rank: int
    score: float
    company_id: uuid.UUID
    name: str
    slug: str
    avatar_color: str
    members_count: int


class LeaderboardPage(BaseModel):
    period: LeaderboardPeriod
    period_key: str
    total: int
    entries: list[LeaderboardEntry]


class CompanyRankOut(BaseModel):
    period: LeaderboardPeriod
    period_key: str
    rank: int
    score: float
    total: int
    neighbors: list[LeaderboardEntry]
