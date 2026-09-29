"""AI Dereverb Page UI."""

from __future__ import annotations

import logging
from pathlib import Path

from qtpy.QtCore import Qt, QUrl
from qtpy.QtGui import QDesktopServices
from qtpy.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QFormLayout,
    QWidget,
)

from src.core.processor_registry import ProcessorRegistry
from src.gui.watermarked_page import WatermarkedPage
from src.gui.widgets import DropZone, LogPanel, ProgressPanel
from src.utils import AppConfig
from src.workers.processor_worker import ProcessorWorker

log = logging.getLogger("sound_processor.gui.dereverb_page")

ACCENT = "#b4befe"  # Lavender


class DereverbPage(WatermarkedPage):
    """UI page for AI Dereverberation and acoustic reflection removal."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = AppConfig()
        self._files: list[Path] = []
        self._worker: ProcessorWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Title
        title = QLabel("AI Dereverb")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #cdd6f4;")
        layout.addWidget(title)

        desc = QLabel("Suppress room reflections, early echoes, and long reverberant tails to recover a dry direct signal.")
        desc.setStyleSheet("color: #a6adc8; font-size: 13px;")
        layout.addWidget(desc)

        # DropZone
        self._drop_zone = DropZone()
        self._drop_zone.setText("🏠 Drop reverberant audio files or folder here")
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

        stitle = QLabel("Dereverb Parameters")
        stitle.setStyleSheet("color: #a6adc8; font-weight: bold; font-size: 13px;")
        settings_vbox.addWidget(stitle)

        form_layout = QFormLayout()
        form_layout.setSpacing(12)

        # Amount Radio Buttons
        amount_widget = QWidget()
        amount_layout = QHBoxLayout(amount_widget)
        amount_layout.setContentsMargins(0, 0, 0, 0)
        amount_layout.setSpacing(12)

        self._btn_group = QButtonGroup(self)
        self._subtle_radio = QRadioButton("Subtle")
        self._moderate_radio = QRadioButton("Moderate")
        self._aggressive_radio = QRadioButton("Aggressive")
        self._moderate_radio.setChecked(True)

        for rb in (self._subtle_radio, self._moderate_radio, self._aggressive_radio):
            rb.setStyleSheet("color: #cdd6f4; font-size: 13px;")
            self._btn_group.addButton(rb)
            amount_layout.addWidget(rb)

        form_layout.addRow("Suppression Depth:", amount_widget)

        # Preserve Warmth Checkbox
        self._preserve_warmth_check = QCheckBox("Preserve Low-Mid Body (<350Hz)")
        self._preserve_warmth_check.setChecked(True)
        self._preserve_warmth_check.setStyleSheet("color: #cdd6f4; font-size: 13px;")
        self._preserve_warmth_check.setToolTip("Retains natural warmth and fundamental vocal harmonics so audio does not sound thin.")
        form_layout.addRow("", self._preserve_warmth_check)

        settings_vbox.addLayout(form_layout)
        left_layout.addWidget(settings_frame)

        # Action Buttons
        btn_layout = QHBoxLayout()
        self._process_btn = QPushButton("Remove Reverb")
        self._process_btn.setStyleSheet(
            f"QPushButton {{ background-color: {ACCENT}; color: #11111b; font-weight: bold; font-size: 14px; border-radius: 6px; padding: 10px 20px; }}"
            f"QPushButton:hover {{ background-color: #cba6f7; }}"
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
        self._log_panel.append_log(f"Selected {len(self._files)} file(s) for AI Dereverb.")

    def _start_processing(self) -> None:
        if not self._files:
            return

        if self._subtle_radio.isChecked():
            amount = "subtle"
        elif self._aggressive_radio.isChecked():
            amount = "aggressive"
        else:
            amount = "moderate"

        preserve_warmth = self._preserve_warmth_check.isChecked()

        options = {
            "amount": amount,
            "preserve_warmth": preserve_warmth,
        }

        processor = ProcessorRegistry.get_processor("dereverb")
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
        self._log_panel.append_log("AI Dereverb finished.")

    def _open_output_dir(self) -> None:
        out_dir = Path(self._config.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(out_dir)))
