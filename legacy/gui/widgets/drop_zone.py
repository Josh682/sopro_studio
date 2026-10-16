"""Drag-and-drop file/folder input widget with premium interactive styles."""

from __future__ import annotations

import logging
from pathlib import Path

from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent, QMouseEvent
from qtpy.QtWidgets import QFileDialog, QLabel

from src.utils.validators import SUPPORTED_AUDIO_EXTENSIONS

log = logging.getLogger("sound_processor.gui.widgets.drop_zone")


class DropZone(QLabel):
    """Interactive drag-and-drop widget for audio files and folders.

    Changes border and background color dynamically during drag-and-drop
    operations, supports clicking to browse files, and emits a signal
    with the selected Path objects.
    """

    #: Emitted when files or folders are dropped or selected.
    filesDropped = Signal(list)  # list[Path]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(80)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setWordWrap(True)
        
        # Initial instruction text
        self.setText(
            "🎵 Drag & Drop audio files or folders here\n"
            "or click anywhere to browse"
        )
        self._reset_style()

    def _reset_style(self) -> None:
        """Reset widget style to standard passive state."""
        self.setStyleSheet(
            """
            QLabel {
                border: 2px dashed #45475a;
                border-radius: 12px;
                color: #a6adc8;
                background-color: #1e1e2e;
                font-size: 14px;
                padding: 12px;
            }
            QLabel:hover {
                border-color: #89b4fa;
                background-color: #252538;
                color: #cdd6f4;
            }
            """
        )

    def _set_active_style(self) -> None:
        """Apply style for active drag hover target state."""
        self.setStyleSheet(
            """
            QLabel {
                border: 2px dashed #a6e3a1;
                border-radius: 12px;
                color: #a6e3a1;
                background-color: #313244;
                font-size: 14px;
                padding: 12px;
            }
            """
        )

    # ------------------------------------------------------------------
    # Drag and Drop Events
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Check if dragged MIME data contains readable paths/URLs."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._set_active_style()
            log.debug("Drag entered drop zone.")
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        """Reset styles when dragging leaves the zone boundary."""
        self._reset_style()
        log.debug("Drag left drop zone.")

    def dropEvent(self, event: QDropEvent) -> None:
        """Process dropped paths and filter/emit valid files or directories."""
        self._reset_style()
        urls = event.mimeData().urls()
        
        paths: list[Path] = []
        for url in urls:
            local_path = url.toLocalFile()
            if local_path:
                paths.append(Path(local_path))

        if paths:
            event.acceptProposedAction()
            log.info("Dropped paths: %s", [str(p) for p in paths])
            self.filesDropped.emit(paths)
        else:
            event.ignore()

    # ------------------------------------------------------------------
    # Mouse Click Selection Event
    # ------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Trigger file selection dialog on left mouse button click."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Build filters dynamically based on supported extensions
            ext_list = [f"*{ext}" for ext in sorted(SUPPORTED_AUDIO_EXTENSIONS)]
            filter_str = f"Audio Files ({' '.join(ext_list)});;All Files (*)"

            files, _ = QFileDialog.getOpenFileNames(
                self,
                "Select Audio Files",
                "",
                filter_str
            )
            
            if files:
                paths = [Path(f) for f in files]
                log.info("Selected files via dialog: %s", [str(p) for p in paths])
                self.filesDropped.emit(paths)
        else:
            super().mousePressEvent(event)
