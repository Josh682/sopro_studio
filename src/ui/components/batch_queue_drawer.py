"""BatchQueueDrawer - Tactical Multi-Track Batch Processing Drawer for Umbra Slot 2.

Implements Milestone 4 requirements:
- Dark rack-mount console table for multi-file batches (e.g. MOD-01 Converter, MOD-03 Combiner).
- Displays track index handle (⠿ 01), filename, format tag, size, duration, and DSP status badge.
- Drag-and-drop row reordering (crucial for MOD-03 Track Combiner mixing sequence)
  along with tactile ▲ / ▼ accessible reorder buttons.
- Individual row removal [✕], Add Files [+ Add Files...], and Clear Queue actions.
- Emits files_reordered, file_removed, file_selected, and add_files_requested signals.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

from src.ui.qt import (
    QAbstractItemView,
    QColor,
    QDropEvent,
    QFont,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    Qt,
    QVBoxLayout,
    QWidget,
    Signal,
)
from src.ui.theme.tokens import TOKENS

log = logging.getLogger("sound_processor.ui.components.batch_queue_drawer")


def _format_size(size_bytes: int) -> str:
    """Format byte size into human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


class StatusBadge(QFrame):
    """Tactile industrial status pill widget for queue table rows."""

    STATUS_CONFIGS = {
        "pending": ("#1C1917", "#78716C", "PENDING", "#44403C"),
        "processing": ("#2D1E10", "#F59E0B", "PROCG [==]", "#F59E0B"),
        "done": ("#0D2818", "#22C55E", "DONE ✓", "#166534"),
        "error": ("#2A0D0D", "#EF4444", "ERROR ✗", "#991B1B"),
    }

    def __init__(self, status: str = "pending", message: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(22)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(0)

        self.lbl_text = QLabel(self)
        self.lbl_text.setFont(TOKENS.typography.create_font("data_mono_sm"))
        self.lbl_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_text)

        self.set_status(status, message)

    def set_status(self, status: str, message: str = "") -> None:
        key = status.lower()
        bg, fg, default_text, border = self.STATUS_CONFIGS.get(key, self.STATUS_CONFIGS["pending"])
        display_text = message if message else default_text
        self.lbl_text.setText(display_text)
        self.lbl_text.setStyleSheet(f"color: {fg}; background: transparent; border: none; font-weight: bold;")
        self.setStyleSheet(
            f"StatusBadge {{"
            f"  background-color: {bg};"
            f"  border: 1px solid {border};"
            f"  border-radius: 3px;"
            f"}}"
        )
        if message:
            self.setToolTip(message)


class RowActionsWidget(QFrame):
    """Tactile micro-action buttons (▲, ▼, ✕) for reordering and removing queue items."""

    move_up_clicked = Signal(int)
    move_down_clicked = Signal(int)
    remove_clicked = Signal(int)

    def __init__(self, row_idx: int, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._row_idx = row_idx
        self.setStyleSheet("background: transparent; border: none;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(3)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        btn_style = (
            f"QPushButton {{"
            f"  background-color: #17100B;"
            f"  color: {TOKENS.colors.text.secondary};"
            f"  border: 1px solid rgba(255, 255, 255, 0.08);"
            f"  border-radius: 3px;"
            f"  font-size: 10px;"
            f"  font-weight: bold;"
            f"  padding: 0px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: #2D1E10;"
            f"  color: #F59E0B;"
            f"  border-color: #F59E0B;"
            f"}}"
            f"QPushButton:pressed {{"
            f"  background-color: #0E0A08;"
            f"}}"
        )

        remove_btn_style = (
            f"QPushButton {{"
            f"  background-color: #1F1111;"
            f"  color: #EF4444;"
            f"  border: 1px solid rgba(239, 68, 68, 0.25);"
            f"  border-radius: 3px;"
            f"  font-size: 11px;"
            f"  font-weight: bold;"
            f"  padding: 0px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: #3A1414;"
            f"  border-color: #EF4444;"
            f"  color: #FFFFFF;"
            f"}}"
            f"QPushButton:pressed {{"
            f"  background-color: #140707;"
            f"}}"
        )

        self.btn_up = QPushButton("▲", self)
        self.btn_up.setFixedSize(20, 20)
        self.btn_up.setToolTip("Move track up")
        self.btn_up.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_up.setStyleSheet(btn_style)
        self.btn_up.clicked.connect(lambda: self.move_up_clicked.emit(self._row_idx))
        layout.addWidget(self.btn_up)

        self.btn_down = QPushButton("▼", self)
        self.btn_down.setFixedSize(20, 20)
        self.btn_down.setToolTip("Move track down")
        self.btn_down.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_down.setStyleSheet(btn_style)
        self.btn_down.clicked.connect(lambda: self.move_down_clicked.emit(self._row_idx))
        layout.addWidget(self.btn_down)

        self.btn_remove = QPushButton("✕", self)
        self.btn_remove.setFixedSize(20, 20)
        self.btn_remove.setToolTip("Remove from queue")
        self.btn_remove.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_remove.setStyleSheet(remove_btn_style)
        self.btn_remove.clicked.connect(lambda: self.remove_clicked.emit(self._row_idx))
        layout.addWidget(self.btn_remove)

    def set_row_idx(self, idx: int, total_rows: int) -> None:
        self._row_idx = idx
        self.btn_up.setEnabled(idx > 0)
        self.btn_down.setEnabled(idx < total_rows - 1)


class ReorderableTableWidget(QTableWidget):
    """QTableWidget subclass with native drag-and-drop row reordering support."""

    order_changed = Signal(int, int)  # (from_row, to_row)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDragDropOverwriteMode(False)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

    def dropEvent(self, event: QDropEvent) -> None:
        if not event.isAccepted() and event.source() == self:
            drop_row = self.drop_on_row(event)
            source_rows = [sel.topRow() for sel in self.selectedRanges()]
            if source_rows and drop_row != -1:
                from_row = source_rows[0]
                if drop_row > from_row:
                    drop_row -= 1
                if from_row != drop_row:
                    self.order_changed.emit(from_row, drop_row)
                    event.acceptProposedAction()
                    return
        super().dropEvent(event)

    def drop_on_row(self, event: QDropEvent) -> int:
        item = self.itemAt(event.position().toPoint())
        if item:
            return item.row()
        return self.rowCount() - 1 if self.rowCount() > 0 else 0


class BatchQueueDrawer(QFrame):
    """Tactile Dark Console Batch Processing Queue Drawer for Slot 2.

    Manages multiple input tracks, internal drag/button reordering, individual
    track removal, and live DSP execution status badges per track.
    """

    files_reordered = Signal(list)  # List[str]
    file_removed = Signal(str)      # str (file_path)
    file_selected = Signal(str)     # str (file_path)
    add_files_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._files: List[str] = []
        self._file_statuses: Dict[str, tuple[str, str]] = {}  # path -> (status, msg)
        self._selected_index: int = 0

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Construct the dark console batch drawer UI."""
        self.setStyleSheet(
            f"BatchQueueDrawer {{"
            f"  background-color: {TOKENS.colors.background.surface_well};"
            f"  border: 1px solid {TOKENS.colors.border.subtle};"
            f"  border-radius: {TOKENS.radii.md}px;"
            f"}}"
        )

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(8)

        # Header bar: Title count + Add Files + Clear Queue
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        self.lbl_title = QLabel("BATCH QUEUE · 0 TRACKS", self)
        self.lbl_title.setFont(TOKENS.typography.create_font("data_mono_sm"))
        self.lbl_title.setStyleSheet(f"color: {TOKENS.colors.text.muted}; background: transparent; border: none;")
        header_layout.addWidget(self.lbl_title)

        header_layout.addStretch()

        # [ + Add Files... ] tactile button
        self.btn_add = QPushButton("+ Add Files...", self)
        self.btn_add.setFont(TOKENS.typography.create_font("data_mono_sm"))
        self.btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: #17100B;"
            f"  color: {TOKENS.colors.text.primary};"
            f"  border: 1px solid {TOKENS.colors.border.card};"
            f"  border-radius: 4px;"
            f"  padding: 3px 10px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: #2D1E10;"
            f"  color: #F59E0B;"
            f"  border-color: #F59E0B;"
            f"}}"
        )
        self.btn_add.clicked.connect(self.add_files_requested.emit)
        header_layout.addWidget(self.btn_add)

        # [ Clear Queue ] button
        self.btn_clear = QPushButton("Clear", self)
        self.btn_clear.setFont(TOKENS.typography.create_font("data_mono_sm"))
        self.btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: transparent;"
            f"  color: {TOKENS.colors.text.muted};"
            f"  border: 1px solid rgba(255, 255, 255, 0.08);"
            f"  border-radius: 4px;"
            f"  padding: 3px 8px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  color: #EF4444;"
            f"  border-color: rgba(239, 68, 68, 0.4);"
            f"}}"
        )
        self.btn_clear.clicked.connect(self.clear)
        header_layout.addWidget(self.btn_clear)

        main_layout.addLayout(header_layout)

        # Reorderable Table Widget
        self.table = ReorderableTableWidget(self)
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["#", "FILE NAME", "FORMAT", "SIZE", "STATUS", "ACTIONS"])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)

        self.table.setColumnWidth(0, 48)   # #
        self.table.setColumnWidth(2, 90)   # Format
        self.table.setColumnWidth(3, 80)   # Size
        self.table.setColumnWidth(4, 115)  # Status
        self.table.setColumnWidth(5, 95)   # Actions

        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        table_qss = (
            f"QTableWidget {{"
            f"  background-color: #0A0D12;"
            f"  border: 1px solid rgba(255, 255, 255, 0.05);"
            f"  border-radius: 4px;"
            f"  gridline-color: transparent;"
            f"  selection-background-color: #241A12;"
            f"  selection-color: #F59E0B;"
            f"}}"
            f"QHeaderView::section {{"
            f"  background-color: #11141A;"
            f"  color: {TOKENS.colors.text.muted};"
            f"  font-size: 10px;"
            f"  font-weight: bold;"
            f"  border: none;"
            f"  border-bottom: 1px solid rgba(255, 255, 255, 0.08);"
            f"  padding: 4px;"
            f"}}"
            f"QScrollBar:vertical {{"
            f"  background: #0A0D12;"
            f"  width: 8px;"
            f"  margin: 0px;"
            f"}}"
            f"QScrollBar::handle:vertical {{"
            f"  background: #2A1F16;"
            f"  min-height: 20px;"
            f"  border-radius: 4px;"
            f"}}"
            f"QScrollBar::handle:vertical:hover {{"
            f"  background: #F59E0B;"
            f"}}"
        )
        self.table.setStyleSheet(table_qss)
        self.table.itemClicked.connect(self._on_table_item_clicked)
        self.table.order_changed.connect(self._on_drag_reorder)

        main_layout.addWidget(self.table)

    # --- Public API ---

    def set_files(self, file_paths: List[str]) -> None:
        """Populate the batch drawer with a list of file paths."""
        self._files = list(file_paths)
        for p in self._files:
            if p not in self._file_statuses:
                self._file_statuses[p] = ("pending", "")
        self._refresh_table()

    def get_files(self) -> List[str]:
        """Return the current file paths in active queue order."""
        return list(self._files)

    def add_files(self, file_paths: List[str]) -> None:
        """Append additional files to the queue."""
        added = False
        for p in file_paths:
            if p not in self._files:
                self._files.append(p)
                self._file_statuses[p] = ("pending", "")
                added = True
        if added:
            self._refresh_table()
            self.files_reordered.emit(list(self._files))

    def set_file_status(self, file_path: str, status: str, message: str = "") -> None:
        """Update live status pill for a specific file."""
        self._file_statuses[file_path] = (status, message)
        if file_path in self._files:
            row = self._files.index(file_path)
            badge_widget = self.table.cellWidget(row, 4)
            if isinstance(badge_widget, StatusBadge):
                badge_widget.set_status(status, message)

    def set_progress(self, file_path: str, progress: float) -> None:
        """Update processing progress readout for a specific file."""
        pct = int(progress * 100)
        self.set_file_status(file_path, "processing", f"PROCG {pct}%")

    def clear(self) -> None:
        """Clear all tracks from the batch queue."""
        if not self._files and not self._file_statuses:
            return
        self._files.clear()
        self._file_statuses.clear()
        self._refresh_table()
        self.files_reordered.emit([])

    # --- Table Population & Rendering ---

    def _refresh_table(self) -> None:
        """Render rows based on current _files order."""
        total = len(self._files)
        self.lbl_title.setText(f"BATCH QUEUE · {total} {'TRACK' if total == 1 else 'TRACKS'}")

        self.table.setRowCount(total)

        for row, path_str in enumerate(self._files):
            p = Path(path_str)
            self.table.setRowHeight(row, 30)

            # Col 0: Index handle
            item_idx = QTableWidgetItem(f"⠿ {row + 1:02d}")
            item_idx.setFont(TOKENS.typography.create_font("data_mono_sm"))
            item_idx.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_idx.setForeground(QColor(TOKENS.colors.text.muted))
            item_idx.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, 0, item_idx)

            # Col 1: Filename
            item_name = QTableWidgetItem(p.name)
            item_name.setFont(TOKENS.typography.create_font("body_regular"))
            item_name.setForeground(QColor(TOKENS.colors.text.primary))
            item_name.setToolTip(str(p.resolve()))
            item_name.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, 1, item_name)

            # Col 2: Format
            suffix = p.suffix.upper()[1:] if p.suffix else "RAW"
            item_fmt = QTableWidgetItem(f"{suffix} Audio")
            item_fmt.setFont(TOKENS.typography.create_font("data_mono_sm"))
            item_fmt.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_fmt.setForeground(QColor(TOKENS.colors.text.secondary))
            item_fmt.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, 2, item_fmt)

            # Col 3: Size
            size_str = "--"
            if p.is_file():
                try:
                    size_str = _format_size(os.path.getsize(path_str))
                except OSError:
                    pass
            item_size = QTableWidgetItem(size_str)
            item_size.setFont(TOKENS.typography.create_font("data_mono_sm"))
            item_size.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_size.setForeground(QColor(TOKENS.colors.text.muted))
            item_size.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, 3, item_size)

            # Col 4: Status Badge
            st, msg = self._file_statuses.get(path_str, ("pending", ""))
            badge = StatusBadge(status=st, message=msg, parent=self.table)
            self.table.setCellWidget(row, 4, badge)

            # Col 5: Actions Widget (▲, ▼, ✕)
            actions = RowActionsWidget(row_idx=row, parent=self.table)
            actions.set_row_idx(row, total)
            actions.move_up_clicked.connect(self._move_row_up)
            actions.move_down_clicked.connect(self._move_row_down)
            actions.remove_clicked.connect(self._remove_row)
            self.table.setCellWidget(row, 5, actions)

        # Highlight currently selected row if within bounds
        if 0 <= self._selected_index < total:
            self.table.selectRow(self._selected_index)

    # --- Reordering & Removal Handlers ---

    def _move_row_up(self, row: int) -> None:
        """Swap row with predecessor."""
        if row > 0:
            self._swap_rows(row, row - 1)

    def _move_row_down(self, row: int) -> None:
        """Swap row with successor."""
        if row < len(self._files) - 1:
            self._swap_rows(row, row + 1)

    def _swap_rows(self, idx1: int, idx2: int) -> None:
        """Internal helper to swap two positions."""
        self._files[idx1], self._files[idx2] = self._files[idx2], self._files[idx1]
        self._selected_index = idx2
        self._refresh_table()
        self.files_reordered.emit(list(self._files))

    def _on_drag_reorder(self, from_row: int, to_row: int) -> None:
        """Handle internal move drag drop."""
        if from_row == to_row or from_row < 0 or to_row < 0:
            return
        item = self._files.pop(from_row)
        self._files.insert(to_row, item)
        self._selected_index = to_row
        self._refresh_table()
        self.files_reordered.emit(list(self._files))

    def _remove_row(self, row: int) -> None:
        """Remove a single file from the batch queue."""
        if 0 <= row < len(self._files):
            removed = self._files.pop(row)
            if removed in self._file_statuses:
                del self._file_statuses[removed]
            self._selected_index = min(self._selected_index, max(0, len(self._files) - 1))
            self._refresh_table()
            self.file_removed.emit(removed)
            self.files_reordered.emit(list(self._files))

    def _on_table_item_clicked(self, item: QTableWidgetItem) -> None:
        """Emit file_selected when user clicks on a table row."""
        row = item.row()
        if 0 <= row < len(self._files):
            self._selected_index = row
            self.file_selected.emit(self._files[row])
