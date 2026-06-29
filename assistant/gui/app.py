"""
GUI application entry point.
Runs the PySide6 event loop in a dedicated thread alongside the asyncio loop.
The two loops communicate via Qt signals / asyncio queues.
"""
from __future__ import annotations

import asyncio
import sys
import threading
from typing import Any

from loguru import logger

from assistant.config import settings

try:
    from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu  # type: ignore
    from PySide6.QtGui import QIcon, QPixmap, QColor, QPainter, QAction  # type: ignore
    from PySide6.QtCore import Qt, QTimer  # type: ignore
    from assistant.gui.window import LiaWindow
    _QT_AVAILABLE = True
except (ImportError, OSError, Exception):
    _QT_AVAILABLE = False
    logger.warning("PySide6 not installed – running headless.")


def _make_tray_icon(app: QApplication) -> QSystemTrayIcon:
    """Create a simple coloured circle as tray icon (no external icon file needed)."""
    px = QPixmap(32, 32)
    px.fill(Qt.transparent)
    painter = QPainter(px)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor("#e94560"))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(2, 2, 28, 28)
    painter.end()
    icon = QIcon(px)

    tray = QSystemTrayIcon(icon, app)
    menu = QMenu()

    show_action = QAction("Show", app)
    quit_action = QAction("Quit", app)

    tray.activated.connect(lambda _: _window_ref[0].show() if _window_ref[0] else None)
    quit_action.triggered.connect(lambda: QApplication.quit())

    menu.addAction(show_action)
    menu.addSeparator()
    menu.addAction(quit_action)
    tray.setContextMenu(menu)
    tray.setToolTip(settings.assistant_name)
    tray.show()
    return tray


_window_ref: list[LiaWindow | None] = [None]


def run_gui(async_loop: asyncio.AbstractEventLoop) -> None:
    """
    Start the Qt application on the MAIN thread.
    Pass the asyncio loop so the window can post signals back safely.
    """
    if not _QT_AVAILABLE:
        logger.info("GUI skipped (PySide6 not installed).")
        return

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(settings.assistant_name)
    app.setQuitOnLastWindowClosed(False)

    window = LiaWindow()
    _window_ref[0] = window

    tray = _make_tray_icon(app)
    show_action = tray.contextMenu().actions()[0]
    show_action.triggered.connect(window.show)

    if not settings.gui_start_minimized:
        window.show()

    # Pump the asyncio loop from Qt's event loop
    _pump_timer = QTimer()
    _pump_timer.setInterval(15)  # 15ms ≈ 66 Hz
    _pump_timer.timeout.connect(lambda: _pump_asyncio(async_loop))
    _pump_timer.start()

    app.exec()


def _pump_asyncio(loop: asyncio.AbstractEventLoop) -> None:
    """Run one iteration of the asyncio event loop from the Qt timer callback."""
    loop.call_soon_threadsafe(lambda: None)
    loop.run_until_complete(asyncio.sleep(0))
