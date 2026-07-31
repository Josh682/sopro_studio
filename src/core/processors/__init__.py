"""Processor plugins."""

from src.core.processors.format_converter import FormatConverter
from src.core.processors.stem_separator import StemSeparator
from src.core.processors.track_combiner import TrackCombiner
from src.core.processors.key_detector import KeyDetector
from src.core.processors.pitch_shifter import PitchShifter
from src.core.processors.tempo_changer import TempoChanger
from src.core.processors.audio_trimmer import AudioTrimmer
from src.core.processors.loudness_normalizer import LoudnessNormalizer

__all__ = [
    "FormatConverter",
    "StemSeparator",
    "TrackCombiner",
    "KeyDetector",
    "PitchShifter",
    "TempoChanger",
    "AudioTrimmer",
    "LoudnessNormalizer",
]
