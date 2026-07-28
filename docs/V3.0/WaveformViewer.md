# Waveform Viewer (V3.0)

## Overview

The `WaveformViewer` component is a dedicated visual inspection tool for the Sound Processor suite. Its primary purpose is to allow users to visually inspect audio data *before* applying AI enhancements or processing for DAW import.

**IMPORTANT NOTE:** This is a **VIEW-ONLY** component. By design, it does not support audio selection, editing, splicing, or manipulation. It is built strictly for high-performance visualization, zooming, scrolling, and playback monitoring.

## Features
- **High-Performance Rendering:** Renders hours of audio instantaneously using downsampled peak data.
- **Zoom & Scroll:** Fluid navigation through audio files using keyboard and mouse controls (Ctrl+Scroll).
- **Playback Cursor:** 30fps smooth animation of the playhead during audio playback.
- **Progressive Loading:** Handles large files (>60 min) gracefully without blocking the UI thread.
- **Catppuccin Mocha Theme:** Integrated color scheme for a modern, sleek appearance.

## Architecture & Data Model

### Peak Data Approach
To maintain 60fps rendering, the viewer never loads the full audio PCM array directly for rendering. Instead, it relies on downsampling audio into N pixels of min/max pairs (peaks). This guarantees that rendering complexity scales with screen width, not audio duration.

```python
from dataclasses import dataclass
import numpy as np

@dataclass
class WaveformPeaks:
    """
    Represents downsampled audio peaks for rendering.
    Stores the minimum and maximum values for each pixel bucket.
    """
    min_peaks: np.ndarray  # 1D array of float32
    max_peaks: np.ndarray  # 1D array of float32
    sample_rate: int
    total_samples: int
    duration_sec: float

    @property
    def num_buckets(self) -> int:
        return len(self.min_peaks)
```

### The QWidget Implementation: `WaveformView`

The main UI component is a custom `QWidget` that handles drawing the peaks.

```python
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor, QPen
from PyQt6.QtCore import Qt, QTimer

class WaveformView(QWidget):
    """
    Custom widget for displaying audio waveforms using pre-calculated peaks.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.peaks: WaveformPeaks | None = None
        self.playhead_sec: float = 0.0
        
        # Zoom model
        self.view_start_sec: float = 0.0
        self.view_end_sec: float = 0.0
        
        # Playhead animation timer
        self._animation_timer = QTimer(self)
        self._animation_timer.timeout.connect(self.update)
        self._animation_timer.setInterval(1000 // 30)  # 30fps
        
    def set_audio(self, peaks: WaveformPeaks) -> None:
        """Loads new peak data and resets the view."""
        self.peaks = peaks
        self.zoom_fit()
        
    def set_playhead(self, time_sec: float) -> None:
        """Updates the playback cursor position."""
        self.playhead_sec = time_sec
        self.update()
        
    def zoom_in(self) -> None:
        """Zooms into the center of the current view."""
        # Implementation...
        
    def zoom_out(self) -> None:
        """Zooms out from the center of the current view."""
        # Implementation...
        
    def zoom_fit(self) -> None:
        """Fits the entire audio file into the widget width."""
        if self.peaks:
            self.view_start_sec = 0.0
            self.view_end_sec = self.peaks.duration_sec
        self.update()
```

## Rendering Pipeline

The rendering occurs within the widget's `paintEvent`. It follows a strict painter sequence to ensure visual hierarchy:

1. **Background:** Fills the widget area with the base color.
2. **Waveform:** Iterates through the visible peak data and draws lines between `min_peak` and `max_peak`.
3. **Center Line:** Draws a horizontal line across the middle representing silence (0.0).
4. **Time Ruler:** Draws tick marks and time labels at the bottom edge.
5. **Playhead:** Draws a vertical line over everything else at `playhead_sec`.

### `paintEvent` Pseudocode

```python
def paintEvent(self, event):
    if not self.peaks:
        return
        
    painter = QPainter(self)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    # 1. Background
    painter.fillRect(self.rect(), Catppuccin.Base)
    
    # 2. Waveform
    painter.setPen(Catppuccin.Blue)
    pixels_per_sec = self.width() / (self.view_end_sec - self.view_start_sec)
    # Vectorized or batched line drawing logic here
    self._draw_waveform_batch(painter, pixels_per_sec)
    
    # 3. Center Line
    painter.setPen(Catppuccin.Surface2)
    mid_y = self.height() // 2
    painter.drawLine(0, mid_y, self.width(), mid_y)
    
    # 4. Time Ruler
    self._draw_time_ruler(painter)
    
    # 5. Playhead
    playhead_x = (self.playhead_sec - self.view_start_sec) * pixels_per_sec
    if 0 <= playhead_x <= self.width():
        painter.setPen(Catppuccin.Red)
        painter.drawLine(int(playhead_x), 0, int(playhead_x), self.height())
```

## Zoom Model

The zoom model is strictly defined by a time window: `view_start_sec` and `view_end_sec`.
When the user uses `Ctrl+Scroll`:
- The delta of the scroll wheel determines the zoom factor.
- The mouse X coordinate maps to a specific time in the audio.
- The `view_start_sec` and `view_end_sec` are expanded or contracted, pivoting around the mouse time.

## Playback Cursor Animation

To prevent the UI from freezing during playback, the `WaveformView` does not rely on the audio engine thread to push position updates synchronously.
Instead:
- The audio engine exposes a thread-safe `get_current_time()` method.
- A `QTimer` running at 30fps queries this method and updates the widget.

## Color Scheme (Catppuccin Mocha)

The visual identity relies on the Catppuccin Mocha palette.

| Element | Color Name | Hex Code | Description |
| :--- | :--- | :--- | :--- |
| **Background** | `Base` | `#1e1e2e` | Deep dark background |
| **Center Line** | `Surface2` | `#585b70` | Subtle contrast for silence line |
| **Waveform** | `Blue` | `#89b4fa` | Primary audio waveform color |
| **Playhead** | `Red` | `#f38ba8` | Standout color for the current time cursor |
| **Time Ruler Text**| `Text` | `#cdd6f4` | High legibility text |

## UI Layout Diagram

```text
+-------------------------------------------------------------+
| [Zoom In] [Zoom Out] [Fit]          playhead: 00:01:23.450  |
+-------------------------------------------------------------+
|                             |                               |
|          _/\_               |             __/\__            |
|         /    \    _/\_      |            /      \           |
|--------/------\--/----\-----|-----------/--------\----------| (Center Line)
|       /        \/      \    |          /          \         |
|      /                  \   |    _/\__/            \        |
|                          \  |   /                   \       |
|                             |                               |
+-------------------------------------------------------------+
| 00:00        00:01          | 00:02         00:03     00:04 | (Time Ruler)
+-------------------------------------------------------------+
                              ^ Playhead
```

## Performance Notes

1. **Peaks Cache:** Calculating min/max peaks for large files takes time. The application calculates this asynchronously using `numpy` and caches the `WaveformPeaks` object in memory.
2. **QPainter Vectorization:** `QPainter.drawLines(QPolygonF)` is used instead of calling `drawLine` in a loop. This batches the draw calls and drastically improves rendering speed.
3. **Progressive Loading:** For files exceeding 60 minutes, the peak calculation worker yields partial results (e.g., every 5 minutes of processed data) via signals so the UI can display the waveform as it loads.
