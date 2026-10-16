"""Background task management."""

import typing

if typing.TYPE_CHECKING:
    from src.core.task_runner import (
        AudioTask,
        AudioTaskRunner,
        TaskResult,
        TaskStatus,
        get_task_runner,
    )
    from src.workers.base_worker import WorkerSignals
    from src.workers.processor_worker import ProcessorWorker
else:
    from src.core.task_runner import (
        AudioTask,
        AudioTaskRunner,
        TaskResult,
        TaskStatus,
        get_task_runner,
    )
    from src.workers.base_worker import WorkerSignals
    from src.workers.processor_worker import ProcessorWorker

__all__ = [
    "WorkerSignals",
    "ProcessorWorker",
    "AudioTaskRunner",
    "AudioTask",
    "TaskResult",
    "TaskStatus",
    "get_task_runner",
]
