"""Comprehensive automated test suite for the deep AudioBuffer module and compatibility adapters."""

import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

from src.core.audio_engine import AudioBuffer, AudioEngine
from src.core.exporter import ExportEngine


class TestAudioBuffer(unittest.TestCase):
    """Tests for the deep AudioBuffer class."""

    def setUp(self):
        self.sr = 44100
        self.duration = 1.5  # seconds
        self.num_frames = int(self.sr * self.duration)
        
        # Generate 440 Hz sine wave
        t = np.linspace(0, self.duration, self.num_frames, endpoint=False, dtype=np.float32)
        sine = 0.5 * np.sin(2 * np.pi * 440 * t)
        
        self.mono_samples = sine
        self.stereo_samples = np.stack([sine, sine * 0.8], axis=1)

        self.mono_buffer = AudioBuffer(
            samples=self.mono_samples,
            sample_rate=self.sr,
            channels=1,
        )
        self.stereo_buffer = AudioBuffer(
            samples=self.stereo_samples,
            sample_rate=self.sr,
            channels=2,
        )

        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    # ------------------------------------------------------------------
    # Properties & In-Memory Operations
    # ------------------------------------------------------------------

    def test_properties(self):
        self.assertEqual(self.mono_buffer.num_frames, self.num_frames)
        self.assertAlmostEqual(self.mono_buffer.duration, self.duration, places=3)
        self.assertTrue(self.mono_buffer.is_mono)

        self.assertEqual(self.stereo_buffer.num_frames, self.num_frames)
        self.assertAlmostEqual(self.stereo_buffer.duration, self.duration, places=3)
        self.assertFalse(self.stereo_buffer.is_mono)

    def test_to_mono(self):
        mono_converted = self.stereo_buffer.to_mono()
        self.assertTrue(mono_converted.is_mono)
        self.assertEqual(mono_converted.channels, 1)
        self.assertEqual(mono_converted.samples.ndim, 1)
        self.assertEqual(mono_converted.num_frames, self.stereo_buffer.num_frames)

    def test_slice(self):
        start = 0.2
        end = 0.8
        sliced = self.mono_buffer.slice(start, end)
        expected_frames = int((end - start) * self.sr)
        self.assertAlmostEqual(sliced.duration, 0.6, places=2)
        self.assertEqual(sliced.num_frames, expected_frames)

        with self.assertRaises(ValueError):
            self.mono_buffer.slice(0.8, 0.2)

    def test_normalize(self):
        # Buffer peak is 0.5
        target_peak = 0.95
        normalized = self.mono_buffer.normalize(target_peak=target_peak)
        peak = float(np.abs(normalized.samples).max())
        self.assertAlmostEqual(peak, target_peak, places=3)

    def test_apply_gain(self):
        # +6 dB is ~2x gain
        gained = self.mono_buffer.apply_gain(6.0)
        peak_orig = float(np.abs(self.mono_buffer.samples).max())
        peak_gained = float(np.abs(gained.samples).max())
        self.assertAlmostEqual(peak_gained / peak_orig, 10.0 ** (6.0 / 20.0), places=3)

    def test_resample(self):
        target_sr = 22050
        resampled = self.mono_buffer.resample(target_sr)
        self.assertEqual(resampled.sample_rate, target_sr)
        expected_frames = int(round(self.num_frames * (target_sr / self.sr)))
        self.assertAlmostEqual(resampled.duration, self.duration, places=2)
        self.assertAlmostEqual(resampled.num_frames, expected_frames, delta=2)

    # ------------------------------------------------------------------
    # File I/O Operations & Format Dispatches
    # ------------------------------------------------------------------

    def test_save_and_load_wav(self):
        wav_path = self.temp_path / "test.wav"
        saved = self.stereo_buffer.save(wav_path, bit_depth=24)
        self.assertTrue(saved.exists())
        self.assertEqual(saved, wav_path)

        # Inspect with soundfile
        info = sf.info(str(wav_path))
        self.assertEqual(info.samplerate, self.sr)
        self.assertEqual(info.channels, 2)
        self.assertEqual(info.subtype, "PCM_24")

        # Load back via AudioBuffer.load
        loaded = AudioBuffer.load(wav_path)
        self.assertEqual(loaded.sample_rate, self.sr)
        self.assertEqual(loaded.channels, 2)
        self.assertAlmostEqual(loaded.duration, self.duration, places=2)

    def test_save_and_load_mp3(self):
        mp3_path = self.temp_path / "test.mp3"
        saved = self.stereo_buffer.save(mp3_path, bitrate=192)
        self.assertTrue(saved.exists())

        loaded = AudioBuffer.load(mp3_path)
        self.assertEqual(loaded.sample_rate, self.sr)
        self.assertEqual(loaded.channels, 2)
        # MP3 may have tiny encoder delay/padding, duration should match within 0.1s
        self.assertAlmostEqual(loaded.duration, self.duration, delta=0.1)

    def test_save_and_load_flac(self):
        flac_path = self.temp_path / "test.flac"
        saved = self.stereo_buffer.save(flac_path, compression=5)
        self.assertTrue(saved.exists())

        loaded = AudioBuffer.load(flac_path)
        self.assertEqual(loaded.sample_rate, self.sr)
        self.assertEqual(loaded.channels, 2)
        self.assertAlmostEqual(loaded.duration, self.duration, places=2)

    def test_format_inference_from_suffix(self):
        auto_wav = self.temp_path / "auto.wav"
        auto_mp3 = self.temp_path / "auto.mp3"
        auto_flac = self.temp_path / "auto.flac"

        self.mono_buffer.save(auto_wav)
        self.mono_buffer.save(auto_mp3)
        self.mono_buffer.save(auto_flac)

        self.assertTrue(auto_wav.exists())
        self.assertTrue(auto_mp3.exists())
        self.assertTrue(auto_flac.exists())

    def test_sliced_loading(self):
        wav_path = self.temp_path / "long.wav"
        self.stereo_buffer.save(wav_path)

        # Load with start_sec and duration_sec
        sliced = AudioBuffer.load(wav_path, start_sec=0.2, duration_sec=0.5)
        self.assertAlmostEqual(sliced.duration, 0.5, delta=0.05)


class TestCompatibilityAdapters(unittest.TestCase):
    """Tests confirming backward compatibility of AudioEngine and ExportEngine."""

    def setUp(self):
        self.sr = 44100
        t = np.linspace(0, 1.0, self.sr, endpoint=False, dtype=np.float32)
        self.samples = 0.5 * np.sin(2 * np.pi * 440 * t)
        self.buffer = AudioBuffer(self.samples, self.sr, 1)

        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

        self.audio_engine = AudioEngine()
        self.export_engine = ExportEngine()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_audio_engine_adapter(self):
        wav_path = self.temp_path / "legacy_in.wav"
        self.buffer.save(wav_path)

        # 1. load
        loaded = self.audio_engine.load(wav_path)
        self.assertIsInstance(loaded, AudioBuffer)
        self.assertEqual(loaded.sample_rate, self.sr)

        # 2. decode_via_ffmpeg
        decoded = self.audio_engine.decode_via_ffmpeg(wav_path)
        self.assertIsInstance(decoded, AudioBuffer)

        # 3. resample
        resampled = self.audio_engine.resample(loaded, 22050)
        self.assertEqual(resampled.sample_rate, 22050)

        # 4. normalize
        normalized = self.audio_engine.normalize(loaded, target_peak=0.9)
        self.assertAlmostEqual(float(np.abs(normalized.samples).max()), 0.9, places=3)

    def test_export_engine_adapter(self):
        wav_out = self.temp_path / "legacy_out.wav"
        mp3_out = self.temp_path / "legacy_out.mp3"
        flac_out = self.temp_path / "legacy_out.flac"
        generic_out = self.temp_path / "legacy_generic.wav"

        self.export_engine.export_wav(self.buffer, wav_out, bit_depth=16)
        self.assertTrue(wav_out.exists())

        self.export_engine.export_mp3(self.buffer, mp3_out, bitrate=128)
        self.assertTrue(mp3_out.exists())

        self.export_engine.export_flac(self.buffer, flac_out, compression=4)
        self.assertTrue(flac_out.exists())

        self.export_engine.export(self.buffer, generic_out)
        self.assertTrue(generic_out.exists())


if __name__ == "__main__":
    unittest.main()
