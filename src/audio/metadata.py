"""Audio file metadata probing via ffprobe."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("sound_processor.audio.metadata")


@dataclass
class AudioInfo:
    """Probed audio file metadata returned by :func:`probe`.

    Attributes:
        duration:    Total playback duration in seconds.
        sample_rate: Audio sample rate in Hz.
        channels:    Number of audio channels (1 = mono, 2 = stereo, …).
        format:      Container format name as reported by ffprobe
                     (e.g. ``"mp3"`` or ``"wav"``).
        codec:       Audio codec name (e.g. ``"pcm_s16le"``, ``"mp3"``).
        bit_rate:    Bit-rate in bits per second, or 0 if unknown.
        tags:        Raw metadata tag dict (title, artist, album, …).
    """

    duration: float
    sample_rate: int
    channels: int
    format: str
    codec:       str = "unknown"
    bit_rate:    int = 0
    tags:        dict[str, str] = field(default_factory=dict)

    # Added for Audio Information / V3
    bit_depth:       int | None = None
    file_size_bytes: int = 0
    peak_dbfs:       float | None = None
    rms_dbfs:        float | None = None
    integrated_lufs: float | None = None

    @property
    def duration_formatted(self) -> str:
        """Format duration as HH:MM:SS.ms."""
        mins, secs = divmod(self.duration, 60)
        hours, mins = divmod(mins, 60)
        return f"{int(hours):02d}:{int(mins):02d}:{secs:06.3f}"

    @property
    def file_size_mb(self) -> float:
        """Return file size in megabytes."""
        return self.file_size_bytes / (1024 * 1024)


class ProbeError(RuntimeError):
    """Raised when ffprobe cannot read the file or returns unexpected output."""


def probe(path: Path, ffmpeg_bin: str = "ffmpeg") -> AudioInfo:
    """Probe *path* with ffprobe and return an :class:`AudioInfo` instance.

    Uses ``ffprobe`` (derived from the *ffmpeg_bin* path or name).  Falls
    back to the system ``ffprobe`` if *ffmpeg_bin* is ``"ffmpeg"`` and
    ``ffprobe`` is on ``PATH``.

    Args:
        path:       Path to the audio file to probe.
        ffmpeg_bin: Path or name of the ``ffmpeg`` binary.  The sibling
                    ``ffprobe`` binary is located automatically.

    Returns:
        :class:`AudioInfo` populated from the first audio stream found.

    Raises:
        FileNotFoundError: If *path* does not exist.
        ProbeError:        If ffprobe cannot be found or returns an error.
    """
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")

    ffprobe_bin = _resolve_ffprobe(ffmpeg_bin)

    cmd = [
        ffprobe_bin,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    log.debug("ffprobe command: %s", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
    except FileNotFoundError:
        raise ProbeError(
            f"ffprobe not found (searched for '{ffprobe_bin}'). "
            "Install FFmpeg and set its path in Settings."
        ) from None
    except subprocess.TimeoutExpired:
        raise ProbeError(f"ffprobe timed out reading '{path}'.") from None

    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace").strip()
        raise ProbeError(f"ffprobe error for '{path}': {stderr}")

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ProbeError(f"ffprobe returned invalid JSON for '{path}': {exc}") from exc

    return _parse_probe_output(data, path)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_ffprobe(ffmpeg_bin: str) -> str:
    """Derive the ffprobe path from *ffmpeg_bin*.

    * If *ffmpeg_bin* is the bare name ``"ffmpeg"``, return ``"ffprobe"``
      (relies on it being on ``PATH``).
    * If *ffmpeg_bin* is an absolute/relative path, replace ``ffmpeg`` with
      ``ffprobe`` in the filename.
    * Verifies the result is on PATH or is a real file; raises
      :class:`ProbeError` otherwise.
    """
    if ffmpeg_bin in ("ffmpeg", ""):
        probe_bin = "ffprobe"
        if shutil.which(probe_bin) is None:
            raise ProbeError(
                "ffprobe not found on PATH. Install FFmpeg to use metadata probing."
            )
        return probe_bin

    p = Path(ffmpeg_bin)
    candidate = p.parent / p.name.replace("ffmpeg", "ffprobe")
    if candidate.is_file():
        return str(candidate)

    # Fallback: system ffprobe
    if shutil.which("ffprobe"):
        return "ffprobe"

    raise ProbeError(
        f"ffprobe binary not found near '{ffmpeg_bin}'. "
        "Ensure FFmpeg and ffprobe are installed in the same directory."
    )


def _parse_probe_output(data: dict, path: Path) -> AudioInfo:
    """Extract :class:`AudioInfo` from the raw ffprobe JSON dict."""
    streams = data.get("streams", [])
    fmt = data.get("format", {})

    # Find the first audio stream.
    audio_stream: dict | None = next(
        (s for s in streams if s.get("codec_type") == "audio"), None
    )
    if audio_stream is None:
        raise ProbeError(f"No audio stream found in '{path}'.")

    try:
        sample_rate = int(audio_stream.get("sample_rate", 0))
        channels = int(audio_stream.get("channels", 0))
        duration = float(
            audio_stream.get("duration")
            or fmt.get("duration")
            or 0.0
        )
        codec = audio_stream.get("codec_name", "unknown")
        bit_rate = int(
            audio_stream.get("bit_rate")
            or fmt.get("bit_rate")
            or 0
        )
        format_name = fmt.get("format_name", path.suffix.lstrip(".")).split(",")[0]
        
        bit_depth = None
        bps = audio_stream.get("bits_per_sample") or audio_stream.get("bits_per_raw_sample")
        if bps and str(bps).isdigit() and int(bps) > 0:
            bit_depth = int(bps)

        file_size_bytes = 0
        size_str = fmt.get("size")
        if size_str and str(size_str).isdigit():
            file_size_bytes = int(size_str)
        elif path.exists():
            file_size_bytes = path.stat().st_size

        tags: dict[str, str] = {
            k: str(v)
            for k, v in {
                **fmt.get("tags", {}),
                **audio_stream.get("tags", {}),
            }.items()
        }
    except (TypeError, ValueError) as exc:
        raise ProbeError(f"Failed to parse ffprobe output for '{path}': {exc}") from exc

    log.debug(
        "Probed '%s': %.2fs, %d Hz, %d ch, codec=%s",
        path.name, duration, sample_rate, channels, codec,
    )

    return AudioInfo(
        duration=duration,
        sample_rate=sample_rate,
        channels=channels,
        format=format_name,
        codec=codec,
        bit_rate=bit_rate,
        tags=tags,
        bit_depth=bit_depth,
        file_size_bytes=file_size_bytes,
    )
