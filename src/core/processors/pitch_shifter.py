"""Pitch Shift Processor Plugin."""

import logging
import threading
from pathlib import Path
from typing import Any, Callable

import librosa
import numpy as np

from src.core.audio_engine import AudioEngine
from src.core.exporter import ExportEngine
from src.core.processors.base_processor import (
    BaseProcessor,
    ParameterDescriptor,
    ProcessorMetadata,
)
from src.core.processor_registry import ProcessorRegistry

log = logging.getLogger("sound_processor.core.processors.pitch_shifter")


class PitchShifter(BaseProcessor):
    """Processor that transposes audio by a specific number of semitones."""

    metadata = ProcessorMetadata(
        id="pitch_shifter",
        name="Pitch Shifter",
        description="Transpose audio by semitones while preserving tempo.",
        version="1.0.0",
        category="Processing",
        tags=["pitch", "transpose", "shift", "music"],
    )

    def __init__(self) -> None:
        self._audio_engine = AudioEngine()
        self._export_engine = ExportEngine()

    def process(
        self,
        input_paths: list[Path],
        output_dir: Path,
        options: dict[str, Any],
        on_progress: Callable[[float, str], None] | None = None,
        cancel_flag: threading.Event | None = None,
    ) -> dict[Path, Path]:
        """Execute the pitch shift on a batch of files.
        
        Args:
            options: Dictionary containing 'semitones' (float). Optional: 'mode' string for filename.
        """
        if not input_paths:
            return {}

        results: dict[Path, Path] = {}
        total_files = len(input_paths)

        semitones = float(options.get("semitones", 0.0))
        target_root = options.get("target_root")  # optional, for naming
        
        if semitones == 0.0:
            log.warning("PitchShifter running with 0.0 semitones. Outputs will be identical to inputs.")

        output_dir.mkdir(parents=True, exist_ok=True)

        for idx, input_path in enumerate(input_paths):
            if cancel_flag and cancel_flag.is_set():
                break

            base_progress = idx / total_files
            
            def local_progress(fraction: float, msg: str) -> None:
                if on_progress:
                    overall = base_progress + (fraction / total_files)
                    on_progress(overall, f"[{input_path.name}] {msg}")

            try:
                local_progress(0.1, "Loading...")
                audio_buffer = self._audio_engine.load(input_path)
                
                local_progress(0.4, f"Shifting by {semitones} semitones...")
                
                shifted_channels = []
                for ch in range(audio_buffer.channels):
                    if cancel_flag and cancel_flag.is_set():
                        break
                    
                    y_channel = audio_buffer.samples[:, ch] if audio_buffer.channels > 1 else audio_buffer.samples
                    
                    shifted = librosa.effects.pitch_shift(
                        y=y_channel,
                        sr=audio_buffer.sample_rate,
                        n_steps=semitones,
                        bins_per_octave=12,
                    )
                    shifted_channels.append(shifted)
                    
                if cancel_flag and cancel_flag.is_set():
                    break
                    
                shifted_data = np.stack(shifted_channels, axis=1) if audio_buffer.channels > 1 else shifted_channels[0]
                audio_buffer.samples = shifted_data
                
                # Determine output filename
                if target_root:
                    suffix = f"_{target_root.replace('#', 'sharp')}"
                else:
                    sign = "+" if semitones > 0 else ""
                    suffix = f"_{sign}{semitones}st"
                    
                out_name = f"{input_path.stem}{suffix}.wav"
                out_path = output_dir / out_name

                local_progress(0.9, "Exporting...")
                self._export_engine.export_wav(
                    buffer=audio_buffer,
                    path=out_path,
                    bit_depth=24,
                )
                
                results[input_path] = out_path
                
            except Exception as e:
                log.exception(f"Error shifting {input_path}")
                # We simply don't add it to results on error

        if on_progress and not (cancel_flag and cancel_flag.is_set()):
            on_progress(1.0, "Pitch shift complete.")

        return results

    @classmethod
    def get_parameter_descriptors(cls) -> list[ParameterDescriptor]:
        return [
            ParameterDescriptor(
                name="semitones",
                label="Semitones",
                type="float",
                default=0.0,
                min=-12.0,
                max=12.0,
                tooltip="Amount to shift pitch (positive = up, negative = down)."
            )
        ]

# Register the processor
ProcessorRegistry.register(PitchShifter)
