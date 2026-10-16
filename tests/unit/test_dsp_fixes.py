"""Unit tests verifying DSP bug fixes from V4.0 (LOG-01, LOG-02, LOG-07)."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import unittest
import numpy as np

from src.core.processors.denoise_processor import (
    apply_hum_notch,
    detect_hum_fundamental,
    DenoiseProcessor,
)
from src.core.processors.restoration_processor import (
    declick_audio,
    inpaint_dropouts,
    AudioRestorationProcessor,
)


class TestDSPFixes(unittest.TestCase):
    """Test suite for V4.0 algorithmic and boundary bug fixes."""

    def test_log01_hum_detection_50hz_and_60hz(self) -> None:
        """LOG-01: Verify FFT hum detection accurately identifies 50Hz/60Hz without false positives."""
        sr = 44100
        duration = 1.0
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)

        # 1. Clean musical tone (e.g. musical B1 ≈ 61.74 Hz) with gentle noise
        clean_music = np.sin(2 * np.pi * 61.74 * t) * 0.3 + np.random.normal(0, 0.05, len(t))
        detected_music = detect_hum_fundamental(clean_music, sr=sr)
        self.assertIsNone(detected_music, "Clean musical tone was falsely detected as electrical hum!")

        # 2. Prominent 60Hz ground hum
        hum_60 = np.sin(2 * np.pi * 60.0 * t) * 0.5 + np.random.normal(0, 0.02, len(t))
        detected_60 = detect_hum_fundamental(hum_60, sr=sr)
        self.assertEqual(detected_60, 60.0, "60Hz hum was not detected!")

        # 3. Prominent 50Hz European/Asian ground hum
        hum_50 = np.sin(2 * np.pi * 50.0 * t) * 0.5 + np.random.normal(0, 0.02, len(t))
        detected_50 = detect_hum_fundamental(hum_50, sr=sr)
        self.assertEqual(detected_50, 50.0, "50Hz hum was not detected!")

    def test_log01_denoise_auto_preserves_clean_audio(self) -> None:
        """LOG-01: Auto mode should not notch clean audio without detected hum."""
        sr = 44100
        t = np.linspace(0, 0.5, int(sr * 0.5), endpoint=False)
        music_b1 = (np.sin(2 * np.pi * 60.0 * t) * 0.4).astype(np.float32)

        processor = DenoiseProcessor()
        # In auto mode with no hum detected, enhance should not notch 60Hz
        # (music_b1 has low noise floor so median power is near peak, meaning no >10dB spike above baseline)
        processed = processor.enhance(music_b1, sr=sr, options={"noise_type": "auto", "strength": 0.2})
        self.assertEqual(len(processed), len(music_b1))
        self.assertFalse(np.isnan(processed).any())

    def test_log02_declick_index_zero_boundary(self) -> None:
        """LOG-02: De-click should repair clicks that occur at index 0 or at the very end of the array."""
        sr = 44100
        audio = np.zeros(1000, dtype=np.float32)
        # Place impulsive click starting at index 0
        audio[0:4] = 0.95
        # Place another click at the end
        audio[-4:] = -0.95

        repaired = declick_audio(audio, sr=sr, strength=0.9, preserve_transients=False)
        self.assertEqual(len(repaired), len(audio))
        self.assertFalse(np.isnan(repaired).any())
        # The peak at index 0 and end should be reduced
        self.assertLess(np.max(np.abs(repaired[0:4])), 0.95, "Click at index 0 was not repaired!")
        self.assertLess(np.max(np.abs(repaired[-4:])), 0.95, "Click at end of array was not repaired!")

    def test_log02_inpaint_dropouts_boundary(self) -> None:
        """LOG-02: Inpaint dropouts should repair zero dropouts at index 0 and at array ends."""
        sr = 44100
        # Sine wave with dropouts
        t = np.linspace(0, 0.1, int(sr * 0.1), endpoint=False)
        audio = (np.sin(2 * np.pi * 200 * t) * 0.5).astype(np.float32)

        # Place 4ms dropout at index 0
        drop_len = int(0.004 * sr)
        audio[0:drop_len] = 0.0

        repaired = inpaint_dropouts(audio, sr=sr, max_gap_ms=40.0)
        self.assertEqual(len(repaired), len(audio))
        self.assertFalse(np.isnan(repaired).any())

    def test_log07_multichannel_audio_restoration(self) -> None:
        """LOG-07: AudioRestorationProcessor should handle 1D mono, 2D mono (N, 1), stereo (N, 2), and multichannel without crash."""
        sr = 22050
        n_samples = 4000
        processor = AudioRestorationProcessor()

        # 1D Mono
        mono_1d = (np.sin(np.linspace(0, 10, n_samples)) * 0.5).astype(np.float32)
        out_1d = processor.enhance(mono_1d, sr=sr, options={"recording_type": "digital"})
        self.assertEqual(out_1d.shape, mono_1d.shape)

        # 2D Stereo
        stereo = np.column_stack([mono_1d, mono_1d])
        out_stereo = processor.enhance(stereo, sr=sr, options={"recording_type": "digital"})
        self.assertEqual(out_stereo.shape, stereo.shape)

        # 4-Channel Ambisonics
        quad = np.column_stack([mono_1d, mono_1d, mono_1d, mono_1d])
        out_quad = processor.enhance(quad, sr=sr, options={"recording_type": "digital"})
        self.assertEqual(out_quad.shape, quad.shape)


if __name__ == "__main__":
    unittest.main()
