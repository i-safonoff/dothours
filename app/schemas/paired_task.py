import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import BuildingFamilyKey, PairedTaskStatus, PairedTaskTargetType


class PairedTaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    building_family: BuildingFamilyKey
    target_minutes: int = Field(gt=0)
    target_type: PairedTaskTargetType
    due_at: datetime
    participant_user_ids: list[uuid.UUID] = Field(min_length=1, max_length=8)


class ParticipantOut(BaseModel):
    user_id: uuid.UUID
    name: str
    minutes_logged: int


class PairedTaskOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    building_family: BuildingFamilyKey
    created_by: uuid.UUID
    target_minutes: int
    target_type: PairedTaskTargetType
    status: PairedTaskStatus
    due_at: datetime
    participants: list[ParticipantOut]
