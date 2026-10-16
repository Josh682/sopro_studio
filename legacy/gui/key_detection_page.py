"""Key Detection Page UI."""

import logging
from pathlib import Path
from typing import Any

from qtpy.QtCore import Qt
from qtpy.QtGui import QDesktopServices
from qtpy.QtCore import QUrl
from qtpy.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.music_analyzer import KeyResult, TempoResult
from src.core.processor_registry import ProcessorRegistry
from src.gui.widgets import DropZone, LogPanel, ProgressPanel
from src.utils import AppConfig
from src.workers import ProcessorWorker

log = logging.getLogger("sound_processor.gui.key_detection_page")


from src.gui.watermarked_page import WatermarkedPage

class KeyDetectionPage(WatermarkedPage):
    """UI page for detecting musical key and tempo."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = AppConfig()
        self._files: list[Path] = []
        self._worker: ProcessorWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Title
        title = QLabel("Key & Tempo Detection")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #cdd6f4;")
        layout.addWidget(title)

        # DropZone
        self._drop_zone = DropZone()
        self._drop_zone.setText("🎵 Drop audio file or folder here")
        self._drop_zone.filesDropped.connect(self._handle_files_input)
        layout.addWidget(self._drop_zone)

        # Main content area
        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        # Left Column: Single Result Box & Actions
        left_layout = QVBoxLayout()
        left_layout.setSpacing(12)

        # Latest Result Box
        res_frame = QFrame()
        res_frame.setObjectName("LatestResultFrame")
        res_frame.setStyleSheet(
            "#LatestResultFrame { background-color: #1e1e2e; border: 1px solid #313244; border-radius: 6px; padding: 12px; }"
        )
        res_layout = QVBoxLayout(res_frame)
        res_layout.setSpacing(8)

        self._latest_file_label = QLabel("Ready")
        self._latest_file_label.setStyleSheet("color: #a6adc8; font-size: 11px;")
        res_layout.addWidget(self._latest_file_label)

        stats_layout = QHBoxLayout()
        self._key_label = QLabel("Key: --")
        self._key_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #cdd6f4;")
        self._bpm_label = QLabel("BPM: --")
        self._bpm_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #cdd6f4;")
        stats_layout.addWidget(self._key_label)
        stats_layout.addWidget(self._bpm_label)
        res_layout.addLayout(stats_layout)

        conf_layout = QHBoxLayout()
        conf_layout.addWidget(QLabel("Confidence:"))
        self._conf_bar = QProgressBar()
        self._conf_bar.setRange(0, 100)
        self._conf_bar.setValue(0)
        self._conf_bar.setTextVisible(True)
        self._conf_bar.setStyleSheet(
            "QProgressBar { background-color: #313244; border-radius: 4px; text-align: center; color: #cdd6f4; }"
            "QProgressBar::chunk { background-color: #89b4fa; border-radius: 4px; }"
        )
        conf_layout.addWidget(self._conf_bar)
        res_layout.addLayout(conf_layout)

        self._reliability_label = QLabel("")
        self._reliability_label.setStyleSheet("color: #a6adc8; font-style: italic;")
        res_layout.addWidget(self._reliability_label)

        # Alternatives
        self._alt_title = QLabel("Alternatives:")
        self._alt_title.setStyleSheet("color: #a6adc8; font-weight: bold; margin-top: 8px;")
        res_layout.addWidget(self._alt_title)
        
        self._alt_label = QPlainTextEdit("--")
        self._alt_label.setReadOnly(True)
        self._alt_label.setStyleSheet("QPlainTextEdit { background: transparent; border: none; color: #bac2de; font-family: monospace; }")
        self._alt_label.setMinimumHeight(60)
        self._alt_label.setMaximumHeight(100)
        res_layout.addWidget(self._alt_label)
        self._alt_title.setVisible(False)
        self._alt_label.setVisible(False)

        left_layout.addWidget(res_frame)

        # Actions
        actions_layout = QHBoxLayout()
        self._analyze_btn = QPushButton("Analyze")
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

        left_layout.addLayout(actions_layout)
        left_layout.addStretch()
        content_layout.addLayout(left_layout, stretch=1)

        # Right Column: Batch Results Table
        right_layout = QVBoxLayout()
        table_header = QHBoxLayout()
        table_header.addWidget(QLabel("Batch Results"))
        table_header.addStretch()
        
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setStyleSheet(
            "QPushButton { background-color: #313244; color: #cdd6f4; border-radius: 4px; padding: 4px 8px; }"
            "QPushButton:hover { background-color: #45475a; }"
        )
        self._clear_btn.clicked.connect(self._clear_results)
        table_header.addWidget(self._clear_btn)
        
        self._open_folder_btn = QPushButton("Open CSV Folder")
        self._open_folder_btn.setStyleSheet(
            "QPushButton { background-color: #a6e3a1; color: #11111b; border-radius: 4px; padding: 4px 8px; font-weight: bold; }"
            "QPushButton:hover { background-color: #94e2d5; }"
        )
        self._open_folder_btn.clicked.connect(self._open_csv_folder)
        table_header.addWidget(self._open_folder_btn)
        
        right_layout.addLayout(table_header)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Filename", "Key", "BPM", "Confidence"])
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
            self._log_panel.append_log(f"Added {len(self._files)} file(s). Ready to analyze.")

    def _clear_results(self) -> None:
        self._files.clear()
        self._table.setRowCount(0)
        self._latest_file_label.setText("Ready")
        self._key_label.setText("Key: --")
        self._bpm_label.setText("BPM: --")
        self._conf_bar.setValue(0)
        self._conf_bar.setStyleSheet(
            "QProgressBar { background-color: #313244; border-radius: 4px; text-align: center; color: #cdd6f4; }"
            "QProgressBar::chunk { background-color: #89b4fa; border-radius: 4px; }"
        )
        self._reliability_label.setText("")
        self._alt_title.setVisible(False)
        self._alt_label.setVisible(False)
        self._alt_label.setPlainText("--")

    def _open_csv_folder(self) -> None:
        out_dir = self._config.output_dir
        if out_dir.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(out_dir)))
        else:
            self._log_panel.append_error("Output directory does not exist yet.")

    def _start_analysis(self) -> None:
        if not self._files:
            self._log_panel.append_error("Please add files before analyzing.")
            return

        self._set_ui_enabled(False)
        self._progress_panel.start_job(f"Analyzing {len(self._files)} track(s)...")
        self._log_panel.clear_logs()
        self._table.setRowCount(0)

        processor = ProcessorRegistry.get_processor("key_detector")
        self._worker = ProcessorWorker(
            processor, 
            self._files.copy(), 
            self._config.output_dir, 
            {}
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

    def _on_analysis_finished(self, results: dict[Path, dict[str, Any]]) -> None:
        was_cancelled = (
            self._worker is not None and self._worker._cancel_flag.is_set()
        )
        
        # Populate table and latest result
        for file_path, result in results.items():
            if "error" in result:
                self._add_table_row(file_path.name, "Error", "--", "--")
                continue
                
            key_res: KeyResult = result.get("key")
            tempo_res: TempoResult = result.get("tempo")
            
            if not key_res or not tempo_res:
                continue
                
            # Update Latest Result Box
            self._latest_file_label.setText(file_path.name)
            self._key_label.setText(f"Key: {key_res.display}")
            self._bpm_label.setText(f"BPM: {tempo_res.bpm}")
            conf_percent = int(key_res.confidence * 100)
            self._conf_bar.setValue(conf_percent)
            
            if key_res.is_reliable:
                self._reliability_label.setText("⚠ Reliable — safe to use")
                self._reliability_label.setStyleSheet("color: #a6e3a1;")
                self._conf_bar.setStyleSheet(
                    "QProgressBar { background-color: #313244; border-radius: 4px; text-align: center; color: #11111b; }"
                    "QProgressBar::chunk { background-color: #a6e3a1; border-radius: 4px; }"
                )
            else:
                self._reliability_label.setText("⚠ Low confidence — verify manually")
                self._reliability_label.setStyleSheet("color: #f38ba8;")
                self._conf_bar.setStyleSheet(
                    "QProgressBar { background-color: #313244; border-radius: 4px; text-align: center; color: #cdd6f4; }"
                    "QProgressBar::chunk { background-color: #f38ba8; border-radius: 4px; }"
                )
                
            # Update Table
            conf_str = f"{conf_percent}% {'⚠' if not key_res.is_reliable else ''}"
            self._add_table_row(file_path.name, key_res.display, str(tempo_res.bpm), conf_str)
            
            # Show Alternatives
            if key_res.alternatives:
                lines = []
                for alt in key_res.alternatives:
                    alt_name = f"{alt['tonic']} {alt['mode'].capitalize()}"
                    alt_conf = f"{alt['confidence']*100:.1f}%"
                    lines.append(f"{alt_name:<12} {alt_conf:>7}")
                self._alt_label.setPlainText("\n".join(lines))
                self._alt_title.setVisible(True)
                self._alt_label.setVisible(True)
            else:
                self._alt_title.setVisible(False)
                self._alt_label.setVisible(False)

        self._set_ui_enabled(True)
        self._progress_panel.finish_job(
            success=not was_cancelled,
            message="Analysis complete! CSV exported." if not was_cancelled else "Analysis cancelled."
        )

    def _add_table_row(self, filename: str, key: str, bpm: str, conf: str) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, 0, QTableWidgetItem(filename))
        self._table.setItem(row, 1, QTableWidgetItem(key))
        self._table.setItem(row, 2, QTableWidgetItem(bpm))
        self._table.setItem(row, 3, QTableWidgetItem(conf))

    def _cleanup_worker(self) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None

    def _set_ui_enabled(self, enabled: bool) -> None:
        self._drop_zone.setAcceptDrops(enabled)
        self._drop_zone.setEnabled(enabled)
        self._clear_btn.setEnabled(enabled)
        self._analyze_btn.setEnabled(enabled)
        self._cancel_btn.setEnabled(not enabled)
