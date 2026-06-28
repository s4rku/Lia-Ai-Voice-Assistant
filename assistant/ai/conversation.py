"""
Conversation loop – the brain stem of lia.

State machine
─────────────
IDLE ──[wake word]──► LISTENING ──[utterance]──► THINKING
  ▲                                                   │
  └──────────────────[done/error]◄── SPEAKING ◄───────┘

The loop is fully async and non-blocking:
  • Wake word detected  → switch to listening mode, say "Yes?"
  • Utterance received  → forward to AI, stream response back via TTS
  • User speaks while lia talks → TTS interrupted, start fresh
  • "sleep" / "stop" / "goodbye" → go back to IDLE
"""
from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import Deque

from loguru import logger

from assistant.config import settings
from assistant.core.events import Event, EventType, bus
from assistant.core.types import AssistantState, Message, Role
from assistant.stt.transcriber import TranscriptResult
from assistant.tts.speaker import speaker
from assistant.wakeword.detector import wake_detector


# ── Phrases that put lia back to sleep ─────────────────────────────────────
_SLEEP_PHRASES = {
    "stop", "sleep", "goodbye", "bye", "go to sleep",
    "that's all", "thanks", "thank you", "shut up",
}

# ── Short responses for immediate context ────────────────────────────────────
_WAKE_RESPONSES = ["Yes?", "How can I help?", "I'm listening.", "Go ahead."]
_ACKNOWLEDGEMENTS = ["Got it.", "On it.", "Sure.", "One moment."]


class ConversationLoop:
    """
    Central async state machine.
    Wires wake-word → STT → AI → TTS together via the event bus.
    """

    def __init__(self) -> None:
        self._state = AssistantState.IDLE
        self._short_memory: Deque[Message] = deque(maxlen=settings.memory_short_term_limit)
        self._wake_import: int = 0          # count of wake detections this session
        self._task: asyncio.Task | None = None
        self._awaiting_ai: bool = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    async def start(self) -> None:
        bus.subscribe(EventType.WAKE_WORD_DETECTED, self._on_wake)
        bus.subscribe(EventType.TRANSCRIPT_READY, self._on_transcript)
        bus.subscribe(EventType.SHUTDOWN, self._on_shutdown)
        logger.info("Conversation loop started. Waiting for wake word…")
        await self._set_state(AssistantState.IDLE)

    async def stop(self) -> None:
        bus.unsubscribe(EventType.WAKE_WORD_DETECTED, self._on_wake)
        bus.unsubscribe(EventType.TRANSCRIPT_READY, self._on_transcript)
        bus.unsubscribe(EventType.SHUTDOWN, self._on_shutdown)

    # ── State transitions ─────────────────────────────────────────────────────
    async def _set_state(self, state: AssistantState) -> None:
        self._state = state
        state_event_map = {
            AssistantState.IDLE: EventType.ASSISTANT_IDLE,
            AssistantState.LISTENING: EventType.ASSISTANT_LISTENING,
            AssistantState.THINKING: EventType.ASSISTANT_THINKING,
            AssistantState.SPEAKING: EventType.ASSISTANT_SPEAKING,
        }
        if evt := state_event_map.get(state):
            await bus.publish(Event(type=evt, source="conversation"))
        logger.debug("State → {}", state)

    # ── Event handlers ────────────────────────────────────────────────────────
    async def _on_wake(self, event: Event) -> None:
        if self._state in (AssistantState.THINKING, AssistantState.EXECUTING):
            return   # busy – ignore
        if self._state == AssistantState.SPEAKING:
            await speaker.interrupt()

        self._wake_import += 1
        await self._set_state(AssistantState.LISTENING)

        # Pick a response variant to avoid sounding repetitive
        response = _WAKE_RESPONSES[self._wake_import % len(_WAKE_RESPONSES)]
        await speaker.say(response)

    async def _on_transcript(self, event: Event) -> None:
        result: TranscriptResult = event.data
        text = result.text.strip()

        if not text:
            return

        # If not in listening state, check if the transcript IS a wake phrase
        if self._state == AssistantState.IDLE:
            activated = await wake_detector.check_transcript(text)
            if not activated:
                return
            # Remove wake phrase prefix from text for cleaner processing
            text = self._strip_wake_prefix(text)
            if not text:
                return  # just the wake word, wait for next utterance

        # Check for sleep command
        if any(phrase in text.lower() for phrase in _SLEEP_PHRASES):
            await self._go_to_sleep()
            return

        # Store user message
        user_msg = Message(role=Role.USER, content=text)
        self._short_memory.append(user_msg)
        logger.info("User: {}", text)

        # Hand off to AI
        await self._set_state(AssistantState.THINKING)
        asyncio.create_task(self._get_ai_response(text), name="ai_response")

    async def _on_shutdown(self, event: Event) -> None:
        await self.stop()

    # ── AI integration ────────────────────────────────────────────────────────
    async def _get_ai_response(self, user_text: str) -> None:
        """
        Request a response from the AI brain.
        Imported here to avoid circular imports at module level.
        """
        try:
            # Import lazily – brain is set up in Phase 3
            from assistant.ai.brain import brain  # noqa: PLC0415
            response = await brain.respond(
                user_text=user_text,
                history=list(self._short_memory),
            )
        except ImportError:
            # Phase 3 not yet built – use a stub response
            response = await self._stub_response(user_text)
        except Exception:
            logger.exception("AI response failed.")
            response = "Sorry, something went wrong on my end."

        if response:
            assistant_msg = Message(role=Role.ASSISTANT, content=response)
            self._short_memory.append(assistant_msg)
            logger.info("lia: {}", response)

            await self._set_state(AssistantState.SPEAKING)
            await speaker.say(response)
            await self._set_state(AssistantState.LISTENING)

    async def _stub_response(self, text: str) -> str:
        """Temporary stub used before Phase 3 (AI brain) is built."""
        await asyncio.sleep(0.1)
        text_lower = text.lower()

        if any(w in text_lower for w in ("hello", "hi", "hey")):
            return f"Hey there! I'm {settings.assistant_name}. AI brain not connected yet."
        if any(w in text_lower for w in ("time", "what time")):
            import arrow  # type: ignore
            return f"It's {arrow.now().format('h:mm A')}."
        if any(w in text_lower for w in ("slow", "cpu", "ram", "memory")):
            from assistant.system.health import get_system_health
            h = get_system_health()
            return f"Your PC is at {h.cpu_percent:.0f}% CPU and {h.ram_percent:.0f}% RAM."
        if "weather" in text_lower:
            return "I'll need my AI brain and a weather API key for that. Coming in Phase 3."
        return f"I heard you say: '{text}'. My AI brain is still being installed. Check back after Phase 3!"

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _strip_wake_prefix(self, text: str) -> str:
        """Remove leading wake phrase from transcript."""
        lower = text.lower()
        for phrase in sorted(settings.wake_words, key=len, reverse=True):
            if lower.startswith(phrase):
                return text[len(phrase):].strip(" ,!?.")
        return text

    async def _go_to_sleep(self) -> None:
        await speaker.say(f"Okay, going quiet. Just say my name when you need me.")
        await self._set_state(AssistantState.IDLE)
        logger.info("lia went to sleep.")

    @property
    def state(self) -> AssistantState:
        return self._state

    @property
    def history(self) -> list[Message]:
        return list(self._short_memory)


# Module singleton
conversation: ConversationLoop = ConversationLoop()
