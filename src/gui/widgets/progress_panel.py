"""Premium dynamic progress panel with status, percentage, and ETA metrics."""

from __future__ import annotations

import time

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget


class ProgressPanel(QWidget):
    """Overall and per-file progress tracking widget.

    Features elegant dark-mode progress styling, status descriptions, progress
    percentage text, and moving-average based ETA calculations.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Header: status label on left, ETA label on right
        header_layout = QHBoxLayout()
        self._status_label = QLabel("Idle")
        self._status_label.setStyleSheet("color: #a6adc8; font-weight: 500; font-size: 13px;")
        
        self._eta_label = QLabel("")
        self._eta_label.setStyleSheet("color: #bac2de; font-size: 12px;")
        self._eta_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        header_layout.addWidget(self._status_label)
        header_layout.addStretch()
        header_layout.addWidget(self._eta_label)
        layout.addLayout(header_layout)

        # Progress bar
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(True)
        self._bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._bar.setStyleSheet(
            """
            QProgressBar {
                border: 1px solid #313244;
                border-radius: 6px;
                background-color: #1e1e2e;
                text-align: center;
                color: #cdd6f4;
                font-weight: bold;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                                  stop:0 #cba6f7, stop:1 #89b4fa);
                border-radius: 5px;
            }
            """
        )
        layout.addWidget(self._bar)

        # Performance metric tracking
        self._start_time: float | None = None
        self._last_update_time: float = 0.0

    def start_job(self, message: str = "Processing...") -> None:
        """Initialize timing parameters and status before starting a job."""
        self._start_time = time.time()
        self._last_update_time = self._start_time
        self._status_label.setText(message)
        self._status_label.setStyleSheet("color: #f9e2af; font-weight: 500; font-size: 13px;")  # Yellow status
        self._eta_label.setText("Calculating ETA...")
        self._bar.setValue(0)

    def set_progress(self, fraction: float, message: str = "") -> None:
        """Update the progress bar and dynamically compute remaining ETA.

        Args:
            fraction: Current progress value as a float between 0.0 and 1.0.
            message: Custom description to show in the status label.
        """
        percent = int(fraction * 100)
        self._bar.setValue(percent)

        if message:
            self._status_label.setText(message)

        # Compute ETA if a job is active
        if self._start_time is not None and fraction > 0.01:
            elapsed = time.time() - self._start_time
            total_estimated = elapsed / fraction
            remaining = total_estimated - elapsed

            if remaining <= 0:
                self._eta_label.setText("")
            elif remaining < 60:
                self._eta_label.setText(f"ETA: {int(remaining)}s remaining")
            else:
                mins = int(remaining // 60)
                secs = int(remaining % 60)
                self._eta_label.setText(f"ETA: {mins}m {secs}s remaining")

    def finish_job(self, success: bool = True, message: str = "") -> None:
        """Update layout to show final execution states.

        Args:
            success: Whether the operation completed successfully or failed.
            message: Clean summary description.
        """
        self._start_time = None
        self._eta_label.setText("")
        
        if success:
            self._bar.setValue(100)
            self._status_label.setText(message or "Completed successfully.")
            self._status_label.setStyleSheet("color: #a6e3a1; font-weight: 500; font-size: 13px;")  # Green status
        else:
            self._status_label.setText(message or "Failed.")
            self._status_label.setStyleSheet("color: #f38ba8; font-weight: 500; font-size: 13px;")  # Red status

    def reset_panel(self) -> None:
        """Reset the progress bar back to passive idle state."""
        self._start_time = None
        self._eta_label.setText("")
        self._bar.setValue(0)
        self._status_label.setText("Idle")
        self._status_label.setStyleSheet("color: #a6adc8; font-weight: 500; font-size: 13px;")
