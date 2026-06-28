"""
lia – Main entry point.
Bootstraps all services in dependency order, then runs the conversation loop.
"""
from __future__ import annotations

import asyncio
import signal
import sys
from typing import NoReturn

from loguru import logger

from assistant.config import settings
from assistant.config.logging_setup import setup_logging
from assistant.core import bus, EventType, Event
from assistant.database.db import _db_instance as db
from assistant.plugins import plugin_manager
from assistant.system.health import start_health_monitor


async def _shutdown(loop: asyncio.AbstractEventLoop) -> None:
    """Graceful shutdown – notify every module, cancel tasks, close DB."""
    logger.info("lia is shutting down…")

    # Signal all modules to clean up
    await bus.publish(Event(type=EventType.SHUTDOWN, source="main"))

    # Stop audio pipeline
    try:
        from assistant.ai.conversation import conversation
        from assistant.tts.speaker import speaker
        from assistant.stt.transcriber import transcriber
        from assistant.audio.vad import vad  # noqa: F401  (just imported for awareness)
        from assistant.wakeword.detector import wake_detector
        from assistant.audio.microphone import microphone

        await conversation.stop()
        await speaker.stop()
        await transcriber.stop()
        await wake_detector.stop()
        await microphone.stop()
    except Exception:
        logger.exception("Error during audio pipeline shutdown.")

    await plugin_manager.teardown_all()
    await db.close()

    # Cancel lingering tasks
    tasks = [t for t in asyncio.all_tasks(loop) if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    loop.stop()


async def _startup() -> None:
    """Initialise every subsystem in dependency order."""

    # ── 1. Database ───────────────────────────────────────────────────────────
    await db.init()

    # ── 2. System health monitor ──────────────────────────────────────────────
    await start_health_monitor()

    # ── 3. Plugins ────────────────────────────────────────────────────────────
    await plugin_manager.setup_all()

    # ── 4. Audio pipeline ─────────────────────────────────────────────────────
    from assistant.audio.microphone import microphone
    from assistant.audio.vad import vad
    from assistant.wakeword.detector import wake_detector
    from assistant.stt.transcriber import transcriber
    from assistant.tts.speaker import speaker
    from assistant.ai.conversation import conversation

    # Load VAD model (downloads ~2 MB silero model on first run)
    await vad.load()

    # Load wake word detector
    await wake_detector.load()

    # Start TTS speaker
    await speaker.start()

    # Start STT transcriber (pre-warms Whisper model in background)
    await transcriber.start()

    # ── 5. Wire VAD into the microphone stream ────────────────────────────────
    async def _vad_pump() -> None:
        """Background task: feeds mic frames into VAD."""
        async for frame in microphone.stream():
            await vad.process_frame(frame)

    asyncio.create_task(_vad_pump(), name="vad_pump")

    # ── 6. Start wake word detector (needs mic running) ───────────────────────
    await wake_detector.start()

    # ── 7. Start conversation loop ────────────────────────────────────────────
    await conversation.start()

    logger.info(
        "✅ lia v0.2.0 ready — say '{}' to wake me up, {}!",
        settings.wake_words[0],
        settings.user_name,
    )
    await bus.publish(Event(type=EventType.ASSISTANT_IDLE, source="main"))


async def _run() -> None:
    await _startup()

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _signal_handler() -> None:
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except (NotImplementedError, ValueError):
            # Windows CMD doesn't support all signals via add_signal_handler
            pass

    try:
        await stop_event.wait()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        await _shutdown(loop)


def main() -> NoReturn:
    """CLI entry point – registered in pyproject.toml as `lia`."""
    setup_logging()
    logger.info("Starting lia…")
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
    sys.exit(0)


if __name__ == "__main__":
    main()
