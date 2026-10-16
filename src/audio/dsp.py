"""Audio Digital Signal Processing (DSP) utilities and chunking algorithms."""

from __future__ import annotations

import logging
import threading
from typing import Callable

import numpy as np

log = logging.getLogger("sound_processor.audio.dsp")


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
    """Process 1D or 2D audio in overlapping windows with smooth Hann crossfades.

    Args:
        audio: Floating point samples in [-1.0, 1.0], shaped (frames,) or (frames, channels).
        sr: Sample rate in Hz.
        chunk_fn: Transformation callable taking and returning a numpy chunk.
        chunk_len_sec: Length of each processing chunk in seconds.
        overlap_sec: Overlap length between consecutive chunks in seconds.
        on_progress: Callback taking (progress_fraction, message).
        cancel_flag: Threading event to check for early abort.
        progress_range: Tuple of (start_fraction, end_fraction) for progress mapping.

    Returns:
        Reconstructed numpy array with smooth windowed transitions.
    """
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
    window_expanded = window[:, np.newaxis] if is_stereo else window

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

    # Avoid zero division on edge tails
    nonzero_mask = norm_weights > 1e-6
    if is_stereo:
        output[nonzero_mask] /= norm_weights[nonzero_mask, np.newaxis]
    else:
        output[nonzero_mask] /= norm_weights[nonzero_mask]

    return output
