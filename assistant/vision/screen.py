"""
Screen vision – screenshot capture, OCR, UI element finding, and
clicking based on visual targets.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from loguru import logger

from assistant.config import settings

try:
    import pyautogui  # type: ignore
    _PAG_AVAILABLE = True
except (ImportError, OSError, Exception):
    pyautogui = None  # type: ignore
    _PAG_AVAILABLE = False

try:
    from PIL import Image  # type: ignore
    import pytesseract  # type: ignore
    pytesseract.pytesseract.tesseract_cmd = settings.tesseract_path
    _OCR_AVAILABLE = True
except (ImportError, OSError, Exception):
    Image = None  # type: ignore
    pytesseract = None  # type: ignore
    _OCR_AVAILABLE = False

try:
    import cv2  # type: ignore
    _CV2_AVAILABLE = True
except (ImportError, OSError, Exception):
    cv2 = None  # type: ignore
    _CV2_AVAILABLE = False

try:
    from openai import AsyncOpenAI  # type: ignore
    _OPENAI_AVAILABLE = True
except (ImportError, OSError, Exception):
    AsyncOpenAI = None  # type: ignore
    _OPENAI_AVAILABLE = False


class ScreenVision:
    """
    Provides computer vision capabilities:
    • Capture screenshots (full or region)
    • OCR – extract all text from screen
    • Find UI elements by text or image template
    • Click on found elements
    • Describe screen using GPT-4o Vision
    """

    def __init__(self) -> None:
        self._last_screenshot: Any = None  # PIL Image

    # ── Screenshot ────────────────────────────────────────────────────────────
    async def capture(
        self,
        region: tuple[int, int, int, int] | None = None,
        save: bool = False,
    ) -> Any:
        """Return a PIL Image of the screen (or region)."""
        if not _PAG_AVAILABLE:
            logger.warning("pyautogui not available – cannot capture screen.")
            return None
        loop = asyncio.get_running_loop()
        img = await loop.run_in_executor(None, lambda: pyautogui.screenshot(region=region))
        self._last_screenshot = img
        if save:
            await self._save_screenshot(img)
        return img

    async def _save_screenshot(self, img: Any) -> Path:
        settings.screenshot_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = settings.screenshot_dir / f"vision_{ts}.png"
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: img.save(str(path)))
        return path

    # ── OCR ───────────────────────────────────────────────────────────────────
    async def read_screen_text(
        self,
        region: tuple[int, int, int, int] | None = None,
    ) -> str:
        """Return all text visible on screen using Tesseract OCR."""
        if not _OCR_AVAILABLE:
            return "OCR not available (pytesseract/PIL not installed)."
        img = await self.capture(region)
        if img is None:
            return "Screen capture failed."
        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(None, lambda: pytesseract.image_to_string(img))
        return text.strip()

    # ── Find text on screen ───────────────────────────────────────────────────
    async def find_text_location(self, text: str) -> tuple[int, int] | None:
        """
        Return (x, y) centre of first occurrence of text on screen.
        Uses OCR + bounding box data.
        """
        if not _OCR_AVAILABLE:
            return None
        img = await self.capture()
        if img is None:
            return None
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(
            None,
            lambda: pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT),
        )
        target = text.lower()
        for i, word in enumerate(data["text"]):
            if target in word.lower() and int(data["conf"][i]) > 30:
                x = data["left"][i] + data["width"][i] // 2
                y = data["top"][i] + data["height"][i] // 2
                return (x, y)
        return None

    # ── Click by text ─────────────────────────────────────────────────────────
    async def click_text(self, text: str, **_: Any) -> str:
        """Find text on screen and click it."""
        pos = await self.find_text_location(text)
        if pos is None:
            return f"Could not find '{text}' on screen."
        if not _PAG_AVAILABLE:
            return f"Found '{text}' at {pos} but pyautogui not available."
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: pyautogui.click(*pos))
        return f"Clicked '{text}' at {pos}."

    # ── Template matching ─────────────────────────────────────────────────────
    async def find_image(self, template_path: str, confidence: float = 0.8) -> tuple[int, int] | None:
        """Find a template image on screen and return its centre (x, y)."""
        if not _PAG_AVAILABLE:
            return None
        loop = asyncio.get_running_loop()
        try:
            pos = await loop.run_in_executor(
                None,
                lambda: pyautogui.locateCenterOnScreen(
                    template_path, confidence=confidence
                ),
            )
            return pos
        except Exception:
            return None

    # ── GPT-4o Vision description ─────────────────────────────────────────────
    async def describe_screen(self, question: str = "What is on the screen?") -> str:
        """Use GPT-4o Vision to describe the current screen state."""
        if not _OPENAI_AVAILABLE or not settings.openai_api_key:
            # Fall back to OCR summary
            text = await self.read_screen_text()
            return f"Screen text (OCR): {text[:500]}" if text else "Vision not available."

        img = await self.capture(save=True)
        if img is None:
            return "Could not capture screen."

        import base64
        import io
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        try:
            resp = await client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": question},
                        {"type": "image_url", "image_url": {
                            "url": f"data:image/png;base64,{b64}",
                            "detail": "low",
                        }},
                    ],
                }],
                max_tokens=300,
            )
            return resp.choices[0].message.content or "No description."
        except Exception as exc:
            return f"Vision API error: {exc}"


# Module singleton
vision: ScreenVision = ScreenVision()
