"""
Speech-to-Text – three backends, automatic fallback chain:

1. OpenAI Whisper API   – best quality, needs paid API key + internet
2. Google Speech API    – free, no key, needs internet (uses SpeechRecognition lib)
3. faster-whisper       – local, needs torch (blocked on some machines)

Pipeline:
  VAD emits EventType.SPEECH_END  (Utterance with raw PCM)
       ↓
  Transcriber.transcribe(utterance)
       ↓
  Publishes EventType.TRANSCRIPT_READY  (TranscriptResult)
"""
from __future__ import annotations

import asyncio
import io
import time
import wave
from dataclasses import dataclass

import numpy as np
from loguru import logger

from assistant.audio.vad import Utterance
from assistant.config import settings
from assistant.core.events import Event, EventType, bus

# ── OpenAI Whisper API ────────────────────────────────────────────────────────
try:
    from openai import AsyncOpenAI  # type: ignore
    _OPENAI_AVAILABLE = True
except (ImportError, OSError, Exception):
    AsyncOpenAI = None  # type: ignore
    _OPENAI_AVAILABLE = False

# ── Google Speech Recognition (free, no key) ──────────────────────────────────
try:
    import speech_recognition as sr_lib  # type: ignore
    _SR_AVAILABLE = True
except (ImportError, OSError, Exception):
    sr_lib = None  # type: ignore
    _SR_AVAILABLE = False

# ── faster-whisper (local, needs torch) ───────────────────────────────────────
try:
    from faster_whisper import WhisperModel  # type: ignore
    _FW_AVAILABLE = True
except (ImportError, OSError, Exception):
    WhisperModel = None  # type: ignore
    _FW_AVAILABLE = False


@dataclass
class TranscriptResult:
    text: str
    language: str
    confidence: float
    duration_s: float
    latency_ms: float
    backend: str = "none"


def _pcm_to_wav_bytes(audio: np.ndarray, sample_rate: int) -> bytes:
    """Convert float32 numpy array → in-memory WAV bytes."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        pcm16 = (audio * 32767).astype(np.int16)
        wf.writeframes(pcm16.tobytes())
    return buf.getvalue()


class Transcriber:
    """
    Async STT with automatic backend fallback.
    Priority: OpenAI API → Google Speech → faster-whisper
    """

    def __init__(self) -> None:
        self._local_model = None
        self._loading = False
        self._lock = asyncio.Lock()
        self._openai_client: AsyncOpenAI | None = None
        self._sr_recogniser = sr_lib.Recognizer() if _SR_AVAILABLE else None
        self._openai_quota_exceeded = False  # skip OpenAI after first 429

    # ── Client helpers ────────────────────────────────────────────────────────
    def _get_openai(self) -> AsyncOpenAI | None:
        if not _OPENAI_AVAILABLE or not settings.openai_api_key:
            return None
        if self._openai_quota_exceeded:
            return None
        if self._openai_client is None:
            self._openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self._openai_client

    # ── Local model ───────────────────────────────────────────────────────────
    async def ensure_local_loaded(self) -> None:
        if not _FW_AVAILABLE:
            return
        async with self._lock:
            if self._local_model is not None or self._loading:
                return
            self._loading = True
        logger.info("Loading local Whisper model '{}'…", settings.stt_model)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._load_local_sync)
        logger.info("Local Whisper model ready.")

    def _load_local_sync(self) -> None:
        self._local_model = WhisperModel(
            settings.stt_model,
            device=settings.stt_device,
            compute_type="int8" if settings.stt_device == "cpu" else "float16",
        )

    # ── Main entry point ──────────────────────────────────────────────────────
    async def transcribe(self, utterance: Utterance) -> TranscriptResult:
        t0 = time.perf_counter()
        duration_s = len(utterance.audio) / utterance.sample_rate

        if duration_s < 0.3:
            return TranscriptResult("", "en", 0.0, duration_s, 0.0, "none")

        # 1. OpenAI Whisper API
        client = self._get_openai()
        if client:
            try:
                result = await self._transcribe_openai(client, utterance)
                result.latency_ms = (time.perf_counter() - t0) * 1000
                logger.info("STT [openai_api]: '{}'  ({:.0f}ms)",
                            result.text[:80], result.latency_ms)
                return result
            except Exception as exc:
                err_str = str(exc)
                if "insufficient_quota" in err_str or "429" in err_str:
                    self._openai_quota_exceeded = True
                    logger.warning("OpenAI Whisper quota exceeded – switching to Google STT permanently.")
                else:
                    logger.warning("OpenAI STT failed ({}), trying next…", exc)

        # 2. Google Speech Recognition (free)
        if _SR_AVAILABLE:
            try:
                result = await self._transcribe_google(utterance)
                result.latency_ms = (time.perf_counter() - t0) * 1000
                if result.text:
                    logger.info("STT [google]: '{}'  ({:.0f}ms)",
                                result.text[:80], result.latency_ms)
                else:
                    logger.debug("STT [google]: no speech recognised in utterance.")
                return result   # return even if empty — avoids unnecessary fallthrough
            except Exception as exc:
                logger.warning("Google STT error ({}), trying local…", exc)

        # 3. faster-whisper (local)
        if _FW_AVAILABLE:
            await self.ensure_local_loaded()
            if self._local_model:
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    None, self._transcribe_local_sync,
                    utterance.audio, utterance.sample_rate,
                )
                result.latency_ms = (time.perf_counter() - t0) * 1000
                logger.info("STT [faster_whisper]: '{}'  ({:.0f}ms)",
                            result.text[:80], result.latency_ms)
                return result

        logger.error("All STT backends failed.")
        return TranscriptResult("", "en", 0.0, duration_s, 0.0, "none")

    # ── Backend: OpenAI Whisper API ───────────────────────────────────────────
    async def _transcribe_openai(
        self, client: AsyncOpenAI, utterance: Utterance
    ) -> TranscriptResult:
        wav_bytes = _pcm_to_wav_bytes(utterance.audio, utterance.sample_rate)
        audio_file = ("audio.wav", io.BytesIO(wav_bytes), "audio/wav")
        lang = settings.stt_language if settings.stt_language != "auto" else None
        response = await client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,  # type: ignore[arg-type]
            language=lang,
            response_format="verbose_json",
        )
        return TranscriptResult(
            text=(response.text or "").strip(),
            language=getattr(response, "language", "en") or "en",
            confidence=0.95,
            duration_s=len(utterance.audio) / utterance.sample_rate,
            latency_ms=0.0,
            backend="openai_api",
        )

    # ── Backend: Google Speech Recognition ───────────────────────────────────
    async def _transcribe_google(self, utterance: Utterance) -> TranscriptResult:
        """
        Uses the free Google Web Speech API via the SpeechRecognition library.
        No API key required.
        """
        # Normalise audio to 70% of full scale so loud mics don't clip
        audio = utterance.audio.copy()
        peak = float(np.max(np.abs(audio)))
        if peak > 0.01:
            audio = audio / peak * 0.7

        wav_bytes = _pcm_to_wav_bytes(audio, utterance.sample_rate)
        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(None, self._google_sync, wav_bytes)
        return TranscriptResult(
            text=text,
            language=settings.stt_language,
            confidence=0.85,
            duration_s=len(utterance.audio) / utterance.sample_rate,
            latency_ms=0.0,
            backend="google",
        )

    def _google_sync(self, wav_bytes: bytes) -> str:
        import speech_recognition as sr  # type: ignore
        recogniser = sr.Recognizer()
        # Normalise audio level before sending
        audio_data = sr.AudioData(wav_bytes, self._sr_sample_rate(), 2)
        try:
            return recogniser.recognize_google(audio_data, language="en-US")
        except sr.UnknownValueError:
            return ""
        except sr.RequestError as exc:
            raise RuntimeError(f"Google STT request error: {exc}") from exc

    def _sr_sample_rate(self) -> int:
        return settings.stt_sample_rate

    # ── Backend: faster-whisper ───────────────────────────────────────────────
    def _transcribe_local_sync(
        self, audio: np.ndarray, sample_rate: int
    ) -> TranscriptResult:
        segments, info = self._local_model.transcribe(
            audio,
            language=settings.stt_language if settings.stt_language != "auto" else None,
            beam_size=5, vad_filter=False, word_timestamps=False,
        )
        text_parts: list[str] = []
        avg_conf = 0.0
        count = 0
        for seg in segments:
            text_parts.append(seg.text.strip())
            avg_conf += getattr(seg, "avg_logprob", 0.0)
            count += 1
        text = " ".join(text_parts).strip()
        return TranscriptResult(
            text=text,
            language=info.language,
            confidence=float(np.exp(avg_conf / max(count, 1))),
            duration_s=len(audio) / sample_rate,
            latency_ms=0.0,
            backend="faster_whisper",
        )

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    async def start(self) -> None:
        bus.subscribe(EventType.SPEECH_END, self._on_speech_end)
        backends = []
        if self._get_openai():
            backends.append("OpenAI Whisper API")
        if _SR_AVAILABLE:
            backends.append("Google Speech (free)")
        if _FW_AVAILABLE:
            backends.append("faster-whisper (local)")
        if not backends:
            backends = ["NONE – check logs"]
        logger.info("Transcriber started — backends: {}", " → ".join(backends))

    async def stop(self) -> None:
        bus.unsubscribe(EventType.SPEECH_END, self._on_speech_end)

    async def _on_speech_end(self, event: Event) -> None:
        utterance: Utterance = event.data
        result = await self.transcribe(utterance)
        if result.text.strip():
            await bus.publish(
                Event(type=EventType.TRANSCRIPT_READY, data=result, source="stt")
            )


# Module singleton
transcriber: Transcriber = Transcriber()
