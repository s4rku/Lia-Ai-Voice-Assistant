"""
Microphone capture module.

Handles the common mismatch between device native sample rates (44100/48000 Hz,
stereo) and what Whisper/VAD expect (16000 Hz, mono).

Strategy:
  1. Query the device's native sample rate and channel count.
  2. Open the stream at those native settings.
  3. Downmix to mono and resample to TARGET_SR (16000 Hz) in the callback
     using a simple decimation approach (no scipy needed for integer ratios,
     scipy.signal.resample used for non-integer ratios).
  4. Push TARGET_SR mono AudioFrames onto the asyncio queue.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Deque

import numpy as np
from loguru import logger

from assistant.config import settings

try:
    import sounddevice as sd  # type: ignore
    _SD_AVAILABLE = True
except (ImportError, OSError, Exception):
    sd = None  # type: ignore
    _SD_AVAILABLE = False
    logger.warning("sounddevice not available – microphone will be silent.")

try:
    from scipy.signal import resample as scipy_resample  # type: ignore
    _SCIPY_AVAILABLE = True
except (ImportError, OSError, Exception):
    scipy_resample = None  # type: ignore
    _SCIPY_AVAILABLE = False

TARGET_SR = 16_000   # Hz – what VAD and STT expect


@dataclass
class AudioFrame:
    """Single chunk of float32 PCM audio at TARGET_SR Hz, mono."""
    data: np.ndarray    # shape (N,), dtype float32, range −1…+1
    sample_rate: int = TARGET_SR


def _resample(audio: np.ndarray, from_sr: int, to_sr: int) -> np.ndarray:
    """Resample 1-D float32 array from from_sr to to_sr."""
    if from_sr == to_sr:
        return audio
    # Integer decimation (e.g. 48000→16000 = divide by 3)
    if from_sr % to_sr == 0:
        step = from_sr // to_sr
        return audio[::step]
    # Scipy resample for non-integer ratios
    if _SCIPY_AVAILABLE:
        n_out = int(len(audio) * to_sr / from_sr)
        return scipy_resample(audio, n_out).astype(np.float32)
    # Fallback: linear interpolation
    x_old = np.linspace(0, 1, len(audio))
    x_new = np.linspace(0, 1, int(len(audio) * to_sr / from_sr))
    return np.interp(x_new, x_old, audio).astype(np.float32)


class MicrophoneStream:
    """
    Async microphone stream that always delivers 16kHz mono AudioFrames.
    Opens the device at its native settings and resamples internally.
    """

    def __init__(
        self,
        chunk_ms: int | None = None,
        device: int | str | None = None,
    ) -> None:
        self._target_sr   = TARGET_SR
        self._chunk_ms    = chunk_ms or settings.stt_chunk_ms
        self._device      = device
        self._native_sr   = TARGET_SR    # resolved on start()
        self._native_ch   = 1            # resolved on start()
        self._queue: asyncio.Queue[AudioFrame | None] = asyncio.Queue(maxsize=400)
        self._stream      = None
        self._running     = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._resample_buf = np.array([], dtype=np.float32)  # leftover samples

    def _resolve_device_params(self) -> tuple[int, int, int]:
        """Return (device_id, native_sr, native_channels)."""
        if not _SD_AVAILABLE:
            return (self._device or 0, TARGET_SR, 1)

        dev_id = self._device
        if dev_id is None:
            try:
                info = sd.query_devices(kind="input")
                dev_id = sd.default.device[0]
            except Exception:
                info = {"default_samplerate": TARGET_SR, "max_input_channels": 1}
                dev_id = None
        else:
            info = sd.query_devices(int(dev_id))

        native_sr = int(info.get("default_samplerate", TARGET_SR))
        native_ch = max(1, min(int(info.get("max_input_channels", 1)), 2))
        return (dev_id, native_sr, native_ch)

    def _sd_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: object,
        status: object,
    ) -> None:
        if status:
            logger.debug("Mic status: {}", status)
        if not (self._loop and self._running):
            return

        # Downmix to mono
        if indata.ndim > 1 and indata.shape[1] > 1:
            mono = indata.mean(axis=1)
        else:
            mono = indata[:, 0] if indata.ndim > 1 else indata.copy()

        # Resample to TARGET_SR
        if self._native_sr != self._target_sr:
            mono = _resample(mono, self._native_sr, self._target_sr)

        mono = mono.astype(np.float32)

        # Emit fixed-size chunks
        combined = np.concatenate([self._resample_buf, mono])
        target_chunk = int(self._target_sr * self._chunk_ms / 1000)
        pos = 0
        while pos + target_chunk <= len(combined):
            chunk = combined[pos: pos + target_chunk]
            pos  += target_chunk
            frame = AudioFrame(data=chunk, sample_rate=self._target_sr)
            try:
                self._loop.call_soon_threadsafe(self._queue.put_nowait, frame)
            except (asyncio.QueueFull, RuntimeError):
                pass
        self._resample_buf = combined[pos:]

    async def start(self) -> None:
        if self._running:
            return
        if not _SD_AVAILABLE:
            logger.warning("Microphone not started – sounddevice unavailable.")
            self._running = True
            return

        dev_id, self._native_sr, self._native_ch = self._resolve_device_params()

        # Compute native chunk size (we feed larger chunks to sounddevice)
        native_chunk = int(self._native_sr * self._chunk_ms / 1000)

        self._loop = asyncio.get_running_loop()
        self._running = True

        self._stream = sd.InputStream(
            samplerate=self._native_sr,
            channels=self._native_ch,
            dtype="float32",
            blocksize=native_chunk,
            device=dev_id if dev_id is not None else None,
            callback=self._sd_callback,
        )
        self._stream.start()
        logger.info(
            "Microphone started — device={} native={}Hz/{}ch → target={}Hz/mono  chunk={}ms",
            dev_id or "default",
            self._native_sr, self._native_ch,
            self._target_sr, self._chunk_ms,
        )

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        await self._queue.put(None)
        logger.info("Microphone stopped.")

    async def stream(self):
        """Async generator yielding AudioFrames until stop() is called."""
        if not self._running:
            await self.start()
        while True:
            frame = await self._queue.get()
            if frame is None:
                break
            yield frame

    def get_device_list(self) -> list[dict]:
        if not _SD_AVAILABLE:
            return []
        return [
            {"id": i, "name": d["name"],
             "sr": int(d["default_samplerate"]),
             "channels": d["max_input_channels"]}
            for i, d in enumerate(sd.query_devices())
            if d["max_input_channels"] > 0
        ]


# Module singleton — device resolved from settings at import time
microphone: MicrophoneStream = MicrophoneStream(device=settings.microphone_device)
