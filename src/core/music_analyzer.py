"""Music Analysis Core (Key and Tempo Detection)."""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Any

import librosa
import numpy as np

from src.core.audio_engine import AudioEngine

log = logging.getLogger("sound_processor.core.music_analyzer")

# Key profile vectors (Krumhansl-Schmuckler, 1990)
MAJOR_PROFILE = np.array(
    [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
)
MINOR_PROFILE = np.array(
    [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
)

NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


@dataclass
class KeyResult:
    """Represents the detected musical key."""
    tonic: str
    mode: str
    confidence: float
    alternatives: list[dict[str, Any]] = field(default_factory=list)

    @property
    def display(self) -> str:
        if not self.tonic or not self.mode:
            return "N/A"
        return f"{self.tonic} {self.mode.capitalize()}"

    @property
    def is_reliable(self) -> bool:
        return self.confidence >= 0.75


@dataclass
class TempoResult:
    """Represents the detected tempo and beats."""
    bpm: float
    beat_frames: np.ndarray


class MusicAnalyzer:
    """Analyzes audio for key and tempo."""

    def __init__(self) -> None:
        self._audio_engine = AudioEngine()

    def analyze(
        self,
        input_path: Path,
        on_progress: Callable[[float, str], None] | None = None,
    ) -> tuple[KeyResult, TempoResult]:
        """Load audio, run key + BPM detection, return both results.
        
        Args:
            input_path: Path to the audio file.
            on_progress: Optional callback to report progress.
            
        Returns:
            Tuple of (KeyResult, TempoResult).
        """
        if on_progress:
            on_progress(0.1, "Loading audio...")

        try:
            # We need a mono mixdown for accurate chromagram and tempo analysis
            audio_buffer = self._audio_engine.load(input_path)
            if audio_buffer.channels > 1:
                # Downmix to mono
                mono_audio = np.mean(audio_buffer.samples, axis=1)
            else:
                mono_audio = audio_buffer.samples
            
            sample_rate = audio_buffer.sample_rate
            
            if on_progress:
                on_progress(0.4, "Analyzing key...")
            
            key_result = self._detect_key(mono_audio, sample_rate)
            
            if on_progress:
                on_progress(0.7, "Analyzing tempo...")
                
            tempo_result = self._estimate_bpm(mono_audio, sample_rate)
            
            if on_progress:
                on_progress(1.0, "Analysis complete.")
                
            return key_result, tempo_result

        except Exception as e:
            log.exception(f"Failed to analyze {input_path}")
            # Return empty/unreliable results on failure
            return KeyResult("", "", 0.0), TempoResult(0.0, np.array([]))

    def _detect_key(self, audio_mono: np.ndarray, sample_rate: int) -> KeyResult:
        """Detect the musical key using Krumhansl-Schmuckler algorithm."""
        # Ensure audio is not too short (less than a second might cause librosa errors)
        if len(audio_mono) < sample_rate:
            return KeyResult("", "", 0.0)

        chroma = librosa.feature.chroma_cqt(y=audio_mono, sr=sample_rate)
        profile = chroma.mean(axis=1)

        major_scores = [np.corrcoef(np.roll(MAJOR_PROFILE, i), profile)[0, 1] for i in range(12)]
        minor_scores = [np.corrcoef(np.roll(MINOR_PROFILE, i), profile)[0, 1] for i in range(12)]

        # Combine and sort all 24 candidates
        candidates = []
        for i in range(12):
            candidates.append({"tonic": NOTES[i], "mode": "major", "confidence": float(major_scores[i])})
            candidates.append({"tonic": NOTES[i], "mode": "minor", "confidence": float(minor_scores[i])})
        
        candidates.sort(key=lambda x: x["confidence"], reverse=True)
        
        best = candidates[0]
        alternatives = candidates[1:5]  # Top 4 alternatives
        
        return KeyResult(
            tonic=best["tonic"], 
            mode=best["mode"], 
            confidence=best["confidence"],
            alternatives=alternatives
        )

    def _estimate_bpm(self, audio_mono: np.ndarray, sample_rate: int) -> TempoResult:
        """Estimate the BPM using librosa."""
        if len(audio_mono) < sample_rate:
            return TempoResult(0.0, np.array([]))
            
        tempo, beat_frames = librosa.beat.beat_track(y=audio_mono, sr=sample_rate)
        
        # In librosa 0.10+, tempo is returned as an array of shape (1,)
        # We need to extract the float value
        if isinstance(tempo, np.ndarray):
            tempo_val = float(tempo[0])
        else:
            tempo_val = float(tempo)
            
        return TempoResult(bpm=round(tempo_val, 1), beat_frames=beat_frames)
