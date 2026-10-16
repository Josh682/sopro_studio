"""Home landing page with quick-access cards and dashboard metrics."""

from __future__ import annotations

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QGridLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from src.gui.watermarked_page import WatermarkedPage


class HomePage(WatermarkedPage):
    """Landing dashboard page providing quick-access shortcuts to app features."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Scroll area container for cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; } QScrollBar { background: #181825; }")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(24)

        # Quick access cards grid layout
        cards_layout = QGridLayout()
        cards_layout.setSpacing(20)

        # Row 0: Foundation Tools
        self._converter_card = self._build_card(
            title="Audio Converter",
            desc="Batch convert files between WAV, MP3, and FLAC with customizable samplerates and bit depths.",
            btn_label="Open Converter",
            target_page="converter",
            color="#89b4fa",  # Blue
        )
        cards_layout.addWidget(self._converter_card, 0, 0)

        self._separator_card = self._build_card(
            title="AI Stem Separator",
            desc="Isolate vocals and instrumentals from any track using the MelBand-RoFormer AI neural network.",
            btn_label="Open Separator",
            target_page="separator",
            color="#fab387",  # Peach
        )
        cards_layout.addWidget(self._separator_card, 0, 1)

        self._combiner_card = self._build_card(
            title="Track Combiner",
            desc="Merge separated stems back together into a single track with volume normalization.",
            btn_label="Open Combiner",
            target_page="combiner",
            color="#a6e3a1",  # Green
        )
        cards_layout.addWidget(self._combiner_card, 0, 2)

        # Row 1: Pitch, Key, Tempo
        self._key_card = self._build_card(
            title="Key & Tempo Detect",
            desc="Analyze musical keys, alternatives, and BPM using the Krumhansl-Schmuckler algorithm.",
            btn_label="Open Key Detect",
            target_page="key_detection",
            color="#f9e2af",  # Yellow
        )
        cards_layout.addWidget(self._key_card, 1, 0)

        self._pitch_card = self._build_card(
            title="Pitch Shifter",
            desc="Batch transpose audio up or down in semitones without affecting the original tempo.",
            btn_label="Open Pitch Shift",
            target_page="pitch_shift",
            color="#f5c2e7",  # Pink
        )
        cards_layout.addWidget(self._pitch_card, 1, 1)

        self._tempo_card = self._build_card(
            title="Tempo Change",
            desc="Batch stretch or compress audio playback speed to match a target BPM without altering pitch.",
            btn_label="Open Tempo Change",
            target_page="tempo_change",
            color="#94e2d5",  # Teal
        )
        cards_layout.addWidget(self._tempo_card, 1, 2)

        # Row 2: Diagnostics & Utility
        self._trim_card = self._build_card(
            title="Audio Trim",
            desc="Destructively crop audio to a specific time range with optional fades and visual waveforms.",
            btn_label="Open Audio Trim",
            target_page="trimmer",
            color="#f38ba8",  # Red
        )
        cards_layout.addWidget(self._trim_card, 2, 0)

        self._loudness_card = self._build_card(
            title="Loudness Normalize",
            desc="Standardize track volumes to EBU R128 targets (LUFS) for streaming or broadcast.",
            btn_label="Open Normalizer",
            target_page="loudness",
            color="#89dceb",  # Sky Blue
        )
        cards_layout.addWidget(self._loudness_card, 2, 1)

        self._metadata_card = self._build_card(
            title="Audio Information",
            desc="Analyze detailed audio statistics including True Peak, LUFS, bit depth, and metadata.",
            btn_label="Open Audio Info",
            target_page="metadata",
            color="#b4befe",  # Lavender
        )
        cards_layout.addWidget(self._metadata_card, 2, 2)

        # Row 3: V4.0 Audio Enhancement & Repair
        self._declip_card = self._build_card(
            title="Declip Repair",
            desc="Reconstruct clipped waveform peaks and eliminate harsh digital distortion using spline and AR models.",
            btn_label="Open Declip",
            target_page="declip",
            color="#cba6f7",  # Mauve
        )
        cards_layout.addWidget(self._declip_card, 3, 0)

        self._denoise_card = self._build_card(
            title="AI Denoise",
            desc="Eliminate tape hiss, 50/60Hz electrical hum, fan drone, and background ambient noise.",
            btn_label="Open Denoise",
            target_page="denoise",
            color="#89dceb",  # Sky Blue
        )
        cards_layout.addWidget(self._denoise_card, 3, 1)

        self._dereverb_card = self._build_card(
            title="AI Dereverb",
            desc="Suppress room reflections, early echoes, and long reverberant tails for a dry direct signal.",
            btn_label="Open Dereverb",
            target_page="dereverb",
            color="#b4befe",  # Lavender
        )
        cards_layout.addWidget(self._dereverb_card, 3, 2)

        # Row 4: Voice & Full Restoration
        self._voice_card = self._build_card(
            title="Voice Enhancement",
            desc="Dial in vocal clarity, reduce boxy lower-mid mud (200-500Hz), tame sibilance, and lift presence.",
            btn_label="Open Voice Enhance",
            target_page="voice_enhancement",
            color="#f5c2e7",  # Pink
        )
        cards_layout.addWidget(self._voice_card, 4, 0)

        self._restoration_card = self._build_card(
            title="Audio Restoration",
            desc="Multi-stage repair suite fixing vinyl crackle, digital dropouts, clipped peaks, and tape hiss.",
            btn_label="Open Restoration",
            target_page="restoration",
            color="#f2cdcd",  # Flamingo
        )
        cards_layout.addWidget(self._restoration_card, 4, 1)

        layout.addLayout(cards_layout)

        # Footer dashboard tip
        tip = QLabel(
            "💡 Pro-tip: Go to Settings to configure the directory where your models and outputs are saved."
        )
        tip.setStyleSheet("color: #a6adc8; font-size: 12px; font-style: italic; margin-top: 16px;")
        tip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(tip)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

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
        card_title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {color};")

        card_desc = QLabel(desc)
        card_desc.setStyleSheet("font-size: 13px; color: #a6adc8; line-height: 1.4;")
        card_desc.setWordWrap(True)
        card_desc.setMinimumHeight(55)

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
                opacity: 0.85;
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
