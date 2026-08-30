import enum


class BuildingFamilyKey(enum.StrEnum):
    sport = "sport"
    study = "study"
    work = "work"
    creativity = "creativity"
    meditation = "meditation"
    reading = "reading"
    custom = "custom"


class ShapeKind(enum.StrEnum):
    circle = "circle"
    square = "square"
    triangle = "triangle"
    hex = "hex"
    blob = "blob"
    diamond = "diamond"


class TimeEntrySource(enum.StrEnum):
    timer = "timer"
    manual = "manual"


class OwnerType(enum.StrEnum):
    user = "user"
    company = "company"


class CompanyRole(enum.StrEnum):
    owner = "owner"
    admin = "admin"
    member = "member"


class LeaderboardPeriod(enum.StrEnum):
    all_time = "all_time"
    weekly = "weekly"
    monthly = "monthly"


class FriendshipStatus(enum.StrEnum):
    pending = "pending"
    accepted = "accepted"
    declined = "declined"
    blocked = "blocked"


class PairedTaskTargetType(enum.StrEnum):
    combined = "combined"
    per_participant = "per_participant"


class PairedTaskStatus(enum.StrEnum):
    active = "active"
    completed = "completed"
    expired = "expired"
    cancelled = "cancelled"
