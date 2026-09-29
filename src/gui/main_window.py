"""Main application window container with stacked layout pages and sidebar navigation."""

from __future__ import annotations

import logging
from pathlib import Path
import time

from qtpy.QtCore import Qt, QUrl
from qtpy.QtGui import QPixmap, QIcon, QDesktopServices
from src.utils.paths import resource_path
from src.utils.updater import UpdateCheckerWorker
from qtpy.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QFrame,
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

# V4.0 Audio Enhancement & Repair Pages
from src.gui.declip_page import DeclipPage
from src.gui.denoise_page import DenoisePage
from src.gui.dereverb_page import DereverbPage
from src.gui.voice_enhancement_page import VoiceEnhancementPage
from src.gui.restoration_page import RestorationPage

log = logging.getLogger("sound_processor.gui.main_window")


class MainWindow(QMainWindow):
    """Primary application frame hosting page switches and dark style themes."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Sopro Studio v1.0")
        self.setMinimumSize(1024, 680)
        
        logo_path = resource_path("assets/sopro_studio_logo.png")
        if logo_path.exists():
            self.setWindowIcon(QIcon(str(logo_path)))

        # Apply CSS stylesheets
        self._apply_theme()

        # Central container
        central = QWidget()
        self.setCentralWidget(central)
        
        main_vbox = QVBoxLayout(central)
        main_vbox.setContentsMargins(0, 0, 0, 0)
        main_vbox.setSpacing(0)

        # Update Banner (Hidden by default)
        self._update_banner = QFrame()
        self._update_banner.setStyleSheet("""
            QFrame {
                background-color: #313244;
                border-bottom: 1px solid #89b4fa;
            }
        """)
        self._update_banner.hide()
        banner_layout = QHBoxLayout(self._update_banner)
        banner_layout.setContentsMargins(20, 10, 20, 10)
        
        self._update_label = QLabel()
        self._update_label.setStyleSheet("color: #cdd6f4; border: none; font-size: 13px;")
        
        self._update_download_btn = QPushButton("Download")
        self._update_download_btn.setStyleSheet("""
            QPushButton {
                background-color: #89b4fa;
                color: #1e1e2e;
                font-weight: bold;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover { background-color: #74c7ec; }
        """)
        self._update_download_btn.clicked.connect(self._on_update_download)
        
        self._update_dismiss_btn = QPushButton("Later")
        self._update_dismiss_btn.setStyleSheet("""
            QPushButton {
                background-color: #45475a;
                color: #cdd6f4;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover { background-color: #585b70; }
        """)
        self._update_dismiss_btn.clicked.connect(self._update_banner.hide)
        
        banner_layout.addWidget(self._update_label)
        banner_layout.addStretch()
        banner_layout.addWidget(self._update_dismiss_btn)
        banner_layout.addWidget(self._update_download_btn)
        
        main_vbox.addWidget(self._update_banner)
        
        # Sidebar and stack container
        content_widget = QWidget()
        layout = QHBoxLayout(content_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        main_vbox.addWidget(content_widget)

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
            "declip": DeclipPage(self),
            "denoise": DenoisePage(self),
            "dereverb": DereverbPage(self),
            "voice_enhancement": VoiceEnhancementPage(self),
            "restoration": RestorationPage(self),
            "settings": SettingsPage(self),
        }
        for page in self._pages.values():
            self._stack.addWidget(page)
        
        layout.addWidget(self._stack, stretch=1)

        # Connect global python logger messages to log panels in pages
        self._setup_logging_bridge()
        
        # Schedule update check 5 seconds after startup
        from qtpy.QtCore import QTimer
        QTimer.singleShot(5000, self._check_for_updates)

        # Navigate to homepage by default
        self._navigate("home")

    def _check_for_updates(self) -> None:
        """Run update check in the background if enabled and 24h passed."""
        if not hasattr(self, "_config") or not self._config.auto_check_updates:
            return
            
        now = time.time()
        last_check = self._config.last_update_check
        
        # Check if 24 hours (86400 seconds) have passed
        if now - last_check < 86400:
            return
            
        # Update last check time
        self._config.last_update_check = now
        
        self._updater_worker = UpdateCheckerWorker(parent=self)
        self._updater_worker.update_available.connect(self._show_update_banner)
        self._updater_worker.start()

    def _show_update_banner(self, version: str, notes: str, download_url: str) -> None:
        """Display the unobtrusive update banner."""
        self._update_download_url = download_url
        self._update_label.setText(
            f"<b>Update Available!</b> Sopro Studio {version} is now available. "
            f"<span style='color: #a6adc8;'>{notes}</span>"
        )
        self._update_banner.show()
        
    def _on_update_download(self) -> None:
        """Open browser to the download URL."""
        if hasattr(self, "_update_download_url"):
            QDesktopServices.openUrl(QUrl(self._update_download_url))
            self._update_banner.hide()

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
            for key in [
                "converter", "separator", "combiner", "key_detection", "pitch_shift",
                "tempo_change", "trimmer", "loudness", "metadata",
                "declip", "denoise", "dereverb", "voice_enhancement", "restoration"
            ]:
                if key in self._pages and hasattr(self._pages[key], "_log_panel"):
                    self._log_handler.log_message.connect(self._pages[key]._log_panel.append_log)

            logging.getLogger("sound_processor").addHandler(self._log_handler)
            log.debug("Qt logging bridge initialized successfully.")
        except Exception as exc:
            log.warning("Could not set up GUI logging bridge: %s", exc)

    def _apply_theme(self) -> None:
        """Read and load stylesheet rules from dark.qss."""
        theme_path = resource_path("assets/themes/dark.qss")
        if theme_path.exists():
            try:
                self.setStyleSheet(theme_path.read_text(encoding="utf-8"))
                log.debug("Styles loaded successfully from dark.qss.")
            except Exception as exc:
                log.warning("Could not read stylesheet: %s", exc)

    def _build_sidebar(self) -> QWidget:
        """Create and style sidebar layouts with collapsible group and button navigation triggers."""
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(230)
        sidebar.setStyleSheet(
            "#Sidebar { background-color: #11111b; border-right: 1px solid #313244; }"
            "QPushButton { background-color: transparent; color: #a6adc8; border: none; padding: 10px 14px; text-align: left; font-size: 13px; font-weight: 500; border-radius: 6px; margin: 0 8px; }"
            "QPushButton:hover { background-color: #1e1e2e; color: #cdd6f4; }"
            "QPushButton:checked { background-color: #313244; color: #cba6f7; font-weight: bold; }"
            "QScrollArea { border: none; background: transparent; }"
        )

        outer_layout = QVBoxLayout(sidebar)
        outer_layout.setContentsMargins(0, 20, 0, 12)
        outer_layout.setSpacing(8)

        # Header with Logo
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(16, 0, 16, 12)
        header_layout.setSpacing(12)

        logo_label = QLabel()
        logo_path = resource_path("assets/sopro_logo_only.png")
        if logo_path.exists():
            pixmap = QPixmap(str(logo_path))
            scaled_pixmap = pixmap.scaledToHeight(28, Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(scaled_pixmap)
            header_layout.addWidget(logo_label)

        title_label = QLabel("Sopro Studio")
        title_label.setObjectName("SidebarTitle")
        title_label.setStyleSheet("font-size: 17px; font-weight: bold; color: #cdd6f4;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        outer_layout.addWidget(header_widget)

        # Scroll area for navigation buttons to handle any screen resolution
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(4)

        self._nav_buttons: dict[str, QPushButton] = {}

        # Core Tools
        core_nav = [
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
        ]

        for key, label in core_nav:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, k=key: self._navigate(k))
            self._nav_buttons[key] = btn
            scroll_layout.addWidget(btn)

        # Collapsible "Enhancement" Section
        self._enhancement_expanded = True
        self._enhancement_toggle_btn = QPushButton("🔧 Enhancement ▾")
        self._enhancement_toggle_btn.setStyleSheet(
            "QPushButton { background-color: #181825; color: #cba6f7; font-weight: bold; font-size: 13px; padding: 10px 14px; border-radius: 6px; margin: 6px 8px; }"
            "QPushButton:hover { background-color: #313244; color: #f5c2e7; }"
        )
        self._enhancement_toggle_btn.clicked.connect(self._toggle_enhancement_section)
        scroll_layout.addWidget(self._enhancement_toggle_btn)

        # Sub-buttons container
        self._enhancement_container = QWidget()
        enhancement_sub_layout = QVBoxLayout(self._enhancement_container)
        enhancement_sub_layout.setContentsMargins(12, 0, 0, 0)
        enhancement_sub_layout.setSpacing(4)

        enhancement_nav = [
            ("declip", "Declip Repair"),
            ("denoise", "AI Denoise"),
            ("dereverb", "AI Dereverb"),
            ("voice_enhancement", "Voice Enhance"),
            ("restoration", "Restoration"),
        ]

        for key, label in enhancement_nav:
            btn = QPushButton(f"  • {label}")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, k=key: self._navigate(k))
            self._nav_buttons[key] = btn
            enhancement_sub_layout.addWidget(btn)

        scroll_layout.addWidget(self._enhancement_container)

        # Settings
        settings_btn = QPushButton("⚙️ Settings")
        settings_btn.setCheckable(True)
        settings_btn.clicked.connect(lambda checked: self._navigate("settings"))
        self._nav_buttons["settings"] = settings_btn
        scroll_layout.addWidget(settings_btn)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        outer_layout.addWidget(scroll, stretch=1)

        return sidebar

    def _toggle_enhancement_section(self) -> None:
        """Toggle visibility of the collapsible Enhancement tools section."""
        self._enhancement_expanded = not self._enhancement_expanded
        self._enhancement_container.setVisible(self._enhancement_expanded)
        arrow = "▾" if self._enhancement_expanded else "▸"
        self._enhancement_toggle_btn.setText(f"🔧 Enhancement {arrow}")

    def _navigate(self, page_key: str) -> None:
        """Switch active page in stacked layout and toggle button checked highlight."""
        if page_key not in self._pages:
            log.warning("Attempted to navigate to unknown page: %s", page_key)
            return

        # If navigating to an enhancement sub-tool, auto-expand the section if collapsed
        enhancement_keys = ["declip", "denoise", "dereverb", "voice_enhancement", "restoration"]
        if page_key in enhancement_keys and not self._enhancement_expanded:
            self._toggle_enhancement_section()

        for key, btn in self._nav_buttons.items():
            btn.setChecked(key == page_key)
            
        self._stack.setCurrentWidget(self._pages[page_key])
        log.debug("Navigated to: %s", page_key)
