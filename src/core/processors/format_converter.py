"""Format Converter Processor."""

import logging
import threading
from pathlib import Path
from typing import Any, Callable

from src.core.audio_engine import AudioEngine
from src.core.exporter import ExportEngine
from src.core.processors.base_processor import (
    BaseProcessor,
    ProcessorMetadata,
    ParameterDescriptor,
)
from src.utils.config import AppConfig

log = logging.getLogger("sound_processor.core.processors.format_converter")


class FormatConverter(BaseProcessor):
    """Processor for audio format conversion, resampling, and normalization."""

    metadata = ProcessorMetadata(
        id="format_converter",
        name="Format Converter",
        description="Convert audio formats with optional resampling and normalization.",
        version="1.0.0",
        category="Converter",
        tags=["conversion", "resample", "normalize"],
    )

    def __init__(self, engine: AudioEngine | None = None, exporter: ExportEngine | None = None):
        app_config = AppConfig()
        ffmpeg_bin = app_config.ffmpeg_path
        self._engine = engine or AudioEngine(ffmpeg_bin=ffmpeg_bin)
        self._exporter = exporter or ExportEngine(ffmpeg_bin=ffmpeg_bin)

    @classmethod
    def get_parameter_descriptors(cls) -> list[ParameterDescriptor]:
        return [
            ParameterDescriptor(name="output_format", label="Output Format", type="choice", choices=["wav", "mp3", "flac"], default="wav"),
            ParameterDescriptor(name="sample_rate", label="Sample Rate (Hz)", type="choice", choices=[44100, 48000, 88200, 96000], default=44100),
            ParameterDescriptor(name="bit_depth", label="Bit Depth", type="choice", choices=[16, 24, 32], default=16),
            ParameterDescriptor(name="mp3_bitrate", label="MP3 Bitrate", type="choice", choices=[128, 192, 320], default=192),
            ParameterDescriptor(name="flac_compression", label="FLAC Compression", type="int", min=0, max=8, default=5),
            ParameterDescriptor(name="normalize", label="Normalize Peak", type="bool", default=False),
        ]

    def process(
        self,
        input_paths: list[Path],
        output_dir: Path,
        options: dict[str, Any],
        on_progress: Callable[[float, str], None] | None = None,
        cancel_flag: threading.Event | None = None,
    ) -> dict[Path, Path]:
        from src.utils.file_utils import unique_output_path

        results = {}
        total = len(input_paths)
        out_fmt = options.get("output_format", "wav").lower().lstrip(".")
        
        for idx, path in enumerate(input_paths):
            if cancel_flag and cancel_flag.is_set():
                break

            def local_progress(fraction: float, message: str) -> None:
                if on_progress:
                    on_progress((idx + fraction) / total, f"[{idx + 1}/{total}] {message}")

            local_progress(0.0, f"Loading {path.name}...")
            log.info("Converting '%s' -> format: %s", path.name, out_fmt)
            
            # Resolve target path
            suffix = f".{out_fmt}"
            out_path = unique_output_path(output_dir, path.stem, suffix)

            # Load
            buffer = self._engine.load(path)
            if cancel_flag and cancel_flag.is_set():
                break

            # Resample
            target_sr_opt = options.get("sample_rate")
            # If target_sr_opt is "Original" or None, we keep original. Assuming it's an int.
            if target_sr_opt and isinstance(target_sr_opt, int) and target_sr_opt != buffer.sample_rate:
                local_progress(0.35, f"Resampling to {target_sr_opt} Hz...")
                buffer = self._engine.resample(buffer, target_sr_opt)
            if cancel_flag and cancel_flag.is_set():
                break

            # Normalize
            if options.get("normalize", False):
                local_progress(0.55, "Normalising...")
                buffer = self._engine.normalize(buffer)
            if cancel_flag and cancel_flag.is_set():
                break

            # Export
            local_progress(0.70, f"Encoding {out_fmt.upper()}...")
            sr = buffer.sample_rate
            if out_fmt == "wav":
                self._exporter.export_wav(buffer, out_path, sample_rate=sr, bit_depth=options.get("bit_depth", 16))
            elif out_fmt == "mp3":
                self._exporter.export_mp3(buffer, out_path, sample_rate=sr, bitrate=options.get("mp3_bitrate", 192))
            elif out_fmt == "flac":
                self._exporter.export_flac(buffer, out_path, sample_rate=sr, compression=options.get("flac_compression", 5))
            else:
                raise ValueError(f"Unsupported format: {out_fmt}")

            results[path] = out_path
            local_progress(1.0, f"Done -> {out_path.name}")
            
        return results

# Register
from src.core.processor_registry import ProcessorRegistry
ProcessorRegistry.register(FormatConverter)
