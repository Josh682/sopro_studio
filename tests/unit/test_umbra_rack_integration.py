"""Comprehensive Unit Tests for Umbra Hardware Rack Integration (Candidate 2).

Tests cover:
1. Analog interactive widgets: AnalogKnob, AnalogToggle, AnalogChoiceSelector, AnalogFader.
2. DynamicRackController factory: Descriptor partitioning into Cluster A, B, C, parameter query and defaults reset.
3. Slot 2 Custom Stage creation and interaction (WaveformStage, AnalysisStage, StemDeckStage).
4. WorkspacePage module configuration and dynamic rack binding.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import unittest

# Ensure QApplication is initialized before creating any QWidget
from src.ui.qt import QApplication

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

from src.core.processors.audio_trimmer import AudioTrimmer
from src.core.processors.format_converter import FormatConverter
from src.core.processors.pitch_shifter import PitchShifter
from src.core.processors.tempo_changer import TempoChanger
from src.ui.components.custom_stages import (
    AnalysisStage,
    StemDeckStage,
    WaveformStage,
    create_custom_stage,
)
from src.ui.components.rack_control_factory import DynamicRackController
from src.ui.views.workspace_template import MODULE_TO_PROCESSOR_ID, WorkspacePage
from src.ui.widgets.analog_controls import (
    AnalogChoiceSelector,
    AnalogFader,
    AnalogKnob,
    AnalogToggle,
)


class TestAnalogWidgets(unittest.TestCase):
    """Test skeuomorphic interactive analog controls."""

    def test_analog_knob(self) -> None:
        knob = AnalogKnob(
            name="cutoff_freq",
            label="Cutoff",
            min_val=20.0,
            max_val=20000.0,
            default_val=1000.0,
            step=10.0,
            unit="Hz",
        )
        self.assertEqual(knob.value(), 1000.0)

        # Signal emission test
        emitted_vals = []
        knob.valueChanged.connect(emitted_vals.append)

        knob.setValue(5000.0)
        self.assertEqual(knob.value(), 5000.0)
        self.assertEqual(emitted_vals, [5000.0])

        # Clamping test
        knob.setValue(30000.0)
        self.assertEqual(knob.value(), 20000.0)

        knob.setValue(5.0)
        self.assertEqual(knob.value(), 20.0)

    def test_analog_toggle(self) -> None:
        toggle = AnalogToggle(
            name="normalize",
            label="Peak Norm",
            default_state=False,
        )
        self.assertFalse(toggle.isChecked())

        emitted_states = []
        toggle.toggled.connect(emitted_states.append)

        toggle.setChecked(True)
        self.assertTrue(toggle.isChecked())
        self.assertEqual(emitted_states, [True])

        toggle.setChecked(False)
        self.assertFalse(toggle.isChecked())
        self.assertEqual(emitted_states, [True, False])

    def test_analog_choice_selector(self) -> None:
        selector = AnalogChoiceSelector(
            name="output_format",
            choices=["wav", "mp3", "flac"],
            label="Format",
            default_choice="wav",
        )
        self.assertEqual(selector.currentChoice(), "wav")

        emitted_choices = []
        selector.currentChoiceChanged.connect(emitted_choices.append)

        selector.setCurrentChoice("flac")
        self.assertEqual(selector.currentChoice(), "flac")
        self.assertEqual(emitted_choices, ["flac"])

        # Invalid choice should be ignored
        selector.setCurrentChoice("invalid_format")
        self.assertEqual(selector.currentChoice(), "flac")

    def test_analog_fader(self) -> None:
        fader = AnalogFader(
            name="master_gain",
            label="Gain",
            min_val=-60.0,
            max_val=12.0,
            default_val=0.0,
            step=0.5,
            unit="dB",
        )
        self.assertEqual(fader.value(), 0.0)

        emitted_fader = []
        fader.valueChanged.connect(emitted_fader.append)

        fader.setValue(-12.0)
        self.assertEqual(fader.value(), -12.0)
        self.assertEqual(emitted_fader, [-12.0])

        # Clamping
        fader.setValue(20.0)
        self.assertEqual(fader.value(), 12.0)
        fader.setValue(-100.0)
        self.assertEqual(fader.value(), -60.0)


class TestRackControlFactory(unittest.TestCase):
    """Test dynamic rack creation and parameter harvesting."""

    def setUp(self) -> None:
        self.controller = DynamicRackController()

    def test_build_format_converter_rack(self) -> None:
        descs = FormatConverter.get_parameter_descriptors()
        panel_a, panel_b, panel_c = self.controller.build_clusters(descs, accent_color="#3B82F6")

        self.assertIsNotNone(panel_a)
        self.assertIsNotNone(panel_b)
        self.assertIsNotNone(panel_c)

        # Verify all parameter names are bound
        param_names = [d.name for d in descs]
        for name in param_names:
            self.assertIn(name, self.controller.controls)

        # Verify default parameters dictionary query
        params = self.controller.get_parameters()
        self.assertIn("output_format", params)
        self.assertEqual(params["output_format"], "wav")
        self.assertIn("normalize", params)
        self.assertFalse(params["normalize"])

        # Change control and test get_parameters reflection
        format_widget = self.controller.controls["output_format"]
        self.assertIsInstance(format_widget, AnalogChoiceSelector)
        format_widget.setCurrentChoice("flac")

        updated_params = self.controller.get_parameters()
        self.assertEqual(updated_params["output_format"], "flac")

        # Test reset to defaults
        self.controller.reset_to_defaults()
        reset_params = self.controller.get_parameters()
        self.assertEqual(reset_params["output_format"], "wav")

    def test_build_trimmer_rack(self) -> None:
        descs = AudioTrimmer.get_parameter_descriptors()
        self.assertEqual(len(descs), 4)

        panel_a, panel_b, panel_c = self.controller.build_clusters(descs, accent_color="#F59E0B")
        self.assertIn("start_sec", self.controller.controls)
        self.assertIn("end_sec", self.controller.controls)
        self.assertIn("fade_in_ms", self.controller.controls)
        self.assertIn("fade_out_ms", self.controller.controls)

        params = self.controller.get_parameters()
        self.assertEqual(params["start_sec"], 0.0)
        self.assertEqual(params["end_sec"], 0.0)

    def test_build_tempo_changer_rack(self) -> None:
        descs = TempoChanger.get_parameter_descriptors()
        panel_a, panel_b, panel_c = self.controller.build_clusters(descs, accent_color="#10B981")
        self.assertIn("mode", self.controller.controls)
        self.assertIn("target_bpm", self.controller.controls)

        params = self.controller.get_parameters()
        self.assertEqual(params["mode"], "bpm")
        self.assertEqual(params["target_bpm"], 120.0)


class TestCustomStages(unittest.TestCase):
    """Test Slot 2 visual stage creation and behavior."""

    def test_stage_factory(self) -> None:
        trimmer_stage = create_custom_stage("trimmer")
        self.assertIsInstance(trimmer_stage, WaveformStage)

        key_stage = create_custom_stage("key_detector")
        self.assertIsInstance(key_stage, AnalysisStage)

        separator_stage = create_custom_stage("separator")
        self.assertIsInstance(separator_stage, StemDeckStage)

        # Converter has no custom analytical stage, returns None
        converter_stage = create_custom_stage("converter")
        self.assertIsNone(converter_stage)

    def test_waveform_stage_range(self) -> None:
        stage = WaveformStage()
        ranges = []
        stage.rangeChanged.connect(lambda s, e: ranges.append((s, e)))

        stage.set_range(5.0, 25.0)
        self.assertEqual(ranges, [(5.0, 25.0)])

    def test_analysis_stage_results(self) -> None:
        stage = AnalysisStage()
        stage.set_results("C Major", "8B", 128.0, 0.99)
        self.assertEqual(stage._key_result, "C MAJOR")
        self.assertEqual(stage._camelot, "8B")
        self.assertEqual(stage._bpm_result, 128.0)


class TestWorkspacePageIntegration(unittest.TestCase):
    """Test full integration in WorkspacePage."""

    def test_configure_module_flow(self) -> None:
        page = WorkspacePage()

        # 1. Configure Format Converter
        mod_converter = {
            "id": "converter",
            "title": "Audio Format Converter",
            "code": "[MOD-01]",
            "accent_key": "converter",
            "action_text": "CONVERT BATCH",
        }
        page.configure_module(mod_converter)

        self.assertEqual(page._current_module_id, "converter")
        self.assertEqual(page.lbl_module_header.text(), "[MOD-01]  AUDIO FORMAT CONVERTER")
        self.assertEqual(page.btn_action_cta.text(), "CONVERT BATCH")
        self.assertIn("output_format", page._rack_controller.controls)

        # 2. Configure Trimmer
        mod_trimmer = {
            "id": "trimmer",
            "title": "Precision Audio Trimmer",
            "code": "[MOD-04]",
            "accent_key": "trimmer",
            "action_text": "TRIM REGION",
        }
        page.configure_module(mod_trimmer)

        self.assertEqual(page._current_module_id, "trimmer")
        self.assertIsInstance(page._custom_stage_widget, WaveformStage)
        self.assertIn("start_sec", page._rack_controller.controls)
        self.assertIn("fade_in_ms", page._rack_controller.controls)

        # 3. Test Waveform Range Sync with Rack Controls
        page._on_waveform_range_changed(2.5, 14.8)
        self.assertEqual(page._rack_controller.controls["start_sec"].value(), 2.5)
        self.assertEqual(page._rack_controller.controls["end_sec"].value(), 14.8)

        # 4. Test Reset
        page.reset_file_and_params()
        self.assertIsNone(page._current_file)
        self.assertEqual(page.deck_stack.currentIndex(), 0)
        self.assertEqual(page._rack_controller.controls["start_sec"].value(), 0.0)


if __name__ == "__main__":
    unittest.main()
