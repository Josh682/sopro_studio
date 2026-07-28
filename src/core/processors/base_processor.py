"""Processor Framework.

Defines the base interface for all audio processors and the registry
for dynamic discovery.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, ClassVar
import threading


@dataclass
class ParameterDescriptor:
    """Describes a parameter for dynamic UI generation."""
    name: str
    label: str
    type: str  # 'float', 'int', 'bool', 'choice', 'string', 'path'
    default: Any
    min: float | None = None
    max: float | None = None
    choices: list[str] | None = None
    tooltip: str = ""


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
    
    A processor encapsulates a specific audio transformation workflow,
    handling its own I/O via the AudioEngine and ExportEngine.
    """
    
    metadata: ClassVar[ProcessorMetadata]

    @abstractmethod
    def process(
        self,
        input_paths: list[Path],
        output_dir: Path,
        options: dict[str, Any],
        on_progress: Callable[[float, str], None] | None = None,
        cancel_flag: threading.Event | None = None,
    ) -> Any:
        """Execute the processor logic on the given inputs.
        
        Args:
            input_paths: List of input audio files.
            output_dir: Target directory for outputs.
            options: Dictionary of processor-specific options.
            on_progress: Callback taking (fraction: float, message: str).
            cancel_flag: Threading event to signal cancellation.
            
        Returns:
            The output path, a list of paths, a dict of stems, or any other
            meaningful result for this processor.
        """
        pass

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
