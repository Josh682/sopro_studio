"""WorkspacePage - 4-Slot Tactile Industrial Skeuomorphic Workspace Template.

Implements DESIGN.md Section 7.1 Contract:
- Slot 1: Top Bar (48px) with [<- ESC: DASHBOARD] and Engine Status LED
- Slot 2: The Deck / Visual Stage (210px, Recessed Chassis #0A0C10)
  Now features interactive drag & drop and click-to-browse manual file selection.
- Slot 3: Hardware Control Rack (280px, Analog Chassis #11141A, 3 Clusters)
- Slot 4: Execution Footer (64px, File Status Pill + Browse Button + Reset + Primary CTA ChunkyButton)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.ui.qt import (
    QColor,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDragMoveEvent,
    QDropEvent,
    QFileDialog,
    QFont,
    QFrame,
    QHBoxLayout,
    QKeyEvent,
    QLabel,
    QMouseEvent,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QStackedWidget,
    Qt,
    QVBoxLayout,
    QWidget,
    Signal,
)

from src.audio.player import AudioPlayerController

import src.core.processors  # Ensure all processors are registered
from src.core.processors.base_processor import ParameterDescriptor
from src.core.processor_registry import ProcessorRegistry
from src.ui.components.custom_stages import (
    AnalysisStage,
    StemDeckStage,
    WaveformStage,
    create_custom_stage,
)
from src.core.task_runner import (
    AudioTask,
    AudioTaskRunner,
    TaskResult,
    get_task_runner,
)
from src.ui.components.rack_control_factory import DynamicRackController
from src.ui.theme.tokens import TOKENS, AccentToken
from src.ui.widgets.tactile_button import TactileButton
from src.utils.config import AppConfig
from src.workers.processor_worker import ProcessorWorker

log = logging.getLogger("sound_processor.ui.views.workspace_template")

MODULE_TO_PROCESSOR_ID = {
    # 9 Consolidated Modules (Option C)
    "converter": "format_converter",
    "separator": "stem_separator",
    "combiner": "track_combiner",
    "analyze": "key_detector",
    "pitch_time": "pitch_shifter",
    "edit": "audio_trimmer",
    "repair": "declip",
    "clean": "denoise",
    "voice": "voice_enhancement",
    # Backward-compatible legacy aliases
    "detect": "key_detector",
    "key_detector": "key_detector",
    "pitch": "pitch_shifter",
    "tempo": "tempo_changer",
    "trim": "audio_trimmer",
    "trimmer": "audio_trimmer",
    "normalize": "loudness_normalizer",
    "loudness": "loudness_normalizer",
    "info": "audio_analyzer",
    "metadata": "audio_analyzer",
    "metadata_editor": "audio_analyzer",
    "audio_analyzer": "audio_analyzer",
    "declip": "declip",
    "denoise": "denoise",
    "dereverb": "dereverb",
    "voice_enhancement": "voice_enhancement",
    "restoration": "restoration",
}

# Supported audio extensions for file picker and drag-and-drop
AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".aiff", ".aif", ".m4a", ".aac", ".opus", ".wma"}


def format_file_size(size_bytes: int) -> str:
    """Format byte size into human-readable representation."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


class InteractiveDeck(QFrame):
    """Interactive visual deck container with click-to-browse and drag-and-drop capabilities."""

    file_dropped = Signal(str)
    browse_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._is_hovered: bool = False
        self._drag_active: bool = False
        self._accent_color: str = TOKENS.colors.accents["converter"].base
        self._current_file: Optional[str] = None
        self._current_files: List[str] = []

        self._setup_ui()
        self._update_appearance()

    def set_accent_color(self, hex_color: str) -> None:
        """Update active accent highlight color."""
        self._accent_color = hex_color
        self._update_appearance()

    def _setup_ui(self) -> None:
        """Build deck visual contents."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 1. Main Icon / Glyph
        self.lbl_glyph = QLabel("📁", self)
        self.lbl_glyph.setFont(QFont("Arial", 28))
        self.lbl_glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_glyph.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(self.lbl_glyph)

        # 2. Primary Title / Filename
        self.lbl_title = QLabel("Select Audio File", self)
        self.lbl_title.setFont(TOKENS.typography.create_font("title_card"))
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_title.setStyleSheet(f"color: {TOKENS.colors.text.primary}; background: transparent; border: none;")
        layout.addWidget(self.lbl_title)

        # 3. Subtitle / Details
        self.lbl_subtitle = QLabel("Click anywhere to browse or drag & drop audio here", self)
        self.lbl_subtitle.setFont(TOKENS.typography.create_font("body_regular"))
        self.lbl_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_subtitle.setStyleSheet(f"color: {TOKENS.colors.text.secondary}; background: transparent; border: none;")
        layout.addWidget(self.lbl_subtitle)

        # 4. Format hint / Action Pill
        self.lbl_formats = QLabel("WAV · MP3 · FLAC · AIFF · OGG · AAC · M4A", self)
        self.lbl_formats.setFont(TOKENS.typography.create_font("data_mono_sm"))
        self.lbl_formats.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_formats.setStyleSheet(f"color: {TOKENS.colors.text.muted}; background: transparent; border: none;")
        layout.addWidget(self.lbl_formats)

    def set_file_info(self, file_path: Optional[str], multi_files: Optional[List[str]] = None) -> None:
        """Update deck presentation based on selected audio file(s)."""
        self._current_file = file_path
        self._current_files = multi_files or ([file_path] if file_path else [])

        if not self._current_file and not self._current_files:
            # Empty state
            self.lbl_glyph.setText("📁")
            self.lbl_title.setText("Select Audio File")
            self.lbl_title.setStyleSheet(f"color: {TOKENS.colors.text.primary}; background: transparent; border: none;")
            self.lbl_subtitle.setText("Click anywhere to browse or drag & drop audio here")
            self.lbl_formats.setText("WAV · MP3 · FLAC · AIFF · OGG · AAC · M4A")
            self.lbl_formats.setStyleSheet(f"color: {TOKENS.colors.text.muted}; background: transparent; border: none;")
        elif len(self._current_files) > 1:
            # Multi-file batch state
            count = len(self._current_files)
            names = [Path(f).name for f in self._current_files[:2]]
            summary = ", ".join(names) + (f" and {count - 2} more" if count > 2 else "")
            self.lbl_glyph.setText("📚")
            self.lbl_title.setText(f"{count} Audio Files Selected")
            self.lbl_title.setStyleSheet(f"color: {self._accent_color}; font-weight: bold; background: transparent; border: none;")
            self.lbl_subtitle.setText(summary)
            self.lbl_formats.setText("Click to replace selection · or drop new files")
            self.lbl_formats.setStyleSheet(f"color: {TOKENS.colors.text.muted}; background: transparent; border: none;")
        else:
            # Single file state
            p = Path(self._current_file)
            size_str = ""
            if p.is_file():
                try:
                    size_str = format_file_size(os.path.getsize(self._current_file))
                except OSError:
                    size_str = ""

            self.lbl_glyph.setText("🎵")
            self.lbl_title.setText(p.name)
            self.lbl_title.setStyleSheet(f"color: {self._accent_color}; font-weight: bold; background: transparent; border: none;")
            meta_details = f"{p.suffix.upper()[1:]} Audio"
            if size_str:
                meta_details += f" · {size_str}"
            meta_details += " · Ready for Processing"
            self.lbl_subtitle.setText(meta_details)
            self.lbl_formats.setText("Click anywhere to choose a different file")
            self.lbl_formats.setStyleSheet(f"color: {TOKENS.colors.text.muted}; background: transparent; border: none;")

        self._update_appearance()

    def _update_appearance(self) -> None:
        """Update border and background styling based on hover and drag states."""
        if self._drag_active:
            border = f"2px dashed {self._accent_color}"
            bg = "#1F1710"
        elif self._is_hovered:
            border = f"1px dashed {self._accent_color}"
            bg = "#17120D"
        else:
            border = f"1px dashed {TOKENS.colors.border.subtle}"
            bg = "#120E0B"

        self.setStyleSheet(
            f"InteractiveDeck {{"
            f"  background-color: {bg};"
            f"  border: {border};"
            f"  border-radius: 8px;"
            f"}}"
        )

    # --- Mouse Click to Browse ---

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Trigger file selection dialog on left mouse button click."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.browse_requested.emit()
            event.accept()
        else:
            super().mousePressEvent(event)

    def enterEvent(self, event) -> None:
        self._is_hovered = True
        self._update_appearance()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._is_hovered = False
        self._update_appearance()
        super().leaveEvent(event)

    # --- Drag & Drop ---

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    suffix = Path(url.toLocalFile()).suffix.lower()
                    if suffix in AUDIO_EXTENSIONS:
                        self._drag_active = True
                        self._update_appearance()
                        event.acceptProposedAction()
                        return
        event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if self._drag_active:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self._drag_active = False
        self._update_appearance()
        event.accept()

    def dropEvent(self, event: QDropEvent) -> None:
        self._drag_active = False
        self._update_appearance()
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    path = url.toLocalFile()
                    if Path(path).suffix.lower() in AUDIO_EXTENSIONS:
                        event.acceptProposedAction()
                        self.file_dropped.emit(path)
                        return
        event.ignore()


class WorkspacePage(QWidget):
    """4-Slot Workspace Template for active module editing with full file selection support."""

    # Navigation & file signals
    back_requested = Signal()
    file_selected = Signal(str, str)  # (module_id, file_path)
    files_selected = Signal(str, list)  # (module_id, list_of_paths)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._current_module_id: str = "converter"
        self._current_module_info: Dict[str, Any] = {}
        self._current_file: Optional[str] = None
        self._current_files: List[str] = []

        self._rack_controller = DynamicRackController()
        self._task_runner = get_task_runner()
        self._current_task: Optional[AudioTask] = None
        self._worker: Optional[ProcessorWorker] = None  # Backward-compat alias
        self._custom_stage_widget: Optional[QWidget] = None
        self._submode: Optional[str] = None
        self._active_processor_id: Optional[str] = None

        # Native Audio Playback Engine
        self._player = AudioPlayerController(self)
        self._player.positionChanged.connect(self._on_player_position_changed)
        self._player.stateChanged.connect(self._on_player_state_changed)
        self._player.timecodeUpdated.connect(self._on_player_timecode_updated)

        # Real-time Ballistic Audio Metering Engine
        from src.audio.metering import AudioMeterEngine
        self._meter_engine = AudioMeterEngine(self)
        self._meter_engine.levelsUpdated.connect(self._on_meter_levels_updated)
        self._meter_engine.ballisticsUpdated.connect(self._on_meter_ballistics_updated)
        self._meter_engine.clipDetected.connect(self._on_meter_clip_detected)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Construct the 4-slot vertical workspace architecture."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 8, 16, 16)
        main_layout.setSpacing(10)

        # =========================================================================
        # SLOT 1: TOP BAR (Height: 48px)
        # =========================================================================
        self.slot1_topbar = QFrame(self)
        self.slot1_topbar.setFixedHeight(TOKENS.dimensions.workspace.slot1_topbar_height)  # 48px
        self.slot1_topbar.setStyleSheet(
            f"background-color: {TOKENS.colors.background.app};"
            f"border-bottom: 1px solid {TOKENS.colors.border.subtle};"
        )
        topbar_layout = QHBoxLayout(self.slot1_topbar)
        topbar_layout.setContentsMargins(8, 0, 8, 0)

        # Back Button: [<- ESC: DASHBOARD]
        self.btn_back = QPushButton("←  ESC : DASHBOARD", self.slot1_topbar)
        self.btn_back.setFont(TOKENS.typography.create_font("data_mono_sm"))
        self.btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_back.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: {TOKENS.colors.background.surface_card};"
            f"  color: {TOKENS.colors.text.secondary};"
            f"  border: 1px solid {TOKENS.colors.border.card};"
            f"  border-radius: {TOKENS.radii.sm}px;"
            f"  padding: 6px 12px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: {TOKENS.colors.background.surface_card_hover};"
            f"  color: {TOKENS.colors.text.primary};"
            f"  border-color: {TOKENS.colors.border.card_hover};"
            f"}}"
        )
        self.btn_back.clicked.connect(self.back_requested.emit)
        topbar_layout.addWidget(self.btn_back)

        topbar_layout.addStretch()

        # Center: Module Title
        self.lbl_module_header = QLabel("AUDIO CONVERTER", self.slot1_topbar)
        self.lbl_module_header.setFont(TOKENS.typography.create_font("title_h1"))
        self.lbl_module_header.setStyleSheet(
            f"color: {TOKENS.colors.accents['converter'].base}; font-weight: 700; letter-spacing: 0.5px;"
        )
        topbar_layout.addWidget(self.lbl_module_header)

        topbar_layout.addStretch()

        # Right: Engine Status LED
        engine_status_layout = QHBoxLayout()
        engine_status_layout.setSpacing(6)
        self.lbl_led_dot = QLabel("●", self.slot1_topbar)
        self.lbl_led_dot.setFont(QFont("Arial", 9))
        self.lbl_led_dot.setStyleSheet(f"color: {TOKENS.colors.semantic.success};")
        engine_status_layout.addWidget(self.lbl_led_dot)

        self.lbl_engine_status = QLabel("COREAUDIO · 48 kHz", self.slot1_topbar)
        self.lbl_engine_status.setFont(TOKENS.typography.create_font("data_mono_sm"))
        self.lbl_engine_status.setStyleSheet(f"color: {TOKENS.colors.text.muted};")
        engine_status_layout.addWidget(self.lbl_engine_status)

        topbar_layout.addLayout(engine_status_layout)
        main_layout.addWidget(self.slot1_topbar)

        # =========================================================================
        # SLOT 2: THE DECK / VISUAL STAGE (Height: 210px, Recessed Chassis)
        # =========================================================================
        self.slot2_deck = QFrame(self)
        self.slot2_deck.setFixedHeight(TOKENS.dimensions.workspace.slot2_deck_height)  # 210px
        self.slot2_deck.setStyleSheet(
            f"QFrame {{"
            f"  background-color: {TOKENS.colors.background.surface_well};"
            f"  border: 1px solid {TOKENS.colors.border.subtle};"
            f"  border-radius: {TOKENS.radii.md}px;"
            f"}}"
        )
        deck_layout = QVBoxLayout(self.slot2_deck)
        deck_layout.setContentsMargins(20, 14, 20, 14)
        deck_layout.setSpacing(8)

        # Deck stage header
        deck_header = QHBoxLayout()
        deck_header.setSpacing(10)
        self.lbl_deck_title = QLabel("VISUAL STAGE / DECK MONITOR", self.slot2_deck)
        self.lbl_deck_title.setFont(TOKENS.typography.create_font("data_mono_sm"))
        self.lbl_deck_title.setStyleSheet(f"color: {TOKENS.colors.text.muted}; background: transparent; border: none;")
        deck_header.addWidget(self.lbl_deck_title)

        deck_header.addStretch()

        # Slot 2 Deck Transport Bar Controls
        transport_container = QFrame(self.slot2_deck)
        transport_container.setStyleSheet("background: transparent; border: none;")
        tb_layout = QHBoxLayout(transport_container)
        tb_layout.setContentsMargins(0, 0, 0, 0)
        tb_layout.setSpacing(4)

        transport_btn_style = (
            f"QPushButton {{"
            f"  background-color: {TOKENS.colors.background.surface_card};"
            f"  color: {TOKENS.colors.text.primary};"
            f"  border: 1px solid {TOKENS.colors.border.card};"
            f"  border-radius: 4px;"
            f"  font-size: 11px;"
            f"  font-weight: bold;"
            f"  padding: 2px 8px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: {TOKENS.colors.background.surface_card_hover};"
            f"  border-color: #F59E0B;"
            f"  color: #F59E0B;"
            f"}}"
            f"QPushButton:checked {{"
            f"  background-color: #2D1E10;"
            f"  border-color: #F59E0B;"
            f"  color: #F59E0B;"
            f"}}"
            f"QPushButton:pressed {{"
            f"  background-color: #120E0B;"
            f"}}"
        )

        self.btn_transport_play = QPushButton("▶", transport_container)
        self.btn_transport_play.setFixedSize(30, 22)
        self.btn_transport_play.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_transport_play.setToolTip("Play / Pause (Spacebar)")
        self.btn_transport_play.setStyleSheet(transport_btn_style)
        self.btn_transport_play.clicked.connect(self._toggle_playback)
        tb_layout.addWidget(self.btn_transport_play)

        self.btn_transport_stop = QPushButton("■", transport_container)
        self.btn_transport_stop.setFixedSize(26, 22)
        self.btn_transport_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_transport_stop.setToolTip("Stop & Rewind")
        self.btn_transport_stop.setStyleSheet(transport_btn_style)
        self.btn_transport_stop.clicked.connect(self._stop_playback)
        tb_layout.addWidget(self.btn_transport_stop)

        self.btn_transport_loop = QPushButton("🔁", transport_container)
        self.btn_transport_loop.setFixedSize(28, 22)
        self.btn_transport_loop.setCheckable(True)
        self.btn_transport_loop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_transport_loop.setToolTip("Toggle Selection Looping")
        self.btn_transport_loop.setStyleSheet(transport_btn_style)
        self.btn_transport_loop.clicked.connect(self._toggle_loop)
        tb_layout.addWidget(self.btn_transport_loop)

        tb_layout.addSpacing(4)

        self.lbl_timecode = QLabel("00:00.00 / 00:00.00", transport_container)
        self.lbl_timecode.setFont(TOKENS.typography.create_font("data_mono_sm"))
        self.lbl_timecode.setStyleSheet(
            f"color: {TOKENS.colors.text.display_readout};"
            f"background-color: {TOKENS.colors.background.surface_display_glass};"
            f"border: 1px solid rgba(255, 255, 255, 0.08);"
            f"border-radius: 3px;"
            f"padding: 2px 8px;"
        )
        tb_layout.addWidget(self.lbl_timecode)

        # Telemetry RMS level & Peak Overload Indicator
        self.lbl_meter_level = QLabel("-∞ dB", transport_container)
        self.lbl_meter_level.setFont(TOKENS.typography.create_font("data_mono_sm"))
        self.lbl_meter_level.setToolTip("Live RMS Audio Level")
        self.lbl_meter_level.setStyleSheet(
            f"color: {TOKENS.colors.text.muted};"
            f"background-color: {TOKENS.colors.background.surface_display_glass};"
            f"border: 1px solid rgba(255, 255, 255, 0.08);"
            f"border-radius: 3px;"
            f"padding: 2px 6px;"
        )
        tb_layout.addWidget(self.lbl_meter_level)

        self.lbl_peak_led = QLabel("PK", transport_container)
        self.lbl_peak_led.setFont(TOKENS.typography.create_font("data_mono_sm"))
        self.lbl_peak_led.setToolTip("Peak Overload Clip Indicator (> -0.1 dBFS)")
        self.lbl_peak_led.setStyleSheet(
            "color: #4A1A1A; background-color: #1A0D0D; border: 1px solid #3A1414; border-radius: 3px; padding: 2px 5px;"
        )
        tb_layout.addWidget(self.lbl_peak_led)

        deck_header.addWidget(transport_container)
        deck_header.addSpacing(8)

        self.lbl_deck_badge = QLabel("READY", self.slot2_deck)
        self.lbl_deck_badge.setFont(TOKENS.typography.create_font("data_mono_sm"))
        self.lbl_deck_badge.setStyleSheet(
            f"color: {TOKENS.colors.semantic.success}; background: transparent; border: none;"
        )
        deck_header.addWidget(self.lbl_deck_badge)
        deck_layout.addLayout(deck_header)

        # Interactive Deck Target & Custom Stages via QStackedWidget
        self.deck_stack = QStackedWidget(self.slot2_deck)
        self.deck_stack.setStyleSheet("background: transparent; border: none;")

        self.interactive_deck = InteractiveDeck(self.deck_stack)
        self.interactive_deck.browse_requested.connect(self.open_file_dialog)
        self.interactive_deck.file_dropped.connect(self.load_file)
        self.deck_stack.addWidget(self.interactive_deck)

        deck_layout.addWidget(self.deck_stack)
        main_layout.addWidget(self.slot2_deck)

        # =========================================================================
        # SLOT 3: HARDWARE CONTROL RACK (Height: 280px, 3 Control Clusters)
        # =========================================================================
        self.slot3_rack = QFrame(self)
        self.slot3_rack.setFixedHeight(TOKENS.dimensions.workspace.slot3_rack_height)  # 280px
        self.slot3_rack.setStyleSheet(
            f"QFrame {{"
            f"  background-color: {TOKENS.colors.background.surface_rack};"
            f"  border: 1px solid {TOKENS.colors.border.subtle};"
            f"  border-radius: {TOKENS.radii.md}px;"
            f"}}"
        )
        rack_layout = QHBoxLayout(self.slot3_rack)
        rack_layout.setContentsMargins(16, 16, 16, 16)
        rack_layout.setSpacing(14)

        # Cluster A: Primary Controls
        self.cluster_a, self.cluster_a_layout, self.cluster_a_header = self._create_cluster_panel("CLUSTER A : PRIMARY PARAMETERS")
        rack_layout.addWidget(self.cluster_a, 4)

        # Cluster B: Secondary Controls
        self.cluster_b, self.cluster_b_layout, self.cluster_b_header = self._create_cluster_panel("CLUSTER B : ENGINE FILTERS")
        rack_layout.addWidget(self.cluster_b, 4)

        # Cluster C: Presets & Targets
        self.cluster_c, self.cluster_c_layout, self.cluster_c_header = self._create_cluster_panel("CLUSTER C : PRESETS")
        rack_layout.addWidget(self.cluster_c, 3)

        main_layout.addWidget(self.slot3_rack)

        # =========================================================================
        # SLOT 4: EXECUTION FOOTER (Height: 64px, Fixed Bottom Bar)
        # =========================================================================
        self.slot4_footer = QFrame(self)
        self.slot4_footer.setFixedHeight(TOKENS.dimensions.workspace.slot4_footer_height)  # 64px
        self.slot4_footer.setStyleSheet(
            f"QFrame {{"
            f"  background-color: {TOKENS.colors.background.surface_card};"
            f"  border: 1px solid {TOKENS.colors.border.card};"
            f"  border-radius: {TOKENS.radii.md}px;"
            f"}}"
        )
        footer_layout = QHBoxLayout(self.slot4_footer)
        footer_layout.setContentsMargins(16, 8, 16, 8)
        footer_layout.setSpacing(12)

        # File Status Pill (Clickable to browse files as well)
        self.lbl_file_pill = QLabel("NO FILE LOADED · CLICK BROWSE OR DROP AUDIO", self.slot4_footer)
        self.lbl_file_pill.setFont(TOKENS.typography.create_font("data_mono_sm"))
        self.lbl_file_pill.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lbl_file_pill.setToolTip("Click to browse audio files")
        self.lbl_file_pill.setStyleSheet(
            f"background-color: {TOKENS.colors.background.surface_well};"
            f"color: {TOKENS.colors.text.secondary};"
            f"border: 1px solid {TOKENS.colors.border.subtle};"
            f"border-radius: {TOKENS.radii.sm}px;"
            f"padding: 8px 14px;"
        )
        # Enable clicking on the file pill to open file dialog
        self.lbl_file_pill.mousePressEvent = lambda e: self.open_file_dialog() if e.button() == Qt.MouseButton.LeftButton else None
        footer_layout.addWidget(self.lbl_file_pill)

        # Dedicated Tactile Manual File Picker Button: [Browse File...]
        self.btn_browse = QPushButton("📁 Browse File...", self.slot4_footer)
        self.btn_browse.setFont(TOKENS.typography.create_font("body_regular"))
        self.btn_browse.setFixedHeight(38)
        self.btn_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_browse.setToolTip("Open file selection dialog")
        self.btn_browse.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: {TOKENS.colors.background.surface_rack};"
            f"  color: {TOKENS.colors.text.primary};"
            f"  border: 1px solid {TOKENS.colors.border.card};"
            f"  border-radius: {TOKENS.radii.md}px;"
            f"  padding: 0 16px;"
            f"  font-weight: 500;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: {TOKENS.colors.background.surface_card_hover};"
            f"  border-color: {TOKENS.colors.border.card_hover};"
            f"  color: {TOKENS.colors.text.primary};"
            f"}}"
            f"QPushButton:pressed {{"
            f"  background-color: {TOKENS.colors.background.surface_well};"
            f"}}"
        )
        self.btn_browse.clicked.connect(self.open_file_dialog)
        footer_layout.addWidget(self.btn_browse)

        footer_layout.addStretch()

        # Secondary Button: Reset Defaults / Clear File
        self.btn_reset = QPushButton("Reset Defaults", self.slot4_footer)
        self.btn_reset.setFont(TOKENS.typography.create_font("body_regular"))
        self.btn_reset.setFixedHeight(38)
        self.btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reset.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: transparent;"
            f"  color: {TOKENS.colors.text.secondary};"
            f"  border: 1px solid {TOKENS.colors.border.card};"
            f"  border-radius: {TOKENS.radii.md}px;"
            f"  padding: 0 16px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: {TOKENS.colors.background.surface_card_hover};"
            f"  color: {TOKENS.colors.text.primary};"
            f"  border-color: {TOKENS.colors.border.card_hover};"
            f"}}"
        )
        self.btn_reset.clicked.connect(self.reset_file_and_params)
        footer_layout.addWidget(self.btn_reset)

        # Primary Action CTA Button (TactileButton, 44px footer height)
        self.btn_action_cta = TactileButton(
            text="EXECUTE ACTION",
            accent_key="converter",
            face_height=TOKENS.dimensions.button.workspace_footer_height,  # 44px
            parent=self.slot4_footer,
        )
        self.btn_action_cta.setMinimumWidth(180)
        self.btn_action_cta.clicked.connect(self.execute_action)
        footer_layout.addWidget(self.btn_action_cta)

        main_layout.addWidget(self.slot4_footer)

    def _create_cluster_panel(self, cluster_title: str) -> tuple[QFrame, QVBoxLayout, QLabel]:
        """Helper to create an analog hardware rack cluster panel."""
        panel = QFrame(self.slot3_rack)
        panel.setStyleSheet(
            f"QFrame {{"
            f"  background-color: #17100B;"
            f"  border: 1px solid rgba(255, 255, 255, 0.05);"
            f"  border-radius: 6px;"
            f"}}"
        )
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)

        header = QLabel(cluster_title, panel)
        header.setFont(TOKENS.typography.create_font("data_mono_sm"))
        header.setStyleSheet(f"color: {TOKENS.colors.text.muted}; background: transparent; border: none;")
        layout.addWidget(header)

        # Cluster body
        body = QFrame(panel)
        body.setStyleSheet("border: none; background: transparent;")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(body)
        return panel, body_layout, header

    # --- Manual File Picker & Buffer Management ---

    def open_file_dialog(self) -> None:
        """Open system native file selection dialog to choose audio file(s) manually."""
        ext_list = [f"*{ext}" for ext in sorted(AUDIO_EXTENSIONS)]
        filter_str = f"Audio Files ({' '.join(ext_list)});;All Files (*)"
        title = f"Select Audio File — {self._current_module_info.get('title', 'Audio')}"

        # If module supports batch operations (e.g. converter, combiner), allow multiple file selection
        if self._current_module_id in ("converter", "combiner"):
            files, _ = QFileDialog.getOpenFileNames(self, title, "", filter_str)
            if files:
                self.load_files(files)
        else:
            file_path, _ = QFileDialog.getOpenFileName(self, title, "", filter_str)
            if file_path:
                self.load_file(file_path)

    def load_file(self, file_path: str) -> None:
        """Load a single audio file into workspace buffer."""
        self._current_file = file_path
        self._current_files = [file_path]
        self._update_file_display()

        # Load into audio transport player & metering engine
        self._player.load(file_path)
        self._meter_engine.load_file(file_path)

        if self._custom_stage_widget is not None:
            if isinstance(self._custom_stage_widget, WaveformStage):
                self._custom_stage_widget.load_audio_preview(file_path)
                self._player.set_loop(
                    self.btn_transport_loop.isChecked(),
                    self._custom_stage_widget._start_sec,
                    self._custom_stage_widget._end_sec,
                )
            self.deck_stack.setCurrentIndex(1)

        self.file_selected.emit(self._current_module_id, file_path)

    def load_files(self, file_paths: List[str]) -> None:
        """Load multiple audio files into workspace buffer."""
        if not file_paths:
            return
        self._current_files = list(file_paths)
        self._current_file = file_paths[0]
        self._update_file_display()

        # Load primary track into audio transport player & metering engine
        self._player.load(self._current_file)
        self._meter_engine.load_file(self._current_file)

        if self._custom_stage_widget is not None:
            if isinstance(self._custom_stage_widget, WaveformStage):
                self._custom_stage_widget.load_audio_preview(self._current_file)
                self._player.set_loop(
                    self.btn_transport_loop.isChecked(),
                    self._custom_stage_widget._start_sec,
                    self._custom_stage_widget._end_sec,
                )
            self.deck_stack.setCurrentIndex(1)

        self.files_selected.emit(self._current_module_id, self._current_files)
        self.file_selected.emit(self._current_module_id, self._current_file)

    def reset_file_and_params(self) -> None:
        """Reset loaded audio file and restore defaults."""
        self._player.stop()
        self._meter_engine.reset()
        if self._current_task is not None and self._current_task.is_running:
            self._current_task.cancel()
        if self._worker is not None and hasattr(self._worker, "cancel"):
            self._worker.cancel()
        self._current_file = None
        self._current_files.clear()
        self._rack_controller.reset_to_defaults()
        self._update_file_display()
        self.lbl_timecode.setText("00:00.00 / 00:00.00")
        self.lbl_meter_level.setText("-∞ dB")
        self.lbl_peak_led.setStyleSheet(
            "color: #4A1A1A; background-color: #1A0D0D; border: 1px solid #3A1414; border-radius: 3px; padding: 2px 5px;"
        )
        self.deck_stack.setCurrentIndex(0)

    def _update_file_display(self) -> None:
        """Refresh deck and footer displays with the active buffer state."""
        accent_key = self._current_module_info.get("accent_key", "converter")
        accent = TOKENS.colors.accents.get(accent_key, TOKENS.colors.accents["converter"])

        self.interactive_deck.set_accent_color(accent.base)
        self.interactive_deck.set_file_info(self._current_file, self._current_files)

        if not self._current_file and not self._current_files:
            self.lbl_file_pill.setText("NO FILE LOADED · CLICK BROWSE OR DROP AUDIO")
            self.lbl_file_pill.setStyleSheet(
                f"background-color: {TOKENS.colors.background.surface_well};"
                f"color: {TOKENS.colors.text.secondary};"
                f"border: 1px solid {TOKENS.colors.border.subtle};"
                f"border-radius: {TOKENS.radii.sm}px;"
                f"padding: 8px 14px;"
            )
            self.lbl_deck_badge.setText("READY")
            self.lbl_deck_badge.setStyleSheet(
                f"color: {TOKENS.colors.semantic.success}; background: transparent; border: none;"
            )
        elif len(self._current_files) > 1:
            count = len(self._current_files)
            first_name = Path(self._current_files[0]).name
            self.lbl_file_pill.setText(f"{count} FILES: {first_name} (+{count - 1}) · READY")
            self.lbl_file_pill.setStyleSheet(
                f"background-color: {TOKENS.colors.background.surface_well};"
                f"color: {accent.base};"
                f"border: 1px solid {accent.base};"
                f"border-radius: {TOKENS.radii.sm}px;"
                f"padding: 8px 14px;"
            )
            self.lbl_deck_badge.setText("BUFFER LOADED")
            self.lbl_deck_badge.setStyleSheet(
                f"color: {accent.base}; background: transparent; border: none;"
            )
        else:
            filename = Path(self._current_file).name
            size_str = ""
            try:
                size_str = format_file_size(os.path.getsize(self._current_file))
            except OSError:
                pass
            info_suffix = f" ({size_str})" if size_str else ""
            self.lbl_file_pill.setText(f"FILE: {filename}{info_suffix} · READY")
            self.lbl_file_pill.setStyleSheet(
                f"background-color: {TOKENS.colors.background.surface_well};"
                f"color: {accent.base};"
                f"border: 1px solid {accent.base};"
                f"border-radius: {TOKENS.radii.sm}px;"
                f"padding: 8px 14px;"
            )
            self.lbl_deck_badge.setText("BUFFER LOADED")
            self.lbl_deck_badge.setStyleSheet(
                f"color: {accent.base}; background: transparent; border: none;"
            )

    # --- Dynamic Rack & Custom Stages ---

    def _get_module_descriptors(self) -> List[ParameterDescriptor]:
        """Return parameter descriptors dynamically tailored to the module or submode."""
        mod = self._current_module_id
        if mod == "analyze":
            return [
                ParameterDescriptor(name="detect_key", label="Detect Musical Key", type="bool", default=True, tooltip="Analyze musical key and Camelot harmonic scale."),
                ParameterDescriptor(name="detect_bpm", label="Detect Tempo (BPM)", type="bool", default=True, tooltip="Analyze beats per minute and rhythm grid."),
                ParameterDescriptor(name="calc_lufs", label="Measure EBU R128 LUFS", type="bool", default=True, tooltip="Calculate integrated LUFS and loudness range."),
                ParameterDescriptor(name="calc_peaks", label="Calculate True Peak", type="bool", default=True, tooltip="Calculate maximum sample and true peak decibels."),
            ]
        elif mod in ("pitch_time", "pitch", "tempo"):
            if not self._submode:
                self._submode = "tempo" if mod == "tempo" else "pitch"
            mode_desc = ParameterDescriptor(
                name="lab_mode",
                label="Lab Engine",
                type="choice",
                choices=["Pitch Shift", "Tempo Stretch"],
                default="Pitch Shift" if self._submode == "pitch" else "Tempo Stretch",
                tooltip="Toggle between Pitch Shifting and Tempo Stretching engines.",
            )
            proc = "pitch_shifter" if self._submode == "pitch" else "tempo_changer"
            cls = ProcessorRegistry.get_processor_class(proc)
            return [mode_desc] + (cls.get_parameter_descriptors() if cls else [])
        elif mod in ("edit", "trim", "trimmer"):
            cls = ProcessorRegistry.get_processor_class("audio_trimmer")
            base_descs = cls.get_parameter_descriptors() if cls else []
            norm_desc = ParameterDescriptor(
                name="normalize_output",
                label="Normalize Post-Trim",
                type="bool",
                default=False,
                tooltip="Normalize peak and loudness after trimming.",
            )
            return base_descs + [norm_desc]
        elif mod in ("repair", "declip"):
            cls = ProcessorRegistry.get_processor_class("declip")
            base_descs = cls.get_parameter_descriptors() if cls else []
            inpaint_desc = ParameterDescriptor(
                name="inpaint_clicks",
                label="Repair Clicks & Dropouts",
                type="bool",
                default=False,
                tooltip="Chain restoration de-click and dropout inpainting after declipping.",
            )
            return base_descs + [inpaint_desc]
        elif mod in ("clean", "denoise", "dereverb"):
            if not self._submode:
                self._submode = "dereverb" if mod == "dereverb" else "denoise"
            clean_desc = ParameterDescriptor(
                name="clean_mode",
                label="Filter Target",
                type="choice",
                choices=["Noise Removal", "Reverb Suppression", "Full Clean (Both)"],
                default="Noise Removal" if self._submode == "denoise" else ("Reverb Suppression" if self._submode == "dereverb" else "Full Clean (Both)"),
                tooltip="Select whether to suppress background noise, room reverb, or chain both.",
            )
            proc = "dereverb" if self._submode == "dereverb" else "denoise"
            cls = ProcessorRegistry.get_processor_class(proc)
            return [clean_desc] + (cls.get_parameter_descriptors() if cls else [])
        else:
            proc_id = MODULE_TO_PROCESSOR_ID.get(mod, mod)
            try:
                cls = ProcessorRegistry.get_processor_class(proc_id)
                return cls.get_parameter_descriptors() if cls else []
            except Exception as e:
                log.warning("Could not get parameter descriptors for module %s: %s", mod, e)
                return []

    def _on_pitch_time_mode_changed(self, new_val: str) -> None:
        """Handle user changing mode in Pitch & Time Lab."""
        new_sub = "pitch" if "pitch" in str(new_val).lower() else "tempo"
        if self._submode != new_sub:
            self._submode = new_sub
            self._active_processor_id = "pitch_shifter" if new_sub == "pitch" else "tempo_changer"
            self._update_rack_parameters()

    def _on_clean_mode_changed(self, new_val: str) -> None:
        """Handle user changing mode in Noise & Room Repair."""
        val_lower = str(new_val).lower()
        if "reverb" in val_lower:
            new_sub = "dereverb"
        elif "both" in val_lower or "full" in val_lower:
            new_sub = "both"
        else:
            new_sub = "denoise"
        if self._submode != new_sub:
            self._submode = new_sub
            self._active_processor_id = "dereverb" if new_sub == "dereverb" else "denoise"
            self._update_rack_parameters()

    def _update_rack_parameters(self) -> None:
        """Query active processor descriptors and populate Slot 3 analog rack clusters."""
        for layout in (self.cluster_a_layout, self.cluster_b_layout, self.cluster_c_layout):
            while layout.count():
                item = layout.takeAt(0)
                w = item.widget()
                if w:
                    w.deleteLater()

        accent_key = self._current_module_info.get("accent_key", "converter")
        accent = TOKENS.colors.accents.get(accent_key, TOKENS.colors.accents["converter"])
        descs = self._get_module_descriptors()

        panel_a, panel_b, panel_c = self._rack_controller.build_clusters(
            descriptors=descs,
            accent_color=accent.base,
            parent=self.slot3_rack,
        )

        self.cluster_a_layout.addWidget(panel_a)
        self.cluster_b_layout.addWidget(panel_b)
        self.cluster_c_layout.addWidget(panel_c)

        # Wire mode switcher callbacks if available
        if self._current_module_id in ("pitch_time", "pitch", "tempo"):
            mode_ctrl = self._rack_controller.controls.get("lab_mode")
            if mode_ctrl and hasattr(mode_ctrl, "choiceChanged"):
                mode_ctrl.choiceChanged.connect(self._on_pitch_time_mode_changed)
        elif self._current_module_id in ("clean", "denoise", "dereverb"):
            clean_ctrl = self._rack_controller.controls.get("clean_mode")
            if clean_ctrl and hasattr(clean_ctrl, "choiceChanged"):
                clean_ctrl.choiceChanged.connect(self._on_clean_mode_changed)

    def _update_custom_stage(self) -> None:
        """Update or switch Slot 2 custom visual stage."""
        accent_key = self._current_module_info.get("accent_key", "converter")
        accent = TOKENS.colors.accents.get(accent_key, TOKENS.colors.accents["converter"])

        if self._custom_stage_widget is not None:
            self.deck_stack.removeWidget(self._custom_stage_widget)
            self._custom_stage_widget.deleteLater()
            self._custom_stage_widget = None

        new_stage = create_custom_stage(
            module_id=self._current_module_id,
            accent_color=accent.base,
            parent=self.slot2_deck,
        )

        if new_stage is not None:
            self._custom_stage_widget = new_stage
            self.deck_stack.addWidget(self._custom_stage_widget)

            if isinstance(new_stage, WaveformStage):
                if self._current_file:
                    new_stage.load_audio_preview(self._current_file)
                new_stage.rangeChanged.connect(self._on_waveform_range_changed)
                new_stage.seekRequested.connect(self._player.seek)
                self._player.set_loop(
                    self.btn_transport_loop.isChecked(),
                    new_stage._start_sec,
                    new_stage._end_sec,
                )

            if self._current_file or self._current_files:
                self.deck_stack.setCurrentIndex(1)
            else:
                self.deck_stack.setCurrentIndex(0)
        else:
            self.deck_stack.setCurrentIndex(0)

    def _on_waveform_range_changed(self, start_sec: float, end_sec: float) -> None:
        """Sync WaveformStage range markers with trimmer controls in Slot 3 and player loop."""
        for name, widget in self._rack_controller.controls.items():
            if name == "start_sec" and hasattr(widget, "setValue"):
                widget.setValue(start_sec)
            elif name == "end_sec" and hasattr(widget, "setValue"):
                widget.setValue(end_sec)
        self._player.set_loop(self.btn_transport_loop.isChecked(), start_sec, end_sec)

    # --- Module Configuration ---

    def configure_module(self, module_info: Dict[str, Any], file_path: Optional[str] = None) -> None:
        """Inject module configuration into the 4-slot workspace."""
        self._player.stop()
        self._current_module_info = module_info
        self._current_module_id = module_info.get("id", "converter")
        self._submode = None
        self._active_processor_id = MODULE_TO_PROCESSOR_ID.get(self._current_module_id, self._current_module_id)
        accent_key = module_info.get("accent_key", "converter")
        accent = TOKENS.colors.accents.get(accent_key, TOKENS.colors.accents["converter"])

        # Update Slot 1 Top Bar
        title = module_info.get("title", "Audio Module").upper()
        code = module_info.get("code", "[MOD-00]")
        self.lbl_module_header.setText(f"{code}  {title}")
        self.lbl_module_header.setStyleSheet(
            f"color: {accent.base}; font-weight: 700; letter-spacing: 0.5px; border: none; background: transparent;"
        )

        # Update Slot 2 Deck title and accent
        self.lbl_deck_title.setText(f"SLOT 2 : {title} DECK")
        self.interactive_deck.set_accent_color(accent.base)

        if file_path:
            self._current_file = file_path
            self._current_files = [file_path]
            self._player.load(file_path)
            self._meter_engine.load_file(file_path)
        else:
            self._current_file = None
            self._current_files = []

        self._update_file_display()

        # Update Slot 3 Rack Clusters with dynamic analog controls
        self._update_rack_parameters()

        # Update Slot 2 Custom Stage
        self._update_custom_stage()

        # Update Slot 4 CTA Button
        action_text = module_info.get("action_text", "Execute")
        self.btn_action_cta.setText(action_text)
        self.btn_action_cta.set_accent_key(accent_key)
        self.btn_action_cta.setEnabled(True)

    # --- Transport & Audio Playback ---

    def _toggle_playback(self) -> None:
        """Toggle audio playback."""
        if not self._current_file:
            return
        self._player.toggle_play_pause()

    def _stop_playback(self) -> None:
        """Stop playback and rewind to start or loop start."""
        self._player.stop()
        self._meter_engine.reset()

    def _toggle_loop(self) -> None:
        """Toggle loop playback mode."""
        start = 0.0
        end = 0.0
        if isinstance(self._custom_stage_widget, WaveformStage):
            start = self._custom_stage_widget._start_sec
            end = self._custom_stage_widget._end_sec
        self._player.set_loop(self.btn_transport_loop.isChecked(), start, end)

    def _on_player_position_changed(self, pos_sec: float) -> None:
        """Update WaveformStage playhead cursor and meter engine on 60 FPS tick."""
        if isinstance(self._custom_stage_widget, WaveformStage):
            self._custom_stage_widget.set_playhead(pos_sec)
        self._meter_engine.process_playhead(pos_sec)

    def _on_meter_levels_updated(self, rms_l: float, rms_r: float, peak_l: float, peak_r: float) -> None:
        """Update live RMS telemetry display in Slot 2 Deck Header."""
        max_rms = max(rms_l, rms_r)
        if max_rms <= -70.0:
            self.lbl_meter_level.setText("-∞ dB")
            self.lbl_meter_level.setStyleSheet(
                f"color: {TOKENS.colors.text.muted};"
                f"background-color: {TOKENS.colors.background.surface_display_glass};"
                f"border: 1px solid rgba(255, 255, 255, 0.08);"
                f"border-radius: 3px;"
                f"padding: 2px 6px;"
            )
        else:
            self.lbl_meter_level.setText(f"{max_rms:.1f} dB")
            color = "#EF4444" if max_rms > -3.0 else ("#F59E0B" if max_rms > -12.0 else "#22C55E")
            self.lbl_meter_level.setStyleSheet(
                f"color: {color};"
                f"background-color: {TOKENS.colors.background.surface_display_glass};"
                f"border: 1px solid rgba(255, 255, 255, 0.08);"
                f"border-radius: 3px;"
                f"padding: 2px 6px;"
            )

        if self._custom_stage_widget is not None and hasattr(self._custom_stage_widget, "set_levels"):
            self._custom_stage_widget.set_levels(rms_l, rms_r)

    def _on_meter_ballistics_updated(self, ang_l: float, ang_r: float) -> None:
        """Forward physical galvanometer needle angles to custom stage."""
        if self._custom_stage_widget is not None and hasattr(self._custom_stage_widget, "set_angles"):
            self._custom_stage_widget.set_angles(ang_l, ang_r)

    def _on_meter_clip_detected(self, clip_l: bool, clip_r: bool) -> None:
        """Update peak overload indicator lamps."""
        is_clipped = clip_l or clip_r
        if is_clipped:
            self.lbl_peak_led.setStyleSheet(
                "color: #FFFFFF; background-color: #EF4444; border: 1px solid #DC2626; border-radius: 3px; padding: 2px 5px; font-weight: bold;"
            )
        else:
            self.lbl_peak_led.setStyleSheet(
                "color: #4A1A1A; background-color: #1A0D0D; border: 1px solid #3A1414; border-radius: 3px; padding: 2px 5px;"
            )

        if self._custom_stage_widget is not None and hasattr(self._custom_stage_widget, "set_clipped"):
            self._custom_stage_widget.set_clipped(clip_l, clip_r)

    def _on_player_state_changed(self, state: str) -> None:
        """Update transport play button icon on state change."""
        if state == "playing":
            self.btn_transport_play.setText("❚❚")
            self.btn_transport_play.setStyleSheet(
                f"QPushButton {{"
                f"  background-color: #2D1E10;"
                f"  color: #F59E0B;"
                f"  border: 1px solid #F59E0B;"
                f"  border-radius: 4px;"
                f"  font-size: 11px;"
                f"  font-weight: bold;"
                f"  padding: 2px 8px;"
                f"}}"
            )
        else:
            self.btn_transport_play.setText("▶")
            self.btn_transport_play.setStyleSheet(
                f"QPushButton {{"
                f"  background-color: {TOKENS.colors.background.surface_card};"
                f"  color: {TOKENS.colors.text.primary};"
                f"  border: 1px solid {TOKENS.colors.border.card};"
                f"  border-radius: 4px;"
                f"  font-size: 11px;"
                f"  font-weight: bold;"
                f"  padding: 2px 8px;"
                f"}}"
                f"QPushButton:hover {{"
                f"  background-color: {TOKENS.colors.background.surface_card_hover};"
                f"  border-color: #F59E0B;"
                f"  color: #F59E0B;"
                f"}}"
            )

    def _on_player_timecode_updated(self, cur_str: str, dur_str: str) -> None:
        """Update digital timecode LCD readout."""
        self.lbl_timecode.setText(f"{cur_str} / {dur_str}")

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle workspace keyboard shortcuts (Spacebar toggles play/pause)."""
        if event.key() == Qt.Key.Key_Space:
            self._toggle_playback()
            event.accept()
            return
        super().keyPressEvent(event)

    # --- DSP Execution & Worker Integration ---

    def execute_action(self) -> None:
        """Trigger background processing of current audio buffer through active processor(s)."""
        if not self._current_file and not self._current_files:
            self.lbl_file_pill.setText("ERROR: NO INPUT FILE · SELECT OR DROP AUDIO FIRST")
            self.lbl_file_pill.setStyleSheet(
                f"background-color: {TOKENS.colors.background.surface_well};"
                f"color: {TOKENS.colors.semantic.error};"
                f"border: 1px solid {TOKENS.colors.semantic.error};"
                f"border-radius: {TOKENS.radii.sm}px;"
                f"padding: 8px 14px;"
            )
            return

        if self._current_task is not None and self._current_task.is_running:
            log.warning("Audio task is already running.")
            return

        options = self._rack_controller.get_parameters()
        input_paths = [Path(f) for f in self._current_files] if self._current_files else [Path(self._current_file)]

        config = AppConfig()
        output_dir = config.output_dir
        if not output_dir.exists():
            try:
                output_dir.mkdir(parents=True, exist_ok=True)
            except OSError:
                output_dir = input_paths[0].parent

        self.btn_action_cta.setEnabled(False)
        self.btn_action_cta.setText("PROCESSING...")
        self.lbl_deck_badge.setText("DSP ACTIVE")
        self.lbl_deck_badge.setStyleSheet(f"color: {TOKENS.colors.semantic.warning}; background: transparent;")

        # Case 1: Music Analyzer (Key & Tempo + Audio Analyzer)
        if self._current_module_id == "analyze":
            def run_analysis(cancel_token=None, on_progress=None):
                kd = ProcessorRegistry.get_processor("key_detector")
                aa = ProcessorRegistry.get_processor("audio_analyzer", ffmpeg_bin=config.ffmpeg_path)
                res = {}
                total = len(input_paths)
                for i, p in enumerate(input_paths):
                    if cancel_token and cancel_token.is_set():
                        break
                    if on_progress:
                        on_progress((i / total) * 0.5, f"[{p.name}] Analyzing Key & Tempo...")
                    k_res = kd.process_file(p, output_dir=output_dir, options=options, cancel_flag=cancel_token)
                    if on_progress:
                        on_progress(((i + 0.5) / total), f"[{p.name}] Analyzing Loudness & Peaks...")
                    a_res = aa.process_file(p, output_dir=output_dir, options=options, cancel_flag=cancel_token)
                    combined = {}
                    if isinstance(k_res, dict):
                        combined.update(k_res)
                    if isinstance(a_res, dict):
                        combined.update(a_res)
                    res[p] = combined
                if on_progress:
                    on_progress(1.0, "Analysis complete.")
                return res

            self._current_task = self._task_runner.submit_callable(
                run_analysis,
                name="Music Analysis",
                on_progress=self._on_worker_progress,
                on_finished=self._on_worker_finished,
                on_error=self._on_worker_error,
            )
            return

        # Case 2: Clip & Click Repair Chain (Declip + Inpaint Clicks/Dropouts)
        if self._current_module_id in ("repair", "declip") and options.get("inpaint_clicks"):
            def run_repair_chain(cancel_token=None, on_progress=None):
                declip = ProcessorRegistry.get_processor("declip", ffmpeg_bin=config.ffmpeg_path)
                resto = ProcessorRegistry.get_processor("restoration", ffmpeg_bin=config.ffmpeg_path)
                res = {}
                total = len(input_paths)
                for i, p in enumerate(input_paths):
                    if cancel_token and cancel_token.is_set():
                        break
                    def p1(sub_f, m):
                        if on_progress:
                            on_progress((i / total) + (sub_f / (total * 2)), f"[{p.name}] Declip: {m}")
                    out1 = declip.process_file(p, output_dir=output_dir, options=options, on_progress=p1, cancel_flag=cancel_token)
                    if cancel_token and cancel_token.is_set():
                        break
                    def p2(sub_f, m):
                        if on_progress:
                            on_progress((i / total) + 0.5 / total + (sub_f / (total * 2)), f"[{p.name}] Restoration: {m}")
                    out2 = resto.process_file(out1, output_dir=output_dir, options={"target_artifacts": ["digital_glitch", "dropout", "vinyl_crackle"], "restoration_strength": 0.5}, on_progress=p2, cancel_flag=cancel_token)
                    res[p] = out2
                return res

            self._current_task = self._task_runner.submit_callable(
                run_repair_chain,
                name="Clip & Click Repair Chain",
                on_progress=self._on_worker_progress,
                on_finished=self._on_worker_finished,
                on_error=self._on_worker_error,
            )
            return

        # Case 3: Audio Editor Chain (Trim + Post-Trim Normalize)
        if self._current_module_id in ("edit", "trim", "trimmer") and options.get("normalize_output"):
            def run_edit_chain(cancel_token=None, on_progress=None):
                trimmer = ProcessorRegistry.get_processor("audio_trimmer", ffmpeg_bin=config.ffmpeg_path)
                normalizer = ProcessorRegistry.get_processor("loudness_normalizer", ffmpeg_bin=config.ffmpeg_path)
                res = {}
                total = len(input_paths)
                for i, p in enumerate(input_paths):
                    if cancel_token and cancel_token.is_set():
                        break
                    def p1(sub_f, m):
                        if on_progress:
                            on_progress((i / total) + (sub_f / (total * 2)), f"[{p.name}] Trimming: {m}")
                    out1 = trimmer.process_file(p, output_dir=output_dir, options=options, on_progress=p1, cancel_flag=cancel_token)
                    if cancel_token and cancel_token.is_set():
                        break
                    def p2(sub_f, m):
                        if on_progress:
                            on_progress((i / total) + 0.5 / total + (sub_f / (total * 2)), f"[{p.name}] Normalizing: {m}")
                    out2 = normalizer.process_file(out1, output_dir=output_dir, options={"target_lufs": -14.0, "max_true_peak": -1.0}, on_progress=p2, cancel_flag=cancel_token)
                    res[p] = out2
                return res

            self._current_task = self._task_runner.submit_callable(
                run_edit_chain,
                name="Trim & Normalize Chain",
                on_progress=self._on_worker_progress,
                on_finished=self._on_worker_finished,
                on_error=self._on_worker_error,
            )
            return

        # Case 4: Noise & Room Repair Chain (Denoise + Dereverb)
        if self._current_module_id in ("clean", "denoise") and self._submode == "both":
            def run_clean_chain(cancel_token=None, on_progress=None):
                denoiser = ProcessorRegistry.get_processor("denoise", ffmpeg_bin=config.ffmpeg_path)
                dereverber = ProcessorRegistry.get_processor("dereverb", ffmpeg_bin=config.ffmpeg_path)
                res = {}
                total = len(input_paths)
                for i, p in enumerate(input_paths):
                    if cancel_token and cancel_token.is_set():
                        break
                    def p1(sub_f, m):
                        if on_progress:
                            on_progress((i / total) + (sub_f / (total * 2)), f"[{p.name}] Denoise: {m}")
                    out1 = denoiser.process_file(p, output_dir=output_dir, options=options, on_progress=p1, cancel_flag=cancel_token)
                    if cancel_token and cancel_token.is_set():
                        break
                    def p2(sub_f, m):
                        if on_progress:
                            on_progress((i / total) + 0.5 / total + (sub_f / (total * 2)), f"[{p.name}] Dereverb: {m}")
                    out2 = dereverber.process_file(out1, output_dir=output_dir, options={"amount": "moderate", "preserve_warmth": True}, on_progress=p2, cancel_flag=cancel_token)
                    res[p] = out2
                return res

            self._current_task = self._task_runner.submit_callable(
                run_clean_chain,
                name="Denoise & Dereverb Clean Chain",
                on_progress=self._on_worker_progress,
                on_finished=self._on_worker_finished,
                on_error=self._on_worker_error,
            )
            return

        # Case 5: Standard Single-Processor Execution
        proc_id = self._active_processor_id or MODULE_TO_PROCESSOR_ID.get(self._current_module_id, self._current_module_id)
        try:
            try:
                processor = ProcessorRegistry.get_processor(proc_id, ffmpeg_bin=config.ffmpeg_path)
            except TypeError:
                processor = ProcessorRegistry.get_processor(proc_id)
        except Exception as e:
            log.exception("Failed to instantiate processor: %s", proc_id)
            self.lbl_file_pill.setText(f"ERROR: {str(e)[:40]}")
            self.btn_action_cta.setEnabled(True)
            self.btn_action_cta.setText(self._current_module_info.get("action_text", "Execute"))
            return

        self._current_task = self._task_runner.submit_processor(
            processor=processor,
            input_paths=input_paths,
            output_dir=output_dir,
            options=options,
            name=self._current_module_info.get("title", "Audio Task"),
            on_progress=self._on_worker_progress,
            on_finished=self._on_worker_finished,
            on_error=self._on_worker_error,
        )

    def _on_worker_progress(self, val: float, msg: str) -> None:
        """Handle background worker progress update."""
        pct = int(val * 100)
        eta_str = ""
        if self._current_task and self._current_task.eta_seconds:
            eta_s = int(self._current_task.eta_seconds)
            eta_str = f" · ETA {eta_s}s"
        self.lbl_engine_status.setText(f"DSP: {pct}%{eta_str}")
        self.lbl_file_pill.setText(f"PROCESSING: {pct}%{eta_str} — {msg}")

    def _on_worker_finished(self, result: Any) -> None:
        """Handle worker completion."""
        action_text = self._current_module_info.get("action_text", "Execute")
        self.btn_action_cta.setText(action_text)
        self.btn_action_cta.setEnabled(True)
        self.lbl_engine_status.setText("COREAUDIO · 48 kHz")

        # Unwrap TaskResult if returned
        data = result
        is_cancelled = False
        is_failed = False
        error_msg = None
        if isinstance(result, TaskResult):
            data = result.data
            is_cancelled = result.is_cancelled
            is_failed = (result.status.value == "failed")
            error_msg = result.error

        if is_cancelled:
            self.lbl_deck_badge.setText("CANCELLED")
            self.lbl_deck_badge.setStyleSheet(f"color: {TOKENS.colors.semantic.warning}; background: transparent;")
            self.lbl_file_pill.setText("PROCESSING CANCELLED BY USER")
            return

        if is_failed:
            self._on_worker_error(error_msg or "Unknown error occurred")
            return

        self.lbl_deck_badge.setText("COMPLETED")
        self.lbl_deck_badge.setStyleSheet(f"color: {TOKENS.colors.semantic.success}; background: transparent;")

        if isinstance(self._custom_stage_widget, AnalysisStage) and isinstance(data, dict):
            first_res = next(iter(data.values())) if data else {}
            if isinstance(first_res, dict):
                key = first_res.get("key", "A MINOR")
                camelot = first_res.get("camelot", "8A")
                bpm = float(first_res.get("bpm", 120.0))
                conf = float(first_res.get("confidence", 0.95))
                self._custom_stage_widget.set_results(key, camelot, bpm, conf)

        accent_key = self._current_module_info.get("accent_key", "converter")
        accent = TOKENS.colors.accents.get(accent_key, TOKENS.colors.accents["converter"])
        self.lbl_file_pill.setText("PROCESSING COMPLETED SUCCESSFULLY")
        self.lbl_file_pill.setStyleSheet(
            f"background-color: {TOKENS.colors.background.surface_well};"
            f"color: {accent.base};"
            f"border: 1px solid {accent.base};"
            f"border-radius: {TOKENS.radii.sm}px;"
            f"padding: 8px 14px;"
        )

    def _on_worker_error(self, err: str) -> None:
        """Handle worker error."""
        action_text = self._current_module_info.get("action_text", "Execute")
        self.btn_action_cta.setText(action_text)
        self.btn_action_cta.setEnabled(True)
        self.lbl_engine_status.setText("DSP ERROR")
        self.lbl_deck_badge.setText("ERROR")
        self.lbl_deck_badge.setStyleSheet(f"color: {TOKENS.colors.semantic.error}; background: transparent;")
        self.lbl_file_pill.setText(f"ERROR: {err[:60]}")
        self.lbl_file_pill.setStyleSheet(
            f"background-color: {TOKENS.colors.background.surface_well};"
            f"color: {TOKENS.colors.semantic.error};"
            f"border: 1px solid {TOKENS.colors.semantic.error};"
            f"border-radius: {TOKENS.radii.sm}px;"
            f"padding: 8px 14px;"
        )
