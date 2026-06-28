"""
lia – Main entry point.
Bootstraps all services in dependency order, then runs the conversation loop.
GUI runs on the main thread; asyncio runs inside the same thread via Qt pump.
"""
from __future__ import annotations

import asyncio
import signal
import sys
import threading
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
    logger.info("Lia is shutting down…")
    await bus.publish(Event(type=EventType.SHUTDOWN, source="main"))

    try:
        from assistant.ai.conversation import conversation
        from assistant.tts.speaker import speaker
        from assistant.stt.transcriber import transcriber
        from assistant.wakeword.detector import wake_detector
        from assistant.audio.microphone import microphone
        from assistant.memory.store import memory

        await conversation.stop()
        await speaker.stop()
        await transcriber.stop()
        await wake_detector.stop()
        await microphone.stop()
        await memory.close_session(summary="Session ended.")
    except Exception:
        logger.exception("Error during pipeline shutdown.")

    await plugin_manager.teardown_all()
    await db.close()

    tasks = [t for t in asyncio.all_tasks(loop) if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    loop.stop()


async def _startup() -> None:
    """Initialise every subsystem in dependency order."""

    # 1. Database
    await db.init()

    # 2. System health monitor
    await start_health_monitor()

    # 3. Plugins
    await plugin_manager.setup_all()

    # 4. Memory store
    from assistant.memory.store import memory
    await memory.init()
    await memory.new_session()

    # 5. Audio pipeline
    from assistant.audio.microphone import microphone
    from assistant.audio.vad import vad
    from assistant.wakeword.detector import wake_detector
    from assistant.stt.transcriber import transcriber
    from assistant.tts.speaker import speaker
    from assistant.ai.conversation import conversation

    await vad.load()
    await wake_detector.load()
    await speaker.start()
    await transcriber.start()

    # 6. VAD pump (feeds mic → VAD)
    async def _vad_pump() -> None:
        async for frame in microphone.stream():
            await vad.process_frame(frame)

    asyncio.create_task(_vad_pump(), name="vad_pump")

    # 7. Wake detector + conversation loop
    await wake_detector.start()
    await conversation.start()

    # 8. Confirmation handler (dangerous actions)
    async def _on_confirm(event: Event) -> None:
        info = event.data or {}
        intent = info.get("intent", "action")
        from assistant.tts.speaker import speaker as sp
        await sp.say(f"Are you sure you want to {intent.replace('_', ' ')}? Say yes or no.")

    bus.subscribe(EventType.CONFIRMATION_REQUIRED, _on_confirm)

    logger.info(
        "✅ Lia v0.3.0 ready — say '{}' to wake me up, {}!",
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
    logger.info("Starting Lia…")

    # ── Decide whether to run with GUI ────────────────────────────────────────
    try:
        from PySide6.QtWidgets import QApplication  # type: ignore
        _qt_available = True
    except ImportError:
        _qt_available = False

    if _qt_available:
        _run_with_gui()
    else:
        logger.info("PySide6 not found – running headless.")
        _run_headless()

    sys.exit(0)


def _run_headless() -> None:
    """Run purely in asyncio – no GUI."""
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")


def _run_with_gui() -> None:
    """
    Run asyncio loop and Qt event loop together on the main thread.
    Qt's timer pumps asyncio every 15 ms.
    """
    import asyncio
    from assistant.gui.app import run_gui

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Start asyncio startup in background before Qt takes over
    async def _boot():
        await _startup()

    loop.run_until_complete(_boot())

    # Qt takes the main thread; it pumps asyncio via a QTimer inside run_gui
    try:
        run_gui(loop)
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(_shutdown(loop))
        loop.close()


if __name__ == "__main__":
    main()
