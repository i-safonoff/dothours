import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CompanyRole


class CompanyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str | None = Field(default=None, min_length=2, max_length=60, pattern=r"^[a-z0-9-]+$")
    description: str = Field(default="", max_length=500)
    avatar_color: str = Field(default="#9B6BFF", pattern=r"^#[0-9A-Fa-f]{6}$")
    is_public: bool = False


class CompanyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    avatar_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    is_public: bool | None = None


class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    description: str
    avatar_color: str
    is_public: bool
    created_by: uuid.UUID
    created_at: datetime
    members_count: int = 0
    my_role: CompanyRole | None = None


class CompanyMemberOut(BaseModel):
    user_id: uuid.UUID
    name: str
    initials: str
    avatar_color: str
    role: CompanyRole
    contribution_minutes_total: int
    joined_at: datetime


class CompanyMemberUpdate(BaseModel):
    role: CompanyRole


class CompanyInviteCreate(BaseModel):
    expires_in_hours: int = Field(default=72, ge=1, le=24 * 30)
    max_uses: int = Field(default=10, ge=1, le=1000)


class CompanyInviteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    code: str
    expires_at: datetime
    max_uses: int
    uses_count: int


class CompanyJoin(BaseModel):
    invite_code: str = Field(min_length=4, max_length=16)
