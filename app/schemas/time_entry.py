import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import TimeEntrySource


class TimeEntryStart(BaseModel):
    category_id: uuid.UUID
    note: str | None = Field(default=None, max_length=280)
    paired_task_id: uuid.UUID | None = None


class TimeEntryManualCreate(BaseModel):
    category_id: uuid.UUID
    started_at: datetime
    ended_at: datetime
    note: str | None = Field(default=None, max_length=280)
    paired_task_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def check_order(self) -> "TimeEntryManualCreate":
        if self.ended_at <= self.started_at:
            raise ValueError("ended_at must be after started_at")
        return self


class TimeEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category_id: uuid.UUID
    started_at: datetime
    ended_at: datetime | None
    duration_seconds: int | None
    source: TimeEntrySource
    note: str | None
    paired_task_id: uuid.UUID | None


class TimeEntrySummary(BaseModel):
    period: str
    date: str
    total_minutes: int
    by_category: dict[uuid.UUID, int]
