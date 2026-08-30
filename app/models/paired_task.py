import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import BuildingFamilyKey, PairedTaskStatus, PairedTaskTargetType


class PairedTask(Base):
    __tablename__ = "paired_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    building_family: Mapped[BuildingFamilyKey] = mapped_column(
        Enum(BuildingFamilyKey, name="building_family_key"), nullable=False
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    target_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    target_type: Mapped[PairedTaskTargetType] = mapped_column(
        Enum(PairedTaskTargetType, name="paired_task_target_type"), nullable=False
    )
    status: Mapped[PairedTaskStatus] = mapped_column(
        Enum(PairedTaskStatus, name="paired_task_status"), default=PairedTaskStatus.active, nullable=False
    )
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PairedTaskParticipant(Base):
    __tablename__ = "paired_task_participants"
    __table_args__ = (UniqueConstraint("paired_task_id", "user_id", name="uq_paired_task_participant"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    paired_task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("paired_tasks.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    minutes_logged: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
