"""StemDeckStage - Custom Visual Deck for Slot 2 (Stem Separator).

Renders 4-track channel monitors for separated stems:
- Vocals
- Drums
- Bass
- Other
Each with mini LED meter, activity indicator, and track level badge.
"""

from __future__ import annotations

from typing import Optional

from src.ui.qt import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPen,
    QPointF,
    QRectF,
    QSizePolicy,
    Qt,
    QWidget,
)
from src.ui.theme.tokens import TOKENS


class StemDeckStage(QWidget):
    """4-track visual stem isolation monitor."""

    STEMS = [
        ("VOCALS", "#EC4899"),
        ("DRUMS", "#3B82F6"),
        ("BASS", "#10B981"),
        ("OTHER", "#F59E0B"),
    ]

    def __init__(
        self,
        accent_color: str = "#EC4899",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._accent_color = accent_color
        self.setFixedHeight(170)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        w = float(self.width())
        h = float(self.height())

        # 1. Recessed Chassis Background
        bg_rect = QRectF(0, 0, w, h)
        p.setBrush(QColor(14, 10, 6))
        p.setPen(QPen(QColor(255, 255, 255, 15), 1.0))
        p.drawRoundedRect(bg_rect, 6, 6)

        # 2. 4 Stem Strips
        strip_w = (w - 32.0) / 4.0
        for i, (name, col_hex) in enumerate(self.STEMS):
            sx = 16.0 + i * strip_w
            sy = 10.0
            sh = h - 20.0
            strip_rect = QRectF(sx + 4, sy, strip_w - 8, sh)

            # Recessed channel frame
            p.setBrush(QColor(20, 14, 10))
            p.setPen(QPen(QColor(255, 255, 255, 12), 1.0))
            p.drawRoundedRect(strip_rect, 4, 4)

            # Strip Header
            p.setFont(QFont("Arial", 8, QFont.Weight.Bold))
            p.setPen(QPen(QColor(col_hex)))
            p.drawText(QRectF(sx + 4, sy + 8, strip_w - 8, 14), Qt.AlignmentFlag.AlignCenter, name)

            # Mini LED Ladder
            led_x = strip_rect.center().x() - 16.0
            led_y = sy + 32.0
            num_leds = 8
            for led_idx in range(num_leds):
                ly = led_y + (num_leds - 1 - led_idx) * 8.0
                led_rect = QRectF(led_x, ly, 32.0, 5.0)
                if led_idx < 4:
                    p.setBrush(QColor(16, 185, 129, 140))  # Green
                elif led_idx < 6:
                    p.setBrush(QColor(245, 158, 11, 140))  # Amber
                else:
                    p.setBrush(QColor(239, 68, 68, 140))  # Red
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRoundedRect(led_rect, 1.0, 1.0)

            # Status Tag
            p.setFont(QFont("Menlo, Courier, monospace", 7, QFont.Weight.Bold))
            p.setPen(QPen(QColor(TOKENS.colors.text.muted)))
            p.drawText(
                QRectF(sx + 4, sy + sh - 22, strip_w - 8, 14),
                Qt.AlignmentFlag.AlignCenter,
                "ISOLATION READY",
            )

        p.end()
