"""Core business logic and processing orchestration."""

import typing

if typing.TYPE_CHECKING:
    from src.core.audio_engine import AudioBuffer, AudioEngine
    from src.core.exporter import ExportEngine
    from src.core.processor_registry import ProcessorRegistry
    from src.core.processors.base_processor import BaseProcessor
    from src.core.task_runner import (
        AudioTask,
        AudioTaskRunner,
        TaskResult,
        TaskStatus,
        get_task_runner,
    )

else:
    from src.core.audio_engine import AudioBuffer, AudioEngine
    from src.core.exporter import ExportEngine
    from src.core.processor_registry import ProcessorRegistry
    from src.core.processors.base_processor import BaseProcessor
    from src.core.task_runner import (
        AudioTask,
        AudioTaskRunner,
        TaskResult,
        TaskStatus,
        get_task_runner,
    )

__all__ = [
    "AudioBuffer",
    "AudioEngine",
    "ExportEngine",
    "BaseProcessor",
    "ProcessorRegistry",
    "AudioTaskRunner",
    "AudioTask",
    "TaskResult",
    "TaskStatus",
    "get_task_runner",
]

# Import processors to ensure they register themselves
import src.core.processors
