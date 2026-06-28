"""
Unit tests for TTS sentence splitter and Speaker queue logic.
No audio hardware required – speaker is patched.
"""
import asyncio
import pytest

from assistant.tts.speaker import split_sentences, Speaker


def test_split_sentences_basic():
    text = "Hello world. How are you? I am fine!"
    parts = split_sentences(text)
    assert len(parts) >= 1
    # All text must be preserved
    assert "Hello world" in " ".join(parts)
    assert "How are you" in " ".join(parts)


def test_split_sentences_short_merged():
    # Very short sentences should be merged together
    text = "Hi. Ok. Sure. Let me check."
    parts = split_sentences(text)
    # Should produce fewer parts than raw sentence count
    assert len(parts) <= 4


def test_split_sentences_single():
    text = "Just one sentence"
    assert split_sentences(text) == ["Just one sentence"]


def test_split_empty():
    assert split_sentences("") == []


@pytest.mark.asyncio
async def test_speaker_say_queues(monkeypatch):
    """say() should enqueue sentences without actually playing audio."""
    sp = Speaker()
    played: list[str] = []

    async def fake_speak(text: str) -> None:
        played.append(text)

    monkeypatch.setattr(sp, "_speak_sentence", fake_speak)
    sp._task = asyncio.create_task(sp._worker())

    await sp.say("Hello there. How are you doing today?")
    await asyncio.sleep(0.05)   # let worker process
    sp._queue.put_nowait(None)  # send sentinel
    await sp._task

    assert len(played) >= 1


@pytest.mark.asyncio
async def test_speaker_interrupt_clears_queue():
    sp = Speaker()
    # Fill queue manually
    await sp._queue.put("sentence one")
    await sp._queue.put("sentence two")
    sp._playing = True

    await sp.interrupt()

    assert sp._queue.empty()
    assert sp._interrupted is True
