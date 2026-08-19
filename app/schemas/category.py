import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import BuildingFamilyKey, ShapeKind


class CategoryCreate(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    shape: ShapeKind
    building_family: BuildingFamilyKey
    minutes_per_day_target: int = Field(default=30, ge=5, le=1440)


class CategoryUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=80)
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    shape: ShapeKind | None = None
    minutes_per_day_target: int | None = Field(default=None, ge=5, le=1440)
    archived: bool | None = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    color: str
    shape: ShapeKind
    building_family: BuildingFamilyKey
    minutes_per_day_target: int
    archived: bool
