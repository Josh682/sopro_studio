"""LauncherCard - Analog Console Modular Plate Card.

Implements DESIGN.md Section 5.2 & Section 7.1:
- Fixed 346x216px card dimensions, 4px corner radius.
- Background #33251A (plate modular bronze), hover #483625.
- Raised bronze plate bevel: top highlight rgba(255,255,255,0.12), bottom shadow rgba(0,0,0,0.65).
- 4 Corner chassis screws (8px diameter, 6px offset).
- Header: Monospace tag [MOD-XX] [TAG] (#B5A899), BrowseButton pill (#120E0B).
- Title: Silkscreen title 15px bold (#EDE6DC).
- Zero description text across all cards.
- Bottom Rack Area: TactileButton (amber illuminated push-button).
- Native Drag-and-Drop audio file support.
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
    QFrame,
    QHBoxLayout,
    QKeyEvent,
    QLabel,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPointF,
    QPushButton,
    QRadialGradient,
    QRectF,
    QSize,
    QSizePolicy,
    Qt,
    QVBoxLayout,
    QWidget,
    Signal,
)

from src.ui.theme.tokens import TOKENS, AccentToken
from src.ui.widgets.module_rack_canvas import ModuleRackCanvas
from src.ui.widgets.tactile_button import TactileButton

# Supported audio formats for drag-and-drop
AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".aiff", ".aif", ".m4a", ".aac"}


def audio_file_from_mime(mime_data) -> Optional[str]:
    """Extract first valid audio local path from drag event mime data."""
    if not mime_data or not mime_data.hasUrls():
        return None
    for url in mime_data.urls():
        if url.isLocalFile():
            file_path = url.toLocalFile()
            suffix = Path(file_path).suffix.lower()
            if suffix in AUDIO_EXTENSIONS:
                return file_path
    return None


class LauncherCard(QFrame):
    """Modular bronze hardware card for an audio module in the 3x3 console grid."""

    # Signals
    file_dropped = Signal(str, str)  # (module_id, file_path)
    open_requested = Signal(str)  # module_id
    focus_changed = Signal(bool)

    def __init__(
        self,
        module_id: str,
        code: str,
        tag: str,
        title: str,
        description: str = "",
        button_text: str = "Open",
        accent_key: str = "converter",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self.module_id = module_id
        self.code = code
        self.tag = tag
        self.title_text = title
        self.description_text = description  # Preserved in attr, but never rendered
        self.button_text = button_text
        self.accent_key = accent_key

        self._is_hovered = False
        self._armed = False  # Global drag-active stand-by indicator
        self._drag_state: Optional[str] = None  # None, "valid", "invalid"

        self.setAcceptDrops(True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedHeight(TOKENS.dimensions.grid.card_height)  # 216px
        self.setFixedWidth(TOKENS.dimensions.grid.card_width)  # 346px
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._setup_ui()

    def set_armed(self, armed: bool) -> None:
        """Set window-wide armed state when audio file drag is active."""
        if self._armed != armed:
            self._armed = armed
            self.update()

    @property
    def accent_token(self) -> AccentToken:
        return TOKENS.colors.accents.get(
            self.accent_key,
            TOKENS.colors.accents["converter"],
        )

    def _setup_ui(self) -> None:
        """Construct card layout according to DESIGN.md Section 5.2 (No Description)."""
        layout = QVBoxLayout(self)
        # Margins: 14px horizontal, 8px top, 4px bottom to ground controls near bottom edge
        layout.setContentsMargins(14, 8, 14, 4)
        layout.setSpacing(0)

        # Top Header Bar: Nama Modul di pojok kiri atas, Input Jack + Browse di kanan
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        # Retained for API compatibility but not added to layout
        self.lbl_tag = QLabel(f"{self.code}  {self.tag}")
        self.lbl_tag.hide()

        # Nama Modul (hanya nama saja di pojok kiri atas, diperbesar sedikit)
        self.lbl_title = QLabel(self.title_text)
        title_font = QFont("Helvetica Neue", 16, QFont.Weight.Bold)
        self.lbl_title.setFont(title_font)
        self.lbl_title.setStyleSheet(f"color: {TOKENS.colors.text.silkscreen_title}; background: transparent;")
        header_layout.addWidget(self.lbl_title, alignment=Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        header_layout.addStretch()

        # Manual File Picker Pill Button: [Browse] (Height: 18px, Radius: 6px)
        self.btn_browse = QPushButton("Browse", self)
        browse_font = QFont("Menlo", 10, QFont.Weight.Bold)
        self.btn_browse.setFont(browse_font)
        self.btn_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_browse.setToolTip(f"Drop audio file into input jack or click to browse for {self.title_text}")
        self.btn_browse.setFixedHeight(TOKENS.dimensions.browse_button.height)  # 18px
        self.btn_browse.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: {TOKENS.colors.background.surface_well_dark};"
            f"  color: {TOKENS.colors.text.silkscreen_tag};"
            f"  border-top: 1px solid rgba(255, 255, 255, 0.12);"
            f"  border-bottom: 1px solid rgba(0, 0, 0, 0.65);"
            f"  border-radius: {TOKENS.radii.button}px;"
            f"  padding: 1px 8px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: #1F1710;"
            f"  color: {TOKENS.colors.text.silkscreen_title};"
            f"  border-top: 1px solid rgba(245, 158, 11, 0.4);"
            f"}}"
            f"QPushButton:pressed {{"
            f"  background-color: #0E0A08;"
            f"  border-top: 1px solid rgba(0, 0, 0, 0.85);"
            f"  border-bottom: 1px solid rgba(255, 255, 255, 0.08);"
            f"}}"
        )
        self.btn_browse.clicked.connect(self._on_browse_clicked)
        header_layout.addWidget(self.btn_browse, alignment=Qt.AlignmentFlag.AlignVCenter)

        layout.addLayout(header_layout)

        # Gap Separator between header and rack canvas
        layout.addSpacing(14)

        # 4. Instrument Rack Canvas (160px)
        self.rack_canvas = ModuleRackCanvas(self.module_id, self)
        layout.addWidget(self.rack_canvas)

        # Primary Illuminated Push Button in Rack (Kept hidden for API & test compatibility)
        self.btn_open = TactileButton(
            text=self.button_text.upper(),
            accent_key=self.accent_key,
            face_height=36,
            parent=self,
        )
        self.btn_open.hide()
        self.btn_open.clicked.connect(lambda: self.open_requested.emit(self.module_id))

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

    # --- Mouse Hover ---

    def enterEvent(self, event) -> None:
        self._is_hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._is_hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            try:
                from src.audio.haptics import play_switch_click
                play_switch_click()
            except Exception:
                pass
            self.open_requested.emit(self.module_id)
        super().mousePressEvent(event)

    def focusInEvent(self, event) -> None:
        self.focus_changed.emit(True)
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event) -> None:
        self.focus_changed.emit(False)
        super().focusOutEvent(event)
        self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            try:
                from src.audio.haptics import play_switch_click
                play_switch_click()
            except Exception:
                pass
            self.open_requested.emit(self.module_id)
            event.accept()
            return
        super().keyPressEvent(event)

    # --- Drag & Drop ---

    def _get_audio_file_from_event(self, event: QDragEnterEvent | QDropEvent) -> Optional[str]:
        """Extract first valid audio local path from drag event mime data."""
        return audio_file_from_mime(event.mimeData())

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
        if hasattr(self, "rack_canvas"):
            self.rack_canvas.update()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if self._drag_state == "valid":
            event.setDropAction(Qt.DropAction.CopyAction)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self._drag_state = None
        self.update()
        if hasattr(self, "rack_canvas"):
            self.rack_canvas.update()
        event.accept()

    def dropEvent(self, event: QDropEvent) -> None:
        audio_file = self._get_audio_file_from_event(event)
        self._drag_state = None
        self.update()
        if hasattr(self, "rack_canvas"):
            self.rack_canvas.update()

        if audio_file:
            event.setDropAction(Qt.DropAction.CopyAction)
            event.acceptProposedAction()
            self.file_dropped.emit(self.module_id, audio_file)
        else:
            event.ignore()

    # --- Custom Bronze Hardware Plate Rendering ---

    def paintEvent(self, event) -> None:
        """Render bronze modular chassis plate, 4 corner screws, input jack, and raised bevels."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = float(self.width())
        h = float(self.height())
        r = float(TOKENS.radii.card)  # 4px

        card_rect = QRectF(0.5, 0.5, w - 1.0, h - 1.0)
        path = QPainterPath()
        path.addRoundedRect(card_rect, r, r)

        # 1. Bronze Plate Modular Fill with vertical gradient (lighter at top)
        plate_grad = QLinearGradient(0.0, 0.0, 0.0, h)
        if self._drag_state == "valid":
            plate_grad.setColorAt(0.0, QColor("#5A4532"))
            plate_grad.setColorAt(0.4, QColor("#4A3828"))
            plate_grad.setColorAt(1.0, QColor("#34251A"))
        elif self._is_hovered:
            plate_grad.setColorAt(0.0, QColor("#543F2D"))
            plate_grad.setColorAt(0.4, QColor("#443224"))
            plate_grad.setColorAt(1.0, QColor("#2F2117"))
        else:
            # Subtle lighting gradient: lighter bronze at top transitioning downward
            plate_grad.setColorAt(0.0, QColor("#463424"))
            plate_grad.setColorAt(0.4, QColor("#3B2B1E"))
            plate_grad.setColorAt(1.0, QColor("#281C13"))
        painter.fillPath(path, plate_grad)

        # 2. Raised Bronze Plate Bevel or Illuminated Drag Perimeter Glow
        if self._drag_state == "valid":
            # 1px border groove with soft amber inner glow
            painter.setPen(QPen(QColor("#F59E0B"), 1.2))
            painter.drawPath(path)
            for inset, alpha in ((1.0, 75), (2.0, 35), (3.0, 15)):
                glow_path = QPainterPath()
                glow_path.addRoundedRect(card_rect.adjusted(inset, inset, -inset, -inset), max(1.0, r - inset), max(1.0, r - inset))
                painter.setPen(QPen(QColor(245, 158, 11, alpha), 1.0))
                painter.drawPath(glow_path)
        elif self._drag_state == "invalid":
            # 1px error border groove with soft red inner glow
            painter.setPen(QPen(QColor("#EF4444"), 1.2))
            painter.drawPath(path)
            for inset, alpha in ((1.0, 80), (2.0, 35)):
                glow_path = QPainterPath()
                glow_path.addRoundedRect(card_rect.adjusted(inset, inset, -inset, -inset), max(1.0, r - inset), max(1.0, r - inset))
                painter.setPen(QPen(QColor(239, 68, 68, alpha), 1.0))
                painter.drawPath(glow_path)
        else:
            # Top highlight bevel
            painter.setPen(QPen(QColor(255, 255, 255, 31), 1.0))
            painter.drawLine(QPointF(r, 0.5), QPointF(w - r, 0.5))

            # Bottom shadow bevel
            painter.setPen(QPen(QColor(0, 0, 0, 166), 1.0))
            painter.drawLine(QPointF(r, h - 0.5), QPointF(w - r, h - 0.5))

            # Left/Right subtle edge
            painter.setPen(QPen(QColor(0, 0, 0, 90), 1.0))
            painter.drawLine(QPointF(0.5, r), QPointF(0.5, h - r))
            painter.drawLine(QPointF(w - 0.5, r), QPointF(w - 0.5, h - r))

        # 2b. Keyboard Focus Indicator: 2px Amber Ring per DESIGN.md & Milestone 5
        if self.hasFocus():
            painter.save()
            focus_ring_rect = card_rect.adjusted(0.5, 0.5, -0.5, -0.5)
            focus_path = QPainterPath()
            focus_path.addRoundedRect(focus_ring_rect, r, r)
            focus_pen = QPen(QColor("#F59E0B"), 2.0)
            painter.setPen(focus_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(focus_path)
            painter.restore()

        # 3. 1/4" Studio Input Jack Socket with Signal Status LED in Header
        self._draw_input_jack(painter)

        # 3. 4 Chassis Corner Screws (8px diameter, 6px offset)
        screw_diam = float(TOKENS.dimensions.hardware.screw_diameter)  # 8px
        screw_r = screw_diam / 2.0
        offsets = [
            (6.0, 6.0),  # Top-Left
            (w - 6.0 - screw_diam, 6.0),  # Top-Right
            (6.0, h - 6.0 - screw_diam),  # Bottom-Left
            (w - 6.0 - screw_diam, h - 6.0 - screw_diam),  # Bottom-Right
        ]

        for sx, sy in offsets:
            s_rect = QRectF(sx, sy, screw_diam, screw_diam)

            # Outer countersink hole
            painter.setPen(QPen(QColor(0, 0, 0, 240), 0.8))
            painter.setBrush(QColor("#110B07"))
            painter.drawEllipse(s_rect)

            # Metallic screw head
            head_rect = s_rect.adjusted(1.0, 1.0, -1.0, -1.0)
            head_grad = QLinearGradient(head_rect.topLeft(), head_rect.bottomRight())
            head_grad.setColorAt(0.0, QColor("#4A3728"))
            head_grad.setColorAt(0.5, QColor("#2D1F15"))
            head_grad.setColorAt(1.0, QColor("#18100A"))
            painter.setPen(QPen(QColor(255, 255, 255, 35), 0.6))
            painter.setBrush(head_grad)
            painter.drawEllipse(head_rect)

            # Slot line (slight angle for realism)
            center = s_rect.center()
            painter.setPen(QPen(QColor(0, 0, 0, 240), 1.0))
            painter.drawLine(
                QPointF(center.x() - 2.0, center.y() - 1.2),
                QPointF(center.x() + 2.0, center.y() + 1.2),
            )
            # Slot highlight
            painter.setPen(QPen(QColor(255, 255, 255, 45), 0.6))
            painter.drawLine(
                QPointF(center.x() - 1.8, center.y() - 0.6),
                QPointF(center.x() + 1.8, center.y() + 1.8),
            )

        painter.end()
        super().paintEvent(event)

    def _draw_input_jack(self, painter: QPainter) -> None:
        """Draw authentic 1/4" studio input jack socket with signal LED next to Browse button."""
        btn_geom = self.btn_browse.geometry()
        btn_x = btn_geom.x()
        btn_y = btn_geom.y()
        btn_h = btn_geom.height()

        # Jack socket centered vertically with browse button, placed 8px to its left
        jack_right = float(btn_x - 8)
        jack_r = 6.5
        jack_cx = jack_right - jack_r
        jack_cy = btn_y + btn_h / 2.0

        # 1. Outer Dark Recessed Socket Cavity
        cavity_rect = QRectF(jack_cx - jack_r, jack_cy - jack_r, jack_r * 2.0, jack_r * 2.0)
        painter.setPen(QPen(QColor("#080503"), 1.0))
        painter.setBrush(QColor("#140D08"))
        painter.drawEllipse(cavity_rect)

        # 2. Fluted Nickel / Chrome Bezel Nut Ring
        nut_r = jack_r - 1.2
        nut_rect = QRectF(jack_cx - nut_r, jack_cy - nut_r, nut_r * 2.0, nut_r * 2.0)
        nut_grad = QLinearGradient(nut_rect.topLeft(), nut_rect.bottomRight())
        nut_grad.setColorAt(0.0, QColor("#CBD5E1"))
        nut_grad.setColorAt(0.5, QColor("#64748B"))
        nut_grad.setColorAt(1.0, QColor("#334155"))
        painter.setPen(QPen(QColor(255, 255, 255, 40), 0.6))
        painter.setBrush(nut_grad)
        painter.drawEllipse(nut_rect)

        # 3. Quarter-inch Bore Center Hole (pitch black depth)
        hole_r = 2.4
        painter.setPen(QPen(QColor(0, 0, 0, 200), 0.8))
        painter.setBrush(QColor("#0A0604"))
        painter.drawEllipse(QPointF(jack_cx, jack_cy), hole_r, hole_r)

        # 4. Silkscreen Text Label 'IN' (Cream/Bone mono text)
        painter.setFont(QFont("Menlo", 8, QFont.Weight.Bold))
        painter.setPen(QColor("#B5A899"))
        lbl_rect = QRectF(jack_cx - jack_r - 20.0, jack_cy - 7.0, 18.0, 14.0)
        painter.drawText(lbl_rect, Qt.AlignmentFlag.AlignCenter, "IN")

        # 5. Signal LED (Left of 'IN' label)
        led_cx = jack_cx - jack_r - 20.0 - 5.0
        led_cy = jack_cy

        # Determine LED appearance based on state
        if self._drag_state == "valid":
            # Target active: Bright amber glow
            glow = QRadialGradient(QPointF(led_cx, led_cy), 5.5)
            glow.setColorAt(0.0, QColor(251, 191, 36, 255))
            glow.setColorAt(0.5, QColor(245, 158, 11, 140))
            glow.setColorAt(1.0, QColor(217, 119, 6, 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(glow)
            painter.drawEllipse(QPointF(led_cx, led_cy), 5.5, 5.5)

            painter.setPen(QPen(QColor("#0A0604"), 0.6))
            painter.setBrush(QColor("#FDE68A"))
            painter.drawEllipse(QPointF(led_cx, led_cy), 2.2, 2.2)

        elif self._drag_state == "invalid":
            # Target error: Red glow
            glow = QRadialGradient(QPointF(led_cx, led_cy), 5.5)
            glow.setColorAt(0.0, QColor(239, 68, 68, 255))
            glow.setColorAt(0.5, QColor(220, 38, 38, 140))
            glow.setColorAt(1.0, QColor(185, 28, 28, 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(glow)
            painter.drawEllipse(QPointF(led_cx, led_cy), 5.5, 5.5)

            painter.setPen(QPen(QColor("#0A0604"), 0.6))
            painter.setBrush(QColor("#FCA5A5"))
            painter.drawEllipse(QPointF(led_cx, led_cy), 2.2, 2.2)

        elif self._armed:
            # Grid armed: Warm amber stand-by glow
            glow = QRadialGradient(QPointF(led_cx, led_cy), 4.0)
            glow.setColorAt(0.0, QColor(245, 158, 11, 180))
            glow.setColorAt(1.0, QColor(245, 158, 11, 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(glow)
            painter.drawEllipse(QPointF(led_cx, led_cy), 4.0, 4.0)

            painter.setPen(QPen(QColor("#0A0604"), 0.6))
            painter.setBrush(QColor("#F59E0B"))
            painter.drawEllipse(QPointF(led_cx, led_cy), 2.2, 2.2)

        else:
            # Idle: Dark unlit LED
            painter.setPen(QPen(QColor("#0A0604"), 0.6))
            painter.setBrush(QColor("#382618"))
            painter.drawEllipse(QPointF(led_cx, led_cy), 2.2, 2.2)
