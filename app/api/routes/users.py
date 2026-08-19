import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.city import DailyProgress
from app.models.user import User
from app.schemas.user import UserOut, UserStats, UserUpdate
from app.services.tracking import compute_streak

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(current_user)


@router.patch("/me", response_model=UserOut)
def update_me(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserOut:
    if payload.name is not None:
        current_user.name = payload.name
    if payload.daily_goal_minutes is not None:
        current_user.daily_goal_minutes = payload.daily_goal_minutes
    db.commit()
    db.refresh(current_user)
    return UserOut.model_validate(current_user)


@router.get("/me/stats", response_model=UserStats)
def get_my_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserStats:
    today_progress = db.scalar(
        select(DailyProgress).where(DailyProgress.user_id == current_user.id, DailyProgress.date == date.today())
    )
    current_streak, longest_streak = compute_streak(db, current_user.id)
    return UserStats(
        today_minutes=today_progress.total_minutes if today_progress else 0,
        streak=current_streak,
        longest_streak=longest_streak,
    )


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: uuid.UUID, db: Session = Depends(get_db)) -> UserOut:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserOut.model_validate(user)
