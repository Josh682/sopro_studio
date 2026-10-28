"""AnalysisStage - Custom Visual Deck for Slot 2 (Key, Tempo, and Loudness Analysis).

Features dual real-time circular analog VU meters with ballistic galvanometer needles,
an interactive 24-cell Camelot Harmonic Matrix with automatic Circle of Fifths
highlighting, BPM tempo readout, and harmonic confidence lock.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from src.ui.qt import (
    QColor,
    QFont,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPainter,
    QPen,
    QPushButton,
    QRectF,
    QSizePolicy,
    Qt,
    QVBoxLayout,
    QWidget,
    Signal,
)
from src.ui.theme.tokens import TOKENS
from src.ui.widgets.analog_controls import CircularVUMeter


CAMELOT_KEY_NAMES: Dict[str, str] = {
    # Minor Keys (A)
    "1A": "G#m", "2A": "D#m", "3A": "A#m", "4A": "Fm",
    "5A": "Cm",  "6A": "Gm",  "7A": "Dm",  "8A": "Am",
    "9A": "Em",  "10A": "Bm", "11A": "F#m", "12A": "C#m",
    # Major Keys (B)
    "1B": "B",   "2B": "F#",  "3B": "C#",  "4B": "Ab",
    "5B": "Eb",  "6B": "Bb",  "7B": "F",   "8B": "C",
    "9B": "G",   "10B": "D",  "11B": "A",   "12B": "E",
}


def get_compatible_camelot_keys(camelot_code: str) -> Set[str]:
    """Calculate harmonically compatible Camelot keys using Circle of Fifths.

    Rules:
    1. Exact Match (same key): (N, L)
    2. Energy Down / Subdominant (-1 step): ((N - 2) % 12 + 1, L)
    3. Energy Up / Dominant (+1 step): (N % 12 + 1, L)
    4. Relative Mode (cross major/minor): (N, opposite(L))

    Example:
        '8A' (A Minor) -> {'8A', '7A', '9A', '8B'}
    """
    clean = camelot_code.upper().strip()
    match = re.match(r"^(\d+)([AB])$", clean)
    if not match:
        return {clean} if clean in CAMELOT_KEY_NAMES else set()

    n = int(match.group(1))
    letter = match.group(2)

    down_n = ((n - 2) % 12) + 1
    up_n = (n % 12) + 1
    other_letter = "B" if letter == "A" else "A"

    return {
        f"{n}{letter}",
        f"{down_n}{letter}",
        f"{up_n}{letter}",
        f"{n}{other_letter}",
    }


def describe_harmonic_relation(selected_code: str, root_code: str) -> str:
    """Describe the harmonic mixing relationship between two Camelot keys."""
    sel = selected_code.upper()
    root = root_code.upper()
    if sel == root:
        return f"{sel} ({CAMELOT_KEY_NAMES.get(sel, '')}) · ROOT DETECTED KEY"

    m_sel = re.match(r"^(\d+)([AB])$", sel)
    m_root = re.match(r"^(\d+)([AB])$", root)
    if not m_sel or not m_root:
        return f"{sel} ({CAMELOT_KEY_NAMES.get(sel, '')})"

    n_sel, l_sel = int(m_sel.group(1)), m_sel.group(2)
    n_root, l_root = int(m_root.group(1)), m_root.group(2)

    diff = (n_sel - n_root) % 12
    if diff == 1 and l_sel == l_root:
        return f"{sel} ({CAMELOT_KEY_NAMES.get(sel, '')}) · +1 ENERGY LIFT (DOMINANT)"
    elif diff == 11 and l_sel == l_root:
        return f"{sel} ({CAMELOT_KEY_NAMES.get(sel, '')}) · -1 ENERGY DROP (SUBDOMINANT)"
    elif n_sel == n_root and l_sel != l_root:
        mode_str = "RELATIVE MAJOR" if l_sel == "B" else "RELATIVE MINOR"
        return f"{sel} ({CAMELOT_KEY_NAMES.get(sel, '')}) · {mode_str}"
    else:
        return f"{sel} ({CAMELOT_KEY_NAMES.get(sel, '')}) · MODULATION SHIFT ({diff:+d})"


class CamelotMatrixWidget(QWidget):
    """Interactive 24-cell Camelot Wheel matrix widget."""

    cellSelected = Signal(str, str)  # code, description

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._detected_key: str = "8A"
        self._compatible_keys: Set[str] = get_compatible_camelot_keys("8A")
        self._selected_cell: str = "8A"
        self._buttons: Dict[str, QPushButton] = {}

        self.setFixedHeight(50)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Row 1: 1B to 12B (Major)
        row_b_layout = QHBoxLayout()
        row_b_layout.setContentsMargins(0, 0, 0, 0)
        row_b_layout.setSpacing(2)

        for i in range(1, 13):
            code = f"{i}B"
            btn = self._create_cell_button(code)
            self._buttons[code] = btn
            row_b_layout.addWidget(btn)

        layout.addLayout(row_b_layout)

        # Row 2: 1A to 12A (Minor)
        row_a_layout = QHBoxLayout()
        row_a_layout.setContentsMargins(0, 0, 0, 0)
        row_a_layout.setSpacing(2)

        for i in range(1, 13):
            code = f"{i}A"
            btn = self._create_cell_button(code)
            self._buttons[code] = btn
            row_a_layout.addWidget(btn)

        layout.addLayout(row_a_layout)
        self._refresh_styles()

    def _create_cell_button(self, code: str) -> QPushButton:
        btn = QPushButton(code, self)
        btn.setFixedHeight(22)
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn.setFont(QFont("Menlo, Courier, monospace", 8, QFont.Weight.Bold))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        key_name = CAMELOT_KEY_NAMES.get(code, "")
        btn.setToolTip(f"{code} : {key_name}")
        btn.clicked.connect(lambda: self._on_cell_clicked(code))
        return btn

    def _on_cell_clicked(self, code: str) -> None:
        self._selected_cell = code
        self._refresh_styles()
        desc = describe_harmonic_relation(code, self._detected_key)
        self.cellSelected.emit(code, desc)

    def set_detected_key(self, camelot_code: str) -> None:
        """Update detected root key and recalculate harmonic compatibility."""
        clean = camelot_code.upper().strip()
        self._detected_key = clean
        self._selected_cell = clean
        self._compatible_keys = get_compatible_camelot_keys(clean)
        self._refresh_styles()

    def _refresh_styles(self) -> None:
        """Refresh styling and illumination of all 24 cells."""
        for code, btn in self._buttons.items():
            key_name = CAMELOT_KEY_NAMES.get(code, "")
            if code == self._detected_key:
                # Root Detected Key: Radiant Warm Amber Gold
                btn.setStyleSheet(
                    "QPushButton {"
                    "  background-color: #F59E0B;"
                    "  color: #0F0B08;"
                    "  border: 1px solid #FDE68A;"
                    "  border-radius: 2px;"
                    "  font-weight: 800;"
                    "}"
                )
            elif code in self._compatible_keys:
                # Harmonically Compatible: Emerald / Mint Glow
                btn.setStyleSheet(
                    "QPushButton {"
                    "  background-color: #064E3B;"
                    "  color: #34D399;"
                    "  border: 1px solid #10B981;"
                    "  border-radius: 2px;"
                    "  font-weight: 700;"
                    "}"
                    "QPushButton:hover { background-color: #047857; color: #FFFFFF; }"
                )
            elif code == self._selected_cell:
                # Manually inspected cell
                btn.setStyleSheet(
                    "QPushButton {"
                    "  background-color: #2D221A;"
                    "  color: #EDE6DC;"
                    "  border: 1px solid #8B5CF6;"
                    "  border-radius: 2px;"
                    "}"
                )
            else:
                # Inactive / Incompatible: Dimmed Gunmetal
                btn.setStyleSheet(
                    "QPushButton {"
                    "  background-color: #120D0A;"
                    "  color: #524338;"
                    "  border: 1px solid rgba(255, 255, 255, 0.04);"
                    "  border-radius: 2px;"
                    "  font-weight: 500;"
                    "}"
                    "QPushButton:hover {"
                    "  background-color: #1C1510;"
                    "  color: #A89582;"
                    "  border-color: rgba(255, 255, 255, 0.10);"
                    "}"
                )


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
        main_layout.setContentsMargins(16, 8, 16, 8)
        main_layout.setSpacing(12)

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
        center_layout.setContentsMargins(4, 2, 4, 2)
        center_layout.setSpacing(3)
        center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Top Readout Bar: Camelot Code + Key Name + BPM
        header_bar = QHBoxLayout()
        header_bar.setContentsMargins(0, 0, 0, 0)
        header_bar.setSpacing(8)

        self.lbl_camelot = QLabel(self._camelot, self.center_panel)
        self.lbl_camelot.setFont(QFont("Menlo, Courier, monospace", 16, QFont.Weight.Bold))
        self.lbl_camelot.setStyleSheet("color: #FDE68A; background: transparent;")
        header_bar.addWidget(self.lbl_camelot)

        self.lbl_key = QLabel(self._key_result, self.center_panel)
        self.lbl_key.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.lbl_key.setStyleSheet("color: #D4A265; background: transparent;")
        header_bar.addWidget(self.lbl_key)

        header_bar.addStretch()

        self.lbl_bpm = QLabel(f"{self._bpm_result:.1f} BPM", self.center_panel)
        self.lbl_bpm.setFont(QFont("Menlo, Courier, monospace", 10, QFont.Weight.Bold))
        self.lbl_bpm.setStyleSheet(
            f"color: {TOKENS.colors.text.primary};"
            f"background-color: {TOKENS.colors.background.surface_card};"
            f"border: 1px solid {TOKENS.colors.border.card};"
            f"border-radius: 3px;"
            f"padding: 1px 8px;"
        )
        header_bar.addWidget(self.lbl_bpm)

        conf_pct = int(self._confidence * 100)
        self.lbl_confidence = QLabel(f"LOCK {conf_pct}%", self.center_panel)
        self.lbl_confidence.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        self.lbl_confidence.setStyleSheet("color: #10B981; background: transparent;")
        header_bar.addWidget(self.lbl_confidence)

        center_layout.addLayout(header_bar)

        # Interactive 24-Cell Camelot Matrix Grid
        self.camelot_matrix = CamelotMatrixWidget(self.center_panel)
        self.camelot_matrix.cellSelected.connect(self._on_matrix_cell_selected)
        center_layout.addWidget(self.camelot_matrix)

        # Bottom Relationship Readout Subtitle
        self.lbl_harmonic_desc = QLabel(
            "8A (Am) · ROOT DETECTED KEY · HARMONIC MATCHES: 7A, 9A, 8B", self.center_panel
        )
        self.lbl_harmonic_desc.setFont(QFont("Menlo, Courier, monospace", 7, QFont.Weight.Bold))
        self.lbl_harmonic_desc.setStyleSheet(
            "color: #10B981; background: transparent; padding: 1px 0px;"
        )
        self.lbl_harmonic_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_layout.addWidget(self.lbl_harmonic_desc)

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

    def _on_matrix_cell_selected(self, code: str, description: str) -> None:
        """Handle user clicking on a Camelot matrix cell."""
        self.lbl_harmonic_desc.setText(description)
        if code in self.camelot_matrix._compatible_keys:
            self.lbl_harmonic_desc.setStyleSheet("color: #10B981; background: transparent;")
        elif code == self.camelot_matrix._detected_key:
            self.lbl_harmonic_desc.setStyleSheet("color: #F59E0B; background: transparent;")
        else:
            self.lbl_harmonic_desc.setStyleSheet(f"color: {TOKENS.colors.text.muted}; background: transparent;")

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
        """Update harmonic detection and BPM results and refresh Camelot matrix."""
        self._key_result = key_str.upper()
        self._camelot = camelot_str.upper()
        self._bpm_result = float(bpm)
        self._confidence = float(confidence)

        self.lbl_camelot.setText(self._camelot)
        self.lbl_key.setText(self._key_result)
        self.lbl_bpm.setText(f"{self._bpm_result:.1f} BPM")
        conf_pct = int(self._confidence * 100)
        self.lbl_confidence.setText(f"LOCK {conf_pct}%")

        self.camelot_matrix.set_detected_key(self._camelot)
        comp_str = ", ".join(sorted(self.camelot_matrix._compatible_keys - {self._camelot}))
        root_name = CAMELOT_KEY_NAMES.get(self._camelot, "")
        self.lbl_harmonic_desc.setText(f"{self._camelot} ({root_name}) · ROOT DETECTED KEY · MATCHES: {comp_str}")
        self.lbl_harmonic_desc.setStyleSheet("color: #10B981; background: transparent;")

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
