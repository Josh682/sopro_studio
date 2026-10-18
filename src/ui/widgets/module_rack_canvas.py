"""ModuleRackCanvas - Skeuomorphic Analog Hardware Rack Canvas for Launcher Cards.

Renders authentic analog console hardware controls for all 9 modules matching
reference/main_dashboard.jpg with pixel precision:
- Concentric spun-metal rotary knobs with dot scale arcs
- Circular analog VU meters with dial scales and needles
- Amber illuminated square push-buttons
- Vertical & horizontal console faders with grooved slider handles
- Golden audio waveform displays
- Multi-segment LED meter ladders
- CRT terminal metadata display
"""

from __future__ import annotations

import math
from typing import Optional

from src.ui.qt import (
    QColor,
    QFont,
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
)

from src.ui.theme.tokens import TOKENS


class ModuleRackCanvas(QWidget):
    """Interactive canvas widget rendering module-specific analog hardware controls."""

    def __init__(self, module_id: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.module_id = module_id
        self.setFixedHeight(160)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._is_hovered = False

        # Dynamic needle angles for [MOD-04] and [MOD-08]
        self._needle_deg_l: float = -20.0
        self._needle_deg_r: float = -8.0
        self._needle_deg_norm: float = -10.0

    def set_meter_angles(self, needle_l: float, needle_r: Optional[float] = None) -> None:
        """Update needle deflection angles for analog VU meters."""
        self._needle_deg_l = max(-40.0, min(42.0, float(needle_l)))
        self._needle_deg_norm = self._needle_deg_l
        if needle_r is not None:
            self._needle_deg_r = max(-40.0, min(42.0, float(needle_r)))
        else:
            self._needle_deg_r = self._needle_deg_l
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            p = self.parent()
            if p and hasattr(p, "open_requested"):
                p.open_requested.emit(p.module_id)
        super().mousePressEvent(event)

    def enterEvent(self, event) -> None:
        self._is_hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._is_hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        w = float(self.width())
        h = float(self.height())

        # Render specific module hardware configuration
        method_name = f"_paint_{self.module_id}"
        painter_method = getattr(self, method_name, self._paint_default)
        painter_method(painter, w, h)

        # Check drag state from parent LauncherCard
        parent = self.parent()
        drag_state = getattr(parent, "_drag_state", None)
        if drag_state:
            self._paint_drop_overlay(painter, w, h, drag_state)

        painter.end()

    # =========================================================================
    # REUSABLE HARDWARE PRIMITIVE DRAWING ROUTINES
    # =========================================================================

    def _draw_knob(
        self,
        p: QPainter,
        cx: float,
        cy: float,
        radius: float = 22.0,
        label: str = "",
        dots: bool = True,
        angle_deg: float = -45.0,
    ) -> None:
        """Draw a concentric spun-aluminum rotary knob with dot scale and label."""
        # 1. Dot Scale Arc (-135 to +135 deg)
        if dots:
            dot_radius = radius + 7.0
            for i in range(9):
                deg = -135.0 + i * 33.75
                rad = math.radians(deg - 90.0)
                dx = cx + dot_radius * math.cos(rad)
                dy = cy + dot_radius * math.sin(rad)

                # Color: active if past angle, else dark
                if deg <= angle_deg + 10:
                    dot_color = QColor("#F59E0B") if i < 7 else QColor("#EF4444")
                else:
                    dot_color = QColor("#332418")

                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(dot_color)
                p.drawEllipse(QPointF(dx, dy), 1.8, 1.8)

        # 2. Outer Rim / Shadow Cavity
        rim_rect = QRectF(cx - radius, cy - radius, radius * 2.0, radius * 2.0)
        p.setPen(QPen(QColor("#080503"), 1.0))
        p.setBrush(QColor("#18110B"))
        p.drawEllipse(rim_rect)

        # Outer Fluted Metal Bevel
        bevel_r = radius * 0.94
        p.setPen(QPen(QColor(255, 255, 255, 30), 0.8))
        p.setBrush(QColor("#241A12"))
        p.drawEllipse(QRectF(cx - bevel_r, cy - bevel_r, bevel_r * 2.0, bevel_r * 2.0))

        # 3. Metallic Spun-Aluminum Cap (Brushed Silver Machined Finish)
        cap_r = radius * 0.80
        cap_rect = QRectF(cx - cap_r, cy - cap_r, cap_r * 2.0, cap_r * 2.0)

        cap_grad = QLinearGradient(cap_rect.topLeft(), cap_rect.bottomRight())
        cap_grad.setColorAt(0.0, QColor("#F1F5F9"))  # Bright specular highlight
        cap_grad.setColorAt(0.25, QColor("#94A3B8")) # Brushed slate silver
        cap_grad.setColorAt(0.50, QColor("#CBD5E1")) # Secondary metallic sheen
        cap_grad.setColorAt(0.75, QColor("#64748B")) # Machined groove tone
        cap_grad.setColorAt(1.0, QColor("#334155"))  # Deep shadow edge

        p.setPen(QPen(QColor(255, 255, 255, 80), 1.0))
        p.setBrush(cap_grad)
        p.drawEllipse(cap_rect)

        # 4. Concentric Machined Spun Lathe Lines
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 40), 0.8))
        p.drawEllipse(QRectF(cx - cap_r * 0.68, cy - cap_r * 0.68, cap_r * 1.36, cap_r * 1.36))
        p.setPen(QPen(QColor(0, 0, 0, 35), 0.8))
        p.drawEllipse(QRectF(cx - cap_r * 0.40, cy - cap_r * 0.40, cap_r * 0.80, cap_r * 0.80))

        # 5. Position Pointer Notch (White line with dark shadow)
        ptr_rad = math.radians(angle_deg - 90.0)
        p1 = QPointF(cx + (cap_r * 0.28) * math.cos(ptr_rad), cy + (cap_r * 0.28) * math.sin(ptr_rad))
        p2 = QPointF(cx + (cap_r * 0.90) * math.cos(ptr_rad), cy + (cap_r * 0.90) * math.sin(ptr_rad))
        # Shadow
        p.setPen(QPen(QColor(0, 0, 0, 160), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(p1.x() + 0.6, p1.y() + 0.6), QPointF(p2.x() + 0.6, p2.y() + 0.6))
        # White marker
        p.setPen(QPen(QColor("#FFFFFF"), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(p1, p2)

        # 6. Center Machined Dimple
        p.setPen(QPen(QColor(0, 0, 0, 100), 0.8))
        p.setBrush(QColor("#475569"))
        p.drawEllipse(QPointF(cx, cy), 2.4, 2.4)

        # 7. Sub-Knob Silkscreen Label
        if label:
            p.setFont(QFont("Menlo", 8, QFont.Weight.Bold))
            p.setPen(QColor("#B5A899"))
            lbl_rect = QRectF(cx - 45.0, cy + radius + 3.0, 90.0, 14.0)
            p.drawText(lbl_rect, Qt.AlignmentFlag.AlignCenter, label)

    def _draw_button(
        self,
        p: QPainter,
        x: float,
        y: float,
        size: float = 36.0,
        label: str = "OPEN",
        is_lit: bool = True,
    ) -> None:
        """Draw an amber illuminated square push-button."""
        r = 5.0
        btn_rect = QRectF(x, y, size, size)

        # Recessed bezel frame
        p.setPen(QPen(QColor("#080503"), 1.0))
        p.setBrush(QColor("#18110B"))
        p.drawRoundedRect(btn_rect, r, r)

        # Amber lens
        lens_rect = btn_rect.adjusted(2.5, 2.5, -2.5, -2.5)
        lens_grad = QLinearGradient(lens_rect.topLeft(), lens_rect.bottomLeft())

        if is_lit:
            lens_grad.setColorAt(0.0, QColor("#FBBF24"))
            lens_grad.setColorAt(0.6, QColor("#F59E0B"))
            lens_grad.setColorAt(1.0, QColor("#D97706"))
            p.setBrush(lens_grad)
            p.setPen(QPen(QColor(255, 255, 255, 80), 1.0))
            p.drawRoundedRect(lens_rect, r - 1.0, r - 1.0)

            # Warm incandescent core
            core = QRadialGradient(lens_rect.center(), size * 0.42)
            core.setColorAt(0.0, QColor(255, 253, 245, 220))
            core.setColorAt(0.5, QColor(251, 191, 36, 120))
            core.setColorAt(1.0, QColor(217, 119, 6, 0))
            p.setBrush(core)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(lens_rect, r - 1.0, r - 1.0)
        else:
            lens_grad.setColorAt(0.0, QColor("#3D2813"))
            lens_grad.setColorAt(1.0, QColor("#24180A"))
            p.setBrush(lens_grad)
            p.setPen(QPen(QColor(255, 255, 255, 20), 1.0))
            p.drawRoundedRect(lens_rect, r - 1.0, r - 1.0)

        # Text label beside button
        if label:
            p.setFont(QFont("Helvetica Neue", 10, QFont.Weight.Bold))
            p.setPen(QColor("#EDE6DC"))
            text_rect = QRectF(x + size + 7.0, y + (size - 18.0) / 2.0, 42.0, 18.0)
            p.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label)

    def _draw_vu_meter(
        self,
        p: QPainter,
        cx: float,
        cy: float,
        radius: float = 38.0,
        needle_deg: float = -15.0,
        title: str = "VU",
    ) -> None:
        """Draw a vintage circular analog VU meter with warm face and needle."""
        # 1. Bezel Ring
        outer_rect = QRectF(cx - radius, cy - radius, radius * 2.0, radius * 2.0)
        bezel_grad = QLinearGradient(outer_rect.topLeft(), outer_rect.bottomRight())
        bezel_grad.setColorAt(0.0, QColor("#4A3728"))
        bezel_grad.setColorAt(0.5, QColor("#281C13"))
        bezel_grad.setColorAt(1.0, QColor("#120C08"))
        p.setPen(QPen(QColor("#080503"), 1.5))
        p.setBrush(bezel_grad)
        p.drawEllipse(outer_rect)

        # Inner shadow rim
        p.setPen(QPen(QColor(0, 0, 0, 180), 1.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(outer_rect.adjusted(1.5, 1.5, -1.5, -1.5))

        # 2. Dial Face
        face_r = radius * 0.86
        face_rect = QRectF(cx - face_r, cy - face_r, face_r * 2.0, face_r * 2.0)
        dial_grad = QLinearGradient(face_rect.topLeft(), face_rect.bottomLeft())
        dial_grad.setColorAt(0.0, QColor("#FAF2DF"))
        dial_grad.setColorAt(0.85, QColor("#F4E4C6"))
        dial_grad.setColorAt(1.0, QColor("#DEC7A1"))
        p.setPen(QPen(QColor("#3A2A1A"), 1.0))
        p.setBrush(dial_grad)
        p.drawEllipse(face_rect)

        # 3. Arc and Tick Marks
        p.setBrush(Qt.BrushStyle.NoBrush)
        arc_rect = face_rect.adjusted(6.0, 6.0, -6.0, -6.0)

        # Black regular arc (-20 to 0)
        p.setPen(QPen(QColor("#1E1810"), 1.4))
        p.drawArc(arc_rect, 50 * 16, 75 * 16)

        # Red danger arc (0 to +3)
        p.setPen(QPen(QColor("#DC2626"), 2.0))
        p.drawArc(arc_rect, 35 * 16, 18 * 16)

        # 4. Small Scale Numbers
        p.setFont(QFont("Helvetica Neue", 6, QFont.Weight.Bold))
        p.setPen(QColor("#1E1810"))
        p.drawText(QRectF(cx - 24.0, cy - face_r * 0.45, 16.0, 10.0), Qt.AlignmentFlag.AlignCenter, "-10")
        p.drawText(QRectF(cx - 10.0, cy - face_r * 0.55, 12.0, 10.0), Qt.AlignmentFlag.AlignCenter, "-3")
        p.drawText(QRectF(cx + 6.0, cy - face_r * 0.52, 10.0, 10.0), Qt.AlignmentFlag.AlignCenter, "0")
        p.setPen(QColor("#DC2626"))
        p.drawText(QRectF(cx + 17.0, cy - face_r * 0.40, 12.0, 10.0), Qt.AlignmentFlag.AlignCenter, "+3")

        # 5. Label ("VU" / "UA")
        p.setFont(QFont("Helvetica Neue", 8, QFont.Weight.Bold))
        p.setPen(QColor("#1E1810"))
        p.drawText(QRectF(cx - 18.0, cy + 4.0, 36.0, 14.0), Qt.AlignmentFlag.AlignCenter, title)

        # 6. Analog Needle
        rad = math.radians(needle_deg - 90.0)
        pivot = QPointF(cx, cy + face_r * 0.4)
        tip = QPointF(cx + face_r * 0.85 * math.cos(rad), cy + face_r * 0.85 * math.sin(rad))

        p.setPen(QPen(QColor("#DC2626"), 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(pivot, tip)

        # Needle pivot cap
        p.setPen(QPen(QColor("#000000"), 0.8))
        p.setBrush(QColor("#241A12"))
        p.drawEllipse(pivot, 3.0, 3.0)

    def _draw_fader(
        self,
        p: QPainter,
        x: float,
        y: float,
        width: float = 30.0,
        height: float = 94.0,
        is_vertical: bool = True,
        pos: float = 0.5,
    ) -> None:
        """Draw an analog mixer fader slot and silver ribbed handle."""
        if is_vertical:
            # Slot
            slot_w = 5.0
            slot_x = x + (width - slot_w) / 2.0
            p.setPen(QPen(QColor("#080503"), 1.0))
            p.setBrush(QColor("#0D0906"))
            p.drawRoundedRect(QRectF(slot_x, y, slot_w, height), 2.5, 2.5)

            # Ticks along fader
            p.setPen(QPen(QColor("#544030"), 1.0))
            for i in range(9):
                ty = y + 4.0 + i * (height - 8.0) / 8.0
                p.drawLine(QPointF(x, ty), QPointF(x + 5.0, ty))
                p.drawLine(QPointF(x + width - 5.0, ty), QPointF(x + width, ty))

            # Fader Cap (Chunky metallic slider knob)
            knob_w = 28.0
            knob_h = 28.0
            knob_x = x + (width - knob_w) / 2.0
            knob_y = y + (height - knob_h) * (1.0 - pos)
            knob_rect = QRectF(knob_x, knob_y, knob_w, knob_h)

            knob_grad = QLinearGradient(knob_rect.topLeft(), knob_rect.topRight())
            knob_grad.setColorAt(0.0, QColor("#F1F5F9"))
            knob_grad.setColorAt(0.25, QColor("#CBD5E1"))
            knob_grad.setColorAt(0.50, QColor("#94A3B8"))
            knob_grad.setColorAt(0.75, QColor("#E2E8F0"))
            knob_grad.setColorAt(1.0, QColor("#64748B"))

            p.setPen(QPen(QColor(255, 255, 255, 70), 1.0))
            p.setBrush(knob_grad)
            p.drawRoundedRect(knob_rect, 3.5, 3.5)

            # Outer rim shadow
            p.setPen(QPen(QColor(0, 0, 0, 160), 1.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(knob_rect, 3.5, 3.5)

            # Horizontal ribs on vertical fader handle
            p.setPen(QPen(QColor(0, 0, 0, 110), 1.0))
            mid_y = knob_rect.center().y()
            p.drawLine(QPointF(knob_rect.left() + 4.0, mid_y - 5.0), QPointF(knob_rect.right() - 4.0, mid_y - 5.0))
            p.drawLine(QPointF(knob_rect.left() + 4.0, mid_y + 5.0), QPointF(knob_rect.right() - 4.0, mid_y + 5.0))

            # Center indicator line (White engraved marker)
            p.setPen(QPen(QColor("#FFFFFF"), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(knob_rect.left() + 2.0, mid_y), QPointF(knob_rect.right() - 2.0, mid_y))
            p.setPen(QPen(QColor(0, 0, 0, 180), 0.8))
            p.drawLine(QPointF(knob_rect.left() + 2.0, mid_y + 1.0), QPointF(knob_rect.right() - 2.0, mid_y + 1.0))
        else:
            # Horizontal fader (Standardized 142x26)
            slot_h = 5.0
            slot_y = y + (height - slot_h) / 2.0
            p.setPen(QPen(QColor("#080503"), 1.0))
            p.setBrush(QColor("#0D0906"))
            p.drawRoundedRect(QRectF(x, slot_y, width, slot_h), 2.5, 2.5)

            # Ticks
            p.setPen(QPen(QColor("#544030"), 1.0))
            for i in range(9):
                tx = x + 5.0 + i * (width - 10.0) / 8.0
                p.drawLine(QPointF(tx, y), QPointF(tx, y + 5.0))
                p.drawLine(QPointF(tx, y + height - 5.0), QPointF(tx, y + height))

            # Fader Cap (Chunky metallic slider knob)
            knob_w = 28.0
            knob_h = 26.0
            knob_x = x + (width - knob_w) * pos
            knob_y = y + (height - knob_h) / 2.0
            knob_rect = QRectF(knob_x, knob_y, knob_w, knob_h)

            knob_grad = QLinearGradient(knob_rect.topLeft(), knob_rect.bottomLeft())
            knob_grad.setColorAt(0.0, QColor("#F1F5F9"))
            knob_grad.setColorAt(0.25, QColor("#CBD5E1"))
            knob_grad.setColorAt(0.50, QColor("#94A3B8"))
            knob_grad.setColorAt(0.75, QColor("#E2E8F0"))
            knob_grad.setColorAt(1.0, QColor("#64748B"))

            p.setPen(QPen(QColor(255, 255, 255, 70), 1.0))
            p.setBrush(knob_grad)
            p.drawRoundedRect(knob_rect, 3.5, 3.5)

            # Outer rim shadow
            p.setPen(QPen(QColor(0, 0, 0, 160), 1.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(knob_rect, 3.5, 3.5)

            # Vertical grip lines
            p.setPen(QPen(QColor(0, 0, 0, 110), 1.0))
            mid_x = knob_rect.center().x()
            p.drawLine(QPointF(mid_x - 5.0, knob_rect.top() + 4.0), QPointF(mid_x - 5.0, knob_rect.bottom() - 4.0))
            p.drawLine(QPointF(mid_x + 5.0, knob_rect.top() + 4.0), QPointF(mid_x + 5.0, knob_rect.bottom() - 4.0))

            # Center indicator line
            p.setPen(QPen(QColor("#FFFFFF"), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(QPointF(mid_x, knob_rect.top() + 2.0), QPointF(mid_x, knob_rect.bottom() - 2.0))
            p.setPen(QPen(QColor(0, 0, 0, 180), 0.8))
            p.drawLine(QPointF(mid_x + 1.0, knob_rect.top() + 2.0), QPointF(mid_x + 1.0, knob_rect.bottom() - 2.0))

    def _draw_led(self, p: QPainter, cx: float, cy: float, color_hex: str) -> None:
        """Draw a lit LED dot indicator with subtle halo."""
        p.setPen(QPen(QColor("#0A0604"), 0.8))
        p.setBrush(QColor(color_hex))
        p.drawEllipse(QPointF(cx, cy), 3.0, 3.0)

    def _draw_readout_box(self, p: QPainter, x: float, y: float, w: float, h: float, text: str, caption: str = "") -> None:
        """Draw a dark digital readout box with amber text and label."""
        rect = QRectF(x, y, w, h)
        p.setPen(QPen(QColor("#000000"), 1.0))
        p.setBrush(QColor("#120E0B"))
        p.drawRoundedRect(rect, 3.0, 3.0)

        # Highlight edge
        p.setPen(QPen(QColor(255, 255, 255, 15), 1.0))
        p.drawLine(rect.topLeft(), rect.topRight())

        # Main Text
        p.setFont(QFont("Helvetica Neue", 11, QFont.Weight.Bold))
        p.setPen(QColor("#FCD34D"))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

        # Caption underneath
        if caption:
            p.setFont(QFont("Helvetica Neue", 9))
            p.setPen(QColor("#9E9182"))
            p.drawText(QRectF(x - 5.0, y + h + 2.0, w + 10.0, 14.0), Qt.AlignmentFlag.AlignCenter, caption)

    # =========================================================================
    # MODULE-SPECIFIC HARDWARE LAYOUTS
    # =========================================================================

    def _paint_converter(self, p: QPainter, w: float, h: float) -> None:
        """[MOD-01] 3 Knobs with dot arcs and LED pairs - grounded lower."""
        y_center = 104.0
        self._draw_knob(p, 48.0, y_center, radius=22.0, label="FORMAT", dots=True, angle_deg=-60.0)

        self._draw_led(p, 99.0, y_center - 10.0, "#F59E0B")
        self._draw_led(p, 99.0, y_center + 10.0, "#EAB308")

        self._draw_knob(p, 150.0, y_center, radius=22.0, label="BIT DEPTH", dots=True, angle_deg=0.0)

        self._draw_led(p, 201.0, y_center - 10.0, "#22C55E")
        self._draw_led(p, 201.0, y_center + 10.0, "#F59E0B")

        self._draw_knob(p, 252.0, y_center, radius=22.0, label="SAMPLE RATE", dots=True, angle_deg=45.0)

    def _paint_separator(self, p: QPainter, w: float, h: float) -> None:
        """[MOD-02] 2 Knobs, Mini Waveform, and Vertical LED Ladder - grounded lower."""
        y_center = 104.0
        self._draw_knob(p, 48.0, y_center, radius=22.0, label="AI MODEL", dots=True, angle_deg=-30.0)

        self._draw_led(p, 96.0, y_center - 8.0, "#F59E0B")
        self._draw_led(p, 96.0, y_center + 8.0, "#22C55E")

        self._draw_knob(p, 144.0, y_center, radius=22.0, label="STEM TARGET", dots=True, angle_deg=35.0)

        # Mini Waveform Well (grounded lower)
        wave_rect = QRectF(190.0, 68.0, 74.0, 78.0)
        p.setPen(QPen(QColor("#000000"), 1.0))
        p.setBrush(QColor("#120E0B"))
        p.drawRoundedRect(wave_rect, 4.0, 4.0)

        # Golden Waveform lines
        p.setPen(QPen(QColor("#F59E0B"), 1.2))
        wave_pts = [
            (194.0, 107.0), (200.0, 100.0), (206.0, 114.0), (212.0, 90.0), (218.0, 122.0),
            (224.0, 87.0), (230.0, 124.0), (236.0, 94.0), (242.0, 117.0), (248.0, 102.0),
            (254.0, 107.0)
        ]
        for i in range(len(wave_pts) - 1):
            p.drawLine(QPointF(*wave_pts[i]), QPointF(*wave_pts[i + 1]))

        # Vertical LED Ladder (grounded lower)
        ladder_x = 278.0
        ladder_y = 60.0
        p.setPen(QPen(QColor("#000000"), 1.0))
        p.setBrush(QColor("#100C08"))
        p.drawRoundedRect(QRectF(ladder_x, ladder_y, 14.0, 86.0), 2.0, 2.0)

        # Segments (Red at top, Amber mid, Green bottom)
        colors = ["#EF4444", "#EF4444", "#F59E0B", "#F59E0B", "#F59E0B", "#22C55E", "#22C55E", "#22C55E", "#22C55E", "#22C55E"]
        for idx, col in enumerate(colors):
            seg_y = ladder_y + 4.0 + idx * 7.8
            p.setBrush(QColor(col))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRect(QRectF(ladder_x + 2.5, seg_y, 9.0, 5.0))

    def _paint_combiner(self, p: QPainter, w: float, h: float) -> None:
        """[MOD-03] Amber Square Button + Vertical Fader with 3 Status LEDs - grounded lower."""
        self._draw_button(p, 34.0, 98.0, size=46.0, label="OPEN", is_lit=True)

        # Status LEDs
        self._draw_led(p, 206.0, 76.0, "#F59E0B")
        self._draw_led(p, 206.0, 104.0, "#EAB308")
        self._draw_led(p, 206.0, 132.0, "#22C55E")

        # Fader (Vertical 30x106, grounded to bottom)
        self._draw_fader(p, 234.0, 40.0, width=30.0, height=106.0, is_vertical=True, pos=0.65)

    def _paint_detect(self, p: QPainter, w: float, h: float) -> None:
        """[MOD-04] Dual Circular VU Meters + Stacked BPM & Key Readout Boxes - grounded lower."""
        # Dual VU Meters
        cy = 104.0
        self._draw_vu_meter(p, 58.0, cy, radius=38.0, needle_deg=self._needle_deg_l, title="UA")
        self._draw_led(p, 110.0, cy - 4.0, "#F59E0B")
        self._draw_vu_meter(p, 162.0, cy, radius=38.0, needle_deg=self._needle_deg_r, title="UA")

        # Stacked Readouts
        self._draw_readout_box(p, 226.0, 64.0, 56.0, 24.0, "BPM", caption="BPM")
        self._draw_readout_box(p, 226.0, 102.0, 56.0, 24.0, "Key", caption="")

        # 3 LEDs below Key
        self._draw_led(p, 234.0, 140.0, "#22C55E")
        self._draw_led(p, 248.0, 140.0, "#F59E0B")
        self._draw_led(p, 262.0, 140.0, "#EAB308")

    def _paint_pitch(self, p: QPainter, w: float, h: float) -> None:
        """[MOD-05] Semitone Knob + Square Button + Pitch Shift Bar Display - grounded lower."""
        # Left controls (MUTE button grounded lower, LEDs above, knob to the right)
        self._draw_button(p, 22.0, 108.0, size=36.0, label="MUTE", is_lit=True)
        self._draw_led(p, 34.0, 64.0, "#F59E0B")
        self._draw_led(p, 34.0, 80.0, "#22C55E")
        self._draw_knob(p, 92.0, 72.0, radius=22.0, label="", dots=False, angle_deg=-20.0)

        # Pitch Shift Matrix Bar Display (Recessed Glass Window, grounded lower)
        disp_rect = QRectF(130.0, 48.0, 154.0, 98.0)
        p.setPen(QPen(QColor("#000000"), 1.2))
        p.setBrush(QColor("#120E0B"))
        p.drawRoundedRect(disp_rect, 4.0, 4.0)

        # Inner highlight
        p.setPen(QPen(QColor(255, 255, 255, 12), 1.0))
        p.drawLine(disp_rect.topLeft(), disp_rect.topRight())

        # Pitch grid bars
        p.setPen(QPen(QColor("#261B12"), 1.0))
        for x in range(int(disp_rect.left()) + 18, int(disp_rect.right()), 20):
            p.drawLine(QPointF(x, disp_rect.top() + 4), QPointF(x, disp_rect.bottom() - 4))

        # Golden Pitch Segment Blocks (with rounded edges)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#F59E0B"))
        p.drawRoundedRect(QRectF(145.0, 96.0, 14.0, 5.0), 1.5, 1.5)
        p.drawRoundedRect(QRectF(165.0, 84.0, 14.0, 5.0), 1.5, 1.5)
        p.drawRoundedRect(QRectF(185.0, 72.0, 14.0, 5.0), 1.5, 1.5)
        p.drawRoundedRect(QRectF(205.0, 90.0, 14.0, 5.0), 1.5, 1.5)
        p.drawRoundedRect(QRectF(225.0, 76.0, 14.0, 5.0), 1.5, 1.5)
        p.drawRoundedRect(QRectF(245.0, 102.0, 14.0, 5.0), 1.5, 1.5)

    def _paint_tempo(self, p: QPainter, w: float, h: float) -> None:
        """[MOD-06] Horizontal Fader + Digital Readout + 2 Knobs + Square Button - grounded lower."""
        # Top Horizontal Fader (Standardized 142x26)
        self._draw_fader(p, 18.0, 60.0, width=142.0, height=26.0, is_vertical=False, pos=0.55)

        # Square Button below fader (grounded lower)
        self._draw_button(p, 22.0, 108.0, size=36.0, label="OPEN", is_lit=True)

        # Digital Readout Box
        self._draw_readout_box(p, 170.0, 62.0, 52.0, 22.0, "0.00")

        # 2 Rotary Knobs (Standardized radius=22.0, vertically aligned at x=260)
        self._draw_knob(p, 260.0, 54.0, radius=22.0, label="", dots=False, angle_deg=-30.0)
        self._draw_knob(p, 260.0, 122.0, radius=22.0, label="", dots=False, angle_deg=20.0)

    def _paint_trim(self, p: QPainter, w: float, h: float) -> None:
        """[MOD-07] Waveform Well with Scrub Slider + 3 Knobs + Fade Buttons - grounded lower."""
        # Left 2 Knobs (Standardized radius=22.0, cleanly spaced without label overlap)
        self._draw_knob(p, 36.0, 42.0, radius=22.0, label="TRIM", dots=False)
        self._draw_knob(p, 36.0, 112.0, radius=22.0, label="TRIM", dots=False)

        # Center Waveform Display Well
        wave_rect = QRectF(72.0, 32.0, 142.0, 76.0)
        p.setPen(QPen(QColor("#000000"), 1.0))
        p.setBrush(QColor("#120E0B"))
        p.drawRoundedRect(wave_rect, 4.0, 4.0)

        # Amber Audio Waveform Bars
        p.setPen(QPen(QColor("#E5A93C"), 1.2))
        mid_y = wave_rect.center().y()
        for x_step in range(int(wave_rect.left()) + 6, int(wave_rect.right()) - 6, 4):
            dist = abs(x_step - wave_rect.center().x()) / (wave_rect.width() / 2.0)
            amp = math.sin((x_step * 0.15)) * (1.0 - dist * 0.4) * 26.0
            p.drawLine(QPointF(x_step, mid_y - amp), QPointF(x_step, mid_y + amp))

        # Horizontal Scrub Slider under waveform (Standardized 142x26, grounded)
        self._draw_fader(p, 72.0, 118.0, width=142.0, height=26.0, is_vertical=False, pos=0.45)

        # Right Knob + Fade Buttons (Standardized radius=22.0)
        self._draw_knob(p, 256.0, 42.0, radius=22.0, label="TRIM", dots=False)

        # 2 Small Fade Buttons
        btn_y = 104.0
        p.setPen(QPen(QColor("#000000"), 1.0))
        p.setBrush(QColor("#241A12"))
        p.drawRoundedRect(QRectF(242.0, btn_y, 16.0, 16.0), 3.0, 3.0)
        p.drawRoundedRect(QRectF(264.0, btn_y, 16.0, 16.0), 3.0, 3.0)

        p.setFont(QFont("Helvetica Neue", 7, QFont.Weight.Bold))
        p.setPen(QColor("#9E9182"))
        p.drawText(QRectF(220.0, btn_y + 19.0, 72.0, 14.0), Qt.AlignmentFlag.AlignCenter, "FADE IN/OUT")

    def _paint_normalize(self, p: QPainter, w: float, h: float) -> None:
        """[MOD-08] Square Button + Large Circular VU Meter + LUFS Box + 4 LEDs - grounded lower."""
        # Left Square Button (MUTE)
        self._draw_button(p, 22.0, 108.0, size=36.0, label="MUTE", is_lit=True)

        # Center Large Circular VU Meter (grounded lower)
        self._draw_vu_meter(p, 156.0, 102.0, radius=44.0, needle_deg=self._needle_deg_norm, title="VU")

        # Right LUFS Box
        p.setFont(QFont("Helvetica Neue", 8, QFont.Weight.Bold))
        p.setPen(QColor("#9E9182"))
        p.drawText(QRectF(228.0, 56.0, 54.0, 14.0), Qt.AlignmentFlag.AlignCenter, "LUFS")
        self._draw_readout_box(p, 228.0, 72.0, 54.0, 24.0, "LUFS")

        # 4 LEDs in 2x2 grid
        self._draw_led(p, 242.0, 116.0, "#22C55E")
        self._draw_led(p, 258.0, 116.0, "#F59E0B")
        self._draw_led(p, 242.0, 134.0, "#332418")
        self._draw_led(p, 258.0, 134.0, "#EF4444")

    def _paint_info(self, p: QPainter, w: float, h: float) -> None:
        """[MOD-09] CRT Terminal Screen with Monospace Metadata + 2 Selector Knobs - grounded lower."""
        # Terminal Display Window (grounded lower)
        term_rect = QRectF(16.0, 26.0, 214.0, 122.0)
        p.setPen(QPen(QColor("#000000"), 1.0))
        p.setBrush(QColor("#100C08"))
        p.drawRoundedRect(term_rect, 4.0, 4.0)

        # CRT Scanlines / Inner highlight
        p.setPen(QPen(QColor(255, 255, 255, 12), 1.0))
        p.drawLine(term_rect.topLeft(), term_rect.topRight())

        # Monospace Metadata Lines (cream silkscreen color)
        p.setFont(QFont("Menlo", 7))
        p.setPen(QColor("#EDE6DC"))
        meta_lines = [
            ("Property name", "Audio Information"),
            ("Format", "WAV / 24-bit PCM"),
            ("Sample rate", "48.0 kHz"),
            ("Channels", "Stereo (2ch)"),
            ("Integr. LUFS", "-14.2 LUFS"),
            ("True Peak", "-0.8 dBTP"),
            ("Duration", "03:42.150"),
            ("BPM / Key", "124.0 / A Minor"),
        ]

        ty = term_rect.top() + 14.0
        for key, val in meta_lines:
            p.setPen(QColor("#9E9182"))
            p.drawText(QPointF(term_rect.left() + 8.0, ty), key)
            p.setPen(QColor("#EDE6DC"))
            p.drawText(QPointF(term_rect.left() + 115.0, ty), val)
            ty += 13.0

        # Right 2 Vertically Stacked Knobs + Arrow (Standardized radius=22.0)
        self._draw_knob(p, 262.0, 48.0, radius=22.0, dots=False, angle_deg=-20.0)

        p.setFont(QFont("Arial", 8))
        p.setPen(QColor("#9E9182"))
        p.drawText(QRectF(252.0, 80.0, 20.0, 12.0), Qt.AlignmentFlag.AlignCenter, "▼")

        self._draw_knob(p, 262.0, 124.0, radius=22.0, dots=False, angle_deg=40.0)

    def _paint_default(self, p: QPainter, w: float, h: float) -> None:
        """Fallback for unspecified module rack."""
        self._draw_button(p, (w - 120.0) / 2.0, (h - 36.0) / 2.0, size=36.0, label="OPEN", is_lit=True)

    # Aliases for Option C consolidated 9 modules
    _paint_analyze = _paint_detect
    _paint_pitch_time = _paint_pitch
    _paint_edit = _paint_trim
    _paint_repair = _paint_tempo
    _paint_clean = _paint_normalize
    _paint_voice = _paint_info

    def _paint_drop_overlay(self, p: QPainter, w: float, h: float, state: str) -> None:
        """Render analog studio HUD overlay during active drag over this module."""
        overlay_rect = QRectF(2.0, 2.0, w - 4.0, h - 4.0)
        overlay_path = QPainterPath()
        overlay_path.addRoundedRect(overlay_rect, 6.0, 6.0)

        # 1. Dark smoked translucent glass scrim (hardware still softly visible underneath)
        p.fillPath(overlay_path, QColor(10, 7, 4, 215))

        # Subtle illuminated border
        if state == "valid":
            p.setPen(QPen(QColor(245, 158, 11, 150), 1.2))
        else:
            p.setPen(QPen(QColor(239, 68, 68, 160), 1.2))
        p.drawPath(overlay_path)

        mid_y = h / 2.0
        # 2. Silkscreen Text Content
        if state == "valid":
            # Primary Call to Action
            p.setFont(QFont("Menlo", 10, QFont.Weight.Bold))
            p.setPen(QColor("#FBBF24"))
            p.drawText(
                QRectF(10.0, mid_y - 20.0, w - 20.0, 18.0),
                Qt.AlignmentFlag.AlignCenter,
                "▼ RELEASE TO LOAD",
            )

            # Target Module Name
            parent = self.parent()
            title = getattr(parent, "title_text", "MODULE").upper()
            p.setFont(QFont("Helvetica Neue", 9, QFont.Weight.Bold))
            p.setPen(QColor("#EDE6DC"))
            p.drawText(
                QRectF(10.0, mid_y + 4.0, w - 20.0, 16.0),
                Qt.AlignmentFlag.AlignCenter,
                title,
            )
        else:
            # Unsupported error state
            p.setFont(QFont("Menlo", 10, QFont.Weight.Bold))
            p.setPen(QColor("#EF4444"))
            p.drawText(
                QRectF(10.0, mid_y - 20.0, w - 20.0, 18.0),
                Qt.AlignmentFlag.AlignCenter,
                "✕ UNSUPPORTED FORMAT",
            )

            p.setFont(QFont("Menlo", 8))
            p.setPen(QColor("#B5A899"))
            p.drawText(
                QRectF(10.0, mid_y + 4.0, w - 20.0, 16.0),
                Qt.AlignmentFlag.AlignCenter,
                "WAV · MP3 · FLAC · AIFF · OGG · M4A",
            )
