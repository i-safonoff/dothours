import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import LeaderboardPeriod


class CityScore(Base):
    """Cached ranking row, recomputed in bulk — never written on the hot path.

    `period_key` pins the row to a concrete week/month ("2026-W35", "2026-08")
    so past periods stay readable; `all_time` always uses the key "all".
    """

    __tablename__ = "city_scores"
    __table_args__ = (UniqueConstraint("company_id", "period", "period_key", name="uq_city_score_period"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True
    )
    period: Mapped[LeaderboardPeriod] = mapped_column(
        Enum(LeaderboardPeriod, name="leaderboard_period"), nullable=False
    )
    period_key: Mapped[str] = mapped_column(String(16), nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
