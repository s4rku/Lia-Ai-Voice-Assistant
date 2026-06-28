"""
lia – centralised settings loaded from .env / environment variables.
All defaults are safe for development; override via .env for production.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ─── Project root (two levels up from this file) ────────────────────────────
ROOT_DIR: Path = Path(__file__).resolve().parents[2]
DATA_DIR: Path = ROOT_DIR / "data"
LOG_DIR: Path = ROOT_DIR / "assistant" / "logs"


class Settings(BaseSettings):
    """All runtime configuration for lia."""

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Identity ─────────────────────────────────────────────────────────────
    assistant_name: str = Field(default="lia")
    user_name: str = Field(default="Boss")

    # ── Wake word ─────────────────────────────────────────────────────────────
    wake_words: list[str] = Field(default=["hey lia", "lia", "hello lia"])

    @field_validator("wake_words", mode="before")
    @classmethod
    def parse_wake_words(cls, v: object) -> list[str]:
        if isinstance(v, str):
            return [w.strip().lower() for w in v.split(",") if w.strip()]
        return v  # type: ignore[return-value]

    # ── OpenAI ────────────────────────────────────────────────────────────────
    openai_api_key: str = Field(default="")
    openai_model: str = Field(default="gpt-4o-mini")
    openai_embedding_model: str = Field(default="text-embedding-3-small")

    # ── Anthropic ────────────────────────────────────────────────────────────
    anthropic_api_key: str = Field(default="")

    # ── STT ──────────────────────────────────────────────────────────────────
    stt_model: str = Field(default="base.en")
    stt_device: Literal["cpu", "cuda"] = Field(default="cpu")
    stt_language: str = Field(default="en")
    stt_silence_ms: int = Field(default=700)   # ms of silence → end of utterance
    stt_sample_rate: int = Field(default=16_000)
    stt_chunk_ms: int = Field(default=30)       # chunk size fed to VAD

    # ── TTS ──────────────────────────────────────────────────────────────────
    tts_voice: str = Field(default="en-US-GuyNeural")
    tts_rate: str = Field(default="+10%")
    tts_volume: str = Field(default="+0%")

    # ── Memory ───────────────────────────────────────────────────────────────
    memory_db_path: Path = Field(default=DATA_DIR / "memory" / "lia.db")
    memory_chroma_path: Path = Field(default=DATA_DIR / "memory" / "chroma")
    memory_short_term_limit: int = Field(default=20)   # messages kept in RAM
    memory_long_term_limit: int = Field(default=100)   # retrieved from vector db

    # ── Vision ───────────────────────────────────────────────────────────────
    tesseract_path: str = Field(default=r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    ffmpeg_path: str = Field(default=r"C:\ffmpeg\bin\ffmpeg.exe")
    screenshot_dir: Path = Field(default=DATA_DIR / "screenshots")

    # ── Weather ───────────────────────────────────────────────────────────────
    weather_api_key: str = Field(default="")
    weather_city: str = Field(default="London")

    # ── GUI ──────────────────────────────────────────────────────────────────
    gui_always_on_top: bool = Field(default=True)
    gui_theme: Literal["dark", "light"] = Field(default="dark")
    gui_start_minimized: bool = Field(default=False)

    # ── Logging ──────────────────────────────────────────────────────────────
    log_level: str = Field(default="INFO")
    log_rotation: str = Field(default="10 MB")
    log_retention: str = Field(default="30 days")

    # ── Performance ──────────────────────────────────────────────────────────
    max_memory_mb: int = Field(default=400)
    response_timeout_s: float = Field(default=15.0)


# Singleton – import this everywhere instead of re-instantiating.
settings: Settings = Settings()
