"""Unit Tests for Milestone 1: AudioPlayerController, Transport & Dynamic Playhead."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Headless platform
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from src.ui.qt import (
    QApplication,
    QKeyEvent,
    QMouseEvent,
    QPoint,
    QPointF,
    Qt,
)

# Ensure QApplication exists
app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

import numpy as np
import soundfile as sf

from src.audio.player import AudioPlayerController, format_timecode
from src.ui.components.custom_stages.waveform_stage import WaveformStage
from src.ui.views.workspace_template import WorkspacePage


class TestAudioPlayer(unittest.TestCase):
    """Test suite for AudioPlayerController and transport integration."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.test_wav = Path(cls.temp_dir.name) / "test_sine_2s.wav"

        # Generate a 2.0-second 44.1kHz stereo test tone
        sr = 44100
        dur = 2.0
        t = np.linspace(0, dur, int(sr * dur), endpoint=False)
        left = 0.5 * np.sin(2 * np.pi * 440.0 * t)
        right = 0.5 * np.sin(2 * np.pi * 880.0 * t)
        stereo = np.column_stack((left, right)).astype(np.float32)
        sf.write(str(cls.test_wav), stereo, sr)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp_dir.cleanup()

    def test_timecode_formatting(self) -> None:
        """Verify MM:SS.cc timecode string conversion."""
        self.assertEqual(format_timecode(0.0), "00:00.00")
        self.assertEqual(format_timecode(5.25), "00:05.25")
        self.assertEqual(format_timecode(74.5), "01:14.50")
        self.assertEqual(format_timecode(3661.2), "61:01.20")
        self.assertEqual(format_timecode(-5.0), "00:00.00")

    def test_player_init_and_properties(self) -> None:
        """Verify default player state on initialization."""
        player = AudioPlayerController()
        self.assertEqual(player.position, 0.0)
        self.assertEqual(player.duration, 0.0)
        self.assertFalse(player.is_playing)
        self.assertFalse(player.is_looping)
        self.assertIsNone(player.current_file)

    def test_player_load_and_seek(self) -> None:
        """Verify loading an audio file, querying duration, and seeking."""
        player = AudioPlayerController()
        loaded = player.load(self.test_wav)
        self.assertTrue(loaded)
        self.assertIsNotNone(player.current_file)
        self.assertAlmostEqual(player.duration, 2.0, delta=0.1)

        # Listen for signals
        pos_captured = []
        player.positionChanged.connect(lambda p: pos_captured.append(p))

        # Seek to 1.0 second
        player.seek(1.0)
        self.assertAlmostEqual(player.position, 1.0, delta=0.01)
        self.assertIn(1.0, pos_captured)

        # Clamping beyond duration
        player.seek(999.0)
        self.assertAlmostEqual(player.position, player.duration, delta=0.01)

        # Clamping negative
        player.seek(-5.0)
        self.assertAlmostEqual(player.position, 0.0, delta=0.01)

    def test_loop_range_configuration(self) -> None:
        """Verify setting loop state and boundaries."""
        player = AudioPlayerController()
        player.load(self.test_wav)

        player.set_loop(True, start_sec=0.4, end_sec=1.6)
        self.assertTrue(player.is_looping)
        self.assertEqual(player._loop_start_sec, 0.4)
        self.assertEqual(player._loop_end_sec, 1.6)

        player.set_loop(False)
        self.assertFalse(player.is_looping)

    def test_waveform_stage_playhead_and_scrubbing(self) -> None:
        """Verify WaveformStage playhead updates and scrubbing signals."""
        stage = WaveformStage()
        stage.resize(400, 170)
        stage.load_audio_preview(str(self.test_wav))
        self.assertAlmostEqual(stage._duration, 2.0, delta=0.1)

        # Test setting playhead
        stage.set_playhead(1.25)
        self.assertAlmostEqual(stage._playhead_sec, 1.25, delta=0.01)

        # Test scrubbing signal emission on mouse press
        seek_target = None
        stage.seekRequested.connect(lambda t: nonlocal_set(t))

        def nonlocal_set(val):
            nonlocal seek_target
            seek_target = val

        # Simulate click at center (x = 200, representing ~50% duration = 1.0s)
        pos = QPointF(200, 80)
        press_event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            pos,
            pos,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        stage.mousePressEvent(press_event)
        self.assertIsNotNone(seek_target)
        self.assertAlmostEqual(seek_target, 1.0, delta=0.2)
        self.assertTrue(stage._is_scrubbing)

        # Simulate release
        release_event = QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            pos,
            pos,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        stage.mouseReleaseEvent(release_event)
        self.assertFalse(stage._is_scrubbing)

    def test_workspace_transport_integration(self) -> None:
        """Verify WorkspacePage transport bar wiring and Spacebar shortcut."""
        ws = WorkspacePage()
        ws.resize(1152, 768)

        # Verify transport controls presence
        self.assertTrue(hasattr(ws, "btn_transport_play"))
        self.assertTrue(hasattr(ws, "btn_transport_stop"))
        self.assertTrue(hasattr(ws, "btn_transport_loop"))
        self.assertTrue(hasattr(ws, "lbl_timecode"))

        # Configure module and load file
        mod_info = {
            "id": "edit",
            "title": "Audio Editor",
            "code": "[MOD-06]",
            "accent_key": "trim",
            "action_text": "Trim & Normalize",
        }
        ws.configure_module(mod_info, file_path=str(self.test_wav))

        # Check timecode updated
        self.assertIn("00:00.00", ws.lbl_timecode.text())
        self.assertIn("00:02.00", ws.lbl_timecode.text())

        # Test toggle playback via method
        ws._toggle_playback()
        self.assertEqual(ws.btn_transport_play.text(), "❚❚")

        # Test pause
        ws._toggle_playback()
        self.assertEqual(ws.btn_transport_play.text(), "▶")

        # Test Spacebar shortcut
        space_press = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier)
        ws.keyPressEvent(space_press)
        self.assertEqual(ws.btn_transport_play.text(), "❚❚")

        # Stop playback
        ws._stop_playback()
        self.assertEqual(ws.btn_transport_play.text(), "▶")

        # Clean reset
        ws.reset_file_and_params()
        self.assertEqual(ws._player.position, 0.0)
        self.assertIn("00:00.00 / 00:00.00", ws.lbl_timecode.text())


if __name__ == "__main__":
    unittest.main()
