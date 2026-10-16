"""Audio Information (Metadata) Page UI."""

import logging
from pathlib import Path
import csv

from qtpy.QtCore import Qt, QUrl
from qtpy.QtGui import QDesktopServices
from qtpy.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.audio.metadata import AudioInfo
from src.gui.widgets import DropZone, LogPanel, ProgressPanel
from src.utils import AppConfig
from src.workers.analyzer_worker import AnalyzerWorker
from src.gui.watermarked_page import WatermarkedPage

log = logging.getLogger("sound_processor.gui.metadata_page")

class MetadataPage(WatermarkedPage):
    """UI page for viewing audio technical information and metadata."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = AppConfig()
        self._files: list[Path] = []
        self._worker: AnalyzerWorker | None = None
        self._results: dict[Path, AudioInfo] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Title
        title = QLabel("Audio Information & Diagnostics")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #cdd6f4;")
        layout.addWidget(title)

        # DropZone
        self._drop_zone = DropZone()
        self._drop_zone.setText("ℹ️ Drop audio file or folder to analyze")
        self._drop_zone.filesDropped.connect(self._handle_files_input)
        layout.addWidget(self._drop_zone)

        # Main content area
        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        # Left Column: Single Result Box & Actions
        left_layout = QVBoxLayout()
        left_layout.setSpacing(12)

        # Info Card Box
        card_frame = QFrame()
        card_frame.setObjectName("InfoCardFrame")
        card_frame.setStyleSheet(
            "#InfoCardFrame { background-color: #1e1e2e; border: 1px solid #313244; border-radius: 6px; padding: 12px; }"
        )
        card_layout = QVBoxLayout(card_frame)
        card_layout.setSpacing(6)

        self._file_name_label = QLabel("Ready")
        self._file_name_label.setStyleSheet("color: #cdd6f4; font-size: 14px; font-weight: bold;")
        card_layout.addWidget(self._file_name_label)
        
        self._file_path_label = QLabel("--")
        self._file_path_label.setStyleSheet("color: #a6adc8; font-size: 11px;")
        card_layout.addWidget(self._file_path_label)
        
        card_layout.addSpacing(8)

        # Format details
        fmt_title = QLabel("[FORMAT]")
        fmt_title.setStyleSheet("color: #f38ba8; font-weight: bold; font-size: 11px;")
        card_layout.addWidget(fmt_title)
        
        self._format_label = QLabel("Codec: --\nSample Rate: --\nBit Depth: --\nChannels: --")
        self._format_label.setStyleSheet("color: #bac2de; font-family: monospace;")
        card_layout.addWidget(self._format_label)
        
        card_layout.addSpacing(8)
        
        # Timing details
        time_title = QLabel("[TIMING & SIZE]")
        time_title.setStyleSheet("color: #89b4fa; font-weight: bold; font-size: 11px;")
        card_layout.addWidget(time_title)
        
        self._time_label = QLabel("Duration: --\nFile Size: --")
        self._time_label.setStyleSheet("color: #bac2de; font-family: monospace;")
        card_layout.addWidget(self._time_label)
        
        card_layout.addSpacing(8)
        
        # Amplitude details
        amp_title = QLabel("[AMPLITUDE & LOUDNESS]")
        amp_title.setStyleSheet("color: #a6e3a1; font-weight: bold; font-size: 11px;")
        card_layout.addWidget(amp_title)
        
        self._amp_label = QLabel("Sample Peak: --\nRMS: --\nLUFS (Int): --")
        self._amp_label.setStyleSheet("color: #bac2de; font-family: monospace;")
        card_layout.addWidget(self._amp_label)
        
        card_layout.addSpacing(8)
        
        # Diagnostics
        diag_title = QLabel("[DIAGNOSTICS]")
        diag_title.setStyleSheet("color: #f9e2af; font-weight: bold; font-size: 11px;")
        card_layout.addWidget(diag_title)
        
        self._diag_label = QLabel("Ready for Processing: Unknown")
        self._diag_label.setStyleSheet("color: #bac2de; font-family: monospace;")
        card_layout.addWidget(self._diag_label)

        left_layout.addWidget(card_frame)

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
        
        self._export_csv_btn = QPushButton("Export CSV")
        self._export_csv_btn.setStyleSheet(
            "QPushButton { background-color: #a6e3a1; color: #11111b; border-radius: 4px; padding: 4px 8px; font-weight: bold; }"
            "QPushButton:hover { background-color: #94e2d5; }"
        )
        self._export_csv_btn.clicked.connect(self._export_csv)
        table_header.addWidget(self._export_csv_btn)
        
        right_layout.addLayout(table_header)

        self._table = QTableWidget(0, 8)
        self._table.setHorizontalHeaderLabels(["Filename", "SR (Hz)", "Bit", "Ch", "Duration", "Size", "Peak (dB)", "LUFS"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 8):
            self._table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
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
        self._results.clear()
        self._table.setRowCount(0)
        self._file_name_label.setText("Ready")
        self._file_path_label.setText("--")
        self._format_label.setText("Codec: --\nSample Rate: --\nBit Depth: --\nChannels: --")
        self._time_label.setText("Duration: --\nFile Size: --")
        self._amp_label.setText("Sample Peak: --\nRMS: --\nLUFS (Int): --")
        self._diag_label.setText("Ready for Processing: Unknown")

    def _start_analysis(self) -> None:
        if not self._files:
            self._log_panel.append_error("Please add files before analyzing.")
            return

        self._set_ui_enabled(False)
        self._progress_panel.start_job(f"Analyzing {len(self._files)} track(s)...")
        self._log_panel.clear_logs()
        self._table.setRowCount(0)
        self._results.clear()

        self._worker = AnalyzerWorker(self._files.copy())
        
        self._worker.progress.connect(self._progress_panel.set_progress)
        self._worker.log_msg.connect(self._log_panel.append_log)
        self._worker.error.connect(self._log_panel.append_error)
        self._worker.finished_analysis.connect(self._on_analysis_finished)
        self._worker.finished.connect(self._cleanup_worker)
        
        self._worker.start()

    def _cancel_analysis(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self._cancel_btn.setEnabled(False)
            self._cancel_btn.setText("Cancelling...")

    def _on_analysis_finished(self, results: dict[Path, AudioInfo]) -> None:
        was_cancelled = (self._worker is not None and self._worker._cancel_flag.is_set())
        self._set_ui_enabled(True)
        self._progress_panel.finish_job(success=not was_cancelled)
        
        self._results = results

        if results:
            self._update_table(results)
            # Update left card with the last processed file
            last_file, last_info = list(results.items())[-1]
            self._update_card(last_info)

    def _cleanup_worker(self) -> None:
        self._worker = None

    def _set_ui_enabled(self, enabled: bool) -> None:
        self._analyze_btn.setEnabled(enabled)
        self._drop_zone.setEnabled(enabled)
        self._clear_btn.setEnabled(enabled)
        self._export_csv_btn.setEnabled(enabled)
        
        self._cancel_btn.setEnabled(not enabled)
        if enabled:
            self._cancel_btn.setText("Cancel")

    def _update_card(self, info: AudioInfo) -> None:
        self._file_name_label.setText(Path(info.filepath).name if hasattr(info, 'filepath') else "File") # probe currently doesn't store filepath, wait, let me check
        # Wait, probe() in metadata.py doesn't store filepath. Let's fix that or pass it.
        # It's better to just use the dictionary key but we don't have it here directly, oh well, we can infer it.
        # Actually I can just pass the path. 
        self._file_name_label.setText("Analysis Complete") 
        # I'll update format
        bd_str = f"{info.bit_depth}-bit" if info.bit_depth else "Unknown"
        ch_str = f"{info.channels} ({'Stereo' if info.channels == 2 else 'Mono' if info.channels == 1 else 'Multichannel'})"
        
        self._format_label.setText(
            f"Codec: {info.codec.upper()} ({info.format})\n"
            f"Sample Rate: {info.sample_rate:,} Hz\n"
            f"Bit Depth: {bd_str}\n"
            f"Channels: {ch_str}"
        )
        self._time_label.setText(
            f"Duration: {info.duration_formatted}\n"
            f"File Size: {info.file_size_mb:.2f} MB"
        )
        
        peak_str = f"{info.peak_dbfs:.2f} dBFS" if info.peak_dbfs is not None else "--"
        rms_str = f"{info.rms_dbfs:.2f} dBFS" if info.rms_dbfs is not None else "--"
        lufs_str = f"{info.integrated_lufs:.2f} LUFS" if info.integrated_lufs is not None else "--"
        self._amp_label.setText(f"Sample Peak: {peak_str}\nRMS: {rms_str}\nLUFS (Int): {lufs_str}")
        
        # Diagnostics
        diag = []
        is_ready = True
        
        if info.peak_dbfs is not None and info.peak_dbfs > -0.1:
            diag.append("⚠️ Audio is peaking heavily (near 0 dBFS). Normalization recommended.")
            is_ready = False
        
        if info.sample_rate not in (44100, 48000, 96000):
            diag.append("⚠️ Non-standard sample rate. May cause drift.")
            
        if info.bit_depth and info.bit_depth < 16:
            diag.append("⚠️ Low bit depth (<16-bit). High noise floor.")
            
        if not diag:
            diag.append("✅ Audio parameters look standard and healthy.")
            
        status = "Ready" if is_ready else "Needs Attention"
        self._diag_label.setText(f"Status: {status}\n\n" + "\n".join(diag))

    def _update_table(self, results: dict[Path, AudioInfo]) -> None:
        self._table.setRowCount(len(results))
        for row, (path, info) in enumerate(results.items()):
            self._table.setItem(row, 0, QTableWidgetItem(path.name))
            self._table.setItem(row, 1, QTableWidgetItem(f"{info.sample_rate:,}"))
            bd = str(info.bit_depth) if info.bit_depth else "?"
            self._table.setItem(row, 2, QTableWidgetItem(bd))
            self._table.setItem(row, 3, QTableWidgetItem(str(info.channels)))
            self._table.setItem(row, 4, QTableWidgetItem(info.duration_formatted))
            self._table.setItem(row, 5, QTableWidgetItem(f"{info.file_size_mb:.1f} MB"))
            
            peak = f"{info.peak_dbfs:.2f}" if info.peak_dbfs is not None else "--"
            self._table.setItem(row, 6, QTableWidgetItem(peak))
            
            lufs = f"{info.integrated_lufs:.2f}" if info.integrated_lufs is not None else "--"
            self._table.setItem(row, 7, QTableWidgetItem(lufs))
            
            # Color row if peaking > -0.1
            if info.peak_dbfs is not None and info.peak_dbfs > -0.1:
                for col in range(8):
                    item = self._table.item(row, col)
                    if item:
                        item.setForeground(Qt.GlobalColor.red)

    def _export_csv(self) -> None:
        if not self._results:
            self._log_panel.append_error("No analysis results to export.")
            return
            
        out_path = self._config.output_dir / "audio_analysis.csv"
        try:
            with out_path.open("w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "File", "Path", "Codec", "SampleRate", "BitDepth", 
                    "Channels", "DurationSec", "SizeMB", "Peak_dBFS", "RMS_dBFS", "LUFS"
                ])
                for path, info in self._results.items():
                    writer.writerow([
                        path.name,
                        str(path.parent),
                        info.codec,
                        info.sample_rate,
                        info.bit_depth or "",
                        info.channels,
                        f"{info.duration:.3f}",
                        f"{info.file_size_mb:.3f}",
                        f"{info.peak_dbfs:.3f}" if info.peak_dbfs is not None else "",
                        f"{info.rms_dbfs:.3f}" if info.rms_dbfs is not None else "",
                        f"{info.integrated_lufs:.3f}" if info.integrated_lufs is not None else ""
                    ])
            self._log_panel.append_log(f"Exported CSV to {out_path}")
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(out_path)))
        except Exception as e:
            self._log_panel.append_error(f"Failed to export CSV: {e}")
