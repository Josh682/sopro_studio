"""Background thread for computing waveform peaks."""

import logging
import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf
from qtpy.QtCore import QThread, Signal

log = logging.getLogger("sound_processor.workers.waveform_worker")

@dataclass
class WaveformPeaks:
    """Represents downsampled audio peaks for rendering."""
    min_peaks: np.ndarray  # 1D array of float32
    max_peaks: np.ndarray  # 1D array of float32
    sample_rate: int
    total_samples: int
    duration_sec: float

    @property
    def num_buckets(self) -> int:
        return len(self.min_peaks)


class WaveformWorker(QThread):
    """Computes downsampled audio peaks in the background."""

    peaks_ready = Signal(object) # WaveformPeaks
    error = Signal(str)

    def __init__(self, file_path: Path, bucket_size: int = 256) -> None:
        super().__init__()
        self.setStackSize(8 * 1024 * 1024)
        self._file_path = file_path
        self._bucket_size = bucket_size
        self._cancel_flag = threading.Event()

    def cancel(self) -> None:
        self._cancel_flag.set()

    def run(self) -> None:
        if not self._file_path.exists():
            self.error.emit(f"File not found: {self._file_path}")
            return
            
        try:
            with sf.SoundFile(str(self._file_path)) as f:
                frames = f.frames
                sr = f.samplerate
                channels = f.channels
                duration = frames / sr
                
                if frames == 0:
                    self.error.emit("Audio file is empty.")
                    return

                num_buckets = (frames + self._bucket_size - 1) // self._bucket_size
                min_peaks = np.zeros(num_buckets, dtype=np.float32)
                max_peaks = np.zeros(num_buckets, dtype=np.float32)

                chunk_size = self._bucket_size * 1024  # Process in larger chunks for efficiency
                bucket_idx = 0
                
                for block in f.blocks(blocksize=chunk_size, dtype='float32'):
                    if self._cancel_flag.is_set():
                        return
                        
                    # If stereo, mix down to mono by taking the mean across channels
                    if channels > 1:
                        block = np.mean(block, axis=1)
                    
                    # Pad block if necessary to be cleanly divisible by bucket_size
                    remainder = len(block) % self._bucket_size
                    if remainder != 0:
                        pad_len = self._bucket_size - remainder
                        block = np.pad(block, (0, pad_len), mode='constant')

                    # Reshape into buckets
                    reshaped = block.reshape(-1, self._bucket_size)
                    
                    # Calculate min/max for each bucket
                    chunk_mins = np.min(reshaped, axis=1)
                    chunk_maxs = np.max(reshaped, axis=1)
                    
                    n_new_buckets = len(chunk_mins)
                    
                    # Handle the case where the very last chunk might overflow the pre-allocated array due to padding
                    if bucket_idx + n_new_buckets > num_buckets:
                        n_new_buckets = num_buckets - bucket_idx
                        chunk_mins = chunk_mins[:n_new_buckets]
                        chunk_maxs = chunk_maxs[:n_new_buckets]

                    min_peaks[bucket_idx:bucket_idx+n_new_buckets] = chunk_mins
                    max_peaks[bucket_idx:bucket_idx+n_new_buckets] = chunk_maxs
                    bucket_idx += n_new_buckets
                    
            if not self._cancel_flag.is_set():
                peaks = WaveformPeaks(
                    min_peaks=min_peaks,
                    max_peaks=max_peaks,
                    sample_rate=sr,
                    total_samples=frames,
                    duration_sec=duration
                )
                self.peaks_ready.emit(peaks)

        except Exception as e:
            log.exception("Error computing waveform peaks.")
            self.error.emit(str(e))
