"""AnalysisStage - Custom Visual Deck for Slot 2 (Key & Tempo Detector).

Renders vintage analog meters, Camelot harmonic key dial, and tempo readouts.
"""

from __future__ import annotations

import math
from typing import Optional

from src.ui.qt import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPointF,
    QRadialGradient,
    QRectF,
    QSizePolicy,
    Qt,
    QWidget,
)
from src.ui.theme.tokens import TOKENS


class AnalysisStage(QWidget):
    """Harmonic key wheel and tempo gauge monitor."""

    def __init__(
        self,
        accent_color: str = "#8B5CF6",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._accent_color = accent_color
        self._key_result: str = "A MINOR"
        self._camelot: str = "8A"
        self._bpm_result: float = 124.0
        self._confidence: float = 0.95

        self.setFixedHeight(170)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_results(self, key_str: str, camelot_str: str, bpm: float, confidence: float = 0.95) -> None:
        self._key_result = key_str.upper()
        self._camelot = camelot_str.upper()
        self._bpm_result = float(bpm)
        self._confidence = float(confidence)
        self.update()

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

        mid_x = w / 2.0

        # 2. Left Zone: Harmonic Key Circle
        key_cx = mid_x - 140.0
        key_cy = h / 2.0
        key_r = 50.0

        p.setBrush(QColor(22, 16, 12))
        p.setPen(QPen(QColor(self._accent_color), 1.5))
        p.drawEllipse(QPointF(key_cx, key_cy), key_r, key_r)

        # Inner Camelot Dial
        p.setFont(QFont("Menlo, Courier, monospace", 16, QFont.Weight.Bold))
        p.setPen(QPen(QColor("#FDE68A")))
        p.drawText(QRectF(key_cx - 40, key_cy - 20, 80, 24), Qt.AlignmentFlag.AlignCenter, self._camelot)

        p.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        p.setPen(QPen(QColor(TOKENS.colors.text.muted)))
        p.drawText(QRectF(key_cx - 50, key_cy + 6, 100, 16), Qt.AlignmentFlag.AlignCenter, self._key_result)

        # 3. Right Zone: Tempo BPM Gauge
        bpm_cx = mid_x + 140.0
        bpm_cy = h / 2.0
        bpm_r = 50.0

        p.setBrush(QColor(22, 16, 12))
        p.setPen(QPen(QColor(self._accent_color), 1.5))
        p.drawEllipse(QPointF(bpm_cx, bpm_cy), bpm_r, bpm_r)

        p.setFont(QFont("Menlo, Courier, monospace", 16, QFont.Weight.Bold))
        p.setPen(QPen(QColor("#FDE68A")))
        p.drawText(QRectF(bpm_cx - 40, bpm_cy - 20, 80, 24), Qt.AlignmentFlag.AlignCenter, f"{self._bpm_result:.1f}")

        p.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        p.setPen(QPen(QColor(TOKENS.colors.text.muted)))
        p.drawText(QRectF(bpm_cx - 50, bpm_cy + 6, 100, 16), Qt.AlignmentFlag.AlignCenter, "BPM TEMPO")

        # 4. Center Readout Badge
        badge_w = 160.0
        badge_h = 36.0
        badge_rect = QRectF(mid_x - badge_w / 2.0, h / 2.0 - badge_h / 2.0, badge_w, badge_h)
        p.setBrush(QColor(18, 12, 8))
        p.setPen(QPen(QColor(255, 255, 255, 20), 1.0))
        p.drawRoundedRect(badge_rect, 4, 4)

        conf_pct = int(self._confidence * 100)
        p.setFont(QFont("Menlo, Courier, monospace", 8, QFont.Weight.Bold))
        p.setPen(QPen(QColor("#10B981")))
        p.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, f"CONFIDENCE: {conf_pct}%\nHARMONIC LOCK")

        p.end()
