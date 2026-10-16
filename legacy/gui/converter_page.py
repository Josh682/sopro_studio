"""Audio format converter page with batch loop worker execution."""

from __future__ import annotations

import logging
from pathlib import Path

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.processor_registry import ProcessorRegistry
from src.gui.widgets import DropZone, LogPanel, ProgressPanel
from src.gui.watermarked_page import WatermarkedPage
from src.utils import AppConfig
from src.workers import ProcessorWorker

log = logging.getLogger("sound_processor.gui.converter_page")


class ConverterPage(WatermarkedPage):
    """UI page for format translation, configuration, and background conversion."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = AppConfig()
        self._files: list[Path] = []
        self._worker: ProcessorWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Title
        title = QLabel("Audio Format Converter")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #cdd6f4;")
        layout.addWidget(title)

        # 1. DropZone
        self._drop_zone = DropZone()
        self._drop_zone.filesDropped.connect(self._handle_files_input)
        layout.addWidget(self._drop_zone)

        # 2. File list and options columns
        middle_layout = QHBoxLayout()
        middle_layout.setSpacing(16)

        # File List Column
        file_list_widget = QWidget()
        file_list_layout = QVBoxLayout(file_list_widget)
        file_list_layout.setContentsMargins(0, 0, 0, 0)
        file_list_layout.setSpacing(6)

        file_list_header = QHBoxLayout()
        file_list_header.addWidget(QLabel("Selected Files:"))
        file_list_header.addStretch()
        self._clear_btn = QPushButton("Clear Selection")
        self._clear_btn.setStyleSheet(
            "QPushButton { background-color: #313244; color: #cdd6f4; border-radius: 4px; padding: 4px 8px; }"
            "QPushButton:hover { background-color: #45475a; }"
        )
        self._clear_btn.clicked.connect(self._clear_files)
        file_list_header.addWidget(self._clear_btn)
        file_list_layout.addLayout(file_list_header)

        self._list_widget = QListWidget()
        self._list_widget.setStyleSheet(
            "QListWidget { background-color: #1e1e2e; border: 1px solid #313244; border-radius: 6px; color: #cdd6f4; }"
        )
        file_list_layout.addWidget(self._list_widget)
        middle_layout.addWidget(file_list_widget, stretch=3)

        # Settings Options Column
        opts_widget = QWidget()
        opts_layout = QVBoxLayout(opts_widget)
        opts_layout.setContentsMargins(0, 0, 0, 0)
        opts_layout.setSpacing(12)

        opts_header = QLabel("Parameters")
        opts_header.setStyleSheet("font-weight: bold; color: #cdd6f4;")
        opts_layout.addWidget(opts_header)

        form_frame = QFrame()
        form_frame.setStyleSheet("QFrame { background-color: #181825; border: 1px solid #313244; border-radius: 6px; }")
        form_layout = QFormLayout(form_frame)
        form_layout.setContentsMargins(12, 12, 12, 12)
        form_layout.setSpacing(10)

        # Output format selector
        self._format_combo = QComboBox()
        self._format_combo.addItems(["WAV", "MP3", "FLAC"])
        self._format_combo.currentTextChanged.connect(self._toggle_format_settings)
        form_layout.addRow("Target Format:", self._format_combo)

        # Stacked settings per format type
        self._settings_stack = QStackedWidget()
        
        # WAV Settings Panel
        self._wav_panel = QWidget()
        wav_lay = QFormLayout(self._wav_panel)
        wav_lay.setContentsMargins(0, 0, 0, 0)
        self._bit_depth_combo = QComboBox()
        self._bit_depth_combo.addItems(["8-bit", "16-bit", "24-bit", "32-bit (float)"])
        self._bit_depth_combo.setCurrentIndex(1)  # Default 16-bit
        wav_lay.addRow("Bit Depth:", self._bit_depth_combo)
        self._settings_stack.addWidget(self._wav_panel)

        # MP3 Settings Panel
        self._mp3_panel = QWidget()
        mp3_lay = QFormLayout(self._mp3_panel)
        mp3_lay.setContentsMargins(0, 0, 0, 0)
        self._bitrate_combo = QComboBox()
        self._bitrate_combo.addItems(["128 kbps", "192 kbps", "256 kbps", "320 kbps"])
        self._bitrate_combo.setCurrentIndex(1)  # Default 192 kbps
        mp3_lay.addRow("Bitrate:", self._bitrate_combo)
        self._settings_stack.addWidget(self._mp3_panel)

        # FLAC Settings Panel
        self._flac_panel = QWidget()
        flac_lay = QFormLayout(self._flac_panel)
        flac_lay.setContentsMargins(0, 0, 0, 0)
        self._flac_slider = QSlider(Qt.Orientation.Horizontal)
        self._flac_slider.setRange(0, 8)
        self._flac_slider.setValue(5)
        self._flac_label = QLabel("5 (Medium)")
        self._flac_slider.valueChanged.connect(lambda val: self._flac_label.setText(f"{val}"))
        flac_lay.addRow("Compression Level:", self._flac_slider)
        flac_lay.addRow("", self._flac_label)
        self._settings_stack.addWidget(self._flac_panel)

        form_layout.addRow(self._settings_stack)

        # Peak normalization checkbox
        self._normalize_check = QCheckBox("Peak Normalise Audio")
        form_layout.addRow(self._normalize_check)

        # Target directory row
        self._output_edit = QLabel(str(self._config.output_dir))
        self._output_edit.setStyleSheet("color: #a6adc8; font-size: 11px;")
        self._output_edit.setWordWrap(True)
        self._output_btn = QPushButton("Change Folder")
        self._output_btn.setStyleSheet(
            "QPushButton { background-color: #313244; color: #cdd6f4; border-radius: 4px; padding: 4px 8px; }"
            "QPushButton:hover { background-color: #45475a; }"
        )
        self._output_btn.clicked.connect(self._change_folder)

        form_layout.addRow("Destination:", self._output_btn)
        form_layout.addRow("", self._output_edit)

        opts_layout.addWidget(form_frame)
        opts_layout.addStretch()
        middle_layout.addWidget(opts_widget, stretch=2)

        layout.addLayout(middle_layout)

        # 3. Actions Row
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(12)

        self._convert_btn = QPushButton("Start Conversion")
        self._convert_btn.setStyleSheet(
            "QPushButton { background-color: #a6e3a1; color: #11111b; font-weight: bold; border-radius: 6px; padding: 10px 24px; }"
            "QPushButton:hover { background-color: #94e2d5; }"
        )
        self._convert_btn.clicked.connect(self._start_conversion)
        actions_layout.addWidget(self._convert_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.setStyleSheet(
            "QPushButton { background-color: #f38ba8; color: #11111b; font-weight: bold; border-radius: 6px; padding: 10px 16px; }"
            "QPushButton:hover { background-color: #eba0ac; }"
            "QPushButton:disabled { background-color: #313244; color: #585b70; }"
        )
        self._cancel_btn.clicked.connect(self._cancel_conversion)
        actions_layout.addWidget(self._cancel_btn)

        layout.addLayout(actions_layout)

        # 4. Progress and Log Panels
        self._progress_panel = ProgressPanel()
        layout.addWidget(self._progress_panel)

        self._log_panel = LogPanel()
        self._log_panel.setMinimumHeight(120)
        layout.addWidget(self._log_panel)

    def _toggle_format_settings(self, fmt: str) -> None:
        """Switch current settings view based on target dropdown selection."""
        if fmt == "WAV":
            self._settings_stack.setCurrentWidget(self._wav_panel)
        elif fmt == "MP3":
            self._settings_stack.setCurrentWidget(self._mp3_panel)
        elif fmt == "FLAC":
            self._settings_stack.setCurrentWidget(self._flac_panel)

    def _change_folder(self) -> None:
        """Browse to update the export target directory."""
        path = QFileDialog.getExistingDirectory(self, "Select Output Folder", self._output_edit.text())
        if path:
            self._output_edit.setText(path)

    def _handle_files_input(self, paths: list[Path]) -> None:
        """Add unique dropped/browsed files to conversion queue list."""
        for p in paths:
            # Resolve directories recursively
            if p.is_dir():
                for ext in [".wav", ".mp3", ".flac", ".ogg", ".m4a"]:
                    for f in p.rglob(f"*{ext}"):
                        if f not in self._files:
                            self._files.append(f)
                            self._list_widget.addItem(f.name)
            elif p.is_file() and p not in self._files:
                self._files.append(p)
                self._list_widget.addItem(p.name)

    def _clear_files(self) -> None:
        """Wipe current conversion files list."""
        self._files.clear()
        self._list_widget.clear()

    def _start_conversion(self) -> None:
        """Instantiate background ConverterWorker thread."""
        if not self._files:
            self._log_panel.append_error("Please add files before converting.")
            return

        # Prepare parameters dictionary
        fmt = self._format_combo.currentText().lower()
        options = {"output_format": fmt, "normalize": self._normalize_check.isChecked()}

        if fmt == "wav":
            bit_depth_map = {"8-bit": 8, "16-bit": 16, "24-bit": 24, "32-bit (float)": 32}
            options["bit_depth"] = bit_depth_map.get(self._bit_depth_combo.currentText(), 16)
        elif fmt == "mp3":
            bitrate_map = {"128 kbps": 128, "192 kbps": 192, "256 kbps": 256, "320 kbps": 320}
            options["mp3_bitrate"] = bitrate_map.get(self._bitrate_combo.currentText(), 192)
        elif fmt == "flac":
            options["flac_compression"] = self._flac_slider.value()

        # Update controls
        self._set_ui_enabled(False)
        self._progress_panel.start_job(f"Converting {len(self._files)} file(s)...")
        self._log_panel.clear_logs()

        # Instantiate background worker
        output_dir = Path(self._output_edit.text())
        processor = ProcessorRegistry.get_processor("format_converter")
        self._worker = ProcessorWorker(processor, self._files, output_dir, options)
        
        # Connect signals
        self._worker.signals.progress.connect(self._progress_panel.set_progress)
        self._worker.signals.log.connect(self._log_panel.append_log)
        self._worker.signals.error.connect(self._log_panel.append_error)
        self._worker.signals.finished.connect(self._on_conversion_finished)
        # QThread.finished fires AFTER run() has fully returned — safe to delete
        self._worker.finished.connect(self._cleanup_worker)
        
        self._worker.start()

    def _cancel_conversion(self) -> None:
        """Command active background thread to cancel execution."""
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self._cancel_btn.setEnabled(False)
            self._log_panel.append_log("Cancellation requested...")

    def _on_conversion_finished(self, results: dict) -> None:
        """Reset UI state. Called while run() is still on the stack — do NOT delete worker here."""
        was_cancelled = (
            self._worker is not None and self._worker._cancel_flag.is_set()
        )
        self._set_ui_enabled(True)
        self._progress_panel.finish_job(
            success=not was_cancelled,
            message="Conversion complete!" if not was_cancelled else "Cancelled."
        )

    def _cleanup_worker(self) -> None:
        """Delete worker only after QThread.finished (i.e., after run() has fully returned)."""
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None

    def _set_ui_enabled(self, enabled: bool) -> None:
        """Toggle active widgets layout during execution states."""
        self._drop_zone.setAcceptDrops(enabled)
        self._drop_zone.setEnabled(enabled)
        self._format_combo.setEnabled(enabled)
        self._bit_depth_combo.setEnabled(enabled)
        self._bitrate_combo.setEnabled(enabled)
        self._flac_slider.setEnabled(enabled)
        self._normalize_check.setEnabled(enabled)
        self._output_btn.setEnabled(enabled)
        self._clear_btn.setEnabled(enabled)
        self._convert_btn.setEnabled(enabled)
        
        self._cancel_btn.setEnabled(not enabled)
