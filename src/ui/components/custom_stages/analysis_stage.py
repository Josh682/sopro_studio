"""AnalysisStage - Custom Visual Deck for Slot 2 (Key, Tempo, and Loudness Analysis).

Features dual real-time circular analog VU meters with ballistic galvanometer needles,
Camelot harmonic key dial, BPM tempo readout, and harmonic confidence lock.
"""

from __future__ import annotations

from typing import Optional

from src.ui.qt import (
    QColor,
    QFont,
    QHBoxLayout,
    QLabel,
    QPainter,
    QPen,
    QRectF,
    QSizePolicy,
    Qt,
    QVBoxLayout,
    QWidget,
)
from src.ui.theme.tokens import TOKENS
from src.ui.widgets.analog_controls import CircularVUMeter


class AnalysisStage(QWidget):
    """Harmonic key wheel, tempo gauge, and dual ballistic VU meter monitor."""

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

        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(20, 10, 20, 10)
        main_layout.setSpacing(16)

        # 1. Left Channel Analog VU Meter (diameter: 130px)
        self.meter_l = CircularVUMeter(
            is_dual=False,
            diameter=130,
            title="CH 1 · L",
            accent_color=self._accent_color,
            parent=self,
        )
        main_layout.addWidget(self.meter_l, 0, Qt.AlignmentFlag.AlignCenter)

        # 2. Center Dial & Harmonic Readout Panel
        self.center_panel = QWidget(self)
        self.center_panel.setStyleSheet("background: transparent; border: none;")
        center_layout = QVBoxLayout(self.center_panel)
        center_layout.setContentsMargins(8, 4, 8, 4)
        center_layout.setSpacing(4)
        center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Camelot Dial Key Text
        self.lbl_camelot = QLabel(self._camelot, self.center_panel)
        self.lbl_camelot.setFont(QFont("Menlo, Courier, monospace", 22, QFont.Weight.Bold))
        self.lbl_camelot.setStyleSheet("color: #FDE68A; background: transparent;")
        self.lbl_camelot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_layout.addWidget(self.lbl_camelot)

        # Musical Key Name
        self.lbl_key = QLabel(self._key_result, self.center_panel)
        self.lbl_key.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        self.lbl_key.setStyleSheet("color: #D4A265; background: transparent;")
        self.lbl_key.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_layout.addWidget(self.lbl_key)

        # BPM readout badge
        self.lbl_bpm = QLabel(f"{self._bpm_result:.1f} BPM", self.center_panel)
        self.lbl_bpm.setFont(QFont("Menlo, Courier, monospace", 11, QFont.Weight.Bold))
        self.lbl_bpm.setStyleSheet(
            f"color: {TOKENS.colors.text.primary};"
            f"background-color: {TOKENS.colors.background.surface_card};"
            f"border: 1px solid {TOKENS.colors.border.card};"
            f"border-radius: 4px;"
            f"padding: 2px 10px;"
        )
        self.lbl_bpm.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_layout.addWidget(self.lbl_bpm)

        # Harmonic Lock Badge
        conf_pct = int(self._confidence * 100)
        self.lbl_confidence = QLabel(f"HARMONIC LOCK · {conf_pct}%", self.center_panel)
        self.lbl_confidence.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        self.lbl_confidence.setStyleSheet("color: #10B981; background: transparent;")
        self.lbl_confidence.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_layout.addWidget(self.lbl_confidence)

        main_layout.addWidget(self.center_panel, 1)

        # 3. Right Channel Analog VU Meter (diameter: 130px)
        self.meter_r = CircularVUMeter(
            is_dual=False,
            diameter=130,
            title="CH 2 · R",
            accent_color=self._accent_color,
            parent=self,
        )
        main_layout.addWidget(self.meter_r, 0, Qt.AlignmentFlag.AlignCenter)

    # -------------------------------------------------------------------------
    # Public Level & Telemetry API
    # -------------------------------------------------------------------------

    def set_levels(self, left_db: float, right_db: float) -> None:
        """Step ballistic meters from raw audio dBFS levels."""
        self.meter_l.set_level(left_db)
        self.meter_r.set_level(right_db)

    def set_angles(self, left_deg: float, right_deg: float) -> None:
        """Directly position needle deflection angles."""
        self.meter_l.set_angles(left_deg)
        self.meter_r.set_angles(right_deg)

    def set_clipped(self, left_clip: bool, right_clip: bool) -> None:
        """Set peak overload clip lamps."""
        self.meter_l.set_clipped(left_clip)
        self.meter_r.set_clipped(right_clip)

    def set_results(self, key_str: str, camelot_str: str, bpm: float, confidence: float = 0.95) -> None:
        """Update harmonic detection and BPM results."""
        self._key_result = key_str.upper()
        self._camelot = camelot_str.upper()
        self._bpm_result = float(bpm)
        self._confidence = float(confidence)

        self.lbl_camelot.setText(self._camelot)
        self.lbl_key.setText(self._key_result)
        self.lbl_bpm.setText(f"{self._bpm_result:.1f} BPM")
        conf_pct = int(self._confidence * 100)
        self.lbl_confidence.setText(f"HARMONIC LOCK · {conf_pct}%")

    def reset(self) -> None:
        """Reset meters and display to resting defaults."""
        self.meter_l.reset()
        self.meter_r.reset()

    def paintEvent(self, event) -> None:
        """Paint recessed metal chassis backdrop behind meters and center panel."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        bg_rect = QRectF(0, 0, float(self.width()), float(self.height()))
        p.setBrush(QColor(14, 10, 6))
        p.setPen(QPen(QColor(255, 255, 255, 15), 1.0))
        p.drawRoundedRect(bg_rect, 6, 6)

        p.end()
        super().paintEvent(event)
