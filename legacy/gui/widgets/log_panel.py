"""Premium scrollable terminal-style log output widget."""

from __future__ import annotations

from datetime import datetime

from qtpy.QtGui import QFont
from qtpy.QtWidgets import QPlainTextEdit


class LogPanel(QPlainTextEdit):
    """Read-only terminal console displaying colored log and execution details.

    Implements automatic scrolling, maximum scrollback buffer limit, custom
    styling, and timestamped lines.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        
        # Max lines kept in memory to prevent slow-downs or leaks
        self.setMaximumBlockCount(1000)

        # Style sheet matching dark theme (slate background, monospace font)
        self.setStyleSheet(
            """
            QPlainTextEdit {
                background-color: #11111b;
                border: 1px solid #313244;
                border-radius: 8px;
                color: #cdd6f4;
                font-family: "Fira Code", "Courier New", monospace;
                font-size: 12px;
                padding: 12px;
            }
            """
        )

    def append_log(self, message: str) -> None:
        """Append a message prefixed with a local timestamp and auto-scroll.

        Args:
            message: Raw log entry text to display.
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {message}"
        self.appendPlainText(formatted)

        # Auto-scroll to the bottom of the console log
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def append_error(self, message: str) -> None:
        """Append an error entry with clear alert flags.

        Args:
            message: Error text to display.
        """
        self.append_log(f"❌ ERROR: {message}")

    def append_success(self, message: str) -> None:
        """Append a success entry with checkmark flags.

        Args:
            message: Success text to display.
        """
        self.append_log(f"✅ SUCCESS: {message}")

    def clear_logs(self) -> None:
        """Clear all messages from the console panel."""
        self.clear()
