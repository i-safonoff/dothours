import uuid
from datetime import UTC, date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.events import types
from app.events.bus import bus, user_channel
from app.models.city import DailyProgress
from app.models.enums import FriendshipStatus
from app.models.friendship import Friendship
from app.models.user import User
from app.schemas.friendship import FriendOut, FriendRequestCreate, FriendRequestOut
from app.services.tracking import compute_streak

router = APIRouter(tags=["friends"])


def _get_request_for_user(db: Session, request_id: uuid.UUID, current_user: User) -> Friendship:
    friend_request = db.get(Friendship, request_id)
    if friend_request is None or friend_request.addressee_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Friend request not found")
    return friend_request


@router.get("/friends", response_model=list[FriendOut])
def list_friends(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[FriendOut]:
    friendships = db.scalars(
        select(Friendship).where(
            Friendship.status == FriendshipStatus.accepted,
            or_(Friendship.requester_id == current_user.id, Friendship.addressee_id == current_user.id),
        )
    ).all()

    friend_ids = [f.addressee_id if f.requester_id == current_user.id else f.requester_id for f in friendships]
    if not friend_ids:
        return []

    friends = db.scalars(select(User).where(User.id.in_(friend_ids))).all()
    today_progress = {
        p.user_id: p
        for p in db.scalars(
            select(DailyProgress).where(DailyProgress.user_id.in_(friend_ids), DailyProgress.date == date.today())
        )
    }

    result = []
    for friend in friends:
        current_streak, _ = compute_streak(db, friend.id)
        progress = today_progress.get(friend.id)
        result.append(
            FriendOut(
                id=friend.id,
                name=friend.name,
                initials=friend.initials,
                today_minutes=progress.total_minutes if progress else 0,
                streak=current_streak,
            )
        )
    return result


@router.post("/friends/requests", response_model=FriendRequestOut, status_code=status.HTTP_201_CREATED)
def send_friend_request(
    payload: FriendRequestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FriendRequestOut:
    if payload.to_user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot friend yourself")

    target = db.get(User, payload.to_user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    existing = db.scalar(
        select(Friendship).where(
            or_(
                and_(Friendship.requester_id == current_user.id, Friendship.addressee_id == payload.to_user_id),
                and_(Friendship.requester_id == payload.to_user_id, Friendship.addressee_id == current_user.id),
            )
        )
    )
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Friendship already exists or pending")

    friend_request = Friendship(requester_id=current_user.id, addressee_id=payload.to_user_id)
    db.add(friend_request)
    db.commit()
    db.refresh(friend_request)

    bus.publish(
        user_channel(payload.to_user_id),
        types.FRIEND_REQUEST_RECEIVED,
        {"request_id": str(friend_request.id), "from_user_id": str(current_user.id)},
    )
    return FriendRequestOut.model_validate(friend_request, from_attributes=True)


@router.get("/friends/requests", response_model=list[FriendRequestOut])
def list_friend_requests(
    direction: Literal["incoming", "outgoing"] = "incoming",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FriendRequestOut]:
    column = Friendship.addressee_id if direction == "incoming" else Friendship.requester_id
    requests = db.scalars(
        select(Friendship).where(column == current_user.id, Friendship.status == FriendshipStatus.pending)
    ).all()
    return [FriendRequestOut.model_validate(r, from_attributes=True) for r in requests]


@router.post("/friends/requests/{request_id}/accept", response_model=FriendRequestOut)
def accept_friend_request(
    request_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FriendRequestOut:
    friend_request = _get_request_for_user(db, request_id, current_user)
    friend_request.status = FriendshipStatus.accepted
    friend_request.responded_at = datetime.now(UTC)
    db.commit()
    db.refresh(friend_request)

    bus.publish(
        user_channel(friend_request.requester_id),
        types.FRIEND_REQUEST_ACCEPTED,
        {"request_id": str(friend_request.id), "by_user_id": str(current_user.id)},
    )
    return FriendRequestOut.model_validate(friend_request, from_attributes=True)


@router.post("/friends/requests/{request_id}/decline", response_model=FriendRequestOut)
def decline_friend_request(
    request_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FriendRequestOut:
    friend_request = _get_request_for_user(db, request_id, current_user)
    friend_request.status = FriendshipStatus.declined
    friend_request.responded_at = datetime.now(UTC)
    db.commit()
    db.refresh(friend_request)
    return FriendRequestOut.model_validate(friend_request, from_attributes=True)


@router.delete("/friends/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_friend(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    friendship = db.scalar(
        select(Friendship).where(
            Friendship.status == FriendshipStatus.accepted,
            or_(
                and_(Friendship.requester_id == current_user.id, Friendship.addressee_id == user_id),
                and_(Friendship.requester_id == user_id, Friendship.addressee_id == current_user.id),
            ),
        )
    )
    if friendship is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Friendship not found")
    db.delete(friendship)
    db.commit()
