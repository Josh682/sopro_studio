"""Audio Quick Toolkit v2.0 — Application Entry Point.

Architected according to DESIGN.md Non-Negotiables:
- Single Source of Truth: tokens.json
- PySide6 desktop framework
- Dark modern Bento Grid launcher with 4-slot tactile workspace
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# Load Qt bridge (prioritizes PySide6 per DESIGN.md, fallbacks to PyQt6 if under alternate venv)
try:
    from src.ui.qt import (
        QApplication,
        QColor,
        QFont,
        QPalette,
        Qt,
        QT_BINDING,
        QT_VERSION,
    )
except ModuleNotFoundError:
    # If neither PySide6 nor PyQt6 is in current interpreter, auto-switch to .venv312
    project_root = Path(__file__).parent.absolute()
    candidate_venvs = [
        project_root / ".venv312" / "bin" / "python",
        project_root / ".venv" / "bin" / "python",
    ]
    for venv_py in candidate_venvs:
        if venv_py.is_file() and sys.executable != str(venv_py):
            res = os.system(f'"{venv_py}" -c "import PySide6" >/dev/null 2>&1')
            if res == 0:
                args = [str(venv_py), str(Path(__file__).resolve())] + sys.argv[1:]
                os.execv(str(venv_py), args)

    print(
        "\n[FATAL ERROR] PySide6 is required but could not be found.\n"
        f"Current Python: {sys.executable}\n"
        "Please ensure PySide6 is installed:\n"
        "  pip install 'PySide6>=6.6.0'\n"
        "Or execute using the designated virtualenv:\n"
        "  .venv312/bin/python main.py\n",
        file=sys.stderr,
    )
    raise

from src.ui.main_window import MainWindow
from src.ui.theme.tokens import TOKENS
from src.utils.logger import setup_logger

log = logging.getLogger("sound_processor.main")


def configure_application_palette(app: QApplication) -> None:
    """Apply global dark theme palette from design tokens."""
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, TOKENS.colors.background.app_qcolor)
    palette.setColor(QPalette.ColorRole.WindowText, TOKENS.colors.text.primary_qcolor)
    palette.setColor(QPalette.ColorRole.Base, TOKENS.colors.background.surface_well_qcolor)
    palette.setColor(QPalette.ColorRole.AlternateBase, TOKENS.colors.background.surface_card_qcolor)
    palette.setColor(QPalette.ColorRole.ToolTipBase, TOKENS.colors.background.surface_card_qcolor)
    palette.setColor(QPalette.ColorRole.ToolTipText, TOKENS.colors.text.primary_qcolor)
    palette.setColor(QPalette.ColorRole.Text, TOKENS.colors.text.primary_qcolor)
    palette.setColor(QPalette.ColorRole.Button, TOKENS.colors.background.surface_card_qcolor)
    palette.setColor(QPalette.ColorRole.ButtonText, TOKENS.colors.text.primary_qcolor)
    palette.setColor(QPalette.ColorRole.BrightText, TOKENS.colors.semantic.warning_qcolor)
    palette.setColor(QPalette.ColorRole.Link, TOKENS.colors.accents["converter"].base_qcolor)
    palette.setColor(QPalette.ColorRole.Highlight, TOKENS.colors.border.focus_qcolor)
    palette.setColor(QPalette.ColorRole.HighlightedText, TOKENS.colors.text.button_dark_qcolor)
    app.setPalette(palette)

    # Set default UI typography font
    font = QFont(TOKENS.typography.font_family_ui, 13)
    app.setFont(font)


def main() -> int:
    """Initialize and run the Audio Quick Toolkit desktop application."""
    # Ensure High DPI scaling is handled smoothly
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    app.setApplicationName("Audio Quick Toolkit")
    app.setApplicationVersion("2.0.0")
    app.setOrganizationName("Sopro Studio")

    # Configure global dark palette from design tokens
    configure_application_palette(app)

    # Setup centralized logger
    project_root = Path(__file__).resolve().parent
    log_dir = project_root / "logs"
    setup_logger(name="sound_processor", log_dir=log_dir, level=logging.DEBUG)
    log.info("Application starting (Audio Quick Toolkit v2.0)...")

    # Launch Primary Shell Window (Default 1152 x 768 px)
    window = MainWindow()
    window.show()

    exit_code = app.exec()
    log.info("Application exited with code: %d", exit_code)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
