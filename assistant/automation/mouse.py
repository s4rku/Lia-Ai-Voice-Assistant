"""
Mouse control and screenshot capture.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger
from assistant.config import settings

try:
    import pyautogui  # type: ignore
    _PAG_AVAILABLE = True
except ImportError:
    pyautogui = None  # type: ignore
    _PAG_AVAILABLE = False

try:
    from PIL import Image  # type: ignore
    _PIL_AVAILABLE = True
except ImportError:
    Image = None  # type: ignore
    _PIL_AVAILABLE = False


async def click(x: int | None = None, y: int | None = None, **_: Any) -> str:
    if not _PAG_AVAILABLE:
        return "pyautogui not installed."
    loop = asyncio.get_running_loop()
    if x is not None and y is not None:
        await loop.run_in_executor(None, lambda: pyautogui.click(x, y))
        return f"Clicked at ({x}, {y})."
    else:
        await loop.run_in_executor(None, pyautogui.click)
        return "Clicked at current position."


async def double_click(x: int | None = None, y: int | None = None, **_: Any) -> str:
    if not _PAG_AVAILABLE:
        return "pyautogui not installed."
    loop = asyncio.get_running_loop()
    pos = (x, y) if x is not None and y is not None else pyautogui.position()
    await loop.run_in_executor(None, lambda: pyautogui.doubleClick(*pos))
    return f"Double-clicked at {pos}."


async def right_click(x: int | None = None, y: int | None = None, **_: Any) -> str:
    if not _PAG_AVAILABLE:
        return "pyautogui not installed."
    loop = asyncio.get_running_loop()
    pos = (x, y) if x is not None and y is not None else pyautogui.position()
    await loop.run_in_executor(None, lambda: pyautogui.rightClick(*pos))
    return f"Right-clicked at {pos}."


async def move_mouse(x: int, y: int, duration: float = 0.3, **_: Any) -> str:
    if not _PAG_AVAILABLE:
        return "pyautogui not installed."
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, lambda: pyautogui.moveTo(x, y, duration=duration))
    return f"Mouse moved to ({x}, {y})."


async def drag(
    x1: int, y1: int, x2: int, y2: int, duration: float = 0.5, **_: Any
) -> str:
    if not _PAG_AVAILABLE:
        return "pyautogui not installed."
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        lambda: pyautogui.drag(x2 - x1, y2 - y1, duration=duration, button="left"),
    )
    return f"Dragged from ({x1},{y1}) to ({x2},{y2})."


async def scroll(direction: str = "down", clicks: int = 3, **_: Any) -> str:
    if not _PAG_AVAILABLE:
        return "pyautogui not installed."
    amount = -clicks if direction == "down" else clicks
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, lambda: pyautogui.scroll(amount))
    return f"Scrolled {direction} {clicks} clicks."


async def take_screenshot(filename: str | None = None, **_: Any) -> str:
    if not _PAG_AVAILABLE:
        return "pyautogui not installed."
    settings.screenshot_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = settings.screenshot_dir / (filename or f"screenshot_{ts}.png")
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, lambda: pyautogui.screenshot(str(path)))
    return f"Screenshot saved: {path}"
