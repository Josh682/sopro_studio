"""Unit Tests for Milestone 2: Real-time Ballistic Analog VU Metering & Live RMS Deflection."""

from __future__ import annotations

import math
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Headless platform for Qt
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from src.ui.qt import (
    QApplication,
    QPaintEvent,
    QRect,
)

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

import numpy as np
import soundfile as sf

from src.audio.metering import AudioMeterEngine, BallisticNeedle
from src.ui.components.custom_stages.analysis_stage import AnalysisStage
from src.ui.views.workspace_template import WorkspacePage
from src.ui.widgets.analog_controls import CircularVUMeter, LEDMeterLadder
from src.ui.widgets.module_rack_canvas import ModuleRackCanvas


class TestBallisticMetering(unittest.TestCase):
    """Test suite for Milestone 2 audio metering, needle ballistics, and analog widgets."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.test_wav = Path(cls.temp_dir.name) / "test_stereo_tone.wav"

        # Generate a 2.0s 44.1kHz stereo test tone:
        # Left channel: 0 dBFS peak (sine amp=1.0, RMS = 1/sqrt(2) ~ -3.01 dBFS)
        # Right channel: -18 dBFS RMS tone (sine amp=sqrt(2)*10^(-18/20) ~ 0.1774)
        sr = 44100
        dur = 2.0
        t = np.linspace(0, dur, int(sr * dur), endpoint=False)
        amp_r = math.sqrt(2) * (10.0 ** (-18.0 / 20.0))
        left = 1.0 * np.sin(2 * np.pi * 1000.0 * t)
        right = amp_r * np.sin(2 * np.pi * 1000.0 * t)
        stereo = np.column_stack((left, right)).astype(np.float32)
        sf.write(str(cls.test_wav), stereo, sr)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp_dir.cleanup()

    # -------------------------------------------------------------------------
    # 1. Physical Galvanometer Needle Ballistics
    # -------------------------------------------------------------------------

    def test_ballistic_needle_resting_and_clamping(self) -> None:
        """Verify needle starts at resting peg (-40 deg) and stays within mechanical stops."""
        needle = BallisticNeedle(stiffness=0.20, damping=0.70)
        self.assertEqual(needle.angle, -40.0)
        self.assertEqual(needle.velocity, 0.0)

        # Silent signal stays clamped at resting peg
        angle = needle.update(-80.0)
        self.assertEqual(angle, -40.0)

        # Excessive input level is clamped to maximum limit (+42.0 deg)
        for _ in range(50):
            needle.update(+20.0)
        self.assertLessEqual(needle.angle, 42.0)
        self.assertGreaterEqual(needle.angle, 39.0)

        # Reset returns to resting position
        needle.reset()
        self.assertEqual(needle.angle, -40.0)
        self.assertEqual(needle.velocity, 0.0)

    def test_ballistic_needle_step_response_and_overshoot(self) -> None:
        """Verify dynamic overshoot and settling of the 2nd-order spring-damper system."""
        needle = BallisticNeedle(stiffness=0.20, damping=0.70)

        # Step input: -18 dBFS (0 VU mark -> target = +29.56 deg)
        angles = []
        for _ in range(40):
            a = needle.update(-18.0)
            angles.append(a)

        # Needle must move upwards from -40 deg towards +29.56 deg
        self.assertGreater(angles[10], 0.0)

        # Overshoot test: max angle during transient should exceed settled target
        max_angle = max(angles)
        settled_angle = angles[-1]
        self.assertAlmostEqual(settled_angle, 29.56, delta=1.5)
        self.assertGreater(max_angle, settled_angle)  # Realistic mechanical overshoot!

    # -------------------------------------------------------------------------
    # 2. AudioMeterEngine DSP Calculations
    # -------------------------------------------------------------------------

    def test_meter_engine_load_and_rms_calculation(self) -> None:
        """Verify accurate RMS and True Peak computation over 50ms audio chunk."""
        engine = AudioMeterEngine()
        loaded = engine.load_file(self.test_wav)
        self.assertTrue(loaded)
        self.assertEqual(engine._sample_rate, 44100)
        self.assertAlmostEqual(engine._duration_sec, 2.0, delta=0.01)

        # Listen to emitted signals
        levels_captured = []
        engine.levelsUpdated.connect(lambda l, r, pl, pr: levels_captured.append((l, r, pl, pr)))

        # Process playhead at 1.0 second (steady tone)
        rms_l, rms_r, peak_l, peak_r = engine.process_playhead(1.0, window_ms=50.0)

        # Left channel: 0 dBFS peak -> RMS should be approx -3.0 dBFS
        self.assertAlmostEqual(rms_l, -3.01, delta=0.5)
        self.assertAlmostEqual(peak_l, 0.0, delta=0.1)

        # Right channel: calibrated -18.0 dBFS RMS
        self.assertAlmostEqual(rms_r, -18.0, delta=0.5)

        # Verify signal was emitted
        self.assertTrue(len(levels_captured) > 0)
        self.assertAlmostEqual(levels_captured[-1][0], rms_l, delta=0.01)

    def test_meter_engine_clipping_detection(self) -> None:
        """Verify True Peak clipping flag is triggered when peak > -0.1 dBFS."""
        engine = AudioMeterEngine()
        engine.load_file(self.test_wav)

        clips_captured = []
        engine.clipDetected.connect(lambda cl, cr: clips_captured.append((cl, cr)))

        # At 1.0s, left channel is 0 dBFS peak (> -0.1 dBFS) -> clip_l must be True
        engine.process_playhead(1.0)
        self.assertTrue(len(clips_captured) > 0)
        clip_l, clip_r = clips_captured[-1]
        self.assertTrue(clip_l)
        self.assertFalse(clip_r)

    # -------------------------------------------------------------------------
    # 3. Circular Analog VU Meter Widget
    # -------------------------------------------------------------------------

    def test_circular_vu_meter_widget_single_and_dual(self) -> None:
        """Verify CircularVUMeter single/dual layout and offscreen rendering."""
        # Single meter
        meter_single = CircularVUMeter(is_dual=False, diameter=110, title="VU")
        self.assertEqual(meter_single.width(), 110)
        self.assertEqual(meter_single.height(), 110)

        meter_single.set_level(-18.0)
        self.assertGreater(meter_single._needle_deg_l, -40.0)

        meter_single.set_clipped(True)
        self.assertTrue(meter_single._clipped_l)

        # Trigger paint event (offscreen render check)
        meter_single.repaint()

        # Dual meter
        meter_dual = CircularVUMeter(is_dual=True, diameter=82, title="DUAL")
        self.assertEqual(meter_dual.width(), 82 * 2 + 12)
        self.assertEqual(meter_dual.height(), 82)

        meter_dual.set_levels(-10.0, -18.0)
        meter_dual.repaint()

        # Reset
        meter_dual.reset()
        self.assertEqual(meter_dual._needle_deg_l, -40.0)
        self.assertEqual(meter_dual._needle_deg_r, -40.0)

    # -------------------------------------------------------------------------
    # 4. LED Meter Ladder Widget
    # -------------------------------------------------------------------------

    def test_led_meter_ladder_segments_and_peak_hold(self) -> None:
        """Verify 12-segment threshold illumination and peak hold behavior."""
        ladder = LEDMeterLadder(width=14, height=96)
        self.assertEqual(ladder.width(), 14)
        self.assertEqual(ladder.height(), 96)

        # Silence: 0 segments lit
        ladder.set_level(-80.0)
        self.assertEqual(ladder._active_segments, 0)

        # Normal operating level (-18 dBFS): 5 green segments lit
        ladder.set_level(-18.0)
        self.assertEqual(ladder._active_segments, 5)

        # High level (-3 dBFS): 10 segments lit (8 green + 2 amber)
        ladder.set_level(-3.0)
        self.assertEqual(ladder._active_segments, 10)
        self.assertEqual(ladder._peak_hold_idx, 10)

        # Level drops down: peak hold retains index 10
        ladder.set_level(-24.0)
        self.assertEqual(ladder._active_segments, 4)
        self.assertEqual(ladder._peak_hold_idx, 10)

        # Offscreen paint execution
        ladder.repaint()

        ladder.reset()
        self.assertEqual(ladder._active_segments, 0)

    # -------------------------------------------------------------------------
    # 5. AnalysisStage Custom Visual Deck Integration
    # -------------------------------------------------------------------------

    def test_analysis_stage_integration(self) -> None:
        """Verify AnalysisStage incorporates dual circular VU meters and displays live results."""
        stage = AnalysisStage()
        stage.resize(600, 170)

        # Verify child meters presence
        self.assertTrue(hasattr(stage, "meter_l"))
        self.assertTrue(hasattr(stage, "meter_r"))
        self.assertIsInstance(stage.meter_l, CircularVUMeter)
        self.assertIsInstance(stage.meter_r, CircularVUMeter)

        # Step live audio levels
        stage.set_levels(-6.0, -18.0)
        self.assertGreater(stage.meter_l._needle_deg_l, stage.meter_r._needle_deg_l)

        # Update harmonic results
        stage.set_results(key_str="C Major", camelot_str="8B", bpm=128.0, confidence=0.98)
        self.assertEqual(stage.lbl_camelot.text(), "8B")
        self.assertEqual(stage.lbl_key.text(), "C MAJOR")
        self.assertEqual(stage.lbl_bpm.text(), "128.0 BPM")

        stage.repaint()

    # -------------------------------------------------------------------------
    # 6. WorkspacePage Meter Wiring
    # -------------------------------------------------------------------------

    def test_workspace_meter_wiring(self) -> None:
        """Verify WorkspacePage wires AudioMeterEngine to transport bar readout."""
        ws = WorkspacePage()
        ws.resize(1152, 768)

        # Verify metering engine and transport header elements
        self.assertTrue(hasattr(ws, "_meter_engine"))
        self.assertTrue(hasattr(ws, "lbl_meter_level"))
        self.assertTrue(hasattr(ws, "lbl_peak_led"))

        # Configure module and load test audio
        mod_info = {
            "id": "analyze",
            "title": "Key & Tempo Detector",
            "code": "[MOD-04]",
            "accent_key": "detect",
            "action_text": "Detect Key & BPM",
        }
        ws.configure_module(mod_info, file_path=str(self.test_wav))

        # Initial resting state
        self.assertEqual(ws.lbl_meter_level.text(), "-∞ dB")

        # Step playhead at 1.0s (active tone)
        ws._on_player_position_changed(1.0)

        # Meter label should update from -∞ dB to actual decibels
        self.assertNotEqual(ws.lbl_meter_level.text(), "-∞ dB")
        self.assertIn("dB", ws.lbl_meter_level.text())

        # Reset cleans up
        ws.reset_file_and_params()
        self.assertEqual(ws.lbl_meter_level.text(), "-∞ dB")


if __name__ == "__main__":
    unittest.main()
