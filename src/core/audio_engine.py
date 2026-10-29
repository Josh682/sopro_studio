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


def _default_ffmpeg_bin() -> str:
    """Resolve the default ffmpeg binary path safely."""
    try:
        from src.utils.config import AppConfig
        return AppConfig().ffmpeg_path
    except Exception:
        return "ffmpeg"


# ---------------------------------------------------------------------------
# Data container & Deep Module
# ---------------------------------------------------------------------------

@dataclass
class AudioBuffer:
    """In-memory audio data with associated metadata and manipulation operations.

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
    def duration_sec(self) -> float:
        """Alias for duration in seconds."""
        return self.duration

    @property
    def num_frames(self) -> int:
        """Number of audio frames."""
        return self.samples.shape[0]

    @property
    def is_mono(self) -> bool:
        """True when the buffer contains a single channel."""
        return self.channels == 1

    # ------------------------------------------------------------------
    # I/O Operations
    # ------------------------------------------------------------------

    @classmethod
    def load(
        cls,
        path: Path | str,
        target_sr: int | None = None,
        mono: bool = False,
        start_sec: float | None = None,
        duration_sec: float | None = None,
        max_duration_sec: float | None = None,
        ffmpeg_bin: str | None = None,
    ) -> "AudioBuffer":
        """Decode *path* and return an :class:`AudioBuffer`.

        Supports any format recognised by FFmpeg (MP3, WAV, FLAC, OGG, …).
        Optional *target_sr* performs high-quality resampling during decode.
        Optional *start_sec* and *duration_sec* perform fast sliced decoding.

        Args:
            path:         Path to the audio file.
            target_sr:    Desired sample rate in Hz (None keeps native rate).
            mono:         If True, mixes down all channels to mono.
            start_sec:    Start offset in seconds for fast seeking.
            duration_sec: Duration in seconds to decode from start.
            ffmpeg_bin:   Path or name of ffmpeg binary (None resolves default).

        Returns:
            :class:`AudioBuffer` with float32 samples in ``[-1.0, 1.0]``.
        """
        from src.audio.loader import load_audio

        path = Path(path)
        bin_path = ffmpeg_bin or _default_ffmpeg_bin()
        effective_duration = duration_sec if duration_sec is not None else max_duration_sec
        samples, sr = load_audio(
            path=path,
            sample_rate=target_sr,
            mono=mono,
            start_sec=start_sec,
            duration_sec=effective_duration,
            ffmpeg_bin=bin_path,
        )
        channels = 1 if samples.ndim == 1 else samples.shape[1]
        log.debug("AudioBuffer.load '%s': sr=%d, ch=%d, shape=%s", path.name, sr, channels, samples.shape)
        return cls(samples=samples, sample_rate=sr, channels=channels)

    def save(
        self,
        path: Path | str,
        format: str | None = None,
        sample_rate: int | None = None,
        bit_depth: int = 16,
        bitrate: int = 192,
        compression: int = 5,
        ffmpeg_bin: str | None = None,
    ) -> Path:
        """Write buffer to disk in WAV, MP3, or FLAC format.

        If *format* is None, the format is inferred from *path* suffix.
        Defaults to WAV if no suffix is specified or recognized.

        Args:
            path:        Destination path. Parent directories are created automatically.
            format:      Explicit format ('wav', 'mp3', 'flac'). Optional.
            sample_rate: Override sample rate (resamples before saving if different).
            bit_depth:   PCM bit depth for WAV (8, 16, 24, 32).
            bitrate:     Target bitrate in kbps for MP3 (128, 192, 320).
            compression: Compression level for FLAC (0-8).
            ffmpeg_bin:  Path or name of ffmpeg binary.

        Returns:
            The resolved output :class:`Path`.
        """
        target_path = Path(path)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        fmt = format.lower().lstrip(".") if format else target_path.suffix.lower().lstrip(".")
        if not fmt:
            fmt = "wav"

        if not target_path.suffix:
            target_path = target_path.with_suffix(f".{fmt}")

        bin_path = ffmpeg_bin or _default_ffmpeg_bin()
        sr = sample_rate if sample_rate is not None else self.sample_rate

        try:
            bit_depth = int(bit_depth)
        except (ValueError, TypeError):
            bit_depth = 16

        try:
            bitrate = int(bitrate)
        except (ValueError, TypeError):
            bitrate = 192

        try:
            compression = int(compression)
        except (ValueError, TypeError):
            compression = 5

        samples_to_save = self.samples
        if sample_rate is not None and sample_rate != self.sample_rate:
            samples_to_save = _resample_samples(self.samples, self.sample_rate, sample_rate)

        if fmt == "wav":
            from src.audio.writer import write_wav
            return write_wav(target_path, samples_to_save, sr, bit_depth=bit_depth)
        elif fmt == "mp3":
            from src.audio.writer import write_mp3
            return write_mp3(target_path, samples_to_save, sr, bitrate=bitrate, ffmpeg_bin=bin_path)
        elif fmt == "flac":
            from src.audio.writer import write_flac
            return write_flac(target_path, samples_to_save, sr, compression=compression, ffmpeg_bin=bin_path)
        else:
            raise ValueError(
                f"Unsupported export format '{fmt}' for '{target_path}'. "
                "Supported formats: .wav, .mp3, .flac"
            )

    # ------------------------------------------------------------------
    # Transformations
    # ------------------------------------------------------------------

    def resample(self, target_sr: int) -> "AudioBuffer":
        """Resample buffer to *target_sr* Hz."""
        if self.sample_rate == target_sr:
            return AudioBuffer(self.samples.copy(), target_sr, self.channels)

        resampled = _resample_samples(self.samples, self.sample_rate, target_sr)
        channels = 1 if resampled.ndim == 1 else resampled.shape[1]
        log.debug("Resampled %d → %d Hz, shape %s → %s", self.sample_rate, target_sr, self.samples.shape, resampled.shape)
        return AudioBuffer(samples=resampled, sample_rate=target_sr, channels=channels)

    def normalize(self, target_peak: float = 0.99) -> "AudioBuffer":
        """Peak-normalise buffer so the loudest sample reaches *target_peak*."""
        peak = float(np.abs(self.samples).max()) if self.samples.size > 0 else 0.0
        if peak == 0.0:
            log.debug("normalize: buffer is silent, skipping.")
            return AudioBuffer(self.samples.copy(), self.sample_rate, self.channels)

        factor = target_peak / peak
        normalised = (self.samples * factor).astype(np.float32)
        log.debug("normalize: peak=%.4f, factor=%.4f", peak, factor)
        return AudioBuffer(samples=normalised, sample_rate=self.sample_rate, channels=self.channels)

    def to_mono(self) -> "AudioBuffer":
        """Return a new mono :class:`AudioBuffer` by averaging all channels."""
        if self.is_mono:
            return AudioBuffer(self.samples.copy(), self.sample_rate, 1)
        mono = self.samples.mean(axis=1).astype(np.float32)
        return AudioBuffer(mono, self.sample_rate, 1)

    def slice(self, start_sec: float, end_sec: float) -> "AudioBuffer":
        """Extract a time slice [start_sec, end_sec] in seconds."""
        if start_sec < 0.0:
            start_sec = 0.0
        if end_sec < start_sec:
            raise ValueError(f"end_sec ({end_sec}) must be >= start_sec ({start_sec})")

        total_frames = self.samples.shape[0]
        start_frame = min(int(start_sec * self.sample_rate), total_frames)
        end_frame = min(int(end_sec * self.sample_rate), total_frames)

        sliced = self.samples[start_frame:end_frame].copy()
        return AudioBuffer(samples=sliced, sample_rate=self.sample_rate, channels=self.channels)

    def apply_gain(self, db: float) -> "AudioBuffer":
        """Apply gain in decibels (dB) to buffer."""
        if db == 0.0:
            return AudioBuffer(samples=self.samples.copy(), sample_rate=self.sample_rate, channels=self.channels)
        factor = 10.0 ** (db / 20.0)
        gained = (self.samples * factor).astype(np.float32)
        return AudioBuffer(samples=gained, sample_rate=self.sample_rate, channels=self.channels)

    def __repr__(self) -> str:
        dur = f"{self.duration:.2f}s"
        return (
            f"AudioBuffer(sr={self.sample_rate}, ch={self.channels}, "
            f"shape={self.samples.shape}, dur={dur})"
        )


# ---------------------------------------------------------------------------
# Backward Compatibility Adapter
# ---------------------------------------------------------------------------

class AudioEngine:
    """Backward-compatibility adapter delegating audio I/O to :class:`AudioBuffer`.

    Args:
        ffmpeg_bin: Path or name of the ``ffmpeg`` binary. Defaults to resolved default.
    """

    def __init__(self, ffmpeg_bin: str | None = None) -> None:
        self._ffmpeg_bin = ffmpeg_bin or _default_ffmpeg_bin()

    def load(self, path: Path, target_sr: int | None = None) -> AudioBuffer:
        """Decode *path* and return an :class:`AudioBuffer`."""
        return AudioBuffer.load(path, target_sr=target_sr, ffmpeg_bin=self._ffmpeg_bin)

    def decode_via_ffmpeg(self, path: Path) -> AudioBuffer:
        """Alias for :meth:`load`."""
        return self.load(path)

    def resample(self, buffer: AudioBuffer, target_sr: int) -> AudioBuffer:
        """Resample *buffer* to *target_sr* Hz."""
        return buffer.resample(target_sr)

    def normalize(self, buffer: AudioBuffer, target_peak: float = 0.99) -> AudioBuffer:
        """Peak-normalise *buffer* to *target_peak*."""
        return buffer.normalize(target_peak)


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
