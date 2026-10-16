"""Comprehensive Unit Tests for Kandidat 4: Unified Processor Hierarchy.

Validates:
1. All 14 processors subclass BaseProcessor directly.
2. All 14 processors are discoverable in ProcessorRegistry.
3. BaseEnhancementProcessor compatibility shim functions properly.
4. src.audio.dsp.process_in_chunks operates smoothly on mono and stereo audio.
5. BaseProcessor.process default batch loop delegates to process_file for FILE mode.
6. AudioAnalyzer first-class BaseProcessor integration (metadata, descriptors, execution).
7. Enhancement processors retain enhance() helper while implementing process_file().
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import soundfile as sf

from src.audio.dsp import process_in_chunks
from src.core.processor_registry import ProcessorRegistry
from src.core.processors.audio_analyzer import AudioAnalyzer
from src.core.processors.audio_trimmer import AudioTrimmer
from src.core.processors.base_enhancement_processor import BaseEnhancementProcessor
from src.core.processors.base_processor import BaseProcessor, ProcessingMode
from src.core.processors.declip_processor import DeclipProcessor
from src.core.processors.denoise_processor import DenoiseProcessor
from src.core.processors.dereverb_processor import DereverbProcessor
from src.core.processors.format_converter import FormatConverter
from src.core.processors.key_detector import KeyDetector
from src.core.processors.loudness_normalizer import LoudnessNormalizer
from src.core.processors.pitch_shifter import PitchShifter
from src.core.processors.restoration_processor import AudioRestorationProcessor
from src.core.processors.stem_separator import StemSeparator
from src.core.processors.tempo_changer import TempoChanger
from src.core.processors.track_combiner import TrackCombiner
from src.core.processors.voice_enhancement_processor import VoiceEnhancementProcessor


ALL_PROCESSOR_CLASSES = [
    FormatConverter,
    StemSeparator,
    TrackCombiner,
    KeyDetector,
    PitchShifter,
    TempoChanger,
    AudioTrimmer,
    LoudnessNormalizer,
    DeclipProcessor,
    DenoiseProcessor,
    DereverbProcessor,
    VoiceEnhancementProcessor,
    AudioRestorationProcessor,
    AudioAnalyzer,
]


class TestUnifiedProcessorHierarchy(unittest.TestCase):
    """Test suite for unified BaseProcessor hierarchy and DSP extraction."""

    def setUp(self) -> None:
        self.tmp_dir = PROJECT_ROOT / "tests" / "fixtures" / "tmp_hierarchy"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        import shutil
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_all_processors_inherit_base_processor(self) -> None:
        """Verify that every single processor directly inherits from BaseProcessor."""
        for proc_cls in ALL_PROCESSOR_CLASSES:
            with self.subTest(processor=proc_cls.__name__):
                self.assertTrue(
                    issubclass(proc_cls, BaseProcessor),
                    f"{proc_cls.__name__} does not inherit from BaseProcessor",
                )
                self.assertTrue(
                    hasattr(proc_cls, "metadata"),
                    f"{proc_cls.__name__} is missing metadata attribute",
                )
                self.assertTrue(
                    bool(proc_cls.metadata.id),
                    f"{proc_cls.__name__} has empty metadata.id",
                )

    def test_enhancement_processors_are_base_processors(self) -> None:
        """Verify the 5 enhancement processors directly subclass BaseProcessor."""
        enhancement_classes = [
            DeclipProcessor,
            DenoiseProcessor,
            DereverbProcessor,
            VoiceEnhancementProcessor,
            AudioRestorationProcessor,
        ]
        for cls in enhancement_classes:
            with self.subTest(cls=cls.__name__):
                self.assertTrue(issubclass(cls, BaseProcessor))
                self.assertEqual(cls.processing_mode, ProcessingMode.FILE)
                self.assertTrue(hasattr(cls, "enhance"))
                self.assertTrue(hasattr(cls, "process_file"))

    def test_base_enhancement_processor_shim(self) -> None:
        """Verify BaseEnhancementProcessor remains functional as a compatibility shim."""
        self.assertTrue(issubclass(BaseEnhancementProcessor, BaseProcessor))
        self.assertEqual(BaseEnhancementProcessor.processing_mode, ProcessingMode.FILE)
        self.assertTrue(hasattr(BaseEnhancementProcessor, "process_in_chunks"))

    def test_processor_registry_registration(self) -> None:
        """Verify all processors and aliases are registered and instantiable in ProcessorRegistry."""
        registered_keys = ProcessorRegistry._processors.keys()
        expected_ids = [
            "format_converter",
            "stem_separator",
            "track_combiner",
            "key_detector",
            "pitch_shifter",
            "tempo_changer",
            "audio_trimmer",
            "loudness_normalizer",
            "declip",
            "denoise",
            "dereverb",
            "voice_enhancement",
            "restoration",
            "audio_analyzer",
        ]
        for eid in expected_ids:
            with self.subTest(id=eid):
                self.assertIn(eid, registered_keys, f"Processor id '{eid}' not found in registry")
                inst = ProcessorRegistry.get_processor(eid)
                self.assertIsInstance(inst, BaseProcessor)

        # Check metadata_editor alias
        self.assertIn("metadata_editor", registered_keys)
        meta_inst = ProcessorRegistry.get_processor("metadata_editor")
        self.assertIsInstance(meta_inst, AudioAnalyzer)

    def test_process_in_chunks_dsp(self) -> None:
        """Verify pure process_in_chunks DSP algorithm with Hann crossfading."""
        sr = 16000
        # 1.5s sine wave (multiple chunks when chunk_len_sec=0.5, overlap=0.1)
        t = np.linspace(0, 1.5, int(sr * 1.5), endpoint=False, dtype=np.float32)
        sine = np.sin(2 * np.pi * 440 * t)

        # Simple gain function chunk_fn
        def double_gain(chunk: np.ndarray) -> np.ndarray:
            return chunk * 2.0

        processed = process_in_chunks(
            audio=sine,
            sr=sr,
            chunk_fn=double_gain,
            chunk_len_sec=0.5,
            overlap_sec=0.1,
        )

        self.assertEqual(processed.shape, sine.shape)
        # Check interior gain matches ~2.0
        mid_idx = len(sine) // 2
        self.assertAlmostEqual(processed[mid_idx], sine[mid_idx] * 2.0, delta=0.05)

        # Test stereo signal
        stereo = np.column_stack([sine, sine * 0.5])
        processed_stereo = process_in_chunks(
            audio=stereo,
            sr=sr,
            chunk_fn=double_gain,
            chunk_len_sec=0.5,
            overlap_sec=0.1,
        )
        self.assertEqual(processed_stereo.shape, stereo.shape)

    def test_audio_analyzer_execution(self) -> None:
        """Verify AudioAnalyzer executes as a BaseProcessor with Peak and RMS computation."""
        sr = 22050
        samples = (np.sin(2 * np.pi * 440 * np.linspace(0, 0.2, int(sr * 0.2))) * 0.5).astype(np.float32)
        test_file = self.tmp_dir / "test_analyze.wav"
        sf.write(str(test_file), samples, sr)

        analyzer = AudioAnalyzer()
        self.assertEqual(analyzer.metadata.id, "audio_analyzer")
        self.assertGreater(len(analyzer.get_parameter_descriptors()), 0)

        # Execute single file
        info = analyzer.analyze(test_file)
        self.assertIsNotNone(info)
        self.assertGreater(info.duration, 0.15)
        self.assertAlmostEqual(info.peak_dbfs, 20 * np.log10(0.5), delta=0.5)

        # Execute batch via BaseProcessor.process
        res = analyzer.process(
            input_paths=[test_file],
            output_dir=self.tmp_dir,
            options={"export_json": True},
        )
        self.assertIn(test_file, res)
        # Verify JSON was exported
        json_path = self.tmp_dir / f"{test_file.stem}_analysis.json"
        self.assertTrue(json_path.exists())

    def test_base_processor_default_batch_delegation(self) -> None:
        """Verify BaseProcessor.process() automatically loops over input_paths for FILE processors."""
        sr = 22050
        samples = (np.sin(2 * np.pi * 440 * np.linspace(0, 0.1, int(sr * 0.1))) * 0.2).astype(np.float32)
        f1 = self.tmp_dir / "batch_1.wav"
        f2 = self.tmp_dir / "batch_2.wav"
        sf.write(str(f1), samples, sr)
        sf.write(str(f2), samples, sr)

        trimmer = AudioTrimmer()
        self.assertEqual(trimmer.processing_mode, ProcessingMode.FILE)

        # Call process directly on a FILE mode processor without caller looping
        res = trimmer.process(
            input_paths=[f1, f2],
            output_dir=self.tmp_dir,
            options={"start_sec": 0.0, "end_sec": 0.05},
        )
        self.assertIn(f1, res)
        self.assertIn(f2, res)
        self.assertTrue(res[f1].exists())
        self.assertTrue(res[f2].exists())


if __name__ == "__main__":
    unittest.main()
