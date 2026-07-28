"""Track Combiner page with custom track list and gain control."""

from __future__ import annotations

import logging
from pathlib import Path

from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.processor_registry import ProcessorRegistry
from src.gui.widgets import DropZone, LogPanel, ProgressPanel
from src.utils import AppConfig
from src.workers import ProcessorWorker

log = logging.getLogger("sound_processor.gui.combiner_page")


from src.gui.watermarked_page import WatermarkedPage

class TrackItemWidget(QWidget):
    """Custom widget for a list item to adjust gain for a specific track."""
    
    gainChanged = Signal(float)

    def __init__(self, filepath: Path, parent: QWidget | None = None):
        super().__init__(parent)
        self.filepath = filepath
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        
        # Up/Down arrows could be added here if order mattered,
        # but since summing is commutative, order doesn't affect audio.
        # We'll just show the filename.
        name_label = QLabel(filepath.name)
        name_label.setStyleSheet("color: #cdd6f4;")
        layout.addWidget(name_label, stretch=1)
        
        # Gain slider
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 200)  # 0.0 to 2.0
        self._slider.setValue(100)
        self._slider.setFixedWidth(150)
        layout.addWidget(self._slider)
        
        # Gain label
        self._val_label = QLabel("1.00x")
        self._val_label.setFixedWidth(40)
        self._val_label.setStyleSheet("color: #a6adc8; font-size: 11px;")
        layout.addWidget(self._val_label)
        
        self._slider.valueChanged.connect(self._on_slider_changed)

    def _on_slider_changed(self, val: int) -> None:
        gain = val / 100.0
        self._val_label.setText(f"{gain:.2f}x")
        self.gainChanged.emit(gain)
        
    def get_gain(self) -> float:
        return self._slider.value() / 100.0


class CombinerPage(WatermarkedPage):
    """UI page for combining tracks."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = AppConfig()
        self._files: list[Path] = []
        self._worker: ProcessorWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Title
        title = QLabel("Track Combiner")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #cdd6f4;")
        layout.addWidget(title)

        # 1. DropZone
        self._drop_zone = DropZone()
        self._drop_zone.setText("🎵 Drop stems or tracks here")
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
        file_list_header.addWidget(QLabel("Track List:"))
        file_list_header.addStretch()
        self._clear_btn = QPushButton("Clear")
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
            "QListWidget::item:selected { background-color: transparent; }"  # disable selection color
        )
        file_list_layout.addWidget(self._list_widget)
        middle_layout.addWidget(file_list_widget, stretch=3)

        # Settings Options Column
        opts_widget = QWidget()
        opts_layout = QVBoxLayout(opts_widget)
        opts_layout.setContentsMargins(0, 0, 0, 0)
        opts_layout.setSpacing(12)

        opts_header = QLabel("Settings")
        opts_header.setStyleSheet("font-weight: bold; color: #cdd6f4;")
        opts_layout.addWidget(opts_header)

        form_frame = QFrame()
        form_frame.setStyleSheet("QFrame { background-color: #181825; border: 1px solid #313244; border-radius: 6px; }")
        form_layout = QFormLayout(form_frame)
        form_layout.setContentsMargins(12, 12, 12, 12)
        form_layout.setSpacing(10)

        # Output filename
        self._filename_edit = QLineEdit("mix")
        self._filename_edit.setStyleSheet(
            "QLineEdit { background-color: #1e1e2e; border: 1px solid #313244; color: #cdd6f4; border-radius: 4px; padding: 4px; }"
        )
        form_layout.addRow("Filename:", self._filename_edit)

        # Output format selector
        self._format_combo = QComboBox()
        self._format_combo.addItems(["WAV", "FLAC"])
        self._format_combo.currentTextChanged.connect(self._toggle_format_settings)
        form_layout.addRow("Format:", self._format_combo)

        # Stacked settings per format type
        self._settings_stack = QStackedWidget()
        
        # WAV Settings Panel
        self._wav_panel = QWidget()
        wav_lay = QFormLayout(self._wav_panel)
        wav_lay.setContentsMargins(0, 0, 0, 0)
        self._bit_depth_combo = QComboBox()
        self._bit_depth_combo.addItems(["16-bit", "24-bit", "32-bit (float)"])
        self._bit_depth_combo.setCurrentIndex(1)  # Default 24-bit
        wav_lay.addRow("Bit Depth:", self._bit_depth_combo)
        self._settings_stack.addWidget(self._wav_panel)

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

        # Mix options
        self._prevent_clip_check = QCheckBox("Prevent Clipping")
        self._prevent_clip_check.setChecked(True)
        form_layout.addRow(self._prevent_clip_check)
        
        self._normalize_check = QCheckBox("Peak Normalise Output")
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

        self._combine_btn = QPushButton("Combine Tracks")
        self._combine_btn.setStyleSheet(
            "QPushButton { background-color: #a6e3a1; color: #11111b; font-weight: bold; border-radius: 6px; padding: 10px 24px; }"
            "QPushButton:hover { background-color: #94e2d5; }"
        )
        self._combine_btn.clicked.connect(self._start_combination)
        actions_layout.addWidget(self._combine_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.setStyleSheet(
            "QPushButton { background-color: #f38ba8; color: #11111b; font-weight: bold; border-radius: 6px; padding: 10px 16px; }"
            "QPushButton:hover { background-color: #eba0ac; }"
            "QPushButton:disabled { background-color: #313244; color: #585b70; }"
        )
        self._cancel_btn.clicked.connect(self._cancel_combination)
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
        elif fmt == "FLAC":
            self._settings_stack.setCurrentWidget(self._flac_panel)

    def _change_folder(self) -> None:
        """Browse to update the export target directory."""
        path = QFileDialog.getExistingDirectory(self, "Select Output Folder", self._output_edit.text())
        if path:
            self._output_edit.setText(path)

    def _handle_files_input(self, paths: list[Path]) -> None:
        """Add unique dropped/browsed files to combiner list."""
        for p in paths:
            if p.is_dir():
                for ext in [".wav", ".mp3", ".flac", ".ogg", ".m4a"]:
                    for f in p.rglob(f"*{ext}"):
                        if f not in self._files:
                            self._add_file(f)
            elif p.is_file() and p not in self._files:
                self._add_file(p)

    def _add_file(self, filepath: Path) -> None:
        self._files.append(filepath)
        
        item = QListWidgetItem(self._list_widget)
        widget = TrackItemWidget(filepath)
        item.setSizeHint(widget.sizeHint())
        
        self._list_widget.addItem(item)
        self._list_widget.setItemWidget(item, widget)

    def _clear_files(self) -> None:
        """Wipe current conversion files list."""
        self._files.clear()
        self._list_widget.clear()

    def _start_combination(self) -> None:
        """Instantiate background ProcessorWorker thread."""
        if not self._files:
            self._log_panel.append_error("Please add files before combining.")
            return

        # Prepare options dictionary
        fmt = self._format_combo.currentText().lower()
        options = {
            "output_format": fmt, 
            "output_filename": self._filename_edit.text() or "mix",
            "prevent_clipping": self._prevent_clip_check.isChecked(),
            "normalize_output": self._normalize_check.isChecked(),
        }

        if fmt == "wav":
            bit_depth_map = {"16-bit": 16, "24-bit": 24, "32-bit (float)": 32}
            options["bit_depth"] = bit_depth_map.get(self._bit_depth_combo.currentText(), 24)
        elif fmt == "flac":
            options["flac_compression"] = self._flac_slider.value()
            
        # Collect gain_per_track
        gain_per_track = {}
        for i in range(self._list_widget.count()):
            item = self._list_widget.item(i)
            widget = self._list_widget.itemWidget(item)
            if isinstance(widget, TrackItemWidget):
                gain_per_track[widget.filepath.name] = widget.get_gain()
        
        options["gain_per_track"] = gain_per_track

        # Update controls
        self._set_ui_enabled(False)
        self._progress_panel.start_job(f"Combining {len(self._files)} track(s)...")
        self._log_panel.clear_logs()

        # Instantiate background worker
        output_dir = Path(self._output_edit.text())
        processor = ProcessorRegistry.get_processor("track_combiner")
        self._worker = ProcessorWorker(processor, self._files, output_dir, options)
        
        # Connect signals
        self._worker.signals.progress.connect(self._progress_panel.set_progress)
        self._worker.signals.log.connect(self._log_panel.append_log)
        self._worker.signals.error.connect(self._log_panel.append_error)
        self._worker.signals.finished.connect(self._on_combination_finished)
        self._worker.finished.connect(self._cleanup_worker)
        
        self._worker.start()

    def _cancel_combination(self) -> None:
        """Command active background thread to cancel execution."""
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self._cancel_btn.setEnabled(False)
            self._log_panel.append_log("Cancellation requested...")

    def _on_combination_finished(self, results: dict) -> None:
        """Reset UI state."""
        was_cancelled = (
            self._worker is not None and self._worker._cancel_flag.is_set()
        )
        self._set_ui_enabled(True)
        self._progress_panel.finish_job(
            success=not was_cancelled,
            message="Combination complete!" if not was_cancelled else "Cancelled."
        )

    def _cleanup_worker(self) -> None:
        """Delete worker only after QThread.finished."""
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None

    def _set_ui_enabled(self, enabled: bool) -> None:
        """Toggle active widgets layout during execution states."""
        self._drop_zone.setAcceptDrops(enabled)
        self._drop_zone.setEnabled(enabled)
        self._format_combo.setEnabled(enabled)
        self._bit_depth_combo.setEnabled(enabled)
        self._filename_edit.setEnabled(enabled)
        self._flac_slider.setEnabled(enabled)
        self._prevent_clip_check.setEnabled(enabled)
        self._normalize_check.setEnabled(enabled)
        self._output_btn.setEnabled(enabled)
        self._clear_btn.setEnabled(enabled)
        self._combine_btn.setEnabled(enabled)
        
        # also disable sliders in the list
        for i in range(self._list_widget.count()):
            item = self._list_widget.item(i)
            widget = self._list_widget.itemWidget(item)
            if isinstance(widget, TrackItemWidget):
                widget.setEnabled(enabled)
        
        self._cancel_btn.setEnabled(not enabled)
