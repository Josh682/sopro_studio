"""Stem Separator Processor."""

import logging
import threading
from pathlib import Path
from typing import Any, Callable

from src.ai.model_manager import ModelManager
from src.core.processors.base_processor import (
    BaseProcessor,
    ProcessorMetadata,
    ParameterDescriptor,
)

log = logging.getLogger("sound_processor.core.processors.stem_separator")

class StemSeparator(BaseProcessor):
    """Processor for separating audio stems using AI models."""

    metadata = ProcessorMetadata(
        id="stem_separator",
        name="Stem Separator",
        description="Extract stems like vocals and instruments using AI models.",
        version="1.0.0",
        category="Separator",
        tags=["ai", "demucs", "roformer", "separation"],
    )

    @classmethod
    def get_parameter_descriptors(cls) -> list[ParameterDescriptor]:
        return [
            ParameterDescriptor(
                name="model_id", 
                label="AI Model", 
                type="string", 
                default="",
            ),
        ]

    def process(
        self,
        input_paths: list[Path],
        output_dir: Path,
        options: dict[str, Any],
        on_progress: Callable[[float, str], None] | None = None,
        cancel_flag: threading.Event | None = None,
    ) -> dict[Path, dict[str, Path]]:
        model_id = options.get("model_id")
        if not model_id:
            raise ValueError("No model_id provided for StemSeparator.")

        log.info("Loading model %s", model_id)
        if on_progress:
            on_progress(0.0, f"Loading model {model_id}...")
            
        manager = options.get("manager")
        if not manager:
            # Fallback for CLI/testing if no manager is injected
            from src.ai import create_default_manager
            manager = create_default_manager(options.get("models_dir"))
            
        model = manager.get_model(model_id)

        results = {}
        total = len(input_paths)

        for idx, path in enumerate(input_paths):
            if cancel_flag and cancel_flag.is_set():
                break

            def local_progress(fraction: float, message: str) -> None:
                if on_progress:
                    on_progress((idx + fraction) / total, f"[{idx + 1}/{total}] {message}")

            local_progress(0.0, f"Separating {path.name}...")
            log.info("Separating '%s' with model %s", path.name, model_id)

            try:
                stems = model.separate(path, output_dir, local_progress, cancel_flag)
                
                # Check stems
                expected_stems = set(model.metadata.stem_names)
                returned_stems = set(stems.keys())

                missing = expected_stems - returned_stems
                if missing:
                    raise RuntimeError(f"Model returned missing stems: {missing}")
                    
                results[path] = stems
                local_progress(1.0, f"Finished separating {path.name}")
            except Exception as e:
                log.error("Failed to separate %s: %s", path.name, e)
                raise

        return results

# Register
from src.core.processor_registry import ProcessorRegistry
ProcessorRegistry.register(StemSeparator)
