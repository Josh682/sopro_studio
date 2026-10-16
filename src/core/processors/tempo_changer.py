"""Tempo Change Processor Plugin."""

import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import librosa
import numpy as np

from src.core.audio_engine import AudioBuffer, AudioEngine
from src.core.exporter import ExportEngine
from src.core.processors.base_processor import (
    BaseProcessor,
    ParameterDescriptor,
    ProcessorMetadata,
)
from src.core.processor_registry import ProcessorRegistry

log = logging.getLogger("sound_processor.core.processors.tempo_changer")


@dataclass
class TempoChangeOptions:
    """Configuration for tempo change processing."""
    mode: str = "bpm"              # "bpm" | "percentage"
    source_bpm: float = 0.0        # required for BPM mode
    target_bpm: float = 0.0        # required for BPM mode
    percent_change: float = 0.0    # required for percentage mode

    @property
    def rate(self) -> float:
        if self.mode == "bpm":
            if self.source_bpm <= 0:
                return 1.0
            return self.target_bpm / self.source_bpm
        else:
            return 1.0 + (self.percent_change / 100.0)


class TempoChanger(BaseProcessor):
    """Changes the playback speed/BPM of audio without altering its pitch."""

    metadata = ProcessorMetadata(
        id="tempo_changer",
        name="Tempo Changer",
        description="Change audio playback speed without altering its pitch.",
        version="1.0.0",
        category="Processing",
        tags=["tempo", "time-stretch", "bpm", "music"],
    )

    def __init__(self, ffmpeg_bin: str | None = None) -> None:
        self._ffmpeg_bin = ffmpeg_bin
        self._audio_engine = AudioEngine(ffmpeg_bin=ffmpeg_bin)
        self._export_engine = ExportEngine(ffmpeg_bin=ffmpeg_bin)

    def process(
        self,
        input_paths: list[Path],
        output_dir: Path,
        options: dict[str, Any],
        on_progress: Callable[[float, str], None] | None = None,
        cancel_flag: threading.Event | None = None,
    ) -> dict[Path, Any]:
        """Process multiple files to change their tempo.

        Args:
            input_paths: List of audio files to process.
            output_dir: Destination directory.
            options: Dictionary containing fields for TempoChangeOptions.
            on_progress: Callback function for progress updates (0.0 to 1.0).
            cancel_flag: Threading event flag to cancel processing.

        Returns:
            Dictionary mapping input paths to their output paths or errors.
        """
        if not input_paths:
            return {}

        results: dict[Path, Any] = {}
        total_files = len(input_paths)

        tempo_opts = TempoChangeOptions(
            mode=options.get("mode", "bpm"),
            source_bpm=float(options.get("source_bpm", 0.0)),
            target_bpm=float(options.get("target_bpm", 0.0)),
            percent_change=float(options.get("percent_change", 0.0)),
        )

        rate = tempo_opts.rate
        if rate == 1.0:
            log.warning("TempoChanger running with rate 1.0. Outputs will be identical to inputs.")

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
                audio_buffer = AudioBuffer.load(input_path, ffmpeg_bin=self._ffmpeg_bin)
                
                local_progress(0.4, f"Stretching by {rate:.3f}x...")
                
                shifted_channels = []
                for ch in range(audio_buffer.channels):
                    if cancel_flag and cancel_flag.is_set():
                        break
                    
                    y_channel = audio_buffer.samples[:, ch] if audio_buffer.channels > 1 else audio_buffer.samples
                    
                    stretched = librosa.effects.time_stretch(y=y_channel, rate=rate)
                    shifted_channels.append(stretched)
                    
                if cancel_flag and cancel_flag.is_set():
                    break
                    
                local_progress(0.9, "Exporting...")
                
                if audio_buffer.channels > 1:
                    stretched_data = np.column_stack(shifted_channels)
                else:
                    stretched_data = shifted_channels[0]
                    
                audio_buffer.samples = stretched_data

                # Determine output filename
                if tempo_opts.mode == "bpm":
                    suffix = f"_{tempo_opts.target_bpm}bpm"
                else:
                    suffix = f"_{tempo_opts.percent_change}pct"
                    
                out_name = f"{input_path.stem}{suffix}.wav"
                out_path = output_dir / out_name

                # Export to WAV
                audio_buffer.save(
                    path=out_path,
                    format="wav",
                    bit_depth=24,  # High quality 24-bit PCM
                    ffmpeg_bin=self._ffmpeg_bin,
                )
                
                results[input_path] = out_path
                log.info(f"Exported: {out_path.name}")
                
            except Exception as e:
                log.exception(f"Error changing tempo for {input_path}")
                results[input_path] = {"error": str(e)}

        return results

    @classmethod
    def get_parameter_descriptors(cls) -> list[ParameterDescriptor]:
        return [
            ParameterDescriptor(
                name="mode",
                type="choice",
                default="bpm",
                choices=["bpm", "percentage"],
                description="Mode for tempo change (bpm or percentage)."
            ),
            ParameterDescriptor(
                name="source_bpm",
                type="float",
                default=120.0,
                min_value=20.0,
                max_value=300.0,
                step=1.0,
                unit="BPM",
                description="Source tempo in BPM."
            ),
            ParameterDescriptor(
                name="target_bpm",
                type="float",
                default=120.0,
                min_value=20.0,
                max_value=300.0,
                step=1.0,
                unit="BPM",
                description="Target tempo in BPM."
            ),
            ParameterDescriptor(
                name="percent_change",
                type="float",
                default=0.0,
                min_value=-50.0,
                max_value=100.0,
                step=1.0,
                unit="%",
                description="Playback speed change percentage."
            ),
        ]

    def get_parameters(self) -> list[ParameterDescriptor]:
        """Backward compatibility alias for get_parameter_descriptors."""
        return self.get_parameter_descriptors()

# Register the processor
ProcessorRegistry.register(TempoChanger)
