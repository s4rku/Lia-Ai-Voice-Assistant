"""
Text-to-Speech using Microsoft Edge TTS (edge-tts).

Features
────────
• Streaming – starts playing audio before the full sentence is generated.
• Interruptible – if SPEECH_START fires while TTS is playing, speech stops
  immediately so lia never talks over the user.
• Queue-based – multiple response chunks are queued and spoken in order.
• Sentence splitting – long AI responses are split at natural boundaries
  so the first sentence plays with minimal latency.
"""
from __future__ import annotations

import asyncio
import io
import re
import tempfile
from pathlib import Path

from loguru import logger

from assistant.config import settings
from assistant.core.events import Event, EventType, bus

# Optional imports – degrade gracefully in unit tests
try:
    import edge_tts  # type: ignore
    _EDGE_AVAILABLE = True
except (ImportError, OSError, Exception):
    edge_tts = None  # type: ignore
    _EDGE_AVAILABLE = False
    logger.warning("edge-tts not installed – TTS will be silent.")

try:
    import pygame  # type: ignore
    _PYGAME_AVAILABLE = True
except (ImportError, OSError, Exception):
    pygame = None  # type: ignore
    _PYGAME_AVAILABLE = False
    logger.warning("pygame not installed – audio playback disabled.")


# ── Sentence splitter ─────────────────────────────────────────────────────────
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def split_sentences(text: str) -> list[str]:
    """Split text into speakable sentences, merging very short ones."""
    if not text.strip():
        return []
    raw = _SENTENCE_RE.split(text.strip())
    merged: list[str] = []
    buf = ""
    for s in raw:
        buf = (buf + " " + s).strip() if buf else s
        if len(buf) >= 40 or s == raw[-1]:
            merged.append(buf)
            buf = ""
    if buf:
        merged.append(buf)
    return merged


class Speaker:
    """
    Async TTS speaker.

    Usage::
        await speaker.say("Hello, how can I help you?")
        await speaker.interrupt()   # stop mid-sentence
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[str | None] = asyncio.Queue()
        self._playing = False
        self._interrupted = False
        self._task: asyncio.Task | None = None
        self._mixer_ready = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    async def start(self) -> None:
        if _PYGAME_AVAILABLE:
            pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
            self._mixer_ready = True
        bus.subscribe(EventType.SPEECH_START, self._on_speech_start)
        self._task = asyncio.create_task(self._worker(), name="tts_worker")
        logger.info("Speaker started (voice={}).", settings.tts_voice)

    async def stop(self) -> None:
        bus.unsubscribe(EventType.SPEECH_START, self._on_speech_start)
        await self._queue.put(None)   # sentinel
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._mixer_ready:
            pygame.mixer.quit()

    # ── Public API ────────────────────────────────────────────────────────────
    async def say(self, text: str) -> None:
        """Queue text for speech. Returns immediately."""
        if not text.strip():
            return
        for sentence in split_sentences(text):
            await self._queue.put(sentence)

    async def say_and_wait(self, text: str) -> None:
        """Say text and wait until all of it has been spoken."""
        await self.say(text)
        await self._queue.join()

    async def interrupt(self) -> None:
        """Stop current speech and clear the queue."""
        self._interrupted = True
        # Drain the queue
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except asyncio.QueueEmpty:
                break
        if self._mixer_ready and pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
        await bus.publish(Event(type=EventType.TTS_INTERRUPTED, source="tts"))
        logger.debug("TTS interrupted.")

    # ── Internal worker ───────────────────────────────────────────────────────
    async def _worker(self) -> None:
        while True:
            text = await self._queue.get()
            if text is None:
                self._queue.task_done()
                break
            self._interrupted = False
            try:
                await self._speak_sentence(text)
            except Exception:
                logger.exception("TTS error for: '{}'", text[:60])
            finally:
                self._queue.task_done()

    async def _speak_sentence(self, text: str) -> None:
        if not text.strip():
            return

        await bus.publish(Event(type=EventType.TTS_START, data=text, source="tts"))
        self._playing = True

        # Generate audio bytes
        audio_bytes = await self._synthesise(text)
        if not audio_bytes or self._interrupted:
            self._playing = False
            return

        # Play audio
        await self._play(audio_bytes)
        self._playing = False

        if not self._interrupted:
            await bus.publish(Event(type=EventType.TTS_DONE, source="tts"))

    async def _synthesise(self, text: str) -> bytes | None:
        """Generate MP3 bytes from edge-tts."""
        if not _EDGE_AVAILABLE:
            logger.debug("TTS (muted): {}", text)
            return None

        try:
            communicate = edge_tts.Communicate(
                text=text,
                voice=settings.tts_voice,
                rate=settings.tts_rate,
                volume=settings.tts_volume,
            )
            buf = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    buf.write(chunk["data"])
                if self._interrupted:
                    return None
            return buf.getvalue()
        except Exception:
            logger.exception("edge-tts synthesis failed.")
            return None

    async def _play(self, audio_bytes: bytes) -> None:
        """Play MP3 bytes using pygame mixer."""
        if not self._mixer_ready or not _PYGAME_AVAILABLE:
            return

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._play_sync, audio_bytes)

    def _play_sync(self, audio_bytes: bytes) -> None:
        """Blocking audio playback (runs in thread pool)."""
        import time
        buf = io.BytesIO(audio_bytes)
        pygame.mixer.music.load(buf, "mp3")
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            if self._interrupted:
                pygame.mixer.music.stop()
                break
            time.sleep(0.02)

    # ── Event handler ─────────────────────────────────────────────────────────
    async def _on_speech_start(self, event: Event) -> None:
        """User started speaking – interrupt lia immediately."""
        if self._playing:
            await self.interrupt()


# Module singleton
speaker: Speaker = Speaker()
