import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.user import UserPublic


class PostCreate(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class PostOut(BaseModel):
    id: uuid.UUID
    author: UserPublic
    text: str
    created_at: datetime
    likes_count: int
    comments_count: int
    liked_by_me: bool


class CommentCreate(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class CommentOut(BaseModel):
    id: uuid.UUID
    post_id: uuid.UUID
    author: UserPublic
    text: str
    created_at: datetime
