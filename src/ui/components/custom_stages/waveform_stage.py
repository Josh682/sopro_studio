"""WaveformStage - Custom Visual Deck for Slot 2 (Trimmer, Loudness, Enhancers).

Renders golden skeuomorphic audio waveforms with time markers, stereo channel rails,
interactive range selector handles, real-time 60 FPS playhead sweeping, and dual-buffer
Before / After (A/B) comparison with ghosted waveform overlay.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

import numpy as np

from src.ui.qt import (
    QColor,
    QFont,
    QFrame,
    QHBoxLayout,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPointF,
    QPushButton,
    QRectF,
    QResizeEvent,
    QSizePolicy,
    Qt,
    QWidget,
    Signal,
)
from src.ui.theme.tokens import TOKENS


def _extract_preview_waveform(path: Path, max_points: int = 500) -> tuple[np.ndarray, float]:
    """Helper to extract downsampled mono audio envelope and duration."""
    try:
        import soundfile as sf
        info = sf.info(str(path))
        dur = float(info.duration)
        data, sr = sf.read(str(path), stop=int(min(dur, 300.0) * info.samplerate), dtype="float32")
        if data.ndim > 1:
            data = np.mean(data, axis=1)
        step = max(1, len(data) // max_points)
        return data[::step], dur
    except Exception:
        try:
            from src.core.audio_engine import AudioBuffer
            buf = AudioBuffer.load(path, duration_sec=300.0)
            dur = buf.duration_sec
            raw = buf.samples
            if raw.ndim > 1:
                raw = np.mean(raw, axis=1)
            step = max(1, len(raw) // max_points)
            return raw[::step], dur
        except Exception:
            # Fallback mock sine
            t = np.linspace(0, 10 * np.pi, max_points)
            mock = np.sin(t) * 0.7 + np.sin(3 * t) * 0.2
            return mock, 60.0



class WaveformStage(QWidget):
    """Visual waveform display with draggable time range markers, real-time playhead,
    and Before/After A/B audio comparison.
    """

    rangeChanged = Signal(float, float)     # start_sec, end_sec
    seekRequested = Signal(float)          # target time_sec
    scrubbingActive = Signal(bool)         # True when mouse is dragging playhead
    abToggled = Signal(str)                # "A" or "B"

    def __init__(
        self,
        accent_color: str = "#F59E0B",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._accent_color = accent_color

        # Dual Buffer Storage (A: Raw Original, B: DSP Processed)
        self._samples_a: Optional[np.ndarray] = None
        self._duration_a: float = 0.0
        self._path_a: Optional[Path] = None

        self._samples_b: Optional[np.ndarray] = None
        self._duration_b: float = 0.0
        self._path_b: Optional[Path] = None

        self._active_ab: str = "A"

        # Range Selection Markers
        self._start_sec: float = 0.0
        self._end_sec: float = 0.0

        # Real-time Playhead & Scrubbing State
        self._playhead_sec: float = 0.0
        self._is_scrubbing: bool = False

        self.setFixedHeight(170)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self._setup_ab_ui()

    @property
    def _duration(self) -> float:
        """Effective duration based on active buffer."""
        if self._active_ab == "B" and self._duration_b > 0:
            return self._duration_b
        return self._duration_a if self._duration_a > 0 else 60.0

    @property
    def _samples(self) -> Optional[np.ndarray]:
        """Effective active sample array."""
        if self._active_ab == "B" and self._samples_b is not None:
            return self._samples_b
        return self._samples_a

    @property
    def active_ab(self) -> str:
        return self._active_ab

    # -------------------------------------------------------------------------
    # A/B Compare UI Controls
    # -------------------------------------------------------------------------

    def _setup_ab_ui(self) -> None:
        """Build tactile backlit [A: RAW] and [B: PROCESSED] comparison buttons."""
        self.btn_ab_container = QFrame(self)
        self.btn_ab_container.setStyleSheet("background: transparent; border: none;")
        self.btn_ab_container.setFixedHeight(24)

        ab_layout = QHBoxLayout(self.btn_ab_container)
        ab_layout.setContentsMargins(0, 0, 0, 0)
        ab_layout.setSpacing(2)

        btn_style_base = (
            "QPushButton {"
            "  background-color: #1A1410;"
            "  color: #8C7C6D;"
            "  border: 1px solid #33261C;"
            "  border-radius: 3px;"
            "  font-family: 'Menlo, Courier, monospace';"
            "  font-size: 9px;"
            "  font-weight: bold;"
            "  padding: 2px 7px;"
            "}"
            "QPushButton:hover {"
            "  background-color: #261D17;"
            "  color: #EDE6DC;"
            "}"
        )

        self.btn_a = QPushButton("A : RAW", self.btn_ab_container)
        self.btn_a.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_a.setToolTip("Listen to original raw audio")
        self.btn_a.setStyleSheet(btn_style_base)
        self.btn_a.clicked.connect(lambda: self.set_ab_mode("A"))
        ab_layout.addWidget(self.btn_a)

        self.btn_b = QPushButton("B : PROCESSED", self.btn_ab_container)
        self.btn_b.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_b.setToolTip("Listen to DSP processed audio")
        self.btn_b.setStyleSheet(btn_style_base)
        self.btn_b.clicked.connect(lambda: self.set_ab_mode("B"))
        ab_layout.addWidget(self.btn_b)

        # Initially hidden until Buffer B is loaded
        self.btn_ab_container.hide()
        self._update_ab_buttons_style()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        # Position A/B container in top right corner of visual stage
        w = self.width()
        self.btn_ab_container.move(w - 185, 4)

    def _update_ab_buttons_style(self) -> None:
        """Update illuminated backlights on A/B buttons."""
        if self._active_ab == "A":
            self.btn_a.setStyleSheet(
                "QPushButton {"
                "  background-color: #F59E0B;"
                "  color: #0A0A0A;"
                "  border: 1px solid #FDE68A;"
                "  border-radius: 3px;"
                "  font-family: 'Menlo, Courier, monospace';"
                "  font-size: 9px;"
                "  font-weight: bold;"
                "  padding: 2px 7px;"
                "}"
            )
            self.btn_b.setStyleSheet(
                "QPushButton {"
                "  background-color: #1A1410;"
                "  color: #8C7C6D;"
                "  border: 1px solid #33261C;"
                "  border-radius: 3px;"
                "  font-family: 'Menlo, Courier, monospace';"
                "  font-size: 9px;"
                "  font-weight: bold;"
                "  padding: 2px 7px;"
                "}"
                "QPushButton:hover { background-color: #261D17; color: #EDE6DC; }"
            )
        else:
            self.btn_a.setStyleSheet(
                "QPushButton {"
                "  background-color: #1A1410;"
                "  color: #8C7C6D;"
                "  border: 1px solid #33261C;"
                "  border-radius: 3px;"
                "  font-family: 'Menlo, Courier, monospace';"
                "  font-size: 9px;"
                "  font-weight: bold;"
                "  padding: 2px 7px;"
                "}"
                "QPushButton:hover { background-color: #261D17; color: #EDE6DC; }"
            )
            self.btn_b.setStyleSheet(
                "QPushButton {"
                "  background-color: #06B6D4;"
                "  color: #0A0A0A;"
                "  border: 1px solid #A5F3FC;"
                "  border-radius: 3px;"
                "  font-family: 'Menlo, Courier, monospace';"
                "  font-size: 9px;"
                "  font-weight: bold;"
                "  padding: 2px 7px;"
                "}"
            )

    def set_ab_mode(self, mode: str) -> None:
        """Switch active comparison mode between 'A' and 'B'."""
        mode_upper = mode.upper()
        if mode_upper not in ("A", "B"):
            return
        if self._active_ab != mode_upper:
            self._active_ab = mode_upper
            self._update_ab_buttons_style()
            self.abToggled.emit(self._active_ab)
            self.update()

    # -------------------------------------------------------------------------
    # Audio Buffer Loading
    # -------------------------------------------------------------------------

    def load_audio_preview(self, file_path: str) -> None:
        """Load original raw audio buffer (Buffer A)."""
        p = Path(file_path).resolve()
        if not p.is_file():
            return

        self._path_a = p
        self._samples_a, self._duration_a = _extract_preview_waveform(p)
        self._start_sec = 0.0
        self._end_sec = self._duration_a
        self._playhead_sec = 0.0

        # Reset B buffer
        self._samples_b = None
        self._duration_b = 0.0
        self._path_b = None
        self._active_ab = "A"
        self.btn_ab_container.hide()

        self.rangeChanged.emit(self._start_sec, self._end_sec)
        self.update()

    def load_processed_preview(self, file_path: str) -> None:
        """Load processed DSP result audio buffer (Buffer B) and enable A/B toggle."""
        p = Path(file_path).resolve()
        if not p.is_file():
            return

        self._path_b = p
        self._samples_b, self._duration_b = _extract_preview_waveform(p)

        # Reveal A/B compare switch and switch active preview to B
        self.btn_ab_container.show()
        self.set_ab_mode("B")

    def set_accent_color(self, color: str) -> None:
        self._accent_color = color
        self.update()

    def set_playhead(self, time_sec: float) -> None:
        """Update playhead position for real-time 60 FPS sweep."""
        self._playhead_sec = max(0.0, float(time_sec))
        self.update()

    def set_range(self, start_sec: float, end_sec: float) -> None:
        self._start_sec = max(0.0, start_sec)
        self._end_sec = min(self._duration, end_sec) if self._duration > 0 else end_sec
        self.rangeChanged.emit(self._start_sec, self._end_sec)
        self.update()

    # -------------------------------------------------------------------------
    # Mouse Seeking & Scrubbing
    # -------------------------------------------------------------------------

    def _x_to_time(self, x: float) -> float:
        """Map mouse pixel X coordinate to audio time in seconds."""
        w = float(self.width())
        dur = self._duration if self._duration > 0 else 60.0
        usable_w = max(1.0, w - 32.0)
        rel_x = max(0.0, min(usable_w, x - 16.0))
        return (rel_x / usable_w) * dur

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_scrubbing = True
            self.scrubbingActive.emit(True)
            pos_x = event.position().x() if hasattr(event, "position") else float(event.x())
            t = self._x_to_time(pos_x)
            self.set_playhead(t)
            self.seekRequested.emit(t)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._is_scrubbing:
            pos_x = event.position().x() if hasattr(event, "position") else float(event.x())
            t = self._x_to_time(pos_x)
            self.set_playhead(t)
            self.seekRequested.emit(t)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._is_scrubbing:
            self._is_scrubbing = False
            self.scrubbingActive.emit(False)
            pos_x = event.position().x() if hasattr(event, "position") else float(event.x())
            t = self._x_to_time(pos_x)
            self.set_playhead(t)
            self.seekRequested.emit(t)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    # -------------------------------------------------------------------------
    # Rendering
    # -------------------------------------------------------------------------

    def _draw_waveform_path(
        self,
        p: QPainter,
        samples: np.ndarray,
        color_hex: str,
        wave_top: float,
        wave_h: float,
        mid_y: float,
        w: float,
        is_ghosted: bool = False,
    ) -> None:
        """Draw an upper and lower envelope waveform path."""
        num_pts = len(samples)
        if num_pts == 0:
            return

        step_x = (w - 32.0) / num_pts

        path_upper = QPainterPath()
        path_lower = QPainterPath()
        path_upper.moveTo(16, mid_y)
        path_lower.moveTo(16, mid_y)

        for i, amp in enumerate(samples):
            px = 16 + i * step_x
            clamped_amp = max(-1.0, min(1.0, float(amp)))
            py_up = mid_y - abs(clamped_amp) * (wave_h * 0.45)
            py_dn = mid_y + abs(clamped_amp) * (wave_h * 0.45)
            path_upper.lineTo(px, py_up)
            path_lower.lineTo(px, py_dn)

        if is_ghosted:
            # Thin translucent ghost contour
            ghost_color = QColor(color_hex)
            ghost_color.setAlpha(60)
            p.setPen(QPen(ghost_color, 1.0, Qt.PenStyle.DashLine))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path_upper)
            p.drawPath(path_lower)
        else:
            # Active illuminated solid waveform with gradient
            base_col = QColor(color_hex)
            wave_grad = QLinearGradient(0, wave_top, 0, wave_top + wave_h)
            wave_grad.setColorAt(0.0, QColor(base_col.red(), base_col.green(), base_col.blue(), 200))
            wave_grad.setColorAt(0.5, QColor(base_col.red(), base_col.green(), base_col.blue(), 245))
            wave_grad.setColorAt(1.0, QColor(base_col.red(), base_col.green(), base_col.blue(), 200))

            p.setPen(QPen(base_col, 1.3))
            p.drawPath(path_upper)
            p.drawPath(path_lower)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        w = float(self.width())
        h = float(self.height())

        # 1. Recessed Chassis Background
        bg_rect = QRectF(0, 0, w, h)
        p.setBrush(QColor(14, 10, 6))
        p.setPen(QPen(QColor(255, 255, 255, 15), 1.0))
        p.drawRoundedRect(bg_rect, 6, 6)

        # 2. Time Ruler at Top
        p.setFont(QFont("Menlo, Courier, monospace", 8))
        p.setPen(QPen(QColor(TOKENS.colors.text.muted)))
        dur = self._duration if self._duration > 0 else 60.0
        ruler_divisions = 8
        for i in range(ruler_divisions + 1):
            rx = 16.0 + i * ((w - 32.0) / ruler_divisions)
            p.drawLine(QPointF(rx, 6), QPointF(rx, 12))
            t_sec = i * (dur / ruler_divisions)
            p.drawText(QRectF(rx - 25, 14, 50, 12), Qt.AlignmentFlag.AlignCenter, f"{t_sec:.1f}s")

        # 3. Waveform Display Area
        wave_top = 34.0
        wave_h = h - 46.0
        mid_y = wave_top + wave_h / 2.0

        # Center zero line
        p.setPen(QPen(QColor(255, 255, 255, 20), 1.0, Qt.PenStyle.DashLine))
        p.drawLine(QPointF(16, mid_y), QPointF(w - 16, mid_y))

        has_samples = (self._samples_a is not None) or (self._samples_b is not None)

        if has_samples:
            # Dual Overlay Waveform Rendering
            active_is_b = (self._active_ab == "B" and self._samples_b is not None)

            # Draw Ghosted Inactive Waveform First (if both present)
            if self._samples_a is not None and self._samples_b is not None:
                if active_is_b:
                    # Ghost is A (Amber)
                    self._draw_waveform_path(
                        p, self._samples_a, self._accent_color, wave_top, wave_h, mid_y, w, is_ghosted=True
                    )
                else:
                    # Ghost is B (Cyan)
                    self._draw_waveform_path(
                        p, self._samples_b, "#06B6D4", wave_top, wave_h, mid_y, w, is_ghosted=True
                    )

            # Draw Active Waveform
            if active_is_b:
                self._draw_waveform_path(
                    p, self._samples_b, "#06B6D4", wave_top, wave_h, mid_y, w, is_ghosted=False
                )
            elif self._samples_a is not None:
                self._draw_waveform_path(
                    p, self._samples_a, self._accent_color, wave_top, wave_h, mid_y, w, is_ghosted=False
                )

            # Active Range Selection Overlay
            if self._duration > 0 and self._end_sec > self._start_sec:
                x_start = 16 + (self._start_sec / self._duration) * (w - 32.0)
                x_end = 16 + (self._end_sec / self._duration) * (w - 32.0)
                range_rect = QRectF(x_start, wave_top, x_end - x_start, wave_h)
                p.setBrush(QColor(245, 158, 11, 25))
                p.setPen(QPen(QColor(self._accent_color), 1.5))
                p.drawRect(range_rect)

            # Dynamic Playhead Cursor & Halo (Liquid 60 FPS Animation)
            if self._duration > 0:
                clamped_playhead = max(0.0, min(self._duration, self._playhead_sec))
                px = 16.0 + (clamped_playhead / self._duration) * (w - 32.0)
                active_glow = QColor("#06B6D4") if active_is_b else QColor(245, 158, 11)

                # Translucent Glow (5px width)
                p.setPen(QPen(QColor(active_glow.red(), active_glow.green(), active_glow.blue(), 70), 5.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawLine(QPointF(px, wave_top), QPointF(px, wave_top + wave_h))

                # Core Crisp Ivory Cursor Line (1.5px width)
                p.setPen(QPen(QColor(237, 230, 220), 1.5))
                p.drawLine(QPointF(px, wave_top - 4), QPointF(px, wave_top + wave_h + 4))

                # Top & Bottom Arrow Pointers
                pointer_top = QPainterPath()
                pointer_top.moveTo(px - 4, wave_top - 6)
                pointer_top.lineTo(px + 4, wave_top - 6)
                pointer_top.lineTo(px, wave_top)
                pointer_top.closeSubpath()
                p.setBrush(active_glow)
                p.setPen(Qt.PenStyle.NoPen)
                p.drawPath(pointer_top)

                pointer_bottom = QPainterPath()
                pointer_bottom.moveTo(px - 4, wave_top + wave_h + 6)
                pointer_bottom.lineTo(px + 4, wave_top + wave_h + 6)
                pointer_bottom.lineTo(px, wave_top + wave_h)
                pointer_bottom.closeSubpath()
                p.drawPath(pointer_bottom)

        else:
            # Idle placeholder message
            p.setFont(QFont("Arial", 9))
            p.setPen(QPen(QColor(TOKENS.colors.text.muted)))
            p.drawText(
                QRectF(16, wave_top, w - 32, wave_h),
                Qt.AlignmentFlag.AlignCenter,
                "LOAD AUDIO FILE TO INSPECT WAVEFORM PEAKS AND SELECT TIME RANGE",
            )

        p.end()
