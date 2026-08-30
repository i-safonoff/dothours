import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.city import CityBuilding
from app.models.company import Company, CompanyInvite, CompanyMembership
from app.models.enums import CompanyRole, OwnerType
from app.models.user import User
from app.schemas.city import CityBuildingOut, CityOut
from app.schemas.company import (
    CompanyCreate,
    CompanyInviteCreate,
    CompanyInviteOut,
    CompanyJoin,
    CompanyMemberOut,
    CompanyMemberUpdate,
    CompanyOut,
    CompanyUpdate,
)
from app.services.companies import (
    generate_invite_code,
    get_membership,
    get_visible_company,
    members_count,
    require_role,
    unique_slug,
)

router = APIRouter(prefix="/companies", tags=["companies"])


def _company_out(db: Session, company: Company, current_user: User) -> CompanyOut:
    membership = get_membership(db, company.id, current_user.id)
    return CompanyOut(
        **CompanyOut.model_validate(company).model_dump(exclude={"members_count", "my_role"}),
        members_count=members_count(db, company.id),
        my_role=membership.role if membership else None,
    )


@router.post("", response_model=CompanyOut, status_code=status.HTTP_201_CREATED)
def create_company(
    payload: CompanyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CompanyOut:
    if payload.slug is not None and db.scalar(select(Company).where(Company.slug == payload.slug)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug already taken")

    company = Company(
        name=payload.name,
        slug=payload.slug or unique_slug(db, payload.name),
        description=payload.description,
        avatar_color=payload.avatar_color,
        is_public=payload.is_public,
        created_by=current_user.id,
    )
    db.add(company)
    db.flush()
    db.add(CompanyMembership(company_id=company.id, user_id=current_user.id, role=CompanyRole.owner))
    db.commit()
    db.refresh(company)
    return _company_out(db, company, current_user)


@router.get("", response_model=list[CompanyOut])
def list_companies(
    mine: bool = Query(default=True, description="Only companies the caller belongs to; false adds public ones"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CompanyOut]:
    member_of = select(CompanyMembership.company_id).where(CompanyMembership.user_id == current_user.id)
    stmt = select(Company).where(Company.id.in_(member_of))
    if not mine:
        stmt = select(Company).where(or_(Company.id.in_(member_of), Company.is_public.is_(True)))

    companies = db.scalars(stmt.order_by(Company.created_at.desc())).all()
    return [_company_out(db, c, current_user) for c in companies]


@router.post("/join", response_model=CompanyOut)
def join_company(
    payload: CompanyJoin,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CompanyOut:
    invite = db.scalar(select(CompanyInvite).where(CompanyInvite.code == payload.invite_code))
    if invite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")

    expires_at = invite.expires_at if invite.expires_at.tzinfo else invite.expires_at.replace(tzinfo=UTC)
    if expires_at < datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Invite expired")
    if invite.uses_count >= invite.max_uses:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Invite already used up")

    if get_membership(db, invite.company_id, current_user.id) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already a member")

    db.add(CompanyMembership(company_id=invite.company_id, user_id=current_user.id, role=CompanyRole.member))
    invite.uses_count += 1
    db.commit()

    company = db.get(Company, invite.company_id)
    return _company_out(db, company, current_user)


@router.get("/{company_id}", response_model=CompanyOut)
def get_company(
    company_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CompanyOut:
    company = get_visible_company(db, company_id, current_user.id)
    return _company_out(db, company, current_user)


@router.patch("/{company_id}", response_model=CompanyOut)
def update_company(
    company_id: uuid.UUID,
    payload: CompanyUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CompanyOut:
    company = get_visible_company(db, company_id, current_user.id)
    require_role(db, company_id, current_user.id, CompanyRole.admin)

    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(company, field, value)
    db.commit()
    db.refresh(company)
    return _company_out(db, company, current_user)


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(
    company_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    company = get_visible_company(db, company_id, current_user.id)
    require_role(db, company_id, current_user.id, CompanyRole.owner)

    db.query(CompanyInvite).filter(CompanyInvite.company_id == company_id).delete()
    db.query(CompanyMembership).filter(CompanyMembership.company_id == company_id).delete()
    db.query(CityBuilding).filter(
        CityBuilding.owner_type == OwnerType.company, CityBuilding.owner_id == company_id
    ).delete()
    db.delete(company)
    db.commit()


@router.get("/{company_id}/members", response_model=list[CompanyMemberOut])
def list_members(
    company_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CompanyMemberOut]:
    get_visible_company(db, company_id, current_user.id)

    rows = db.execute(
        select(CompanyMembership, User)
        .join(User, User.id == CompanyMembership.user_id)
        .where(CompanyMembership.company_id == company_id)
        .order_by(CompanyMembership.contribution_minutes_total.desc())
    ).all()
    return [
        CompanyMemberOut(
            user_id=user.id,
            name=user.name,
            initials=user.initials,
            avatar_color=user.avatar_color,
            role=membership.role,
            contribution_minutes_total=membership.contribution_minutes_total,
            joined_at=membership.joined_at,
        )
        for membership, user in rows
    ]


@router.patch("/{company_id}/members/{user_id}", response_model=CompanyMemberOut)
def update_member_role(
    company_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: CompanyMemberUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CompanyMemberOut:
    get_visible_company(db, company_id, current_user.id)
    require_role(db, company_id, current_user.id, CompanyRole.owner)

    membership = get_membership(db, company_id, user_id)
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    if membership.user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot change your own role")

    membership.role = payload.role
    db.commit()

    user = db.get(User, user_id)
    return CompanyMemberOut(
        user_id=user.id,
        name=user.name,
        initials=user.initials,
        avatar_color=user.avatar_color,
        role=membership.role,
        contribution_minutes_total=membership.contribution_minutes_total,
        joined_at=membership.joined_at,
    )


@router.delete("/{company_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    company_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Kick a member (admin+), or leave the company yourself. The owner must hand over first."""
    get_visible_company(db, company_id, current_user.id)
    if user_id != current_user.id:
        require_role(db, company_id, current_user.id, CompanyRole.admin)

    membership = get_membership(db, company_id, user_id)
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    if membership.role == CompanyRole.owner:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Transfer ownership before leaving")

    db.delete(membership)
    db.commit()


@router.post("/{company_id}/invites", response_model=CompanyInviteOut, status_code=status.HTTP_201_CREATED)
def create_invite(
    company_id: uuid.UUID,
    payload: CompanyInviteCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CompanyInviteOut:
    get_visible_company(db, company_id, current_user.id)
    require_role(db, company_id, current_user.id, CompanyRole.admin)

    invite = CompanyInvite(
        company_id=company_id,
        code=generate_invite_code(),
        created_by=current_user.id,
        expires_at=datetime.now(UTC) + timedelta(hours=payload.expires_in_hours),
        max_uses=payload.max_uses,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return CompanyInviteOut.model_validate(invite)


@router.get("/{company_id}/invites", response_model=list[CompanyInviteOut])
def list_invites(
    company_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CompanyInviteOut]:
    get_visible_company(db, company_id, current_user.id)
    require_role(db, company_id, current_user.id, CompanyRole.admin)

    invites = db.scalars(
        select(CompanyInvite).where(CompanyInvite.company_id == company_id).order_by(CompanyInvite.created_at.desc())
    ).all()
    return [CompanyInviteOut.model_validate(i) for i in invites]


@router.get("/{company_id}/city", response_model=CityOut)
def get_company_city(
    company_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CityOut:
    get_visible_company(db, company_id, current_user.id)

    buildings = db.scalars(
        select(CityBuilding).where(CityBuilding.owner_type == OwnerType.company, CityBuilding.owner_id == company_id)
    ).all()
    return CityOut(buildings=[CityBuildingOut.model_validate(b) for b in buildings])
