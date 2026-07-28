"""Single entry point for audio I/O: load, resample, and normalize.

:class:`AudioEngine` is the central hub that all higher-level components
(converter, separator) use to obtain audio data.  It delegates decode work to
:mod:`audio.loader` (FFmpeg subprocess) and resampling to *torchaudio* when
available, with a *librosa* fallback for environments without Torch.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np

log = logging.getLogger("sound_processor.core.audio_engine")


# ---------------------------------------------------------------------------
# Data container
# ---------------------------------------------------------------------------

@dataclass
class AudioBuffer:
    """In-memory audio data with associated metadata.

    Attributes:
        samples:     Float32 numpy array shaped ``(frames,)`` for mono or
                     ``(frames, channels)`` for multi-channel audio.
                     Sample values are always in ``[-1.0, 1.0]``.
        sample_rate: Sample rate of *samples* in Hz.
        channels:    Number of audio channels (1 = mono, 2 = stereo, …).
    """

    samples: np.ndarray
    sample_rate: int
    channels: int

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    @property
    def duration(self) -> float:
        """Playback duration in seconds."""
        frames = self.samples.shape[0]
        return frames / self.sample_rate if self.sample_rate else 0.0

    @property
    def is_mono(self) -> bool:
        """True when the buffer contains a single channel."""
        return self.channels == 1

    def to_mono(self) -> "AudioBuffer":
        """Return a new mono :class:`AudioBuffer` by averaging all channels."""
        if self.is_mono:
            return AudioBuffer(self.samples.copy(), self.sample_rate, 1)
        mono = self.samples.mean(axis=1)
        return AudioBuffer(mono, self.sample_rate, 1)

    def __repr__(self) -> str:
        dur = f"{self.duration:.2f}s"
        return (
            f"AudioBuffer(sr={self.sample_rate}, ch={self.channels}, "
            f"shape={self.samples.shape}, dur={dur})"
        )


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class AudioEngine:
    """Shared audio engine for loading, resampling, normalising audio.

    All heavy I/O is delegated to the ``audio`` package.  The engine holds
    no persistent state; it is safe to share a single instance across
    multiple workers.

    Args:
        ffmpeg_bin: Path or name of the ``ffmpeg`` binary used for decoding.
                    Defaults to ``"ffmpeg"`` (resolved from ``PATH``).
    """

    def __init__(self, ffmpeg_bin: str = "ffmpeg") -> None:
        self._ffmpeg_bin = ffmpeg_bin

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, path: Path, target_sr: int | None = None) -> AudioBuffer:
        """Decode *path* and return an :class:`AudioBuffer`.

        Supports any format recognised by FFmpeg (MP3, WAV, FLAC, OGG, …).
        An optional *target_sr* triggers high-quality resampling inside
        FFmpeg before the data is returned.

        Args:
            path:      Path to the audio file.
            target_sr: Desired sample rate.  ``None`` preserves the native rate.

        Returns:
            :class:`AudioBuffer` with float32 samples in ``[-1.0, 1.0]``.

        Raises:
            FileNotFoundError: If *path* does not exist.
            :class:`audio.loader.LoadError`: If FFmpeg decoding fails.
        """
        from src.audio.loader import load_audio  # deferred to avoid circular at import time

        samples, sr = load_audio(path, sample_rate=target_sr, ffmpeg_bin=self._ffmpeg_bin)
        channels = 1 if samples.ndim == 1 else samples.shape[1]

        log.debug("Loaded '%s': sr=%d, ch=%d, shape=%s", path.name, sr, channels, samples.shape)
        return AudioBuffer(samples=samples, sample_rate=sr, channels=channels)

    def decode_via_ffmpeg(self, path: Path) -> AudioBuffer:
        """Alias for :meth:`load` — explicitly signals FFmpeg is used.

        Provided for callers that want to be explicit about the decode path
        (e.g. the separator engine).
        """
        return self.load(path)

    def resample(self, buffer: AudioBuffer, target_sr: int) -> AudioBuffer:
        """Resample *buffer* to *target_sr* Hz.

        Uses *torchaudio* (polyphase resampler) when available; falls back to
        *librosa* otherwise.  Returns *buffer* unchanged when
        ``buffer.sample_rate == target_sr``.

        Args:
            buffer:    Source audio buffer.
            target_sr: Desired output sample rate in Hz.

        Returns:
            New :class:`AudioBuffer` at *target_sr*.
        """
        if buffer.sample_rate == target_sr:
            return AudioBuffer(buffer.samples.copy(), target_sr, buffer.channels)

        resampled = _resample_samples(buffer.samples, buffer.sample_rate, target_sr)
        channels = 1 if resampled.ndim == 1 else resampled.shape[1]
        log.debug(
            "Resampled %d → %d Hz, shape %s → %s",
            buffer.sample_rate, target_sr, buffer.samples.shape, resampled.shape,
        )
        return AudioBuffer(samples=resampled, sample_rate=target_sr, channels=channels)

    def normalize(self, buffer: AudioBuffer, target_peak: float = 0.99) -> AudioBuffer:
        """Peak-normalise *buffer* so the loudest sample reaches *target_peak*.

        If the buffer is silent (all zeros) it is returned unchanged.

        Args:
            buffer:      Source audio buffer.
            target_peak: Peak amplitude to normalise to (default 0.99 — just
                         below digital full-scale to prevent clipping).

        Returns:
            New :class:`AudioBuffer` with normalised samples.
        """
        peak = float(np.abs(buffer.samples).max())
        if peak == 0.0:
            log.debug("normalize: buffer is silent, skipping.")
            return AudioBuffer(buffer.samples.copy(), buffer.sample_rate, buffer.channels)

        factor = target_peak / peak
        normalised = (buffer.samples * factor).astype(np.float32)
        log.debug("normalize: peak=%.4f, factor=%.4f", peak, factor)
        return AudioBuffer(samples=normalised, sample_rate=buffer.sample_rate, channels=buffer.channels)


# ---------------------------------------------------------------------------
# Resampling back-end helpers
# ---------------------------------------------------------------------------

def _resample_samples(
    samples: np.ndarray,
    orig_sr: int,
    target_sr: int,
) -> np.ndarray:
    """Resample *samples* from *orig_sr* to *target_sr*.

    Tries *torchaudio* first (best quality, GPU-optional), then *librosa*,
    and finally a simple scipy-based fallback.

    Args:
        samples:   Float32 array ``(frames,)`` or ``(frames, channels)``.
        orig_sr:   Source sample rate.
        target_sr: Target sample rate.

    Returns:
        Float32 resampled array preserving the channel layout of *samples*.
    """
    # --- torchaudio (preferred) -----------------------------------------
    try:
        import torch
        import torchaudio.functional as F  # type: ignore[import]

        # torchaudio expects (channels, frames) — convert as needed.
        if samples.ndim == 1:
            t = torch.from_numpy(samples).unsqueeze(0)           # (1, frames)
            out = F.resample(t, orig_sr, target_sr)
            return out.squeeze(0).numpy()
        else:
            t = torch.from_numpy(samples.T.copy())               # (ch, frames)
            out = F.resample(t, orig_sr, target_sr)
            return out.numpy().T                                  # back to (frames, ch)

    except ImportError:
        pass  # torchaudio not available

    # --- librosa fallback -----------------------------------------------
    try:
        import librosa  # type: ignore[import]

        if samples.ndim == 1:
            return librosa.resample(samples, orig_sr=orig_sr, target_sr=target_sr)
        else:
            # resample each channel independently
            resampled_channels = [
                librosa.resample(samples[:, ch], orig_sr=orig_sr, target_sr=target_sr)
                for ch in range(samples.shape[1])
            ]
            return np.stack(resampled_channels, axis=1)

    except ImportError:
        pass  # librosa not available

    # --- scipy fallback (always available in CPython) -------------------
    try:
        from scipy.signal import resample_poly  # type: ignore[import]
        from math import gcd

        g = gcd(orig_sr, target_sr)
        up, down = target_sr // g, orig_sr // g

        if samples.ndim == 1:
            return resample_poly(samples, up, down).astype(np.float32)
        else:
            resampled_channels = [
                resample_poly(samples[:, ch], up, down).astype(np.float32)
                for ch in range(samples.shape[1])
            ]
            return np.stack(resampled_channels, axis=1)

    except ImportError:
        pass

    # --- Minimal integer-ratio fallback (nearest-neighbour) -------------
    log.warning(
        "No resampling library found (torchaudio, librosa, scipy). "
        "Falling back to nearest-neighbour — quality may be poor."
    )
    ratio = target_sr / orig_sr
    num_frames_in = samples.shape[0]
    num_frames_out = int(round(num_frames_in * ratio))
    indices = (np.arange(num_frames_out) / ratio).astype(int).clip(0, num_frames_in - 1)
    return samples[indices].astype(np.float32)
