"""WorkspacePage - 4-Slot Tactile Industrial Skeuomorphic Workspace Template.

Implements DESIGN.md Section 7.1 Contract:
- Slot 1: Top Bar (48px) with [<- ESC: DASHBOARD] and Engine Status LED
- Slot 2: The Deck / Visual Stage (210px, Recessed Chassis #0A0C10)
  Now features interactive drag & drop and click-to-browse manual file selection.
- Slot 3: Hardware Control Rack (280px, Analog Chassis #11141A, 3 Clusters)
- Slot 4: Execution Footer (64px, File Status Pill + Browse Button + Reset + Primary CTA ChunkyButton)
"""

from __future__ import annotations

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
    QLabel,
    QMouseEvent,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    Qt,
    QVBoxLayout,
    QWidget,
    Signal,
)

from src.ui.theme.tokens import TOKENS, AccentToken
from src.ui.widgets.tactile_button import TactileButton

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
            bg = "#121A28"
        elif self._is_hovered:
            border = f"1px dashed {self._accent_color}"
            bg = "#0B0E15"
        else:
            border = f"1px dashed {TOKENS.colors.border.subtle}"
            bg = "#050608"

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
        self.lbl_deck_title = QLabel("VISUAL STAGE / DECK MONITOR", self.slot2_deck)
        self.lbl_deck_title.setFont(TOKENS.typography.create_font("data_mono_sm"))
        self.lbl_deck_title.setStyleSheet(f"color: {TOKENS.colors.text.muted}; background: transparent; border: none;")
        deck_header.addWidget(self.lbl_deck_title)
        deck_header.addStretch()

        self.lbl_deck_badge = QLabel("READY", self.slot2_deck)
        self.lbl_deck_badge.setFont(TOKENS.typography.create_font("data_mono_sm"))
        self.lbl_deck_badge.setStyleSheet(
            f"color: {TOKENS.colors.semantic.success}; background: transparent; border: none;"
        )
        deck_header.addWidget(self.lbl_deck_badge)
        deck_layout.addLayout(deck_header)

        # Interactive Deck Target (Click anywhere to browse or drag & drop)
        self.interactive_deck = InteractiveDeck(self.slot2_deck)
        self.interactive_deck.browse_requested.connect(self.open_file_dialog)
        self.interactive_deck.file_dropped.connect(self.load_file)
        deck_layout.addWidget(self.interactive_deck)

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
        self.cluster_a = self._create_cluster_panel("CLUSTER A : PRIMARY PARAMETERS")
        rack_layout.addWidget(self.cluster_a, 4)

        # Cluster B: Secondary Controls
        self.cluster_b = self._create_cluster_panel("CLUSTER B : ENGINE FILTERS")
        rack_layout.addWidget(self.cluster_b, 4)

        # Cluster C: Presets & Targets
        self.cluster_c = self._create_cluster_panel("CLUSTER C : PRESETS")
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
        footer_layout.addWidget(self.btn_action_cta)

        main_layout.addWidget(self.slot4_footer)

    def _create_cluster_panel(self, cluster_title: str) -> QFrame:
        """Helper to create an analog hardware rack cluster panel."""
        panel = QFrame(self.slot3_rack)
        panel.setStyleSheet(
            f"QFrame {{"
            f"  background-color: #0D1017;"
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
        body_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        msg = QLabel("Hardware parameters connected to audio DSP pipe.", body)
        msg.setFont(TOKENS.typography.create_font("body_small"))
        msg.setStyleSheet(f"color: {TOKENS.colors.text.muted}; border: none; background: transparent;")
        body_layout.addWidget(msg)

        layout.addWidget(body)
        return panel

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
        self.file_selected.emit(self._current_module_id, file_path)

    def load_files(self, file_paths: List[str]) -> None:
        """Load multiple audio files into workspace buffer."""
        if not file_paths:
            return
        self._current_files = list(file_paths)
        self._current_file = file_paths[0]
        self._update_file_display()
        self.files_selected.emit(self._current_module_id, self._current_files)
        self.file_selected.emit(self._current_module_id, self._current_file)

    def reset_file_and_params(self) -> None:
        """Reset loaded audio file and restore defaults."""
        self._current_file = None
        self._current_files.clear()
        self._update_file_display()

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

    # --- Module Configuration ---

    def configure_module(self, module_info: Dict[str, Any], file_path: Optional[str] = None) -> None:
        """Inject module configuration into the 4-slot workspace."""
        self._current_module_info = module_info
        self._current_module_id = module_info.get("id", "converter")
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
        else:
            self._current_file = None
            self._current_files = []

        self._update_file_display()

        # Update Slot 4 CTA Button
        action_text = module_info.get("action_text", "Execute")
        self.btn_action_cta.setText(action_text)
        self.btn_action_cta.set_accent_key(accent_key)
