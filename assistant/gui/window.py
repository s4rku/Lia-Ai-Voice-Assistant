"""
Main application window.
A compact floating panel with:
  • Animated orb
  • Conversation history (scrollable)
  • Microphone level indicator
  • CPU / RAM badges
  • Settings button
  • Always-on-top toggle
"""
from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from assistant.config import settings
from assistant.core.events import Event, EventType, bus
from assistant.core.types import AssistantState

try:
    from PySide6.QtCore import (  # type: ignore
        Qt, QTimer, Signal, Slot, QThread, QMetaObject, Q_ARG,
    )
    from PySide6.QtGui import QFont, QColor, QPalette, QIcon, QAction
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QTextEdit, QScrollArea, QPushButton, QSystemTrayIcon,
        QMenu, QSizePolicy, QFrame,
    )
    from assistant.gui.orb import OrbWidget
    _QT_AVAILABLE = True
except ImportError:
    _QT_AVAILABLE = False
    logger.warning("PySide6 not installed – GUI disabled.")


# ── Themes ────────────────────────────────────────────────────────────────────
DARK = {
    "bg":       "#1a1a2e",
    "surface":  "#16213e",
    "border":   "#0f3460",
    "text":     "#e0e0e0",
    "dim":      "#8888aa",
    "user_bg":  "#0f3460",
    "ai_bg":    "#1a1a2e",
    "accent":   "#e94560",
}

LIGHT = {
    "bg":       "#f5f5f5",
    "surface":  "#ffffff",
    "border":   "#dde1e7",
    "text":     "#1a1a2e",
    "dim":      "#666688",
    "user_bg":  "#dde1e7",
    "ai_bg":    "#ffffff",
    "accent":   "#0f3460",
}


if _QT_AVAILABLE:
    class LiaWindow(QMainWindow):
        # Thread-safe signals for updating UI from async callbacks
        _sig_state   = Signal(str)
        _sig_message = Signal(str, str)   # role, text
        _sig_stats   = Signal(str)        # stats bar text

        def __init__(self) -> None:
            super().__init__()
            self._theme = DARK if settings.gui_theme == "dark" else LIGHT
            self._init_ui()
            self._connect_events()
            self._start_stats_timer()

        # ── UI construction ───────────────────────────────────────────────────
        def _init_ui(self) -> None:
            self.setWindowTitle(f"{settings.assistant_name}")
            self.setMinimumSize(320, 480)
            self.resize(360, 560)
            self.setWindowFlags(
                Qt.WindowStaysOnTopHint if settings.gui_always_on_top else Qt.Window
                | Qt.FramelessWindowHint
            )
            self.setAttribute(Qt.WA_TranslucentBackground)
            self._apply_theme()

            central = QWidget()
            self.setCentralWidget(central)
            root = QVBoxLayout(central)
            root.setContentsMargins(12, 12, 12, 12)
            root.setSpacing(8)

            # Title bar
            title_row = QHBoxLayout()
            lbl_name = QLabel(settings.assistant_name.upper())
            lbl_name.setStyleSheet(
                f"color:{self._theme['accent']}; font-size:14px; font-weight:bold; letter-spacing:2px;"
            )
            title_row.addWidget(lbl_name)
            title_row.addStretch()

            btn_pin = QPushButton("📌")
            btn_pin.setFixedSize(28, 28)
            btn_pin.setCheckable(True)
            btn_pin.setChecked(settings.gui_always_on_top)
            btn_pin.setToolTip("Always on top")
            btn_pin.clicked.connect(self._toggle_pin)
            btn_pin.setStyleSheet("QPushButton{border:none;background:transparent;font-size:14px;}")
            title_row.addWidget(btn_pin)

            btn_theme = QPushButton("🌙")
            btn_theme.setFixedSize(28, 28)
            btn_theme.setToolTip("Toggle theme")
            btn_theme.setStyleSheet("QPushButton{border:none;background:transparent;font-size:14px;}")
            btn_theme.clicked.connect(self._toggle_theme)
            title_row.addWidget(btn_theme)

            btn_close = QPushButton("✕")
            btn_close.setFixedSize(28, 28)
            btn_close.setStyleSheet(
                f"QPushButton{{border:none;background:transparent;color:{self._theme['dim']};font-size:14px;}}"
                f"QPushButton:hover{{color:{self._theme['accent']};}}"
            )
            btn_close.clicked.connect(self.hide)
            title_row.addWidget(btn_close)

            root.addLayout(title_row)

            # Orb
            orb_row = QHBoxLayout()
            orb_row.addStretch()
            self._orb = OrbWidget()
            orb_row.addWidget(self._orb)
            orb_row.addStretch()
            root.addLayout(orb_row)

            # State label
            self._lbl_state = QLabel("Idle — say hey lia")
            self._lbl_state.setAlignment(Qt.AlignCenter)
            self._lbl_state.setStyleSheet(f"color:{self._theme['dim']};font-size:11px;")
            root.addWidget(self._lbl_state)

            # Divider
            root.addWidget(self._divider())

            # Conversation history
            self._chat_area = QTextEdit()
            self._chat_area.setReadOnly(True)
            self._chat_area.setFrameShape(QFrame.NoFrame)
            self._chat_area.setStyleSheet(
                f"background:{self._theme['surface']}; color:{self._theme['text']};"
                f"border-radius:8px; font-size:13px; padding:8px;"
            )
            self._chat_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            root.addWidget(self._chat_area, stretch=1)

            # Stats bar
            self._lbl_stats = QLabel("CPU — | RAM —")
            self._lbl_stats.setStyleSheet(f"color:{self._theme['dim']};font-size:10px;")
            self._lbl_stats.setAlignment(Qt.AlignCenter)
            root.addWidget(self._lbl_stats)

            self._sig_state.connect(self._on_state_changed)
            self._sig_message.connect(self._on_message)
            self._sig_stats.connect(self._lbl_stats.setText)

        def _divider(self) -> QFrame:
            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setStyleSheet(f"color:{self._theme['border']};")
            return line

        def _apply_theme(self) -> None:
            t = self._theme
            self.setStyleSheet(
                f"QMainWindow,QWidget{{background:{t['bg']};border-radius:12px;}}"
            )

        # ── Event wiring ──────────────────────────────────────────────────────
        def _connect_events(self) -> None:
            bus.subscribe(EventType.ASSISTANT_IDLE,      self._ev_idle)
            bus.subscribe(EventType.ASSISTANT_LISTENING, self._ev_listening)
            bus.subscribe(EventType.ASSISTANT_THINKING,  self._ev_thinking)
            bus.subscribe(EventType.ASSISTANT_SPEAKING,  self._ev_speaking)
            bus.subscribe(EventType.TRANSCRIPT_READY,    self._ev_transcript)
            bus.subscribe(EventType.TTS_START,           self._ev_tts_start)

        async def _ev_idle(self, _: Event) -> None:
            self._sig_state.emit("idle")

        async def _ev_listening(self, _: Event) -> None:
            self._sig_state.emit("listening")

        async def _ev_thinking(self, _: Event) -> None:
            self._sig_state.emit("thinking")

        async def _ev_speaking(self, _: Event) -> None:
            self._sig_state.emit("speaking")

        async def _ev_transcript(self, event: Event) -> None:
            self._sig_message.emit("user", event.data.text)

        async def _ev_tts_start(self, event: Event) -> None:
            self._sig_message.emit("assistant", str(event.data or ""))

        # ── Slots ─────────────────────────────────────────────────────────────
        @Slot(str)
        def _on_state_changed(self, state: str) -> None:
            self._orb.set_state(state)
            labels = {
                "idle":      f"Idle — say '{settings.wake_words[0]}'",
                "listening": "Listening…",
                "thinking":  "Thinking…",
                "speaking":  "Speaking…",
                "error":     "Something went wrong.",
            }
            self._lbl_state.setText(labels.get(state, state))

        @Slot(str, str)
        def _on_message(self, role: str, text: str) -> None:
            if not text.strip():
                return
            t = self._theme
            if role == "user":
                prefix = f"<b style='color:{t[\"accent\"]}'>{settings.user_name}:</b> "
            else:
                prefix = f"<b style='color:#7ec8e3'>{settings.assistant_name}:</b> "
            self._chat_area.append(prefix + text.replace("\n", "<br>"))
            # Auto-scroll to bottom
            sb = self._chat_area.verticalScrollBar()
            sb.setValue(sb.maximum())

        def _toggle_pin(self, checked: bool) -> None:
            flags = self.windowFlags()
            if checked:
                self.setWindowFlags(flags | Qt.WindowStaysOnTopHint)
            else:
                self.setWindowFlags(flags & ~Qt.WindowStaysOnTopHint)
            self.show()

        def _toggle_theme(self) -> None:
            self._theme = LIGHT if self._theme is DARK else DARK
            self._apply_theme()
            self._chat_area.setStyleSheet(
                f"background:{self._theme['surface']}; color:{self._theme['text']};"
                f"border-radius:8px; font-size:13px; padding:8px;"
            )

        # ── Stats timer ───────────────────────────────────────────────────────
        def _start_stats_timer(self) -> None:
            self._stats_timer = QTimer(self)
            self._stats_timer.timeout.connect(self._refresh_stats)
            self._stats_timer.start(3000)

        def _refresh_stats(self) -> None:
            try:
                from assistant.system.health import get_system_health
                h = get_system_health()
                text = f"CPU {h.cpu_percent:.0f}%  |  RAM {h.ram_used_mb:.0f}/{h.ram_total_mb:.0f} MB"
                if h.battery_percent is not None:
                    text += f"  |  🔋{h.battery_percent:.0f}%"
                self._sig_stats.emit(text)
            except Exception:
                pass

        # ── Drag to move (frameless window) ───────────────────────────────────
        def mousePressEvent(self, event: Any) -> None:
            if event.button() == Qt.LeftButton:
                self._drag_pos = event.globalPosition().toPoint()

        def mouseMoveEvent(self, event: Any) -> None:
            if event.buttons() == Qt.LeftButton and hasattr(self, "_drag_pos"):
                delta = event.globalPosition().toPoint() - self._drag_pos
                self.move(self.pos() + delta)
                self._drag_pos = event.globalPosition().toPoint()

else:
    class LiaWindow:  # type: ignore[no-redef]
        def __init__(self): pass
        def show(self): pass
        def hide(self): pass
