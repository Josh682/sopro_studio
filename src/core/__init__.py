"""Core business logic and processing orchestration."""

import typing

if typing.TYPE_CHECKING:
    from src.core.audio_engine import AudioEngine, AudioBuffer
    from src.core.exporter import ExportEngine
    from src.core.processors.base_processor import BaseProcessor
    from src.core.processor_registry import ProcessorRegistry

else:
    from src.core.audio_engine import AudioEngine
    from src.core.exporter import ExportEngine
    from src.core.processors.base_processor import BaseProcessor
    from src.core.processor_registry import ProcessorRegistry

__all__ = [
    "AudioEngine",
    "ExportEngine",
    "BaseProcessor",
    "ProcessorRegistry",
]

# Import processors to ensure they register themselves
import src.core.processors
