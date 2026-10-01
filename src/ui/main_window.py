"""MainWindow - Main Application Shell & Navigation Controller.

Features:
- Fixed 44px titlebar with branding, audio engine status indicator.
- QStackedWidget hosting:
  - Index 0: LauncherGridPage (3x3 Bento Grid)
  - Index 1: WorkspacePage (4-Slot Tactical Workspace Template)
- Global Esc shortcut returning to Launcher from any workspace.
- Window bounds: default 1152x768, minimum 960x640 (strict standard resolution budget).
- Dark chassis theme matching DESIGN.md.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from src.ui.qt import (
    QColor,
    QFont,
    QFrame,
    QHBoxLayout,
    QIcon,
    QKeyEvent,
    QLabel,
    QMainWindow,
    QSize,
    QStackedWidget,
    Qt,
    QVBoxLayout,
    QWidget,
)

from src.ui.theme.tokens import TOKENS
from src.ui.views.launcher_grid import MODULE_DEFINITIONS, LauncherGridPage
from src.ui.views.workspace_template import WorkspacePage

log = logging.getLogger("sound_processor.main_window")


class MainWindow(QMainWindow):
    """Primary Shell Window for Audio Quick Toolkit."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("Audio Quick Toolkit")
        self.resize(
            TOKENS.dimensions.window.default_width,  # 1152px
            TOKENS.dimensions.window.default_height,  # 768px
        )
        # Support minimum size down to 960x640
        self.setMinimumSize(960, 640)

        # Global dark chassis background
        self.setStyleSheet(f"background-color: {TOKENS.colors.background.app}; color: {TOKENS.colors.text.primary};")

        self._module_map: Dict[str, Dict[str, str]] = {m["id"]: m for m in MODULE_DEFINITIONS}

        self._setup_shell_ui()

    def _setup_shell_ui(self) -> None:
        """Construct the titlebar, stacked widget, and page views."""
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Shell Titlebar (Height: 44px)
        self.titlebar = self._create_titlebar()
        root_layout.addWidget(self.titlebar)

        # 2. Main Stacked Navigation Controller
        self.stack = QStackedWidget(central_widget)

        # Index 0: Bento Grid Launcher
        self.page_launcher = LauncherGridPage(self.stack)
        self.page_launcher.module_requested.connect(self.navigate_to_module)
        self.page_launcher.file_dropped_on_module.connect(self.navigate_to_module_with_file)
        self.stack.addWidget(self.page_launcher)

        # Index 1: 4-Slot Workspace Template
        self.page_workspace = WorkspacePage(self.stack)
        self.page_workspace.back_requested.connect(self.navigate_to_launcher)
        self.stack.addWidget(self.page_workspace)

        root_layout.addWidget(self.stack)

    def _create_titlebar(self) -> QFrame:
        """Create the 44px top Titlebar according to DESIGN.md Section 5.1."""
        titlebar = QFrame(self)
        titlebar.setFixedHeight(TOKENS.dimensions.shell.titlebar_height)  # 44px
        titlebar.setStyleSheet(
            f"QFrame {{"
            f"  background-color: {TOKENS.colors.background.app};"
            f"  border-bottom: 1px solid {TOKENS.colors.border.subtle};"
            f"}}"
        )

        tb_layout = QHBoxLayout(titlebar)
        tb_layout.setContentsMargins(TOKENS.dimensions.shell.margin_x, 0, TOKENS.dimensions.shell.margin_x, 0)
        tb_layout.setSpacing(12)

        # Left branding: Iconmark + Wordmark
        self.lbl_logo = QLabel("◈", titlebar)
        self.lbl_logo.setFont(QFont("Arial", 16))
        self.lbl_logo.setStyleSheet(f"color: {TOKENS.colors.accents['converter'].base}; background: transparent;")
        tb_layout.addWidget(self.lbl_logo)

        self.lbl_brand = QLabel("Audio Quick Toolkit", titlebar)
        self.lbl_brand.setFont(TOKENS.typography.create_font("title_h1"))
        self.lbl_brand.setStyleSheet(
            f"color: {TOKENS.colors.text.primary}; font-weight: 700; letter-spacing: -0.2px; background: transparent;"
        )
        tb_layout.addWidget(self.lbl_brand)

        # Subtitle / Version tag
        self.lbl_version = QLabel("v2.0 · Pro Suite", titlebar)
        self.lbl_version.setFont(TOKENS.typography.create_font("data_mono_sm"))
        self.lbl_version.setStyleSheet(f"color: {TOKENS.colors.text.muted}; background: transparent;")
        tb_layout.addWidget(self.lbl_version)

        tb_layout.addStretch()

        # Right: Audio Engine Status Dot
        self.lbl_engine_dot = QLabel("●", titlebar)
        self.lbl_engine_dot.setFont(QFont("Arial", 9))
        self.lbl_engine_dot.setStyleSheet(f"color: {TOKENS.colors.semantic.success}; background: transparent;")
        tb_layout.addWidget(self.lbl_engine_dot)

        self.lbl_engine_text = QLabel("CoreAudio · 48 kHz", titlebar)
        self.lbl_engine_text.setFont(TOKENS.typography.create_font("data_mono_sm"))
        self.lbl_engine_text.setStyleSheet(f"color: {TOKENS.colors.text.secondary}; background: transparent;")
        tb_layout.addWidget(self.lbl_engine_text)

        return titlebar

    # --- Navigation Methods ---

    def navigate_to_module(self, module_id: str) -> None:
        """Switch to WorkspacePage (Index 1) for the given module."""
        module_info = self._module_map.get(module_id)
        if not module_info:
            log.warning("Unknown module id: %s", module_id)
            return

        log.info("Navigating to module: %s", module_id)
        self.page_workspace.configure_module(module_info)
        self.stack.setCurrentIndex(1)

    def navigate_to_module_with_file(self, module_id: str, file_path: str) -> None:
        """Switch to WorkspacePage (Index 1) with pre-loaded audio file."""
        module_info = self._module_map.get(module_id)
        if not module_info:
            return

        log.info("Navigating to module: %s with file: %s", module_id, file_path)
        self.page_workspace.configure_module(module_info, file_path=file_path)
        self.stack.setCurrentIndex(1)

    def navigate_to_launcher(self) -> None:
        """Return to Bento Grid Launcher (Index 0)."""
        log.info("Returning to Launcher grid.")
        self.stack.setCurrentIndex(0)

    # --- Global Keyboard Shortcuts ---

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle global keyboard shortcuts (Esc returns to Launcher)."""
        if event.key() == Qt.Key.Key_Escape:
            if self.stack.currentIndex() != 0:
                self.navigate_to_launcher()
                event.accept()
                return

        super().keyPressEvent(event)
