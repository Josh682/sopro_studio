"""Qt abstraction bridge for Audio Quick Toolkit.

Prioritizes PySide6 (official Qt 6 framework per DESIGN.md Non-Negotiables),
with seamless fallback to PyQt6 if executed under Python environments where
PyQt6 is installed (e.g. system Homebrew or legacy virtual environments).
"""

import os
import subprocess
import sys
from pathlib import Path

def _fix_pyside6_hidden_flags() -> None:
    """Fix macOS UF_HIDDEN flag on PySide6 .dylib files.

    pip install PySide6 on macOS marks .dylib plugin files with the hidden
    flag (UF_HIDDEN). Qt's QFactoryLoader uses QDir with default filters
    which skip hidden files, so the cocoa platform plugin is invisible
    despite being physically present. We clear the flag recursively.
    """
    try:
        import PySide6
        pyside_dir = Path(PySide6.__file__).parent
        if pyside_dir.is_dir():
            subprocess.run(
                ["chflags", "-R", "nohidden", str(pyside_dir)],
                capture_output=True, timeout=10,
            )
    except Exception:
        pass

_fix_pyside6_hidden_flags()

try:
    import PySide6
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtCore import (
        QEvent,
        QMimeData,
        QPoint,
        QPointF,
        QRect,
        QRectF,
        QSize,
        Qt,
        QUrl,
        Signal,
    )
    from PySide6.QtGui import (
        QColor,
        QDragEnterEvent,
        QDragLeaveEvent,
        QDragMoveEvent,
        QDropEvent,
        QFont,
        QFontMetrics,
        QIcon,
        QKeyEvent,
        QLinearGradient,
        QMouseEvent,
        QPainter,
        QPainterPath,
        QPalette,
        QPen,
        QPixmap,
    )
    from PySide6.QtWidgets import (
        QApplication,
        QFileDialog,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QMainWindow,
        QPushButton,
        QSizePolicy,
        QSpacerItem,
        QStackedWidget,
        QVBoxLayout,
        QWidget,
    )

    QT_BINDING = "PySide6"
    QT_VERSION = PySide6.__version__

except ImportError:
    try:
        import PyQt6
        from PyQt6 import QtCore, QtGui, QtWidgets
        from PyQt6.QtCore import (
            QEvent,
            QMimeData,
            QPoint,
            QPointF,
            QRect,
            QRectF,
            QSize,
            Qt,
            QUrl,
            pyqtSignal as Signal,
        )
        from PyQt6.QtGui import (
            QColor,
            QDragEnterEvent,
            QDragLeaveEvent,
            QDragMoveEvent,
            QDropEvent,
            QFont,
            QFontMetrics,
            QIcon,
            QKeyEvent,
            QLinearGradient,
            QMouseEvent,
            QPainter,
            QPainterPath,
            QPalette,
            QPen,
            QPixmap,
        )
        from PyQt6.QtWidgets import (
            QApplication,
            QFileDialog,
            QFrame,
            QGridLayout,
            QHBoxLayout,
            QLabel,
            QMainWindow,
            QPushButton,
            QSizePolicy,
            QSpacerItem,
            QStackedWidget,
            QVBoxLayout,
            QWidget,
        )

        QT_BINDING = "PyQt6"
        QT_VERSION = PyQt6.QtCore.PYQT_VERSION_STR

    except ImportError:
        print(
            "\n[FATAL ERROR] Neither PySide6 nor PyQt6 could be found in the current Python environment:\n"
            f"  Python executable: {sys.executable}\n"
            "  Python version:    {sys.version}\n\n"
            "Please run with the virtualenv containing PySide6:\n"
            "  .venv312/bin/python main.py\n"
            "Or install PySide6 into your active environment:\n"
            "  pip install 'PySide6>=6.6.0'\n",
            file=sys.stderr,
        )
        raise ModuleNotFoundError(
            "Neither PySide6 nor PyQt6 is installed. Please run '.venv312/bin/python main.py' "
            "or install PySide6 via 'pip install PySide6>=6.6.0'."
        )


__all__ = [
    "QtCore",
    "QtGui",
    "QtWidgets",
    "Qt",
    "Signal",
    "QPoint",
    "QPointF",
    "QRect",
    "QRectF",
    "QSize",
    "QUrl",
    "QMimeData",
    "QColor",
    "QFont",
    "QFontMetrics",
    "QIcon",
    "QKeyEvent",
    "QMouseEvent",
    "QDragEnterEvent",
    "QDragMoveEvent",
    "QDragLeaveEvent",
    "QDropEvent",
    "QLinearGradient",
    "QPainter",
    "QPainterPath",
    "QPalette",
    "QPen",
    "QPixmap",
    "QApplication",
    "QFileDialog",
    "QWidget",
    "QMainWindow",
    "QStackedWidget",
    "QFrame",
    "QLabel",
    "QPushButton",
    "QVBoxLayout",
    "QHBoxLayout",
    "QGridLayout",
    "QSizePolicy",
    "QSpacerItem",
    "QT_BINDING",
    "QT_VERSION",
]
