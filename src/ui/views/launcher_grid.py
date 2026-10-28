"""LauncherGridPage - 3x3 Analog Console Hardware Grid for Module Launchers.

Implements DESIGN.md Section 5.1 & Section 7.1:
- 3x3 layout with 16px horizontal and 16px vertical gap.
- Margins: 24px horizontal, 20px vertical.
- 9 modules on modular bronze hardware cards (346x216px).
- Navigation triggers via amber backlit button click, manual browse button, or file drag-and-drop.
- Zero scrollbars at standard 1152x768 resolution.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.ui.qt import (
    QDragEnterEvent,
    QDragLeaveEvent,
    QDragMoveEvent,
    QDropEvent,
    QEvent,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QKeyEvent,
    QLabel,
    QSizePolicy,
    Qt,
    QTimer,
    QVBoxLayout,
    QWidget,
    Signal,
)

from src.ui.theme.tokens import TOKENS
from src.ui.widgets.launcher_card import LauncherCard, audio_file_from_mime

# Specification for all 9 modules from DESIGN.md Section 7.1 & 7.2
MODULE_DEFINITIONS: List[Dict[str, str]] = [
    {
        "id": "converter",
        "code": "[MOD-01]",
        "tag": "[CONV]",
        "title": "Audio Converter",
        "button_text": "Open Converter",
        "action_text": "Convert Files",
        "accent_key": "converter",
    },
    {
        "id": "separator",
        "code": "[MOD-02]",
        "tag": "[STEM]",
        "title": "AI Stem Separator",
        "button_text": "Open Separator",
        "action_text": "Separate Stems",
        "accent_key": "separator",
    },
    {
        "id": "combiner",
        "code": "[MOD-03]",
        "tag": "[MERG]",
        "title": "Track Combiner",
        "button_text": "Open Combiner",
        "action_text": "Merge Tracks",
        "accent_key": "combiner",
    },
    {
        "id": "analyze",
        "code": "[MOD-04]",
        "tag": "[DETC]",
        "title": "Music Analyzer",
        "button_text": "Open Analyzer",
        "action_text": "Analyze Audio",
        "accent_key": "detect",
    },
    {
        "id": "pitch_time",
        "code": "[MOD-05]",
        "tag": "[PTCH]",
        "title": "Pitch & Time Lab",
        "button_text": "Open Lab",
        "action_text": "Process Audio",
        "accent_key": "pitch",
    },
    {
        "id": "edit",
        "code": "[MOD-06]",
        "tag": "[EDIT]",
        "title": "Audio Editor",
        "button_text": "Open Editor",
        "action_text": "Trim & Normalize",
        "accent_key": "trim",
    },
    {
        "id": "repair",
        "code": "[MOD-07]",
        "tag": "[REPR]",
        "title": "Clip & Click Repair",
        "button_text": "Open Repair",
        "action_text": "Repair Audio",
        "accent_key": "tempo",
    },
    {
        "id": "clean",
        "code": "[MOD-08]",
        "tag": "[DENR]",
        "title": "Noise & Room Repair",
        "button_text": "Open Cleaner",
        "action_text": "Clean Audio",
        "accent_key": "normalize",
    },
    {
        "id": "voice",
        "code": "[MOD-09]",
        "tag": "[VOIC]",
        "title": "Voice & Polish Lab",
        "button_text": "Open Voice Lab",
        "action_text": "Enhance Voice",
        "accent_key": "info",
    },
]


class LauncherGridPage(QWidget):
    """Console viewport page rendering the 3x3 modular hardware grid."""

    # Navigation signals
    module_requested = Signal(str)  # module_id
    file_dropped_on_module = Signal(str, str)  # (module_id, file_path)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.setAcceptDrops(True)
        self._cards: Dict[str, LauncherCard] = {}
        self._focused_card_index: int = 0
        self._disarm_timer = QTimer(self)
        self._disarm_timer.setSingleShot(True)
        self._disarm_timer.setInterval(80)
        self._disarm_timer.timeout.connect(lambda: self._set_armed(False))
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Initialize the grid layout and populate 9 modular cards."""
        # Top-level container layout matching DESIGN.md Section 5.2 margins
        main_layout = QVBoxLayout(self)
        margin_x = TOKENS.dimensions.shell.margin_x  # 24px
        margin_y = TOKENS.dimensions.shell.margin_y  # 20px
        main_layout.setContentsMargins(margin_x, margin_y, margin_x, margin_y)
        main_layout.setSpacing(0)

        # 3x3 Modular Grid layout
        grid_layout = QGridLayout()
        grid_layout.setHorizontalSpacing(TOKENS.dimensions.grid.gap_x)  # 16px
        grid_layout.setVerticalSpacing(TOKENS.dimensions.grid.gap_y)  # 16px
        grid_layout.setContentsMargins(0, 0, 0, 0)

        for i, mod in enumerate(MODULE_DEFINITIONS):
            row = i // TOKENS.dimensions.grid.columns
            col = i % TOKENS.dimensions.grid.columns

            card = LauncherCard(
                module_id=mod["id"],
                code=mod["code"],
                tag=mod["tag"],
                title=mod["title"],
                button_text=mod["button_text"],
                accent_key=mod["accent_key"],
                parent=self,
            )

            # Connect signals and event filter for global drag state coordination
            card.open_requested.connect(self._on_card_opened)
            card.file_dropped.connect(self._on_card_file_dropped)
            card.focus_changed.connect(lambda focused, idx=i: self._on_card_focus_changed(idx, focused))
            card.installEventFilter(self)

            self._cards[mod["id"]] = card
            grid_layout.addWidget(card, row, col)

        # Explicit Tab Order across cards 0 through 8
        card_list = list(self._cards.values())
        for idx in range(len(card_list) - 1):
            QWidget.setTabOrder(card_list[idx], card_list[idx + 1])

        main_layout.addLayout(grid_layout)

    def _on_card_focus_changed(self, idx: int, focused: bool) -> None:
        if focused:
            self._focused_card_index = idx

    def get_focused_card_index(self) -> int:
        return self._focused_card_index

    def set_focused_card_index(self, index: int) -> None:
        card_list = list(self._cards.values())
        if 0 <= index < len(card_list):
            self._focused_card_index = index
            card_list[index].setFocus(Qt.FocusReason.TabFocusReason)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle 3x3 grid spatial arrow key navigation across module cards."""
        card_list = list(self._cards.values())
        current_idx = self._focused_card_index
        for idx, card in enumerate(card_list):
            if card.hasFocus():
                current_idx = idx
                break

        key = event.key()
        if key in (Qt.Key.Key_Right, Qt.Key.Key_Left, Qt.Key.Key_Down, Qt.Key.Key_Up):
            if key == Qt.Key.Key_Right:
                target_idx = (current_idx + 1) % len(card_list)
            elif key == Qt.Key.Key_Left:
                target_idx = (current_idx - 1) % len(card_list)
            elif key == Qt.Key.Key_Down:
                target_idx = (current_idx + 3) % len(card_list)
            elif key == Qt.Key.Key_Up:
                target_idx = (current_idx - 3) % len(card_list)
            else:
                target_idx = current_idx

            self._focused_card_index = target_idx
            card_list[target_idx].setFocus(Qt.FocusReason.TabFocusReason)
            event.accept()
            return
        super().keyPressEvent(event)

    def _set_armed(self, armed: bool) -> None:
        """Propagate armed stand-by state to all 9 module cards."""
        for card in self._cards.values():
            card.set_armed(armed)

    def _on_drag_enter(self, event) -> None:
        if audio_file_from_mime(event.mimeData()):
            self._disarm_timer.stop()
            self._set_armed(True)

    def eventFilter(self, obj, event) -> bool:
        """Monitor drag events over cards to control global arming without consuming events."""
        event_type = event.type()
        if event_type == QEvent.Type.DragEnter:
            self._on_drag_enter(event)
        elif event_type == QEvent.Type.DragLeave:
            self._disarm_timer.start()
        elif event_type == QEvent.Type.Drop:
            self._disarm_timer.stop()
            self._set_armed(False)
        return False

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """Handle drag entering the grid container area between cards."""
        if audio_file_from_mime(event.mimeData()):
            self._disarm_timer.stop()
            self._set_armed(True)
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if audio_file_from_mime(event.mimeData()):
            self._disarm_timer.stop()
            event.accept()
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self._disarm_timer.start()
        event.accept()

    def dropEvent(self, event: QDropEvent) -> None:
        self._disarm_timer.stop()
        self._set_armed(False)
        event.ignore()

    def _on_card_opened(self, module_id: str) -> None:
        self.module_requested.emit(module_id)

    def _on_card_file_dropped(self, module_id: str, file_path: str) -> None:
        self.file_dropped_on_module.emit(module_id, file_path)

    def get_card(self, module_id: str) -> Optional[LauncherCard]:
        return self._cards.get(module_id)
