"""Format-specific audio export engine.

:class:`ExportEngine` writes :class:`~core.audio_engine.AudioBuffer` objects
to disk in WAV, MP3, or FLAC format.  All actual I/O is delegated to the
lower-level :mod:`audio.writer` functions so encoding logic lives in one
place.
"""

from __future__ import annotations

import logging
from pathlib import Path

from src.core.audio_engine import AudioBuffer

log = logging.getLogger("sound_processor.core.exporter")


class ExportEngine:
    """Writes :class:`AudioBuffer` objects to WAV, MP3, or FLAC files.

    Args:
        ffmpeg_bin: Path or name of the ``ffmpeg`` binary used for MP3 and
                    FLAC encoding.  Defaults to ``"ffmpeg"`` (from ``PATH``).
    """

    def __init__(self, ffmpeg_bin: str = "ffmpeg") -> None:
        self._ffmpeg_bin = ffmpeg_bin

    # ------------------------------------------------------------------
    # WAV
    # ------------------------------------------------------------------

    def export_wav(
        self,
        buffer: AudioBuffer,
        path: Path,
        sample_rate: int | None = None,
        bit_depth: int = 16,
    ) -> Path:
        """Write *buffer* to a PCM WAV file at *path*.

        Args:
            buffer:      Audio data to export.
            path:        Destination file path.  Parent directory is created
                         automatically.
            sample_rate: Override the sample rate written to the file header.
                         When ``None`` the buffer's own sample rate is used.
            bit_depth:   PCM bit depth: 8, 16, 24, or 32 (default 16).

        Returns:
            Resolved *path* on success.

        Raises:
            ValueError:  If *bit_depth* is not supported.
            :class:`audio.writer.WriteError`: If soundfile write fails.
        """
        from src.audio.writer import write_wav  # deferred — avoids heavy import at startup

        sr = sample_rate if sample_rate is not None else buffer.sample_rate
        path.parent.mkdir(parents=True, exist_ok=True)

        log.info(
            "Exporting WAV: '%s' (sr=%d, bit_depth=%d, ch=%d)",
            path.name, sr, bit_depth, buffer.channels,
        )
        return write_wav(path, buffer.samples, sr, bit_depth=bit_depth)

    # ------------------------------------------------------------------
    # MP3
    # ------------------------------------------------------------------

    def export_mp3(
        self,
        buffer: AudioBuffer,
        path: Path,
        sample_rate: int | None = None,
        bitrate: int = 192,
    ) -> Path:
        """Encode *buffer* to an MP3 file via FFmpeg/libmp3lame.

        Args:
            buffer:      Audio data to export.
            path:        Destination file path.
            sample_rate: Override sample rate (``None`` uses buffer's rate).
            bitrate:     Target bitrate in kbps (e.g. 128, 192, 320).

        Returns:
            Resolved *path* on success.

        Raises:
            :class:`audio.writer.WriteError`: If FFmpeg encoding fails.
        """
        from src.audio.writer import write_mp3

        sr = sample_rate if sample_rate is not None else buffer.sample_rate
        path.parent.mkdir(parents=True, exist_ok=True)

        log.info(
            "Exporting MP3: '%s' (%d kbps, sr=%d, ch=%d)",
            path.name, bitrate, sr, buffer.channels,
        )
        return write_mp3(
            path, buffer.samples, sr,
            bitrate=bitrate, ffmpeg_bin=self._ffmpeg_bin,
        )

    # ------------------------------------------------------------------
    # FLAC
    # ------------------------------------------------------------------

    def export_flac(
        self,
        buffer: AudioBuffer,
        path: Path,
        sample_rate: int | None = None,
        compression: int = 5,
    ) -> Path:
        """Encode *buffer* to a FLAC file via FFmpeg.

        Args:
            buffer:      Audio data to export.
            path:        Destination file path.
            sample_rate: Override sample rate (``None`` uses buffer's rate).
            compression: FLAC compression level 0 (fastest) – 8 (smallest).

        Returns:
            Resolved *path* on success.

        Raises:
            :class:`audio.writer.WriteError`: If FFmpeg encoding fails.
        """
        from src.audio.writer import write_flac

        sr = sample_rate if sample_rate is not None else buffer.sample_rate
        path.parent.mkdir(parents=True, exist_ok=True)

        log.info(
            "Exporting FLAC: '%s' (compression=%d, sr=%d, ch=%d)",
            path.name, compression, sr, buffer.channels,
        )
        return write_flac(
            path, buffer.samples, sr,
            compression=compression, ffmpeg_bin=self._ffmpeg_bin,
        )

    # ------------------------------------------------------------------
    # Generic dispatcher
    # ------------------------------------------------------------------

    def export(
        self,
        buffer: AudioBuffer,
        path: Path,
        sample_rate: int | None = None,
        **kwargs,
    ) -> Path:
        """Write *buffer* to *path* using the format inferred from the extension.

        Dispatches to :meth:`export_wav`, :meth:`export_mp3`, or
        :meth:`export_flac`.  Extra *kwargs* are forwarded to the
        format-specific method (e.g. ``bit_depth=24``, ``bitrate=320``).

        Raises:
            ValueError: If the file extension is not supported.
        """
        ext = path.suffix.lower()
        if ext == ".wav":
            return self.export_wav(buffer, path, sample_rate=sample_rate, **kwargs)
        if ext == ".mp3":
            return self.export_mp3(buffer, path, sample_rate=sample_rate, **kwargs)
        if ext == ".flac":
            return self.export_flac(buffer, path, sample_rate=sample_rate, **kwargs)
        raise ValueError(
            f"Unsupported export format '{ext}' for '{path}'. "
            "Supported: .wav, .mp3, .flac"
        )
