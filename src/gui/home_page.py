"""Home landing page with quick-access cards and dashboard metrics."""

from __future__ import annotations

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QGridLayout, QLabel, QPushButton, QVBoxLayout, QWidget
from src.gui.watermarked_page import WatermarkedPage


class HomePage(WatermarkedPage):
    """Landing dashboard page providing quick-access shortcuts to app features."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(24)

        # Header/Watermark logic is inherited from WatermarkedPage

        # Quick access cards grid layout
        cards_layout = QGridLayout()
        cards_layout.setSpacing(20)

        # Converter Card
        self._converter_card = self._build_card(
            title="Audio Converter",
            desc="Batch convert files between WAV, MP3, and FLAC with customizable samplerates and bit depths.",
            btn_label="Open Converter",
            target_page="converter",
            color="#89b4fa"  # Blue
        )
        cards_layout.addWidget(self._converter_card, 0, 0)

        # Separator Card
        self._separator_card = self._build_card(
            title="AI Stem Separator",
            desc="Isolate vocals and instrumentals from any track using the MelBand-RoFormer AI neural network.",
            btn_label="Open Separator",
            target_page="separator",
            color="#fab387"  # Peach
        )
        cards_layout.addWidget(self._separator_card, 0, 1)

        # Combiner Card
        self._combiner_card = self._build_card(
            title="Track Combiner",
            desc="Merge separated stems back together into a single track with volume normalization.",
            btn_label="Open Combiner",
            target_page="combiner",
            color="#a6e3a1"  # Green
        )
        cards_layout.addWidget(self._combiner_card, 0, 2)

        # Key Detector Card
        self._key_card = self._build_card(
            title="Key & Tempo Detect",
            desc="Analyze musical keys, alternatives, and BPM using the Krumhansl-Schmuckler algorithm.",
            btn_label="Open Key Detect",
            target_page="key_detection",
            color="#f9e2af"  # Yellow
        )
        cards_layout.addWidget(self._key_card, 1, 0)

        # Pitch Shifter Card
        self._pitch_card = self._build_card(
            title="Pitch Shifter",
            desc="Batch transpose audio up or down in semitones without affecting the original tempo.",
            btn_label="Open Pitch Shift",
            target_page="pitch_shift",
            color="#f5c2e7"  # Pink
        )
        cards_layout.addWidget(self._pitch_card, 1, 1)

        # Tempo Change Card
        self._tempo_card = self._build_card(
            title="Tempo Change",
            desc="Batch stretch or compress audio playback speed to match a target BPM without altering pitch.",
            btn_label="Open Tempo Change",
            target_page="tempo_change",
            color="#94e2d5"  # Teal
        )
        cards_layout.addWidget(self._tempo_card, 1, 2)

        # Audio Trim Card
        self._trim_card = self._build_card(
            title="Audio Trim",
            desc="Destructively crop audio to a specific time range with optional fades.",
            btn_label="Open Audio Trim",
            target_page="trimmer",
            color="#f38ba8"  # Red
        )
        cards_layout.addWidget(self._trim_card, 2, 0)
        
        # Loudness Normalize Card
        self._loudness_card = self._build_card(
            title="Loudness Normalize",
            desc="Standardize track volumes to EBU R128 targets (LUFS) for streaming or broadcast.",
            btn_label="Open Normalizer",
            target_page="loudness",
            color="#89dceb"  # Sky Blue
        )
        cards_layout.addWidget(self._loudness_card, 2, 1)

        # Audio Information Card
        self._metadata_card = self._build_card(
            title="Audio Information",
            desc="Analyze detailed audio statistics including True Peak, LUFS, bit depth, and metadata.",
            btn_label="Open Audio Info",
            target_page="metadata",
            color="#b4befe"  # Lavender
        )
        cards_layout.addWidget(self._metadata_card, 2, 2)

        layout.addLayout(cards_layout)

        # Footer dashboard tip
        layout.addStretch()
        
        tip = QLabel(
            "💡 Pro-tip: Go to Settings to configure the directory where your models are saved "
            "and to adjust the chunk size to tune memory usage."
        )
        tip.setStyleSheet("color: #a6adc8; font-size: 12px; font-style: italic;")
        tip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(tip)

    def _build_card(self, title: str, desc: str, btn_label: str, target_page: str, color: str = "#cba6f7") -> QWidget:
        """Helper to build a styled dash-card container."""
        card = QWidget()
        card.setObjectName("DashCard")
        card.setStyleSheet(
            """
            QWidget#DashCard {
                background-color: #1e1e2e;
                border: 1px solid #313244;
                border-radius: 12px;
            }
            """
        )
        
        lay = QVBoxLayout(card)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(16)

        card_title = QLabel(title)
        card_title.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {color};")
        
        card_desc = QLabel(desc)
        card_desc.setStyleSheet("font-size: 13px; color: #a6adc8; line-height: 1.4;")
        card_desc.setWordWrap(True)
        card_desc.setMinimumHeight(60)

        btn = QPushButton(btn_label)
        btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {color};
                color: #11111b;
                font-weight: bold;
                border-radius: 6px;
                padding: 10px 16px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                opacity: 0.8;
            }}
            """
        )
        btn.clicked.connect(lambda: self._go_to(target_page))

        lay.addWidget(card_title)
        lay.addWidget(card_desc)
        lay.addWidget(btn)
        
        return card


    def _go_to(self, page_key: str) -> None:
        """Route page navigation event to the root MainWindow shell."""
        window = self.window()
        if hasattr(window, "_navigate"):
            window._navigate(page_key)
