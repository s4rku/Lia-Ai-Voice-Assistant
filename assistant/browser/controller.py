"""
Browser automation using Playwright (async).
Supports Chrome, Edge, Firefox.
All public methods are async and safe to call from the conversation loop.
"""
from __future__ import annotations

import asyncio
from typing import Any, Literal

from loguru import logger

try:
    from playwright.async_api import (  # type: ignore
        async_playwright, Browser, BrowserContext, Page, Playwright,
    )
    _PW_AVAILABLE = True
except (ImportError, OSError, Exception):
    _PW_AVAILABLE = False
    logger.warning("playwright not installed – browser automation disabled.")


BrowserType = Literal["chromium", "firefox", "webkit"]


class BrowserController:
    """
    Manages a single Playwright browser instance.
    Lazy-initialises on first use to keep startup fast.
    """

    def __init__(self) -> None:
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._browser_type: BrowserType = "chromium"

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    async def _ensure_ready(self, browser_type: BrowserType = "chromium") -> bool:
        if not _PW_AVAILABLE:
            logger.warning("Playwright not available.")
            return False
        if self._page and not self._page.is_closed():
            return True

        self._browser_type = browser_type
        self._pw = await async_playwright().start()

        launcher = getattr(self._pw, browser_type)
        self._browser = await launcher.launch(headless=False)
        self._context = await self._browser.new_context()
        self._page = await self._context.new_page()
        logger.info("Browser started: {}", browser_type)
        return True

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()
        self._page = None
        self._browser = None
        self._pw = None
        logger.info("Browser closed.")

    # ── Navigation ────────────────────────────────────────────────────────────
    async def open_url(self, url: str, browser: BrowserType = "chromium", **_: Any) -> str:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        if not await self._ensure_ready(browser):
            return "Browser not available."
        await self._page.goto(url, wait_until="domcontentloaded", timeout=15000)
        title = await self._page.title()
        return f"Opened: {title} ({url})"

    async def search_google(self, query: str, **_: Any) -> str:
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        return await self.open_url(url)

    async def go_back(self, **_: Any) -> str:
        if not self._page:
            return "No browser open."
        await self._page.go_back()
        return "Navigated back."

    async def go_forward(self, **_: Any) -> str:
        if not self._page:
            return "No browser open."
        await self._page.go_forward()
        return "Navigated forward."

    async def reload(self, **_: Any) -> str:
        if not self._page:
            return "No browser open."
        await self._page.reload()
        return "Page reloaded."

    # ── Tabs ──────────────────────────────────────────────────────────────────
    async def new_tab(self, url: str = "", **_: Any) -> str:
        if not await self._ensure_ready():
            return "Browser not available."
        self._page = await self._context.new_page()
        if url:
            return await self.open_url(url)
        return "New tab opened."

    async def close_tab(self, **_: Any) -> str:
        if self._page:
            await self._page.close()
            pages = self._context.pages if self._context else []
            self._page = pages[-1] if pages else None
            return "Tab closed."
        return "No tab to close."

    async def list_tabs(self, **_: Any) -> str:
        if not self._context:
            return "No browser open."
        titles = []
        for p in self._context.pages:
            try:
                titles.append(await p.title())
            except Exception:
                titles.append("(unknown)")
        return "Tabs: " + ", ".join(titles) if titles else "No open tabs."

    # ── Page interaction ──────────────────────────────────────────────────────
    async def click_element(self, selector: str = "", text: str = "", **_: Any) -> str:
        if not self._page:
            return "No browser open."
        try:
            if text:
                await self._page.get_by_text(text, exact=False).first.click(timeout=5000)
                return f"Clicked element with text: {text}"
            if selector:
                await self._page.click(selector, timeout=5000)
                return f"Clicked: {selector}"
            return "Provide selector or text."
        except Exception as exc:
            return f"Click failed: {exc}"

    async def fill_input(self, selector: str, value: str, **_: Any) -> str:
        if not self._page:
            return "No browser open."
        try:
            await self._page.fill(selector, value, timeout=5000)
            return f"Filled '{selector}' with value."
        except Exception as exc:
            return f"Fill failed: {exc}"

    async def get_page_text(self, **_: Any) -> str:
        if not self._page:
            return "No browser open."
        text = await self._page.inner_text("body")
        return text[:2000]

    async def get_page_title(self, **_: Any) -> str:
        if not self._page:
            return "No browser open."
        return await self._page.title()

    # ── Media ─────────────────────────────────────────────────────────────────
    async def play_youtube(self, query: str, **_: Any) -> str:
        url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        if not await self._ensure_ready():
            return "Browser not available."
        await self._page.goto(url, wait_until="domcontentloaded", timeout=15000)
        # Click first video result
        try:
            await self._page.click("ytd-video-renderer a#thumbnail", timeout=5000)
            return f"Playing YouTube: {query}"
        except Exception:
            return f"Opened YouTube search for: {query}"

    async def youtube_pause(self, **_: Any) -> str:
        if not self._page:
            return "No browser open."
        await self._page.keyboard.press("k")
        return "YouTube paused/resumed."

    async def youtube_volume(self, direction: str = "up", **_: Any) -> str:
        if not self._page:
            return "No browser open."
        key = "ArrowUp" if direction == "up" else "ArrowDown"
        await self._page.keyboard.press(key)
        return f"YouTube volume {direction}."

    # ── Screenshot ────────────────────────────────────────────────────────────
    async def screenshot(self, filename: str | None = None, **_: Any) -> str:
        if not self._page:
            return "No browser open."
        from assistant.config import settings
        from datetime import datetime
        settings.screenshot_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = settings.screenshot_dir / (filename or f"browser_{ts}.png")
        await self._page.screenshot(path=str(path), full_page=False)
        return f"Browser screenshot saved: {path}"

    # ── Gmail shortcut ────────────────────────────────────────────────────────
    async def open_gmail(self, **_: Any) -> str:
        return await self.open_url("https://mail.google.com")

    async def open_discord(self, **_: Any) -> str:
        return await self.open_url("https://discord.com/app")


# Module singleton
browser: BrowserController = BrowserController()
