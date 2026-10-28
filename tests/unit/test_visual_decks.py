"""Unit tests for Milestone 3: Interactive Visual Decks & Stem Player.

Tests:
1. StemDeckStage (Interactive Stem Mixer, Solo/Mute matrix, mini faders, LED ladders).
2. WaveformStage (Dual-buffer A/B comparison, ghosted overlay, playhead scrubbing).
3. AnalysisStage (24-cell Camelot Harmonic Matrix, Circle of Fifths compatibility algorithm).
4. AudioPlayerController (Seamless A/B source swapping, multi-stem playback and mixing).
"""

from __future__ import annotations

import math
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Set headless Qt platform before any Qt modules load
os.environ["QT_QPA_PLATFORM"] = "offscreen"

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from src.ui.qt import QApplication

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

import numpy as np
import soundfile as sf

from src.audio.player import AudioPlayerController
from src.audio.metering import AudioMeterEngine
from src.ui.components.custom_stages.stem_deck_stage import (
    StemDeckStage,
    StemChannelStrip,
    db_to_linear,
    slider_to_db,
)
from src.ui.components.custom_stages.waveform_stage import WaveformStage
from src.ui.components.custom_stages.analysis_stage import (
    AnalysisStage,
    CamelotMatrixWidget,
    get_compatible_camelot_keys,
    describe_harmonic_relation,
    CAMELOT_KEY_NAMES,
)


class TestVisualDecks(unittest.TestCase):
    """Test suite for Milestone 3 Interactive Visual Decks."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp_dir = Path(tempfile.mkdtemp(prefix="test_visual_decks_")).resolve()

        # Generate a test audio file
        cls.test_wav_a = (cls.tmp_dir / "track_a.wav").resolve()
        cls.test_wav_b = (cls.tmp_dir / "track_b.wav").resolve()

        sr = 44100
        dur = 2.0
        t = np.linspace(0, dur, int(sr * dur), endpoint=False)
        tone_a = (np.sin(2 * np.pi * 440 * t) * 0.5).astype(np.float32)
        tone_b = (np.sin(2 * np.pi * 880 * t) * 0.3).astype(np.float32)

        sf.write(str(cls.test_wav_a), np.column_stack((tone_a, tone_a)), sr)
        sf.write(str(cls.test_wav_b), np.column_stack((tone_b, tone_b)), sr)

        # Generate 4 stem files
        cls.stems = {}
        for stem_name, freq in [("vocals", 500), ("drums", 150), ("bass", 80), ("other", 1000)]:
            p = cls.tmp_dir / f"stem_{stem_name}.wav"
            stem_tone = (np.sin(2 * np.pi * freq * t) * 0.4).astype(np.float32)
            sf.write(str(p), np.column_stack((stem_tone, stem_tone)), sr)
            cls.stems[stem_name] = p

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.tmp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # 1. StemDeckStage & StemChannelStrip Tests
    # -------------------------------------------------------------------------

    def test_slider_and_db_conversions(self) -> None:
        """Test fader slider position to dB and linear gain conversion formulas."""
        self.assertEqual(slider_to_db(0), -80.0)
        self.assertEqual(db_to_linear(-80.0), 0.0)

        # Unity gain: slider=80 -> 0.0 dB -> gain 1.0
        self.assertAlmostEqual(slider_to_db(80), 0.0, places=4)
        self.assertAlmostEqual(db_to_linear(0.0), 1.0, places=4)

        # Max boost: slider=100 -> +6.0 dB -> gain ~1.995
        self.assertAlmostEqual(slider_to_db(100), 6.0, places=4)
        self.assertAlmostEqual(db_to_linear(6.0), 1.99526, places=3)

    def test_stem_channel_strip_solo_mute(self) -> None:
        """Test StemChannelStrip solo and mute button signals and visual state."""
        strip = StemChannelStrip(stem_name="VOCALS", accent_color="#EC4899")

        solo_events = []
        mute_events = []
        fader_events = []

        strip.soloToggled.connect(lambda name, val: solo_events.append((name, val)))
        strip.muteToggled.connect(lambda name, val: mute_events.append((name, val)))
        strip.faderChanged.connect(lambda name, val: fader_events.append((name, val)))

        # Toggle Solo
        strip.btn_solo.click()
        self.assertEqual(solo_events, [("vocals", True)])
        self.assertEqual(strip.lbl_status.text(), "SOLO")

        # Toggle Mute
        strip.btn_mute.click()
        self.assertEqual(mute_events, [("vocals", True)])
        self.assertEqual(strip.lbl_status.text(), "MUTED")

        # Adjust fader
        strip.slider.setValue(40)  # -30 dB
        self.assertEqual(len(fader_events), 1)
        self.assertEqual(fader_events[0][0], "vocals")
        self.assertAlmostEqual(fader_events[0][1], db_to_linear(-30.0), places=3)

    def test_stem_deck_stage_loading(self) -> None:
        """Test loading stem files into StemDeckStage."""
        deck = StemDeckStage()
        deck.load_stems(self.stems)

        for name in ["vocals", "drums", "bass", "other"]:
            strip = deck._stem_strips[name]
            self.assertEqual(strip.lbl_status.text(), "READY")

        # Test setting levels
        deck.set_stem_levels({"vocals": -12.0, "drums": -6.0, "bass": -18.0, "other": -24.0})
        self.assertAlmostEqual(deck._stem_strips["vocals"].led_ladder._level_db, -12.0)
        self.assertAlmostEqual(deck._stem_strips["drums"].led_ladder._level_db, -6.0)

    # -------------------------------------------------------------------------
    # 2. WaveformStage A/B Comparison Tests
    # -------------------------------------------------------------------------

    def test_waveform_stage_ab_loading_and_toggle(self) -> None:
        """Test dual-buffer loading and A/B comparison switching in WaveformStage."""
        stage = WaveformStage(accent_color="#F59E0B")

        # Initially no samples
        self.assertIsNone(stage._samples)
        self.assertTrue(stage.btn_ab_container.isHidden())

        # Load Buffer A
        stage.load_audio_preview(str(self.test_wav_a))
        self.assertIsNotNone(stage._samples_a)
        self.assertAlmostEqual(stage._duration, 2.0, places=1)
        self.assertEqual(stage.active_ab, "A")
        self.assertTrue(stage.btn_ab_container.isHidden())

        # Load Buffer B (Processed)
        stage.load_processed_preview(str(self.test_wav_b))
        self.assertIsNotNone(stage._samples_b)
        self.assertFalse(stage.btn_ab_container.isHidden())
        self.assertEqual(stage.active_ab, "B")

        # Toggle to A
        ab_events = []
        stage.abToggled.connect(lambda mode: ab_events.append(mode))
        stage.btn_a.click()

        self.assertEqual(stage.active_ab, "A")
        self.assertEqual(ab_events, ["A"])

    # -------------------------------------------------------------------------
    # 3. AnalysisStage & Camelot Harmonic Matrix Tests
    # -------------------------------------------------------------------------

    def test_camelot_compatibility_rules(self) -> None:
        """Test Camelot harmonic wheel compatibility calculations."""
        # 8A (A Minor): compatible keys are 8A (exact), 7A (-1 step), 9A (+1 step), 8B (relative major)
        compat_8a = get_compatible_camelot_keys("8A")
        self.assertEqual(compat_8a, {"8A", "7A", "9A", "8B"})

        # 1A (G# Minor): wraps around 12A (-1 step) and 2A (+1 step), and 1B
        compat_1a = get_compatible_camelot_keys("1A")
        self.assertEqual(compat_1a, {"1A", "12A", "2A", "1B"})

        # 12B (E Major): wraps around 11B (-1 step), 1B (+1 step), and 12A
        compat_12b = get_compatible_camelot_keys("12B")
        self.assertEqual(compat_12b, {"12B", "11B", "1B", "12A"})

        # Relationship descriptions
        desc_self = describe_harmonic_relation("8A", "8A")
        self.assertIn("ROOT DETECTED KEY", desc_self)

        desc_rel = describe_harmonic_relation("8B", "8A")
        self.assertIn("RELATIVE MAJOR", desc_rel)

        desc_up = describe_harmonic_relation("9A", "8A")
        self.assertIn("+1 ENERGY LIFT", desc_up)

        desc_down = describe_harmonic_relation("7A", "8A")
        self.assertIn("-1 ENERGY DROP", desc_down)

    def test_camelot_matrix_widget(self) -> None:
        """Test CamelotMatrixWidget buttons, detected key, and click signals."""
        matrix = CamelotMatrixWidget()
        self.assertEqual(len(matrix._buttons), 24)

        selected_events = []
        matrix.cellSelected.connect(lambda code, desc: selected_events.append((code, desc)))

        matrix.set_detected_key("4A")
        self.assertEqual(matrix._detected_key, "4A")
        self.assertEqual(matrix._compatible_keys, {"4A", "3A", "5A", "4B"})

        # Click on relative major 4B
        matrix._buttons["4B"].click()
        self.assertEqual(len(selected_events), 1)
        self.assertEqual(selected_events[0][0], "4B")
        self.assertIn("RELATIVE MAJOR", selected_events[0][1])

    def test_analysis_stage_results_update(self) -> None:
        """Test AnalysisStage set_results updates key, BPM, and Camelot wheel."""
        stage = AnalysisStage()
        stage.set_results(key_str="C Minor", camelot_str="5A", bpm=128.0, confidence=0.98)

        self.assertEqual(stage.lbl_camelot.text(), "5A")
        self.assertEqual(stage.lbl_key.text(), "C MINOR")
        self.assertEqual(stage.lbl_bpm.text(), "128.0 BPM")
        self.assertEqual(stage.lbl_confidence.text(), "LOCK 98%")
        self.assertEqual(stage.camelot_matrix._detected_key, "5A")

    # -------------------------------------------------------------------------
    # 4. AudioPlayerController Extensions (A/B & Stems)
    # -------------------------------------------------------------------------

    def test_player_ab_source_swap(self) -> None:
        """Test seamless source swapping with playhead position preservation."""
        player = AudioPlayerController()
        ok = player.load_ab(self.test_wav_a, self.test_wav_b)
        self.assertTrue(ok)
        self.assertEqual(player.active_ab, "A")
        self.assertEqual(player.current_file, self.test_wav_a)

        # Seek to 1.25s
        player.seek(1.25)
        self.assertAlmostEqual(player.position, 1.25, places=2)

        # Switch to B
        swapped = player.set_ab_mode("B")
        self.assertTrue(swapped)
        self.assertEqual(player.active_ab, "B")
        self.assertEqual(player.current_file, self.test_wav_b)
        self.assertAlmostEqual(player.position, 1.25, places=2)

        player.stop()

    def test_player_multi_stem_mixing(self) -> None:
        """Test multi-stem loading, solo/mute gating logic, and fader volume."""
        player = AudioPlayerController()
        ok = player.load_stems(self.stems)
        self.assertTrue(ok)
        self.assertTrue(player.is_stem_mode)
        self.assertEqual(len(player._stem_players), 4)

        # Initial state: all unity gain, unmuted, unsoloed
        gains = player.get_stem_gains()
        for stem in ["vocals", "drums", "bass", "other"]:
            self.assertAlmostEqual(gains[stem], 1.0)

        # Mute Drums
        player.set_stem_mute("drums", True)
        gains = player.get_stem_gains()
        self.assertAlmostEqual(gains["drums"], 0.0)
        self.assertAlmostEqual(gains["vocals"], 1.0)

        # Solo Vocals -> only Vocals audible, even unmuted stems are silenced
        player.set_stem_solo("vocals", True)
        gains = player.get_stem_gains()
        self.assertAlmostEqual(gains["vocals"], 1.0)
        self.assertAlmostEqual(gains["bass"], 0.0)
        self.assertAlmostEqual(gains["drums"], 0.0)
        self.assertAlmostEqual(gains["other"], 0.0)

        # Adjust fader of Vocals to 1.5 (+3.5 dB)
        player.set_stem_fader("vocals", 1.5)
        gains = player.get_stem_gains()
        self.assertAlmostEqual(gains["vocals"], 1.5)

        # Unsolo
        player.set_stem_solo("vocals", False)
        gains = player.get_stem_gains()
        self.assertAlmostEqual(gains["vocals"], 1.5)
        self.assertAlmostEqual(gains["bass"], 1.0)
        self.assertAlmostEqual(gains["drums"], 0.0)  # still muted

        player.stop()

    def test_meter_engine_multi_stem(self) -> None:
        """Test AudioMeterEngine loading and calculating per-stem RMS at playhead."""
        engine = AudioMeterEngine()
        ok = engine.load_stems(self.stems)
        self.assertTrue(ok)
        self.assertEqual(len(engine._stem_samples), 4)

        levels = engine.process_stem_playhead(pos_sec=0.5, stem_gains={"vocals": 1.0, "drums": 0.0})
        self.assertIn("vocals", levels)
        self.assertIn("drums", levels)
        self.assertGreater(levels["vocals"], -50.0)
        self.assertEqual(levels["drums"], -80.0)


if __name__ == "__main__":
    unittest.main()
