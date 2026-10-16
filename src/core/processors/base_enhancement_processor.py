"""Backward-compatibility shim for single-file enhancement processors.

Deprecated: Inherit directly from BaseProcessor and use src.audio.dsp.process_in_chunks.
"""

from __future__ import annotations

import abc
import logging
import threading
from pathlib import Path
from typing import Any, Callable

import numpy as np

from src.audio.dsp import process_in_chunks
from src.core.audio_engine import AudioBuffer, AudioEngine
from src.core.exporter import ExportEngine
from src.core.processors.base_processor import BaseProcessor, ProcessingMode
from src.utils.config import AppConfig

log = logging.getLogger("sound_processor.core.processors.base_enhancement")


class BaseEnhancementProcessor(BaseProcessor):
    """Backward-compatibility base class for single-file enhancement processors.
    
    Deprecated: Prefer subclassing BaseProcessor directly and using
    src.audio.dsp.process_in_chunks for overlapping window operations.
    """

    processing_mode = ProcessingMode.FILE

    def __init__(
        self,
        engine: AudioEngine | None = None,
        exporter: ExportEngine | None = None,
        ffmpeg_bin: str | None = None,
    ) -> None:
        app_config = AppConfig()
        self._ffmpeg_bin = ffmpeg_bin or app_config.ffmpeg_path
        self._engine = engine or AudioEngine(ffmpeg_bin=self._ffmpeg_bin)
        self._exporter = exporter or ExportEngine(ffmpeg_bin=self._ffmpeg_bin)

    def process_file(
        self,
        input_path: Path,
        output_dir: Path,
        options: dict[str, Any],
        on_progress: Callable[[float, str], None] | None = None,
        cancel_flag: threading.Event | None = None,
    ) -> Path:
        """Standard pipeline: load audio, run enhance(), export result."""
        if cancel_flag and cancel_flag.is_set():
            return input_path

        if on_progress:
            on_progress(0.05, f"Loading {input_path.name}...")

        buffer = AudioBuffer.load(input_path, ffmpeg_bin=self._ffmpeg_bin)
        samples = buffer.samples
        sr = buffer.sample_rate
        channels = buffer.channels

        if cancel_flag and cancel_flag.is_set():
            return input_path

        if on_progress:
            on_progress(0.15, "Enhancing audio...")

        processed_samples = self.enhance(
            audio=samples,
            sr=sr,
            options=options,
            on_progress=on_progress,
            cancel_flag=cancel_flag,
        )

        if cancel_flag and cancel_flag.is_set():
            return input_path

        if on_progress:
            on_progress(0.90, "Exporting processed audio...")

        # Construct unique output path
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        suffix = input_path.suffix.lower()
        if suffix not in [".wav", ".mp3", ".flac"]:
            suffix = ".wav"

        proc_id = getattr(getattr(self, "metadata", None), "id", "enhanced")
        base_name = f"{input_path.stem}_{proc_id}"
        out_path = output_dir / f"{base_name}{suffix}"
        counter = 1
        while out_path.exists():
            out_path = output_dir / f"{base_name}_{counter}{suffix}"
            counter += 1

        # Reshape if 1D mono
        if processed_samples.ndim == 1 and channels > 1:
            processed_samples = np.repeat(processed_samples[:, np.newaxis], channels, axis=1)

        out_buffer = AudioBuffer(
            samples=processed_samples.astype(np.float32),
            sample_rate=sr,
            channels=channels if processed_samples.ndim > 1 else 1,
        )

        exported_path = out_buffer.save(out_path, ffmpeg_bin=self._ffmpeg_bin)

        if on_progress:
            on_progress(1.0, f"Completed: {exported_path.name}")

        return exported_path

    @abc.abstractmethod
    def enhance(
        self,
        audio: np.ndarray,
        sr: int,
        options: dict[str, Any],
        on_progress: Callable[[float, str], None] | None = None,
        cancel_flag: threading.Event | None = None,
    ) -> np.ndarray:
        """Perform the actual audio transformation on in-memory numpy samples."""
        raise NotImplementedError

    # Delegate process_in_chunks to src.audio.dsp
    process_in_chunks = staticmethod(process_in_chunks)
