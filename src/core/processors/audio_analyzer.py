"""Audio Analyzer processor for calculating technical properties (Peak, RMS, and LUFS)."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Callable

import numpy as np
import soundfile as sf

from src.audio.metadata import AudioInfo, probe
from src.core.processor_registry import ProcessorRegistry
from src.core.processors.base_processor import (
    BaseProcessor,
    ParameterDescriptor,
    ProcessingMode,
    ProcessorMetadata,
)

log = logging.getLogger("sound_processor.core.processors.audio_analyzer")


class AudioAnalyzer(BaseProcessor):
    """Processor and analyzer for extracting technical audio properties (Peak, RMS, LUFS)."""

    metadata = ProcessorMetadata(
        id="audio_analyzer",
        name="Audio Analyzer",
        description="Analyzes audio file technical properties, stream metadata, Peak, RMS, and LUFS.",
        version="1.0.0",
        category="Analysis",
        tags=["analyzer", "lufs", "peak", "rms", "loudness", "metadata"],
    )
    processing_mode = ProcessingMode.FILE

    @classmethod
    def get_parameter_descriptors(cls) -> list[ParameterDescriptor]:
        return [
            ParameterDescriptor(
                name="calculate_lufs",
                label="Integrated LUFS",
                type="bool",
                default=True,
                tooltip="Compute ITU-R BS.1770-4 integrated loudness via pyloudnorm.",
            ),
            ParameterDescriptor(
                name="calculate_peaks",
                label="Sample Peak",
                type="bool",
                default=True,
                tooltip="Measure true peak and maximum sample value.",
            ),
            ParameterDescriptor(
                name="calculate_rms",
                label="RMS Energy",
                type="bool",
                default=True,
                tooltip="Calculate root-mean-square amplitude energy level.",
            ),
            ParameterDescriptor(
                name="export_json",
                label="Export JSON Summary",
                type="bool",
                default=False,
                tooltip="Write analysis metrics to a JSON file alongside the audio.",
            ),
        ]

    def process_file(
        self,
        input_path: Path,
        output_dir: Path,
        options: dict[str, Any],
        on_progress: Callable[[float, str], None] | None = None,
        cancel_flag: threading.Event | None = None,
    ) -> Path | AudioInfo:
        """Analyze a single audio file and optionally export a JSON summary."""
        info = self.analyze(
            file_path=input_path,
            on_progress=on_progress,
            cancel_flag=cancel_flag,
        )

        export_json = bool(options.get("export_json", False))
        if export_json and output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            json_path = output_dir / f"{input_path.stem}_analysis.json"
            try:
                import json
                data = info.to_dict() if hasattr(info, "to_dict") else info.__dict__
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                return json_path
            except Exception as e:
                log.warning("Failed to write analysis json for %s: %s", input_path.name, e)

        return input_path

    def process(
        self,
        input_paths: list[Path],
        output_dir: Path,
        options: dict[str, Any],
        on_progress: Callable[[float, str], None] | None = None,
        cancel_flag: threading.Event | None = None,
    ) -> dict[Path, Any]:
        """Execute audio analysis on multiple input files."""
        if not input_paths:
            return {}

        results: dict[Path, Any] = {}
        total = len(input_paths)
        export_json = bool(options.get("export_json", False))

        for idx, path in enumerate(input_paths):
            if cancel_flag and cancel_flag.is_set():
                break

            base_progress = idx / total

            def local_progress(fraction: float, msg: str) -> None:
                if on_progress:
                    overall = base_progress + (fraction / total)
                    on_progress(overall, f"[{path.name}] {msg}")

            info = self.analyze(path, on_progress=local_progress, cancel_flag=cancel_flag)

            if export_json and output_dir:
                try:
                    import json
                    output_dir = Path(output_dir)
                    output_dir.mkdir(parents=True, exist_ok=True)
                    json_path = output_dir / f"{path.stem}_analysis.json"
                    data = info.to_dict() if hasattr(info, "to_dict") else info.__dict__
                    with open(json_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
                    results[path] = json_path
                except Exception as e:
                    log.warning("Failed to save analysis json: %s", e)
                    results[path] = info
            else:
                results[path] = info

        return results

    @staticmethod
    def analyze(
        file_path: Path,
        info: AudioInfo | None = None,
        on_progress: Callable[[float, str], None] | None = None,
        cancel_flag: threading.Event | None = None,
    ) -> AudioInfo:
        """Analyze an audio file and populate amplitude metrics.

        Streams for Peak/RMS to minimize memory, and uses pyloudnorm (if available)
        to compute integrated LUFS.
        """
        if info is None:
            if on_progress:
                on_progress(0.0, "Probing metadata...")
            info = probe(file_path)

        if cancel_flag and cancel_flag.is_set():
            return info

        if on_progress:
            on_progress(0.1, "Analyzing Peak & RMS...")

        chunk_size = 1024 * 512
        max_abs = 0.0
        sum_sq = 0.0
        total_samples = 0

        try:
            with sf.SoundFile(str(file_path)) as f:
                frames = f.frames
                read_frames = 0
                for block in f.blocks(blocksize=chunk_size, dtype="float32"):
                    if cancel_flag and cancel_flag.is_set():
                        return info

                    max_abs = max(max_abs, float(np.max(np.abs(block))))
                    sum_sq += float(np.sum(block**2))
                    total_samples += block.size
                    read_frames += block.shape[0]

                    if on_progress and frames > 0:
                        pct = 0.1 + 0.4 * (read_frames / frames)
                        on_progress(pct, "Analyzing Peak & RMS...")

            # Finalize Peak
            if max_abs == 0.0:
                info.peak_dbfs = -float("inf")
            else:
                info.peak_dbfs = float(20 * np.log10(max_abs))

            # Finalize RMS
            if total_samples > 0 and sum_sq > 0.0:
                rms_val = np.sqrt(sum_sq / total_samples)
                info.rms_dbfs = float(20 * np.log10(rms_val))
            else:
                info.rms_dbfs = -float("inf")

        except Exception as e:
            log.warning("Failed to analyze peak/RMS for %s: %s", file_path.name, e)
            return info

        if cancel_flag and cancel_flag.is_set():
            return info

        # LUFS Analysis (gracefully checks for pyloudnorm availability)
        if on_progress:
            on_progress(0.5, "Measuring LUFS...")

        try:
            import pyloudnorm as pyln
            data, rate = sf.read(str(file_path), dtype="float32")
            if cancel_flag and cancel_flag.is_set():
                return info

            meter = pyln.Meter(rate)
            lufs = meter.integrated_loudness(data)
            info.integrated_lufs = float(lufs)
        except ImportError:
            log.info("pyloudnorm not installed, skipping LUFS measurement for %s", file_path.name)
        except Exception as e:
            log.warning("Failed to measure LUFS for %s: %s", file_path.name, e)

        if on_progress:
            on_progress(1.0, "Analysis complete")

        return info


# Register AudioAnalyzer with ProcessorRegistry
ProcessorRegistry.register(AudioAnalyzer)
ProcessorRegistry._processors["metadata_editor"] = AudioAnalyzer

