"""Domain metrics — the ones a Grafana dashboard about *the product* needs.

HTTP-level RED metrics come from prometheus-fastapi-instrumentator in
app/main.py; everything here is about tracked time, not requests.
"""

from prometheus_client import Counter, Gauge, Histogram

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


notifications_created_total = Counter(
    "dothours_notifications_created_total",
    "In-app notifications written, by kind",
    labelnames=("kind",),
)

events_published_total = Counter(
    "dothours_events_published_total",
    "Realtime events handed to the bus, by event name",
    labelnames=("event",),
)

ws_connections = Gauge(
    "dothours_ws_connections",
    "WebSocket clients connected to this process",
)

background_task_runs_total = Counter(
    "dothours_background_task_runs_total",
    "Celery task executions, by task and outcome",
    labelnames=("task", "outcome"),
)

background_task_duration_seconds = Histogram(
    "dothours_background_task_duration_seconds",
    "How long a Celery task takes",
    labelnames=("task",),
)


def sync_active_timers(count: int) -> None:
    """Reset the gauge from the database — inc/dec alone drifts across restarts."""
    active_timers.set(count)
