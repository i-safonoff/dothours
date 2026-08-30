"""Timezone helpers — a user's reminders should land in their evening, not UTC's."""

from datetime import datetime, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

UTC_ZONE = ZoneInfo("UTC")


def is_known_timezone(name: str) -> bool:
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return False
    return True


def zone_for(name: str) -> tzinfo:
    """Never raises — a bad value in the database must not break a batch job."""
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return UTC_ZONE


def local_now(name: str, now: datetime) -> datetime:
    return now.astimezone(zone_for(name))
