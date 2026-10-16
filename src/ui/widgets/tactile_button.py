"""ChunkyButton / TactileButton - Analog Console Amber Illuminated Button.

Subclasses QPushButton with custom QPainter rendering:
- Analog Console amber backlighting per DESIGN.md Section 6.1
- Off state: Warm dark amber lens (#3D2813 -> #24180A) with silkscreen text (#8C7355)
- Hover state: 40% amber illumination with halo glow
- Pressed state: 100% lit amber lens (#F59E0B -> #D97706), filament core (#FFF3DB), +2px physical travel
- 3D mechanical bevels: raised ring (#2A2016) with top highlight (rgba(255,255,255,0.15))
- Corner radius: 6px per DESIGN.md
- Tactile audio click callback hook preserved
"""

from __future__ import annotations

from typing import Callable, Optional

from src.ui.qt import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPointF,
    QPushButton,
    QRadialGradient,
    QRectF,
    QSize,
    Qt,
    QWidget,
)

from src.ui.theme.tokens import TOKENS, AccentToken


class TactileButton(QPushButton):
    """Analog Console illuminated push button with 3D mechanical bezel and amber lens."""

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
        self._bevel_pressed = TOKENS.dimensions.button.pressed_bevel_depth  # 1px
        self._travel_y = 2  # 2px physical travel per DESIGN.md Section 6.1
        self._corner_radius = float(TOKENS.radii.button)  # 6px

        # Typography: 12px Bold with Helvetica Neue
        self._button_font = QFont("Helvetica Neue")
        self._button_font.setFamilies(["Helvetica Neue", "Arial"])
        self._button_font.setPixelSize(12)
        self._button_font.setWeight(QFont.Weight.Bold)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

        # Fixed height = face + bevel rest
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
        return QSize(160, self._face_height + self._bevel_rest)

    def minimumSizeHint(self) -> QSize:
        return QSize(100, self._face_height + self._bevel_rest)

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

    # --- Skeuomorphic Custom Painting ---

    def paintEvent(self, event) -> None:
        """Render amber illuminated button with recessed well, metallic bezel, and lens."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        w = float(self.width())
        total_h = float(self.height())
        face_h = total_h - float(self._bevel_rest)
        r = self._corner_radius

        is_down = self.isDown()
        is_hover = self._is_hovered and self.isEnabled()
        is_enabled = self.isEnabled()

        y_offset = float(self._travel_y) if is_down else 0.0

        # 1. Base Recessed Well (#120E0B)
        well_rect = QRectF(0.0, 0.0, w, total_h)
        well_path = QPainterPath()
        well_path.addRoundedRect(well_rect, r + 1.0, r + 1.0)
        painter.fillPath(well_path, QColor("#120E0B"))

        # 2. Bevel Ring / Outer Mechanical Body (#2A2016)
        bezel_rect = QRectF(1.0, y_offset + 1.0, w - 2.0, face_h + (1.0 if not is_down else 0.0))
        bezel_path = QPainterPath()
        bezel_path.addRoundedRect(bezel_rect, r, r)
        painter.fillPath(bezel_path, QColor("#2A2016"))

        # 3. Lens Body (QLinearGradient)
        lens_rect = bezel_rect.adjusted(2.0, 2.0, -2.0, -2.0)
        lens_path = QPainterPath()
        lens_path.addRoundedRect(lens_rect, max(2.0, r - 2.0), max(2.0, r - 2.0))

        lens_grad = QLinearGradient(0.0, lens_rect.top(), 0.0, lens_rect.bottom())

        if not is_enabled:
            lens_grad.setColorAt(0.0, QColor("#221A12"))
            lens_grad.setColorAt(1.0, QColor("#140F0A"))
            text_color = QColor("#4A3B2C")
        elif is_down:
            # 100% Lit Amber
            lens_grad.setColorAt(0.0, QColor("#F59E0B"))
            lens_grad.setColorAt(1.0, QColor("#D97706"))
            text_color = QColor("#120E0B")
        elif is_hover:
            # 40% Lit Amber
            lens_grad.setColorAt(0.0, QColor("#7A4C18"))
            lens_grad.setColorAt(1.0, QColor("#4D2C0C"))
            text_color = QColor("#D4A265")
        else:
            # Off state
            lens_grad.setColorAt(0.0, QColor("#3D2813"))
            lens_grad.setColorAt(1.0, QColor("#24180A"))
            text_color = QColor("#8C7355")

        painter.fillPath(lens_path, lens_grad)

        # 4. Filament Core (when lit / pressed)
        if is_down and is_enabled:
            filament = QRadialGradient(lens_rect.center(), lens_rect.width() * 0.4)
            filament.setColorAt(0.0, QColor(255, 243, 219, 200))
            filament.setColorAt(0.5, QColor(245, 158, 11, 100))
            filament.setColorAt(1.0, QColor(245, 158, 11, 0))
            painter.fillPath(lens_path, filament)

        # 5. Top Bevel Highlight (1px light reflection)
        highlight_pen = QPen(QColor(255, 255, 255, 38 if not is_down else 15), 1.0)
        painter.setPen(highlight_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(
            QPointF(lens_rect.left() + r, lens_rect.top()),
            QPointF(lens_rect.right() - r, lens_rect.top()),
        )

        # 6. Focus Ring
        if self.hasFocus() and is_enabled:
            focus_pen = QPen(QColor("#F59E0B"), 2.0)
            painter.setPen(focus_pen)
            painter.drawRoundedRect(well_rect.adjusted(1.0, 1.0, -1.0, -1.0), r, r)

        # 7. Button Label
        painter.setFont(self._button_font)
        painter.setPen(text_color)
        painter.drawText(lens_rect, Qt.AlignmentFlag.AlignCenter, self.text())

        painter.end()
