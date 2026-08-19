import uuid

from pydantic import BaseModel, ConfigDict, Field


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str
    initials: str
    daily_goal_minutes: int


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    daily_goal_minutes: int | None = Field(default=None, ge=5, le=1440)


class UserStats(BaseModel):
    today_minutes: int
    streak: int
    longest_streak: int
