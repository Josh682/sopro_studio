from __future__ import annotations

from pathlib import Path
from qtpy.QtCore import Qt
from qtpy.QtGui import QPainter, QPixmap
from qtpy.QtWidgets import QWidget

class WatermarkedPage(QWidget):
    """Base class for pages that display a subtle background logo watermark."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        
        self._bg_pixmap = None
        logo_path = Path(__file__).resolve().parent.parent.parent / "assets" / "sopro_studio_logo.png"
        if logo_path.exists():
            original_pixmap = QPixmap(str(logo_path))
            self._bg_pixmap = original_pixmap.scaled(
                600, 600, 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._bg_pixmap is not None and not self._bg_pixmap.isNull():
            painter = QPainter(self)
            painter.setOpacity(0.10)
            
            x = int((self.width() - self._bg_pixmap.width()) / 2)
            y = int((self.height() - self._bg_pixmap.height()) / 2)
            
            painter.drawPixmap(x, y, self._bg_pixmap)
            painter.end()
