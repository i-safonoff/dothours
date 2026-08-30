"""The bus itself: channel isolation, and what happens when Redis is not there."""

import asyncio
import json
import logging

import pytest

from app.core.config import get_settings
from app.events.bus import EventBus, company_channel, user_channel

UNREACHABLE_BROKER = "redis://127.0.0.1:6399/0"


def test_channel_names_are_stable() -> None:
    assert user_channel("abc") == "user:abc"
    assert company_channel("xyz") == "company:xyz"


def run(coro):
    return asyncio.run(coro)


def test_memory_backend_delivers_only_to_the_right_channel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "ws_backend", "memory")
    bus = EventBus()

    async def scenario() -> dict:
        async with bus.subscribe(["user:1"]) as stream:
            bus.publish("user:2", "timer.started", {"entry_id": "other"})
            bus.publish("user:1", "timer.started", {"entry_id": "mine"})
            raw = await asyncio.wait_for(anext(stream), timeout=1)
            return json.loads(raw)

    event = run(scenario())
    assert event["data"]["entry_id"] == "mine"


def test_publish_to_an_unreachable_redis_falls_back_to_the_local_bus(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "ws_backend", "redis")
    monkeypatch.setattr(settings, "celery_broker_url", UNREACHABLE_BROKER)
    bus = EventBus()

    async def scenario() -> dict:
        # Подписка тоже не достучится до Redis и переключится на локальную шину.
        async with bus.subscribe(["user:1"]) as stream:
            bus.publish("user:1", "notification.created", {"notification_id": "n1"})
            raw = await asyncio.wait_for(anext(stream), timeout=2)
            return json.loads(raw)

    with caplog.at_level(logging.WARNING, logger="dothours.events"):
        event = run(scenario())

    assert event["event"] == "notification.created"
    assert any(record.levelno == logging.WARNING for record in caplog.records), (
        "недоступный Redis должен оставить след в логах, а не молча деградировать"
    )


def test_publishing_to_nobody_is_a_no_op(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "ws_backend", "memory")
    bus = EventBus()
    bus.publish("user:nobody", "timer.started", {})  # не должно бросать


def test_a_slow_subscriber_is_dropped_not_blocking(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "ws_backend", "memory")
    bus = EventBus()

    async def scenario() -> int:
        async with bus.subscribe(["user:1"]) as stream:
            for i in range(150):  # очередь на 100 — лишнее отбрасывается, publish не виснет
                bus.publish("user:1", "timer.started", {"n": i})
            first = json.loads(await asyncio.wait_for(anext(stream), timeout=1))
            return first["data"]["n"]

    assert run(scenario()) == 0
