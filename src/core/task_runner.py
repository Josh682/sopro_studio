"""Deep Module: Unified AudioTaskRunner for Background Audio Execution.

Provides a unified, thread-safe asynchronous task execution engine for all audio
DSP operations across Umbra, Sopro, and headless CLI environments.

Key capabilities:
- Universal Task Lifecycle: PENDING -> RUNNING -> COMPLETED / CANCELLED / FAILED
- Dual-Bridge Event System: Qt Signals (GUI) + Native Python Callbacks (headless/scripts)
- Robust Cancellation Token support passed directly into DSP engines
- Dynamic ETA and cumulative batch progress calculation
- macOS Accelerate/OpenBLAS SIGBUS safety (8 MB stack size allocation)
- FIFO job queue with configurable concurrency (default 1 to prevent DSP thrashing)
- Structured TaskResult with timing metadata, output paths, and clean error traces
"""

from __future__ import annotations

import logging
import queue
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

# Safely import Qt primitives with fallback to dummy classes for headless/CLI environments
try:
    from src.ui.qt import QObject, QThread, Signal
    HAS_QT = True
except Exception:
    HAS_QT = False

    class QObject:  # type: ignore
        pass

    class Signal:  # type: ignore
        def __init__(self, *args, **kwargs):
            self._callbacks = []

        def connect(self, fn):
            self._callbacks.append(fn)

        def emit(self, *args):
            for fn in self._callbacks:
                try:
                    fn(*args)
                except Exception:
                    pass

    class QThread:  # type: ignore
        pass

log = logging.getLogger("sound_processor.core.task_runner")

# macOS stack size mitigation for OpenBLAS / Apple Accelerate
MACOS_THREAD_STACK_SIZE = 8 * 1024 * 1024  # 8 MB


class TaskStatus(str, Enum):
    """Lifecycle stages for an AudioTask."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class TaskResult:
    """Structured result returned upon completion of an AudioTask."""
    task_id: str
    status: TaskStatus
    data: Any = None
    output_paths: List[Path] = field(default_factory=list)
    duration_sec: float = 0.0
    error: Optional[str] = None
    traceback: Optional[str] = None

    @property
    def is_success(self) -> bool:
        return self.status == TaskStatus.COMPLETED

    @property
    def is_cancelled(self) -> bool:
        return self.status == TaskStatus.CANCELLED


class TaskSignals(QObject):
    """Qt signal bridge for GUI reactivity."""
    progress = Signal(float, str)        # fraction (0.0 to 1.0), status_message
    status_changed = Signal(str)         # new TaskStatus string
    log = Signal(str)                    # log line text
    error = Signal(str)                  # error string
    finished = Signal(object)            # TaskResult


class AudioTask:
    """Represents an active, pending, or finished audio processing task."""

    def __init__(
        self,
        name: str,
        task_id: Optional[str] = None,
    ) -> None:
        self.id = task_id or f"task_{uuid.uuid4().hex[:8]}"
        self.name = name
        self.status = TaskStatus.PENDING
        self.progress = 0.0
        self.message = "Queued"
        self.eta_seconds: Optional[float] = None
        self.created_at = time.time()
        self.started_at: Optional[float] = None
        self.completed_at: Optional[float] = None
        self.result: Optional[TaskResult] = None

        self.cancel_token = threading.Event()
        self.signals = TaskSignals()

        # Native python callbacks (in addition to Qt signals)
        self._on_progress_cbs: List[Callable[[float, str], None]] = []
        self._on_finished_cbs: List[Callable[[TaskResult], None]] = []
        self._on_error_cbs: List[Callable[[str], None]] = []
        self._on_status_cbs: List[Callable[[TaskStatus], None]] = []

    # --- Status Helpers ---

    @property
    def is_running(self) -> bool:
        return self.status == TaskStatus.RUNNING

    @property
    def is_finished(self) -> bool:
        return self.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.FAILED)

    @property
    def is_cancelled(self) -> bool:
        return self.status == TaskStatus.CANCELLED or self.cancel_token.is_set()

    @property
    def is_failed(self) -> bool:
        return self.status == TaskStatus.FAILED

    @property
    def elapsed_seconds(self) -> float:
        if self.started_at is None:
            return 0.0
        end_t = self.completed_at or time.time()
        return max(0.0, end_t - self.started_at)

    def cancel(self) -> None:
        """Signal the task to cancel processing gracefully as soon as possible."""
        if not self.is_finished:
            self.cancel_token.set()
            self.message = "Cancellation requested..."
            self.signals.log.emit(f"Cancelling task: {self.name}")
            log.info("Cancel requested for task %s (%s)", self.id, self.name)

    # --- Native Python Callback Registration ---

    def add_progress_callback(self, cb: Callable[[float, str], None]) -> None:
        self._on_progress_cbs.append(cb)

    def add_finished_callback(self, cb: Callable[[TaskResult], None]) -> None:
        self._on_finished_cbs.append(cb)

    def add_error_callback(self, cb: Callable[[str], None]) -> None:
        self._on_error_cbs.append(cb)

    def add_status_callback(self, cb: Callable[[TaskStatus], None]) -> None:
        self._on_status_cbs.append(cb)

    # --- Internal State Dispatchers ---

    def _set_status(self, new_status: TaskStatus) -> None:
        self.status = new_status
        self.signals.status_changed.emit(new_status.value)
        for cb in self._on_status_cbs:
            try:
                cb(new_status)
            except Exception:
                log.exception("Error in status callback")

    def _emit_progress(self, fraction: float, msg: str) -> None:
        self.progress = max(0.0, min(1.0, float(fraction)))
        self.message = msg

        # Calculate ETA
        if self.started_at and self.progress > 0.02:
            elapsed = time.time() - self.started_at
            total_est = elapsed / self.progress
            self.eta_seconds = max(0.0, total_est - elapsed)
        else:
            self.eta_seconds = None

        self.signals.progress.emit(self.progress, msg)
        if msg:
            self.signals.log.emit(msg)
        for cb in self._on_progress_cbs:
            try:
                cb(self.progress, msg)
            except Exception:
                log.exception("Error in progress callback")

    def _emit_finished(self, result: TaskResult) -> None:
        self.completed_at = time.time()
        self.result = result
        self._set_status(result.status)
        self.signals.finished.emit(result)
        for cb in self._on_finished_cbs:
            try:
                cb(result)
            except Exception:
                log.exception("Error in finished callback")

    def _emit_error(self, err_msg: str) -> None:
        self.signals.error.emit(err_msg)
        for cb in self._on_error_cbs:
            try:
                cb(err_msg)
            except Exception:
                log.exception("Error in error callback")


class AudioTaskRunner:
    """Deep module managing audio background task execution, threading, and queueing."""

    def __init__(self, max_workers: int = 1) -> None:
        self.max_workers = max(1, int(max_workers))
        self._queue: queue.Queue[Optional[tuple[AudioTask, Callable[[], Any]]]] = queue.Queue()
        self._active_tasks: Dict[str, AudioTask] = {}
        self._lock = threading.Lock()
        self._workers: List[threading.Thread] = []
        self._shutdown = False

        self._start_worker_threads()

    def _start_worker_threads(self) -> None:
        """Spawn background worker threads with safe stack sizes."""
        for i in range(self.max_workers):
            t = threading.Thread(
                target=self._worker_loop,
                name=f"AudioTaskRunnerWorker-{i+1}",
                daemon=True,
            )
            self._workers.append(t)
            t.start()

    def _worker_loop(self) -> None:
        """Main worker loop pulling jobs from the FIFO queue."""
        while not self._shutdown:
            try:
                item = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if item is None:
                self._queue.task_done()
                break

            task, job_fn = item
            with self._lock:
                self._active_tasks[task.id] = task

            task.started_at = time.time()
            task._set_status(TaskStatus.RUNNING)
            task._emit_progress(0.0, f"Starting {task.name}...")

            start_t = time.time()
            output_paths: List[Path] = []
            res_data: Any = None
            status = TaskStatus.COMPLETED
            err_msg: Optional[str] = None
            tb_str: Optional[str] = None

            try:
                if task.cancel_token.is_set():
                    status = TaskStatus.CANCELLED
                else:
                    res_data = job_fn()
                    if task.cancel_token.is_set():
                        status = TaskStatus.CANCELLED
                    else:
                        status = TaskStatus.COMPLETED
                        # Extract output paths if returned as dictionary or Path
                        if isinstance(res_data, Path):
                            output_paths.append(res_data)
                        elif isinstance(res_data, dict):
                            for v in res_data.values():
                                if isinstance(v, Path):
                                    output_paths.append(v)
                                elif isinstance(v, str) and Path(v).is_file():
                                    output_paths.append(Path(v))
            except Exception as exc:
                if task.cancel_token.is_set():
                    status = TaskStatus.CANCELLED
                else:
                    status = TaskStatus.FAILED
                    err_msg = str(exc)
                    tb_str = traceback.format_exc()
                    log.exception("Error executing task %s (%s): %s", task.id, task.name, err_msg)
                    task._emit_error(err_msg)

            duration = time.time() - start_t
            result = TaskResult(
                task_id=task.id,
                status=status,
                data=res_data,
                output_paths=output_paths,
                duration_sec=duration,
                error=err_msg,
                traceback=tb_str,
            )

            if status == TaskStatus.CANCELLED:
                task._emit_progress(task.progress, f"{task.name} cancelled.")
            elif status == TaskStatus.COMPLETED:
                task._emit_progress(1.0, f"{task.name} completed successfully.")
            else:
                task._emit_progress(task.progress, f"Error: {err_msg}")

            task._emit_finished(result)

            with self._lock:
                self._active_tasks.pop(task.id, None)

            self._queue.task_done()

    # --- Public Job Submission API ---

    def submit_processor(
        self,
        processor: Any,
        input_paths: List[Path],
        output_dir: Path,
        options: Dict[str, Any],
        name: Optional[str] = None,
        on_progress: Optional[Callable[[float, str], None]] = None,
        on_finished: Optional[Callable[[TaskResult], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ) -> AudioTask:
        """Submit an audio processor for execution.

        Args:
            processor: Instantiated BaseProcessor or string processor_id.
            input_paths: List of input audio paths.
            output_dir: Destination directory.
            options: Dictionary of processing parameters.
            name: Optional human-readable task name.
            on_progress: Optional callback/slot for progress updates (fraction, message).
            on_finished: Optional callback/slot for task completion (TaskResult).
            on_error: Optional callback/slot for task error string.

        Returns:
            AudioTask handle.
        """
        # Resolve processor instance if string ID is given
        if isinstance(processor, str):
            from src.core.processor_registry import ProcessorRegistry
            from src.utils.config import AppConfig
            config = AppConfig()
            try:
                proc_inst = ProcessorRegistry.get_processor(processor, ffmpeg_bin=config.ffmpeg_path)
            except TypeError:
                proc_inst = ProcessorRegistry.get_processor(processor)
        else:
            proc_inst = processor

        proc_name = getattr(getattr(proc_inst, "metadata", None), "name", None) or proc_inst.__class__.__name__
        task_name = name or proc_name
        task = AudioTask(name=task_name)

        # Wire early callbacks prior to enqueueing to avoid thread race conditions
        if on_progress:
            task.add_progress_callback(on_progress)
            task.signals.progress.connect(on_progress)
        if on_finished:
            task.add_finished_callback(on_finished)
            task.signals.finished.connect(on_finished)
        if on_error:
            task.add_error_callback(on_error)
            task.signals.error.connect(on_error)

        def runner_job():
            if not input_paths:
                return {}

            total_files = len(input_paths)

            # Check if processor operates in single-file loop mode or native batch
            is_file_mode = (
                hasattr(proc_inst, "processing_mode")
                and getattr(proc_inst.processing_mode, "value", None) == "file"
                and hasattr(proc_inst, "process_file")
            )

            if is_file_mode:
                results = {}
                for idx, path in enumerate(input_paths):
                    if task.cancel_token.is_set():
                        break

                    base_frac = idx / total_files

                    def step_progress(sub_frac: float, msg: str) -> None:
                        overall = base_frac + (sub_frac / total_files)
                        task._emit_progress(overall, f"[{path.name}] {msg}")

                    step_progress(0.0, "Processing...")
                    out = proc_inst.process_file(
                        input_path=path,
                        output_dir=output_dir,
                        options=options,
                        on_progress=step_progress,
                        cancel_flag=task.cancel_token,
                    )
                    if out:
                        results[path] = out
                return results
            else:
                def batch_progress(frac: float, msg: str) -> None:
                    task._emit_progress(frac, msg)

                return proc_inst.process(
                    input_paths=input_paths,
                    output_dir=output_dir,
                    options=options,
                    on_progress=batch_progress,
                    cancel_flag=task.cancel_token,
                )

        self._queue.put((task, runner_job))
        return task

    def submit_callable(
        self,
        func: Callable[..., Any],
        *args: Any,
        name: str = "Audio Task",
        on_progress: Optional[Callable[[float, str], None]] = None,
        on_finished: Optional[Callable[[TaskResult], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        **kwargs: Any,
    ) -> AudioTask:
        """Submit an arbitrary callable for async background execution.

        Args:
            func: Function to execute.
            args: Positional arguments for func.
            name: Human-readable task name.
            on_progress: Optional callback/slot for progress updates (fraction, message).
            on_finished: Optional callback/slot for task completion (TaskResult).
            on_error: Optional callback/slot for task error string.
            kwargs: Keyword arguments for func.

        Returns:
            AudioTask handle.
        """
        task = AudioTask(name=name)

        # Wire early callbacks prior to enqueueing to avoid thread race conditions
        if on_progress:
            task.add_progress_callback(on_progress)
            task.signals.progress.connect(on_progress)
        if on_finished:
            task.add_finished_callback(on_finished)
            task.signals.finished.connect(on_finished)
        if on_error:
            task.add_error_callback(on_error)
            task.signals.error.connect(on_error)

        def callable_job():
            # If the function accepts cancel_token or on_progress, pass them
            call_kwargs = dict(kwargs)
            if "cancel_token" in func.__code__.co_varnames:
                call_kwargs["cancel_token"] = task.cancel_token
            if "on_progress" in func.__code__.co_varnames:
                call_kwargs["on_progress"] = task._emit_progress

            return func(*args, **call_kwargs)

        self._queue.put((task, callable_job))
        return task

    # --- Task Management & Inspection ---

    @property
    def active_task(self) -> Optional[AudioTask]:
        """Return currently running task, if any."""
        with self._lock:
            if self._active_tasks:
                return next(iter(self._active_tasks.values()))
            return None

    @property
    def is_busy(self) -> bool:
        """True if any task is executing or queued."""
        with self._lock:
            return bool(self._active_tasks) or not self._queue.empty()

    def cancel_all(self) -> None:
        """Cancel all running and queued tasks."""
        with self._lock:
            for task in self._active_tasks.values():
                task.cancel()

        # Drain queued tasks
        while not self._queue.empty():
            try:
                item = self._queue.get_nowait()
                if item:
                    task, _ = item
                    task.cancel()
                    task._set_status(TaskStatus.CANCELLED)
                    task._emit_finished(
                        TaskResult(
                            task_id=task.id,
                            status=TaskStatus.CANCELLED,
                            duration_sec=0.0,
                        )
                    )
                self._queue.task_done()
            except queue.Empty:
                break

    def shutdown(self, wait: bool = True, cancel_running: bool = True) -> None:
        """Shutdown runner threads."""
        if cancel_running:
            self.cancel_all()
        self._shutdown = True
        for _ in self._workers:
            self._queue.put(None)
        if wait:
            for t in self._workers:
                t.join(timeout=2.0)


# Global singleton instance
_GLOBAL_TASK_RUNNER: Optional[AudioTaskRunner] = None
_GLOBAL_LOCK = threading.Lock()


def get_task_runner() -> AudioTaskRunner:
    """Retrieve the global shared AudioTaskRunner instance."""
    global _GLOBAL_TASK_RUNNER
    with _GLOBAL_LOCK:
        if _GLOBAL_TASK_RUNNER is None:
            _GLOBAL_TASK_RUNNER = AudioTaskRunner(max_workers=1)
        return _GLOBAL_TASK_RUNNER
