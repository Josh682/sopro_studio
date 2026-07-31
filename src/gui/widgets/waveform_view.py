"""Reusable Waveform Visualization Component."""

import logging
import numpy as np
from qtpy.QtWidgets import QWidget
from qtpy.QtGui import QPainter, QColor, QPen
from qtpy.QtCore import Qt, Signal, QPointF

from src.workers.waveform_worker import WaveformPeaks

log = logging.getLogger("sound_processor.gui.widgets.waveform_view")

class WaveformView(QWidget):
    """
    High-performance audio waveform visualization widget.
    Strictly view-only. Parent widgets can draw overlays on top.
    """
    
    view_changed = Signal(float, float) # start_sec, end_sec
    clicked_time = Signal(float) # time_sec
    
    # Seeking signals
    seek_started = Signal()
    seek_moved = Signal(float)
    seek_ended = Signal(float)
    
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.peaks: WaveformPeaks | None = None
        
        self.view_start_sec: float = 0.0
        self.view_end_sec: float = 1.0 # arbitrary default
        
        # Colors (Catppuccin Mocha)
        self.color_bg = QColor("#1e1e2e")
        self.color_center = QColor("#585b70")
        self.color_wave = QColor("#89b4fa")
        
        # Interaction state
        self._is_panning = False
        self._is_scrubbing = False
        self._last_mouse_x = 0
        
        self.setMouseTracking(True)
        # Prevent default background drawing for performance
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        
    def set_peaks(self, peaks: WaveformPeaks | None) -> None:
        """Loads new peak data and resets the view."""
        self.peaks = peaks
        if self.peaks:
            self.view_start_sec = 0.0
            self.view_end_sec = self.peaks.duration_sec
            self.view_changed.emit(self.view_start_sec, self.view_end_sec)
        self.update()
        
    def time_to_x(self, time_sec: float) -> float:
        """Convert a time in seconds to an x-coordinate in the widget."""
        if self.view_end_sec <= self.view_start_sec or self.width() == 0:
            return 0.0
        return (time_sec - self.view_start_sec) / (self.view_end_sec - self.view_start_sec) * self.width()
        
    def x_to_time(self, x: float) -> float:
        """Convert an x-coordinate in the widget to a time in seconds."""
        if self.width() == 0:
            return 0.0
        return self.view_start_sec + (x / self.width()) * (self.view_end_sec - self.view_start_sec)
        
    def zoom(self, factor: float, anchor_x: float) -> None:
        """Zooms the view by factor, keeping anchor_x stationary."""
        if not self.peaks:
            return
            
        anchor_time = self.x_to_time(anchor_x)
        current_duration = self.view_end_sec - self.view_start_sec
        new_duration = current_duration * factor
        
        # Clamp zoom level (e.g., max zoom = 0.1s, min zoom = full file)
        min_dur = 0.1
        max_dur = self.peaks.duration_sec
        if new_duration < min_dur:
            new_duration = min_dur
        if new_duration > max_dur:
            new_duration = max_dur
            
        ratio = anchor_x / self.width() if self.width() > 0 else 0.5
        new_start = anchor_time - new_duration * ratio
        new_end = new_start + new_duration
        
        # Clamp to bounds
        if new_start < 0:
            new_end -= new_start
            new_start = 0.0
        if new_end > self.peaks.duration_sec:
            new_start -= (new_end - self.peaks.duration_sec)
            new_end = self.peaks.duration_sec
            if new_start < 0:
                new_start = 0.0
                
        self.view_start_sec = new_start
        self.view_end_sec = new_end
        self.view_changed.emit(self.view_start_sec, self.view_end_sec)
        self.update()
        
    def zoom_in(self) -> None:
        self.zoom(0.8, self.width() / 2)
        
    def zoom_out(self) -> None:
        self.zoom(1.25, self.width() / 2)
        
    def zoom_fit(self) -> None:
        if self.peaks:
            self.view_start_sec = 0.0
            self.view_end_sec = self.peaks.duration_sec
            self.view_changed.emit(self.view_start_sec, self.view_end_sec)
            self.update()

    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Zoom
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom(0.8, event.position().x())
            elif delta < 0:
                self.zoom(1.25, event.position().x())
            event.accept()
        else:
            super().wheelEvent(event)
            
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self._is_panning = True
            self._last_mouse_x = event.position().x()
            self._drag_started_x = self._last_mouse_x
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        elif event.button() == Qt.MouseButton.LeftButton:
            self._is_scrubbing = True
            self.seek_started.emit()
            time_sec = self.x_to_time(event.position().x())
            if self.peaks:
                time_sec = max(0.0, min(self.peaks.duration_sec, time_sec))
            self.seek_moved.emit(time_sec)
            event.accept()
            
    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self._is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
        elif event.button() == Qt.MouseButton.LeftButton:
            self._is_scrubbing = False
            time_sec = self.x_to_time(event.position().x())
            if self.peaks:
                time_sec = max(0.0, min(self.peaks.duration_sec, time_sec))
            self.seek_ended.emit(time_sec)
            event.accept()
            
    def mouseMoveEvent(self, event) -> None:
        if self._is_panning and self.peaks:
            dx = event.position().x() - self._last_mouse_x
            
            # Convert dx to time delta
            dt = -(dx / self.width()) * (self.view_end_sec - self.view_start_sec)
            
            new_start = self.view_start_sec + dt
            new_end = self.view_end_sec + dt
            
            # Clamp
            if new_start < 0:
                new_end -= new_start
                new_start = 0.0
            elif new_end > self.peaks.duration_sec:
                new_start -= (new_end - self.peaks.duration_sec)
                new_end = self.peaks.duration_sec
                
            self.view_start_sec = new_start
            self.view_end_sec = new_end
            self._last_mouse_x = event.position().x()
            
            self.view_changed.emit(self.view_start_sec, self.view_end_sec)
            self.update()
        elif self._is_scrubbing and self.peaks:
            time_sec = self.x_to_time(event.position().x())
            time_sec = max(0.0, min(self.peaks.duration_sec, time_sec))
            self.seek_moved.emit(time_sec)
            
        event.accept()
        
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        
        # 1. Background
        painter.fillRect(self.rect(), self.color_bg)
        
        if not self.peaks or self.width() == 0 or self.height() == 0:
            return
            
        # 2. Center Line
        mid_y = self.height() / 2.0
        painter.setPen(self.color_center)
        painter.drawLine(0, int(mid_y), self.width(), int(mid_y))
        
        # 3. Waveform
        # Determine which buckets are visible
        duration = self.peaks.duration_sec
        if duration <= 0:
            return
            
        start_ratio = self.view_start_sec / duration
        end_ratio = self.view_end_sec / duration
        
        total_buckets = self.peaks.num_buckets
        start_idx = int(start_ratio * total_buckets)
        end_idx = int(end_ratio * total_buckets) + 1
        
        start_idx = max(0, min(start_idx, total_buckets - 1))
        end_idx = max(0, min(end_idx, total_buckets))
        
        if end_idx <= start_idx:
            return
            
        # Extract visible peaks
        vis_min = self.peaks.min_peaks[start_idx:end_idx]
        vis_max = self.peaks.max_peaks[start_idx:end_idx]
        num_vis = len(vis_min)
        
        if num_vis == 0:
            return

        # Map to screen coordinates
        x_coords = np.linspace(
            self.time_to_x(start_idx / total_buckets * duration),
            self.time_to_x((end_idx - 1) / total_buckets * duration),
            num_vis
        )
        
        y_min = mid_y - vis_min * (self.height() / 2.0)
        y_max = mid_y - vis_max * (self.height() / 2.0)
        
        line_coords = []
        for i in range(num_vis):
            line_coords.append(QPointF(float(x_coords[i]), float(y_min[i])))
            line_coords.append(QPointF(float(x_coords[i]), float(y_max[i])))
            
        painter.setPen(self.color_wave)
        painter.drawLines(line_coords)
