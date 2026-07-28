"""Shared utilities: config, logging, validators, file helpers.

Public re-exports so callers can do::

    from src.utils import AppConfig, setup_logger, get_logger
    from src.utils import is_audio_file, validate_ffmpeg_path
    from src.utils import ensure_dir, unique_output_path, sanitize_filename

Note: ``AppConfig`` requires qtpy (``QSettings``).  It is imported lazily
here so that non-GUI code (tests, CLI tools, worker modules) can import the
rest of the ``utils`` package without a Qt runtime available.
"""

from src.utils.file_utils import (
    ensure_dir,
    get_file_size_mb,
    safe_remove,
    safe_rmtree,
    sanitize_filename,
    stem_with_suffix,
    temp_wav_file,
    unique_output_path,
)
from src.utils.logger import QtLogHandler, get_logger, setup_logger
from src.utils.validators import (
    SUPPORTED_AUDIO_EXTENSIONS,
    SUPPORTED_OUTPUT_FORMATS,
    VALID_BIT_DEPTHS,
    VALID_MP3_BITRATES,
    VALID_SAMPLE_RATES,
    is_audio_file,
    validate_audio_file,
    validate_bit_depth,
    validate_ffmpeg_path,
    validate_flac_compression,
    validate_mp3_bitrate,
    validate_output_directory,
    validate_output_format,
    validate_sample_rate,
)


def __getattr__(name: str):
    """Lazy-import Qt-dependent symbols to avoid requiring qtpy at module load."""
    if name == "AppConfig":
        from src.utils.config import AppConfig  # noqa: PLC0415
        return AppConfig
    raise AttributeError(f"module 'utils' has no attribute {name!r}")


__all__ = [
    # config (lazy — requires qtpy)
    "AppConfig",
    # logger
    "QtLogHandler",
    "setup_logger",
    "get_logger",
    # file helpers
    "ensure_dir",
    "safe_remove",
    "safe_rmtree",
    "unique_output_path",
    "sanitize_filename",
    "temp_wav_file",
    "get_file_size_mb",
    "stem_with_suffix",
    # validators
    "is_audio_file",
    "validate_audio_file",
    "validate_ffmpeg_path",
    "validate_output_format",
    "validate_sample_rate",
    "validate_bit_depth",
    "validate_mp3_bitrate",
    "validate_flac_compression",
    "validate_output_directory",
    # constants
    "SUPPORTED_AUDIO_EXTENSIONS",
    "SUPPORTED_OUTPUT_FORMATS",
    "VALID_SAMPLE_RATES",
    "VALID_BIT_DEPTHS",
    "VALID_MP3_BITRATES",
]
