"""
Voice Activity Detection using Silero VAD.
Wraps the model in a stateful detector that emits speech_start / speech_end
events and accumulates speech audio into utterance buffers.
"""
from __future__ import annotations

import asyncio
import sys
from collections import deque
from dataclasses import dataclass, field
from typing import Deque

import numpy as np
from loguru import logger

if sys.version_info >= (3, 11):
    from enum import auto, StrEnum
else:
    from enum import auto
    from enum import Enum

    class StrEnum(str, Enum):  # type: ignore[no-redef]
        @staticmethod
        def _generate_next_value_(name, start, count, last_values):
            return name.lower()

# torch/silero is optional at import time so unit tests work without hardware
try:
    import torch  # type: ignore
    _TORCH_AVAILABLE = True
except ImportError:
    torch = None  # type: ignore
    _TORCH_AVAILABLE = False
    logger.warning("torch not installed – VAD will pass all audio through.")

from assistant.audio.microphone import AudioFrame
from assistant.config import settings
from assistant.core.events import Event, EventType, bus


class VADState(StrEnum):
    SILENCE = auto()
    SPEECH = auto()


@dataclass
class Utterance:
    """A complete speech segment ready for STT."""
    audio: np.ndarray     # concatenated float32 PCM
    sample_rate: int


class SileroVAD:
    """
    Loads the Silero VAD model once and runs it frame-by-frame.

    The detector publishes:
      • EventType.SPEECH_START  – voice detected
      • EventType.SPEECH_END    – silence detected, Utterance attached to event
    """

    # Silero VAD expects exactly 512 samples at 16 kHz (32 ms)
    _WINDOW_SAMPLES = 512

    def __init__(
        self,
        threshold: float = 0.50,
        min_speech_ms: int = 250,
        silence_ms: int | None = None,
    ) -> None:
        self._threshold = threshold
        self._min_speech_samples = int(settings.stt_sample_rate * min_speech_ms / 1000)
        self._silence_samples = int(
            settings.stt_sample_rate * (silence_ms or settings.stt_silence_ms) / 1000
        )
        self._model: torch.jit.ScriptModule | None = None
        self._state = VADState.SILENCE
        self._speech_buf: list[np.ndarray] = []
        self._silence_counter = 0
        self._residual = np.array([], dtype=np.float32)

    # ── Initialisation ────────────────────────────────────────────────────────
    async def load(self) -> None:
        """Download/load Silero VAD model (first call downloads ~2 MB)."""
        if not _TORCH_AVAILABLE:
            logger.info("VAD: torch unavailable – running in pass-through mode.")
            return
        logger.info("Loading Silero VAD model…")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._load_sync)
        logger.info("Silero VAD ready.")

    def _load_sync(self) -> None:
        if not _TORCH_AVAILABLE:
            return
        model, _ = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            onnx=False,
            verbose=False,
        )
        model.eval()
        self._model = model

    # ── Frame processing ──────────────────────────────────────────────────────
    def _score_window(self, window: np.ndarray) -> float:
        """Return VAD confidence for a single 512-sample window."""
        if self._model is None or not _TORCH_AVAILABLE:
            return 1.0   # no VAD → treat everything as speech
        tensor = torch.from_numpy(window).unsqueeze(0)
        with torch.no_grad():
            prob = self._model(tensor, settings.stt_sample_rate).item()
        return float(prob)

    async def process_frame(self, frame: AudioFrame) -> None:
        """Feed one microphone frame through the VAD state machine."""
        # Concatenate residual from previous frame
        audio = np.concatenate([self._residual, frame.data])
        pos = 0

        while pos + self._WINDOW_SAMPLES <= len(audio):
            window = audio[pos: pos + self._WINDOW_SAMPLES]
            pos += self._WINDOW_SAMPLES
            prob = self._score_window(window)

            if self._state == VADState.SILENCE:
                if prob >= self._threshold:
                    self._state = VADState.SPEECH
                    self._speech_buf = [window]
                    self._silence_counter = 0
                    await bus.publish(Event(type=EventType.SPEECH_START, source="vad"))
                    logger.debug("VAD: speech started (p={:.2f})", prob)
            else:  # SPEECH
                self._speech_buf.append(window)
                if prob < self._threshold:
                    self._silence_counter += self._WINDOW_SAMPLES
                    if self._silence_counter >= self._silence_samples:
                        await self._emit_utterance()
                else:
                    self._silence_counter = 0

        self._residual = audio[pos:]

    async def _emit_utterance(self) -> None:
        combined = np.concatenate(self._speech_buf)
        if len(combined) >= self._min_speech_samples:
            utterance = Utterance(audio=combined, sample_rate=settings.stt_sample_rate)
            await bus.publish(
                Event(type=EventType.SPEECH_END, data=utterance, source="vad")
            )
            logger.debug("VAD: utterance emitted ({:.2f}s)", len(combined) / settings.stt_sample_rate)
        else:
            logger.debug("VAD: utterance too short, discarded.")
        self._state = VADState.SILENCE
        self._speech_buf = []
        self._silence_counter = 0


# Module-level singleton
vad: SileroVAD = SileroVAD()
