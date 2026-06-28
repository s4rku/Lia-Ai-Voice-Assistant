"""
Speech-to-Text using faster-whisper.

Pipeline
────────
1. VAD emits EventType.SPEECH_END with an Utterance (raw PCM).
2. Transcriber picks it up, runs faster-whisper in a thread pool.
3. Publishes EventType.TRANSCRIPT_READY with the text string.

Whisper model is lazy-loaded on first use (avoids 2–4 s cold start at import).
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Literal

import numpy as np
from loguru import logger

from assistant.audio.vad import Utterance
from assistant.config import settings
from assistant.core.events import Event, EventType, bus

# faster-whisper is optional at import time so unit tests don't need it
try:
    from faster_whisper import WhisperModel  # type: ignore
    _FW_AVAILABLE = True
except ImportError:
    WhisperModel = None  # type: ignore
    _FW_AVAILABLE = False
    logger.warning("faster-whisper not installed – STT will return empty strings.")


@dataclass
class TranscriptResult:
    text: str
    language: str
    confidence: float
    duration_s: float
    latency_ms: float


class Transcriber:
    """
    Async wrapper around faster-whisper.
    Subscribes to SPEECH_END events and publishes TRANSCRIPT_READY.
    """

    def __init__(self) -> None:
        self._model: WhisperModel | None = None  # lazy
        self._loading = False
        self._lock = asyncio.Lock()

    # ── Model loading ─────────────────────────────────────────────────────────
    async def ensure_loaded(self) -> None:
        """Load Whisper model if not already loaded (thread-safe)."""
        async with self._lock:
            if self._model is not None or not _FW_AVAILABLE:
                return
            if self._loading:
                return
            self._loading = True
        logger.info(
            "Loading Whisper model '{}' on {}…",
            settings.stt_model, settings.stt_device,
        )
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._load_sync)
        logger.info("Whisper model loaded.")

    def _load_sync(self) -> None:
        self._model = WhisperModel(
            settings.stt_model,
            device=settings.stt_device,
            compute_type="int8" if settings.stt_device == "cpu" else "float16",
        )

    # ── Transcription ─────────────────────────────────────────────────────────
    async def transcribe(self, utterance: Utterance) -> TranscriptResult:
        """Transcribe a speech utterance. Returns TranscriptResult."""
        await self.ensure_loaded()

        if not _FW_AVAILABLE or self._model is None:
            return TranscriptResult(
                text="", language="en", confidence=0.0,
                duration_s=len(utterance.audio) / utterance.sample_rate,
                latency_ms=0.0,
            )

        t0 = time.perf_counter()
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, self._transcribe_sync, utterance.audio, utterance.sample_rate
        )
        latency = (time.perf_counter() - t0) * 1000
        result.latency_ms = latency
        logger.debug(
            "STT: '{}' (lang={}, conf={:.2f}, {:.0f}ms)",
            result.text, result.language, result.confidence, latency,
        )
        return result

    def _transcribe_sync(self, audio: np.ndarray, sample_rate: int) -> TranscriptResult:
        """Blocking transcription – runs in thread pool."""
        segments, info = self._model.transcribe(  # type: ignore[union-attr]
            audio,
            language=settings.stt_language if settings.stt_language != "auto" else None,
            beam_size=5,
            vad_filter=False,   # VAD already done upstream
            word_timestamps=False,
        )
        text_parts: list[str] = []
        avg_conf = 0.0
        count = 0
        for seg in segments:
            text_parts.append(seg.text.strip())
            avg_conf += getattr(seg, "avg_logprob", 0.0)
            count += 1

        text = " ".join(text_parts).strip()
        confidence = float(np.exp(avg_conf / max(count, 1)))
        return TranscriptResult(
            text=text,
            language=info.language,
            confidence=confidence,
            duration_s=len(audio) / sample_rate,
            latency_ms=0.0,     # filled in by caller
        )

    # ── Event integration ─────────────────────────────────────────────────────
    async def start(self) -> None:
        """Subscribe to SPEECH_END events and start processing."""
        bus.subscribe(EventType.SPEECH_END, self._on_speech_end)
        # Pre-warm model in background
        asyncio.create_task(self.ensure_loaded(), name="whisper_load")
        logger.info("Transcriber started.")

    async def stop(self) -> None:
        bus.unsubscribe(EventType.SPEECH_END, self._on_speech_end)

    async def _on_speech_end(self, event: Event) -> None:
        utterance: Utterance = event.data
        result = await self.transcribe(utterance)
        if result.text:
            await bus.publish(
                Event(type=EventType.TRANSCRIPT_READY, data=result, source="stt")
            )


# Module singleton
transcriber: Transcriber = Transcriber()
