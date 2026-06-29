"""
Keyboard input and clipboard automation.
"""
from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

try:
    import pyautogui  # type: ignore
    import pyperclip  # type: ignore  (installed with pyautogui)
    _PAG_AVAILABLE = True
except (ImportError, OSError, Exception):
    pyautogui = None  # type: ignore
    pyperclip = None  # type: ignore
    _PAG_AVAILABLE = False

try:
    from pynput.keyboard import Controller as KbController, Key  # type: ignore
    _PYNPUT_AVAILABLE = True
    _kb = KbController()
except (ImportError, OSError, Exception):
    KbController = None  # type: ignore
    Key = None  # type: ignore
    _PYNPUT_AVAILABLE = False
    _kb = None


async def type_text(text: str, interval: float = 0.03, **_: Any) -> str:
    if not _PAG_AVAILABLE:
        return "pyautogui not installed."
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, lambda: pyautogui.typewrite(text, interval=interval))
    return f"Typed: {text[:40]}{'…' if len(text) > 40 else ''}"


async def press_key(key: str, **_: Any) -> str:
    if not _PAG_AVAILABLE:
        return "pyautogui not installed."
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, lambda: pyautogui.press(key))
    return f"Pressed: {key}"


async def hotkey(*keys: str, **kwargs: Any) -> str:
    combo = kwargs.get("combo", "")
    if combo:
        keys = tuple(k.strip() for k in combo.split("+"))
    if not _PAG_AVAILABLE:
        return "pyautogui not installed."
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, lambda: pyautogui.hotkey(*keys))
    return f"Hotkey: {'+'.join(keys)}"


async def clipboard_get(**_: Any) -> str:
    try:
        import pyperclip  # type: ignore
        content = pyperclip.paste()
        return f"Clipboard: {content[:200]}"
    except Exception as exc:
        return f"Clipboard read failed: {exc}"


async def clipboard_set(text: str, **_: Any) -> str:
    try:
        import pyperclip  # type: ignore
        pyperclip.copy(text)
        return "Copied to clipboard."
    except Exception as exc:
        return f"Clipboard write failed: {exc}"
