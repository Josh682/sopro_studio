"""Sopro Studio v1.0 — application entry point."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_API", "pyqt6")

from qtpy.QtWidgets import QApplication  # noqa: E402
from src.gui.main_window import MainWindow  # noqa: E402
from src.utils.logger import setup_logger  # noqa: E402


log = logging.getLogger("sound_processor.main")


def main() -> int:
    # Initialize QApplication
    app = QApplication(sys.argv)
    app.setApplicationName("Sopro Studio")
    app.setApplicationVersion("1.0")

    # Resolve logs directory relative to project root
    project_root = Path(__file__).resolve().parent
    log_dir = project_root / "logs"

    # Setup centralized rotating logging
    setup_logger(name="sound_processor", log_dir=log_dir, level=logging.DEBUG)
    log.info("Application starting (Sopro Studio v1.0)...")

    # Launch GUI main window shell
    window = MainWindow()
    window.showMaximized()

    exit_code = app.exec()
    log.info("Application exiting with code: %d", exit_code)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
