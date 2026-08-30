"""Domain metrics — the ones a Grafana dashboard about *the product* needs.

HTTP-level RED metrics come from prometheus-fastapi-instrumentator in
app/main.py; everything here is about tracked time, not requests.
"""

from prometheus_client import Counter, Gauge

registrations_total = Counter(
    "dothours_registrations_total",
    "Users that completed registration",
)

timers_started_total = Counter(
    "dothours_timers_started_total",
    "Timers started via POST /time-entries/start",
)

timers_stopped_total = Counter(
    "dothours_timers_stopped_total",
    "Timers stopped via POST /time-entries/{id}/stop",
)

minutes_tracked_total = Counter(
    "dothours_minutes_tracked_total",
    "Minutes credited to a city, by building family and entry source",
    labelnames=("building_family", "source"),
)

buildings_level_up_total = Counter(
    "dothours_buildings_level_up_total",
    "Times a city building reached a new level",
    labelnames=("building_family", "owner_type", "level"),
)

active_timers = Gauge(
    "dothours_active_timers",
    "Timers currently running (entries with no ended_at)",
)


def sync_active_timers(count: int) -> None:
    """Reset the gauge from the database — inc/dec alone drifts across restarts."""
    active_timers.set(count)
