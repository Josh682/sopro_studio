"""Main application window container with stacked layout pages and sidebar navigation."""

from __future__ import annotations

import logging
from pathlib import Path

from qtpy.QtCore import Qt
from qtpy.QtGui import QPixmap, QIcon
from qtpy.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.gui.converter_page import ConverterPage
from src.gui.home_page import HomePage
from src.gui.separator_page import SeparatorPage
from src.gui.combiner_page import CombinerPage
from src.gui.key_detection_page import KeyDetectionPage
from src.gui.pitch_shift_page import PitchShiftPage
from src.gui.tempo_change_page import TempoChangePage
from src.gui.trimmer_page import TrimmerPage
from src.gui.loudness_page import LoudnessPage
from src.gui.metadata_page import MetadataPage
from src.gui.settings_page import SettingsPage

log = logging.getLogger("sound_processor.gui.main_window")


class MainWindow(QMainWindow):
    """Primary application frame hosting page switches and dark style themes."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Sopro Studio v1.0")
        self.setMinimumSize(1024, 680)
        
        logo_path = Path(__file__).resolve().parent.parent.parent / "assets" / "sopro_studio_logo.png"
        if logo_path.exists():
            self.setWindowIcon(QIcon(str(logo_path)))

        # Apply CSS stylesheets
        self._apply_theme()

        # Central container
        central = QWidget()
        self.setCentralWidget(central)
        
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Sidebar navigation panel
        sidebar = self._build_sidebar()
        layout.addWidget(sidebar)

        # Page view stacker
        self._stack = QStackedWidget()
        self._pages = {
            "home": HomePage(self),
            "converter": ConverterPage(self),
            "separator": SeparatorPage(self),
            "combiner": CombinerPage(self),
            "key_detection": KeyDetectionPage(self),
            "pitch_shift": PitchShiftPage(self),
            "tempo_change": TempoChangePage(self),
            "trimmer": TrimmerPage(self),
            "loudness": LoudnessPage(self),
            "metadata": MetadataPage(self),
            "settings": SettingsPage(self),
        }
        for page in self._pages.values():
            self._stack.addWidget(page)
        
        layout.addWidget(self._stack, stretch=1)

        # Connect global python logger messages to log panels in pages
        self._setup_logging_bridge()

        # Navigate to homepage by default
        self._navigate("home")

    def _setup_logging_bridge(self) -> None:
        """Setup logging bridge via QtLogHandler to forward all app logs to page consoles."""
        from src.utils.logger import QtLogHandler

        try:
            self._log_handler = QtLogHandler()
            
            # Simple format so LogPanel timestamp looks clean
            formatter = logging.Formatter("%(levelname)s: %(message)s")
            self._log_handler.setFormatter(formatter)
            self._log_handler.setLevel(logging.INFO)

            # Route logs to all tool consoles
            self._log_handler.log_message.connect(self._pages["converter"]._log_panel.append_log)
            self._log_handler.log_message.connect(self._pages["separator"]._log_panel.append_log)
            self._log_handler.log_message.connect(self._pages["combiner"]._log_panel.append_log)
            self._log_handler.log_message.connect(self._pages["key_detection"]._log_panel.append_log)
            self._log_handler.log_message.connect(self._pages["pitch_shift"]._log_panel.append_log)
            self._log_handler.log_message.connect(self._pages["tempo_change"]._log_panel.append_log)
            self._log_handler.log_message.connect(self._pages["trimmer"]._log_panel.append_log)
            self._log_handler.log_message.connect(self._pages["loudness"]._log_panel.append_log)
            self._log_handler.log_message.connect(self._pages["metadata"]._log_panel.append_log)

            logging.getLogger("sound_processor").addHandler(self._log_handler)
            log.debug("Qt logging bridge initialized successfully.")
        except Exception as exc:
            log.warning("Could not set up GUI logging bridge: %s", exc)

    def _apply_theme(self) -> None:
        """Read and load stylesheet rules from dark.qss."""
        theme_path = Path(__file__).resolve().parent.parent / "assets" / "themes" / "dark.qss"
        if theme_path.exists():
            try:
                self.setStyleSheet(theme_path.read_text(encoding="utf-8"))
                log.debug("Styles loaded successfully from dark.qss.")
            except Exception as exc:
                log.warning("Could not read stylesheet: %s", exc)

    def _build_sidebar(self) -> QWidget:
        """Create and style sidebar layouts with button navigation triggers."""
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(220)
        sidebar.setStyleSheet(
            "#Sidebar { background-color: #11111b; border-right: 1px solid #313244; }"
            "QPushButton { background-color: transparent; color: #a6adc8; border: none; padding: 12px 16px; text-align: left; font-size: 14px; font-weight: 500; border-radius: 6px; margin: 0 12px; }"
            "QPushButton:hover { background-color: #1e1e2e; color: #cdd6f4; }"
            "QPushButton:checked { background-color: #313244; color: #cba6f7; font-weight: bold; }"
        )

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 24, 0, 12)
        layout.setSpacing(8)

        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(16, 0, 16, 16)
        header_layout.setSpacing(12)

        logo_label = QLabel()
        logo_path = Path(__file__).resolve().parent.parent.parent / "assets" / "sopro_logo_only.png"
        if logo_path.exists():
            pixmap = QPixmap(str(logo_path))
            scaled_pixmap = pixmap.scaledToHeight(32, Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(scaled_pixmap)
            header_layout.addWidget(logo_label)

        title_label = QLabel("Sopro Studio")
        title_label.setObjectName("SidebarTitle")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #cdd6f4;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        layout.addWidget(header_widget)

        self._nav_buttons: dict[str, QPushButton] = {}
        for key, label in [
            ("home", "Home"),
            ("converter", "Converter"),
            ("separator", "Separator"),
            ("combiner", "Combiner"),
            ("key_detection", "Key Detection"),
            ("pitch_shift", "Pitch Shift"),
            ("tempo_change", "Tempo Change"),
            ("trimmer", "Audio Trim"),
            ("loudness", "Loudness Normalize"),
            ("metadata", "Information"),
            ("settings", "Settings"),
        ]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, k=key: self._navigate(k))
            self._nav_buttons[key] = btn
            layout.addWidget(btn)

        layout.addStretch()
        return sidebar

    def _navigate(self, page_key: str) -> None:
        """Switch active page in stacked layout and toggle button checked highlight."""
        if page_key not in self._pages:
            log.warning("Attempted to navigate to unknown page: %s", page_key)
            return

        for key, btn in self._nav_buttons.items():
            btn.setChecked(key == page_key)
            
        self._stack.setCurrentWidget(self._pages[page_key])
        log.debug("Navigated to: %s", page_key)
