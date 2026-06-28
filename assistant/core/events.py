"""
Lightweight async pub/sub event bus.
Every module communicates through events – no circular imports.
"""
from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

if sys.version_info >= (3, 11):
    from enum import auto, StrEnum
else:
    from enum import auto
    from enum import Enum

    class StrEnum(str, Enum):  # type: ignore[no-redef]
        """Backport of StrEnum for Python 3.10."""
        @staticmethod
        def _generate_next_value_(name, start, count, last_values):
            return name.lower()

from loguru import logger


class EventType(StrEnum):
    # ── Audio pipeline ───────────────────────────────────────────────────────
    WAKE_WORD_DETECTED = auto()
    SPEECH_START = auto()
    SPEECH_END = auto()
    TRANSCRIPT_READY = auto()

    # ── AI ───────────────────────────────────────────────────────────────────
    AI_RESPONSE_CHUNK = auto()
    AI_RESPONSE_DONE = auto()

    # ── TTS ──────────────────────────────────────────────────────────────────
    TTS_START = auto()
    TTS_DONE = auto()
    TTS_INTERRUPTED = auto()

    # ── Automation ───────────────────────────────────────────────────────────
    COMMAND_REQUESTED = auto()
    COMMAND_DONE = auto()
    CONFIRMATION_REQUIRED = auto()
    CONFIRMATION_ANSWER = auto()

    # ── System ───────────────────────────────────────────────────────────────
    ASSISTANT_IDLE = auto()
    ASSISTANT_LISTENING = auto()
    ASSISTANT_THINKING = auto()
    ASSISTANT_SPEAKING = auto()
    SHUTDOWN = auto()
    ERROR = auto()


@dataclass
class Event:
    type: EventType
    data: Any = None
    source: str = "system"


# Type alias for subscriber callbacks
Subscriber = Callable[[Event], Awaitable[None]]


class EventBus:
    """Async publish/subscribe bus. Thread-safe via asyncio queues."""

    def __init__(self) -> None:
        self._subscribers: dict[EventType, list[Subscriber]] = {}

    def subscribe(self, event_type: EventType, callback: Subscriber) -> None:
        self._subscribers.setdefault(event_type, []).append(callback)

    def unsubscribe(self, event_type: EventType, callback: Subscriber) -> None:
        subs = self._subscribers.get(event_type, [])
        if callback in subs:
            subs.remove(callback)

    async def publish(self, event: Event) -> None:
        """Fire all subscribers for the event. Errors are logged, not raised."""
        for callback in self._subscribers.get(event.type, []):
            try:
                await callback(event)
            except Exception:
                logger.exception("EventBus subscriber error for {}", event.type)

    def emit(self, event: Event) -> None:
        """Fire-and-forget from sync code – schedules on the running loop."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.publish(event))
        except RuntimeError:
            # No running loop – silently drop (e.g. during tests without loop)
            logger.warning("EventBus.emit called outside of async context – dropped {}", event.type)


# Global singleton used by all modules
bus: EventBus = EventBus()
