"""Input validation helpers for audio files, paths, and encoding parameters."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

SUPPORTED_AUDIO_EXTENSIONS: frozenset[str] = frozenset(
    {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".opus", ".wma", ".aiff", ".aif"}
)

SUPPORTED_OUTPUT_FORMATS: frozenset[str] = frozenset({"wav", "mp3", "flac"})

VALID_SAMPLE_RATES: frozenset[int] = frozenset(
    {8000, 11025, 16000, 22050, 32000, 44100, 48000, 88200, 96000, 176400, 192000}
)

VALID_BIT_DEPTHS: frozenset[int] = frozenset({8, 16, 24, 32})

VALID_MP3_BITRATES: frozenset[int] = frozenset(
    {32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320}
)

VALID_FLAC_COMPRESSION: range = range(0, 9)  # 0-8


def is_audio_file(path: Path) -> bool:
    """Return True if *path* points to an existing file with a known audio extension."""
    return path.is_file() and path.suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS


def validate_audio_file(path: Path) -> tuple[bool, str]:
    """Validate an audio input file and return (ok, error_message).

    Returns (True, "") on success, or (False, human-readable reason) on failure.
    """
    if not path.exists():
        return False, f"File not found: {path}"
    if not path.is_file():
        return False, f"Path is not a file: {path}"
    if path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
        return False, (
            f"Unsupported extension '{path.suffix}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_AUDIO_EXTENSIONS))}"
        )
    if path.stat().st_size == 0:
        return False, f"File is empty: {path}"
    return True, ""


def validate_output_format(fmt: str) -> tuple[bool, str]:
    """Validate that *fmt* is a supported output format."""
    if fmt.lower() not in SUPPORTED_OUTPUT_FORMATS:
        return False, (
            f"Unsupported output format '{fmt}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_OUTPUT_FORMATS))}"
        )
    return True, ""


def validate_sample_rate(sample_rate: int) -> tuple[bool, str]:
    """Validate that *sample_rate* is a standard PCM sample rate."""
    if sample_rate not in VALID_SAMPLE_RATES:
        return False, (
            f"Invalid sample rate {sample_rate} Hz. "
            f"Supported: {', '.join(str(r) for r in sorted(VALID_SAMPLE_RATES))}"
        )
    return True, ""


def validate_bit_depth(bit_depth: int) -> tuple[bool, str]:
    """Validate WAV bit depth."""
    if bit_depth not in VALID_BIT_DEPTHS:
        return False, (
            f"Invalid bit depth {bit_depth}. "
            f"Supported: {', '.join(str(b) for b in sorted(VALID_BIT_DEPTHS))}"
        )
    return True, ""


def validate_mp3_bitrate(bitrate: int) -> tuple[bool, str]:
    """Validate MP3 bitrate in kbps."""
    if bitrate not in VALID_MP3_BITRATES:
        return False, (
            f"Invalid MP3 bitrate {bitrate} kbps. "
            f"Supported: {', '.join(str(b) for b in sorted(VALID_MP3_BITRATES))}"
        )
    return True, ""


def validate_flac_compression(level: int) -> tuple[bool, str]:
    """Validate FLAC compression level (0–8)."""
    if level not in VALID_FLAC_COMPRESSION:
        return False, f"FLAC compression level must be 0–8, got {level}."
    return True, ""


def validate_ffmpeg_path(path: str) -> bool:
    """Return True if the given path or name resolves to a working ffmpeg binary."""
    if path in ("ffmpeg", ""):
        return shutil.which("ffmpeg") is not None
    resolved = Path(path)
    if not resolved.is_file():
        return False
    try:
        result = subprocess.run(
            [str(resolved), "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def validate_output_directory(path: Path) -> tuple[bool, str]:
    """Validate that *path* is a writable directory (creates it if missing)."""
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return False, f"Cannot create output directory: {exc}"
    if not path.is_dir():
        return False, f"Output path is not a directory: {path}"
    return True, ""
