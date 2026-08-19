import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, Integer, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import BuildingFamilyKey, OwnerType


class CityBuilding(Base):
    """Materialized state of a building — recomputed when a time entry stops.

    Not derived on every read on purpose: summing all time_entries per
    request does not scale once a user has months of history.
    """

    __tablename__ = "city_buildings"
    __table_args__ = (UniqueConstraint("owner_type", "owner_id", "building_family", name="uq_city_building_owner"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_type: Mapped[OwnerType] = mapped_column(Enum(OwnerType, name="owner_type"), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    building_family: Mapped[BuildingFamilyKey] = mapped_column(
        Enum(BuildingFamilyKey, name="building_family_key"), nullable=False
    )
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    total_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DailyProgress(Base):
    __tablename__ = "daily_progress"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_daily_progress_user_date"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    total_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    goal_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    goal_met: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
