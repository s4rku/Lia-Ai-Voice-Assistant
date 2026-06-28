"""
Automation dispatcher – routes intent strings to the correct handler.
Called by brain.py after extracting action JSON from the AI response.
"""
from __future__ import annotations

import time
import json
from typing import Any

from loguru import logger

from assistant.core.events import Event, EventType, bus
from assistant.database.db import _db_instance as db
from assistant.database.models import CommandHistory

# Safety confirmation required for these intents
_DANGEROUS_INTENTS = {
    "shutdown", "restart", "delete_file", "delete_folder",
    "format_drive", "run_powershell", "run_cmd",
    "empty_recycle_bin", "kill_process",
}

_pending_confirmation: dict[str, Any] | None = None


async def dispatch_action(intent: str, params: dict[str, Any]) -> str:
    """
    Route an intent to its handler. Returns a human-readable result string.
    Dangerous intents pause and wait for CONFIRMATION_ANSWER event.
    """
    global _pending_confirmation

    if intent in _DANGEROUS_INTENTS:
        _pending_confirmation = {"intent": intent, "params": params}
        await bus.publish(Event(
            type=EventType.CONFIRMATION_REQUIRED,
            data={"intent": intent, "params": params},
            source="dispatcher",
        ))
        return f"Awaiting confirmation for: {intent}"

    return await _run_action(intent, params)


async def confirm_action(confirmed: bool) -> str:
    """Called when the user answers yes/no to a dangerous action."""
    global _pending_confirmation
    if _pending_confirmation is None:
        return "Nothing pending."
    if confirmed:
        intent = _pending_confirmation["intent"]
        params = _pending_confirmation["params"]
        _pending_confirmation = None
        return await _run_action(intent, params)
    else:
        _pending_confirmation = None
        return "Cancelled."


async def _run_action(intent: str, params: dict[str, Any]) -> str:
    t0 = time.perf_counter()
    result = "Done."
    success = True

    try:
        from assistant.automation import (  # noqa: PLC0415
            apps, keyboard, mouse, system_ctrl, file_ops,
        )

        from assistant.browser.controller import browser  # noqa: PLC0415
        from assistant.vision.screen import vision       # noqa: PLC0415

        handlers: dict[str, Any] = {
            # Apps
            "open_app":        apps.open_app,
            "close_app":       apps.close_app,
            "kill_process":    apps.kill_process,
            "switch_window":   apps.switch_window,
            "minimize_window": apps.minimize_window,
            "maximize_window": apps.maximize_window,
            "list_windows":    apps.list_windows,
            # Keyboard
            "type_text":       keyboard.type_text,
            "press_key":       keyboard.press_key,
            "hotkey":          keyboard.hotkey,
            "clipboard_get":   keyboard.clipboard_get,
            "clipboard_set":   keyboard.clipboard_set,
            # Mouse
            "click":           mouse.click,
            "double_click":    mouse.double_click,
            "right_click":     mouse.right_click,
            "move_mouse":      mouse.move_mouse,
            "drag":            mouse.drag,
            "scroll":          mouse.scroll,
            "take_screenshot": mouse.take_screenshot,
            # System
            "set_volume":      system_ctrl.set_volume,
            "mute":            system_ctrl.mute,
            "set_brightness":  system_ctrl.set_brightness,
            "shutdown":        system_ctrl.shutdown,
            "restart":         system_ctrl.restart,
            "sleep":           system_ctrl.sleep,
            "lock":            system_ctrl.lock,
            "run_cmd":         system_ctrl.run_cmd,
            "run_powershell":  system_ctrl.run_powershell,
            # Files
            "create_folder":   file_ops.create_folder,
            "delete_file":     file_ops.delete_file,
            "move_file":       file_ops.move_file,
            "copy_file":       file_ops.copy_file,
            "rename_file":     file_ops.rename_file,
            "search_files":    file_ops.search_files,
            "read_file":       file_ops.read_file_content,
            "zip_files":       file_ops.zip_files,
            "extract_archive": file_ops.extract_archive,
            "empty_recycle_bin": file_ops.empty_recycle_bin,
            # Browser
            "open_url":        browser.open_url,
            "search_google":   browser.search_google,
            "new_tab":         browser.new_tab,
            "close_tab":       browser.close_tab,
            "go_back":         browser.go_back,
            "go_forward":      browser.go_forward,
            "play_youtube":    browser.play_youtube,
            "youtube_pause":   browser.youtube_pause,
            "open_gmail":      browser.open_gmail,
            "open_discord":    browser.open_discord,
            "browser_click":   browser.click_element,
            "get_page_text":   browser.get_page_text,
            # Vision
            "click_text":      vision.click_text,
            "read_screen":     vision.read_screen_text,
            "describe_screen": vision.describe_screen,
        }

        handler = handlers.get(intent)
        if handler:
            result = await handler(**params) or "Done."
        else:
            result = f"Unknown intent: {intent}"
            logger.warning("No handler for intent: {}", intent)

    except Exception as exc:
        success = False
        result = f"Error running {intent}: {exc}"
        logger.exception("Automation error for intent '{}'", intent)

    elapsed = (time.perf_counter() - t0) * 1000
    logger.info("Action '{}' → {} ({:.0f}ms)", intent, result[:80], elapsed)

    # Persist to command history (fire-and-forget)
    try:
        async with db.session() as s:
            s.add(CommandHistory(
                command_type=intent,
                description=result[:200],
                parameters=json.dumps(params)[:500],
                success=success,
                execution_ms=elapsed,
            ))
    except Exception:
        pass

    await bus.publish(Event(type=EventType.COMMAND_DONE, data=result, source="dispatcher"))
    return result
