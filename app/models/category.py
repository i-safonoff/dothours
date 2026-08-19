import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import BuildingFamilyKey, ShapeKind

if TYPE_CHECKING:
    from app.models.time_entry import TimeEntry
    from app.models.user import User


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(80), nullable=False)
    color: Mapped[str] = mapped_column(String(7), nullable=False)
    shape: Mapped[ShapeKind] = mapped_column(Enum(ShapeKind, name="shape_kind"), nullable=False)
    building_family: Mapped[BuildingFamilyKey] = mapped_column(
        Enum(BuildingFamilyKey, name="building_family_key"), nullable=False
    )
    minutes_per_day_target: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    owner: Mapped["User"] = relationship(back_populates="categories")
    time_entries: Mapped[list["TimeEntry"]] = relationship(back_populates="category", cascade="all, delete-orphan")
