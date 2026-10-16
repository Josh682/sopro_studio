"""Voice Enhancement Page UI."""

from __future__ import annotations

import logging
from pathlib import Path

from qtpy.QtCore import Qt, QUrl
from qtpy.QtGui import QDesktopServices
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QFormLayout,
    QWidget,
)

from src.core.processor_registry import ProcessorRegistry
from src.core.processors.voice_enhancement_processor import PRESETS
from src.gui.watermarked_page import WatermarkedPage
from src.gui.widgets import DropZone, LogPanel, ProgressPanel
from src.utils import AppConfig
from src.workers.processor_worker import ProcessorWorker

log = logging.getLogger("sound_processor.gui.voice_enhancement_page")

ACCENT = "#f5c2e7"  # Pink


class VoiceEnhancementPage(WatermarkedPage):
    """UI page for voice clarity, presence lift, and de-essing."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = AppConfig()
        self._files: list[Path] = []
        self._worker: ProcessorWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Title
        title = QLabel("Voice Enhancement")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #cdd6f4;")
        layout.addWidget(title)

        desc = QLabel("Improve vocal clarity, reduce boxy lower-mid resonances (200-500Hz), tame harsh sibilance, and lift speech presence.")
        desc.setStyleSheet("color: #a6adc8; font-size: 13px;")
        layout.addWidget(desc)

        # DropZone
        self._drop_zone = DropZone()
        self._drop_zone.setText("🎙️ Drop dialogue, voiceover, or vocal recordings here")
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

        stitle = QLabel("Vocal Profile & Processing")
        stitle.setStyleSheet("color: #a6adc8; font-weight: bold; font-size: 13px;")
        settings_vbox.addWidget(stitle)

        form_layout = QFormLayout()
        form_layout.setSpacing(12)

        # Preset Combo
        self._preset_combo = QComboBox()
        self._preset_combo.addItems(["Podcast (Spoken Word)", "Voiceover (Smooth & Warm)", "Vocal Production (Musical)", "Custom"])
        self._preset_combo.setStyleSheet(
            "QComboBox { background-color: #313244; color: #cdd6f4; border: 1px solid #45475a; border-radius: 4px; padding: 6px; }"
        )
        self._preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        form_layout.addRow("Target Application:", self._preset_combo)

        # Clarity / Mud Reduction Slider
        clarity_layout = QHBoxLayout()
        self._clarity_slider = QSlider(Qt.Orientation.Horizontal)
        self._clarity_slider.setRange(0, 100)
        self._clarity_slider.setValue(70)
        self._clarity_slider.setStyleSheet(f"QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 2px; }}")
        self._clarity_label = QLabel("70%")
        self._clarity_label.setStyleSheet("color: #cdd6f4; font-weight: bold; min-width: 40px;")
        self._clarity_slider.valueChanged.connect(lambda v: self._clarity_label.setText(f"{v}%"))
        clarity_layout.addWidget(self._clarity_slider)
        clarity_layout.addWidget(self._clarity_label)
        form_layout.addRow("Mud Reduction (200-500Hz):", clarity_layout)

        # De-essing Slider
        deess_layout = QHBoxLayout()
        self._deess_slider = QSlider(Qt.Orientation.Horizontal)
        self._deess_slider.setRange(0, 100)
        self._deess_slider.setValue(40)
        self._deess_slider.setStyleSheet(f"QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 2px; }}")
        self._deess_label = QLabel("40%")
        self._deess_label.setStyleSheet("color: #cdd6f4; font-weight: bold; min-width: 40px;")
        self._deess_slider.valueChanged.connect(lambda v: self._deess_label.setText(f"{v}%"))
        deess_layout.addWidget(self._deess_slider)
        deess_layout.addWidget(self._deess_label)
        form_layout.addRow("De-essing (6.5-11kHz):", deess_layout)

        # Enhance Presence Checkbox
        self._presence_check = QCheckBox("Enhance Presence (2.5 - 4.5 kHz)")
        self._presence_check.setChecked(True)
        self._presence_check.setStyleSheet("color: #cdd6f4; font-size: 13px;")
        self._presence_check.setToolTip("Brings vocals forward in the mix for higher intelligibility.")
        form_layout.addRow("", self._presence_check)

        settings_vbox.addLayout(form_layout)
        left_layout.addWidget(settings_frame)

        # Action Buttons
        btn_layout = QHBoxLayout()
        self._process_btn = QPushButton("Enhance Voice")
        self._process_btn.setStyleSheet(
            f"QPushButton {{ background-color: {ACCENT}; color: #11111b; font-weight: bold; font-size: 14px; border-radius: 6px; padding: 10px 20px; }}"
            f"QPushButton:hover {{ background-color: #f2cdcd; }}"
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

    def _on_preset_changed(self, idx: int) -> None:
        key_map = ["podcast", "voiceover", "vocal", "custom"]
        key = key_map[idx]
        if key in PRESETS and key != "custom":
            p = PRESETS[key]
            self._clarity_slider.setValue(int(p["clarity_strength"] * 100))
            self._deess_slider.setValue(int(p["de_ess_strength"] * 100))
            self._presence_check.setChecked(p["enhance_presence"])

    def _handle_files_input(self, paths: list[Path]) -> None:
        self._files = [p for p in paths if p.is_file() and p.suffix.lower() in [".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aif", ".aiff"]]
        if not self._files:
            self._log_panel.append_log("No valid audio files selected.")
            self._process_btn.setEnabled(False)
            return

        self._process_btn.setEnabled(True)
        self._log_panel.append_log(f"Selected {len(self._files)} file(s) for Voice Enhancement.")

    def _start_processing(self) -> None:
        if not self._files:
            return

        key_map = ["podcast", "voiceover", "vocal", "custom"]
        target_use = key_map[self._preset_combo.currentIndex()]

        options = {
            "target_use": target_use,
            "clarity_strength": self._clarity_slider.value() / 100.0,
            "de_ess_strength": self._deess_slider.value() / 100.0,
            "enhance_presence": self._presence_check.isChecked(),
        }

        processor = ProcessorRegistry.get_processor("voice_enhancement")
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
        self._log_panel.append_log("Voice Enhancement finished.")

    def _open_output_dir(self) -> None:
        out_dir = Path(self._config.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(out_dir)))
