"""
Microphone capture module.
Streams raw PCM frames from the default input device using sounddevice.
Frames are placed on an asyncio queue for downstream consumers (VAD, wake word).
"""
from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from typing import Deque

import numpy as np
from loguru import logger

from assistant.config import settings

# sounddevice requires PortAudio – guard import so unit tests work without hardware
try:
    import sounddevice as sd  # type: ignore
    _SD_AVAILABLE = True
except (ImportError, OSError):
    sd = None  # type: ignore
    _SD_AVAILABLE = False
    logger.warning("sounddevice not available – microphone will be silent.")


@dataclass
class AudioFrame:
    """A single chunk of 16-bit PCM audio at 16 kHz mono."""
    data: np.ndarray          # shape (N,), dtype float32  −1…+1
    sample_rate: int = 16_000


class MicrophoneStream:
    """
    Wraps sounddevice's InputStream and exposes an async generator of AudioFrames.

    Usage::

        async for frame in mic.stream():
            process(frame)
    """

    def __init__(
        self,
        sample_rate: int | None = None,
        chunk_ms: int | None = None,
        device: int | str | None = None,
    ) -> None:
        self._sr = sample_rate or settings.stt_sample_rate
        self._chunk_ms = chunk_ms or settings.stt_chunk_ms
        self._device = device
        self._chunk_frames = int(self._sr * self._chunk_ms / 1000)
        self._queue: asyncio.Queue[AudioFrame | None] = asyncio.Queue(maxsize=200)
        self._stream: sd.InputStream | None = None
        self._running = False
        self._loop: asyncio.AbstractEventLoop | None = None

    # ── Internal sounddevice callback (runs in a C thread) ───────────────────
    def _sd_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: object,
        status: sd.CallbackFlags,
    ) -> None:
        if status:
            logger.debug("Microphone status: {}", status)
        if self._loop and self._running:
            frame = AudioFrame(data=indata[:, 0].copy(), sample_rate=self._sr)
            try:
                self._loop.call_soon_threadsafe(self._queue.put_nowait, frame)
            except asyncio.QueueFull:
                pass  # drop frame rather than block

    # ── Public API ───────────────────────────────────────────────────────────
    async def start(self) -> None:
        if self._running:
            return
        if not _SD_AVAILABLE:
            logger.warning("Microphone not started – sounddevice unavailable.")
            self._running = True
            return
        self._loop = asyncio.get_running_loop()
        self._running = True
        self._stream = sd.InputStream(
            samplerate=self._sr,
            channels=1,
            dtype="float32",
            blocksize=self._chunk_frames,
            device=self._device,
            callback=self._sd_callback,
        )
        self._stream.start()
        logger.info(
            "Microphone started — {}Hz, {}ms chunks (device={})",
            self._sr, self._chunk_ms, self._device or "default",
        )

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        await self._queue.put(None)  # sentinel to unblock consumers
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
        """Return list of available audio input devices."""
        if not _SD_AVAILABLE:
            return []
        devices = []
        for i, dev in enumerate(sd.query_devices()):
            if dev["max_input_channels"] > 0:
                devices.append({"id": i, "name": dev["name"]})
        return devices


# ── Module-level singleton ────────────────────────────────────────────────────
microphone: MicrophoneStream = MicrophoneStream()
