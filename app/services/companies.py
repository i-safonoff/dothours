"""Company membership helpers: slug/invite-code generation and permission checks."""

import re
import secrets
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.company import Company, CompanyMembership
from app.models.enums import CompanyRole

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")

# Slugs are URL-facing, so Cyrillic names get transliterated rather than dropped:
# stripping non-latin characters turned every Russian name into the same "company".
_TRANSLITERATION = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}

ROLE_RANK = {CompanyRole.member: 0, CompanyRole.admin: 1, CompanyRole.owner: 2}


def slugify(name: str) -> str:
    lowered = "".join(_TRANSLITERATION.get(char, char) for char in name.lower())
    slug = _SLUG_STRIP.sub("-", lowered).strip("-")
    return slug[:52] or "company"


def unique_slug(db: Session, base: str) -> str:
    slug = slugify(base)
    candidate = slug
    while db.scalar(select(Company).where(Company.slug == candidate)) is not None:
        candidate = f"{slug}-{secrets.token_hex(3)}"
    return candidate


def generate_invite_code() -> str:
    return secrets.token_urlsafe(8)[:12]


def get_membership(db: Session, company_id: uuid.UUID, user_id: uuid.UUID) -> CompanyMembership | None:
    return db.scalar(
        select(CompanyMembership).where(
            CompanyMembership.company_id == company_id, CompanyMembership.user_id == user_id
        )
    )


def get_visible_company(db: Session, company_id: uuid.UUID, user_id: uuid.UUID) -> Company:
    """A company is visible to its members, and to anyone if it is public."""
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    if not company.is_public and get_membership(db, company_id, user_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company


def require_membership(db: Session, company_id: uuid.UUID, user_id: uuid.UUID) -> CompanyMembership:
    membership = get_membership(db, company_id, user_id)
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this company")
    return membership


def require_role(db: Session, company_id: uuid.UUID, user_id: uuid.UUID, minimum: CompanyRole) -> CompanyMembership:
    membership = require_membership(db, company_id, user_id)
    if ROLE_RANK[membership.role] < ROLE_RANK[minimum]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Requires {minimum.value} role")
    return membership


def members_count(db: Session, company_id: uuid.UUID) -> int:
    return (
        db.scalar(select(func.count()).select_from(CompanyMembership).where(CompanyMembership.company_id == company_id))
        or 0
    )


def user_company_ids(db: Session, user_id: uuid.UUID) -> list[uuid.UUID]:
    return list(db.scalars(select(CompanyMembership.company_id).where(CompanyMembership.user_id == user_id)).all())
