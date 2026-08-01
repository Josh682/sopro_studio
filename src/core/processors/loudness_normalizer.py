"""Loudness Normalization Processor."""

import json
import logging
import re
import subprocess
import threading
from pathlib import Path
from typing import Any, Callable

from src.core.processors.base_processor import (
    BaseProcessor,
    ParameterDescriptor,
    ProcessingMode,
    ProcessorMetadata,
)
from src.utils.config import AppConfig

log = logging.getLogger("sound_processor.core.processors.loudness_normalizer")


class LoudnessNormalizer(BaseProcessor):
    """Two-pass Loudness Normalizer using FFmpeg's loudnorm filter."""

    metadata = ProcessorMetadata(
        id="loudness_normalizer",
        name="Loudness Normalizer",
        description="Normalizes audio to target LUFS and True Peak using EBU R128 standards.",
        version="1.0",
        category="Mastering",
        tags=["loudness", "lufs", "true-peak", "ebu-r128"],
    )
    processing_mode = ProcessingMode.FILE

    def __init__(self) -> None:
        app_config = AppConfig()
        self._ffmpeg_bin = app_config.ffmpeg_path

    @classmethod
    def get_parameter_descriptors(cls) -> list[ParameterDescriptor]:
        return [
            ParameterDescriptor(
                name="target_lufs",
                label="Target LUFS",
                type="float",
                default=-14.0,
                min=-36.0,
                max=-5.0,
                tooltip="Target integrated loudness in LUFS.",
            ),
            ParameterDescriptor(
                name="max_true_peak",
                label="Max True Peak (dBTP)",
                type="float",
                default=-1.0,
                min=-10.0,
                max=0.0,
                tooltip="Maximum allowed true peak to prevent clipping.",
            ),
            ParameterDescriptor(
                name="lra",
                label="Loudness Range (LU)",
                type="float",
                default=11.0,
                min=1.0,
                max=20.0,
                tooltip="Target Loudness Range (LRA).",
            )
        ]

    def process_file(
        self,
        input_path: Path,
        output_dir: Path,
        options: dict[str, Any],
        on_progress: Callable[[float, str], None] | None = None,
        cancel_flag: threading.Event | None = None,
    ) -> Path:
        target_lufs = float(options.get("target_lufs", -14.0))
        max_tp = float(options.get("max_true_peak", -1.0))
        lra = float(options.get("lra", 11.0))

        if cancel_flag and cancel_flag.is_set():
            return input_path

        output_path = output_dir / f"{input_path.stem}_norm{input_path.suffix}"

        # --- Pass 1: Analysis ---
        if on_progress:
            on_progress(0.1, "Pass 1: Analyzing loudness...")

        pass1_cmd = [
            self._ffmpeg_bin, "-y", "-i", str(input_path),
            "-af", f"loudnorm=I={target_lufs}:TP={max_tp}:LRA={lra}:print_format=json",
            "-f", "null", "/dev/null"
        ]

        try:
            # We use Popen instead of subprocess.run to allow cancelation checking
            process = subprocess.Popen(
                pass1_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            while True:
                if cancel_flag and cancel_flag.is_set():
                    process.terminate()
                    process.wait()
                    return input_path
                    
                retcode = process.poll()
                if retcode is not None:
                    _, stderr = process.communicate()
                    if retcode != 0:
                        log.error(f"FFmpeg Pass 1 failed:\n{stderr}")
                        raise RuntimeError("Failed to analyze loudness with FFmpeg.")
                    result_stderr = stderr
                    break
                    
                if cancel_flag:
                    cancel_flag.wait(0.2)
                    
        except Exception as e:
            raise RuntimeError(f"FFmpeg Pass 1 failed: {e}")

        # Extract JSON block
        match = re.search(r'(\{[\s\S]*?"target_offset"[\s\S]*?\})', result_stderr)
        if not match:
            log.error(f"Could not find JSON in FFmpeg output:\n{result_stderr}")
            raise RuntimeError("Failed to parse FFmpeg loudnorm output.")

        try:
            stats = json.loads(match.group(1))
        except json.JSONDecodeError:
            raise RuntimeError("FFmpeg output was not valid JSON.")

        # --- Pass 2: Normalization ---
        if on_progress:
            on_progress(0.5, "Pass 2: Applying linear gain & true peak limiter...")

        measured_i = stats.get("input_i", "-24.0")
        measured_tp = stats.get("input_tp", "-2.0")
        measured_lra = stats.get("input_lra", "11.0")
        measured_thresh = stats.get("input_thresh", "-35.0")
        offset = stats.get("target_offset", "0.0")

        # Construct the loudnorm filter for pass 2
        af_filter = (
            f"loudnorm=I={target_lufs}:TP={max_tp}:LRA={lra}:"
            f"measured_I={measured_i}:measured_TP={measured_tp}:"
            f"measured_LRA={measured_lra}:measured_thresh={measured_thresh}:"
            f"offset={offset}:linear=true:print_format=summary"
        )

        pass2_cmd = [
            self._ffmpeg_bin, "-y", "-i", str(input_path),
            "-af", af_filter,
            "-map_metadata", "0",
            "-id3v2_version", "3",
            str(output_path)
        ]

        try:
            process = subprocess.Popen(
                pass2_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            while True:
                if cancel_flag and cancel_flag.is_set():
                    process.terminate()
                    process.wait()
                    if output_path.exists():
                        output_path.unlink()
                    return input_path
                    
                retcode = process.poll()
                if retcode is not None:
                    if retcode != 0:
                        _, stderr = process.communicate()
                        log.error(f"FFmpeg Pass 2 failed:\n{stderr}")
                        raise RuntimeError("Failed to apply normalization.")
                    break
                    
                if cancel_flag:
                    cancel_flag.wait(0.2)

        except Exception as e:
            if output_path.exists():
                output_path.unlink()
            raise RuntimeError(f"FFmpeg Pass 2 failed: {e}")

        if on_progress:
            on_progress(1.0, "Normalization complete.")

        return output_path

from src.core.processor_registry import ProcessorRegistry
ProcessorRegistry.register(LoudnessNormalizer)
