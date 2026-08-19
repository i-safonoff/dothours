import uuid

from pydantic import BaseModel, ConfigDict

from app.models.enums import BuildingFamilyKey


class CityBuildingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    building_family: BuildingFamilyKey
    level: int
    total_minutes: int


class CityOut(BaseModel):
    buildings: list[CityBuildingOut]


class BuildingLevelOut(BaseModel):
    level: int
    title: str
    hours_threshold: int


class BuildingFamilyOut(BaseModel):
    key: BuildingFamilyKey
    title: str
    levels: list[BuildingLevelOut]
