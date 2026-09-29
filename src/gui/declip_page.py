"""Declip Repair Page UI."""

from __future__ import annotations

import logging
from pathlib import Path

from qtpy.QtCore import Qt, QUrl
from qtpy.QtGui import QDesktopServices
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QFormLayout,
    QWidget,
)

from src.core.processor_registry import ProcessorRegistry
from src.gui.watermarked_page import WatermarkedPage
from src.gui.widgets import DropZone, LogPanel, ProgressPanel
from src.utils import AppConfig
from src.workers.processor_worker import ProcessorWorker

log = logging.getLogger("sound_processor.gui.declip_page")

ACCENT = "#cba6f7"  # Mauve


class DeclipPage(WatermarkedPage):
    """UI page for detecting and repairing digital audio clipping."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = AppConfig()
        self._files: list[Path] = []
        self._worker: ProcessorWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Title
        title = QLabel("Declip Repair")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #cdd6f4;")
        layout.addWidget(title)

        desc = QLabel("Restore clipped waveform peaks and eliminate harsh digital distortion using cubic spline and AR prediction.")
        desc.setStyleSheet("color: #a6adc8; font-size: 13px;")
        layout.addWidget(desc)

        # DropZone
        self._drop_zone = DropZone()
        self._drop_zone.setText("🔊 Drop clipped audio files or folder here")
        self._drop_zone.filesDropped.connect(self._handle_files_input)
        layout.addWidget(self._drop_zone)

        # Main horizontal layout: Settings on Left, Progress & Logs on Right
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

        stitle = QLabel("Repair Parameters")
        stitle.setStyleSheet("color: #a6adc8; font-weight: bold; font-size: 13px;")
        settings_vbox.addWidget(stitle)

        form_layout = QFormLayout()
        form_layout.setSpacing(12)

        # Algorithm Combo
        self._algo_combo = QComboBox()
        self._algo_combo.addItems(["Auto-Select", "Cubic Spline", "Autoregressive (AR)"])
        self._algo_combo.setStyleSheet(
            "QComboBox { background-color: #313244; color: #cdd6f4; border: 1px solid #45475a; border-radius: 4px; padding: 6px; }"
        )
        form_layout.addRow("Algorithm:", self._algo_combo)

        # Clipping Threshold
        self._threshold_spin = QDoubleSpinBox()
        self._threshold_spin.setRange(0.80, 1.00)
        self._threshold_spin.setDecimals(2)
        self._threshold_spin.setSingleStep(0.01)
        self._threshold_spin.setValue(0.99)
        self._threshold_spin.setStyleSheet(
            "background-color: #181825; color: #cdd6f4; border: 1px solid #313244; border-radius: 4px; padding: 6px;"
        )
        form_layout.addRow("Clipping Threshold:", self._threshold_spin)

        # Headroom gain
        self._headroom_check = QCheckBox("Apply -3dB headroom makeup gain")
        self._headroom_check.setChecked(True)
        self._headroom_check.setStyleSheet("color: #cdd6f4; font-size: 13px;")
        self._headroom_check.setToolTip("Reduces gain slightly to ensure reconstructed peaks do not exceed 0 dBFS.")
        form_layout.addRow("", self._headroom_check)

        settings_vbox.addLayout(form_layout)
        left_layout.addWidget(settings_frame)

        # Action Buttons
        btn_layout = QHBoxLayout()
        self._process_btn = QPushButton("Repair Clipped Audio")
        self._process_btn.setStyleSheet(
            f"QPushButton {{ background-color: {ACCENT}; color: #11111b; font-weight: bold; font-size: 14px; border-radius: 6px; padding: 10px 20px; }}"
            f"QPushButton:hover {{ background-color: #b4befe; }}"
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

    def _handle_files_input(self, paths: list[Path]) -> None:
        self._files = [p for p in paths if p.is_file() and p.suffix.lower() in [".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aif", ".aiff"]]
        if not self._files:
            self._log_panel.append_log("No valid audio files selected.")
            self._process_btn.setEnabled(False)
            return

        self._process_btn.setEnabled(True)
        self._log_panel.append_log(f"Selected {len(self._files)} file(s) for Declip Repair.")

    def _start_processing(self) -> None:
        if not self._files:
            return

        algo_map = {"Auto-Select": "auto", "Cubic Spline": "spline", "Autoregressive (AR)": "ar_model"}
        algo = algo_map.get(self._algo_combo.currentText(), "auto")
        threshold = self._threshold_spin.value()
        headroom = self._headroom_check.isChecked()

        options = {
            "algorithm": algo,
            "threshold": threshold,
            "auto_makeup_gain": headroom,
        }

        processor = ProcessorRegistry.get_processor("declip")
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
        self._log_panel.append_log("Declip repair finished.")

    def _open_output_dir(self) -> None:
        out_dir = Path(self._config.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(out_dir)))
