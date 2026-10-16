"""Processor Framework.

Defines the base interface for all audio processors and the registry
for dynamic discovery.
"""

from enum import Enum
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, ClassVar
import threading


class ProcessingMode(Enum):
    """Defines how a processor handles files."""
    BATCH = "batch"   # Processor handles the batch loop natively
    FILE = "file"     # Processor handles one file path at a time


@dataclass
class ParameterDescriptor:
    """Describes a parameter for dynamic UI generation."""
    name: str
    label: str = ""
    type: str = "string"  # 'float', 'int', 'bool', 'choice', 'string', 'path'
    default: Any = None
    min: float | None = None
    max: float | None = None
    choices: list[str] | None = None
    tooltip: str = ""
    # Aliases and extra UI metadata
    min_value: float | None = None
    max_value: float | None = None
    step: float | None = None
    unit: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        if not self.label:
            self.label = self.name.replace("_", " ").title()
        if self.min_value is not None and self.min is None:
            self.min = self.min_value
        elif self.min is not None and self.min_value is None:
            self.min_value = self.min
        if self.max_value is not None and self.max is None:
            self.max = self.max_value
        elif self.max is not None and self.max_value is None:
            self.max_value = self.max
        if self.description and not self.tooltip:
            self.tooltip = self.description
        elif self.tooltip and not self.description:
            self.description = self.tooltip


@dataclass
class ProcessorMetadata:
    """Metadata describing a processor."""
    id: str
    name: str
    description: str
    version: str
    category: str
    tags: list[str] = field(default_factory=list)


class BaseProcessor(ABC):
    """Abstract base class for all audio processors.
    
    A processor encapsulates a specific audio transformation workflow.
    """
    
    metadata: ClassVar[ProcessorMetadata]
    processing_mode: ClassVar[ProcessingMode] = ProcessingMode.BATCH

    def process_file(
        self,
        input_path: Path,
        output_dir: Path,
        options: dict[str, Any],
        on_progress: Callable[[float, str], None] | None = None,
        cancel_flag: threading.Event | None = None,
    ) -> Path:
        """Process a single file (used when processing_mode == FILE)."""
        raise NotImplementedError("process_file must be implemented for FILE mode.")

    def process(
        self,
        input_paths: list[Path],
        output_dir: Path,
        options: dict[str, Any],
        on_progress: Callable[[float, str], None] | None = None,
        cancel_flag: threading.Event | None = None,
    ) -> Any:
        """Execute the processor logic on the given inputs.

        Default implementation handles FILE processing mode by iterating
        over input_paths and delegating each file to process_file().
        BATCH processors override this method directly.

        Args:
            input_paths: List of input audio files.
            output_dir: Target directory for outputs.
            options: Dictionary of processor-specific options.
            on_progress: Callback taking (fraction: float, message: str).
            cancel_flag: Threading event to signal cancellation.

        Returns:
            Dictionary of {input_path: output_path} for FILE mode, or custom batch results.
        """
        if not input_paths:
            return {}

        if getattr(self, "processing_mode", None) == ProcessingMode.FILE:
            results: dict[Path, Path] = {}
            total = len(input_paths)
            for idx, path in enumerate(input_paths):
                if cancel_flag and cancel_flag.is_set():
                    break

                base_progress = idx / total

                def local_progress(fraction: float, msg: str) -> None:
                    if on_progress:
                        overall = base_progress + (fraction / total)
                        on_progress(overall, f"[{path.name}] {msg}")

                out_path = self.process_file(
                    input_path=path,
                    output_dir=output_dir,
                    options=options,
                    on_progress=local_progress,
                    cancel_flag=cancel_flag,
                )
                if out_path:
                    results[path] = out_path
            return results

        raise NotImplementedError("Batch processors must implement process().")

    def validate_options(self, options: dict[str, Any]) -> tuple[bool, str]:
        """Validate options before processing.
        
        Returns:
            (is_valid, error_message)
        """
        return True, ""

    @classmethod
    def get_parameter_descriptors(cls) -> list[ParameterDescriptor]:
        """Return parameters for dynamic UI generation."""
        return []
