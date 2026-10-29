"""Unit tests for FormatConverter, TrackCombiner, and DynamicRackController parameter types.

Verifies:
1. FormatConverter handles both integer and string bit_depth, sample_rate, and bitrate.
2. DynamicRackController preserves exact types for discrete choices (e.g. int 16 instead of str '16').
3. Audio writer and AudioBuffer accept string bit_depth without raising Unsupported bit depth.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ui.qt import QApplication

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

from src.audio.writer import write_flac, write_mp3, write_wav
from src.core.audio_engine import AudioBuffer
from src.core.processors.format_converter import FormatConverter
from src.core.processors.track_combiner import TrackCombiner
from src.ui.components.rack_control_factory import DynamicRackController
from src.utils.config import AppConfig


class TestConverterParameterTypes(unittest.TestCase):
    """Test parameter type conversions and format converter execution."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.input_wav = self.temp_dir / "test_input.wav"
        self.out_dir = self.temp_dir / "output"
        self.out_dir.mkdir(parents=True, exist_ok=True)

        # 0.5s stereo sine tone @ 44.1 kHz
        sr = 44100
        t = np.linspace(0, 0.5, int(sr * 0.5), endpoint=False, dtype=np.float32)
        sine = 0.5 * np.sin(2 * np.pi * 440.0 * t)
        stereo_samples = np.column_stack((sine, sine))
        write_wav(self.input_wav, stereo_samples, sr, bit_depth=16)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_writer_accepts_string_bit_depth_and_bitrate(self) -> None:
        """Ensure write_wav, write_mp3, and write_flac accept string params."""
        samples = np.zeros((1000, 2), dtype=np.float32)
        
        # WAV with str bit_depth
        wav_path = self.temp_dir / "out_str_16.wav"
        res_wav = write_wav(wav_path, samples, 44100, bit_depth="16")
        self.assertTrue(res_wav.exists())

        res_wav_24 = write_wav(self.temp_dir / "out_str_24.wav", samples, 44100, bit_depth="24")
        self.assertTrue(res_wav_24.exists())

        # AudioBuffer.save with str bit_depth
        buf = AudioBuffer(samples=samples, sample_rate=44100, channels=2)
        saved_wav = buf.save(self.temp_dir / "out_buf_str.wav", format="wav", bit_depth="16")
        self.assertTrue(saved_wav.exists())

    def test_dynamic_rack_controller_choice_type_preservation(self) -> None:
        """Verify DynamicRackController maps string choice selections back to original types."""
        controller = DynamicRackController()
        descs = FormatConverter.get_parameter_descriptors()
        self._panels = controller.build_clusters(descs, accent_color="#3B82F6")

        params = controller.get_parameters()
        # Default bit_depth descriptor is int 16
        self.assertIsInstance(params["bit_depth"], int)
        self.assertEqual(params["bit_depth"], 16)

        # Default sample_rate is int 44100
        self.assertIsInstance(params["sample_rate"], int)
        self.assertEqual(params["sample_rate"], 44100)

        # Default mp3_bitrate is int 192
        self.assertIsInstance(params["mp3_bitrate"], int)
        self.assertEqual(params["mp3_bitrate"], 192)

        # Change bit_depth choice in widget to "24"
        widget = controller.controls["bit_depth"]
        widget.setCurrentChoice("24")
        updated = controller.get_parameters()
        self.assertIsInstance(updated["bit_depth"], int)
        self.assertEqual(updated["bit_depth"], 24)

    def test_format_converter_with_string_options(self) -> None:
        """FormatConverter must succeed when options dict contains strings from UI/CLI."""
        converter = FormatConverter()
        
        # Options with string types as might be passed from external callers or uncast inputs
        options = {
            "output_format": "wav",
            "sample_rate": "48000",
            "bit_depth": "16",
            "mp3_bitrate": "192",
            "flac_compression": "5",
            "normalize": False,
        }

        results = converter.process(
            input_paths=[self.input_wav],
            output_dir=self.out_dir,
            options=options,
        )

        self.assertIn(self.input_wav, results)
        out_file = results[self.input_wav]
        self.assertTrue(out_file.exists())
        self.assertTrue(out_file.name.endswith(".wav"))

    def test_format_converter_with_mp3_and_flac(self) -> None:
        """FormatConverter handles mp3 and flac conversion with string options."""
        converter = FormatConverter()
        
        # Test MP3 conversion
        mp3_options = {
            "output_format": "mp3",
            "sample_rate": "44100",
            "mp3_bitrate": "192",
            "normalize": True,
        }
        res_mp3 = converter.process(
            input_paths=[self.input_wav],
            output_dir=self.out_dir,
            options=mp3_options,
        )
        self.assertIn(self.input_wav, res_mp3)
        self.assertTrue(res_mp3[self.input_wav].exists())

        # Test FLAC conversion
        flac_options = {
            "output_format": "flac",
            "sample_rate": "44100",
            "flac_compression": "5",
        }
        res_flac = converter.process(
            input_paths=[self.input_wav],
            output_dir=self.out_dir,
            options=flac_options,
        )
        self.assertIn(self.input_wav, res_flac)
        self.assertTrue(res_flac[self.input_wav].exists())

    def test_track_combiner_with_string_bit_depth(self) -> None:
        """TrackCombiner must succeed when bit_depth is passed as string."""
        combiner = TrackCombiner()
        options = {
            "output_format": "wav",
            "bit_depth": "24",
            "output_filename": "combined_test",
        }
        res = combiner.process(
            input_paths=[self.input_wav, self.input_wav],
            output_dir=self.out_dir,
            options=options,
        )
        self.assertIn(self.input_wav, res)
        self.assertTrue(res[self.input_wav].exists())


if __name__ == "__main__":
    unittest.main()
