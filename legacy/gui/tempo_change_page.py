"""Tempo Change Page UI."""

import logging
from pathlib import Path

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.processor_registry import ProcessorRegistry
from src.gui.widgets.drop_zone import DropZone
from src.gui.widgets.log_panel import LogPanel
from src.gui.widgets.progress_panel import ProgressPanel
from src.utils.config import AppConfig
from src.workers.processor_worker import ProcessorWorker

log = logging.getLogger("sound_processor.gui.tempo_change_page")


from src.gui.watermarked_page import WatermarkedPage

class TempoChangePage(WatermarkedPage):
    """Page for configuring and running batch tempo change operations."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = AppConfig()
        self._files: list[Path] = []
        self._worker: ProcessorWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(24)

        # Header
        header = QLabel("Tempo Change")
        header.setStyleSheet("font-size: 24px; font-weight: bold; color: #cdd6f4;")
        layout.addWidget(header)

        # DropZone
        self._drop_zone = DropZone()
        self._drop_zone.setText("🎵 Drop audio file or folder here")
        self._drop_zone.filesDropped.connect(self._handle_files_input)
        layout.addWidget(self._drop_zone)

        # Main content area
        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        # Left Column: Configuration & Actions
        left_layout = QVBoxLayout()
        left_layout.setSpacing(12)

        config_frame = QFrame()
        config_frame.setObjectName("ConfigFrame")
        config_frame.setStyleSheet(
            "#ConfigFrame { background-color: #1e1e2e; border: 1px solid #313244; border-radius: 6px; padding: 12px; }"
        )
        config_layout = QVBoxLayout(config_frame)

        # Mode Selection
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Mode:"))
        
        self._mode_group = QButtonGroup(self)
        self._bpm_mode_rb = QRadioButton("BPM")
        self._percent_mode_rb = QRadioButton("Percentage")
        self._bpm_mode_rb.setChecked(True)
        
        self._mode_group.addButton(self._bpm_mode_rb)
        self._mode_group.addButton(self._percent_mode_rb)
        
        mode_layout.addWidget(self._bpm_mode_rb)
        mode_layout.addWidget(self._percent_mode_rb)
        mode_layout.addStretch()
        config_layout.addLayout(mode_layout)

        # Stack for the two mode forms
        self._mode_stack = QStackedWidget()
        
        # BPM Mode Form
        bpm_widget = QWidget()
        bpm_layout = QFormLayout(bpm_widget)
        self._source_bpm_edit = QLineEdit()
        self._source_bpm_edit.setPlaceholderText("e.g. 140")
        self._target_bpm_edit = QLineEdit()
        self._target_bpm_edit.setPlaceholderText("e.g. 128")
        self._source_bpm_edit.textChanged.connect(self._update_bpm_calculations)
        self._target_bpm_edit.textChanged.connect(self._update_bpm_calculations)
        
        self._bpm_rate_label = QLabel("--")
        self._bpm_rate_label.setStyleSheet("color: #a6e3a1; font-weight: bold;")
        
        bpm_layout.addRow("Source BPM:", self._source_bpm_edit)
        bpm_layout.addRow("Target BPM:", self._target_bpm_edit)
        bpm_layout.addRow("Rate:", self._bpm_rate_label)
        
        # Percentage Mode Form
        percent_widget = QWidget()
        percent_layout = QFormLayout(percent_widget)
        self._percent_change_edit = QLineEdit()
        self._percent_change_edit.setPlaceholderText("e.g. -8.6")
        self._percent_change_edit.textChanged.connect(self._update_percent_calculations)
        
        self._percent_rate_label = QLabel("--")
        self._percent_rate_label.setStyleSheet("color: #a6e3a1; font-weight: bold;")
        
        percent_layout.addRow("Change (%):", self._percent_change_edit)
        percent_layout.addRow("Rate:", self._percent_rate_label)
        
        self._mode_stack.addWidget(bpm_widget)
        self._mode_stack.addWidget(percent_widget)
        
        config_layout.addWidget(self._mode_stack)

        self._bpm_mode_rb.toggled.connect(
            lambda checked: self._mode_stack.setCurrentIndex(0) if checked else None
        )
        self._percent_mode_rb.toggled.connect(
            lambda checked: self._mode_stack.setCurrentIndex(1) if checked else None
        )

        # Output Selection
        out_layout = QHBoxLayout()
        out_layout.addWidget(QLabel("Output:"))
        self._output_edit = QLineEdit(str(self._config.output_dir))
        self._output_edit.setReadOnly(True)
        out_layout.addWidget(self._output_edit)
        
        out_btn = QPushButton("Change Folder")
        out_btn.clicked.connect(self._select_output_dir)
        out_layout.addWidget(out_btn)
        config_layout.addLayout(out_layout)

        left_layout.addWidget(config_frame)

        # Actions
        actions_layout = QHBoxLayout()
        self._analyze_btn = QPushButton("Change Tempo")
        self._analyze_btn.setStyleSheet(
            "QPushButton { background-color: #89b4fa; color: #11111b; font-weight: bold; border-radius: 6px; padding: 10px 24px; }"
            "QPushButton:hover { background-color: #74c7ec; }"
        )
        self._analyze_btn.clicked.connect(self._start_analysis)
        actions_layout.addWidget(self._analyze_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.setStyleSheet(
            "QPushButton { background-color: #f38ba8; color: #11111b; font-weight: bold; border-radius: 6px; padding: 10px 16px; }"
            "QPushButton:hover { background-color: #eba0ac; }"
            "QPushButton:disabled { background-color: #313244; color: #585b70; }"
        )
        self._cancel_btn.clicked.connect(self._cancel_analysis)
        actions_layout.addWidget(self._cancel_btn)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setStyleSheet(
            "QPushButton { background-color: #313244; color: #cdd6f4; border-radius: 4px; padding: 4px 8px; }"
            "QPushButton:hover { background-color: #45475a; }"
        )
        self._clear_btn.clicked.connect(self._clear_results)
        actions_layout.addWidget(self._clear_btn)

        left_layout.addLayout(actions_layout)
        left_layout.addStretch()
        content_layout.addLayout(left_layout, stretch=1)

        layout.addLayout(content_layout)

        # Progress and Log Panels
        self._progress_panel = ProgressPanel()
        layout.addWidget(self._progress_panel)

        self._log_panel = LogPanel()
        self._log_panel.setMinimumHeight(150)
        layout.addWidget(self._log_panel)

    def _update_bpm_calculations(self) -> None:
        try:
            source = float(self._source_bpm_edit.text() or 0)
            target = float(self._target_bpm_edit.text() or 0)
            if source > 0:
                rate = target / source
                pct = (rate - 1.0) * 100
                self._bpm_rate_label.setText(f"{rate:.3f}x ({pct:+.1f}%)")
            else:
                self._bpm_rate_label.setText("--")
        except ValueError:
            self._bpm_rate_label.setText("--")

    def _update_percent_calculations(self) -> None:
        try:
            pct = float(self._percent_change_edit.text() or 0)
            rate = 1.0 + (pct / 100.0)
            self._percent_rate_label.setText(f"{rate:.3f}x")
        except ValueError:
            self._percent_rate_label.setText("--")

    def _handle_files_input(self, paths: list[Path]) -> None:
        for p in paths:
            if p.is_dir():
                for ext in [".wav", ".mp3", ".flac", ".ogg", ".m4a"]:
                    for f in p.rglob(f"*{ext}"):
                        if f not in self._files:
                            self._files.append(f)
            elif p.is_file() and p not in self._files:
                self._files.append(p)
                
        if self._files:
            self._log_panel.append_log(f"Added {len(self._files)} file(s). Ready to process.")

    def _clear_results(self) -> None:
        self._files.clear()
        self._source_bpm_edit.clear()
        self._target_bpm_edit.clear()
        self._percent_change_edit.clear()
        self._bpm_rate_label.setText("--")
        self._percent_rate_label.setText("--")
        self._log_panel.clear_logs()

    def _select_output_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Output Directory", str(self._config.output_dir))
        if path:
            self._config.output_dir = Path(path)
            self._output_edit.setText(path)

    def _start_analysis(self) -> None:
        if not self._files:
            self._log_panel.append_error("Please add files before processing.")
            return

        mode = "bpm" if self._bpm_mode_rb.isChecked() else "percentage"
        options = {"mode": mode}

        if mode == "bpm":
            try:
                source = float(self._source_bpm_edit.text())
                target = float(self._target_bpm_edit.text())
                if source <= 0:
                    raise ValueError("Source BPM must be greater than 0.")
                options["source_bpm"] = source
                options["target_bpm"] = target
            except ValueError as e:
                self._log_panel.append_error(f"Invalid BPM values: {e}")
                return
        else:
            try:
                pct = float(self._percent_change_edit.text())
                options["percent_change"] = pct
            except ValueError as e:
                self._log_panel.append_error(f"Invalid percentage value: {e}")
                return

        self._set_ui_enabled(False)
        self._progress_panel.start_job(f"Processing {len(self._files)} track(s)...")
        self._log_panel.clear_logs()

        processor = ProcessorRegistry.get_processor("tempo_changer")
        self._worker = ProcessorWorker(
            processor, 
            self._files.copy(), 
            self._config.output_dir, 
            options
        )
        
        self._worker.signals.progress.connect(self._progress_panel.set_progress)
        self._worker.signals.log.connect(self._log_panel.append_log)
        self._worker.signals.error.connect(self._log_panel.append_error)
        self._worker.signals.finished.connect(self._on_analysis_finished)
        self._worker.finished.connect(self._cleanup_worker)
        
        self._worker.start()

    def _cancel_analysis(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self._cancel_btn.setEnabled(False)
            self._log_panel.append_log("Cancellation requested...")

    def _on_analysis_finished(self, results: dict) -> None:
        was_cancelled = (
            self._worker is not None and self._worker._cancel_flag.is_set()
        )
        self._set_ui_enabled(True)
        
        if not was_cancelled and results:
            self._progress_panel.finish_job(True, "Tempo change complete!")
        elif was_cancelled:
            self._progress_panel.finish_job(False, "Cancelled.")
        else:
            self._progress_panel.finish_job(False, "Failed to process files.")

    def _cleanup_worker(self) -> None:
        self._worker = None

    def _set_ui_enabled(self, enabled: bool) -> None:
        self._drop_zone.setEnabled(enabled)
        self._bpm_mode_rb.setEnabled(enabled)
        self._percent_mode_rb.setEnabled(enabled)
        self._source_bpm_edit.setEnabled(enabled)
        self._target_bpm_edit.setEnabled(enabled)
        self._percent_change_edit.setEnabled(enabled)
        self._analyze_btn.setEnabled(enabled)
        self._clear_btn.setEnabled(enabled)
        self._cancel_btn.setEnabled(not enabled)
