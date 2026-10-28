"""Unit tests for Milestone 4: Batch Processing Queue Drawer & Output Routing Pipeline.

Verifies:
1. BatchQueueDrawer table population, format/size formatting, and title readouts.
2. Drag-to-reorder, micro-button reordering (▲/▼), and row index synchronization.
3. DSP status transitions (PENDING, PROCESSING, DONE, ERROR) and progress updates.
4. Single row removal [✕], Add Files [+ Add Files...], and Clear Queue actions.
5. Cross-platform file manager reveal helper (reveal_in_file_manager).
6. WorkspacePage Deck Header segmented toggle between [ ≡ QUEUE ] and [ ∿ DECK / WAVE ].
7. Post-processing hand-off cluster in Slot 4 (Reveal in Finder, Play Result, Send to Module).
8. End-to-end cross-module routing pipeline wired to MainWindow.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import soundfile as sf

from src.ui.qt import QApplication, QTableWidgetItem, Qt
from src.ui.components.batch_queue_drawer import (
    BatchQueueDrawer,
    RowActionsWidget,
    StatusBadge,
    _format_size,
)
from src.ui.main_window import MainWindow
from src.ui.views.workspace_template import WorkspacePage
from src.utils.file_utils import reveal_in_file_manager


# Ensure a single headless QApplication instance exists
app = QApplication.instance()
if app is None:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication(sys.argv)


def _create_sine_wav(path: Path, freq: float = 440.0, dur: float = 0.5, sr: int = 44100) -> None:
    """Helper to generate a valid WAV file with soundfile."""
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)
    sig = (np.sin(2 * np.pi * freq * t) * 0.5).astype(np.float32)
    stereo = np.column_stack((sig, sig))
    sf.write(str(path), stereo, sr)


class TestBatchQueueDrawer(unittest.TestCase):
    """Test suite for the dark console BatchQueueDrawer component."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.tmp_dir.name).resolve()

        # Create 3 valid audio files
        self.p1 = self.base_path / "track_01_kick.wav"
        self.p2 = self.base_path / "track_02_snare.wav"
        self.p3 = self.base_path / "track_03_hihat.flac"

        _create_sine_wav(self.p1, 100.0)
        _create_sine_wav(self.p2, 250.0)
        _create_sine_wav(self.p3, 1000.0)

        self.f1 = str(self.p1)
        self.f2 = str(self.p2)
        self.f3 = str(self.p3)

        self.drawer = BatchQueueDrawer()
        self.drawer.show()

    def tearDown(self) -> None:
        self.drawer.deleteLater()
        self.tmp_dir.cleanup()

    def test_size_formatting(self) -> None:
        """Verify byte size formatting helper."""
        self.assertEqual(_format_size(500), "500 B")
        self.assertEqual(_format_size(2048), "2.0 KB")
        self.assertEqual(_format_size(10 * 1024 * 1024), "10.0 MB")

    def test_table_population(self) -> None:
        """Verify drawer populates table rows and headers correctly."""
        files = [self.f1, self.f2, self.f3]
        self.drawer.set_files(files)

        self.assertEqual(self.drawer.table.rowCount(), 3)
        self.assertEqual(self.drawer.get_files(), files)
        self.assertIn("3 TRACKS", self.drawer.lbl_title.text())

        # Check Col 0: Index grip
        self.assertEqual(self.drawer.table.item(0, 0).text(), "⠿ 01")
        self.assertEqual(self.drawer.table.item(1, 0).text(), "⠿ 02")
        self.assertEqual(self.drawer.table.item(2, 0).text(), "⠿ 03")

        # Check Col 1: Filename
        self.assertEqual(self.drawer.table.item(0, 1).text(), "track_01_kick.wav")
        self.assertEqual(self.drawer.table.item(1, 1).text(), "track_02_snare.wav")
        self.assertEqual(self.drawer.table.item(2, 1).text(), "track_03_hihat.flac")

        # Check Col 2: Format tag
        self.assertEqual(self.drawer.table.item(0, 2).text(), "WAV Audio")
        self.assertEqual(self.drawer.table.item(1, 2).text(), "WAV Audio")
        self.assertEqual(self.drawer.table.item(2, 2).text(), "FLAC Audio")

        # Check Col 4: Initial Status Badge
        badge0 = self.drawer.table.cellWidget(0, 4)
        self.assertIsInstance(badge0, StatusBadge)
        self.assertEqual(badge0.lbl_text.text(), "PENDING")

    def test_status_and_progress_updates(self) -> None:
        """Verify status pill updates and progress readouts."""
        self.drawer.set_files([self.f1, self.f2])

        # Transition f1 to processing
        self.drawer.set_file_status(self.f1, "processing", "PROCG [==]")
        b1 = self.drawer.table.cellWidget(0, 4)
        self.assertEqual(b1.lbl_text.text(), "PROCG [==]")

        # Update progress on f1
        self.drawer.set_progress(self.f1, 0.75)
        self.assertEqual(b1.lbl_text.text(), "PROCG 75%")

        # Complete f1
        self.drawer.set_file_status(self.f1, "done", "DONE ✓")
        self.assertEqual(b1.lbl_text.text(), "DONE ✓")

        # Error on f2
        self.drawer.set_file_status(self.f2, "error", "ERROR ✗")
        b2 = self.drawer.table.cellWidget(1, 4)
        self.assertEqual(b2.lbl_text.text(), "ERROR ✗")

    def test_row_reordering_micro_buttons(self) -> None:
        """Verify ▲ / ▼ micro buttons swap rows and emit files_reordered."""
        self.drawer.set_files([self.f1, self.f2, self.f3])

        reordered_events = []
        self.drawer.files_reordered.connect(reordered_events.append)

        # Move f1 down -> [f2, f1, f3]
        self.drawer._move_row_down(0)
        self.assertEqual(self.drawer.get_files(), [self.f2, self.f1, self.f3])
        self.assertEqual(len(reordered_events), 1)
        self.assertEqual(reordered_events[0], [self.f2, self.f1, self.f3])

        # Move f3 up -> [f2, f3, f1]
        self.drawer._move_row_up(2)
        self.assertEqual(self.drawer.get_files(), [self.f2, self.f3, self.f1])
        self.assertEqual(len(reordered_events), 2)
        self.assertEqual(reordered_events[1], [self.f2, self.f3, self.f1])

        # Check index handles updated
        self.assertEqual(self.drawer.table.item(0, 0).text(), "⠿ 01")
        self.assertEqual(self.drawer.table.item(1, 0).text(), "⠿ 02")
        self.assertEqual(self.drawer.table.item(2, 0).text(), "⠿ 03")

    def test_drag_reorder_handler(self) -> None:
        """Verify _on_drag_reorder method updates files and emits signal."""
        self.drawer.set_files([self.f1, self.f2, self.f3])

        reordered_events = []
        self.drawer.files_reordered.connect(reordered_events.append)

        # Drag from index 2 to index 0 -> [f3, f1, f2]
        self.drawer._on_drag_reorder(2, 0)
        self.assertEqual(self.drawer.get_files(), [self.f3, self.f1, self.f2])
        self.assertEqual(len(reordered_events), 1)
        self.assertEqual(reordered_events[0], [self.f3, self.f1, self.f2])

    def test_row_removal_and_clear(self) -> None:
        """Verify removing row updates table and emits file_removed."""
        self.drawer.set_files([self.f1, self.f2, self.f3])

        removed_events = []
        self.drawer.file_removed.connect(removed_events.append)

        # Remove row 1 (f2)
        self.drawer._remove_row(1)
        self.assertEqual(len(removed_events), 1)
        self.assertEqual(removed_events[0], self.f2)
        self.assertEqual(self.drawer.get_files(), [self.f1, self.f3])
        self.assertEqual(self.drawer.table.rowCount(), 2)

        # Clear queue
        self.drawer.clear()
        self.assertEqual(self.drawer.get_files(), [])
        self.assertEqual(self.drawer.table.rowCount(), 0)

    def test_file_selected_signal(self) -> None:
        """Verify clicking row emits file_selected."""
        self.drawer.set_files([self.f1, self.f2])

        selected_events = []
        self.drawer.file_selected.connect(selected_events.append)

        item = self.drawer.table.item(1, 1)
        self.drawer._on_table_item_clicked(item)
        self.assertEqual(len(selected_events), 1)
        self.assertEqual(selected_events[0], self.f2)


class TestFileRevealHelper(unittest.TestCase):
    """Test suite for reveal_in_file_manager helper."""

    def test_nonexistent_file(self) -> None:
        """Verify non-existent path returns False safely."""
        fake_path = "/nonexistent/path/to/nothing_12345.wav"
        self.assertFalse(reveal_in_file_manager(fake_path))

    @patch("subprocess.run")
    def test_darwin_file_reveal(self, mock_run) -> None:
        """Verify macOS calls 'open -R'."""
        with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
            with patch("sys.platform", "darwin"):
                result = reveal_in_file_manager(tmp.name)
                self.assertTrue(result)
                mock_run.assert_called_once()
                cmd = mock_run.call_args[0][0]
                self.assertEqual(cmd[0], "open")
                self.assertEqual(cmd[1], "-R")
                self.assertEqual(cmd[2], str(Path(tmp.name).resolve()))

    @patch("subprocess.run")
    def test_windows_file_reveal(self, mock_run) -> None:
        """Verify Windows calls explorer /select,."""
        with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
            with patch("sys.platform", "win32"):
                result = reveal_in_file_manager(tmp.name)
                self.assertTrue(result)
                mock_run.assert_called_once()
                cmd = mock_run.call_args[0][0]
                self.assertEqual(cmd[0], "explorer")
                self.assertTrue(cmd[1].startswith("/select,"))


class TestWorkspaceBatchAndRouting(unittest.TestCase):
    """Test suite for WorkspacePage queue integration and post-processing handoff."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.tmp_dir.name).resolve()

        self.p1 = self.base_path / "track_01.wav"
        self.p2 = self.base_path / "track_02.wav"
        self.p3 = self.base_path / "track_03.wav"
        self.out_p = self.base_path / "output_processed.wav"

        _create_sine_wav(self.p1, 200.0)
        _create_sine_wav(self.p2, 300.0)
        _create_sine_wav(self.p3, 400.0)
        _create_sine_wav(self.out_p, 500.0)

        self.f1 = str(self.p1)
        self.f2 = str(self.p2)
        self.f3 = str(self.p3)
        self.out_file = str(self.out_p)

        self.page = WorkspacePage()
        self.page.show()

    def tearDown(self) -> None:
        self.page.deleteLater()
        self.tmp_dir.cleanup()

    def test_single_file_hides_queue_toggle(self) -> None:
        """Verify single file mode hides view toggle and shows visual stage."""
        self.page.load_file(self.f1)
        self.assertTrue(self.page.view_toggle_container.isHidden())
        self.assertEqual(self.page._current_file, self.f1)
        self.assertEqual(len(self.page._current_files), 1)

    def test_multi_file_shows_queue_toggle(self) -> None:
        """Verify loading multiple files displays toggle pill and defaults to queue view."""
        self.page.load_files([self.f1, self.f2, self.f3])
        self.assertFalse(self.page.view_toggle_container.isHidden())
        self.assertTrue(self.page.btn_view_queue.isChecked())
        self.assertEqual(self.page.deck_stack.currentWidget(), self.page.batch_queue_drawer)
        self.assertEqual(self.page.btn_view_queue.text(), "≡ QUEUE (3)")

        # Switch to visual stage
        self.page._on_view_stage_clicked()
        self.assertTrue(self.page.btn_view_stage.isChecked())
        self.assertFalse(self.page.btn_view_queue.isChecked())
        if self.page._custom_stage_widget:
            self.assertEqual(self.page.deck_stack.currentWidget(), self.page._custom_stage_widget)

    def test_queue_reordering_updates_workspace_files(self) -> None:
        """Verify reordering batch queue emits files_selected with new list."""
        self.page.load_files([self.f1, self.f2, self.f3])

        emitted_lists = []
        self.page.files_selected.connect(lambda mod, flist: emitted_lists.append(flist))

        new_order = [self.f3, self.f1, self.f2]
        self.page._on_queue_files_reordered(new_order)
        self.assertEqual(self.page._current_files, new_order)
        self.assertEqual(len(emitted_lists), 1)
        self.assertEqual(emitted_lists[0], new_order)

    def test_queue_file_removal_switches_back_to_single_file_mode(self) -> None:
        """Verify removing down to 1 file automatically hides toggle and returns to deck."""
        self.page.load_files([self.f1, self.f2])
        self.assertFalse(self.page.view_toggle_container.isHidden())

        # Remove f2
        self.page._on_queue_file_removed(self.f2)
        self.assertEqual(self.page._current_files, [self.f1])
        self.assertTrue(self.page.view_toggle_container.isHidden())

    def test_post_processing_handoff_cluster(self) -> None:
        """Verify successful DSP execution reveals handoff buttons and routes output."""
        self.page.load_file(self.f1)
        self.assertTrue(self.page.handoff_container.isHidden())

        # Simulate completion
        self.page._on_worker_finished(Path(self.out_file))
        self.assertFalse(self.page.handoff_container.isHidden())
        self.assertEqual(Path(self.page._last_output_file), Path(self.out_file))

        # Test routing signal
        route_events = []
        self.page.route_to_module_requested.connect(lambda mod_id, fpath: route_events.append((mod_id, fpath)))

        self.page._route_to_target_module("voice")
        self.assertEqual(len(route_events), 1)
        self.assertEqual(route_events[0], ("voice", str(self.out_file)))

    def test_play_result_action(self) -> None:
        """Verify Play Result loads the output file into audio player."""
        self.page.load_file(self.f1)
        self.page._on_worker_finished(Path(self.out_file))

        self.page._play_result_audio()
        self.assertEqual(str(self.page._player.current_file), str(self.out_file))


class TestMainWindowRoutingIntegration(unittest.TestCase):
    """Test suite verifying end-to-end routing between WorkspacePage and MainWindow."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.tmp_dir.name).resolve()
        self.out_p = self.base_path / "mastered_lead.wav"
        _create_sine_wav(self.out_p, 440.0)
        self.out_file = str(self.out_p)

        self.window = MainWindow()
        self.window.show()

    def tearDown(self) -> None:
        self.window.deleteLater()
        self.tmp_dir.cleanup()

    def test_route_to_module_requested_transitions_workspace(self) -> None:
        """Verify signal routes output file into target module workspace directly."""
        # Start at launcher
        self.assertEqual(self.window.stack.currentIndex(), 0)

        # Trigger routing from workspace
        self.window.page_workspace.route_to_module_requested.emit("clean", self.out_file)

        # Main window should transition to workspace (index 1) configured for 'clean'
        self.assertEqual(self.window.stack.currentIndex(), 1)
        self.assertEqual(self.window.page_workspace._current_module_id, "clean")
        self.assertEqual(self.window.page_workspace._current_file, self.out_file)
        self.assertEqual(str(self.window.page_workspace._player.current_file), str(self.out_file))


if __name__ == "__main__":
    unittest.main()
