"""StemDeckStage - Custom Visual Deck for Slot 2 (AI Stem Separator).

Interactive 4-track stem mixing console:
- Vocals (#EC4899)
- Drums  (#3B82F6)
- Bass   (#10B981)
- Other  (#F59E0B)

Provides:
- Illuminated Solo [S] and Mute [M] matrix switches.
- Tactile vertical volume faders (-60 dB to +6 dB, unity at 0 dB).
- Real-time 8-segment LED level ladder driven by live playhead RMS.
- Post-separation stem routing and direct audio playback.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, Optional

from src.ui.qt import (
    QColor,
    QFont,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPainter,
    QPen,
    QPushButton,
    QRectF,
    QSizePolicy,
    QSlider,
    Qt,
    QVBoxLayout,
    QWidget,
    Signal,
)
from src.ui.theme.tokens import TOKENS


def db_to_linear(db: float) -> float:
    """Convert decibels to linear amplitude gain."""
    if db <= -60.0:
        return 0.0
    return math.pow(10.0, db / 20.0)


def slider_to_db(val: int) -> float:
    """Map slider integer [0, 100] to decibels [-60.0 dB, +6.0 dB].
    
    0 = -inf (muted)
    80 = 0.0 dB (unity)
    100 = +6.0 dB
    """
    if val <= 0:
        return -80.0
    elif val <= 80:
        return -60.0 + (float(val) / 80.0) * 60.0
    else:
        return ((float(val) - 80.0) / 20.0) * 6.0


class MiniStemLEDLadder(QWidget):
    """8-segment vertical mini LED level ladder for a stem channel."""

    def __init__(self, accent_color: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._accent_color = accent_color
        self._level_db: float = -80.0
        self.setFixedWidth(14)
        self.setFixedHeight(54)

    def set_level(self, dbfs: float) -> None:
        """Update active LED segments from audio level in dBFS."""
        self._level_db = float(dbfs)
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = float(self.width())
        h = float(self.height())
        num_leds = 8
        spacing = 2.0
        led_h = (h - (num_leds - 1) * spacing) / num_leds

        # Map dBFS [-48, 0] to active segment count [0, 8]
        if self._level_db <= -48.0:
            active_count = 0
        elif self._level_db >= 0.0:
            active_count = num_leds
        else:
            norm = (self._level_db + 48.0) / 48.0
            active_count = int(round(norm * num_leds))

        for i in range(num_leds):
            # i=0 bottom, i=7 top
            ly = h - (i + 1) * led_h - i * spacing
            led_rect = QRectF(1.0, ly, w - 2.0, led_h)

            is_lit = i < active_count

            if i < 5:
                # Green zone (-48 dB to -12 dB)
                color = QColor(16, 185, 129, 230) if is_lit else QColor(16, 185, 129, 35)
            elif i < 7:
                # Amber zone (-12 dB to -2 dB)
                color = QColor(245, 158, 11, 240) if is_lit else QColor(245, 158, 11, 35)
            else:
                # Red peak zone (> -2 dB)
                color = QColor(239, 68, 68, 255) if is_lit else QColor(239, 68, 68, 40)

            p.setBrush(color)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(led_rect, 1.0, 1.0)

        p.end()


class StemChannelStrip(QFrame):
    """Interactive channel strip for a single isolated stem."""

    soloToggled = Signal(str, bool)      # stem_name, is_solo
    muteToggled = Signal(str, bool)      # stem_name, is_mute
    faderChanged = Signal(str, float)    # stem_name, linear_gain

    def __init__(
        self,
        stem_name: str,
        accent_color: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.stem_name = stem_name.upper()
        self.accent_color = accent_color
        self._is_solo: bool = False
        self._is_mute: bool = False
        self._db_value: float = 0.0
        self._linear_gain: float = 1.0

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 1. Strip Header (Stem Label)
        self.lbl_title = QLabel(self.stem_name, self)
        self.lbl_title.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_title.setStyleSheet(f"color: {self.accent_color}; background: transparent; border: none;")
        layout.addWidget(self.lbl_title)

        # 2. Solo [S] and Mute [M] Matrix Push Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(4)

        btn_base_style = (
            "QPushButton {"
            "  background-color: #1A1410;"
            "  color: #8C7C6D;"
            "  border: 1px solid #33261C;"
            "  border-radius: 3px;"
            "  font-size: 9px;"
            "  font-weight: bold;"
            "  padding: 2px 0px;"
            "}"
            "QPushButton:hover {"
            "  background-color: #261D17;"
            "  color: #EDE6DC;"
            "}"
        )

        self.btn_solo = QPushButton("S", self)
        self.btn_solo.setFixedSize(22, 18)
        self.btn_solo.setCheckable(True)
        self.btn_solo.setToolTip(f"Solo {self.stem_name}")
        self.btn_solo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_solo.setStyleSheet(btn_base_style)
        self.btn_solo.clicked.connect(self._on_solo_clicked)
        btn_layout.addWidget(self.btn_solo)

        self.btn_mute = QPushButton("M", self)
        self.btn_mute.setFixedSize(22, 18)
        self.btn_mute.setCheckable(True)
        self.btn_mute.setToolTip(f"Mute {self.stem_name}")
        self.btn_mute.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_mute.setStyleSheet(btn_base_style)
        self.btn_mute.clicked.connect(self._on_mute_clicked)
        btn_layout.addWidget(self.btn_mute)

        layout.addLayout(btn_layout)

        # 3. Center Section: Mini Fader Slider & Vertical LED Ladder
        center_layout = QHBoxLayout()
        center_layout.setContentsMargins(4, 2, 4, 2)
        center_layout.setSpacing(6)
        center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Mini vertical volume fader slider
        self.slider = QSlider(Qt.Orientation.Vertical, self)
        self.slider.setRange(0, 100)
        self.slider.setValue(80)  # Unity 0.0 dB
        self.slider.setFixedHeight(54)
        self.slider.setFixedWidth(16)
        self.slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self.slider.setStyleSheet(
            f"QSlider::groove:vertical {{"
            f"  background: #120D0A;"
            f"  width: 4px;"
            f"  border-radius: 2px;"
            f"}}"
            f"QSlider::sub-page:vertical {{"
            f"  background: #2D221A;"
            f"  border-radius: 2px;"
            f"}}"
            f"QSlider::add-page:vertical {{"
            f"  background: {self.accent_color};"
            f"  border-radius: 2px;"
            f"}}"
            f"QSlider::handle:vertical {{"
            f"  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #E0D4C3, stop:1 #80705E);"
            f"  height: 10px;"
            f"  margin: 0 -5px;"
            f"  border: 1px solid #33261C;"
            f"  border-radius: 2px;"
            f"}}"
        )
        self.slider.valueChanged.connect(self._on_slider_changed)
        center_layout.addWidget(self.slider)

        # Mini LED Level Ladder
        self.led_ladder = MiniStemLEDLadder(accent_color=self.accent_color, parent=self)
        center_layout.addWidget(self.led_ladder)

        layout.addLayout(center_layout)

        # 4. Readout Badge (dB)
        self.lbl_db = QLabel("0.0 dB", self)
        self.lbl_db.setFont(QFont("Menlo, Courier, monospace", 8, QFont.Weight.Bold))
        self.lbl_db.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_db.setStyleSheet(
            f"color: {TOKENS.colors.text.display_readout};"
            f"background-color: {TOKENS.colors.background.surface_display_glass};"
            f"border: 1px solid rgba(255, 255, 255, 0.08);"
            f"border-radius: 2px;"
            f"padding: 1px 3px;"
        )
        layout.addWidget(self.lbl_db)

        # 5. Status Badge
        self.lbl_status = QLabel("ACTIVE", self)
        self.lbl_status.setFont(QFont("Menlo, Courier, monospace", 7, QFont.Weight.Bold))
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setStyleSheet(f"color: {TOKENS.colors.text.muted}; background: transparent;")
        layout.addWidget(self.lbl_status)

        self._update_style()

    def _update_style(self) -> None:
        """Update frame border and button backlights."""
        # Recessed frame
        if self._is_solo:
            self.setStyleSheet(
                f"StemChannelStrip {{"
                f"  background-color: #1A1215;"
                f"  border: 1px solid {self.accent_color};"
                f"  border-radius: 4px;"
                f"}}"
            )
        elif self._is_mute:
            self.setStyleSheet(
                "StemChannelStrip {"
                "  background-color: #181010;"
                "  border: 1px solid #4A1A1A;"
                "  border-radius: 4px;"
                "}"
            )
        else:
            self.setStyleSheet(
                "StemChannelStrip {"
                "  background-color: #140E0A;"
                "  border: 1px solid rgba(255, 255, 255, 0.06);"
                "  border-radius: 4px;"
                "}"
            )

        # Solo button backlight
        if self._is_solo:
            self.btn_solo.setStyleSheet(
                f"QPushButton {{"
                f"  background-color: {self.accent_color};"
                f"  color: #0A0A0A;"
                f"  border: 1px solid #FFFFFF;"
                f"  border-radius: 3px;"
                f"  font-size: 9px;"
                f"  font-weight: bold;"
                f"}}"
            )
        else:
            self.btn_solo.setStyleSheet(
                "QPushButton {"
                "  background-color: #1A1410;"
                "  color: #8C7C6D;"
                "  border: 1px solid #33261C;"
                "  border-radius: 3px;"
                "  font-size: 9px;"
                "  font-weight: bold;"
                "}"
            )

        # Mute button backlight
        if self._is_mute:
            self.btn_mute.setStyleSheet(
                "QPushButton {"
                "  background-color: #EF4444;"
                "  color: #FFFFFF;"
                "  border: 1px solid #FFAAAA;"
                "  border-radius: 3px;"
                "  font-size: 9px;"
                "  font-weight: bold;"
                "}"
            )
        else:
            self.btn_mute.setStyleSheet(
                "QPushButton {"
                "  background-color: #1A1410;"
                "  color: #8C7C6D;"
                "  border: 1px solid #33261C;"
                "  border-radius: 3px;"
                "  font-size: 9px;"
                "  font-weight: bold;"
                "}"
            )

    def _on_solo_clicked(self) -> None:
        self._is_solo = self.btn_solo.isChecked()
        self._update_status()
        self._update_style()
        self.soloToggled.emit(self.stem_name.lower(), self._is_solo)

    def _on_mute_clicked(self) -> None:
        self._is_mute = self.btn_mute.isChecked()
        self._update_status()
        self._update_style()
        self.muteToggled.emit(self.stem_name.lower(), self._is_mute)

    def _on_slider_changed(self, val: int) -> None:
        self._db_value = slider_to_db(val)
        self._linear_gain = db_to_linear(self._db_value)

        if val <= 0:
            self.lbl_db.setText("MUTED")
            self.lbl_db.setStyleSheet("color: #EF4444; background-color: #1A0D0D; border: 1px solid #3A1414; border-radius: 2px;")
        elif self._db_value >= 0.05:
            self.lbl_db.setText(f"+{self._db_value:.1f} dB")
            self.lbl_db.setStyleSheet(f"color: {self.accent_color}; background-color: #120D0A; border: 1px solid rgba(255,255,255,0.08); border-radius: 2px;")
        else:
            self.lbl_db.setText(f"{self._db_value:.1f} dB")
            self.lbl_db.setStyleSheet(f"color: {TOKENS.colors.text.display_readout}; background-color: #120D0A; border: 1px solid rgba(255,255,255,0.08); border-radius: 2px;")

        self.faderChanged.emit(self.stem_name.lower(), self._linear_gain)

    def _update_status(self) -> None:
        if self._is_mute:
            self.lbl_status.setText("MUTED")
            self.lbl_status.setStyleSheet("color: #EF4444; background: transparent;")
        elif self._is_solo:
            self.lbl_status.setText("SOLO")
            self.lbl_status.setStyleSheet(f"color: {self.accent_color}; background: transparent;")
        else:
            self.lbl_status.setText("ACTIVE")
            self.lbl_status.setStyleSheet(f"color: {TOKENS.colors.text.muted}; background: transparent;")

    def set_level(self, dbfs: float) -> None:
        """Update live ladder LED deflection."""
        self.led_ladder.set_level(dbfs)


class StemDeckStage(QWidget):
    """4-track visual stem isolation monitor & interactive mixer."""

    STEMS = [
        ("VOCALS", "#EC4899"),
        ("DRUMS", "#3B82F6"),
        ("BASS", "#10B981"),
        ("OTHER", "#F59E0B"),
    ]

    stemSoloToggled = Signal(str, bool)    # stem_name, is_solo
    stemMuteToggled = Signal(str, bool)    # stem_name, is_mute
    stemFaderChanged = Signal(str, float)  # stem_name, gain_linear
    stemsLoaded = Signal(dict)             # {stem_name: Path}

    def __init__(
        self,
        accent_color: str = "#EC4899",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._accent_color = accent_color
        self._stem_strips: Dict[str, StemChannelStrip] = {}
        self._stem_paths: Dict[str, Path] = {}

        self.setFixedHeight(170)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        for name, col_hex in self.STEMS:
            strip = StemChannelStrip(stem_name=name, accent_color=col_hex, parent=self)
            strip.soloToggled.connect(self._on_strip_solo)
            strip.muteToggled.connect(self._on_strip_mute)
            strip.faderChanged.connect(self._on_strip_fader)
            self._stem_strips[name.lower()] = strip
            layout.addWidget(strip)

    def _on_strip_solo(self, stem_name: str, is_solo: bool) -> None:
        self.stemSoloToggled.emit(stem_name, is_solo)

    def _on_strip_mute(self, stem_name: str, is_mute: bool) -> None:
        self.stemMuteToggled.emit(stem_name, is_mute)

    def _on_strip_fader(self, stem_name: str, gain: float) -> None:
        self.stemFaderChanged.emit(stem_name, gain)

    def load_stems(self, stems: dict[str, str | Path]) -> None:
        """Register separated stems and update channel readiness."""
        self._stem_paths = {k.lower(): Path(v) for k, v in stems.items()}
        for name, strip in self._stem_strips.items():
            if name in self._stem_paths and self._stem_paths[name].is_file():
                strip.lbl_status.setText("READY")
                strip.lbl_status.setStyleSheet("color: #10B981; background: transparent;")
            else:
                strip.lbl_status.setText("OFFLINE")
                strip.lbl_status.setStyleSheet("color: #6B7280; background: transparent;")
        self.stemsLoaded.emit(self._stem_paths)

    def set_stem_level(self, stem_name: str, dbfs: float) -> None:
        """Update LED level for a specific stem channel."""
        name = stem_name.lower()
        if name in self._stem_strips:
            self._stem_strips[name].set_level(dbfs)

    def set_stem_levels(self, levels: dict[str, float]) -> None:
        """Update LED levels for all stems simultaneously."""
        for name, db in levels.items():
            self.set_stem_level(name, db)

    def reset(self) -> None:
        """Reset all faders and buttons to defaults."""
        for strip in self._stem_strips.values():
            strip.slider.setValue(80)
            strip.btn_solo.setChecked(False)
            strip.btn_mute.setChecked(False)
            strip._is_solo = False
            strip._is_mute = False
            strip._update_status()
            strip._update_style()
            strip.set_level(-80.0)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        bg_rect = QRectF(0, 0, float(self.width()), float(self.height()))
        p.setBrush(QColor(14, 10, 6))
        p.setPen(QPen(QColor(255, 255, 255, 15), 1.0))
        p.drawRoundedRect(bg_rect, 6, 6)
        p.end()
        super().paintEvent(event)
