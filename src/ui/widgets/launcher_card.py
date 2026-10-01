"""LauncherCard - Bento Grid Module Card with Tactile Affordances.

Features:
- Fixed 194px card height, 14px corner radius.
- Background #131720 with overhead lighting highlight.
- Monospace module tag, H3 title, elided 2-line description.
- Native Drag-and-Drop with visual border highlight (valid audio vs invalid).
- Bottom TactileButton matching module accent color.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.ui.qt import (
    QColor,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDragMoveEvent,
    QDropEvent,
    QFileDialog,
    QFont,
    QFontMetrics,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPointF,
    QPushButton,
    QRectF,
    QSize,
    QSizePolicy,
    QSpacerItem,
    Qt,
    QVBoxLayout,
    QWidget,
    Signal,
)

from src.ui.theme.tokens import TOKENS, AccentToken
from src.ui.widgets.tactile_button import TactileButton

# Supported audio formats for drag-and-drop
AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".aiff", ".aif", ".m4a", ".aac"}


class LauncherCard(QFrame):
    """Launcher card for a single audio module in the Bento Grid."""

    # Signals
    file_dropped = Signal(str, str)  # (module_id, file_path)
    open_requested = Signal(str)  # module_id

    def __init__(
        self,
        module_id: str,
        code: str,
        tag: str,
        title: str,
        description: str,
        button_text: str,
        accent_key: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self.module_id = module_id
        self.code = code
        self.tag = tag
        self.title_text = title
        self.description_text = description
        self.button_text = button_text
        self.accent_key = accent_key

        self._is_hovered = False
        self._drag_state: Optional[str] = None  # None, "valid", "invalid"

        self.setAcceptDrops(True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setFixedHeight(TOKENS.dimensions.grid.card_height)  # 194px
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._setup_ui()

    @property
    def accent_token(self) -> AccentToken:
        return TOKENS.colors.accents.get(
            self.accent_key,
            TOKENS.colors.accents["converter"],
        )

    def _setup_ui(self) -> None:
        """Construct card content layout according to DESIGN.md Section 5.2."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(0)

        # 1. Header: Monospace Tag [MOD-XX] [TAG] + Browse Button + Accent Dot
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        self.lbl_tag = QLabel(f"{self.code}  {self.tag}")
        self.lbl_tag.setFont(TOKENS.typography.create_font("data_mono_sm"))
        self.lbl_tag.setStyleSheet(f"color: {TOKENS.colors.text.muted}; background: transparent;")
        header_layout.addWidget(self.lbl_tag)

        header_layout.addStretch()

        # Manual File Picker Button: [Browse]
        self.btn_browse = QPushButton("📁 Browse", self)
        self.btn_browse.setFont(TOKENS.typography.create_font("data_mono_sm"))
        self.btn_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_browse.setToolTip(f"Select audio file for {self.title_text}")
        self.btn_browse.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: transparent;"
            f"  color: {TOKENS.colors.text.secondary};"
            f"  border: 1px solid {TOKENS.colors.border.subtle};"
            f"  border-radius: {TOKENS.radii.sm}px;"
            f"  padding: 2px 7px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: {TOKENS.colors.background.surface_card_hover};"
            f"  color: {self.accent_token.base};"
            f"  border-color: {self.accent_token.base};"
            f"}}"
            f"QPushButton:pressed {{"
            f"  background-color: {TOKENS.colors.background.surface_well};"
            f"}}"
        )
        self.btn_browse.clicked.connect(self._on_browse_clicked)
        header_layout.addWidget(self.btn_browse)

        # Accent dot indicator
        self.lbl_dot = QLabel("●")
        self.lbl_dot.setFont(QFont("Arial", 8))
        self.lbl_dot.setStyleSheet(f"color: {self.accent_token.base}; background: transparent;")
        header_layout.addWidget(self.lbl_dot)

        layout.addLayout(header_layout)

        # 2. Module Title H3
        layout.addSpacing(4)
        self.lbl_title = QLabel(self.title_text)
        self.lbl_title.setFont(TOKENS.typography.create_font("title_card"))
        self.lbl_title.setStyleSheet(f"color: {TOKENS.colors.text.primary}; background: transparent;")
        layout.addWidget(self.lbl_title)

        # 3. Description (max 2 lines elided)
        layout.addSpacing(6)
        self.lbl_desc = QLabel()
        self.lbl_desc.setFont(TOKENS.typography.create_font("body_regular"))
        self.lbl_desc.setStyleSheet(f"color: {TOKENS.colors.text.secondary}; background: transparent;")
        self.lbl_desc.setWordWrap(True)
        self.lbl_desc.setFixedHeight(34)
        self._update_elided_description()
        layout.addWidget(self.lbl_desc)

        # Vertical stretch / gap before button
        layout.addStretch()

        # 4. Mechanical Tactile Button at bottom
        self.btn_open = TactileButton(
            text=self.button_text,
            accent_key=self.accent_key,
            face_height=TOKENS.dimensions.button.launcher_height,  # 38px
            parent=self,
        )
        self.btn_open.clicked.connect(lambda: self.open_requested.emit(self.module_id))
        layout.addWidget(self.btn_open)

    def _update_elided_description(self) -> None:
        """Elide description text so it never overflows 2 lines (34px)."""
        metrics = QFontMetrics(TOKENS.typography.create_font("body_regular"))
        # Width available for text inside card (approx 300px at standard resolution)
        target_width = max(240, self.width() - 40)
        elided = metrics.elidedText(self.description_text, Qt.TextElideMode.ElideRight, target_width * 2 - 10)
        self.lbl_desc.setText(elided)

    def _on_browse_clicked(self) -> None:
        """Open system file picker to select an audio file directly from the card."""
        ext_list = [f"*{ext}" for ext in sorted(AUDIO_EXTENSIONS)]
        filter_str = f"Audio Files ({' '.join(ext_list)});;All Files (*)"
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Select Audio File — {self.title_text}",
            "",
            filter_str,
        )
        if file_path:
            self.file_dropped.emit(self.module_id, file_path)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_elided_description()

    # --- Mouse Hover ---

    def enterEvent(self, event) -> None:
        self._is_hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._is_hovered = False
        self.update()
        super().leaveEvent(event)

    # --- Drag & Drop ---

    def _get_audio_file_from_event(self, event: QDragEnterEvent | QDropEvent) -> Optional[str]:
        """Extract first valid audio local path from drag event mime data."""
        if not event.mimeData().hasUrls():
            return None
        for url in event.mimeData().urls():
            if url.isLocalFile():
                file_path = url.toLocalFile()
                suffix = Path(file_path).suffix.lower()
                if suffix in AUDIO_EXTENSIONS:
                    return file_path
        return None

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        audio_file = self._get_audio_file_from_event(event)
        if audio_file:
            self._drag_state = "valid"
            event.setDropAction(Qt.DropAction.CopyAction)
            event.acceptProposedAction()
        else:
            self._drag_state = "invalid"
            event.ignore()
        self.update()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if self._drag_state == "valid":
            event.setDropAction(Qt.DropAction.CopyAction)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self._drag_state = None
        self.update()
        event.accept()

    def dropEvent(self, event: QDropEvent) -> None:
        audio_file = self._get_audio_file_from_event(event)
        self._drag_state = None
        self.update()

        if audio_file:
            event.setDropAction(Qt.DropAction.CopyAction)
            event.acceptProposedAction()
            self.file_dropped.emit(self.module_id, audio_file)
        else:
            event.ignore()

    # --- Custom Card Rendering ---

    def paintEvent(self, event) -> None:
        """Render card surface, overhead lighting, and active border highlight."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = float(self.width())
        h = float(self.height())
        r = float(TOKENS.radii.lg)  # 14px

        card_rect = QRectF(0.5, 0.5, w - 1.0, h - 1.0)
        path = QPainterPath()
        path.addRoundedRect(card_rect, r, r)

        # 1. Background fill
        if self._drag_state == "valid":
            bg_color = TOKENS.colors.background.surface_card_hover_qcolor
        elif self._is_hovered:
            bg_color = TOKENS.colors.background.surface_card_hover_qcolor
        else:
            bg_color = TOKENS.colors.background.surface_card_qcolor
        painter.fillPath(path, bg_color)

        # 2. Subtle overhead light gradient
        overhead = QLinearGradient(0.0, 0.0, 0.0, h)
        overhead.setColorAt(0.0, QColor(255, 255, 255, 13))  # 5% white highlight at top
        overhead.setColorAt(0.5, QColor(255, 255, 255, 0))
        painter.fillPath(path, overhead)

        # 3. Perimeter border
        if self._drag_state == "valid":
            border_pen = QPen(self.accent_token.base_qcolor, 2.0)
        elif self._drag_state == "invalid":
            border_pen = QPen(TOKENS.colors.semantic.error_qcolor, 2.0)
        elif self._is_hovered:
            border_pen = QPen(TOKENS.colors.border.card_hover_qcolor, 1.0)
        else:
            border_pen = QPen(TOKENS.colors.border.card_qcolor, 1.0)

        border_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(border_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        painter.end()
        super().paintEvent(event)
