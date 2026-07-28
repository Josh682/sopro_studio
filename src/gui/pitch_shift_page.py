"""Pitch Shift Page UI."""

import logging
from pathlib import Path

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from src.core.processor_registry import ProcessorRegistry
from src.gui.widgets import DropZone, LogPanel, ProgressPanel
from src.utils import AppConfig
from src.workers import ProcessorWorker

log = logging.getLogger("sound_processor.gui.pitch_shift_page")

CHROMATIC_SCALE = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


from src.gui.watermarked_page import WatermarkedPage

class PitchShiftPage(WatermarkedPage):
    """UI page for pitch shifting."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = AppConfig()
        self._files: list[Path] = []
        self._worker: ProcessorWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Title
        title = QLabel("Pitch Shift")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #cdd6f4;")
        layout.addWidget(title)

        # DropZone
        self._drop_zone = DropZone()
        self._drop_zone.setText("🎵 Drop audio file or folder here")
        self._drop_zone.filesDropped.connect(self._handle_files_input)
        layout.addWidget(self._drop_zone)

        # Settings
        settings_frame = QFrame()
        settings_frame.setStyleSheet(
            "QFrame { background-color: #181825; border: 1px solid #313244; border-radius: 6px; }"
        )
        settings_layout = QVBoxLayout(settings_frame)
        settings_layout.setSpacing(16)
        settings_layout.setContentsMargins(16, 16, 16, 16)

        # Mode Selection
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Mode:"))
        
        self._mode_group = QButtonGroup(self)
        self._radio_manual = QRadioButton("Manual Semitones")
        self._radio_manual.setChecked(True)
        self._radio_target = QRadioButton("Target Root")
        
        self._mode_group.addButton(self._radio_manual)
        self._mode_group.addButton(self._radio_target)
        
        mode_layout.addWidget(self._radio_manual)
        mode_layout.addWidget(self._radio_target)
        mode_layout.addStretch()
        settings_layout.addLayout(mode_layout)

        # Controls Container
        controls_layout = QHBoxLayout()

        # 1. Manual Mode Controls
        self._manual_widget = QWidget()
        manual_lay = QVBoxLayout(self._manual_widget)
        manual_lay.setContentsMargins(0, 0, 0, 0)
        
        slider_row = QHBoxLayout()
        slider_row.addWidget(QLabel("-12"))
        
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(-12, 12)
        self._slider.setValue(0)
        self._slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._slider.setTickInterval(1)
        self._slider.setFixedWidth(200)
        slider_row.addWidget(self._slider)
        
        slider_row.addWidget(QLabel("+12"))
        
        self._manual_val_label = QLabel("0 semitones")
        self._manual_val_label.setStyleSheet("color: #a6adc8; font-weight: bold; margin-left: 12px;")
        slider_row.addWidget(self._manual_val_label)
        slider_row.addStretch()
        
        manual_lay.addLayout(slider_row)
        
        # 2. Target Mode Controls
        self._target_widget = QWidget()
        target_lay = QFormLayout(self._target_widget)
        target_lay.setContentsMargins(0, 0, 0, 0)
        
        self._source_combo = QComboBox()
        self._source_combo.addItems(CHROMATIC_SCALE)
        self._source_combo.setCurrentText("A")
        
        self._target_combo = QComboBox()
        self._target_combo.addItems(CHROMATIC_SCALE)
        self._target_combo.setCurrentText("C")
        
        self._computed_shift_label = QLabel("+3 semitones")
        self._computed_shift_label.setStyleSheet("color: #a6adc8; font-weight: bold;")
        
        target_lay.addRow("Source Root:", self._source_combo)
        target_lay.addRow("Target Root:", self._target_combo)
        target_lay.addRow("Computed Shift:", self._computed_shift_label)
        
        self._target_widget.setVisible(False)

        controls_layout.addWidget(self._manual_widget)
        controls_layout.addWidget(self._target_widget)
        controls_layout.addStretch()
        
        settings_layout.addLayout(controls_layout)
        
        # Output directory
        out_layout = QHBoxLayout()
        self._output_edit = QLabel(str(self._config.output_dir))
        self._output_edit.setStyleSheet("color: #a6adc8; font-size: 11px;")
        
        self._output_btn = QPushButton("Change Folder")
        self._output_btn.setStyleSheet(
            "QPushButton { background-color: #313244; color: #cdd6f4; border-radius: 4px; padding: 4px 8px; }"
            "QPushButton:hover { background-color: #45475a; }"
        )
        self._output_btn.clicked.connect(self._change_folder)
        
        out_layout.addWidget(QLabel("Output:"))
        out_layout.addWidget(self._output_edit, stretch=1)
        out_layout.addWidget(self._output_btn)
        
        settings_layout.addLayout(out_layout)
        layout.addWidget(settings_frame)

        # Actions Row
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(12)

        self._shift_btn = QPushButton("Shift Pitch")
        self._shift_btn.setStyleSheet(
            "QPushButton { background-color: #a6e3a1; color: #11111b; font-weight: bold; border-radius: 6px; padding: 10px 24px; }"
            "QPushButton:hover { background-color: #94e2d5; }"
        )
        self._shift_btn.clicked.connect(self._start_shift)
        actions_layout.addWidget(self._shift_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.setStyleSheet(
            "QPushButton { background-color: #f38ba8; color: #11111b; font-weight: bold; border-radius: 6px; padding: 10px 16px; }"
            "QPushButton:hover { background-color: #eba0ac; }"
            "QPushButton:disabled { background-color: #313244; color: #585b70; }"
        )
        self._cancel_btn.clicked.connect(self._cancel_shift)
        actions_layout.addWidget(self._cancel_btn)
        
        self._clear_btn = QPushButton("Clear Files")
        self._clear_btn.setStyleSheet(
            "QPushButton { background-color: #313244; color: #cdd6f4; border-radius: 6px; padding: 10px 16px; }"
            "QPushButton:hover { background-color: #45475a; }"
        )
        self._clear_btn.clicked.connect(self._clear_files)
        actions_layout.addWidget(self._clear_btn)

        layout.addLayout(actions_layout)

        # Progress and Log
        self._progress_panel = ProgressPanel()
        layout.addWidget(self._progress_panel)

        self._log_panel = LogPanel()
        self._log_panel.setMinimumHeight(120)
        layout.addWidget(self._log_panel)

        # Connections
        self._radio_manual.toggled.connect(self._toggle_mode)
        self._slider.valueChanged.connect(self._update_manual_label)
        self._source_combo.currentTextChanged.connect(self._update_target_label)
        self._target_combo.currentTextChanged.connect(self._update_target_label)

    def _toggle_mode(self, checked: bool) -> None:
        self._manual_widget.setVisible(checked)
        self._target_widget.setVisible(not checked)

    def _update_manual_label(self, val: int) -> None:
        sign = "+" if val > 0 else ""
        self._manual_val_label.setText(f"{sign}{val} semitone{'s' if abs(val) != 1 else ''}")

    def _update_target_label(self) -> None:
        shift = self._compute_semitones()
        sign = "+" if shift > 0 else ""
        self._computed_shift_label.setText(f"{sign}{shift} semitone{'s' if abs(shift) != 1 else ''}")

    def _compute_semitones(self) -> int:
        src = self._source_combo.currentText()
        tgt = self._target_combo.currentText()
        try:
            src_idx = CHROMATIC_SCALE.index(src)
            tgt_idx = CHROMATIC_SCALE.index(tgt)
        except ValueError:
            return 0
            
        delta = (tgt_idx - src_idx) % 12
        if delta > 6:
            delta -= 12
        return delta

    def _change_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Output Folder", self._output_edit.text())
        if path:
            self._output_edit.setText(path)

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
            self._log_panel.append_log(f"Added {len(self._files)} file(s) for pitch shifting.")

    def _clear_files(self) -> None:
        self._files.clear()
        self._log_panel.append_log("File list cleared.")

    def _start_shift(self) -> None:
        if not self._files:
            self._log_panel.append_error("Please add files before shifting.")
            return

        options = {}
        if self._radio_manual.isChecked():
            options["semitones"] = float(self._slider.value())
        else:
            options["semitones"] = float(self._compute_semitones())
            options["target_root"] = self._target_combo.currentText()

        self._set_ui_enabled(False)
        self._progress_panel.start_job(f"Pitch Shifting {len(self._files)} track(s)...")
        self._log_panel.clear_logs()

        output_dir = Path(self._output_edit.text())
        processor = ProcessorRegistry.get_processor("pitch_shifter")
        
        self._worker = ProcessorWorker(processor, self._files.copy(), output_dir, options)
        self._worker.signals.progress.connect(self._progress_panel.set_progress)
        self._worker.signals.log.connect(self._log_panel.append_log)
        self._worker.signals.error.connect(self._log_panel.append_error)
        self._worker.signals.finished.connect(self._on_shift_finished)
        self._worker.finished.connect(self._cleanup_worker)
        
        self._worker.start()

    def _cancel_shift(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self._cancel_btn.setEnabled(False)
            self._log_panel.append_log("Cancellation requested...")

    def _on_shift_finished(self, results: dict) -> None:
        was_cancelled = (
            self._worker is not None and self._worker._cancel_flag.is_set()
        )
        self._set_ui_enabled(True)
        
        if not was_cancelled and results:
            self._progress_panel.finish_job(True, "Pitch shift complete!")
        elif was_cancelled:
            self._progress_panel.finish_job(False, "Cancelled.")
        else:
            self._progress_panel.finish_job(False, "Failed to process files.")

    def _cleanup_worker(self) -> None:
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None

    def _set_ui_enabled(self, enabled: bool) -> None:
        self._drop_zone.setAcceptDrops(enabled)
        self._drop_zone.setEnabled(enabled)
        self._radio_manual.setEnabled(enabled)
        self._radio_target.setEnabled(enabled)
        self._slider.setEnabled(enabled)
        self._source_combo.setEnabled(enabled)
        self._target_combo.setEnabled(enabled)
        self._output_btn.setEnabled(enabled)
        self._clear_btn.setEnabled(enabled)
        self._shift_btn.setEnabled(enabled)
        self._cancel_btn.setEnabled(not enabled)
