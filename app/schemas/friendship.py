import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import FriendshipStatus


class FriendRequestCreate(BaseModel):
    to_user_id: uuid.UUID


class FriendRequestOut(BaseModel):
    id: uuid.UUID
    requester_id: uuid.UUID
    addressee_id: uuid.UUID
    status: FriendshipStatus
    created_at: datetime


class FriendOut(BaseModel):
    id: uuid.UUID
    name: str
    initials: str
    today_minutes: int
    streak: int
