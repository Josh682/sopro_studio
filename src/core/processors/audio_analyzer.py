"""Audio Analyzer for calculating peak, RMS, and LUFS."""

import logging
import threading
from pathlib import Path
from typing import Callable
import numpy as np
import soundfile as sf
import pyloudnorm as pyln

from src.audio.metadata import AudioInfo, probe

log = logging.getLogger("sound_processor.core.processors.audio_analyzer")

class AudioAnalyzer:
    """Analyzer for extracting technical audio properties (Peak, RMS, LUFS)."""

    @staticmethod
    def analyze(
        file_path: Path,
        info: AudioInfo | None = None,
        on_progress: Callable[[float, str], None] | None = None,
        cancel_flag: threading.Event | None = None,
    ) -> AudioInfo:
        """
        Analyze an audio file and populate amplitude metrics.
        Streams for Peak/RMS to minimize memory, but loads full file for LUFS 
        since pyloudnorm requires the full contiguous array.
        """
        if info is None:
            if on_progress:
                on_progress(0.0, "Probing metadata...")
            info = probe(file_path)

        if cancel_flag and cancel_flag.is_set():
            return info

        if on_progress:
            on_progress(0.1, "Analyzing Peak & RMS...")

        # Calculate Peak and RMS via streaming chunks (Sample Peak)
        chunk_size = 1024 * 512
        max_abs = 0.0
        sum_sq = 0.0
        total_samples = 0

        try:
            with sf.SoundFile(str(file_path)) as f:
                frames = f.frames
                read_frames = 0
                for block in f.blocks(blocksize=chunk_size, dtype='float32'):
                    if cancel_flag and cancel_flag.is_set():
                        return info
                        
                    max_abs = max(max_abs, float(np.max(np.abs(block))))
                    sum_sq += float(np.sum(block**2))
                    total_samples += block.size
                    read_frames += block.shape[0]
                    
                    if on_progress and frames > 0:
                        # Map Peak/RMS to 10% -> 50%
                        pct = 0.1 + 0.4 * (read_frames / frames)
                        on_progress(pct, "Analyzing Peak & RMS...")
                        
            # Finalize Peak
            if max_abs == 0.0:
                info.peak_dbfs = -float('inf')
            else:
                info.peak_dbfs = float(20 * np.log10(max_abs))
                
            # Finalize RMS
            if total_samples > 0 and sum_sq > 0.0:
                rms_val = np.sqrt(sum_sq / total_samples)
                info.rms_dbfs = float(20 * np.log10(rms_val))
            else:
                info.rms_dbfs = -float('inf')
                
        except Exception as e:
            log.warning("Failed to analyze peak/RMS for %s: %s", file_path.name, e)
            return info

        if cancel_flag and cancel_flag.is_set():
            return info

        # LUFS Analysis (requires full file load into pyloudnorm)
        if on_progress:
            on_progress(0.5, "Measuring LUFS...")
            
        try:
            data, rate = sf.read(str(file_path), dtype='float32')
            if cancel_flag and cancel_flag.is_set():
                return info
                
            meter = pyln.Meter(rate) 
            lufs = meter.integrated_loudness(data)
            info.integrated_lufs = float(lufs)
            
        except Exception as e:
            log.warning("Failed to measure LUFS for %s: %s", file_path.name, e)

        if on_progress:
            on_progress(1.0, "Analysis complete")

        return info
