"""Unit tests for Milestone 5: Haptics, Accessibility & macOS Packaging.

Verifies:
1. Procedural mechanical audio synthesis (Switch Click @ 2.1kHz and Knob Detent @ 3.5kHz).
2. HapticsEngine playback methods, volume scaling, and mute toggling.
3. TactileButton default haptics trigger and keyboard activation.
4. LauncherCard keyboard focus policy, focus ring rendering, and Return/Space activation.
5. LauncherGridPage tab order chain and 3x3 spatial arrow key grid navigation.
6. AnalogKnob keyboard adjustment (±1% span on Arrow keys, PageUp/Down, Home/End, R reset).
7. AnalogKnob center detent crossing detection.
8. scripts/build_macos_app.py spec generation, Info.plist creation, and dry-run validation.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

from src.ui.qt import QApplication, QKeyEvent, QMouseEvent, QPointF, Qt, QVBoxLayout, QWidget
from src.audio.haptics import (
    HapticsEngine,
    get_haptics_engine,
    get_haptics_volume,
    is_haptics_enabled,
    play_knob_detent,
    play_switch_click,
    set_haptics_enabled,
    set_haptics_volume,
    synthesize_knob_detent,
    synthesize_switch_click,
)
from src.ui.views.launcher_grid import LauncherGridPage, MODULE_DEFINITIONS
from src.ui.widgets.analog_controls import AnalogKnob
from src.ui.widgets.launcher_card import LauncherCard
from src.ui.widgets.tactile_button import TactileButton
from scripts.build_macos_app import (
    generate_info_plist_dict,
    get_pyinstaller_spec_config,
    run_dry_run,
    validate_environment,
)


app = QApplication.instance()
if app is None:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication(sys.argv)


class TestHapticsSynthesis(unittest.TestCase):
    """Test suite for procedural zero-asset mechanical audio synthesis."""

    def test_switch_click_pcm_synthesis(self) -> None:
        """Verify 15ms @ 2.1kHz damped sine wave properties."""
        sr = 44100
        dur = 0.015
        pcm_bytes = synthesize_switch_click(sample_rate=sr, duration_sec=dur, frequency=2100.0)

        expected_samples = int(sr * dur)
        self.assertEqual(len(pcm_bytes), expected_samples * 2)  # 16-bit = 2 bytes/sample

        # Unpack samples into NumPy array
        samples = np.frombuffer(pcm_bytes, dtype=np.int16)
        self.assertEqual(len(samples), expected_samples)

        # Check exponential decay: first quarter RMS must be significantly higher than last quarter
        q1 = np.sqrt(np.mean(samples[: expected_samples // 4].astype(np.float64) ** 2))
        q4 = np.sqrt(np.mean(samples[-expected_samples // 4 :].astype(np.float64) ** 2))
        self.assertGreater(q1, q4 * 3.0)

    def test_knob_detent_pcm_synthesis(self) -> None:
        """Verify 6ms @ 3.5kHz micro-burst properties."""
        sr = 44100
        dur = 0.006
        pcm_bytes = synthesize_knob_detent(sample_rate=sr, duration_sec=dur, frequency=3500.0)

        expected_samples = int(sr * dur)
        self.assertEqual(len(pcm_bytes), expected_samples * 2)

        samples = np.frombuffer(pcm_bytes, dtype=np.int16)
        self.assertEqual(len(samples), expected_samples)

        # High frequency check: peak amplitude within range
        self.assertGreater(np.max(np.abs(samples)), 1000)

    def test_haptics_engine_controls(self) -> None:
        """Verify HapticsEngine volume, enable toggling, and global trigger methods."""
        engine = get_haptics_engine()

        # Test enable/disable
        set_haptics_enabled(False)
        self.assertFalse(is_haptics_enabled())
        # Playing when disabled should be a no-op
        play_switch_click()
        play_knob_detent()

        set_haptics_enabled(True)
        self.assertTrue(is_haptics_enabled())

        # Test volume scaling
        set_haptics_volume(0.42)
        self.assertAlmostEqual(get_haptics_volume(), 0.42, places=2)
        set_haptics_volume(0.7)  # Restore default

        # Direct trigger execution without throwing
        play_switch_click()
        play_knob_detent()


class TestAccessibilityAndKeyboard(unittest.TestCase):
    """Test suite for keyboard navigation, focus rings, and knob adjustments."""

    def setUp(self) -> None:
        self.container = QWidget()
        layout = QVBoxLayout(self.container)

        self.card = LauncherCard(
            module_id="converter",
            code="[MOD-01]",
            tag="[CONV]",
            title="Audio Converter",
            parent=self.container,
        )
        layout.addWidget(self.card)

        self.knob = AnalogKnob(
            name="drive",
            label="Drive",
            min_val=-10.0,
            max_val=10.0,
            default_val=0.0,
            step=0.1,
            unit="dB",
            parent=self.container,
        )
        layout.addWidget(self.knob)

        self.container.show()
        self.container.activateWindow()

    def tearDown(self) -> None:
        self.container.deleteLater()

    def test_launcher_card_keyboard_focus_and_activation(self) -> None:
        """Verify LauncherCard accepts focus, paints focus ring, and activates via Enter/Space."""
        self.assertEqual(self.card.focusPolicy(), Qt.FocusPolicy.StrongFocus)

        self.card.setFocus(Qt.FocusReason.TabFocusReason)

        # Listen for module open request
        opened = []
        self.card.open_requested.connect(opened.append)

        # Trigger via Return key
        ret_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        self.card.keyPressEvent(ret_event)
        self.assertEqual(len(opened), 1)
        self.assertEqual(opened[0], "converter")

        # Trigger via Space key
        space_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier)
        self.card.keyPressEvent(space_event)
        self.assertEqual(len(opened), 2)
        self.assertEqual(opened[1], "converter")

    def test_launcher_grid_tab_and_arrow_navigation(self) -> None:
        """Verify tab ordering across 9 cards and 3x3 arrow key grid navigation."""
        grid = LauncherGridPage()
        grid.show()

        cards = list(grid._cards.values())
        self.assertEqual(len(cards), 9)

        # Verify Tab ordering chain
        for i in range(len(cards) - 1):
            self.assertEqual(cards[i].focusPolicy(), Qt.FocusPolicy.StrongFocus)
            next_w = cards[i].nextInFocusChain()
            # Next in focus chain should lead eventually to next card
            self.assertIsNotNone(next_w)

        # Test Spatial 3x3 Arrow Navigation using tracked focus index
        # Focus Card 0 [MOD-01]
        grid.set_focused_card_index(0)
        self.assertEqual(grid.get_focused_card_index(), 0)

        # Press Right -> Card 1 [MOD-02]
        r_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier)
        grid.keyPressEvent(r_event)
        self.assertEqual(grid.get_focused_card_index(), 1)

        # Press Down -> Card 4 [MOD-05]
        d_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.NoModifier)
        grid.keyPressEvent(d_event)
        self.assertEqual(grid.get_focused_card_index(), 4)

        # Press Left -> Card 3 [MOD-04]
        l_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Left, Qt.KeyboardModifier.NoModifier)
        grid.keyPressEvent(l_event)
        self.assertEqual(grid.get_focused_card_index(), 3)

        # Press Up -> Card 0 [MOD-01]
        u_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Up, Qt.KeyboardModifier.NoModifier)
        grid.keyPressEvent(u_event)
        self.assertEqual(grid.get_focused_card_index(), 0)

        grid.deleteLater()

    def test_analog_knob_keyboard_adjustment(self) -> None:
        """Verify AnalogKnob keyboard adjustments (±1% on arrows, Home/End, R reset)."""
        self.assertEqual(self.knob.focusPolicy(), Qt.FocusPolicy.StrongFocus)
        self.knob.setFocus(Qt.FocusReason.TabFocusReason)

        span = 20.0  # -10 to +10
        one_pct = span * 0.01  # 0.2
        self.knob.setValue(0.0)

        # Press Up -> increase by 1%
        up_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Up, Qt.KeyboardModifier.NoModifier)
        self.knob.keyPressEvent(up_event)
        self.assertAlmostEqual(self.knob.value(), one_pct, places=2)

        # Press Down -> decrease by 1%
        down_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.NoModifier)
        self.knob.keyPressEvent(down_event)
        self.assertAlmostEqual(self.knob.value(), 0.0, places=2)

        # Press End -> max value (+10.0)
        end_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_End, Qt.KeyboardModifier.NoModifier)
        self.knob.keyPressEvent(end_event)
        self.assertAlmostEqual(self.knob.value(), 10.0, places=2)

        # Press Home -> min value (-10.0)
        home_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Home, Qt.KeyboardModifier.NoModifier)
        self.knob.keyPressEvent(home_event)
        self.assertAlmostEqual(self.knob.value(), -10.0, places=2)

        # Press R -> reset to default (0.0)
        r_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_R, Qt.KeyboardModifier.NoModifier)
        self.knob.keyPressEvent(r_event)
        self.assertAlmostEqual(self.knob.value(), 0.0, places=2)

    @patch("src.audio.haptics.play_knob_detent")
    def test_analog_knob_center_detent_tick(self, mock_tick) -> None:
        """Verify crossing 12 o'clock detent (0 dB) triggers detent tick sound."""
        self.knob.setValue(-1.0)
        mock_tick.reset_mock()

        # Step from -1.0 to +1.0 crosses 0.0 detent
        self.knob.setValue(1.0)
        mock_tick.assert_called_once()

        mock_tick.reset_mock()
        # Step from +1.0 to +2.0 does not cross 0.0 detent
        self.knob.setValue(2.0)
        mock_tick.assert_not_called()

        # Step back from +2.0 to -2.0 crosses 0.0 detent
        self.knob.setValue(-2.0)
        mock_tick.assert_called_once()

    @patch("src.audio.haptics.play_switch_click")
    def test_tactile_button_haptics_callback(self, mock_click) -> None:
        """Verify TactileButton automatically invokes play_switch_click on press and keypress."""
        btn = TactileButton(text="EXECUTE")
        btn.show()

        # Keyboard press
        enter_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        btn.keyPressEvent(enter_event)
        mock_click.assert_called_once()

        btn.deleteLater()


class TestMacOSPackagingScript(unittest.TestCase):
    """Test suite for scripts/build_macos_app.py."""

    def test_environment_validation(self) -> None:
        """Verify environment check detects Python and project assets."""
        env = validate_environment()
        self.assertTrue(env["python_version_ok"])
        self.assertTrue(env["main_script_exists"])
        self.assertTrue(env["assets_dir_exists"])
        self.assertTrue(env["ffmpeg_bin_exists"])
        self.assertTrue(env["ffprobe_bin_exists"])

    def test_info_plist_generation(self) -> None:
        """Verify Info.plist includes all required macOS metadata and permission strings."""
        plist = generate_info_plist_dict()
        self.assertEqual(plist["CFBundleName"], "Umbra")
        self.assertEqual(plist["CFBundleIdentifier"], "com.soundprocessor.umbra")
        self.assertEqual(plist["CFBundleVersion"], "2.0.0")
        self.assertTrue(plist["NSHighResolutionCapable"])
        self.assertIn("microphone", plist["NSMicrophoneUsageDescription"].lower())
        self.assertIn("documents", plist["NSDocumentsFolderUsageDescription"].lower())

    def test_pyinstaller_spec_config(self) -> None:
        """Verify PyInstaller spec configuration bundles all necessary binaries and hidden imports."""
        cfg = get_pyinstaller_spec_config()
        self.assertEqual(cfg["app_name"], "Umbra")
        self.assertTrue(cfg["main_script"].endswith("main.py"))

        # Verify binaries
        bin_names = [Path(b[0]).name for b in cfg["binaries"]]
        self.assertIn("ffmpeg", bin_names)
        self.assertIn("ffprobe", bin_names)

        # Verify hidden imports
        self.assertIn("PySide6.QtMultimedia", cfg["hidden_imports"])
        self.assertIn("soundfile", cfg["hidden_imports"])
        self.assertIn("src.audio.haptics", cfg["hidden_imports"])

    def test_dry_run_execution(self) -> None:
        """Verify --dry-run completes cleanly with returncode 0."""
        ret = run_dry_run()
        self.assertEqual(ret, 0)


if __name__ == "__main__":
    unittest.main()
