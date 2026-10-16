"""MainWindow - Main Application Shell & Navigation Controller.

Features:
- Fixed 44px Hardware Brand Strip with diamond mark and CoreAudio status.
- Left and Right 16px Walnut Wood End-Cheeks per DESIGN.md Section 5.1.
- macOS native title bar manages window title and traffic lights.
- QStackedWidget hosting:
  - Index 0: LauncherGridPage (3x3 Modular Console Grid)
  - Index 1: WorkspacePage (4-Slot Tactical Workspace Template)
- Global Esc shortcut returning to Launcher from any workspace.
- Window bounds: default 1152x768, minimum 960x640 (strict standard resolution budget).
- Bronze chassis theme (#3B2C1E) matching DESIGN.md.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from src.ui.qt import (
    QColor,
    QFont,
    QFrame,
    QHBoxLayout,
    QKeyEvent,
    QLabel,
    QMainWindow,
    QPainter,
    QPen,
    QPointF,
    QPushButton,
    QRectF,
    QSize,
    QSizePolicy,
    QStackedWidget,
    Qt,
    QVBoxLayout,
    QWidget,
)

from src.ui.theme.tokens import TOKENS
from src.ui.views.launcher_grid import MODULE_DEFINITIONS, LauncherGridPage
from src.ui.views.settings_view import SettingsView
from src.ui.views.workspace_template import WorkspacePage

log = logging.getLogger("sound_processor.main_window")


class WoodCheek(QFrame):
    """16px Solid Walnut Wood End-Cheek with subtle grain texture."""

    def __init__(self, is_right: bool = False, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._is_right = is_right
        self.setFixedWidth(TOKENS.dimensions.hardware.wood_cheeks_width)  # 16px
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        w = float(self.width())
        h = float(self.height())

        # Base walnut fill
        base_color = QColor(TOKENS.colors.background.wood_walnut_base)
        painter.fillRect(QRectF(0, 0, w, h), base_color)

        # Subtle vertical grain highlights
        grain_pen = QPen(QColor(TOKENS.colors.background.wood_walnut_grain), 1.0)
        painter.setPen(grain_pen)
        painter.drawLine(QPointF(4.0, 0), QPointF(4.0, h))
        painter.drawLine(QPointF(11.0, 0), QPointF(11.0, h))

        # Inner shadow border meeting the chassis
        shadow_pen = QPen(QColor(TOKENS.colors.background.wood_walnut_shadow), 1.0)
        painter.setPen(shadow_pen)
        if self._is_right:
            painter.drawLine(QPointF(0, 0), QPointF(0, h))
        else:
            painter.drawLine(QPointF(w - 1.0, 0), QPointF(w - 1.0, h))

        painter.end()


class MainWindow(QMainWindow):
    """Primary Shell Window for Umbra."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("Umbra")
        self.resize(
            TOKENS.dimensions.window.default_width,  # 1152px
            TOKENS.dimensions.window.default_height,  # 768px
        )
        self.setMinimumSize(960, 640)

        # Global chassis bronze background
        self.setStyleSheet(f"background-color: {TOKENS.colors.background.app}; color: {TOKENS.colors.text.primary};")

        self._module_map: Dict[str, Dict[str, str]] = {m["id"]: m for m in MODULE_DEFINITIONS}
        # Backward-compatible legacy aliases for navigation
        legacy_aliases = {
            "detect": "analyze",
            "pitch": "pitch_time",
            "tempo": "pitch_time",
            "trim": "edit",
            "normalize": "clean",
            "info": "voice",
        }
        for old_id, new_id in legacy_aliases.items():
            if new_id in self._module_map and old_id not in self._module_map:
                self._module_map[old_id] = self._module_map[new_id]

        self._setup_shell_ui()

    def _setup_shell_ui(self) -> None:
        """Construct the wood end-cheeks, titlebar, stacked widget, and page views."""
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        # Outer layout: Left Cheek (16px) | Center Console | Right Cheek (16px)
        outer_layout = QHBoxLayout(central_widget)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # 1. Left Walnut Wood Cheek
        self.left_wood_cheek = WoodCheek(is_right=False, parent=central_widget)
        outer_layout.addWidget(self.left_wood_cheek)

        # 2. Center Console Body (Titlebar + Viewport)
        console_container = QWidget(central_widget)
        console_layout = QVBoxLayout(console_container)
        console_layout.setContentsMargins(0, 0, 0, 0)
        console_layout.setSpacing(0)

        # 2a. Shell Titlebar (Height: 44px)
        self.titlebar = self._create_titlebar()
        console_layout.addWidget(self.titlebar)

        # 2b. Main Stacked Navigation Controller
        self.stack = QStackedWidget(console_container)

        # Index 0: Modular Hardware Grid Launcher
        self.page_launcher = LauncherGridPage(self.stack)
        self.page_launcher.module_requested.connect(self.navigate_to_module)
        self.page_launcher.file_dropped_on_module.connect(self.navigate_to_module_with_file)
        self.stack.addWidget(self.page_launcher)

        # Index 1: 4-Slot Workspace Template
        self.page_workspace = WorkspacePage(self.stack)
        self.page_workspace.back_requested.connect(self.navigate_to_launcher)
        self.stack.addWidget(self.page_workspace)

        # Index 2: Settings View
        self.page_settings = SettingsView(self.stack)
        self.page_settings.back_requested.connect(self.navigate_to_launcher)
        self.stack.addWidget(self.page_settings)

        console_layout.addWidget(self.stack)
        outer_layout.addWidget(console_container)

        # 3. Right Walnut Wood Cheek
        self.right_wood_cheek = WoodCheek(is_right=True, parent=central_widget)
        outer_layout.addWidget(self.right_wood_cheek)

    def _create_titlebar(self) -> QFrame:
        """Create the 44px Brand & Status Strip according to DESIGN.md Section 5.1."""
        titlebar = QFrame(self)
        titlebar.setFixedHeight(TOKENS.dimensions.shell.titlebar_height)  # 44px
        titlebar.setStyleSheet(
            f"QFrame {{"
            f"  background-color: {TOKENS.colors.background.app};"
            f"  border-bottom: 1px solid rgba(0, 0, 0, 0.55);"
            f"}}"
        )

        tb_layout = QHBoxLayout(titlebar)
        tb_layout.setContentsMargins(TOKENS.dimensions.shell.margin_x, 0, TOKENS.dimensions.shell.margin_x, 0)
        tb_layout.setSpacing(10)

        # Left branding: Cyan-Blue Diamond Mark + Silkscreen Wordmark
        self.lbl_logo = QLabel("◆", titlebar)
        self.lbl_logo.setFont(QFont("Arial", 14))
        self.lbl_logo.setStyleSheet("color: #5B9BFA; background: transparent;")
        tb_layout.addWidget(self.lbl_logo)

        self.lbl_brand = QLabel("UMBRA", titlebar)
        self.lbl_brand.setFont(TOKENS.typography.create_font("title_h1"))
        self.lbl_brand.setStyleSheet(
            f"color: {TOKENS.colors.text.silkscreen_title}; letter-spacing: -0.2px; background: transparent;"
        )
        tb_layout.addWidget(self.lbl_brand)

        # Subtitle / Version tag
        self.lbl_version = QLabel("v2.0 · Pro Suite", titlebar)
        self.lbl_version.setFont(TOKENS.typography.create_font("silkscreen_sub"))
        self.lbl_version.setStyleSheet(f"color: {TOKENS.colors.text.silkscreen_sub}; background: transparent;")
        tb_layout.addWidget(self.lbl_version)

        tb_layout.addStretch()

        # Right: Audio Engine Status Dot & Label
        self.lbl_engine_dot = QLabel("●", titlebar)
        self.lbl_engine_dot.setFont(QFont("Arial", 8))
        self.lbl_engine_dot.setStyleSheet(f"color: {TOKENS.colors.lamps.led_green_lit}; background: transparent;")
        tb_layout.addWidget(self.lbl_engine_dot)

        self.lbl_engine_text = QLabel("CoreAudio · 48 kHz", titlebar)
        self.lbl_engine_text.setFont(TOKENS.typography.create_font("data_mono_sm"))
        self.lbl_engine_text.setStyleSheet(f"color: {TOKENS.colors.text.silkscreen_sub}; background: transparent;")
        tb_layout.addWidget(self.lbl_engine_text)

        tb_layout.addSpacing(6)

        # Settings Gear Icon Button (disebelah kanan 48kHz)
        self.btn_settings = QPushButton("⚙", titlebar)
        self.btn_settings.setFixedSize(26, 22)
        self.btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_settings.setToolTip("Settings")
        self.btn_settings.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: {TOKENS.colors.background.surface_well_dark};"
            f"  color: {TOKENS.colors.text.silkscreen_tag};"
            f"  border: 1px solid rgba(255, 255, 255, 0.12);"
            f"  border-radius: 4px;"
            f"  font-size: 13px;"
            f"  padding: 0px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: #261B12;"
            f"  color: #F59E0B;"
            f"  border: 1px solid rgba(245, 158, 11, 0.5);"
            f"}}"
            f"QPushButton:pressed {{"
            f"  background-color: #0E0A08;"
            f"  color: #D97706;"
            f"  border: 1px solid rgba(0, 0, 0, 0.8);"
            f"}}"
        )
        self.btn_settings.clicked.connect(self.navigate_to_settings)
        tb_layout.addWidget(self.btn_settings)

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

    def navigate_to_settings(self) -> None:
        """Switch to SettingsView (Index 2), or toggle back to launcher if already in settings."""
        if self.stack.currentIndex() == 2:
            self.navigate_to_launcher()
        else:
            log.info("Navigating to settings.")
            self.stack.setCurrentIndex(2)

    def navigate_to_launcher(self) -> None:
        """Return to Modular Hardware Grid Launcher (Index 0)."""
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
