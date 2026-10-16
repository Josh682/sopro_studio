"""Overlay widget for the waveform viewer to display trim markers and playhead."""

import logging
from qtpy.QtWidgets import QWidget
from qtpy.QtGui import QPainter, QColor, QPen
from qtpy.QtCore import Qt

from src.gui.widgets.waveform_view import WaveformView

log = logging.getLogger("sound_processor.gui.widgets.trim_overlay")

class TrimOverlay(QWidget):
    """
    Transparent overlay widget that draws trim markers and a playhead
    over a WaveformView.
    """
    
    def __init__(self, waveform_view: WaveformView, parent: QWidget | None = None):
        super().__init__(parent)
        self.waveform_view = waveform_view
        
        # Overlay settings
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        
        # State
        self.playhead_sec = -1.0
        self.trim_start_sec = -1.0
        self.trim_end_sec = -1.0
        
        # Colors (Catppuccin Mocha)
        self.color_playhead = QColor("#f38ba8") # Red
        self.color_start = QColor("#a6e3a1") # Green
        self.color_end = QColor("#f9e2af") # Yellow
        self.color_dim = QColor(30, 30, 46, 128) # Semi-transparent base
        
        # Connect to waveform view changes
        self.waveform_view.view_changed.connect(self._on_view_changed)
        
    def set_playhead(self, time_sec: float) -> None:
        self.playhead_sec = time_sec
        self.update()
        
    def set_trim_markers(self, start_sec: float, end_sec: float) -> None:
        self.trim_start_sec = start_sec
        self.trim_end_sec = end_sec
        self.update()
        
    def _on_view_changed(self, start_sec: float, end_sec: float) -> None:
        self.update()
        
    def paintEvent(self, event) -> None:
        if not self.waveform_view.peaks:
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        
        # Dim areas outside the trim region
        if self.trim_start_sec >= 0 or self.trim_end_sec >= 0:
            start_x = 0
            if self.trim_start_sec >= 0:
                start_x = int(self.waveform_view.time_to_x(self.trim_start_sec))
                
            end_x = self.width()
            if self.trim_end_sec >= 0:
                end_x = int(self.waveform_view.time_to_x(self.trim_end_sec))
                
            # Draw dim rects
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self.color_dim)
            if start_x > 0:
                painter.drawRect(0, 0, start_x, self.height())
            if end_x < self.width():
                painter.drawRect(end_x, 0, self.width() - end_x, self.height())
        
        # Draw Trim Start Marker
        if self.trim_start_sec >= 0:
            x = int(self.waveform_view.time_to_x(self.trim_start_sec))
            if 0 <= x <= self.width():
                painter.setPen(QPen(self.color_start, 2))
                painter.drawLine(x, 0, x, self.height())
                
        # Draw Trim End Marker
        if self.trim_end_sec >= 0:
            x = int(self.waveform_view.time_to_x(self.trim_end_sec))
            if 0 <= x <= self.width():
                painter.setPen(QPen(self.color_end, 2))
                painter.drawLine(x, 0, x, self.height())
                
        # Draw Playhead
        if self.playhead_sec >= 0:
            x = int(self.waveform_view.time_to_x(self.playhead_sec))
            if 0 <= x <= self.width():
                painter.setPen(QPen(self.color_playhead, 2))
                painter.drawLine(x, 0, x, self.height())

class TrimmerWaveformContainer(QWidget):
    """
    Container that holds a WaveformView and a TrimOverlay,
    keeping their geometry synchronized.
    """
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.waveform_view = WaveformView(self)
        self.overlay = TrimOverlay(self.waveform_view, self)
        
        # Give it a minimum height
        self.setMinimumHeight(150)
        
    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.waveform_view.setGeometry(self.rect())
        self.overlay.setGeometry(self.rect())
