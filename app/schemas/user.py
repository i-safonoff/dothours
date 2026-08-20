import uuid

from pydantic import BaseModel, ConfigDict, Field


class UserOut(BaseModel):
    """Private view — includes email. Only ever returned for the caller themself."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str
    initials: str
    avatar_color: str
    status: str
    daily_goal_minutes: int


class UserPublic(BaseModel):
    """Public view — what a friend, feed reader, or profile visitor sees."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    initials: str
    avatar_color: str
    status: str


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    status: str | None = Field(default=None, max_length=140)
    avatar_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    daily_goal_minutes: int | None = Field(default=None, ge=5, le=1440)


class UserStats(BaseModel):
    today_minutes: int
    streak: int
    longest_streak: int
