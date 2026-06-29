"""
Animated orb widget – the visual centrepiece of Lia's GUI.
States: idle (slow pulse) → listening (fast blue pulse) →
        thinking (spinning gradient) → speaking (wave ripple)
"""
from __future__ import annotations

import math

from loguru import logger

try:
    from PySide6.QtCore import (  # type: ignore
        Qt, QTimer, QPropertyAnimation, QEasingCurve,
        Property, QObject, Signal, QPointF,
    )
    from PySide6.QtGui import (
        QColor, QPainter, QRadialGradient, QPen, QBrush, QConicalGradient,
    )
    from PySide6.QtWidgets import QWidget
    _QT_AVAILABLE = True
except (ImportError, OSError, Exception):
    _QT_AVAILABLE = False


if _QT_AVAILABLE:
    class OrbWidget(QWidget):
        """
        A circular, animated orb that reflects assistant state.
        Uses a QTimer to repaint every 30 ms (≈33 fps).
        """

        # Colours per state
        _COLOURS = {
            "idle":      (60,  120, 220),
            "listening": (20,  200, 120),
            "thinking":  (200, 140,  20),
            "speaking":  (220,  60, 140),
            "error":     (220,  40,  40),
        }

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.setFixedSize(120, 120)
            self.setAttribute(Qt.WA_TranslucentBackground)
            self._state = "idle"
            self._phase = 0.0          # animation phase 0..2π
            self._spin  = 0.0          # spin angle for thinking state
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._tick)
            self._timer.start(30)

        def set_state(self, state: str) -> None:
            self._state = state
            self.update()

        def _tick(self) -> None:
            speeds = {
                "idle": 0.04, "listening": 0.12,
                "thinking": 0.10, "speaking": 0.16, "error": 0.08,
            }
            self._phase = (self._phase + speeds.get(self._state, 0.05)) % (2 * math.pi)
            self._spin  = (self._spin + 3.0) % 360.0
            self.update()

        def paintEvent(self, _event: Any) -> None:  # type: ignore[override]
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)

            w, h = self.width(), self.height()
            cx, cy = w / 2, h / 2
            r = min(w, h) / 2 - 6

            col = self._COLOURS.get(self._state, (80, 80, 200))

            if self._state == "thinking":
                self._draw_spinning(painter, cx, cy, r, col)
            elif self._state == "speaking":
                self._draw_wave(painter, cx, cy, r, col)
            else:
                self._draw_pulse(painter, cx, cy, r, col)

            painter.end()

        def _draw_pulse(self, p: QPainter, cx: float, cy: float, r: float, col: tuple) -> None:
            alpha = int(180 + 70 * math.sin(self._phase))
            inner = QColor(*col, alpha)
            outer = QColor(*col, 0)
            grad = QRadialGradient(cx, cy, r)
            grad.setColorAt(0.0, inner)
            grad.setColorAt(0.6, QColor(*col, int(alpha * 0.4)))
            grad.setColorAt(1.0, outer)
            p.setBrush(QBrush(grad))
            p.setPen(Qt.NoPen)
            p.drawEllipse(int(cx - r), int(cy - r), int(r * 2), int(r * 2))

            # Outer glow ring
            ring_r = r + 4 * abs(math.sin(self._phase))
            pen = QPen(QColor(*col, 60), 2)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(int(cx - ring_r), int(cy - ring_r), int(ring_r * 2), int(ring_r * 2))

        def _draw_spinning(self, p: QPainter, cx: float, cy: float, r: float, col: tuple) -> None:
            grad = QConicalGradient(cx, cy, self._spin)
            grad.setColorAt(0.0, QColor(*col, 255))
            grad.setColorAt(0.5, QColor(*col, 60))
            grad.setColorAt(1.0, QColor(*col, 255))
            p.setBrush(QBrush(grad))
            pen = QPen(QColor(*col, 80), 3)
            p.setPen(pen)
            p.drawEllipse(int(cx - r), int(cy - r), int(r * 2), int(r * 2))

        def _draw_wave(self, p: QPainter, cx: float, cy: float, r: float, col: tuple) -> None:
            # Draw 3 concentric ripple rings
            for i in range(3):
                offset = (self._phase + i * 2.0) % (2 * math.pi)
                rr = r * (0.4 + 0.6 * (offset / (2 * math.pi)))
                alpha = int(200 * (1 - offset / (2 * math.pi)))
                pen = QPen(QColor(*col, alpha), 2)
                p.setPen(pen)
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(int(cx - rr), int(cy - rr), int(rr * 2), int(rr * 2))

            # Centre dot
            p.setBrush(QBrush(QColor(*col, 220)))
            p.setPen(Qt.NoPen)
            p.drawEllipse(int(cx - 12), int(cy - 12), 24, 24)

else:
    # Stub so import doesn't fail when Qt is absent
    class OrbWidget:  # type: ignore[no-redef]
        def __init__(self, *a, **kw): pass
        def set_state(self, s): pass
