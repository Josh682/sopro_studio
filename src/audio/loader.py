"""FFmpeg-backed audio decode: loads any supported format into a numpy array.

The loader uses FFmpeg's ``rawvideo`` / ``pcm_f32le`` pipe output to produce
a float32 numpy array, avoiding any intermediate file on disk.  An optional
target sample rate triggers an automatic resample via the ``aresample`` filter.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import numpy as np

log = logging.getLogger("sound_processor.audio.loader")


class LoadError(RuntimeError):
    """Raised when FFmpeg cannot decode the audio file."""


def load_audio(
    path: Path,
    sample_rate: int | None = None,
    mono: bool = False,
    ffmpeg_bin: str = "ffmpeg",
) -> tuple[np.ndarray, int]:
    """Decode *path* to a float32 numpy array via FFmpeg.

    The returned array has shape ``(samples, channels)`` for stereo and
    ``(samples,)`` for mono (or when *mono* is True).  All sample values
    are normalised to the range ``[-1.0, 1.0]``.

    Args:
        path:        Path to the audio file.
        sample_rate: Target sample rate in Hz.  If *None* the file's native
                     rate is preserved.  FFmpeg performs high-quality
                     resampling internally when a rate is specified.
        mono:        If *True*, down-mix all channels to mono before
                     returning.
        ffmpeg_bin:  Path or name of the ``ffmpeg`` binary.

    Returns:
        ``(samples_array, actual_sample_rate)`` tuple.

    Raises:
        FileNotFoundError: If *path* does not exist.
        LoadError:         If FFmpeg cannot be found or decoding fails.
    """
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")

    # Probe native sample rate & channel count so we can shape the output.
    native_sr, native_channels = _probe_stream_info(path, ffmpeg_bin)
    target_sr = sample_rate if sample_rate is not None else native_sr

    cmd = _build_decode_command(path, target_sr, mono, ffmpeg_bin)
    log.debug("FFmpeg decode command: %s", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=300,
        )
    except FileNotFoundError:
        raise LoadError(
            f"FFmpeg not found (searched for '{ffmpeg_bin}'). "
            "Install FFmpeg and set its path in Settings."
        ) from None
    except subprocess.TimeoutExpired:
        raise LoadError(f"FFmpeg timed out while decoding '{path}'.") from None

    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace").strip()
        raise LoadError(f"FFmpeg error decoding '{path}': {stderr}")

    raw_bytes = result.stdout
    if not raw_bytes:
        raise LoadError(f"FFmpeg returned no audio data for '{path}'.")

    # Interpret raw bytes as float32 PCM.
    samples = np.frombuffer(raw_bytes, dtype=np.float32)

    out_channels = 1 if mono else native_channels
    if out_channels > 1:
        # Reshape to (num_frames, channels).
        num_frames = samples.size // out_channels
        samples = samples[: num_frames * out_channels].reshape(num_frames, out_channels)
    # else: keep as 1-D array for mono

    log.debug(
        "Loaded '%s': shape=%s, sr=%d, channels=%d",
        path.name, samples.shape, target_sr, out_channels,
    )
    return samples, target_sr


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_decode_command(
    path: Path,
    target_sr: int,
    mono: bool,
    ffmpeg_bin: str,
) -> list[str]:
    """Build the FFmpeg command that writes raw float32 PCM to stdout."""
    cmd = [
        ffmpeg_bin,
        "-y",                       # overwrite (no-op for stdout)
        "-i", str(path),
        "-f", "f32le",              # raw little-endian float32
        "-acodec", "pcm_f32le",
        "-ar", str(target_sr),
    ]
    if mono:
        cmd += ["-ac", "1"]
    cmd += ["pipe:1"]              # write to stdout
    return cmd


def _probe_stream_info(path: Path, ffmpeg_bin: str) -> tuple[int, int]:
    """Return (sample_rate, channels) for the first audio stream in *path*.

    Uses a lightweight ffprobe call.  Falls back to (44100, 2) on any error
    so that decoding can still proceed.
    """
    try:
        from src.audio.metadata import probe  # local import to avoid circular deps
        info = probe(path, ffmpeg_bin)
        return info.sample_rate, info.channels
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "Could not probe '%s' (%s). Assuming 44100 Hz stereo.",
            path.name, exc,
        )
        return 44100, 2
