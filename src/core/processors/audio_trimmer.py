"""Audio Trim Processor Plugin."""

import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np
import soundfile as sf

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
        
        # 1. Get info to calculate frames
        info = sf.info(str(input_path))
        
        # Validate bounds
        try:
            trim_opts.validate(info.duration)
        except ValueError as ve:
            raise RuntimeError(f"Validation failed for {input_path.name}: {ve}")
        
        start_frame = int(trim_opts.start_sec * info.samplerate)
        frames_to_read = int((trim_opts.end_sec - trim_opts.start_sec) * info.samplerate)
        
        if on_progress:
            on_progress(0.4, "Extracting audio slice...")
        
        # 2. Read only the required slice (saves memory)
        data, sr = sf.read(str(input_path), start=start_frame, frames=frames_to_read)
        
        if cancel_flag and cancel_flag.is_set():
            return None
            
        if on_progress:
            on_progress(0.7, "Applying fades...")
        
        # 3. Apply Fades
        if trim_opts.fade_in_ms > 0:
            data = self._apply_fade_in(data, sr, trim_opts.fade_in_ms)
        if trim_opts.fade_out_ms > 0:
            data = self._apply_fade_out(data, sr, trim_opts.fade_out_ms)
            
        if cancel_flag and cancel_flag.is_set():
            return None
            
        if on_progress:
            on_progress(0.9, "Exporting...")
        
        out_name = f"{input_path.stem}_trimmed.wav"
        out_path = output_dir / out_name

        # 4. Export
        # We always output WAV as requested by the spec
        sf.write(str(out_path), data, sr, format="WAV", subtype="PCM_24")
        
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

    def get_parameters(self) -> list[ParameterDescriptor]:
        return [
            ParameterDescriptor(
                name="start_sec",
                type=float,
                default=0.0,
                description="Trim start time in seconds."
            ),
            ParameterDescriptor(
                name="end_sec",
                type=float,
                default=0.0,
                description="Trim end time in seconds."
            ),
            ParameterDescriptor(
                name="fade_in_ms",
                type=float,
                default=0.0,
                description="Fade in duration in milliseconds."
            ),
            ParameterDescriptor(
                name="fade_out_ms",
                type=float,
                default=0.0,
                description="Fade out duration in milliseconds."
            ),
        ]

# Register the processor
ProcessorRegistry.register(AudioTrimmer)
