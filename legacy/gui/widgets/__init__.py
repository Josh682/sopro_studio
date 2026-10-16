"""Reusable GUI widgets.

Re-exports custom components for clean layout import:

    from src.gui.widgets import DropZone, LogPanel, ProgressPanel, StemPreviewWidget
"""

from src.gui.widgets.drop_zone import DropZone
from src.gui.widgets.log_panel import LogPanel
from src.gui.widgets.progress_panel import ProgressPanel
from src.gui.widgets.stem_preview import StemPreviewWidget
from src.gui.widgets.waveform_view import WaveformView
from src.gui.widgets.trim_overlay import TrimOverlay, TrimmerWaveformContainer

__all__ = [
    "DropZone",
    "LogPanel",
    "ProgressPanel",
    "StemPreviewWidget",
    "WaveformView",
    "TrimOverlay",
    "TrimmerWaveformContainer",
]
