"""
Unit tests for wake word transcript fallback.
"""
import pytest
from assistant.wakeword.detector import WakeWordDetector
from assistant.core.events import EventType
from unittest.mock import AsyncMock, patch


@pytest.fixture
def detector():
    return WakeWordDetector()


@pytest.mark.asyncio
async def test_wake_phrase_detected(detector, monkeypatch):
    fired: list[str] = []

    async def fake_fire(result):
        fired.append(result.phrase)

    monkeypatch.setattr(detector, "_fire", fake_fire)

    result = await detector.check_transcript("hey lia open spotify")
    assert result is True
    assert len(fired) == 1


@pytest.mark.asyncio
async def test_no_wake_phrase(detector):
    result = await detector.check_transcript("open spotify please")
    assert result is False


@pytest.mark.asyncio
async def test_wake_phrase_case_insensitive(detector, monkeypatch):
    fired: list[str] = []

    async def fake_fire(result):
        fired.append(result.phrase)

    monkeypatch.setattr(detector, "_fire", fake_fire)

    result = await detector.check_transcript("HELLO lia are you there")
    assert result is True


@pytest.mark.asyncio
async def test_all_default_wake_words(detector, monkeypatch):
    monkeypatch.setattr(detector, "_fire", AsyncMock())

    for phrase in ["hey lia", "lia", "hello lia"]:
        result = await detector.check_transcript(f"{phrase} do something")
        assert result is True, f"Expected '{phrase}' to be detected"
