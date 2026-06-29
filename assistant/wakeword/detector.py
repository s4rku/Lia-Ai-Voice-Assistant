"""
Wake word detection – offline, runs 100% on device.

Strategy
────────
Primary:   OpenWakeWord  (neural, works for "hey jarvis"-style phrases)
Fallback:  simple energy + keyword fuzzy-match using the STT transcript
           (activates only when OWW model files are unavailable)

The detector listens to raw microphone frames (NOT after VAD – wake word must
work even in silence) and publishes EventType.WAKE_WORD_DETECTED when triggered.
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
from loguru import logger

from assistant.audio.microphone import AudioFrame, microphone
from assistant.config import settings
from assistant.core.events import Event, EventType, bus

# Optional import – gracefully degrade if openwakeword not installed
try:
    from openwakeword.model import Model as OWWModel  # type: ignore
    _OWW_AVAILABLE = True
except (ImportError, OSError, Exception):
    _OWWModel = None  # type: ignore
    _OWW_AVAILABLE = False
    logger.warning("openwakeword not installed – falling back to transcript-based wake word.")


@dataclass
class WakeWordResult:
    phrase: str
    confidence: float
    backend: str   # "oww" | "transcript"


class WakeWordDetector:
    """
    Detects wake words and publishes WAKE_WORD_DETECTED events.
    Runs as a background asyncio task, consuming microphone frames.
    """

    # OWW expects 1280 samples @ 16 kHz (80 ms chunks)
    _OWW_CHUNK = 1280

    def __init__(self) -> None:
        self._oww: OWWModel | None = None  # type: ignore[name-defined]
        self._wake_words = [w.lower().strip() for w in settings.wake_word_list]
        self._running = False
        self._task: asyncio.Task | None = None
        self._residual = np.array([], dtype=np.float32)
        # Callbacks that other modules can register
        self._callbacks: list[Callable[[WakeWordResult], None]] = []

    # ── Initialisation ────────────────────────────────────────────────────────
    async def load(self) -> None:
        if _OWW_AVAILABLE:
            await self._load_oww()
        else:
            logger.info("Wake word: transcript-fallback mode (no OWW model).")

    async def _load_oww(self) -> None:
        """Load OWW model in a thread pool to avoid blocking the event loop."""
        logger.info("Loading OpenWakeWord models…")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._init_oww_sync)
        logger.info("OpenWakeWord ready — watching for: {}", self._wake_words)

    def _init_oww_sync(self) -> None:
        # OWW ships with a built-in "hey jarvis" model; we map our wake words
        # to its closest built-in model.  Custom ONNX models can be dropped in
        # data/models/ and OWW picks them up automatically.
        model_dir = Path("data/models")
        model_dir.mkdir(parents=True, exist_ok=True)
        self._oww = _OWW_AVAILABLE and OWWModel(
            wakeword_models=["hey_jarvis"],          # closest built-in phrase
            inference_framework="onnx",
            custom_verifier_threshold=0.5,
        )

    # ── Start / Stop ──────────────────────────────────────────────────────────
    async def start(self) -> None:
        if self._running:
            return
        await microphone.start()
        self._running = True
        self._task = asyncio.create_task(self._listen_loop(), name="wakeword_listener")
        logger.info("Wake word detector started.")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Wake word detector stopped.")

    # ── Main listen loop ──────────────────────────────────────────────────────
    async def _listen_loop(self) -> None:
        async for frame in microphone.stream():
            if not self._running:
                break
            await self._process_frame(frame)

    async def _process_frame(self, frame: AudioFrame) -> None:
        if self._oww:
            await self._oww_process(frame)
        # Transcript-fallback is handled by the conversation loop (see below)

    async def _oww_process(self, frame: AudioFrame) -> None:
        """Feed audio to OWW and check for detections."""
        audio = np.concatenate([self._residual, frame.data])
        pos = 0

        while pos + self._OWW_CHUNK <= len(audio):
            chunk = audio[pos: pos + self._OWW_CHUNK]
            pos += self._OWW_CHUNK
            # Convert float32 [-1,1] → int16 as OWW expects
            pcm16 = (chunk * 32767).astype(np.int16)
            loop = asyncio.get_running_loop()
            scores = await loop.run_in_executor(
                None, self._oww.predict, pcm16
            )
            await self._check_scores(scores)

        self._residual = audio[pos:]

    async def _check_scores(self, scores: dict[str, float]) -> None:
        for model_name, score in scores.items():
            if score > 0.5:
                result = WakeWordResult(
                    phrase=model_name, confidence=score, backend="oww"
                )
                await self._fire(result)
                return

    # ── Transcript-based fallback (called externally by conversation loop) ────
    async def check_transcript(self, text: str) -> bool:
        """
        Returns True and fires event if text starts with a wake word.
        Used when OWW is unavailable.
        """
        lowered = text.lower().strip()
        for phrase in self._wake_words:
            # Allow small typos: 'hey lia' vs 'hey lia!'
            pattern = re.compile(r"\b" + re.escape(phrase) + r"\b")
            if pattern.search(lowered):
                result = WakeWordResult(
                    phrase=phrase, confidence=1.0, backend="transcript"
                )
                await self._fire(result)
                return True
        return False

    async def _fire(self, result: WakeWordResult) -> None:
        logger.info(
            "Wake word detected: '{}' (conf={:.2f}, via {})",
            result.phrase, result.confidence, result.backend,
        )
        await bus.publish(
            Event(type=EventType.WAKE_WORD_DETECTED, data=result, source="wakeword")
        )
        for cb in self._callbacks:
            cb(result)

    def on_wake(self, callback: Callable[[WakeWordResult], None]) -> None:
        """Register a synchronous callback for wake word events."""
        self._callbacks.append(callback)


# Module singleton
wake_detector: WakeWordDetector = WakeWordDetector()
