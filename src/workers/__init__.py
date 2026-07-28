"""Background task management."""

import typing

if typing.TYPE_CHECKING:
    from src.workers.base_worker import WorkerSignals
    from src.workers.processor_worker import ProcessorWorker
else:
    from src.workers.base_worker import WorkerSignals
    from src.workers.processor_worker import ProcessorWorker

__all__ = [
    "WorkerSignals",
    "ProcessorWorker",
]
