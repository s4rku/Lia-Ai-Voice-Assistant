"""
Voice Activity Detection.

Two backends:
  1. Silero VAD (neural, torch)   – best quality, needs torch
  2. Energy VAD (RMS threshold)   – pure numpy fallback, no deps

State machine: SILENCE → SPEECH → SILENCE
  SPEECH_START  published when voice begins
  SPEECH_END    published with full Utterance when silence detected
"""
from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass

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

# torch – optional, hard-blocked by App Control on some machines
try:
    import torch  # type: ignore
    _TORCH_AVAILABLE = True
except (ImportError, OSError, Exception):
    torch = None  # type: ignore
    _TORCH_AVAILABLE = False
    logger.info("torch unavailable – VAD using energy-based fallback.")

from assistant.audio.microphone import AudioFrame
from assistant.config import settings
from assistant.core.events import Event, EventType, bus


class VADState(StrEnum):
    SILENCE = auto()
    SPEECH  = auto()


@dataclass
class Utterance:
    """A complete speech segment ready for STT."""
    audio: np.ndarray   # float32 PCM, concatenated windows
    sample_rate: int


# ─────────────────────────────────────────────────────────────────────────────
#  Energy VAD  (pure numpy – no torch required)
# ─────────────────────────────────────────────────────────────────────────────
class EnergyVAD:
    """
    Adaptive energy-based voice detector.

    Measures a rolling noise floor during silence and detects speech as
    energy significantly above that floor. This handles rooms with constant
    background noise (fans, HVAC, mic hiss) without needing manual calibration.

    Tuning (all configurable via settings):
      speech_ratio      – speech RMS must be this many times above noise floor
      pre_roll_ms       – keep N ms before speech onset (avoids clipping)
      silence_ms        – silence duration that ends an utterance
      min_speech_ms     – discard utterances shorter than this
      noise_update_rate – how fast the noise floor adapts (0–1, lower=slower)
    """

    _WINDOW_SAMPLES = 512   # 32 ms @ 16 kHz

    def __init__(
        self,
        energy_threshold: float = 0.015,  # kept for compatibility, used as floor
        speech_ratio: float = 3.5,         # speech must be N× above noise
        pre_roll_ms: int = 200,
        silence_ms: int | None = None,
        min_speech_ms: int = 300,
        noise_update_rate: float = 0.05,   # EMA rate for noise floor
    ) -> None:
        sr = settings.stt_sample_rate
        self._hard_floor    = energy_threshold   # never go below this
        self._speech_ratio  = speech_ratio
        self._silence_samples    = int(sr * (silence_ms or settings.stt_silence_ms) / 1000)
        self._min_speech_samples = int(sr * min_speech_ms / 1000)
        self._pre_roll_size      = int(sr * pre_roll_ms / 1000)
        self._noise_rate         = noise_update_rate

        # State
        self._state           = VADState.SILENCE
        self._speech_buf:  list[np.ndarray] = []
        self._pre_roll:    list[np.ndarray] = []
        self._silence_counter = 0
        self._residual        = np.array([], dtype=np.float32)

        # Adaptive noise floor – start low, adapts during silence quickly
        self._noise_floor: float = 0.008

    def _rms(self, window: np.ndarray) -> float:
        return float(np.sqrt(np.mean(window ** 2)))

    def _is_speech(self, rms: float) -> bool:
        """True when RMS is clearly above the noise floor."""
        threshold = max(self._hard_floor, self._noise_floor * self._speech_ratio)
        return rms >= threshold

    def _update_noise_floor(self, rms: float) -> None:
        """EMA update of noise floor – only in silence state."""
        self._noise_floor = (
            (1 - self._noise_rate) * self._noise_floor
            + self._noise_rate * rms
        )
        # Never let noise floor go above hard floor
        self._noise_floor = min(self._noise_floor, self._hard_floor * 2)

    async def process_frame(self, frame: AudioFrame) -> None:
        audio = np.concatenate([self._residual, frame.data])
        pos = 0

        while pos + self._WINDOW_SAMPLES <= len(audio):
            window = audio[pos: pos + self._WINDOW_SAMPLES]
            pos   += self._WINDOW_SAMPLES
            rms    = self._rms(window)
            speech = self._is_speech(rms)

            if self._state == VADState.SILENCE:
                # Update noise model while silent
                if not speech:
                    self._update_noise_floor(rms)

                # Maintain pre-roll ring buffer
                self._pre_roll.append(window)
                total_pre = sum(len(w) for w in self._pre_roll)
                while len(self._pre_roll) > 1 and \
                      total_pre - len(self._pre_roll[0]) >= self._pre_roll_size:
                    total_pre -= len(self._pre_roll.pop(0))

                if speech:
                    self._state = VADState.SPEECH
                    self._speech_buf = list(self._pre_roll) + [window]
                    self._silence_counter = 0
                    self._pre_roll = []
                    await bus.publish(Event(type=EventType.SPEECH_START, source="vad"))
                    logger.debug(
                        "VAD[energy]: speech start (rms={:.4f} noise_floor={:.4f})",
                        rms, self._noise_floor,
                    )

            else:  # SPEECH
                self._speech_buf.append(window)
                if not speech:
                    self._silence_counter += self._WINDOW_SAMPLES
                    if self._silence_counter >= self._silence_samples:
                        await self._emit_utterance()
                else:
                    self._silence_counter = 0

        self._residual = audio[pos:]

    async def _emit_utterance(self) -> None:
        combined = np.concatenate(self._speech_buf)
        self._state = VADState.SILENCE
        self._speech_buf = []
        self._silence_counter = 0
        self._pre_roll = []

        dur = len(combined) / settings.stt_sample_rate
        if len(combined) >= self._min_speech_samples:
            utt = Utterance(audio=combined, sample_rate=settings.stt_sample_rate)
            logger.debug("VAD[energy]: utterance emitted ({:.2f}s, noise_floor={:.4f})",
                         dur, self._noise_floor)
            await bus.publish(Event(type=EventType.SPEECH_END, data=utt, source="vad"))
        else:
            logger.debug("VAD[energy]: utterance too short ({:.2f}s), discarded.", dur)


# ─────────────────────────────────────────────────────────────────────────────
#  Silero VAD  (neural, torch-based)
# ─────────────────────────────────────────────────────────────────────────────
class SileroVAD:
    _WINDOW_SAMPLES = 512

    def __init__(
        self,
        threshold: float = 0.50,
        min_speech_ms: int = 250,
        silence_ms: int | None = None,
    ) -> None:
        sr = settings.stt_sample_rate
        self._threshold          = threshold
        self._min_speech_samples = int(sr * min_speech_ms / 1000)
        self._silence_samples    = int(sr * (silence_ms or settings.stt_silence_ms) / 1000)
        self._model              = None
        self._state              = VADState.SILENCE
        self._speech_buf: list[np.ndarray] = []
        self._silence_counter    = 0
        self._residual           = np.array([], dtype=np.float32)

    async def load(self) -> None:
        if not _TORCH_AVAILABLE:
            return
        logger.info("Loading Silero VAD model…")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._load_sync)
        logger.info("Silero VAD ready.")

    def _load_sync(self) -> None:
        model, _ = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            onnx=False,
            verbose=False,
        )
        model.eval()
        self._model = model

    def _score(self, window: np.ndarray) -> float:
        if self._model is None:
            return 0.0
        tensor = torch.from_numpy(window).unsqueeze(0)
        with torch.no_grad():
            return float(self._model(tensor, settings.stt_sample_rate).item())

    async def process_frame(self, frame: AudioFrame) -> None:
        audio = np.concatenate([self._residual, frame.data])
        pos = 0
        while pos + self._WINDOW_SAMPLES <= len(audio):
            window = audio[pos: pos + self._WINDOW_SAMPLES]
            pos   += self._WINDOW_SAMPLES
            prob   = self._score(window)

            if self._state == VADState.SILENCE:
                if prob >= self._threshold:
                    self._state = VADState.SPEECH
                    self._speech_buf = [window]
                    self._silence_counter = 0
                    await bus.publish(Event(type=EventType.SPEECH_START, source="vad"))
            else:
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
        self._state = VADState.SILENCE
        self._speech_buf = []
        self._silence_counter = 0
        if len(combined) >= self._min_speech_samples:
            utt = Utterance(audio=combined, sample_rate=settings.stt_sample_rate)
            await bus.publish(Event(type=EventType.SPEECH_END, data=utt, source="vad"))


# ─────────────────────────────────────────────────────────────────────────────
#  Public interface – auto-selects backend
# ─────────────────────────────────────────────────────────────────────────────
class VAD:
    """
    Unified VAD.  Uses Silero when torch is available, energy-based otherwise.
    Exposes the same load() / process_frame() interface.
    """

    def __init__(self) -> None:
        if _TORCH_AVAILABLE:
            self._backend: SileroVAD | EnergyVAD = SileroVAD()
            logger.info("VAD: using Silero (neural).")
        else:
            self._backend = EnergyVAD(
                energy_threshold=settings.vad_energy_threshold,
                speech_ratio=settings.vad_speech_ratio,
            )
            logger.info(
                "VAD: using energy-based fallback (threshold={}, ratio={}).",
                settings.vad_energy_threshold, settings.vad_speech_ratio,
            )

    async def load(self) -> None:
        if isinstance(self._backend, SileroVAD):
            await self._backend.load()

    async def process_frame(self, frame: AudioFrame) -> None:
        await self._backend.process_frame(frame)


# Module singleton
vad: VAD = VAD()
