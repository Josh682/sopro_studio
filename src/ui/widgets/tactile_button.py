"""ChunkyButton / TactileButton - 3D Mechanical Tactile Push Button.

Subclasses QPushButton with custom QPainter rendering:
- 3D physical press: 4px rest bevel, 3px hover, 1px active/pressed bevel
- translateY(3px) physical travel when pressed
- Module-specific solid accent face and exact darker shadow bevel
- Bold sans-serif high-contrast dark text (#090B0E / #000000)
- Tactile audio click callback hook
"""

from __future__ import annotations

from typing import Callable, Optional

from src.ui.qt import (
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QPointF,
    QPushButton,
    QRectF,
    QSize,
    Qt,
    QWidget,
)

from src.ui.theme.tokens import TOKENS, AccentToken


class TactileButton(QPushButton):
    """3D tactile button with mechanical depth and travel."""

    def __init__(
        self,
        text: str = "",
        accent_key: str = "converter",
        face_height: int = 38,
        audio_click_callback: Optional[Callable[[], None]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(text, parent)

        self._accent_key = accent_key
        self._face_height = face_height
        self._audio_click_callback = audio_click_callback
        self._is_hovered = False

        # Token metrics
        self._bevel_rest = TOKENS.dimensions.button.bevel_depth  # 4px
        self._bevel_hover = 3  # 3px hover elevation per prompt
        self._bevel_pressed = TOKENS.dimensions.button.pressed_bevel_depth  # 1px
        self._travel_y = TOKENS.dimensions.button.pressed_translation_y  # 3px
        self._corner_radius = float(TOKENS.radii.md)  # 8px

        # Typography
        self._button_font = QFont(TOKENS.typography.font_family_ui, 13)
        self._button_font.setWeight(QFont.Weight.Bold)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

        # Set fixed height based on face + rest bevel clearance
        self.setFixedHeight(self._face_height + self._bevel_rest)

    @property
    def accent_token(self) -> AccentToken:
        """Retrieve AccentToken from design tokens."""
        return TOKENS.colors.accents.get(
            self._accent_key,
            TOKENS.colors.accents["converter"],
        )

    def set_accent_key(self, accent_key: str) -> None:
        """Update button module accent color."""
        self._accent_key = accent_key
        self.update()

    def set_audio_click_callback(self, callback: Optional[Callable[[], None]]) -> None:
        """Register or remove the audio click feedback callback."""
        self._audio_click_callback = callback

    def sizeHint(self) -> QSize:
        """Preferred size hint."""
        return QSize(160, self._face_height + self._bevel_rest)

    def minimumSizeHint(self) -> QSize:
        """Minimum size hint."""
        return QSize(120, self._face_height + self._bevel_rest)

    # --- Interaction Events ---

    def enterEvent(self, event) -> None:
        self._is_hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._is_hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            if self._audio_click_callback:
                try:
                    self._audio_click_callback()
                except Exception:
                    pass
        super().mousePressEvent(event)
        self.update()

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        self.update()

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self.update()

    # --- Custom Painting ---

    def paintEvent(self, event) -> None:
        """Render tactile 3D button layers using QPainter."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        w = float(self.width())
        total_h = float(self.height())
        face_h = total_h - float(self._bevel_rest)
        r = self._corner_radius
        accent = self.accent_token

        # Determine geometry and palette by state
        if not self.isEnabled():
            y_offset = 0.0
            bevel = 0.0
            face_color = QColor("#202531")
            shadow_color = QColor("#141720")
            text_color = QColor("#525D6B")
            painter.setOpacity(0.4)
        elif self.isDown():
            y_offset = float(self._travel_y)  # +3px
            bevel = float(self._bevel_pressed)  # 1px
            face_color = accent.base_qcolor
            shadow_color = accent.darker_qcolor
            text_color = TOKENS.colors.text.button_dark_qcolor
            painter.setOpacity(1.0)
        elif self._is_hovered:
            y_offset = 0.0
            bevel = float(self._bevel_hover)  # 3px
            # Lightness +4% on hover
            face_color = accent.base_qcolor.lighter(104)
            shadow_color = accent.darker_qcolor
            text_color = TOKENS.colors.text.button_dark_qcolor
            painter.setOpacity(1.0)
        else:
            y_offset = 0.0
            bevel = float(self._bevel_rest)  # 4px
            face_color = accent.base_qcolor
            shadow_color = accent.darker_qcolor
            text_color = TOKENS.colors.text.button_dark_qcolor
            painter.setOpacity(1.0)

        # 1. Draw 3D bottom bevel/shadow layer
        if bevel > 0.0:
            shadow_rect = QRectF(0.0, y_offset, w, face_h + bevel)
            shadow_path = QPainterPath()
            shadow_path.addRoundedRect(shadow_rect, r, r)
            painter.fillPath(shadow_path, shadow_color)

        # 2. Draw front button face
        face_rect = QRectF(0.0, y_offset, w, face_h)
        face_path = QPainterPath()
        face_path.addRoundedRect(face_rect, r, r)
        painter.fillPath(face_path, face_color)

        # 3. Draw focus ring if focused
        if self.hasFocus() and self.isEnabled():
            pen = QPen(TOKENS.colors.border.focus_qcolor, 2.0)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            focus_rect = face_rect.adjusted(1.0, 1.0, -1.0, -1.0)
            painter.drawRoundedRect(focus_rect, r - 1.0, r - 1.0)

        # 4. Draw button text
        painter.setFont(self._button_font)
        painter.setPen(text_color)
        painter.drawText(face_rect, Qt.AlignmentFlag.AlignCenter, self.text())

        painter.end()
