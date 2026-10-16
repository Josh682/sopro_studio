"""Format-specific audio export engine.

:class:`ExportEngine` is maintained as a backward-compatibility adapter
delegating to :meth:`AudioBuffer.save`.
"""

from __future__ import annotations

import logging
from pathlib import Path

from src.core.audio_engine import AudioBuffer

log = logging.getLogger("sound_processor.core.exporter")


class ExportEngine:
    """Backward-compatibility adapter delegating audio export to :class:`AudioBuffer`.

    Args:
        ffmpeg_bin: Path or name of the ``ffmpeg`` binary used for MP3 and
                    FLAC encoding. Defaults to ``"ffmpeg"``.
    """

    def __init__(self, ffmpeg_bin: str | None = None) -> None:
        self._ffmpeg_bin = ffmpeg_bin

    def export_wav(
        self,
        buffer: AudioBuffer,
        path: Path,
        sample_rate: int | None = None,
        bit_depth: int = 16,
    ) -> Path:
        """Write *buffer* to a PCM WAV file at *path*."""
        return buffer.save(
            path=path,
            format="wav",
            sample_rate=sample_rate,
            bit_depth=bit_depth,
            ffmpeg_bin=self._ffmpeg_bin,
        )

    def export_mp3(
        self,
        buffer: AudioBuffer,
        path: Path,
        sample_rate: int | None = None,
        bitrate: int = 192,
    ) -> Path:
        """Encode *buffer* to an MP3 file via FFmpeg/libmp3lame."""
        return buffer.save(
            path=path,
            format="mp3",
            sample_rate=sample_rate,
            bitrate=bitrate,
            ffmpeg_bin=self._ffmpeg_bin,
        )

    def export_flac(
        self,
        buffer: AudioBuffer,
        path: Path,
        sample_rate: int | None = None,
        compression: int = 5,
    ) -> Path:
        """Encode *buffer* to a FLAC file via FFmpeg."""
        return buffer.save(
            path=path,
            format="flac",
            sample_rate=sample_rate,
            compression=compression,
            ffmpeg_bin=self._ffmpeg_bin,
        )

    def export(
        self,
        buffer: AudioBuffer,
        path: Path,
        sample_rate: int | None = None,
        **kwargs,
    ) -> Path:
        """Write *buffer* to *path* using the format inferred from the extension or kwargs."""
        return buffer.save(
            path=path,
            sample_rate=sample_rate,
            ffmpeg_bin=self._ffmpeg_bin,
            **kwargs,
        )

    def export_by_format(
        self,
        buffer: AudioBuffer,
        path: Path,
        fmt: str,
        sample_rate: int | None = None,
        **kwargs,
    ) -> Path:
        """Write *buffer* to *path* using an explicit format string."""
        return buffer.save(
            path=path,
            format=fmt,
            sample_rate=sample_rate,
            ffmpeg_bin=self._ffmpeg_bin,
            **kwargs,
        )
