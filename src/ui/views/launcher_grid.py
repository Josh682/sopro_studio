"""LauncherGridPage - 3x3 Dark Modern Bento Grid for Module Launchers.

Implements:
- 3x3 layout with 24px horizontal and 20px vertical gap.
- 9 modules with exact tags, titles, descriptions, and accent bindings.
- Navigation triggers via button click or file drag-and-drop.
- Zero scrollbars at standard 1152x768 resolution.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.ui.qt import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    Qt,
    QVBoxLayout,
    QWidget,
    Signal,
)

from src.ui.theme.tokens import TOKENS
from src.ui.widgets.launcher_card import LauncherCard

# Specification for all 9 modules from DESIGN.md and prompt
MODULE_DEFINITIONS: List[Dict[str, str]] = [
    {
        "id": "converter",
        "code": "[MOD-01]",
        "tag": "[CONV]",
        "title": "Audio Converter",
        "description": "Convert between WAV, MP3, FLAC and AIFF.",
        "button_text": "Open Converter",
        "action_text": "Convert Files",
        "accent_key": "converter",
    },
    {
        "id": "separator",
        "code": "[MOD-02]",
        "tag": "[STEM]",
        "title": "AI Stem Separator",
        "description": "Extract clean vocals and instrumentals from any audio file.",
        "button_text": "Open Separator",
        "action_text": "Separate Stems",
        "accent_key": "separator",
    },
    {
        "id": "combiner",
        "code": "[MOD-03]",
        "tag": "[MERG]",
        "title": "Track Combiner",
        "description": "Merge stems and tracks into a single audio file.",
        "button_text": "Open Combiner",
        "action_text": "Merge Tracks",
        "accent_key": "combiner",
    },
    {
        "id": "detect",
        "code": "[MOD-04]",
        "tag": "[DETC]",
        "title": "Key & Tempo Detect",
        "description": "Find the musical key and BPM of any track.",
        "button_text": "Open Detector",
        "action_text": "Export Key & Tempo",
        "accent_key": "detect",
    },
    {
        "id": "pitch",
        "code": "[MOD-05]",
        "tag": "[PTCH]",
        "title": "Pitch Shifter",
        "description": "Transpose audio up or down in semitones.",
        "button_text": "Open Shifter",
        "action_text": "Shift Pitch",
        "accent_key": "pitch",
    },
    {
        "id": "tempo",
        "code": "[MOD-06]",
        "tag": "[TMP]",
        "title": "Tempo Change",
        "description": "Speed up or slow down audio without altering pitch.",
        "button_text": "Open Tempo",
        "action_text": "Apply Tempo Change",
        "accent_key": "tempo",
    },
    {
        "id": "trim",
        "code": "[MOD-07]",
        "tag": "[TRIM]",
        "title": "Audio Trim",
        "description": "Cut and trim audio with millisecond precision.",
        "button_text": "Open Trimmer",
        "action_text": "Trim Audio",
        "accent_key": "trim",
    },
    {
        "id": "normalize",
        "code": "[MOD-08]",
        "tag": "[NORM]",
        "title": "Loudness Normalize",
        "description": "Standardize volume to LUFS streaming presets.",
        "button_text": "Open Normalizer",
        "action_text": "Normalize Loudness",
        "accent_key": "normalize",
    },
    {
        "id": "info",
        "code": "[MOD-09]",
        "tag": "[INFO]",
        "title": "Audio Information",
        "description": "Inspect detailed audio metadata and properties.",
        "button_text": "Open Inspector",
        "action_text": "Copy Metadata",
        "accent_key": "info",
    },
]


class LauncherGridPage(QWidget):
    """Main dashboard page rendering the 3x3 Bento Grid of audio modules."""

    # Navigation signals
    module_requested = Signal(str)  # module_id
    file_dropped_on_module = Signal(str, str)  # (module_id, file_path)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._cards: Dict[str, LauncherCard] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Initialize the grid layout and populate 9 cards."""
        # Top-level container layout
        main_layout = QVBoxLayout(self)
        margin_x = TOKENS.dimensions.shell.margin_x  # 32px
        margin_y = TOKENS.dimensions.shell.margin_y  # 24px
        main_layout.setContentsMargins(margin_x, margin_y, margin_x, margin_y)
        main_layout.setSpacing(0)

        # 3x3 Bento Grid layout
        grid_layout = QGridLayout()
        grid_layout.setHorizontalSpacing(TOKENS.dimensions.grid.gap_x)  # 24px
        grid_layout.setVerticalSpacing(TOKENS.dimensions.grid.gap_y)  # 20px
        grid_layout.setContentsMargins(0, 0, 0, 0)

        for i, mod in enumerate(MODULE_DEFINITIONS):
            row = i // TOKENS.dimensions.grid.columns
            col = i % TOKENS.dimensions.grid.columns

            card = LauncherCard(
                module_id=mod["id"],
                code=mod["code"],
                tag=mod["tag"],
                title=mod["title"],
                description=mod["description"],
                button_text=mod["button_text"],
                accent_key=mod["accent_key"],
                parent=self,
            )

            # Connect signals
            card.open_requested.connect(self._on_card_opened)
            card.file_dropped.connect(self._on_card_file_dropped)

            self._cards[mod["id"]] = card
            grid_layout.addWidget(card, row, col)

        main_layout.addLayout(grid_layout)

    def _on_card_opened(self, module_id: str) -> None:
        self.module_requested.emit(module_id)

    def _on_card_file_dropped(self, module_id: str, file_path: str) -> None:
        self.file_dropped_on_module.emit(module_id, file_path)

    def get_card(self, module_id: str) -> Optional[LauncherCard]:
        return self._cards.get(module_id)
