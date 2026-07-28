"""Key Detection Processor Plugin."""

import csv
import logging
import threading
from pathlib import Path
from typing import Any, Callable

from src.core.music_analyzer import MusicAnalyzer
from src.core.processors.base_processor import (
    BaseProcessor,
    ParameterDescriptor,
    ProcessorMetadata,
)
from src.core.processor_registry import ProcessorRegistry

log = logging.getLogger("sound_processor.core.processors.key_detector")


class KeyDetector(BaseProcessor):
    """Processor that analyzes audio for key and tempo."""

    metadata = ProcessorMetadata(
        id="key_detector",
        name="Key & Tempo Detector",
        description="Detects musical key and BPM using Krumhansl-Schmuckler algorithm.",
        version="1.0.0",
        category="Analysis",
        tags=["key", "tempo", "bpm", "music"],
    )

    def process(
        self,
        input_paths: list[Path],
        output_dir: Path,
        options: dict[str, Any],
        on_progress: Callable[[float, str], None] | None = None,
        cancel_flag: threading.Event | None = None,
    ) -> dict[Path, dict[str, Any]]:
        """Run analysis on a batch of files and output a CSV report.

        Returns:
            A dictionary mapping input paths to their parsed result dictionaries.
        """
        if not input_paths:
            return {}

        analyzer = MusicAnalyzer()
        results = {}
        total_files = len(input_paths)

        csv_path = output_dir / "key_analysis.csv"
        
        # We will keep a list of rows to write at the end (or as we go)
        rows = []
        rows.append(["filename", "key", "mode", "confidence", "bpm", "alt_1", "alt_1_conf", "alt_2", "alt_2_conf", "alt_3", "alt_3_conf"])

        for idx, input_path in enumerate(input_paths):
            if cancel_flag and cancel_flag.is_set():
                break

            base_progress = idx / total_files
            
            def local_progress(fraction: float, msg: str) -> None:
                if on_progress:
                    overall = base_progress + (fraction / total_files)
                    on_progress(overall, f"[{input_path.name}] {msg}")

            try:
                key_res, tempo_res = analyzer.analyze(input_path, on_progress=local_progress)
                
                results[input_path] = {
                    "key": key_res,
                    "tempo": tempo_res,
                }
                
                # Format for CSV
                alt1_key = alt1_conf = alt2_key = alt2_conf = alt3_key = alt3_conf = ""
                if len(key_res.alternatives) >= 1:
                    alt1_key = f"{key_res.alternatives[0]['tonic']} {key_res.alternatives[0]['mode']}"
                    alt1_conf = f"{key_res.alternatives[0]['confidence']:.2f}"
                if len(key_res.alternatives) >= 2:
                    alt2_key = f"{key_res.alternatives[1]['tonic']} {key_res.alternatives[1]['mode']}"
                    alt2_conf = f"{key_res.alternatives[1]['confidence']:.2f}"
                if len(key_res.alternatives) >= 3:
                    alt3_key = f"{key_res.alternatives[2]['tonic']} {key_res.alternatives[2]['mode']}"
                    alt3_conf = f"{key_res.alternatives[2]['confidence']:.2f}"
                
                if key_res.display == "N/A":
                    rows.append([
                        input_path.name, 
                        "N/A", 
                        "N/A", 
                        f"{key_res.confidence:.2f}", 
                        str(tempo_res.bpm),
                        alt1_key, alt1_conf, alt2_key, alt2_conf, alt3_key, alt3_conf
                    ])
                else:
                    rows.append([
                        input_path.name,
                        key_res.tonic,
                        key_res.mode,
                        f"{key_res.confidence:.2f}",
                        str(tempo_res.bpm),
                        alt1_key, alt1_conf, alt2_key, alt2_conf, alt3_key, alt3_conf
                    ])
                    
            except Exception as e:
                log.exception(f"Error analyzing {input_path}")
                results[input_path] = {"error": str(e)}

        # Write CSV if we have processed anything and haven't cancelled midway
        # (or even if cancelled, write what we have)
        if len(rows) > 1:
            try:
                output_dir.mkdir(parents=True, exist_ok=True)
                with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerows(rows)
                if on_progress:
                    on_progress(1.0, f"Saved report to {csv_path.name}")
            except Exception as e:
                log.error(f"Failed to write CSV report: {e}")

        return results

    @classmethod
    def get_parameter_descriptors(cls) -> list[ParameterDescriptor]:
        return []

# Register the processor
ProcessorRegistry.register(KeyDetector)
