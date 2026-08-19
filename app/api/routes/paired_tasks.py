import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.enums import FriendshipStatus, PairedTaskStatus
from app.models.friendship import Friendship
from app.models.paired_task import PairedTask, PairedTaskParticipant
from app.models.user import User
from app.schemas.paired_task import PairedTaskCreate, PairedTaskOut, ParticipantOut

router = APIRouter(prefix="/paired-tasks", tags=["paired-tasks"])


def _are_friends(db: Session, user_a: uuid.UUID, user_b: uuid.UUID) -> bool:
    return (
        db.scalar(
            select(Friendship).where(
                Friendship.status == FriendshipStatus.accepted,
                or_(
                    and_(Friendship.requester_id == user_a, Friendship.addressee_id == user_b),
                    and_(Friendship.requester_id == user_b, Friendship.addressee_id == user_a),
                ),
            )
        )
        is not None
    )


def _to_out(db: Session, task: PairedTask) -> PairedTaskOut:
    participants = db.scalars(
        select(PairedTaskParticipant).where(PairedTaskParticipant.paired_task_id == task.id)
    ).all()
    users_by_id = {u.id: u for u in db.scalars(select(User).where(User.id.in_([p.user_id for p in participants])))}
    return PairedTaskOut(
        id=task.id,
        title=task.title,
        description=task.description,
        building_family=task.building_family,
        created_by=task.created_by,
        target_minutes=task.target_minutes,
        target_type=task.target_type,
        status=task.status,
        due_at=task.due_at,
        participants=[
            ParticipantOut(
                user_id=p.user_id,
                name=users_by_id[p.user_id].name if p.user_id in users_by_id else "?",
                minutes_logged=p.minutes_logged,
            )
            for p in participants
        ],
    )


@router.post("", response_model=PairedTaskOut, status_code=status.HTTP_201_CREATED)
def create_paired_task(
    payload: PairedTaskCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PairedTaskOut:
    participant_ids = set(payload.participant_user_ids) | {current_user.id}
    for participant_id in participant_ids:
        if participant_id != current_user.id and not _are_friends(db, current_user.id, participant_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User {participant_id} is not in your friends list",
            )

    task = PairedTask(
        title=payload.title,
        description=payload.description,
        building_family=payload.building_family,
        created_by=current_user.id,
        target_minutes=payload.target_minutes,
        target_type=payload.target_type,
        due_at=payload.due_at,
    )
    db.add(task)
    db.flush()

    for participant_id in participant_ids:
        db.add(PairedTaskParticipant(paired_task_id=task.id, user_id=participant_id))

    db.commit()
    db.refresh(task)
    return _to_out(db, task)


@router.get("", response_model=list[PairedTaskOut])
def list_paired_tasks(
    mine: bool = True,
    status_filter: PairedTaskStatus | None = Query(default=None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PairedTaskOut]:
    stmt = select(PairedTask)
    if mine:
        stmt = stmt.join(PairedTaskParticipant, PairedTaskParticipant.paired_task_id == PairedTask.id).where(
            PairedTaskParticipant.user_id == current_user.id
        )
    if status_filter is not None:
        stmt = stmt.where(PairedTask.status == status_filter)

    tasks = db.scalars(stmt.order_by(PairedTask.due_at)).unique().all()
    return [_to_out(db, task) for task in tasks]


@router.get("/{task_id}", response_model=PairedTaskOut)
def get_paired_task(
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PairedTaskOut:
    task = db.get(PairedTask, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paired task not found")

    is_participant = db.scalar(
        select(PairedTaskParticipant).where(
            PairedTaskParticipant.paired_task_id == task_id, PairedTaskParticipant.user_id == current_user.id
        )
    )
    if is_participant is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a participant of this task")

    return _to_out(db, task)
