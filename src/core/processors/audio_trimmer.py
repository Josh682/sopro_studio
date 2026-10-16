"""Audio Trim Processor Plugin."""

import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np
import soundfile as sf

from src.core.audio_engine import AudioBuffer
from src.core.processors.base_processor import (
    BaseProcessor,
    ParameterDescriptor,
    ProcessorMetadata,
    ProcessingMode,
)
from src.core.processor_registry import ProcessorRegistry

log = logging.getLogger("sound_processor.core.processors.audio_trimmer")


@dataclass
class TrimOptions:
    """Configuration for trim processing."""
    start_sec: float = 0.0
    end_sec: float = 0.0
    fade_in_ms: float = 0.0
    fade_out_ms: float = 0.0

    def validate(self, total_duration: float):
        if self.start_sec < 0 or self.end_sec > total_duration:
            raise ValueError("Trim points out of bounds.")
        if self.start_sec >= self.end_sec:
            raise ValueError("Start time must be before end time.")


class AudioTrimmer(BaseProcessor):
    """Trims audio to a specific range and applies optional fades."""

    metadata = ProcessorMetadata(
        id="audio_trimmer",
        name="Audio Trimmer",
        description="Destructively crop audio to a specific time range with optional fades.",
        version="1.0.0",
        category="Processing",
        tags=["trim", "crop", "fade", "audio"],
    )
    processing_mode = ProcessingMode.FILE

    def process_file(
        self,
        input_path: Path,
        output_dir: Path,
        options: dict[str, Any],
        on_progress: Callable[[float, str], None] | None = None,
        cancel_flag: threading.Event | None = None,
    ) -> Path:
        """Process a single file to trim it.

        Args:
            input_path: Audio file to process.
            output_dir: Destination directory.
            options: Dictionary containing fields for TrimOptions.
            on_progress: Callback function for progress updates (0.0 to 1.0).
            cancel_flag: Threading event flag to cancel processing.

        Returns:
            The output path.
        """
        trim_opts = TrimOptions(
            start_sec=float(options.get("start_sec", 0.0)),
            end_sec=float(options.get("end_sec", 0.0)),
            fade_in_ms=float(options.get("fade_in_ms", 0.0)),
            fade_out_ms=float(options.get("fade_out_ms", 0.0)),
        )

        output_dir.mkdir(parents=True, exist_ok=True)

        if on_progress:
            on_progress(0.1, "Analyzing file metadata...")
        
        # 1. Get info to calculate frames and duration
        duration = 0.0
        try:
            from src.audio.metadata import probe
            info = probe(input_path)
            duration = info.duration
        except Exception:
            try:
                info = sf.info(str(input_path))
                duration = info.duration
            except Exception:
                duration = 0.0

        # Validate bounds
        if duration > 0.0:
            try:
                trim_opts.validate(duration)
            except ValueError as ve:
                raise RuntimeError(f"Validation failed for {input_path.name}: {ve}")
        
        slice_duration = trim_opts.end_sec - trim_opts.start_sec if trim_opts.end_sec > trim_opts.start_sec else None

        if on_progress:
            on_progress(0.4, "Extracting audio slice...")
        
        # 2. Sliced load via AudioBuffer (memory efficient)
        buffer = AudioBuffer.load(
            input_path,
            start_sec=trim_opts.start_sec if trim_opts.start_sec > 0 else None,
            duration_sec=slice_duration,
        )
        
        if cancel_flag and cancel_flag.is_set():
            return None
            
        if on_progress:
            on_progress(0.7, "Applying fades...")
        
        # 3. Apply Fades
        data = buffer.samples
        sr = buffer.sample_rate
        if trim_opts.fade_in_ms > 0:
            data = self._apply_fade_in(data, sr, trim_opts.fade_in_ms)
        if trim_opts.fade_out_ms > 0:
            data = self._apply_fade_out(data, sr, trim_opts.fade_out_ms)
            
        buffer.samples = data

        if cancel_flag and cancel_flag.is_set():
            return None
            
        if on_progress:
            on_progress(0.9, "Exporting...")
        
        out_name = f"{input_path.stem}_trimmed.wav"
        out_path = output_dir / out_name

        # 4. Export
        buffer.save(out_path, format="wav", bit_depth=24)
        
        log.info(f"Exported: {out_path.name}")
        return out_path

    @staticmethod
    def _apply_fade_in(data: np.ndarray, sr: int, fade_ms: float) -> np.ndarray:
        fade_frames = int((fade_ms / 1000.0) * sr)
        fade_frames = min(fade_frames, len(data))
        if fade_frames <= 0:
            return data
            
        curve = np.linspace(0.0, 1.0, fade_frames, dtype=data.dtype)
        
        if data.ndim > 1:
            curve = curve[:, np.newaxis]
            
        data[:fade_frames] *= curve
        return data

    @staticmethod
    def _apply_fade_out(data: np.ndarray, sr: int, fade_ms: float) -> np.ndarray:
        fade_frames = int((fade_ms / 1000.0) * sr)
        fade_frames = min(fade_frames, len(data))
        if fade_frames <= 0:
            return data
            
        curve = np.linspace(1.0, 0.0, fade_frames, dtype=data.dtype)
        
        if data.ndim > 1:
            curve = curve[:, np.newaxis]
            
        data[-fade_frames:] *= curve
        return data

    @classmethod
    def get_parameter_descriptors(cls) -> list[ParameterDescriptor]:
        return [
            ParameterDescriptor(
                name="start_sec",
                type="float",
                default=0.0,
                min_value=0.0,
                step=0.1,
                unit="s",
                description="Trim start time in seconds."
            ),
            ParameterDescriptor(
                name="end_sec",
                type="float",
                default=0.0,
                min_value=0.0,
                step=0.1,
                unit="s",
                description="Trim end time in seconds (0 = full length)."
            ),
            ParameterDescriptor(
                name="fade_in_ms",
                type="float",
                default=0.0,
                min_value=0.0,
                max_value=10000.0,
                step=50.0,
                unit="ms",
                description="Fade in duration in milliseconds."
            ),
            ParameterDescriptor(
                name="fade_out_ms",
                type="float",
                default=0.0,
                min_value=0.0,
                max_value=10000.0,
                step=50.0,
                unit="ms",
                description="Fade out duration in milliseconds."
            ),
        ]

    def get_parameters(self) -> list[ParameterDescriptor]:
        """Backward compatibility alias for get_parameter_descriptors."""
        return self.get_parameter_descriptors()

# Register the processor
ProcessorRegistry.register(AudioTrimmer)
