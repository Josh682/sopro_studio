"""Application configuration settings page with persistent QSettings binding."""

from __future__ import annotations

import logging
from pathlib import Path

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from src.utils import AppConfig
from src.utils.paths import outputs_dir, models_dir

log = logging.getLogger("sound_processor.gui.settings_page")


from src.gui.watermarked_page import WatermarkedPage

class SettingsPage(WatermarkedPage):
    """Configuration dashboard for paths, binaries, and engine VRAM settings."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = AppConfig()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(24)

        # Header Title
        title = QLabel("Settings")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #cdd6f4;")
        layout.addWidget(title)

        # Form content
        form = QWidget()
        form_layout = QFormLayout(form)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(16)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # 1. Output Directory Row
        self._output_edit = QLineEdit()
        self._output_btn = QPushButton("Browse...")
        self._output_btn.clicked.connect(self._browse_output)
        
        output_row = QHBoxLayout()
        output_row.addWidget(self._output_edit)
        output_row.addWidget(self._output_btn)
        form_layout.addRow("Default Output Folder:", output_row)

        # 2. Models Directory Row
        self._models_edit = QLineEdit()
        self._models_btn = QPushButton("Browse...")
        self._models_btn.clicked.connect(self._browse_models)
        
        models_row = QHBoxLayout()
        models_row.addWidget(self._models_edit)
        models_row.addWidget(self._models_btn)
        form_layout.addRow("AI Models Folder:", models_row)

        # Auto Update Toggle
        self._auto_update_checkbox = QCheckBox("Automatically check for updates")
        self._auto_update_checkbox.setStyleSheet("color: #cdd6f4;")
        form_layout.addRow("", self._auto_update_checkbox)

        # 3. FFmpeg Path Row
        self._ffmpeg_edit = QLineEdit()
        self._ffmpeg_btn = QPushButton("Browse...")
        self._ffmpeg_btn.clicked.connect(self._browse_ffmpeg)
        
        ffmpeg_row = QHBoxLayout()
        ffmpeg_row.addWidget(self._ffmpeg_edit)
        ffmpeg_row.addWidget(self._ffmpeg_btn)
        form_layout.addRow("FFmpeg Executable:", ffmpeg_row)

        # 4. MelBand Chunk Size Row
        self._chunk_slider = QSlider(Qt.Orientation.Horizontal)
        self._chunk_slider.setRange(2, 16)  # 2 to 16 seconds
        self._chunk_slider.setSingleStep(1)
        self._chunk_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._chunk_slider.setTickInterval(2)
        self._chunk_slider.valueChanged.connect(self._update_chunk_label)

        self._chunk_label = QLabel("")
        self._chunk_label.setStyleSheet("color: #a6adc8; font-size: 12px;")

        chunk_row = QVBoxLayout()
        chunk_row.addWidget(self._chunk_slider)
        chunk_row.addWidget(self._chunk_label)
        form_layout.addRow("Inference VRAM Chunk Size:", chunk_row)

        layout.addWidget(form)

        # Action Buttons
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(12)

        self._save_btn = QPushButton("Save Settings")
        self._save_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #a6e3a1;
                color: #11111b;
                font-weight: bold;
                border-radius: 6px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #94e2d5;
            }
            """
        )
        self._save_btn.clicked.connect(self._save_settings)

        self._reset_btn = QPushButton("Reset to Defaults")
        self._reset_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #313244;
                color: #cdd6f4;
                border-radius: 6px;
                padding: 10px 16px;
            }
            QPushButton:hover {
                background-color: #45475a;
            }
            """
        )
        self._reset_btn.clicked.connect(self._load_defaults)

        actions_layout.addWidget(self._save_btn)
        actions_layout.addWidget(self._reset_btn)
        actions_layout.addStretch()
        
        layout.addLayout(actions_layout)
        layout.addStretch()

        # Load values into widgets initially
        self._load_settings()

    def _load_settings(self) -> None:
        """Populate widgets with current saved configurations."""
        self._output_edit.setText(str(self._config.output_dir))
        self._models_edit.setText(str(self._config.models_dir))
        self._auto_update_checkbox.setChecked(self._config.auto_check_updates)
        self._ffmpeg_edit.setText(self._config.ffmpeg_path)
        
        # Convert samples back to seconds (default 352800 / 44100 = 8s)
        samples = self._config.melband_chunk_size
        seconds = max(2, min(16, int(round(samples / 44100))))
        self._chunk_slider.setValue(seconds)
        self._update_chunk_label(seconds)

    def _update_chunk_label(self, seconds: int) -> None:
        """Update VRAM description dynamically based on slider value."""
        samples = seconds * 44100
        
        if seconds <= 4:
            vram_tip = "Low VRAM (< 4 GB) — Safe fallback, slower speed."
        elif seconds <= 9:
            vram_tip = "Recommended (4–8 GB VRAM) — Ideal quality/speed balance."
        else:
            vram_tip = "High Performance (> 8 GB VRAM) — Fastest speed, high memory footprint."

        self._chunk_label.setText(
            f"{seconds} seconds ({samples:,} samples) — {vram_tip}"
        )

    def _save_settings(self) -> None:
        """Persist user entries to system config settings."""
        self._config.output_dir = Path(self._output_edit.text().strip())
        self._config.models_dir = Path(self._models_edit.text().strip())
        self._config.auto_check_updates = self._auto_update_checkbox.isChecked()
        self._config.ffmpeg_path = self._ffmpeg_edit.text().strip()
        
        seconds = self._chunk_slider.value()
        self._config.melband_chunk_size = seconds * 44100
        
        log.info("Settings saved persistently.")

    def _load_defaults(self) -> None:
        """Reset forms to standard built-in defaults."""
        default_out = outputs_dir()
        default_models = models_dir()
        
        self._output_edit.setText(str(default_out))
        self._models_edit.setText(str(default_models))
        self._auto_update_checkbox.setChecked(True)
        self._ffmpeg_edit.setText("ffmpeg")
        self._chunk_slider.setValue(8)  # 8 seconds
        self._update_chunk_label(8)
        
        log.info("Settings fields reset to defaults.")

    # ------------------------------------------------------------------
    # Browsers
    # ------------------------------------------------------------------

    def _browse_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Output Directory", self._output_edit.text())
        if path:
            self._output_edit.setText(path)

    def _browse_models(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select AI Models Directory", self._models_edit.text())
        if path:
            self._models_edit.setText(path)

    def _browse_ffmpeg(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select FFmpeg Binary", self._ffmpeg_edit.text())
        if path:
            self._ffmpeg_edit.setText(path)
