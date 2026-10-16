"""Audio Restoration Page UI."""

from __future__ import annotations

import logging
from pathlib import Path

from qtpy.QtCore import Qt, QUrl
from qtpy.QtGui import QDesktopServices
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QFormLayout,
    QWidget,
)

from src.core.processor_registry import ProcessorRegistry
from src.core.processors.restoration_processor import RECORDING_PROFILES
from src.gui.watermarked_page import WatermarkedPage
from src.gui.widgets import DropZone, LogPanel, ProgressPanel
from src.utils import AppConfig
from src.workers.processor_worker import ProcessorWorker

log = logging.getLogger("sound_processor.gui.restoration_page")

ACCENT = "#f2cdcd"  # Flamingo


class RestorationPage(WatermarkedPage):
    """UI page for multi-stage audio restoration of damaged and archival audio."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = AppConfig()
        self._files: list[Path] = []
        self._worker: ProcessorWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Title
        title = QLabel("Audio Restoration")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #cdd6f4;")
        layout.addWidget(title)

        desc = QLabel("Comprehensive multi-stage repair suite targeting vinyl crackle, digital dropouts, clipped peaks, and tape hiss.")
        desc.setStyleSheet("color: #a6adc8; font-size: 13px;")
        layout.addWidget(desc)

        # DropZone
        self._drop_zone = DropZone()
        self._drop_zone.setText("🔬 Drop damaged, vinyl, or tape audio files here")
        self._drop_zone.filesDropped.connect(self._handle_files_input)
        layout.addWidget(self._drop_zone)

        # Main horizontal layout
        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        # Left Column: Settings
        left_layout = QVBoxLayout()
        left_layout.setSpacing(16)

        settings_frame = QFrame()
        settings_frame.setObjectName("SettingsFrame")
        settings_frame.setStyleSheet(
            "#SettingsFrame { background-color: #1e1e2e; border: 1px solid #313244; border-radius: 6px; padding: 14px; }"
        )
        settings_vbox = QVBoxLayout(settings_frame)
        settings_vbox.setSpacing(12)

        stitle = QLabel("Restoration Pipeline & Profiles")
        stitle.setStyleSheet("color: #a6adc8; font-weight: bold; font-size: 13px;")
        settings_vbox.addWidget(stitle)

        form_layout = QFormLayout()
        form_layout.setSpacing(12)

        # Profile Combo
        self._profile_combo = QComboBox()
        self._profile_combo.addItems([
            "Digital (Dropouts & Clipping)",
            "Tape (Hiss & Dropouts)",
            "Vinyl (Crackle & Hiss)",
            "Broadcast (Glitch & Hiss)",
            "Custom (Manual Selection)",
        ])
        self._profile_combo.setStyleSheet(
            "QComboBox { background-color: #313244; color: #cdd6f4; border: 1px solid #45475a; border-radius: 4px; padding: 6px; }"
        )
        self._profile_combo.currentIndexChanged.connect(self._on_profile_changed)
        form_layout.addRow("Medium Profile:", self._profile_combo)

        # Global Strength Slider
        strength_layout = QHBoxLayout()
        self._strength_slider = QSlider(Qt.Orientation.Horizontal)
        self._strength_slider.setRange(10, 100)
        self._strength_slider.setValue(50)
        self._strength_slider.setStyleSheet(f"QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 2px; }}")
        self._strength_label = QLabel("50%")
        self._strength_label.setStyleSheet("color: #cdd6f4; font-weight: bold; min-width: 40px;")
        self._strength_slider.valueChanged.connect(lambda v: self._strength_label.setText(f"{v}%"))
        strength_layout.addWidget(self._strength_slider)
        strength_layout.addWidget(self._strength_label)
        form_layout.addRow("Restoration Strength:", strength_layout)

        # Artifact Selection Checkboxes
        artifacts_widget = QWidget()
        artifacts_grid = QGridLayout(artifacts_widget)
        artifacts_grid.setContentsMargins(0, 0, 0, 0)
        artifacts_grid.setSpacing(8)

        self._crackle_check = QCheckBox("Vinyl Crackle / De-click")
        self._dropout_check = QCheckBox("Digital Dropout Inpainting")
        self._clipping_check = QCheckBox("Harmonic Distortion / De-clip")
        self._hiss_check = QCheckBox("Tape Hiss / Broadband Noise")
        self._wow_check = QCheckBox("Wow & Flutter (Coming Soon)")
        self._wow_check.setEnabled(False)
        self._wow_check.setToolTip("Tape pitch stabilization is planned for a future release.")

        for cb in (self._crackle_check, self._dropout_check, self._clipping_check, self._hiss_check, self._wow_check):
            cb.setStyleSheet("color: #cdd6f4; font-size: 12px;")

        artifacts_grid.addWidget(self._crackle_check, 0, 0)
        artifacts_grid.addWidget(self._dropout_check, 0, 1)
        artifacts_grid.addWidget(self._clipping_check, 1, 0)
        artifacts_grid.addWidget(self._hiss_check, 1, 1)
        artifacts_grid.addWidget(self._wow_check, 2, 0, 1, 2)

        form_layout.addRow("Target Artifacts:", artifacts_widget)

        # Preserve Transients Checkbox
        self._transients_check = QCheckBox("Protect Musical Transients")
        self._transients_check.setChecked(True)
        self._transients_check.setStyleSheet("color: #cdd6f4; font-size: 13px;")
        self._transients_check.setToolTip("Prevents drum attacks and vocal consonants from being softened.")
        form_layout.addRow("", self._transients_check)

        settings_vbox.addLayout(form_layout)
        left_layout.addWidget(settings_frame)

        # Set initial checkboxes for default profile (digital)
        self._apply_profile_checkboxes("digital")

        # Action Buttons
        btn_layout = QHBoxLayout()
        self._process_btn = QPushButton("Restore Audio")
        self._process_btn.setStyleSheet(
            f"QPushButton {{ background-color: {ACCENT}; color: #11111b; font-weight: bold; font-size: 14px; border-radius: 6px; padding: 10px 20px; }}"
            f"QPushButton:hover {{ background-color: #eba0ac; }}"
            f"QPushButton:disabled {{ background-color: #45475a; color: #6c7086; }}"
        )
        self._process_btn.clicked.connect(self._start_processing)
        self._process_btn.setEnabled(False)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setStyleSheet(
            "QPushButton { background-color: #f38ba8; color: #11111b; font-weight: bold; border-radius: 6px; padding: 10px 16px; }"
            "QPushButton:hover { background-color: #eba0ac; }"
        )
        self._cancel_btn.clicked.connect(self._cancel_processing)
        self._cancel_btn.setVisible(False)

        self._open_btn = QPushButton("Open Output Folder")
        self._open_btn.setStyleSheet(
            "QPushButton { background-color: #313244; color: #cdd6f4; border: 1px solid #45475a; border-radius: 6px; padding: 10px 16px; }"
            "QPushButton:hover { background-color: #45475a; }"
        )
        self._open_btn.clicked.connect(self._open_output_dir)

        btn_layout.addWidget(self._process_btn)
        btn_layout.addWidget(self._cancel_btn)
        btn_layout.addWidget(self._open_btn)
        left_layout.addLayout(btn_layout)
        left_layout.addStretch()

        content_layout.addLayout(left_layout, stretch=1)

        # Right Column: Progress & Console
        right_layout = QVBoxLayout()
        right_layout.setSpacing(12)

        self._progress_panel = ProgressPanel()
        right_layout.addWidget(self._progress_panel)

        self._log_panel = LogPanel()
        right_layout.addWidget(self._log_panel, stretch=1)

        content_layout.addLayout(right_layout, stretch=1)
        layout.addLayout(content_layout)

    def _apply_profile_checkboxes(self, profile: str) -> None:
        targets = RECORDING_PROFILES.get(profile, [])
        self._crackle_check.setChecked("vinyl_crackle" in targets or "digital_glitch" in targets)
        self._dropout_check.setChecked("dropout" in targets)
        self._clipping_check.setChecked("clipping" in targets)
        self._hiss_check.setChecked("tape_hiss" in targets)

    def _on_profile_changed(self, idx: int) -> None:
        key_map = ["digital", "tape", "vinyl", "broadcast", "custom"]
        key = key_map[idx]
        if key != "custom":
            self._apply_profile_checkboxes(key)

    def _handle_files_input(self, paths: list[Path]) -> None:
        self._files = [p for p in paths if p.is_file() and p.suffix.lower() in [".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aif", ".aiff"]]
        if not self._files:
            self._log_panel.append_log("No valid audio files selected.")
            self._process_btn.setEnabled(False)
            return

        self._process_btn.setEnabled(True)
        self._log_panel.append_log(f"Selected {len(self._files)} file(s) for Audio Restoration.")

    def _start_processing(self) -> None:
        if not self._files:
            return

        key_map = ["digital", "tape", "vinyl", "broadcast", "custom"]
        rec_type = key_map[self._profile_combo.currentIndex()]

        active_artifacts = []
        if self._crackle_check.isChecked():
            active_artifacts.extend(["vinyl_crackle", "digital_glitch"])
        if self._dropout_check.isChecked():
            active_artifacts.append("dropout")
        if self._clipping_check.isChecked():
            active_artifacts.append("clipping")
        if self._hiss_check.isChecked():
            active_artifacts.append("tape_hiss")

        options = {
            "recording_type": rec_type,
            "restoration_strength": self._strength_slider.value() / 100.0,
            "target_artifacts": active_artifacts,
            "preserve_transients": self._transients_check.isChecked(),
        }

        processor = ProcessorRegistry.get_processor("restoration")
        output_dir = Path(self._config.output_dir)

        self._worker = ProcessorWorker(
            processor=processor,
            input_paths=self._files,
            output_dir=output_dir,
            options=options,
        )

        self._worker.signals.progress.connect(self._progress_panel.set_progress)
        self._worker.signals.log.connect(self._log_panel.append_log)
        self._worker.signals.finished.connect(self._on_finished)

        self._process_btn.setEnabled(False)
        self._cancel_btn.setVisible(True)
        self._drop_zone.setEnabled(False)
        self._progress_panel.reset()

        self._worker.start()

    def _cancel_processing(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()

    def _on_finished(self, results: dict) -> None:
        self._process_btn.setEnabled(len(self._files) > 0)
        self._cancel_btn.setVisible(False)
        self._drop_zone.setEnabled(True)
        self._log_panel.append_log("Audio Restoration finished.")

    def _open_output_dir(self) -> None:
        out_dir = Path(self._config.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(out_dir)))
