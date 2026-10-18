"""Analog Hardware Controls for Umbra Rack.

Provides authentic skeuomorphic interactive controls for audio console racks:
- AnalogKnob: Spun-metal rotary knob with dot-scale arc, dynamic readout, and mouse drag/wheel control.
- AnalogToggle: Illuminated tactile push button with glowing LED indicator.
- AnalogChoiceSelector: Segmented stepped detent selector for discrete choices (e.g. WAV/MP3/FLAC).
- AnalogFader: Vertical console fader with grooved slider handle and dB markings.
"""

from __future__ import annotations

import math
from typing import List, Optional

from src.ui.qt import (
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPointF,
    QRadialGradient,
    QRectF,
    QSize,
    QSizePolicy,
    Qt,
    QWidget,
    Signal,
)
from src.ui.theme.tokens import TOKENS


class AnalogKnob(QWidget):
    """Skeuomorphic rotary parameter knob with interactive mouse drag and wheel."""

    valueChanged = Signal(float)

    def __init__(
        self,
        name: str,
        label: str = "",
        min_val: float = 0.0,
        max_val: float = 100.0,
        default_val: float = 0.0,
        step: float = 1.0,
        unit: str = "",
        accent_color: str = "#F59E0B",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.name = name
        self.label = label or name.replace("_", " ").title()
        self._min = float(min_val)
        self._max = float(max_val) if max_val > min_val else min_val + 100.0
        self._default = float(default_val)
        self._step = float(step) if step > 0 else 1.0
        self._value = max(self._min, min(self._max, float(default_val)))
        self.unit = unit
        self._accent_color = accent_color

        self.setFixedSize(76, 96)
        self.setCursor(Qt.CursorShape.SizeVerCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

        self._drag_start_y: Optional[float] = None
        self._drag_start_val: float = self._value
        self._is_hovered: bool = False

    # --- Property Accessors ---

    def value(self) -> float:
        return self._value

    def setValue(self, val: float) -> None:
        clamped = max(self._min, min(self._max, float(val)))
        if abs(clamped - self._value) > 1e-5:
            self._value = clamped
            self.valueChanged.emit(self._value)
            self.update()

    def setRange(self, min_val: float, max_val: float, step: float = 1.0) -> None:
        self._min = float(min_val)
        self._max = float(max_val)
        self._step = float(step)
        self.setValue(self._value)

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
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_y = event.position().y()
            self._drag_start_val = self._value
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_start_y is not None:
            dy = self._drag_start_y - event.position().y()  # drag up increases
            span = self._max - self._min
            # 120 pixels for full range sweep
            delta_val = (dy / 120.0) * span
            new_val = self._drag_start_val + delta_val
            # Snap to step if reasonable
            if self._step > 0:
                steps_count = round((new_val - self._min) / self._step)
                new_val = self._min + steps_count * self._step
            self.setValue(new_val)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_y = None
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.setValue(self._default)
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        if delta != 0:
            direction = 1.0 if delta > 0 else -1.0
            inc = self._step if self._step > 0 else (self._max - self._min) / 50.0
            self.setValue(self._value + direction * inc)
            event.accept()
        else:
            super().wheelEvent(event)

    # --- Painting ---

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        w = float(self.width())
        cx = w / 2.0
        cy = 38.0
        radius = 20.0

        # 1. Silkscreen Label at Top
        p.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        p.setPen(QPen(QColor(TOKENS.colors.text.silkscreen_tag)))
        rect_lbl = QRectF(0, 2, w, 14)
        p.drawText(rect_lbl, Qt.AlignmentFlag.AlignCenter, self.label[:12].upper())

        # 2. Dot-Scale Arc (-135 deg to +135 deg, 270 deg span)
        span = self._max - self._min if self._max > self._min else 1.0
        norm = (self._value - self._min) / span
        current_deg = -135.0 + norm * 270.0

        dot_radius = radius + 6.0
        num_dots = 11
        for i in range(num_dots):
            deg = -135.0 + i * (270.0 / (num_dots - 1))
            rad = math.radians(deg - 90.0)
            dx = cx + dot_radius * math.cos(rad)
            dy = cy + dot_radius * math.sin(rad)
            is_active = deg <= current_deg + 1.0
            color = QColor(self._accent_color) if is_active else QColor(255, 255, 255, 30)
            p.setBrush(color)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(dx, dy), 1.6, 1.6)

        # 3. Outer Shadow / Recessed Ring
        shadow_grad = QRadialGradient(cx, cy, radius + 2.0)
        shadow_grad.setColorAt(0.0, QColor(0, 0, 0, 180))
        shadow_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(shadow_grad)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), radius + 2.0, radius + 2.0)

        # 4. Spun-metal Bevel Rim
        rim_grad = QLinearGradient(cx - radius, cy - radius, cx + radius, cy + radius)
        rim_grad.setColorAt(0.0, QColor(70, 56, 44))
        rim_grad.setColorAt(0.5, QColor(32, 24, 18))
        rim_grad.setColorAt(1.0, QColor(90, 72, 56))
        p.setBrush(rim_grad)
        hover_color = QColor(self._accent_color) if self._is_hovered else QColor(0, 0, 0, 200)
        p.setPen(QPen(hover_color, 1.0))
        p.drawEllipse(QPointF(cx, cy), radius, radius)

        # 5. Inner Metal Cap
        cap_r = radius - 3.5
        cap_grad = QRadialGradient(cx - 2, cy - 2, cap_r)
        cap_grad.setColorAt(0.0, QColor(55, 42, 32))
        cap_grad.setColorAt(0.7, QColor(28, 20, 15))
        cap_grad.setColorAt(1.0, QColor(18, 12, 8))
        p.setBrush(cap_grad)
        p.setPen(QPen(QColor(0, 0, 0, 160), 0.8))
        p.drawEllipse(QPointF(cx, cy), cap_r, cap_r)

        # 6. Concentric Machining Rings
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 16), 0.5))
        p.drawEllipse(QPointF(cx, cy), cap_r * 0.65, cap_r * 0.65)
        p.drawEllipse(QPointF(cx, cy), cap_r * 0.35, cap_r * 0.35)

        # 7. Needle Indicator Line
        rad_ind = math.radians(current_deg - 90.0)
        ix_inner = cx + (cap_r * 0.25) * math.cos(rad_ind)
        iy_inner = cy + (cap_r * 0.25) * math.sin(rad_ind)
        ix_outer = cx + (cap_r * 0.90) * math.cos(rad_ind)
        iy_outer = cy + (cap_r * 0.90) * math.sin(rad_ind)

        p.setPen(QPen(QColor(self._accent_color), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(ix_inner, iy_inner), QPointF(ix_outer, iy_outer))

        # Center amber jewel dot
        p.setBrush(QColor(self._accent_color))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), 2.2, 2.2)

        # 8. Digital Readout Box at Bottom
        box_y = 68.0
        box_h = 22.0
        p.setBrush(QColor(18, 12, 8))
        p.setPen(QPen(QColor(255, 255, 255, 20), 1.0))
        p.drawRoundedRect(QRectF(4, box_y, w - 8, box_h), 3, 3)

        # Format display text
        if self._step >= 1.0:
            val_str = f"{int(round(self._value))}"
        elif self._step >= 0.1:
            val_str = f"{self._value:.1f}"
        else:
            val_str = f"{self._value:.2f}"
        if self.unit:
            disp_text = f"{val_str} {self.unit}"
        else:
            disp_text = val_str

        p.setFont(QFont("Menlo, Courier, monospace", 8, QFont.Weight.Bold))
        p.setPen(QPen(QColor("#FCD34D")))
        p.drawText(QRectF(4, box_y, w - 8, box_h), Qt.AlignmentFlag.AlignCenter, disp_text)

        p.end()


class AnalogToggle(QWidget):
    """Illuminated push toggle button with tactile bezel and amber LED."""

    toggled = Signal(bool)

    def __init__(
        self,
        name: str,
        label: str = "",
        default_state: bool = False,
        accent_color: str = "#F59E0B",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.name = name
        self.label = label or name.replace("_", " ").title()
        self._checked = bool(default_state)
        self._accent_color = accent_color
        self._is_hovered: bool = False

        self.setFixedSize(80, 56)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool) -> None:
        if self._checked != bool(checked):
            self._checked = bool(checked)
            self.toggled.emit(self._checked)
            self.update()

    def enterEvent(self, event) -> None:
        self._is_hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._is_hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)
            event.accept()
        else:
            super().mousePressEvent(event)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        w = float(self.width())
        h = float(self.height())

        # 1. Silkscreen Label at Top
        p.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        p.setPen(QPen(QColor(TOKENS.colors.text.silkscreen_tag)))
        p.drawText(QRectF(0, 0, w, 14), Qt.AlignmentFlag.AlignCenter, self.label[:12].upper())

        # 2. Beveled Button Chassis
        btn_rect = QRectF(4, 16, w - 8, h - 20)
        grad = QLinearGradient(btn_rect.topLeft(), btn_rect.bottomLeft())
        if self._checked:
            grad.setColorAt(0.0, QColor(36, 26, 18))
            grad.setColorAt(1.0, QColor(22, 16, 12))
        else:
            grad.setColorAt(0.0, QColor(48, 36, 26))
            grad.setColorAt(1.0, QColor(28, 20, 15))

        p.setBrush(grad)
        border_col = QColor(self._accent_color) if self._is_hovered else QColor(255, 255, 255, 28)
        p.setPen(QPen(border_col, 1.0))
        p.drawRoundedRect(btn_rect, 4, 4)

        # 3. Illuminated LED Lens & Status
        led_cx = btn_rect.left() + 14.0
        led_cy = btn_rect.center().y()
        led_r = 4.5

        if self._checked:
            # Glow halo
            glow = QRadialGradient(led_cx, led_cy, 12.0)
            glow.setColorAt(0.0, QColor(245, 158, 11, 140))
            glow.setColorAt(1.0, QColor(245, 158, 11, 0))
            p.setBrush(glow)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(led_cx, led_cy), 12.0, 12.0)

            # Bright lit lens
            lens_grad = QRadialGradient(led_cx - 1, led_cy - 1, led_r)
            lens_grad.setColorAt(0.0, QColor("#FDE68A"))
            lens_grad.setColorAt(0.6, QColor("#F59E0B"))
            lens_grad.setColorAt(1.0, QColor("#B45309"))
            p.setBrush(lens_grad)
            p.drawEllipse(QPointF(led_cx, led_cy), led_r, led_r)

            status_text = "ENGAGED"
            text_col = QColor("#FDE68A")
        else:
            # Unlit dark lens
            p.setBrush(QColor(40, 24, 16))
            p.setPen(QPen(QColor(0, 0, 0, 180), 0.8))
            p.drawEllipse(QPointF(led_cx, led_cy), led_r, led_r)

            status_text = "BYPASS"
            text_col = QColor(TOKENS.colors.text.muted)

        # 4. Status Text
        p.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        p.setPen(QPen(text_col))
        text_rect = QRectF(btn_rect.left() + 24, btn_rect.top(), btn_rect.width() - 26, btn_rect.height())
        p.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, status_text)

        p.end()


class AnalogChoiceSelector(QWidget):
    """Segmented stepped detent selector for discrete choices (e.g. WAV / MP3 / FLAC)."""

    currentChoiceChanged = Signal(str)

    def __init__(
        self,
        name: str,
        choices: List[str],
        label: str = "",
        default_choice: str = "",
        accent_color: str = "#F59E0B",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.name = name
        self.label = label or name.replace("_", " ").title()
        self.choices = [str(c) for c in choices] if choices else ["DEFAULT"]
        self._current_choice = default_choice if default_choice in self.choices else self.choices[0]
        self._accent_color = accent_color

        self.setFixedHeight(56)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def currentChoice(self) -> str:
        return self._current_choice

    def setCurrentChoice(self, choice: str) -> None:
        if choice in self.choices and choice != self._current_choice:
            self._current_choice = choice
            self.currentChoiceChanged.emit(self._current_choice)
            self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            x = event.position().x()
            w = float(self.width())
            seg_w = w / len(self.choices)
            idx = int(x // seg_w)
            if 0 <= idx < len(self.choices):
                self.setCurrentChoice(self.choices[idx])
            event.accept()
        else:
            super().mousePressEvent(event)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        w = float(self.width())
        h = float(self.height())

        # 1. Silkscreen Label at Top
        p.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        p.setPen(QPen(QColor(TOKENS.colors.text.silkscreen_tag)))
        p.drawText(QRectF(0, 0, w, 14), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.label[:20].upper())

        # 2. Recessed Well Track
        track_rect = QRectF(0, 18, w, 32)
        p.setBrush(QColor(18, 12, 8))
        p.setPen(QPen(QColor(255, 255, 255, 18), 1.0))
        p.drawRoundedRect(track_rect, 4, 4)

        # 3. Choice Segments
        seg_w = w / len(self.choices)
        for i, choice in enumerate(self.choices):
            seg_rect = QRectF(i * seg_w + 2, 20, seg_w - 4, 28)
            is_active = (choice == self._current_choice)

            if is_active:
                # Active metallic brass pill
                pill_grad = QLinearGradient(seg_rect.topLeft(), seg_rect.bottomLeft())
                pill_grad.setColorAt(0.0, QColor(75, 52, 28))
                pill_grad.setColorAt(1.0, QColor(42, 28, 15))
                p.setBrush(pill_grad)
                p.setPen(QPen(QColor(self._accent_color), 1.2))
                p.drawRoundedRect(seg_rect, 3, 3)

                # Text
                p.setFont(QFont("Menlo, Courier, monospace", 8, QFont.Weight.Bold))
                p.setPen(QPen(QColor("#FDE68A")))
            else:
                p.setFont(QFont("Menlo, Courier, monospace", 8, QFont.Weight.Normal))
                p.setPen(QPen(QColor(TOKENS.colors.text.muted)))

            disp = choice.upper()
            if len(disp) > 10:
                disp = disp[:9] + "…"
            p.drawText(seg_rect, Qt.AlignmentFlag.AlignCenter, disp)

        p.end()


class AnalogFader(QWidget):
    """Vertical console slider with grooved metallic handle and center detent."""

    valueChanged = Signal(float)

    def __init__(
        self,
        name: str,
        label: str = "",
        min_val: float = 0.0,
        max_val: float = 100.0,
        default_val: float = 0.0,
        step: float = 1.0,
        unit: str = "",
        accent_color: str = "#F59E0B",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.name = name
        self.label = label or name.replace("_", " ").title()
        self._min = float(min_val)
        self._max = float(max_val) if max_val > min_val else min_val + 100.0
        self._default = float(default_val)
        self._step = float(step) if step > 0 else 1.0
        self._value = max(self._min, min(self._max, float(default_val)))
        self.unit = unit
        self._accent_color = accent_color

        self.setFixedSize(54, 110)
        self.setCursor(Qt.CursorShape.SizeVerCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self._drag_start_y: Optional[float] = None
        self._drag_start_val: float = self._value

    def value(self) -> float:
        return self._value

    def setValue(self, val: float) -> None:
        clamped = max(self._min, min(self._max, float(val)))
        if abs(clamped - self._value) > 1e-5:
            self._value = clamped
            self.valueChanged.emit(self._value)
            self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_y = event.position().y()
            self._drag_start_val = self._value
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_start_y is not None:
            dy = self._drag_start_y - event.position().y()
            span = self._max - self._min
            delta_val = (dy / 70.0) * span
            new_val = self._drag_start_val + delta_val
            if self._step > 0:
                steps_count = round((new_val - self._min) / self._step)
                new_val = self._min + steps_count * self._step
            self.setValue(new_val)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_y = None
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        if delta != 0:
            direction = 1.0 if delta > 0 else -1.0
            inc = self._step if self._step > 0 else (self._max - self._min) / 40.0
            self.setValue(self._value + direction * inc)
            event.accept()
        else:
            super().wheelEvent(event)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        w = float(self.width())
        h = float(self.height())
        cx = w / 2.0

        # 1. Silkscreen Label at Top
        p.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        p.setPen(QPen(QColor(TOKENS.colors.text.silkscreen_tag)))
        p.drawText(QRectF(0, 0, w, 14), Qt.AlignmentFlag.AlignCenter, self.label[:8].upper())

        # 2. Recessed Track Slot
        track_y = 18.0
        track_h = 70.0
        p.setBrush(QColor(14, 10, 6))
        p.setPen(QPen(QColor(0, 0, 0, 200), 1.0))
        p.drawRoundedRect(QRectF(cx - 3.5, track_y, 7.0, track_h), 3, 3)

        # Scale tick marks
        for i in range(5):
            ty = track_y + 4 + i * ((track_h - 8) / 4)
            p.setPen(QPen(QColor(255, 255, 255, 35), 1.0))
            p.drawLine(QPointF(cx - 9, ty), QPointF(cx - 5, ty))
            p.drawLine(QPointF(cx + 5, ty), QPointF(cx + 9, ty))

        # 3. Handle Position (0.0 bottom, 1.0 top)
        span = self._max - self._min if self._max > self._min else 1.0
        norm = (self._value - self._min) / span
        handle_y = (track_y + track_h - 10) - norm * (track_h - 20)

        # Handle Knob
        handle_w = 34.0
        handle_h = 16.0
        h_rect = QRectF(cx - handle_w / 2.0, handle_y - handle_h / 2.0, handle_w, handle_h)

        h_grad = QLinearGradient(h_rect.topLeft(), h_rect.bottomLeft())
        h_grad.setColorAt(0.0, QColor(72, 54, 40))
        h_grad.setColorAt(0.5, QColor(42, 32, 24))
        h_grad.setColorAt(1.0, QColor(24, 18, 12))
        p.setBrush(h_grad)
        p.setPen(QPen(QColor(255, 255, 255, 25), 1.0))
        p.drawRoundedRect(h_rect, 3, 3)

        # Center indicator groove
        p.setPen(QPen(QColor(self._accent_color), 1.8))
        p.drawLine(QPointF(cx - 10, handle_y), QPointF(cx + 10, handle_y))

        # 4. Readout at Bottom
        box_y = 92.0
        p.setFont(QFont("Menlo, Courier, monospace", 7, QFont.Weight.Bold))
        p.setPen(QPen(QColor("#FCD34D")))
        val_str = f"{self._value:.1f}" if self._step < 1.0 else f"{int(round(self._value))}"
        disp = f"{val_str}{self.unit}" if self.unit else val_str
        p.drawText(QRectF(0, box_y, w, 16), Qt.AlignmentFlag.AlignCenter, disp)

        p.end()


class CircularVUMeter(QWidget):
    """Vintage circular analog VU meter with ballistic galvanometer needle.
    
    Supports both Single (110px) and Dual stereo (82px per chamber) modes,
    aged ivory dial face, scale markings (-20 to +3 dB), and red overload peak LED.
    """

    def __init__(
        self,
        is_dual: bool = False,
        diameter: int = 110,
        title: str = "VU",
        accent_color: str = "#F59E0B",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._is_dual = bool(is_dual)
        self._diameter = max(60, int(diameter))
        self._title = title
        self._accent_color = accent_color

        # Dynamic needle angles in degrees (-40.0 resting to +40.0 max)
        self._needle_deg_l: float = -40.0
        self._needle_deg_r: float = -40.0

        # Clipping / Peak warning states
        self._clipped_l: bool = False
        self._clipped_r: bool = False

        # Internal ballistic needles for independent physics stepping
        from src.audio.metering import BallisticNeedle
        self._ballistic_l = BallisticNeedle(stiffness=0.20, damping=0.70)
        self._ballistic_r = BallisticNeedle(stiffness=0.20, damping=0.70)

        if self._is_dual:
            # Dual chamber stereo layout
            self.setFixedSize(self._diameter * 2 + 12, self._diameter)
        else:
            self.setFixedSize(self._diameter, self._diameter)

        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    # --- Level & Angle Setters ---

    def set_angles(self, left_deg: float, right_deg: Optional[float] = None) -> None:
        """Set physical needle deflection angles directly."""
        self._needle_deg_l = max(-40.0, min(42.0, float(left_deg)))
        if right_deg is not None:
            self._needle_deg_r = max(-40.0, min(42.0, float(right_deg)))
        else:
            self._needle_deg_r = self._needle_deg_l
        self.update()

    def set_levels(self, left_db: float, right_db: Optional[float] = None) -> None:
        """Step ballistic needle physics from audio levels in dBFS."""
        self._needle_deg_l = self._ballistic_l.update(float(left_db))
        if right_db is not None:
            self._needle_deg_r = self._ballistic_r.update(float(right_db))
        else:
            self._needle_deg_r = self._needle_deg_l
        self.update()

    def set_level(self, db: float) -> None:
        """Single-channel level update in dBFS."""
        self.set_levels(db, db)

    def set_clipped(self, left_clip: bool, right_clip: Optional[bool] = None) -> None:
        """Set peak overload clip lamp state."""
        self._clipped_l = bool(left_clip)
        self._clipped_r = bool(right_clip if right_clip is not None else left_clip)
        self.update()

    def reset(self) -> None:
        """Reset needles to resting pin and clear peak clip lamps."""
        self._ballistic_l.reset()
        self._ballistic_r.reset()
        self._needle_deg_l = -40.0
        self._needle_deg_r = -40.0
        self._clipped_l = False
        self._clipped_r = False
        self.update()

    # --- Painting ---

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        h = float(self.height())
        radius = h / 2.0 - 2.0

        if self._is_dual:
            # Draw Left and Right Chambers
            cx_l = radius + 2.0
            cx_r = float(self.width()) - radius - 2.0
            cy = h / 2.0

            self._draw_single_meter(p, cx_l, cy, radius, self._needle_deg_l, "L", self._clipped_l)
            self._draw_single_meter(p, cx_r, cy, radius, self._needle_deg_r, "R", self._clipped_r)
        else:
            cx = float(self.width()) / 2.0
            cy = h / 2.0
            self._draw_single_meter(p, cx, cy, radius, self._needle_deg_l, self._title, self._clipped_l)

        p.end()

    def _draw_single_meter(
        self,
        p: QPainter,
        cx: float,
        cy: float,
        radius: float,
        needle_deg: float,
        title: str,
        clipped: bool,
    ) -> None:
        """Draw an authentic circular analog meter chamber."""
        # 1. Spun-Metal Outer Bezel Ring
        outer_rect = QRectF(cx - radius, cy - radius, radius * 2.0, radius * 2.0)
        bezel_grad = QLinearGradient(outer_rect.topLeft(), outer_rect.bottomRight())
        bezel_grad.setColorAt(0.0, QColor("#4A3728"))
        bezel_grad.setColorAt(0.4, QColor("#281C13"))
        bezel_grad.setColorAt(1.0, QColor("#120C08"))
        p.setPen(QPen(QColor("#080503"), 1.5))
        p.setBrush(bezel_grad)
        p.drawEllipse(outer_rect)

        # Highlight edge & inner shadow
        p.setPen(QPen(QColor(255, 255, 255, 30), 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(outer_rect.adjusted(1.0, 1.0, -1.0, -1.0))

        # 2. Recessed Chamber Face (Warm aged ivory gradient)
        face_r = radius * 0.86
        face_rect = QRectF(cx - face_r, cy - face_r, face_r * 2.0, face_r * 2.0)
        dial_grad = QLinearGradient(face_rect.topLeft(), face_rect.bottomLeft())
        dial_grad.setColorAt(0.0, QColor("#FAF2DF"))
        dial_grad.setColorAt(0.85, QColor("#F4E4C6"))
        dial_grad.setColorAt(1.0, QColor("#DEC7A1"))
        p.setPen(QPen(QColor("#3A2A1A"), 1.0))
        p.setBrush(dial_grad)
        p.drawEllipse(face_rect)

        # 3. Printed Scale Arcs
        arc_rect = face_rect.adjusted(face_r * 0.14, face_r * 0.14, -face_r * 0.14, -face_r * 0.14)

        # Black regular arc (-20 to 0 dB, ~50 deg to 125 deg)
        p.setPen(QPen(QColor("#1E1810"), 1.6))
        p.drawArc(arc_rect, 52 * 16, 73 * 16)

        # Red danger arc (0 to +3 dB, ~34 deg to 52 deg)
        p.setPen(QPen(QColor("#B91C1C"), 2.2))
        p.drawArc(arc_rect, 34 * 16, 18 * 16)

        # Scale tick marks & numbers
        ticks = [
            (-20, "-20", -40.0, False),
            (-10, "-10", -22.6, False),
            (-7, "-7", -12.2, False),
            (-5, "-5", -5.2, False),
            (-3, "-3", 1.7, False),
            (-1, "-1", 8.7, False),
            (0, "0", 12.2, False),
            (1, "+1", 18.0, True),
            (2, "+2", 24.0, True),
            (3, "+3", 30.0, True),
        ]

        tick_inner_r = face_r * 0.72
        tick_outer_r = face_r * 0.82
        pivot_y_offset = face_r * 0.35
        pivot = QPointF(cx, cy + pivot_y_offset)

        for val, txt, deg, is_red in ticks:
            rad = math.radians(deg - 90.0)
            tx1 = cx + tick_inner_r * math.cos(rad)
            ty1 = cy + tick_inner_r * math.sin(rad)
            tx2 = cx + tick_outer_r * math.cos(rad)
            ty2 = cy + tick_outer_r * math.sin(rad)

            color = QColor("#B91C1C") if is_red else QColor("#1E1810")
            p.setPen(QPen(color, 1.2))
            p.drawLine(QPointF(tx1, ty1), QPointF(tx2, ty2))

        # 4. Scale Numbers (Selected for readability)
        font_sz = max(5, int(face_r * 0.13))
        p.setFont(QFont("Helvetica Neue, Arial", font_sz, QFont.Weight.Bold))
        p.setPen(QColor("#1E1810"))
        p.drawText(QRectF(cx - face_r * 0.60, cy - face_r * 0.35, face_r * 0.35, face_r * 0.22), Qt.AlignmentFlag.AlignCenter, "-20")
        p.drawText(QRectF(cx - face_r * 0.38, cy - face_r * 0.58, face_r * 0.30, face_r * 0.22), Qt.AlignmentFlag.AlignCenter, "-10")
        p.drawText(QRectF(cx - face_r * 0.15, cy - face_r * 0.70, face_r * 0.30, face_r * 0.22), Qt.AlignmentFlag.AlignCenter, "-3")
        p.drawText(QRectF(cx + face_r * 0.12, cy - face_r * 0.65, face_r * 0.25, face_r * 0.22), Qt.AlignmentFlag.AlignCenter, "0")
        p.setPen(QColor("#B91C1C"))
        p.drawText(QRectF(cx + face_r * 0.36, cy - face_r * 0.45, face_r * 0.30, face_r * 0.22), Qt.AlignmentFlag.AlignCenter, "+3")

        # 5. Silkscreen Logo Label ("VU" / "UA")
        lbl_font_sz = max(6, int(face_r * 0.18))
        p.setFont(QFont("Helvetica Neue, Arial", lbl_font_sz, QFont.Weight.Bold))
        p.setPen(QColor("#241A12"))
        p.drawText(QRectF(cx - face_r * 0.40, cy + face_r * 0.05, face_r * 0.80, face_r * 0.25), Qt.AlignmentFlag.AlignCenter, title)

        # 6. Peak Overload Clip LED Lamp (Upper Right)
        led_x = cx + face_r * 0.62
        led_y = cy - face_r * 0.55
        led_r = max(2.5, face_r * 0.07)

        # LED label "PK"
        p.setFont(QFont("Helvetica Neue, Arial", max(4, int(face_r * 0.09)), QFont.Weight.Bold))
        p.setPen(QColor("#544030"))
        p.drawText(QRectF(led_x - 12, led_y - 12, 24, 10), Qt.AlignmentFlag.AlignCenter, "PK")

        if clipped:
            # Active glowing red LED
            glow = QRadialGradient(led_x, led_y, led_r * 2.8)
            glow.setColorAt(0.0, QColor(239, 68, 68, 255))
            glow.setColorAt(0.5, QColor(220, 38, 38, 160))
            glow.setColorAt(1.0, QColor(220, 38, 38, 0))
            p.setBrush(glow)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(led_x, led_y), led_r * 2.5, led_r * 2.5)

            p.setBrush(QColor("#EF4444"))
            p.setPen(QPen(QColor("#FFFFFF"), 0.8))
            p.drawEllipse(QPointF(led_x, led_y), led_r, led_r)
        else:
            # Off unlit dark maroon jewel
            p.setBrush(QColor("#3A1414"))
            p.setPen(QPen(QColor("#200808"), 0.8))
            p.drawEllipse(QPointF(led_x, led_y), led_r, led_r)

        # 7. Tapered Galvanometer Needle
        rad = math.radians(needle_deg - 90.0)
        tip_r = face_r * 0.90
        tip = QPointF(cx + tip_r * math.cos(rad), cy + pivot_y_offset + tip_r * math.sin(rad))

        # Needle shadow
        shadow_offset = QPointF(1.0, 1.5)
        p.setPen(QPen(QColor(0, 0, 0, 80), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(pivot + shadow_offset, tip + shadow_offset)

        # Physical needle line (Red vintage finish)
        p.setPen(QPen(QColor("#DC2626"), 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(pivot, tip)

        # 8. Pivot Cap
        p.setPen(QPen(QColor("#000000"), 1.0))
        p.setBrush(QColor("#1A120B"))
        cap_r = max(3.5, face_r * 0.12)
        p.drawEllipse(pivot, cap_r, cap_r)

        # Pivot center jewel dot
        p.setBrush(QColor("#544030"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(pivot, cap_r * 0.45, cap_r * 0.45)


class LEDMeterLadder(QWidget):
    """12-segment vertical audio level indicator ladder with optical glow and peak hold.
    
    Segments Composition (bottom to top):
        1-8:   Green (#22C55E) - Normal operating level (-42 to -12 dBFS)
        9-10:  Amber (#F59E0B) - Approaching threshold (-8 to -4 dBFS)
        11-12: Red   (#EF4444) - Peak overload / clipping (-1 to 0 dBFS)
    """

    THRESHOLDS = [
        -42.0, -36.0, -30.0, -24.0, -18.0, -15.0, -12.0, -10.0,  # Green 1-8
        -6.0, -3.0,                                               # Amber 9-10
        -1.0, 0.0,                                                # Red 11-12
    ]

    def __init__(
        self,
        width: int = 14,
        height: int = 96,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._width = max(10, int(width))
        self._height = max(40, int(height))
        self.setFixedSize(self._width, self._height)

        self._current_db: float = -80.0
        self._peak_hold_idx: int = -1
        self._peak_hold_ticks: int = 0
        self._active_segments: int = 0

    def set_level(self, dbfs: float) -> None:
        """Update active segments based on input in dBFS."""
        self._current_db = float(dbfs)

        # Determine how many segments light up
        active = 0
        for i, thresh in enumerate(self.THRESHOLDS):
            if self._current_db >= thresh:
                active = i + 1

        self._active_segments = active

        # Peak hold logic: hold peak dot for ~60 frames (1 second @ 60 FPS)
        if active >= self._peak_hold_idx:
            self._peak_hold_idx = active
            self._peak_hold_ticks = 60
        elif self._peak_hold_ticks > 0:
            self._peak_hold_ticks -= 1
        else:
            if self._peak_hold_idx > 0:
                self._peak_hold_idx -= 1  # Decay downwards
            self._peak_hold_ticks = 4

        self.update()

    def reset(self) -> None:
        """Reset all LEDs to unlit state."""
        self._current_db = -80.0
        self._active_segments = 0
        self._peak_hold_idx = -1
        self._peak_hold_ticks = 0
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = float(self.width())
        h = float(self.height())

        # Recessed background channel well
        p.setBrush(QColor("#0D0906"))
        p.setPen(QPen(QColor(255, 255, 255, 18), 1.0))
        p.drawRoundedRect(QRectF(0, 0, w, h), 3, 3)

        num_segs = 12
        pad_y = 4.0
        avail_h = h - pad_y * 2.0
        gap = 2.0
        seg_h = (avail_h - gap * (num_segs - 1)) / num_segs
        seg_w = w - 6.0
        seg_x = 3.0

        for i in range(num_segs):
            # Index from bottom (0 = bottom segment 1, 11 = top segment 12)
            seg_idx = i
            seg_y = (h - pad_y - seg_h) - i * (seg_h + gap)
            rect = QRectF(seg_x, seg_y, seg_w, seg_h)

            is_lit = (seg_idx < self._active_segments)
            is_peak = (seg_idx == self._peak_hold_idx - 1)

            # Determine color tier
            if seg_idx < 8:
                lit_color = QColor("#22C55E")     # Green
                dim_color = QColor("#122A16")
                glow_color = QColor(34, 197, 94, 120)
            elif seg_idx < 10:
                lit_color = QColor("#F59E0B")     # Amber
                dim_color = QColor("#302008")
                glow_color = QColor(245, 158, 11, 140)
            else:
                lit_color = QColor("#EF4444")     # Red
                dim_color = QColor("#341212")
                glow_color = QColor(239, 68, 68, 160)

            if is_lit or is_peak:
                # Lit optical segment with halo glow
                p.setBrush(glow_color)
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRoundedRect(rect.adjusted(-1.0, -0.5, 1.0, 0.5), 1.5, 1.5)

                p.setBrush(lit_color)
                p.setPen(QPen(QColor(255, 255, 255, 90), 0.5))
                p.drawRoundedRect(rect, 1.0, 1.0)
            else:
                # Unlit jewel cap
                p.setBrush(dim_color)
                p.setPen(QPen(QColor(0, 0, 0, 120), 0.5))
                p.drawRoundedRect(rect, 1.0, 1.0)

        p.end()

