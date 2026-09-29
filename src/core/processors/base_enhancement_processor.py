"""Base class for single-file enhancement and restoration audio processors."""

from __future__ import annotations

import abc
import logging
import threading
from pathlib import Path
from typing import Any, Callable

import numpy as np

from src.core.audio_engine import AudioBuffer, AudioEngine
from src.core.exporter import ExportEngine
from src.core.processors.base_processor import BaseProcessor, ProcessingMode
from src.utils.config import AppConfig

log = logging.getLogger("sound_processor.core.processors.base_enhancement")


class BaseEnhancementProcessor(BaseProcessor):
    """Abstract base for audio enhancement processors operating file-by-file.
    
    Provides standard audio loading, chunked crossfade processing utility,
    progress routing, and format-preserving export.
    """

    processing_mode = ProcessingMode.FILE

    def __init__(self, engine: AudioEngine | None = None, exporter: ExportEngine | None = None) -> None:
        app_config = AppConfig()
        ffmpeg_bin = app_config.ffmpeg_path
        self._engine = engine or AudioEngine(ffmpeg_bin=ffmpeg_bin)
        self._exporter = exporter or ExportEngine(ffmpeg_bin=ffmpeg_bin)

    def process_file(
        self,
        input_path: Path,
        output_dir: Path,
        options: dict[str, Any],
        on_progress: Callable[[float, str], None] | None = None,
        cancel_flag: threading.Event | None = None,
    ) -> Path:
        """Standard pipeline: load audio, run enhance(), export result."""
        if cancel_flag and cancel_flag.is_set():
            return input_path

        if on_progress:
            on_progress(0.05, f"Loading {input_path.name}...")

        buffer = self._engine.load(input_path)
        samples = buffer.samples
        sr = buffer.sample_rate
        channels = buffer.channels

        if cancel_flag and cancel_flag.is_set():
            return input_path

        if on_progress:
            on_progress(0.15, f"Enhancing audio...")

        processed_samples = self.enhance(
            audio=samples,
            sr=sr,
            options=options,
            on_progress=on_progress,
            cancel_flag=cancel_flag,
        )

        if cancel_flag and cancel_flag.is_set():
            return input_path

        if on_progress:
            on_progress(0.90, "Exporting processed audio...")

        # Construct unique output path
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        suffix = input_path.suffix.lower()
        if suffix not in [".wav", ".mp3", ".flac"]:
            suffix = ".wav"
            
        base_name = f"{input_path.stem}_{self.metadata.id}"
        out_path = output_dir / f"{base_name}{suffix}"
        counter = 1
        while out_path.exists():
            out_path = output_dir / f"{base_name}_{counter}{suffix}"
            counter += 1

        # Reshape if 1D mono
        if processed_samples.ndim == 1 and channels > 1:
            processed_samples = np.repeat(processed_samples[:, np.newaxis], channels, axis=1)

        out_buffer = AudioBuffer(
            samples=processed_samples.astype(np.float32),
            sample_rate=sr,
            channels=channels if processed_samples.ndim > 1 else 1,
        )

        exported_path = self._exporter.export(out_buffer, out_path)
        
        if on_progress:
            on_progress(1.0, f"Completed: {exported_path.name}")

        return exported_path

    @abc.abstractmethod
    def enhance(
        self,
        audio: np.ndarray,
        sr: int,
        options: dict[str, Any],
        on_progress: Callable[[float, str], None] | None = None,
        cancel_flag: threading.Event | None = None,
    ) -> np.ndarray:
        """Perform the actual audio transformation.
        
        Args:
            audio: Floating point samples in [-1.0, 1.0], 1D (mono) or 2D (frames, channels).
            sr: Audio sample rate in Hz.
            options: Parameter dictionary from the UI.
            on_progress: Callback taking (progress_fraction, message).
            cancel_flag: Threading event checking for user abort.
            
        Returns:
            Processed audio numpy array (float32).
        """
        raise NotImplementedError

    @staticmethod
    def process_in_chunks(
        audio: np.ndarray,
        sr: int,
        chunk_fn: Callable[[np.ndarray], np.ndarray],
        chunk_len_sec: float = 8.0,
        overlap_sec: float = 0.5,
        on_progress: Callable[[float, str], None] | None = None,
        cancel_flag: threading.Event | None = None,
        progress_range: tuple[float, float] = (0.2, 0.85),
    ) -> np.ndarray:
        """Processes 1D or 2D audio in overlapping windows with Hann crossfades."""
        n_frames = audio.shape[0]
        chunk_size = int(chunk_len_sec * sr)
        overlap = int(overlap_sec * sr)
        step = max(1, chunk_size - overlap)

        if n_frames <= chunk_size:
            return chunk_fn(audio)

        is_stereo = (audio.ndim == 2)
        channels = audio.shape[1] if is_stereo else 1

        output = np.zeros_like(audio, dtype=np.float32)
        norm_weights = np.zeros(n_frames, dtype=np.float32)

        # Build Hann window for smooth crossfades
        window = np.hanning(chunk_size).astype(np.float32)
        if is_stereo:
            window_expanded = window[:, np.newaxis]
        else:
            window_expanded = window

        total_steps = int(np.ceil((n_frames - overlap) / step))
        step_idx = 0

        p_start, p_end = progress_range

        for start in range(0, n_frames, step):
            if cancel_flag and cancel_flag.is_set():
                break

            end = min(start + chunk_size, n_frames)
            actual_len = end - start
            chunk = audio[start:end]

            if actual_len < chunk_size:
                # Pad final chunk to standard size
                if is_stereo:
                    padded = np.zeros((chunk_size, channels), dtype=np.float32)
                    padded[:actual_len] = chunk
                else:
                    padded = np.zeros(chunk_size, dtype=np.float32)
                    padded[:actual_len] = chunk
                processed_padded = chunk_fn(padded)
                processed_chunk = processed_padded[:actual_len]
                win = window[:actual_len, np.newaxis] if is_stereo else window[:actual_len]
                norm_win = window[:actual_len]
            else:
                processed_chunk = chunk_fn(chunk)
                win = window_expanded
                norm_win = window

            output[start:end] += processed_chunk * win
            norm_weights[start:end] += norm_win

            step_idx += 1
            if on_progress and total_steps > 0:
                frac = p_start + (step_idx / total_steps) * (p_end - p_start)
                on_progress(min(p_end, frac), f"Processing chunk {step_idx}/{total_steps}...")

        # Avoid zero division
        nonzero_mask = norm_weights > 1e-6
        if is_stereo:
            output[nonzero_mask] /= norm_weights[nonzero_mask, np.newaxis]
        else:
            output[nonzero_mask] /= norm_weights[nonzero_mask]

        return output
