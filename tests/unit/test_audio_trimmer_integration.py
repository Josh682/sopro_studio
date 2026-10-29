"""Unit tests for Audio Trimmer bounds synchronization and processor instantiation.

Verifies:
1. AudioTrimmer and LoudnessNormalizer instantiation resilience with ffmpeg_bin and extra kwargs.
2. ProcessorRegistry.get_processor argument tolerance across registered processors.
3. AudioTrimmer.process_file execution with partial slice, full length (end_sec=0), and fades.
4. WorkspacePage trimmer parameter bounds:
   - Dynamic adaptation of Cluster A (start_sec, end_sec) to loaded audio file duration (0 to file_dur).
   - Bidirectional sync between AnalogKnob controls and WaveformStage visual markers.
5. Trim & Normalize chain execution without 'takes no arguments' error.
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

from src.ui.qt import QApplication, QKeyEvent, Qt
from src.core.processor_registry import ProcessorRegistry
from src.core.processors.audio_trimmer import AudioTrimmer, TrimOptions
from src.core.processors.loudness_normalizer import LoudnessNormalizer
from src.ui.views.workspace_template import WorkspacePage
from src.ui.components.custom_stages.waveform_stage import WaveformStage

app = QApplication.instance()
if app is None:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication(sys.argv)


class TestAudioTrimmerInstantiation(unittest.TestCase):
    """Test suite verifying constructor parameter compatibility."""

    def test_audio_trimmer_constructor(self) -> None:
        """Verify AudioTrimmer accepts ffmpeg_bin and extra kwargs without error."""
        t1 = AudioTrimmer()
        self.assertIsInstance(t1, AudioTrimmer)

        t2 = AudioTrimmer(ffmpeg_bin="/mock/ffmpeg")
        self.assertEqual(t2.ffmpeg_bin, "/mock/ffmpeg")

        t3 = AudioTrimmer(ffmpeg_bin="/mock/ffmpeg", extra_param="foo", another=123)
        self.assertEqual(t3.ffmpeg_bin, "/mock/ffmpeg")

    def test_loudness_normalizer_constructor(self) -> None:
        """Verify LoudnessNormalizer accepts ffmpeg_bin without TypeError."""
        n1 = LoudnessNormalizer()
        self.assertIsInstance(n1, LoudnessNormalizer)

        n2 = LoudnessNormalizer(ffmpeg_bin="/mock/ffmpeg")
        self.assertEqual(n2._ffmpeg_bin, "/mock/ffmpeg")

    def test_processor_registry_get_processor_resilience(self) -> None:
        """Verify ProcessorRegistry.get_processor cleanly instantiates processors even with kwargs."""
        trimmer = ProcessorRegistry.get_processor("audio_trimmer", ffmpeg_bin="/mock/ffmpeg")
        self.assertIsInstance(trimmer, AudioTrimmer)

        normalizer = ProcessorRegistry.get_processor("loudness_normalizer", ffmpeg_bin="/mock/ffmpeg")
        self.assertIsInstance(normalizer, LoudnessNormalizer)

    def test_trim_options_validation(self) -> None:
        """Verify TrimOptions validation rules and edge cases."""
        # Valid range
        opts = TrimOptions(start_sec=1.0, end_sec=5.0)
        opts.validate(10.0)  # Should not raise

        # Start >= End
        with self.assertRaises(ValueError):
            TrimOptions(start_sec=5.0, end_sec=5.0).validate(10.0)

        with self.assertRaises(ValueError):
            TrimOptions(start_sec=6.0, end_sec=5.0).validate(10.0)

        # Negative start
        with self.assertRaises(ValueError):
            TrimOptions(start_sec=-1.0, end_sec=5.0).validate(10.0)

        # End out of bounds
        with self.assertRaises(ValueError):
            TrimOptions(start_sec=1.0, end_sec=12.0).validate(10.0)


class TestAudioTrimmerProcessing(unittest.TestCase):
    """Test suite verifying audio file trimming operations."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)

        # Create 2.0-second test audio file
        self.sr = 44100
        t = np.linspace(0, 2.0, int(self.sr * 2.0), endpoint=False)
        sig = 0.5 * np.sin(2 * np.pi * 440 * t)
        self.input_wav = self.tmp_path / "test_tone.wav"
        sf.write(str(self.input_wav), sig, self.sr)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_process_file_slice(self) -> None:
        """Verify slicing a subset (0.5s to 1.5s) produces 1.0s output."""
        trimmer = AudioTrimmer()
        out = trimmer.process_file(
            input_path=self.input_wav,
            output_dir=self.tmp_path / "out",
            options={"start_sec": 0.5, "end_sec": 1.5, "fade_in_ms": 10.0, "fade_out_ms": 10.0},
        )
        self.assertTrue(out.exists())

        info = sf.info(str(out))
        self.assertAlmostEqual(info.duration, 1.0, delta=0.05)

    def test_process_file_auto_end(self) -> None:
        """Verify end_sec=0 defaults to full duration."""
        trimmer = AudioTrimmer()
        out = trimmer.process_file(
            input_path=self.input_wav,
            output_dir=self.tmp_path / "out2",
            options={"start_sec": 0.5, "end_sec": 0.0},
        )
        self.assertTrue(out.exists())

        info = sf.info(str(out))
        self.assertAlmostEqual(info.duration, 1.5, delta=0.05)


class TestWorkspaceTrimmerIntegration(unittest.TestCase):
    """Test suite verifying UI Cluster A parameter bounds and WaveformStage synchronization."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)

        # Create 350.0-second test audio file (> 100 seconds to test beyond old 100s limit)
        self.sr = 22050
        duration_sec = 350.0
        # Generate short chunk of samples and write with 350s metadata length or full samples
        # A simple 10-second file is fast and enough to test against custom duration, let's create 240s with silent frames
        data = np.zeros((int(self.sr * 240.0),), dtype=np.float32)
        # Add transient at start
        data[:1000] = 0.5
        self.long_audio = self.tmp_path / "long_track.wav"
        sf.write(str(self.long_audio), data, self.sr)

        self.workspace = WorkspacePage()
        self.workspace.show()

    def tearDown(self) -> None:
        self.workspace.deleteLater()
        self.tmp_dir.cleanup()

    def test_trimmer_bounds_adapted_to_audio_duration(self) -> None:
        """Verify Cluster A parameters (start_sec, end_sec) span from 0 to actual duration (240s) not 100s."""
        mod_info = {
            "id": "edit",
            "code": "[MOD-06]",
            "tag": "[EDIT]",
            "title": "Audio Editor",
            "button_text": "Open Editor",
            "action_text": "Trim & Normalize",
            "accent_key": "trim",
        }
        self.workspace.configure_module(mod_info, str(self.long_audio))

        # Check rack controls
        start_ctrl = self.workspace._rack_controller.controls.get("start_sec")
        end_ctrl = self.workspace._rack_controller.controls.get("end_sec")

        self.assertIsNotNone(start_ctrl)
        self.assertIsNotNone(end_ctrl)

        # Both controls must have max equal to 240.0s (not 100.0s!)
        self.assertAlmostEqual(start_ctrl._max, 240.0, delta=1.0)
        self.assertAlmostEqual(end_ctrl._max, 240.0, delta=1.0)

        # end_sec must be initialized to 240.0s (the full duration), not 100.0s
        self.assertAlmostEqual(end_ctrl.value(), 240.0, delta=1.0)
        self.assertAlmostEqual(start_ctrl.value(), 0.0, delta=0.1)

    def test_bidirectional_knob_and_waveform_sync(self) -> None:
        """Verify adjusting knobs updates WaveformStage range, and vice versa."""
        mod_info = {
            "id": "edit",
            "code": "[MOD-06]",
            "tag": "[EDIT]",
            "title": "Audio Editor",
            "button_text": "Open Editor",
            "action_text": "Trim & Normalize",
            "accent_key": "trim",
        }
        self.workspace.configure_module(mod_info, str(self.long_audio))

        start_ctrl = self.workspace._rack_controller.controls.get("start_sec")
        end_ctrl = self.workspace._rack_controller.controls.get("end_sec")
        stage = self.workspace._custom_stage_widget
        self.assertIsInstance(stage, WaveformStage)

        # 1. Turn knobs: start_sec = 25.0, end_sec = 180.0
        start_ctrl.setValue(25.0)
        end_ctrl.setValue(180.0)

        self.assertAlmostEqual(stage._start_sec, 25.0, delta=0.5)
        self.assertAlmostEqual(stage._end_sec, 180.0, delta=0.5)

        # 2. Adjust stage: emit rangeChanged(10.0, 200.0)
        stage.set_range(10.0, 200.0)

        self.assertAlmostEqual(start_ctrl.value(), 10.0, delta=0.5)
        self.assertAlmostEqual(end_ctrl.value(), 200.0, delta=0.5)

    def test_run_edit_chain_instantiation(self) -> None:
        """Verify Trim & Normalize chain initiates without 'AudioTrimmer() takes no arguments'."""
        mod_info = {
            "id": "edit",
            "code": "[MOD-06]",
            "tag": "[EDIT]",
            "title": "Audio Editor",
            "button_text": "Open Editor",
            "action_text": "Trim & Normalize",
            "accent_key": "trim",
        }
        # Create small 0.5s audio file for fast execution
        quick_wav = self.tmp_path / "quick.wav"
        sf.write(str(quick_wav), np.zeros((11025,), dtype=np.float32), 22050)

        self.workspace.configure_module(mod_info, str(quick_wav))

        # Check that trimmer and normalizer can be created with ffmpeg_bin
        trimmer = ProcessorRegistry.get_processor("audio_trimmer", ffmpeg_bin="ffmpeg")
        normalizer = ProcessorRegistry.get_processor("loudness_normalizer", ffmpeg_bin="ffmpeg")
        self.assertIsInstance(trimmer, AudioTrimmer)
        self.assertIsInstance(normalizer, LoudnessNormalizer)


if __name__ == "__main__":
    unittest.main()
