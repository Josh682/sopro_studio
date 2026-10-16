"""Audio Trim Page UI — Batch and Single (interactive) modes."""

from __future__ import annotations

import logging
from pathlib import Path

from qtpy.QtCore import Qt, QUrl, QTimer
from qtpy.QtMultimedia import QMediaPlayer, QAudioOutput
from qtpy.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.processor_registry import ProcessorRegistry
from src.gui.widgets.drop_zone import DropZone
from src.gui.widgets.log_panel import LogPanel
from src.gui.widgets.progress_panel import ProgressPanel
from src.gui.widgets.trim_overlay import TrimmerWaveformContainer
from src.workers.waveform_worker import WaveformWorker, WaveformPeaks
from src.utils.config import AppConfig
from src.workers.processor_worker import ProcessorWorker
from src.gui.watermarked_page import WatermarkedPage

log = logging.getLogger("sound_processor.gui.trimmer_page")

# ── Accent colour (matches the Audio Trim home-page card) ─────────────────────
ACCENT      = "#f38ba8"   # rose / red-pink
ACCENT_DARK = "#eba0ac"   # hover shade

# ── Shared style tokens ───────────────────────────────────────────────────────
INPUT_STYLE = (
    "QLineEdit {"
    "  background-color: #313244;"
    "  color: #cdd6f4;"
    "  border: 1px solid #45475a;"
    "  border-radius: 4px;"
    "  padding: 6px 8px;"
    "  font-size: 13px;"
    "}"
    f"QLineEdit:focus {{ border: 1px solid {ACCENT}; }}"
)
LABEL_STYLE   = "color: #a6adc8; font-size: 13px;"
SECTION_STYLE = f"color: {ACCENT}; font-size: 11px; font-weight: bold; letter-spacing: 1px;"


def _hline() -> QFrame:
    d = QFrame()
    d.setFrameShape(QFrame.Shape.HLine)
    d.setStyleSheet("background-color: #313244; max-height: 1px; border: none;")
    return d


def _row(label: str, widget: QWidget, label_w: int = 120) -> QHBoxLayout:
    h = QHBoxLayout()
    h.setSpacing(10)
    lbl = QLabel(label)
    lbl.setFixedWidth(label_w)
    lbl.setStyleSheet(LABEL_STYLE)
    lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
    h.addWidget(lbl)
    h.addWidget(widget)
    return h


def _input(placeholder: str = "") -> QLineEdit:
    w = QLineEdit()
    w.setPlaceholderText(placeholder)
    w.setStyleSheet(INPUT_STYLE)
    return w


def _card() -> tuple[QFrame, QVBoxLayout]:
    f = QFrame()
    f.setStyleSheet(
        "QFrame { background-color: #1e1e2e; border: 1px solid #313244; border-radius: 8px; }"
    )
    lay = QVBoxLayout(f)
    lay.setContentsMargins(16, 12, 16, 12)
    lay.setSpacing(10)
    return f, lay


def _seconds_to_str(secs: float) -> str:
    m = int(secs) // 60
    s = secs - m * 60
    return f"{m:02d}:{s:06.3f}"


def _primary_btn(text: str) -> QPushButton:
    b = QPushButton(text)
    b.setStyleSheet(
        f"QPushButton {{ background: {ACCENT}; color: #11111b; font-weight: bold;"
        "  border-radius: 6px; padding: 9px 22px; }"
        f"QPushButton:hover {{ background: {ACCENT_DARK}; }}"
        "QPushButton:disabled { background: #313244; color: #585b70; }"
    )
    return b


def _ghost_btn(text: str) -> QPushButton:
    b = QPushButton(text)
    b.setStyleSheet(
        "QPushButton { background: #313244; color: #cdd6f4; border-radius: 6px; padding: 9px 16px; }"
        "QPushButton:hover { background: #45475a; }"
        "QPushButton:disabled { color: #585b70; }"
    )
    return b


def _danger_btn(text: str) -> QPushButton:
    b = QPushButton(text)
    b.setEnabled(False)
    b.setStyleSheet(
        f"QPushButton {{ background: {ACCENT}; color: #11111b; font-weight: bold;"
        "  border-radius: 6px; padding: 9px 16px; }"
        f"QPushButton:hover {{ background: {ACCENT_DARK}; }}"
        "QPushButton:disabled { background: #313244; color: #585b70; }"
    )
    return b


# ── Batch Mode pane ───────────────────────────────────────────────────────────

class _BatchPane(QWidget):
    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._files: list[Path] = []
        self._worker: ProcessorWorker | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        # ── Drop Zone (no wrapper card — it has its own border/bg) ───────────
        self._drop_zone = DropZone()
        self._drop_zone.setText("✂️  Drop audio files or a folder here")
        self._drop_zone.setMaximumHeight(90)
        self._drop_zone.filesDropped.connect(self._on_drop)
        root.addWidget(self._drop_zone)

        # ── Selected files card ───────────────────────────────────────────────
        files_card, fly = _card()
        files_hdr = QHBoxLayout()
        files_lbl = QLabel("SELECTED FILES")
        files_lbl.setStyleSheet(SECTION_STYLE)
        self._count_lbl = QLabel("0 files")
        self._count_lbl.setStyleSheet("color: #585b70; font-size: 11px;")
        self._count_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        files_hdr.addWidget(files_lbl)
        files_hdr.addWidget(self._count_lbl)
        fly.addLayout(files_hdr)
        self._file_list = QListWidget()
        self._file_list.setMaximumHeight(64)
        self._file_list.setStyleSheet(
            "QListWidget { background-color: #181825; border: 1px solid #313244;"
            "  border-radius: 4px; color: #cdd6f4; font-size: 12px; padding: 3px; }"
            "QListWidget::item { padding: 2px 4px; }"
        )
        fly.addWidget(self._file_list)
        root.addWidget(files_card)

        # ── Trim Settings card ────────────────────────────────────────────────
        trim_card, tly = _card()
        section_lbl = QLabel("TRIM SETTINGS")
        section_lbl.setStyleSheet(SECTION_STYLE)
        tly.addWidget(section_lbl)
        tly.addWidget(_hline())

        self._start = _input("e.g. 0.0")
        self._end   = _input("e.g. 5.0")
        self._fi    = _input("e.g. 500  (optional)")
        self._fo    = _input("e.g. 500  (optional)")
        tly.addLayout(_row("Start Time (s):", self._start))
        tly.addLayout(_row("End Time (s):",   self._end))
        tly.addLayout(_row("Fade In (ms):",   self._fi))
        tly.addLayout(_row("Fade Out (ms):",  self._fo))

        tly.addWidget(_hline())
        out_row = QHBoxLayout()
        out_row.setSpacing(8)
        out_lbl = QLabel("Output:")
        out_lbl.setFixedWidth(120)
        out_lbl.setStyleSheet(LABEL_STYLE)
        self._out_edit = QLineEdit(str(self._config.output_dir))
        self._out_edit.setReadOnly(True)
        self._out_edit.setStyleSheet(INPUT_STYLE)
        browse_btn = _ghost_btn("Browse…")
        browse_btn.setFixedWidth(80)
        browse_btn.setStyleSheet(
            "QPushButton { background: #313244; color: #cdd6f4; border-radius: 4px; padding: 5px 8px; }"
            "QPushButton:hover { background: #45475a; }"
        )
        browse_btn.clicked.connect(self._browse_out)
        out_row.addWidget(out_lbl)
        out_row.addWidget(self._out_edit)
        out_row.addWidget(browse_btn)
        tly.addLayout(out_row)
        root.addWidget(trim_card)

        # ── Actions ───────────────────────────────────────────────────────────
        act = QHBoxLayout()
        act.setSpacing(8)
        self._go_btn = _primary_btn("Trim All Files")
        self._cancel_btn = _danger_btn("Cancel")
        self._clear_btn = _ghost_btn("Clear")
        self._cancel_btn.setEnabled(False)
        act.addWidget(self._go_btn)
        act.addWidget(self._cancel_btn)
        act.addWidget(self._clear_btn)
        act.addStretch()
        root.addLayout(act)

        self._progress = ProgressPanel()
        root.addWidget(self._progress)
        self._log = LogPanel()
        self._log.setMinimumHeight(70)
        root.addWidget(self._log)

        self._go_btn.clicked.connect(self._start_batch)
        self._cancel_btn.clicked.connect(self._cancel)
        self._clear_btn.clicked.connect(self._clear)

    def _on_drop(self, paths: list[Path]) -> None:
        for p in paths:
            if p.is_dir():
                for ext in [".wav", ".mp3", ".flac", ".ogg", ".m4a"]:
                    for f in p.rglob(f"*{ext}"):
                        if f not in self._files:
                            self._files.append(f)
            elif p.is_file() and p not in self._files:
                self._files.append(p)
        if self._files:
            self._file_list.clear()
            for f in self._files:
                self._file_list.addItem(f.name)
            n = len(self._files)
            self._count_lbl.setText(f"{n} file{'s' if n != 1 else ''}")
            self._log.append_log(f"Added {n} file(s). Ready to trim.")

    def _clear(self) -> None:
        self._files.clear()
        self._file_list.clear()
        self._count_lbl.setText("0 files")
        for w in (self._start, self._end, self._fi, self._fo):
            w.clear()
        self._log.clear_logs()

    def _browse_out(self) -> None:
        p = QFileDialog.getExistingDirectory(self, "Select Output Directory", str(self._config.output_dir))
        if p:
            self._config.output_dir = Path(p)
            self._out_edit.setText(p)

    def _start_batch(self) -> None:
        if not self._files:
            self._log.append_error("Please add files before processing.")
            return
        options: dict = {}
        try:
            s = self._start.text().strip()
            e = self._end.text().strip()
            if not s or not e:
                raise ValueError("Start Time and End Time are required.")
            options["start_sec"] = float(s)
            options["end_sec"]   = float(e)
            if self._fi.text().strip():
                options["fade_in_ms"] = float(self._fi.text())
            if self._fo.text().strip():
                options["fade_out_ms"] = float(self._fo.text())
        except ValueError as ex:
            self._log.append_error(f"Invalid input: {ex}")
            return
        self._set_enabled(False)
        self._progress.start_job(f"Trimming {len(self._files)} file(s)…")
        self._log.clear_logs()
        processor = ProcessorRegistry.get_processor("audio_trimmer")
        self._worker = ProcessorWorker(processor, self._files.copy(), self._config.output_dir, options)
        self._worker.signals.progress.connect(self._progress.set_progress)
        self._worker.signals.log.connect(self._log.append_log)
        self._worker.signals.error.connect(self._log.append_error)
        self._worker.signals.finished.connect(self._on_done)
        self._worker.finished.connect(lambda: setattr(self, "_worker", None))
        self._worker.start()

    def _cancel(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._cancel_btn.setEnabled(False)
            self._log.append_log("Cancellation requested…")

    def _on_done(self, results: dict) -> None:
        cancelled = self._worker is not None and self._worker._cancel_flag.is_set()
        self._set_enabled(True)
        if not cancelled and results:
            self._progress.finish_job(True, "Batch trim complete!")
        elif cancelled:
            self._progress.finish_job(False, "Cancelled.")
        else:
            self._progress.finish_job(False, "Processing failed.")

    def _set_enabled(self, v: bool) -> None:
        for w in (self._drop_zone, self._start, self._end, self._fi, self._fo,
                  self._go_btn, self._clear_btn):
            w.setEnabled(v)
        self._cancel_btn.setEnabled(not v)

    @property
    def _log_panel(self) -> LogPanel:
        return self._log


# ── Single / Interactive pane ─────────────────────────────────────────────────

class _SinglePane(QWidget):
    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._file: Path | None = None
        self._duration: float = 0.0
        self._seek_updating = False
        self._waveform_worker: WaveformWorker | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        # ── File picker card ──────────────────────────────────────────────────
        pick_card, ply = _card()
        pick_hdr = QLabel("AUDIO FILE")
        pick_hdr.setStyleSheet(SECTION_STYLE)
        ply.addWidget(pick_hdr)
        pick_row = QHBoxLayout()
        pick_row.setSpacing(8)
        self._file_lbl = QLabel("No file selected")
        self._file_lbl.setStyleSheet("color: #a6adc8; font-size: 12px;")
        self._file_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        pick_btn = QPushButton("Open File…")
        pick_btn.setFixedWidth(90)
        pick_btn.setStyleSheet(
            f"QPushButton {{ background: {ACCENT}; color: #11111b; font-weight: bold;"
            "  border-radius: 4px; padding: 5px 8px; }"
            f"QPushButton:hover {{ background: {ACCENT_DARK}; }}"
        )
        pick_btn.clicked.connect(self._pick_file)
        pick_row.addWidget(self._file_lbl)
        pick_row.addWidget(pick_btn)
        ply.addLayout(pick_row)
        root.addWidget(pick_card)

        # ── Player card ───────────────────────────────────────────────────────
        player_card, pll = _card()
        player_lbl = QLabel("AUDIO PLAYER")
        player_lbl.setStyleSheet(SECTION_STYLE)
        pll.addWidget(player_lbl)
        pll.addWidget(_hline())
        
        self._waveform = TrimmerWaveformContainer()
        self._waveform.waveform_view.seek_started.connect(self._on_seek_started)
        self._waveform.waveform_view.seek_moved.connect(self._on_seek_moved)
        self._waveform.waveform_view.seek_ended.connect(self._on_seek_ended)
        self._waveform.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)

        # Time row with waveform
        time_row = QHBoxLayout()
        self._pos_lbl = QLabel("00:00.000")
        self._pos_lbl.setStyleSheet(
            f"color: {ACCENT}; font-size: 13px; font-weight: bold;"
            " font-family: 'Courier New', 'Menlo', monospace;"
        )
        self._pos_lbl.setFixedWidth(80)
        self._pos_lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        self._dur_lbl = QLabel("00:00.000")
        self._dur_lbl.setStyleSheet(
            "color: #a6adc8; font-size: 13px;"
            " font-family: 'Courier New', 'Menlo', monospace;"
        )
        self._dur_lbl.setFixedWidth(80)
        self._dur_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        time_row.addWidget(self._pos_lbl)
        time_row.addWidget(self._waveform, 1) # Waveform takes expanding space
        time_row.addWidget(self._dur_lbl)
        pll.addLayout(time_row)

        # Controls row
        ICON_BTN = (
            "QPushButton {"
            "  background: #313244; color: #cdd6f4;"
            "  border-radius: 6px; padding: 0px; font-size: 16px;"
            "  min-width: 36px; min-height: 36px; max-width: 36px; max-height: 36px;"
            "}"
            "QPushButton:hover { background: #45475a; }"
            "QPushButton:disabled { color: #585b70; }"
        )
        PLAY_BTN = (
            f"QPushButton {{ background: {ACCENT}; color: #11111b; font-weight: bold;"
            "  border-radius: 6px; font-size: 16px;"
            "  min-width: 36px; min-height: 36px; max-width: 36px; max-height: 36px;"
            "}"
            f"QPushButton:hover {{ background: {ACCENT_DARK}; }}"
            "QPushButton:disabled { background: #313244; color: #585b70; }"
        )
        MARKER_BTN = (
            "QPushButton {"
            "  background: #313244; color: #cdd6f4;"
            f"  border: 1px solid {ACCENT};"
            "  border-radius: 6px; padding: 5px 12px;"
            "  font-size: 12px; min-height: 36px;"
            "}"
            "QPushButton:hover { background: #45475a; }"
            "QPushButton:disabled { border-color: #313244; color: #585b70; }"
        )

        self._back10_btn    = QPushButton("⏪︎")
        self._rewind_btn    = QPushButton("⏮︎")
        self._play_btn      = QPushButton("▶︎")
        self._stop_btn      = QPushButton("■︎")
        self._fwd10_btn     = QPushButton("⏩︎")
        self._set_start_btn = QPushButton("📍 Set Trim Start")
        self._set_end_btn   = QPushButton("📍 Set Trim End")

        self._back10_btn.setStyleSheet(ICON_BTN)
        self._rewind_btn.setStyleSheet(ICON_BTN)
        self._play_btn.setStyleSheet(PLAY_BTN)
        self._stop_btn.setStyleSheet(ICON_BTN)
        self._fwd10_btn.setStyleSheet(ICON_BTN)
        self._set_start_btn.setStyleSheet(MARKER_BTN)
        self._set_end_btn.setStyleSheet(MARKER_BTN)

        self._back10_btn.setToolTip("Back 10 seconds")
        self._rewind_btn.setToolTip("Rewind to start")
        self._play_btn.setToolTip("Play / Pause")
        self._stop_btn.setToolTip("Stop")
        self._fwd10_btn.setToolTip("Forward 10 seconds")

        transport_btns = (
            self._back10_btn, self._rewind_btn, self._play_btn,
            self._stop_btn, self._fwd10_btn,
            self._set_start_btn, self._set_end_btn,
        )
        for b in transport_btns:
            b.setEnabled(False)

        self._back10_btn.clicked.connect(self._back10)
        self._rewind_btn.clicked.connect(self._rewind)
        self._play_btn.clicked.connect(self._toggle_play)
        self._stop_btn.clicked.connect(self._stop)
        self._fwd10_btn.clicked.connect(self._fwd10)
        self._set_start_btn.clicked.connect(self._mark_start)
        self._set_end_btn.clicked.connect(self._mark_end)

        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(6)
        ctrl_row.addStretch()
        for b in transport_btns:
            ctrl_row.addWidget(b)
        ctrl_row.addStretch()
        pll.addLayout(ctrl_row)
        root.addWidget(player_card)

        # ── Trim Settings card ────────────────────────────────────────────────
        trim_card, tly = _card()
        trim_lbl = QLabel("TRIM SETTINGS")
        trim_lbl.setStyleSheet(SECTION_STYLE)
        tly.addWidget(trim_lbl)
        tly.addWidget(_hline())

        self._s_start = _input("e.g. 0.000  (seconds)")
        self._s_end   = _input("e.g. 5.000  (seconds)")
        
        self._s_start.textChanged.connect(self._update_overlay_markers)
        self._s_end.textChanged.connect(self._update_overlay_markers)
        
        self._s_fi    = _input("e.g. 500  (optional)")
        self._s_fo    = _input("e.g. 500  (optional)")
        tly.addLayout(_row("Start Time (s):", self._s_start))
        tly.addLayout(_row("End Time (s):",   self._s_end))
        tly.addLayout(_row("Fade In (ms):",   self._s_fi))
        tly.addLayout(_row("Fade Out (ms):",  self._s_fo))

        tly.addWidget(_hline())
        out_row = QHBoxLayout()
        out_row.setSpacing(8)
        out_lbl = QLabel("Output:")
        out_lbl.setFixedWidth(120)
        out_lbl.setStyleSheet(LABEL_STYLE)
        self._out_edit = QLineEdit(str(self._config.output_dir))
        self._out_edit.setReadOnly(True)
        self._out_edit.setStyleSheet(INPUT_STYLE)
        browse_btn2 = QPushButton("Browse…")
        browse_btn2.setFixedWidth(80)
        browse_btn2.setStyleSheet(
            "QPushButton { background: #313244; color: #cdd6f4; border-radius: 4px; padding: 5px 8px; }"
            "QPushButton:hover { background: #45475a; }"
        )
        browse_btn2.clicked.connect(self._browse_out)
        out_row.addWidget(out_lbl)
        out_row.addWidget(self._out_edit)
        out_row.addWidget(browse_btn2)
        tly.addLayout(out_row)
        root.addWidget(trim_card)

        # ── Actions ───────────────────────────────────────────────────────────
        act = QHBoxLayout()
        act.setSpacing(8)
        self._export_btn = _primary_btn("Export Trim")
        self._export_btn.setEnabled(False)
        act.addWidget(self._export_btn)
        act.addStretch()
        root.addLayout(act)

        self._progress = ProgressPanel()
        root.addWidget(self._progress)
        self._log = LogPanel()
        self._log.setMinimumHeight(70)
        root.addWidget(self._log)

        self._export_btn.clicked.connect(self._export)

        # ── Media player ──────────────────────────────────────────────────────
        self._player = QMediaPlayer()
        self._audio_out = QAudioOutput()
        self._audio_out.setVolume(1.0)
        self._player.setAudioOutput(self._audio_out)
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.playbackStateChanged.connect(self._on_state_changed)

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(80)
        self._poll_timer.timeout.connect(self._refresh_position)

    # ── File pick ─────────────────────────────────────────────────────────────

    def _pick_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Audio File", str(self._config.output_dir),
            "Audio Files (*.wav *.mp3 *.flac *.ogg *.m4a)"
        )
        if path:
            self._load_file(Path(path))

    def _load_file(self, p: Path) -> None:
        self._stop()
        self._file = p
        self._file_lbl.setText(p.name)
        self._player.setSource(QUrl.fromLocalFile(str(p)))
        for b in (self._play_btn, self._stop_btn, self._rewind_btn,
                  self._back10_btn, self._fwd10_btn,
                  self._set_start_btn, self._set_end_btn, self._export_btn):
            b.setEnabled(True)
        self._log.append_log(f"Loaded: {p.name}")
        
        if self._waveform_worker and self._waveform_worker.isRunning():
            self._waveform_worker.cancel()
            
        self._waveform_worker = WaveformWorker(p)
        self._waveform_worker.peaks_ready.connect(self._on_peaks_ready)
        self._waveform_worker.start()

    def _on_peaks_ready(self, peaks: WaveformPeaks) -> None:
        self._waveform.waveform_view.set_peaks(peaks)
        self._update_overlay_markers()
        
    def _on_seek_started(self) -> None:
        self._seek_updating = True
        self._poll_timer.stop()

    def _on_seek_moved(self, time_sec: float) -> None:
        if self._duration > 0:
            self._pos_lbl.setText(_seconds_to_str(time_sec))
            self._waveform.overlay.set_playhead(time_sec)

    def _on_seek_ended(self, time_sec: float) -> None:
        if self._duration > 0:
            target_ms = int(time_sec * 1000)
            self._player.setPosition(target_ms)
        self._seek_updating = False
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._poll_timer.start()

    # ── Playback ──────────────────────────────────────────────────────────────

    def _toggle_play(self) -> None:
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._player.play()
            self._poll_timer.start()

    def _stop(self) -> None:
        self._player.stop()
        self._poll_timer.stop()

    def _rewind(self) -> None:
        self._player.setPosition(0)

    def _back10(self) -> None:
        self._player.setPosition(max(0, self._player.position() - 10_000))

    def _fwd10(self) -> None:
        self._player.setPosition(min(int(self._duration * 1000), self._player.position() + 10_000))

    def _on_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        playing = (state == QMediaPlayer.PlaybackState.PlayingState)
        self._play_btn.setText("⏸︎" if playing else "▶︎")
        if not playing:
            self._poll_timer.stop()

    def _on_position_changed(self, pos_ms: int) -> None:
        if not self._seek_updating:
            self._update_ui_position(pos_ms)

    def _on_duration_changed(self, dur_ms: int) -> None:
        self._duration = dur_ms / 1000.0
        self._dur_lbl.setText(_seconds_to_str(self._duration))

    def _refresh_position(self) -> None:
        if self._seek_updating:
            return
        self._update_ui_position(self._player.position())

    def _update_ui_position(self, pos_ms: int) -> None:
        pos_s = pos_ms / 1000.0
        self._pos_lbl.setText(_seconds_to_str(pos_s))
        self._waveform.overlay.set_playhead(pos_s)


    # ── Trim markers ──────────────────────────────────────────────────────────

    def _update_overlay_markers(self) -> None:
        try:
            s_text = self._s_start.text().strip()
            e_text = self._s_end.text().strip()
            
            start_sec = float(s_text) if s_text else -1.0
            end_sec = float(e_text) if e_text else -1.0
            
            self._waveform.overlay.set_trim_markers(start_sec, end_sec)
        except ValueError:
            pass # Ignore invalid inputs during typing

    def _mark_start(self) -> None:
        pos = self._player.position() / 1000.0
        self._s_start.setText(f"{pos:.3f}")
        self._log.append_log(f"Trim start set to {_seconds_to_str(pos)}")

    def _mark_end(self) -> None:
        pos = self._player.position() / 1000.0
        self._s_end.setText(f"{pos:.3f}")
        self._log.append_log(f"Trim end set to {_seconds_to_str(pos)}")

    def _browse_out(self) -> None:
        p = QFileDialog.getExistingDirectory(self, "Select Output Directory", str(self._config.output_dir))
        if p:
            self._config.output_dir = Path(p)
            self._out_edit.setText(p)

    # ── Export ────────────────────────────────────────────────────────────────

    def _export(self) -> None:
        if not self._file:
            self._log.append_error("No file loaded.")
            return
        try:
            s = self._s_start.text().strip()
            e = self._s_end.text().strip()
            if not s or not e:
                raise ValueError("Set both Start Time and End Time first.")
            options: dict = {"start_sec": float(s), "end_sec": float(e)}
            if self._s_fi.text().strip():
                options["fade_in_ms"] = float(self._s_fi.text())
            if self._s_fo.text().strip():
                options["fade_out_ms"] = float(self._s_fo.text())
        except ValueError as ex:
            self._log.append_error(f"Invalid input: {ex}")
            return
        self._stop()
        self._export_btn.setEnabled(False)
        self._progress.start_job("Exporting trimmed file…")
        self._log.clear_logs()
        processor = ProcessorRegistry.get_processor("audio_trimmer")
        out_dir = Path(self._out_edit.text())
        self._worker = ProcessorWorker(processor, [self._file], out_dir, options)
        self._worker.signals.progress.connect(self._progress.set_progress)
        self._worker.signals.log.connect(self._log.append_log)
        self._worker.signals.error.connect(self._log.append_error)
        self._worker.signals.finished.connect(self._on_export_done)
        self._worker.finished.connect(lambda: setattr(self, "_worker", None))
        self._worker.start()

    def _on_export_done(self, results: dict) -> None:
        self._export_btn.setEnabled(True)
        if results:
            self._progress.finish_job(True, "Export complete!")
        else:
            self._progress.finish_job(False, "Export failed.")

    @property
    def _log_panel(self) -> LogPanel:
        return self._log


# ── Main TrimmerPage ──────────────────────────────────────────────────────────

class TrimmerPage(WatermarkedPage):
    """Audio Trim page — Batch and Single (interactive) modes."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = AppConfig()

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 20, 40, 12)
        root.setSpacing(8)

        # ── Header ────────────────────────────────────────────────────────────
        header = QLabel("Audio Trim")
        header.setStyleSheet("font-size: 24px; font-weight: bold; color: #cdd6f4;")
        root.addWidget(header)

        # ── Mode selector card ────────────────────────────────────────────────
        mode_card, mly = _card()
        mode_card.setStyleSheet(
            "QFrame { background-color: #1e1e2e; border: 1px solid #313244; border-radius: 8px; }"
        )
        mly.setContentsMargins(14, 10, 14, 10)
        mly.setSpacing(0)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(6)

        self._batch_rb  = QRadioButton("Batch Trim")
        self._single_rb = QRadioButton("Single Trim")
        self._batch_rb.setChecked(True)

        grp = QButtonGroup(self)
        grp.addButton(self._batch_rb)
        grp.addButton(self._single_rb)

        # Active tab: deep red, generous padding, indicator fully hidden
        TAB_ON = (
            "QRadioButton {"
            "  background: #e64553;"
            "  color: #ffffff;"
            "  font-weight: bold;"
            "  font-size: 13px;"
            "  border-radius: 6px;"
            "  padding: 6px 20px 6px 20px;"
            "}"
            "QRadioButton:hover { background: #f38ba8; }"
            "QRadioButton::indicator {"
            "  width: 0px; height: 0px;"
            "  border: none; background: transparent; image: none;"
            "}"
        )
        TAB_OFF = (
            "QRadioButton {"
            "  background: transparent;"
            "  color: #a6adc8;"
            "  font-size: 13px;"
            "  border-radius: 6px;"
            "  padding: 6px 20px 6px 20px;"
            "}"
            "QRadioButton:hover { background: #313244; color: #cdd6f4; }"
            "QRadioButton::indicator {"
            "  width: 0px; height: 0px;"
            "  border: none; background: transparent; image: none;"
            "}"
        )
        self._batch_rb.setStyleSheet(TAB_ON)
        self._single_rb.setStyleSheet(TAB_OFF)
        self._TAB_ON  = TAB_ON
        self._TAB_OFF = TAB_OFF

        mode_row.addWidget(self._batch_rb)
        mode_row.addWidget(self._single_rb)
        mode_row.addStretch()
        mly.addLayout(mode_row)
        root.addWidget(mode_card)

        # ── Stacked panes ─────────────────────────────────────────────────────
        self._stack = QStackedWidget()
        self._batch_pane  = _BatchPane(self._config)
        self._single_pane = _SinglePane(self._config)
        self._stack.addWidget(self._batch_pane)
        self._stack.addWidget(self._single_pane)
        root.addWidget(self._stack)

        self._batch_rb.toggled.connect(self._switch_mode)
        self._single_rb.toggled.connect(self._switch_mode)
        self._switch_mode()

    def _switch_mode(self) -> None:
        if self._batch_rb.isChecked():
            self._stack.setCurrentWidget(self._batch_pane)
            self._batch_rb.setStyleSheet(self._TAB_ON)
            self._single_rb.setStyleSheet(self._TAB_OFF)
        else:
            self._stack.setCurrentWidget(self._single_pane)
            self._batch_rb.setStyleSheet(self._TAB_OFF)
            self._single_rb.setStyleSheet(self._TAB_ON)

    @property
    def _log_panel(self) -> LogPanel:
        return self._batch_pane._log_panel
