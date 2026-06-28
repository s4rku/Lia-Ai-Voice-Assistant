"""
Unit tests for the EventBus.
"""
import asyncio
import pytest

from assistant.core.events import EventBus, Event, EventType


@pytest.mark.asyncio
async def test_subscribe_and_publish():
    bus = EventBus()
    received: list[Event] = []

    async def handler(evt: Event) -> None:
        received.append(evt)

    bus.subscribe(EventType.WAKE_WORD_DETECTED, handler)
    await bus.publish(Event(type=EventType.WAKE_WORD_DETECTED, data="lia"))

    assert len(received) == 1
    assert received[0].data == "lia"


@pytest.mark.asyncio
async def test_unsubscribe():
    bus = EventBus()
    received: list[Event] = []

    async def handler(evt: Event) -> None:
        received.append(evt)

    bus.subscribe(EventType.SPEECH_START, handler)
    bus.unsubscribe(EventType.SPEECH_START, handler)
    await bus.publish(Event(type=EventType.SPEECH_START))

    assert len(received) == 0


@pytest.mark.asyncio
async def test_subscriber_error_does_not_propagate():
    bus = EventBus()

    async def bad_handler(evt: Event) -> None:
        raise ValueError("simulated error")

    bus.subscribe(EventType.ERROR, bad_handler)
    # Should not raise
    await bus.publish(Event(type=EventType.ERROR))


@pytest.mark.asyncio
async def test_multiple_subscribers():
    bus = EventBus()
    counts: list[int] = [0, 0]

    async def h1(evt: Event) -> None:
        counts[0] += 1

    async def h2(evt: Event) -> None:
        counts[1] += 1

    bus.subscribe(EventType.TRANSCRIPT_READY, h1)
    bus.subscribe(EventType.TRANSCRIPT_READY, h2)
    await bus.publish(Event(type=EventType.TRANSCRIPT_READY, data="hello"))

    assert counts == [1, 1]
