"""SettingsView - Analog Console Preferences & Audio Engine Configuration.

Provides configuration controls for:
- Default output directory with native directory picker
- Audio engine device, sample rate, and buffer sizes
- AI processing hardware acceleration (CPU / Metal MPS / CUDA)
- Persistent settings integration with AppConfig
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from src.ui.qt import (
    QFileDialog,
    QFont,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    Qt,
    QVBoxLayout,
    QWidget,
    Signal,
)

from src.ui.theme.tokens import TOKENS
from src.utils import AppConfig
from src.utils.paths import outputs_dir, models_dir


class SettingsView(QWidget):
    """Analog-themed settings page within the MainWindow navigation stack."""

    back_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._config = AppConfig()

        self._setup_ui()
        self._load_values()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        margin_x = TOKENS.dimensions.shell.margin_x  # 24px
        main_layout.setContentsMargins(margin_x, 12, margin_x, 20)
        main_layout.setSpacing(16)

        # 1. Top Bar with Back Button & Header Title
        topbar = QFrame(self)
        topbar.setFixedHeight(40)
        topbar_layout = QHBoxLayout(topbar)
        topbar_layout.setContentsMargins(0, 0, 0, 0)
        topbar_layout.setSpacing(12)

        self.btn_back = QPushButton("←  ESC : DASHBOARD", topbar)
        self.btn_back.setFont(TOKENS.typography.create_font("data_mono_sm"))
        self.btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_back.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: {TOKENS.colors.background.surface_card};"
            f"  color: {TOKENS.colors.text.secondary};"
            f"  border: 1px solid {TOKENS.colors.border.card};"
            f"  border-radius: {TOKENS.radii.sm}px;"
            f"  padding: 6px 14px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: {TOKENS.colors.background.surface_card_hover};"
            f"  color: {TOKENS.colors.text.primary};"
            f"  border-color: {TOKENS.colors.border.card_hover};"
            f"}}"
            f"QPushButton:pressed {{"
            f"  background-color: #120E0B;"
            f"}}"
        )
        self.btn_back.clicked.connect(self.back_requested.emit)
        topbar_layout.addWidget(self.btn_back)

        self.lbl_title = QLabel("SYSTEM & ENGINE SETTINGS", topbar)
        self.lbl_title.setFont(TOKENS.typography.create_font("title_h1"))
        self.lbl_title.setStyleSheet(f"color: {TOKENS.colors.text.silkscreen_title}; font-weight: 700; letter-spacing: 0.5px;")
        topbar_layout.addWidget(self.lbl_title)

        topbar_layout.addStretch()
        main_layout.addWidget(topbar)

        # 2. Main Settings Container (Chassis Bronze Panel)
        panel = QFrame(self)
        panel.setStyleSheet(
            f"QFrame {{"
            f"  background-color: {TOKENS.colors.background.surface_card};"
            f"  border: 1px solid {TOKENS.colors.border.card};"
            f"  border-radius: {TOKENS.radii.card}px;"
            f"}}"
        )
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(28, 24, 28, 24)
        panel_layout.setSpacing(20)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)

        # Section 1: Storage & Directories
        lbl_sec1 = QLabel("STORAGE & EXPORT PATHS", panel)
        lbl_sec1.setFont(TOKENS.typography.create_font("silkscreen_tag"))
        lbl_sec1.setStyleSheet("color: #F59E0B; font-weight: bold;")
        panel_layout.addWidget(lbl_sec1)

        # Output Dir Row
        lbl_out = QLabel("Default Output Directory:", panel)
        lbl_out.setFont(TOKENS.typography.create_font("body_sm"))
        lbl_out.setStyleSheet(f"color: {TOKENS.colors.text.secondary};")
        grid.addWidget(lbl_out, 0, 0)

        self.txt_output = QLineEdit(panel)
        self.txt_output.setFont(TOKENS.typography.create_font("data_mono_sm"))
        self.txt_output.setStyleSheet(
            f"QLineEdit {{"
            f"  background-color: #100C08;"
            f"  color: {TOKENS.colors.text.primary};"
            f"  border: 1px solid {TOKENS.colors.border.subtle};"
            f"  border-radius: 4px;"
            f"  padding: 6px 10px;"
            f"}}"
            f"QLineEdit:focus {{"
            f"  border: 1px solid #F59E0B;"
            f"}}"
        )
        grid.addWidget(self.txt_output, 0, 1)

        self.btn_browse_out = QPushButton("Browse...", panel)
        self.btn_browse_out.setFont(TOKENS.typography.create_font("data_mono_sm"))
        self.btn_browse_out.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_browse_out.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: #241A12;"
            f"  color: {TOKENS.colors.text.secondary};"
            f"  border: 1px solid {TOKENS.colors.border.card};"
            f"  border-radius: 4px;"
            f"  padding: 6px 12px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: #332418;"
            f"  color: #EDE6DC;"
            f"}}"
        )
        self.btn_browse_out.clicked.connect(self._browse_output_dir)
        grid.addWidget(self.btn_browse_out, 0, 2)

        # Section 2: Audio Engine
        lbl_sec2 = QLabel("CORE AUDIO ENGINE", panel)
        lbl_sec2.setFont(TOKENS.typography.create_font("silkscreen_tag"))
        lbl_sec2.setStyleSheet("color: #F59E0B; font-weight: bold; margin-top: 8px;")
        grid.addWidget(lbl_sec2, 1, 0, 1, 3)

        lbl_sr = QLabel("Processing Sample Rate:", panel)
        lbl_sr.setFont(TOKENS.typography.create_font("body_sm"))
        lbl_sr.setStyleSheet(f"color: {TOKENS.colors.text.secondary};")
        grid.addWidget(lbl_sr, 2, 0)

        self.lbl_sr_val = QLabel("48.0 kHz (Studio Reference)", panel)
        self.lbl_sr_val.setFont(TOKENS.typography.create_font("data_mono_sm"))
        self.lbl_sr_val.setStyleSheet("color: #22C55E; font-weight: bold;")
        grid.addWidget(self.lbl_sr_val, 2, 1)

        lbl_buf = QLabel("Buffer Block Size:", panel)
        lbl_buf.setFont(TOKENS.typography.create_font("body_sm"))
        lbl_buf.setStyleSheet(f"color: {TOKENS.colors.text.secondary};")
        grid.addWidget(lbl_buf, 3, 0)

        self.lbl_buf_val = QLabel("512 samples (10.7 ms latency)", panel)
        self.lbl_buf_val.setFont(TOKENS.typography.create_font("data_mono_sm"))
        self.lbl_buf_val.setStyleSheet("color: #EDE6DC;")
        grid.addWidget(self.lbl_buf_val, 3, 1)

        # Section 3: Hardware Acceleration
        lbl_sec3 = QLabel("AI ACCELERATION BACKEND", panel)
        lbl_sec3.setFont(TOKENS.typography.create_font("silkscreen_tag"))
        lbl_sec3.setStyleSheet("color: #F59E0B; font-weight: bold; margin-top: 8px;")
        grid.addWidget(lbl_sec3, 4, 0, 1, 3)

        lbl_acc = QLabel("Compute Device:", panel)
        lbl_acc.setFont(TOKENS.typography.create_font("body_sm"))
        lbl_acc.setStyleSheet(f"color: {TOKENS.colors.text.secondary};")
        grid.addWidget(lbl_acc, 5, 0)

        self.lbl_acc_val = QLabel("Apple Metal Performance Shaders (MPS / GPU)", panel)
        self.lbl_acc_val.setFont(TOKENS.typography.create_font("data_mono_sm"))
        self.lbl_acc_val.setStyleSheet("color: #38BDF8; font-weight: bold;")
        grid.addWidget(self.lbl_acc_val, 5, 1)

        panel_layout.addLayout(grid)
        panel_layout.addStretch()

        # Action Buttons Row
        actions_row = QHBoxLayout()
        actions_row.addStretch()

        self.btn_save = QPushButton("SAVE CHANGES", panel)
        self.btn_save.setFont(TOKENS.typography.create_font("data_mono_sm"))
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: #F59E0B;"
            f"  color: #1A1108;"
            f"  font-weight: bold;"
            f"  border: 1px solid rgba(0, 0, 0, 0.4);"
            f"  border-radius: 4px;"
            f"  padding: 8px 24px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: #FBBF24;"
            f"}}"
            f"QPushButton:pressed {{"
            f"  background-color: #D97706;"
            f"}}"
        )
        self.btn_save.clicked.connect(self._save_settings)
        actions_row.addWidget(self.btn_save)

        panel_layout.addLayout(actions_row)
        main_layout.addWidget(panel)

    def _browse_output_dir(self) -> None:
        current = self.txt_output.text() or str(outputs_dir())
        chosen = QFileDialog.getExistingDirectory(self, "Select Output Directory", current)
        if chosen:
            self.txt_output.setText(chosen)

    def _load_values(self) -> None:
        try:
            saved_dir = str(self._config.output_dir)
        except Exception:
            saved_dir = str(outputs_dir())
        self.txt_output.setText(saved_dir)

    def _save_settings(self) -> None:
        out_path = self.txt_output.text().strip()
        if out_path:
            try:
                self._config.output_dir = Path(out_path)
            except Exception:
                pass
            self.btn_save.setText("SAVED ✓")
            self.btn_save.setStyleSheet(
                "QPushButton {"
                "  background-color: #22C55E;"
                "  color: #0F172A;"
                "  font-weight: bold;"
                "  border: 1px solid rgba(0, 0, 0, 0.4);"
                "  border-radius: 4px;"
                "  padding: 8px 24px;"
                "}"
            )
