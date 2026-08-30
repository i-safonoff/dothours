"""Realtime event bus.

Events are **hints, not data**: an event says "something about you changed,
re-read it", never "here is the new state". That keeps publishing cheap and
harmless — a publish that races a rolled-back transaction costs the client one
redundant GET, not a wrong screen.

Two backends:

- `redis` — a Redis pub/sub channel per subscriber, so several uvicorn workers
  (or a Celery worker) can push to a socket held by another process.
- `memory` — an in-process fan-out. Correct only for a single process, which
  is exactly the case in tests and in a plain `uvicorn --reload` dev loop.

Publishing is synchronous on purpose: the request handlers are sync `def`
functions, and forcing them through an event loop to announce a hint would be
a lot of machinery for no gain.
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from app.core.config import get_settings
from app.core.metrics import events_published_total

logger = logging.getLogger("dothours.events")


# Channel names. A channel is always "who should hear this", never "what happened".
def user_channel(user_id: Any) -> str:
    return f"user:{user_id}"


def company_channel(company_id: Any) -> str:
    return f"company:{company_id}"


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._redis = None
        self._redis_broken = False

    # -- configuration -------------------------------------------------

    @property
    def backend(self) -> str:
        return get_settings().ws_backend

    def _redis_client(self):
        if self._redis is None:
            from redis.asyncio import Redis

            self._redis = Redis.from_url(get_settings().celery_broker_url, decode_responses=True)
        return self._redis

    # -- publishing ----------------------------------------------------

    def publish(self, channel: str, event: str, data: dict[str, Any] | None = None) -> None:
        """Fire-and-forget. Never raises: a broken bus must not fail a request."""
        message = json.dumps({"event": event, "data": data or {}}, default=str)
        events_published_total.labels(event).inc()

        if self.backend == "redis" and not self._redis_broken:
            self._publish_via_redis(channel, message)
        else:
            self._publish_locally(channel, message)

    def _publish_via_redis(self, channel: str, message: str) -> None:
        try:
            from redis import Redis

            with Redis.from_url(get_settings().celery_broker_url) as client:
                client.publish(channel, message)
        except Exception as exc:  # noqa: BLE001 -- realtime is best effort
            logger.warning("Realtime publish to %s failed, falling back locally: %s", channel, exc)
            self._publish_locally(channel, message)

    def _publish_locally(self, channel: str, message: str) -> None:
        queues = self._subscribers.get(channel)
        if not queues:
            return

        loop = self._loop
        for queue in list(queues):
            if loop is not None and loop.is_running():
                # Sync handlers run in a worker thread; hop back onto the loop.
                loop.call_soon_threadsafe(self._offer, queue, message)
            else:
                self._offer(queue, message)

    @staticmethod
    def _offer(queue: asyncio.Queue, message: str) -> None:
        try:
            queue.put_nowait(message)
        except asyncio.QueueFull:
            logger.warning("Dropping a realtime event: subscriber is not keeping up")

    # -- subscribing ---------------------------------------------------

    @asynccontextmanager
    async def subscribe(self, channels: list[str]) -> AsyncIterator[AsyncIterator[str]]:
        if self.backend == "redis":
            try:
                async with self._subscribe_redis(channels) as stream:
                    yield stream
                    return
            except Exception as exc:  # noqa: BLE001
                logger.warning("Realtime subscribe failed, using the in-process bus: %s", exc)
                self._redis_broken = True

        async with self._subscribe_local(channels) as stream:
            yield stream

    @asynccontextmanager
    async def _subscribe_redis(self, channels: list[str]) -> AsyncIterator[AsyncIterator[str]]:
        pubsub = self._redis_client().pubsub()
        await pubsub.subscribe(*channels)

        async def stream() -> AsyncIterator[str]:
            async for message in pubsub.listen():
                if message.get("type") == "message":
                    yield message["data"]

        try:
            yield stream()
        finally:
            await pubsub.unsubscribe(*channels)
            await pubsub.aclose()

    @asynccontextmanager
    async def _subscribe_local(self, channels: list[str]) -> AsyncIterator[AsyncIterator[str]]:
        self._loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        for channel in channels:
            self._subscribers.setdefault(channel, set()).add(queue)

        async def stream() -> AsyncIterator[str]:
            while True:
                yield await queue.get()

        try:
            yield stream()
        finally:
            for channel in channels:
                subscribers = self._subscribers.get(channel)
                if subscribers is not None:
                    subscribers.discard(queue)
                    if not subscribers:
                        del self._subscribers[channel]


bus = EventBus()
