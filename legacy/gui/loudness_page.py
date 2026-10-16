"""Loudness Normalization Page UI."""

import logging
from pathlib import Path

from qtpy.QtCore import Qt, QUrl
from qtpy.QtGui import QDesktopServices
from qtpy.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QFormLayout,
    QWidget,
)

from src.audio.metadata import AudioInfo
from src.core.processor_registry import ProcessorRegistry
from src.gui.widgets import DropZone, LogPanel, ProgressPanel
from src.utils import AppConfig
from src.workers.analyzer_worker import AnalyzerWorker
from src.workers.processor_worker import ProcessorWorker
from src.gui.watermarked_page import WatermarkedPage

log = logging.getLogger("sound_processor.gui.loudness_page")

PRESETS = {
    "Spotify / YouTube": {"lufs": -14.0, "tp": -1.0, "lra": 11.0},
    "Apple Music": {"lufs": -16.0, "tp": -1.0, "lra": 11.0},
    "Broadcast (EBU R128)": {"lufs": -23.0, "tp": -1.0, "lra": 18.0},
    "Broadcast (ATSC A/85)": {"lufs": -24.0, "tp": -2.0, "lra": 18.0},
    "Podcast": {"lufs": -16.0, "tp": -1.5, "lra": 11.0},
    "CD Mastering": {"lufs": -9.0, "tp": -0.1, "lra": 9.0},
    "Custom": None,
}

class LoudnessPage(WatermarkedPage):
    """UI page for Loudness Normalization."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = AppConfig()
        self._files: list[Path] = []
        self._analyzer_worker: AnalyzerWorker | None = None
        self._processor_worker: ProcessorWorker | None = None
        
        self._measurements: dict[Path, AudioInfo] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Title
        title = QLabel("Loudness Normalization")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #cdd6f4;")
        layout.addWidget(title)

        # DropZone
        self._drop_zone = DropZone()
        self._drop_zone.setText("🔊 Drop audio file or folder to normalize")
        self._drop_zone.filesDropped.connect(self._handle_files_input)
        layout.addWidget(self._drop_zone)

        # Main content area
        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        # Left Column: Measurement & Settings
        left_layout = QVBoxLayout()
        left_layout.setSpacing(16)
        
        # --- Settings Frame ---
        settings_frame = QFrame()
        settings_frame.setObjectName("SettingsFrame")
        settings_frame.setStyleSheet(
            "#SettingsFrame { background-color: #1e1e2e; border: 1px solid #313244; border-radius: 6px; padding: 12px; }"
        )
        settings_layout = QVBoxLayout(settings_frame)
        
        stitle = QLabel("Target Settings")
        stitle.setStyleSheet("color: #a6adc8; font-weight: bold; font-size: 13px;")
        settings_layout.addWidget(stitle)
        
        form_layout = QFormLayout()
        form_layout.setSpacing(12)
        
        self._preset_combo = QComboBox()
        self._preset_combo.addItems(list(PRESETS.keys()))
        self._preset_combo.currentTextChanged.connect(self._on_preset_changed)
        self._preset_combo.setStyleSheet(
            "QComboBox { background-color: #313244; color: #cdd6f4; border: 1px solid #45475a; border-radius: 4px; padding: 4px; }"
        )
        form_layout.addRow("Preset:", self._preset_combo)
        
        self._lufs_spin = QDoubleSpinBox()
        self._lufs_spin.setRange(-40.0, 0.0)
        self._lufs_spin.setDecimals(1)
        self._lufs_spin.setSingleStep(0.5)
        self._lufs_spin.setSuffix(" LUFS")
        self._lufs_spin.setStyleSheet("background-color: #181825; color: #cdd6f4; border: 1px solid #313244; padding: 4px;")
        form_layout.addRow("Target LUFS:", self._lufs_spin)
        
        self._tp_spin = QDoubleSpinBox()
        self._tp_spin.setRange(-20.0, 0.0)
        self._tp_spin.setDecimals(1)
        self._tp_spin.setSingleStep(0.1)
        self._tp_spin.setSuffix(" dBTP")
        self._tp_spin.setStyleSheet("background-color: #181825; color: #cdd6f4; border: 1px solid #313244; padding: 4px;")
        form_layout.addRow("Max True Peak:", self._tp_spin)
        
        self._lra_spin = QDoubleSpinBox()
        self._lra_spin.setRange(1.0, 30.0)
        self._lra_spin.setDecimals(1)
        self._lra_spin.setSingleStep(1.0)
        self._lra_spin.setSuffix(" LU")
        self._lra_spin.setStyleSheet("background-color: #181825; color: #cdd6f4; border: 1px solid #313244; padding: 4px;")
        form_layout.addRow("Target LRA:", self._lra_spin)
        
        # Connect spinners to custom preset if changed manually
        self._lufs_spin.valueChanged.connect(lambda: self._check_custom_preset())
        self._tp_spin.valueChanged.connect(lambda: self._check_custom_preset())
        self._lra_spin.valueChanged.connect(lambda: self._check_custom_preset())

        settings_layout.addLayout(form_layout)
        left_layout.addWidget(settings_frame)
        
        # Initialize default preset
        self._updating_preset = False
        self._on_preset_changed("Spotify / YouTube")

        # --- Actions ---
        actions_layout = QHBoxLayout()
        
        self._analyze_btn = QPushButton("Analyze Only")
        self._analyze_btn.setStyleSheet(
            "QPushButton { background-color: #313244; color: #cdd6f4; font-weight: bold; border-radius: 6px; padding: 10px 16px; }"
            "QPushButton:hover { background-color: #45475a; }"
        )
        self._analyze_btn.clicked.connect(self._start_analysis)
        actions_layout.addWidget(self._analyze_btn)

        self._normalize_btn = QPushButton("NORMALIZE & EXPORT")
        self._normalize_btn.setStyleSheet(
            "QPushButton { background-color: #a6e3a1; color: #11111b; font-weight: bold; border-radius: 6px; padding: 10px 16px; }"
            "QPushButton:hover { background-color: #94e2d5; }"
        )
        self._normalize_btn.clicked.connect(self._start_normalization)
        actions_layout.addWidget(self._normalize_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.setStyleSheet(
            "QPushButton { background-color: #f38ba8; color: #11111b; font-weight: bold; border-radius: 6px; padding: 10px 16px; }"
            "QPushButton:hover { background-color: #eba0ac; }"
            "QPushButton:disabled { background-color: #313244; color: #585b70; }"
        )
        self._cancel_btn.clicked.connect(self._cancel_all)
        actions_layout.addWidget(self._cancel_btn)

        left_layout.addLayout(actions_layout)
        left_layout.addStretch()
        content_layout.addLayout(left_layout, stretch=1)

        # Right Column: Files & Status Table
        right_layout = QVBoxLayout()
        table_header = QHBoxLayout()
        table_header.addWidget(QLabel("Files & Measurements"))
        table_header.addStretch()
        
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setStyleSheet(
            "QPushButton { background-color: #313244; color: #cdd6f4; border-radius: 4px; padding: 4px 8px; }"
            "QPushButton:hover { background-color: #45475a; }"
        )
        self._clear_btn.clicked.connect(self._clear_results)
        table_header.addWidget(self._clear_btn)
        
        self._open_folder_btn = QPushButton("Open Folder")
        self._open_folder_btn.setStyleSheet(
            "QPushButton { background-color: #89b4fa; color: #11111b; border-radius: 4px; padding: 4px 8px; font-weight: bold; }"
            "QPushButton:hover { background-color: #74c7ec; }"
        )
        self._open_folder_btn.clicked.connect(self._open_folder)
        table_header.addWidget(self._open_folder_btn)
        
        right_layout.addLayout(table_header)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Filename", "Orig. LUFS", "Orig. Peak", "Status"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setStyleSheet(
            "QTableWidget { background-color: #181825; border: 1px solid #313244; color: #cdd6f4; gridline-color: #313244; border-radius: 6px; }"
            "QHeaderView::section { background-color: #1e1e2e; color: #cdd6f4; border: 1px solid #313244; padding: 4px; }"
        )
        right_layout.addWidget(self._table)

        content_layout.addLayout(right_layout, stretch=2)
        layout.addLayout(content_layout)

        # Progress and Log Panels
        self._progress_panel = ProgressPanel()
        layout.addWidget(self._progress_panel)

        self._log_panel = LogPanel()
        self._log_panel.setMinimumHeight(100)
        layout.addWidget(self._log_panel)

    def _on_preset_changed(self, text: str) -> None:
        if self._updating_preset:
            return
            
        settings = PRESETS.get(text)
        if settings:
            self._updating_preset = True
            self._lufs_spin.setValue(settings["lufs"])
            self._tp_spin.setValue(settings["tp"])
            self._lra_spin.setValue(settings["lra"])
            self._updating_preset = False

    def _check_custom_preset(self) -> None:
        if self._updating_preset:
            return
            
        # If values don't match the current preset, set to Custom
        current_preset = self._preset_combo.currentText()
        if current_preset != "Custom":
            settings = PRESETS.get(current_preset)
            if settings:
                if (abs(settings["lufs"] - self._lufs_spin.value()) > 0.01 or
                    abs(settings["tp"] - self._tp_spin.value()) > 0.01 or
                    abs(settings["lra"] - self._lra_spin.value()) > 0.01):
                    
                    self._updating_preset = True
                    self._preset_combo.setCurrentText("Custom")
                    self._updating_preset = False

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
            self._log_panel.append_log(f"Added {len(self._files)} file(s).")
            self._update_table()

    def _clear_results(self) -> None:
        self._files.clear()
        self._measurements.clear()
        self._update_table()

    def _open_folder(self) -> None:
        out_dir = self._config.output_dir
        if out_dir.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(out_dir)))

    def _update_table(self) -> None:
        self._table.setRowCount(len(self._files))
        for row, path in enumerate(self._files):
            self._table.setItem(row, 0, QTableWidgetItem(path.name))
            
            info = self._measurements.get(path)
            if info:
                lufs = f"{info.integrated_lufs:.2f} LUFS" if info.integrated_lufs is not None else "--"
                peak = f"{info.peak_dbfs:.2f} dB" if info.peak_dbfs is not None else "--"
                self._table.setItem(row, 1, QTableWidgetItem(lufs))
                self._table.setItem(row, 2, QTableWidgetItem(peak))
                self._table.setItem(row, 3, QTableWidgetItem("Analyzed"))
            else:
                self._table.setItem(row, 1, QTableWidgetItem("--"))
                self._table.setItem(row, 2, QTableWidgetItem("--"))
                self._table.setItem(row, 3, QTableWidgetItem("Pending"))

    def _set_ui_enabled(self, enabled: bool) -> None:
        self._analyze_btn.setEnabled(enabled)
        self._normalize_btn.setEnabled(enabled)
        self._drop_zone.setEnabled(enabled)
        self._clear_btn.setEnabled(enabled)
        self._preset_combo.setEnabled(enabled)
        self._lufs_spin.setEnabled(enabled)
        self._tp_spin.setEnabled(enabled)
        self._lra_spin.setEnabled(enabled)
        
        self._cancel_btn.setEnabled(not enabled)
        if enabled:
            self._cancel_btn.setText("Cancel")

    def _start_analysis(self) -> None:
        if not self._files:
            self._log_panel.append_error("Please add files first.")
            return

        self._set_ui_enabled(False)
        self._progress_panel.start_job("Analyzing files...")
        self._log_panel.clear_logs()

        self._analyzer_worker = AnalyzerWorker(self._files.copy())
        self._analyzer_worker.progress.connect(self._progress_panel.set_progress)
        self._analyzer_worker.log_msg.connect(self._log_panel.append_log)
        self._analyzer_worker.error.connect(self._log_panel.append_error)
        self._analyzer_worker.finished_analysis.connect(self._on_analysis_finished)
        
        self._analyzer_worker.start()

    def _on_analysis_finished(self, results: dict[Path, AudioInfo]) -> None:
        was_cancelled = (self._analyzer_worker is not None and self._analyzer_worker._cancel_flag.is_set())
        self._analyzer_worker = None
        
        self._measurements.update(results)
        self._update_table()
        
        self._set_ui_enabled(True)
        self._progress_panel.finish_job(success=not was_cancelled)

    def _start_normalization(self) -> None:
        if not self._files:
            self._log_panel.append_error("Please add files first.")
            return

        self._set_ui_enabled(False)
        self._progress_panel.start_job("Normalizing files...")
        self._log_panel.clear_logs()

        options = {
            "target_lufs": self._lufs_spin.value(),
            "max_true_peak": self._tp_spin.value(),
            "lra": self._lra_spin.value(),
        }

        processor = ProcessorRegistry.get_processor("loudness_normalizer")
        self._processor_worker = ProcessorWorker(
            processor,
            self._files.copy(),
            self._config.output_dir,
            options
        )
        
        self._processor_worker.signals.progress.connect(self._progress_panel.set_progress)
        self._processor_worker.signals.log.connect(self._log_panel.append_log)
        self._processor_worker.signals.error.connect(self._log_panel.append_error)
        self._processor_worker.signals.finished.connect(self._on_normalization_finished)
        
        self._processor_worker.start()

    def _on_normalization_finished(self, results: dict) -> None:
        was_cancelled = (self._processor_worker is not None and self._processor_worker._cancel_flag.is_set())
        self._processor_worker = None
        
        if results and not was_cancelled:
            # Update table statuses
            for row, path in enumerate(self._files):
                if path in results:
                    val = results[path]
                    if isinstance(val, dict) and "error" in val:
                        self._table.setItem(row, 3, QTableWidgetItem("Error"))
                        item = self._table.item(row, 3)
                        if item:
                            item.setForeground(Qt.GlobalColor.red)
                    else:
                        self._table.setItem(row, 3, QTableWidgetItem("Normalized"))
                        item = self._table.item(row, 3)
                        if item:
                            item.setForeground(Qt.GlobalColor.green)
        
        self._set_ui_enabled(True)
        self._progress_panel.finish_job(success=not was_cancelled)

    def _cancel_all(self) -> None:
        if self._analyzer_worker and self._analyzer_worker.isRunning():
            self._analyzer_worker.cancel()
        if self._processor_worker and self._processor_worker.isRunning():
            self._processor_worker.cancel()
        
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.setText("Cancelling...")
