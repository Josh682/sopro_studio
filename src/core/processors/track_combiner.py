"""Track Combiner processor for merging multiple audio files."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np

from src.audio import probe
from src.core.audio_engine import AudioBuffer, AudioEngine
from src.core.exporter import ExportEngine
from src.core.processor_registry import ProcessorRegistry
from src.core.processors.base_processor import BaseProcessor, ProcessorMetadata, ParameterDescriptor

log = logging.getLogger("sound_processor.core.processors.track_combiner")


class TrackCombiner(BaseProcessor):
    """Merges multiple audio files into a single mixdown file."""

    metadata = ProcessorMetadata(
        id="track_combiner",
        name="Track Combiner",
        description="Merges multiple audio files into a single mixdown file with sample-accurate summing and peak normalization.",
        version="1.0.0",
        category="Mixer",
        tags=["combine", "mix", "sum"],
    )

    @classmethod
    def get_parameter_descriptors(cls) -> list[ParameterDescriptor]:
        return [
            ParameterDescriptor(name="output_format", label="Output Format", type="choice", choices=["wav", "flac"], default="wav"),
            ParameterDescriptor(name="bit_depth", label="Bit Depth", type="choice", choices=[16, 24, 32], default=24),
            ParameterDescriptor(name="output_filename", label="Output Filename", type="string", default="mix"),
            ParameterDescriptor(name="prevent_clipping", label="Prevent Clipping", type="bool", default=True),
            ParameterDescriptor(name="normalize_output", label="Peak Normalize Output", type="bool", default=False),
        ]



    def process(
        self,
        input_paths: list[Path],
        output_dir: Path,
        options: dict[str, Any],
        on_progress=None,
        cancel_flag=None,
    ) -> dict[Path, Path]:
        files = input_paths
        if not files:
            log.warning("No files provided for combination.")
            return {}

        self.emit_progress(0.0, "Probing files...")
        
        # Parse options
        out_fmt = options.get("output_format", "wav").lower()
        bit_depth = options.get("bit_depth", 24)
        out_name = options.get("output_filename", "mix")
        gain_per_track = options.get("gain_per_track", {})
        prevent_clipping = options.get("prevent_clipping", True)
        normalize_output = options.get("normalize_output", False)
        
        # 1. Find max sample rate and duration
        target_sr = 44100
        for i, p in enumerate(files):
            try:
                info = probe(p)
                if info.sample_rate > target_sr:
                    target_sr = info.sample_rate
            except Exception as exc:
                log.warning("Could not probe '%s': %s", p.name, exc)

        engine = AudioEngine()
        loaded_arrays = []
        
        # 2. Load, resample and upmix
        for i, p in enumerate(files):
            pct = 10.0 + (i / len(files)) * 40.0
            self.emit_progress(pct, f"Loading {p.name}...")
            
            self.check_cancelled()
            
            buffer = engine.load(p, target_sr=target_sr)
            
            # Upmix to stereo if mono
            samples = buffer.samples
            if samples.ndim == 1:
                # (frames,) -> (frames, 1) -> (frames, 2)
                samples = np.repeat(samples[:, np.newaxis], 2, axis=1)
            elif samples.shape[1] == 1:
                # (frames, 1) -> (frames, 2)
                samples = np.repeat(samples, 2, axis=1)
            
            # Apply individual track gain
            gain = gain_per_track.get(p.name, 1.0)
            if gain != 1.0:
                samples = samples * gain
                
            loaded_arrays.append(samples)
            
        # 3. Pad to max duration
        self.emit_progress(60.0, "Padding and mixing stems...")
        self.check_cancelled()
        
        max_frames = max(arr.shape[0] for arr in loaded_arrays)
        padded_arrays = []
        
        for arr in loaded_arrays:
            diff = max_frames - arr.shape[0]
            if diff > 0:
                arr = np.pad(arr, ((0, diff), (0, 0)), mode="constant")
            padded_arrays.append(arr)
            
        # 4. Sum
        mixed = np.sum(padded_arrays, axis=0, dtype=np.float32)
        
        # 5. Prevent Clipping or Normalize
        self.emit_progress(80.0, "Applying peak normalization checks...")
        peak = float(np.abs(mixed).max())
        if peak == 0.0:
            log.warning("Resulting mix is entirely silence.")
        else:
            if normalize_output:
                factor = 0.99 / peak
                mixed = (mixed * factor).astype(np.float32)
                log.info("Mix normalized by %.2f dB", 20 * np.log10(factor))
            elif prevent_clipping and peak > 1.0:
                factor = 0.99 / peak
                mixed = (mixed * factor).astype(np.float32)
                log.info("Peak reduced by %.2f dB to prevent clipping", -20 * np.log10(factor))
            elif peak > 1.0:
                log.warning("Mix is clipping! Peak level is %.2f (over 1.0) but prevention is disabled.", peak)

        # 6. Export
        self.emit_progress(90.0, "Writing mixdown file...")
        self.check_cancelled()
        
        out_buffer = AudioBuffer(mixed, target_sr, channels=2)
        exporter = ExportEngine(str(output_dir))
        
        # Find unique output path
        base_path = output_dir / f"{out_name}.{out_fmt}"
        unique_path = base_path
        counter = 1
        while unique_path.exists():
            unique_path = output_dir / f"{out_name}_{counter}.{out_fmt}"
            counter += 1
            
        options_dict = {"bit_depth": bit_depth}
        if out_fmt == "flac":
            options_dict["compression"] = 5  # default
            
        out_path = exporter.export(out_buffer, out_fmt, unique_path.name, options_dict)
        
        self.emit_progress(100.0, f"Mixdown complete: {out_path.name}")
        return {files[0]: out_path}

ProcessorRegistry.register(TrackCombiner)
