"""Processor plugins."""

from src.core.processors.format_converter import FormatConverter
from src.core.processors.stem_separator import StemSeparator
from src.core.processors.track_combiner import TrackCombiner
from src.core.processors.key_detector import KeyDetector
from src.core.processors.pitch_shifter import PitchShifter
from src.core.processors.tempo_changer import TempoChanger
from src.core.processors.audio_trimmer import AudioTrimmer
from src.core.processors.loudness_normalizer import LoudnessNormalizer
from src.core.processors.base_enhancement_processor import BaseEnhancementProcessor
from src.core.processors.declip_processor import DeclipProcessor
from src.core.processors.denoise_processor import DenoiseProcessor
from src.core.processors.dereverb_processor import DereverbProcessor
from src.core.processors.voice_enhancement_processor import VoiceEnhancementProcessor
from src.core.processors.restoration_processor import AudioRestorationProcessor

__all__ = [
    "FormatConverter",
    "StemSeparator",
    "TrackCombiner",
    "KeyDetector",
    "PitchShifter",
    "TempoChanger",
    "AudioTrimmer",
    "LoudnessNormalizer",
    "BaseEnhancementProcessor",
    "DeclipProcessor",
    "DenoiseProcessor",
    "DereverbProcessor",
    "VoiceEnhancementProcessor",
    "AudioRestorationProcessor",
]
