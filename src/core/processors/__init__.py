"""Processor plugins."""

from src.core.processors.format_converter import FormatConverter
from src.core.processors.stem_separator import StemSeparator
from src.core.processors.track_combiner import TrackCombiner
from src.core.processors.key_detector import KeyDetector
from src.core.processors.pitch_shifter import PitchShifter
from src.core.processors.tempo_changer import TempoChanger

__all__ = [
    "FormatConverter",
    "StemSeparator",
    "TrackCombiner",
    "KeyDetector",
    "PitchShifter",
    "TempoChanger",
]
