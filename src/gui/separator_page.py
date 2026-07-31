"""AI stem separator page with model-driven UI updates and SeparatorWorker execution."""

from __future__ import annotations

import logging
from pathlib import Path

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.ai import create_default_manager
from src.core.processor_registry import ProcessorRegistry
from src.gui.widgets import DropZone, LogPanel, ProgressPanel, StemPreviewWidget
from src.utils import AppConfig
from src.workers import ProcessorWorker

log = logging.getLogger("sound_processor.gui.separator_page")


from src.gui.watermarked_page import WatermarkedPage

class SeparatorPage(WatermarkedPage):
    """UI page for choosing separation models, previewing stems, and running inference."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = AppConfig()
        self._manager = create_default_manager(self._config.models_dir)
        self._file_path: Path | None = None
        self._worker: ProcessorWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Title
        title = QLabel("AI Instrument Separator")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #cdd6f4;")
        layout.addWidget(title)

        # 1. Model Selector Panel
        model_frame = QFrame()
        model_frame.setStyleSheet("QFrame { background-color: #181825; border: 1px solid #313244; border-radius: 6px; }")
        model_layout = QVBoxLayout(model_frame)
        model_layout.setContentsMargins(12, 12, 12, 12)
        model_layout.setSpacing(8)

        sel_layout = QHBoxLayout()
        sel_layout.addWidget(QLabel("AI Model:"))
        self._model_combo = QComboBox()
        self._model_combo.currentTextChanged.connect(self._on_model_changed)
        sel_layout.addWidget(self._model_combo, stretch=1)
        model_layout.addLayout(sel_layout)

        self._model_desc = QLabel("")
        self._model_desc.setStyleSheet("color: #a6adc8; font-size: 12px;")
        self._model_desc.setWordWrap(True)
        model_layout.addWidget(self._model_desc)

        layout.addWidget(model_frame)

        # 2. Input Section: DropZone + selected file info
        input_layout = QHBoxLayout()
        input_layout.setSpacing(16)

        # DropZone Column
        self._drop_zone = DropZone()
        self._drop_zone.setText("🎵 Drop audio file here\nor click to browse")
        self._drop_zone.filesDropped.connect(self._handle_file_input)
        input_layout.addWidget(self._drop_zone, stretch=3)

        # File Info & Stem Preview Column
        self._info_panel = QFrame()
        self._info_panel.setStyleSheet("QFrame { background-color: #1e1e2e; border: 1px solid #313244; border-radius: 6px; }")
        info_lay = QVBoxLayout(self._info_panel)
        info_lay.setContentsMargins(12, 12, 12, 12)
        info_lay.setSpacing(12)

        info_header = QLabel("File Details")
        info_header.setStyleSheet("font-weight: bold; color: #cdd6f4;")
        info_lay.addWidget(info_header)

        self._file_name_label = QLabel("No file selected")
        self._file_name_label.setStyleSheet("color: #f5c2e7; font-weight: 500;")
        self._file_name_label.setWordWrap(True)
        info_lay.addWidget(self._file_name_label)

        self._file_details_label = QLabel("")
        self._file_details_label.setStyleSheet("color: #a6adc8; font-size: 12px;")
        info_lay.addWidget(self._file_details_label)

        info_lay.addSpacing(4)

        # Reusable stem preview widget
        self._stem_preview = StemPreviewWidget()
        info_lay.addWidget(self._stem_preview)
        info_lay.addStretch()

        input_layout.addWidget(self._info_panel, stretch=2)
        layout.addLayout(input_layout)

        # Output folder row
        folder_frame = QWidget()
        folder_layout = QHBoxLayout(folder_frame)
        folder_layout.setContentsMargins(0, 0, 0, 0)
        folder_layout.setSpacing(12)
        
        folder_layout.addWidget(QLabel("Output Folder:"))
        self._output_edit = QLabel(str(self._config.output_dir))
        self._output_edit.setStyleSheet("color: #a6adc8; font-size: 12px;")
        folder_layout.addWidget(self._output_edit, stretch=1)
        
        self._output_btn = QPushButton("Change Folder")
        self._output_btn.setStyleSheet(
            "QPushButton { background-color: #313244; color: #cdd6f4; border-radius: 4px; padding: 4px 8px; }"
            "QPushButton:hover { background-color: #45475a; }"
        )
        self._output_btn.clicked.connect(self._change_folder)
        folder_layout.addWidget(self._output_btn)
        
        layout.addWidget(folder_frame)

        # 3. Actions Row
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(12)

        self._separate_btn = QPushButton("Separate Stems")
        self._separate_btn.setStyleSheet(
            "QPushButton { background-color: #a6e3a1; color: #11111b; font-weight: bold; border-radius: 6px; padding: 10px 24px; }"
            "QPushButton:hover { background-color: #94e2d5; }"
        )
        self._separate_btn.clicked.connect(self._start_separation)
        actions_layout.addWidget(self._separate_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.setStyleSheet(
            "QPushButton { background-color: #f38ba8; color: #11111b; font-weight: bold; border-radius: 6px; padding: 10px 16px; }"
            "QPushButton:hover { background-color: #eba0ac; }"
            "QPushButton:disabled { background-color: #313244; color: #585b70; }"
        )
        self._cancel_btn.clicked.connect(self._cancel_separation)
        actions_layout.addWidget(self._cancel_btn)

        layout.addLayout(actions_layout)

        # 4. Progress and Log Panels
        self._progress_panel = ProgressPanel()
        layout.addWidget(self._progress_panel)

        self._log_panel = LogPanel()
        self._log_panel.setMinimumHeight(120)
        layout.addWidget(self._log_panel)

        # Initialize list of models
        self._populate_models()

    def _populate_models(self) -> None:
        """Read registered models and populate selector combo."""
        self._model_combo.clear()
        models = self._manager.list_models()
        
        last_model_id = self._config.last_selected_separator_model
        default_idx = 0
        
        for idx, meta in enumerate(models):
            self._model_combo.addItem(meta.display_name, userData=meta.model_id)
            if meta.model_id == last_model_id:
                default_idx = idx
                
        if self._model_combo.count() > 0:
            self._model_combo.setCurrentIndex(default_idx)
            # Ensure the UI reflects the initial selection
            self._on_model_changed(self._model_combo.currentText())

    def _on_model_changed(self, display_name: str) -> None:
        """Trigger UI metadata changes when a new model is selected."""
        idx = self._model_combo.currentIndex()
        if idx < 0:
            return
        
        model_id = self._model_combo.itemData(idx)
        models = self._manager.list_models()
        meta = next((m for m in models if m.model_id == model_id), None)
        
        if meta:
            self._model_desc.setText(meta.description)
            self._stem_preview.update_stems(meta.stem_names)
            
            # Persist selection
            self._config.last_selected_separator_model = model_id

    def _change_folder(self) -> None:
        """Browse to update output folder."""
        path = QFileDialog.getExistingDirectory(self, "Select Output Folder", self._output_edit.text())
        if path:
            self._output_edit.setText(path)

    def _handle_file_input(self, paths: list[Path]) -> None:
        """Add the first dropped/selected file to separator workspace."""
        if not paths:
            return
        
        p = paths[0]
        if p.is_file():
            self._file_path = p
            self._file_name_label.setText(p.name)
            
            # Resolve audio metadata
            try:
                from src.audio import probe
                info = probe(p)
                duration_str = f"{int(info.duration // 60)}m {int(info.duration % 60)}s"
                self._file_details_label.setText(
                    f"Format: {info.format.upper()} ({info.codec.upper()})\n"
                    f"Sample Rate: {info.sample_rate:,} Hz\n"
                    f"Channels: {info.channels} ({'Stereo' if info.channels == 2 else 'Mono'})\n"
                    f"Duration: {duration_str}"
                )
            except Exception as exc:
                log.exception("Error probing file '%s': %s", p, exc)
                self._file_details_label.setText("Error probing audio details.")

    def _start_separation(self) -> None:
        """Instantiate SeparatorWorker thread."""
        if self._file_path is None:
            self._log_panel.append_error("Please drop or browse an audio file first.")
            return

        idx = self._model_combo.currentIndex()
        if idx < 0:
            return
        
        model_id = self._model_combo.itemData(idx)
        models = self._manager.list_models()
        meta = next((m for m in models if m.model_id == model_id), None)

        if not meta:
            return

        # Configure UI
        self._set_ui_enabled(False)
        self._progress_panel.start_job("Starting AI stem separation...")
        self._log_panel.clear_logs()

        # Instantiate worker thread
        output_dir = Path(self._output_edit.text())
        processor = ProcessorRegistry.get_processor("stem_separator")
        options = {"model_id": model_id, "manager": self._manager}
        self._worker = ProcessorWorker(processor, [self._file_path], output_dir, options)
        
        # Connect signals
        self._worker.signals.progress.connect(self._progress_panel.set_progress)
        self._worker.signals.log.connect(self._log_panel.append_log)
        self._worker.signals.error.connect(self._log_panel.append_error)
        self._worker.signals.finished.connect(self._on_separation_finished)
        # QThread.finished fires AFTER run() has fully returned — safe to delete
        self._worker.finished.connect(self._cleanup_worker)
        
        self._worker.start()

    def _cancel_separation(self) -> None:
        """Signal active background separator thread to cancel."""
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self._cancel_btn.setEnabled(False)
            self._log_panel.append_log("Cancellation requested...")

    def _on_separation_finished(self, results: dict | None) -> None:
        """Reset UI state. Called while run() is still on the stack — do NOT delete worker here."""
        self._set_ui_enabled(True)
        self._progress_panel.finish_job(
            success=results is not None,
            message="Separation complete!" if results is not None else "Cancelled."
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
        self._model_combo.setEnabled(enabled)
        self._output_btn.setEnabled(enabled)
        self._separate_btn.setEnabled(enabled)
        
        self._cancel_btn.setEnabled(not enabled)
