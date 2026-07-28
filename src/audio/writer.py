"""Format-specific audio writing via soundfile (WAV) and FFmpeg (MP3, FLAC).

WAV files are written directly with *soundfile* for maximum control over
bit depth and sample rate.  MP3 and FLAC output is produced by piping raw
PCM into an FFmpeg subprocess, avoiding any temporary file on disk.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

log = logging.getLogger("sound_processor.audio.writer")


class WriteError(RuntimeError):
    """Raised when audio cannot be written to the requested path."""


# ---------------------------------------------------------------------------
# WAV
# ---------------------------------------------------------------------------

_BIT_DEPTH_SUBTYPES: dict[int, str] = {
    8:  "PCM_U8",
    16: "PCM_16",
    24: "PCM_24",
    32: "PCM_32",
}


def write_wav(
    path: Path,
    samples: np.ndarray,
    sample_rate: int,
    bit_depth: int = 16,
) -> Path:
    """Write *samples* to a WAV file at *path* using soundfile.

    Args:
        path:        Output file path (parent directory must exist).
        samples:     Float32 or integer numpy array, shape ``(frames,)``
                     for mono or ``(frames, channels)`` for multi-channel.
        sample_rate: Sample rate in Hz.
        bit_depth:   PCM bit depth — 8, 16, 24, or 32 (default 16).

    Returns:
        The resolved *path* on success.

    Raises:
        ValueError:  If *bit_depth* is not supported.
        WriteError:  If soundfile fails to write the file.
    """
    subtype = _BIT_DEPTH_SUBTYPES.get(bit_depth)
    if subtype is None:
        raise ValueError(
            f"Unsupported bit depth: {bit_depth}. "
            f"Supported: {sorted(_BIT_DEPTH_SUBTYPES)}"
        )

    # Ensure parent directory exists.
    path.parent.mkdir(parents=True, exist_ok=True)

    # Normalise to float32 for consistent soundfile behaviour.
    data = _ensure_float32(samples)

    try:
        sf.write(str(path), data, sample_rate, subtype=subtype)
    except Exception as exc:
        raise WriteError(f"Failed to write WAV '{path}': {exc}") from exc

    log.debug(
        "Wrote WAV '%s': %d Hz, %d-bit, shape=%s",
        path.name, sample_rate, bit_depth, data.shape,
    )
    return path


# ---------------------------------------------------------------------------
# MP3
# ---------------------------------------------------------------------------

def write_mp3(
    path: Path,
    samples: np.ndarray,
    sample_rate: int,
    bitrate: int = 192,
    ffmpeg_bin: str = "ffmpeg",
) -> Path:
    """Encode *samples* to an MP3 file at *path* via FFmpeg.

    Args:
        path:        Output file path.
        samples:     Float32 numpy array, shape ``(frames,)`` or
                     ``(frames, channels)``.
        sample_rate: Sample rate in Hz.
        bitrate:     MP3 target bitrate in kbps (e.g. 128, 192, 320).
        ffmpeg_bin:  Path or name of the ``ffmpeg`` binary.

    Returns:
        The resolved *path* on success.

    Raises:
        WriteError: If FFmpeg cannot be found or encoding fails.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    channels = _channel_count(samples)
    raw_bytes = _samples_to_bytes(samples)

    cmd = [
        ffmpeg_bin,
        "-y",
        "-f", "f32le",
        "-ar", str(sample_rate),
        "-ac", str(channels),
        "-i", "pipe:0",             # read raw PCM from stdin
        "-codec:a", "libmp3lame",
        "-b:a", f"{bitrate}k",
        str(path),
    ]
    log.debug("FFmpeg MP3 encode: %s", " ".join(cmd))

    _run_ffmpeg(cmd, raw_bytes, path)
    log.debug("Wrote MP3 '%s': %d kbps, %d Hz", path.name, bitrate, sample_rate)
    return path


# ---------------------------------------------------------------------------
# FLAC
# ---------------------------------------------------------------------------

def write_flac(
    path: Path,
    samples: np.ndarray,
    sample_rate: int,
    compression: int = 5,
    ffmpeg_bin: str = "ffmpeg",
) -> Path:
    """Encode *samples* to a FLAC file at *path* via FFmpeg.

    Args:
        path:         Output file path.
        samples:      Float32 numpy array, shape ``(frames,)`` or
                      ``(frames, channels)``.
        sample_rate:  Sample rate in Hz.
        compression:  FLAC compression level 0 (fastest) – 8 (smallest).
        ffmpeg_bin:   Path or name of the ``ffmpeg`` binary.

    Returns:
        The resolved *path* on success.

    Raises:
        WriteError: If FFmpeg cannot be found or encoding fails.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    channels = _channel_count(samples)
    raw_bytes = _samples_to_bytes(samples)

    cmd = [
        ffmpeg_bin,
        "-y",
        "-f", "f32le",
        "-ar", str(sample_rate),
        "-ac", str(channels),
        "-i", "pipe:0",
        "-codec:a", "flac",
        "-compression_level", str(compression),
        str(path),
    ]
    log.debug("FFmpeg FLAC encode: %s", " ".join(cmd))

    _run_ffmpeg(cmd, raw_bytes, path)
    log.debug(
        "Wrote FLAC '%s': compression=%d, %d Hz",
        path.name, compression, sample_rate,
    )
    return path


# ---------------------------------------------------------------------------
# Convenience dispatcher
# ---------------------------------------------------------------------------

def write_audio(
    path: Path,
    samples: np.ndarray,
    sample_rate: int,
    ffmpeg_bin: str = "ffmpeg",
    **kwargs,
) -> Path:
    """Write audio to *path* using the format inferred from the file extension.

    Dispatches to :func:`write_wav`, :func:`write_mp3`, or :func:`write_flac`
    based on ``path.suffix``.

    Extra *kwargs* are forwarded to the format-specific writer
    (e.g. ``bit_depth=24`` for WAV, ``bitrate=320`` for MP3).

    Raises:
        WriteError: If the extension is not supported.
    """
    ext = path.suffix.lower()
    if ext == ".wav":
        return write_wav(path, samples, sample_rate, **kwargs)
    if ext == ".mp3":
        return write_mp3(path, samples, sample_rate, ffmpeg_bin=ffmpeg_bin, **kwargs)
    if ext == ".flac":
        return write_flac(path, samples, sample_rate, ffmpeg_bin=ffmpeg_bin, **kwargs)
    raise WriteError(
        f"Cannot write to '{path}': unsupported extension '{ext}'. "
        "Supported: .wav, .mp3, .flac"
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ensure_float32(samples: np.ndarray) -> np.ndarray:
    """Convert *samples* to float32 if not already."""
    if samples.dtype == np.float32:
        return samples
    if np.issubdtype(samples.dtype, np.integer):
        info = np.iinfo(samples.dtype)
        return (samples.astype(np.float32) / info.max).clip(-1.0, 1.0)
    return samples.astype(np.float32)


def _channel_count(samples: np.ndarray) -> int:
    """Return the number of channels from a samples array."""
    return 1 if samples.ndim == 1 else samples.shape[1]


def _samples_to_bytes(samples: np.ndarray) -> bytes:
    """Convert samples to raw float32 little-endian bytes for FFmpeg stdin."""
    data = _ensure_float32(samples)
    # FFmpeg expects interleaved samples: flatten (frames, channels) → 1-D.
    return data.flatten(order="C").tobytes()


def _run_ffmpeg(cmd: list[str], stdin_data: bytes, out_path: Path) -> None:
    """Run an FFmpeg encode command, piping *stdin_data* and raising on error."""
    try:
        result = subprocess.run(
            cmd,
            input=stdin_data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=600,
        )
    except FileNotFoundError:
        raise WriteError(
            f"FFmpeg not found ('{cmd[0]}'). Install FFmpeg and set its path in Settings."
        ) from None
    except subprocess.TimeoutExpired:
        raise WriteError(f"FFmpeg timed out encoding '{out_path}'.") from None

    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace").strip()
        raise WriteError(f"FFmpeg error encoding '{out_path}': {stderr}")
