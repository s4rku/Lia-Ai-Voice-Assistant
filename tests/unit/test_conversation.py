"""
Unit tests for the ConversationLoop state machine.
All external dependencies (speaker, wake detector, AI) are mocked.
"""
import asyncio
import pytest

from unittest.mock import AsyncMock, patch, MagicMock

from assistant.ai.conversation import ConversationLoop, _SLEEP_PHRASES
from assistant.core.events import Event, EventType
from assistant.core.types import AssistantState
from assistant.stt.transcriber import TranscriptResult
import assistant.ai.conversation as conv_module
import assistant.tts.speaker as tts_module
import assistant.wakeword.detector as ww_module


def make_transcript(text: str) -> Event:
    result = TranscriptResult(
        text=text, language="en", confidence=0.95,
        duration_s=1.0, latency_ms=50.0
    )
    return Event(type=EventType.TRANSCRIPT_READY, data=result, source="stt")


@pytest.fixture
def loop_with_mocks(monkeypatch):
    """Return a ConversationLoop with speaker and AI stubbed out."""
    from assistant.tts.speaker import speaker as sp
    from assistant.wakeword.detector import wake_detector as wd

    conv = ConversationLoop()

    # Patch bound methods on the singleton instances directly
    sp.say = AsyncMock()
    sp.interrupt = AsyncMock()
    wd.check_transcript = AsyncMock(return_value=False)

    return conv


@pytest.mark.asyncio
async def test_initial_state_is_idle(loop_with_mocks):
    assert loop_with_mocks.state == AssistantState.IDLE


@pytest.mark.asyncio
async def test_wake_word_moves_to_listening(loop_with_mocks):
    conv = loop_with_mocks
    await conv.start()

    wake_event = Event(type=EventType.WAKE_WORD_DETECTED, source="wakeword")
    await conv._on_wake(wake_event)

    assert conv.state == AssistantState.LISTENING
    await conv.stop()


@pytest.mark.asyncio
async def test_sleep_phrase_returns_to_idle(loop_with_mocks):
    conv = loop_with_mocks
    await conv.start()
    # Manually set to listening
    conv._state = AssistantState.LISTENING

    evt = make_transcript("goodbye")
    await conv._on_transcript(evt)

    assert conv.state == AssistantState.IDLE
    await conv.stop()


@pytest.mark.asyncio
async def test_strip_wake_prefix():
    conv = ConversationLoop()
    assert conv._strip_wake_prefix("hey lia open chrome") == "open chrome"
    assert conv._strip_wake_prefix("lia, what time is it") == "what time is it"


@pytest.mark.asyncio
async def test_stub_response_hello():
    conv = ConversationLoop()
    resp = await conv._stub_response("hello there")
    assert "lia" in resp or "hello" in resp.lower() or "hey" in resp.lower()


@pytest.mark.asyncio
async def test_history_accumulates(loop_with_mocks, monkeypatch):
    conv = loop_with_mocks
    monkeypatch.setattr(conv, "_get_ai_response", AsyncMock())
    await conv.start()
    conv._state = AssistantState.LISTENING

    evt = make_transcript("open notepad please")
    await conv._on_transcript(evt)

    assert len(conv.history) >= 1
    assert conv.history[0].content == "open notepad please"
    await conv.stop()
