import uuid

from pydantic import BaseModel, ConfigDict

from app.models.enums import BuildingFamilyKey


class CityBuildingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    building_family: BuildingFamilyKey
    level: int
    total_minutes: int
    district_id: uuid.UUID | None = None
    position_x: int = 0
    position_y: int = 0
    rotation: int = 0
    variant: int = 1


class CityOut(BaseModel):
    buildings: list[CityBuildingOut]


class CityDistrictOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    building_family: BuildingFamilyKey | None
    title: str
    grid_x: int
    grid_y: int
    grid_w: int
    grid_h: int


class BuildingLevelOut(BaseModel):
    level: int
    title: str
    hours_threshold: int


class BuildingFamilyOut(BaseModel):
    key: BuildingFamilyKey
    title: str
    levels: list[BuildingLevelOut]
