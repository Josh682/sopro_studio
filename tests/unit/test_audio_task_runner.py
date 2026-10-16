"""Comprehensive Unit Tests for AudioTaskRunner (Candidate 3).

Validates:
1. Task lifecycle: PENDING -> RUNNING -> COMPLETED / CANCELLED / FAILED.
2. Callable execution and result extraction in TaskResult.
3. Interactive task cancellation and cleanup.
4. Error handling and exception capture without crashing background workers.
5. Dual event bridge: Qt Signals and native Python callbacks.
6. FIFO task queueing and concurrency constraints.
7. ETA and progress fraction calculation.
8. Processor execution through submit_processor.
"""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ui.qt import QApplication

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

import numpy as np
import soundfile as sf

from src.core.audio_engine import AudioBuffer
from src.core.task_runner import (
    AudioTask,
    AudioTaskRunner,
    TaskResult,
    TaskStatus,
    get_task_runner,
)


class TestAudioTaskRunner(unittest.TestCase):
    """Test suite for AudioTaskRunner deep module."""

    def setUp(self) -> None:
        self.runner = AudioTaskRunner(max_workers=1)
        self.tmp_dir = PROJECT_ROOT / "tests" / "fixtures" / "tmp_tasks"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.runner.shutdown(wait=True, cancel_running=True)

    def test_callable_success_lifecycle(self) -> None:
        """Test submitting a callable function that completes successfully."""
        def simple_compute(x: int, y: int) -> int:
            time.sleep(0.05)
            return x + y

        finished_results = []
        task = self.runner.submit_callable(
            simple_compute,
            15,
            27,
            name="Addition Task",
            on_finished=finished_results.append,
        )

        self.assertEqual(task.name, "Addition Task")
        self.assertIn(task.status, (TaskStatus.PENDING, TaskStatus.RUNNING))

        # Wait for completion (max 2s)
        timeout = time.time() + 2.0
        while not task.is_finished and time.time() < timeout:
            app.processEvents()
            time.sleep(0.01)

        self.assertTrue(task.is_finished)
        self.assertEqual(task.status, TaskStatus.COMPLETED)
        self.assertTrue(task.result.is_success)
        self.assertEqual(task.result.data, 42)
        self.assertGreater(task.result.duration_sec, 0.04)
        self.assertGreaterEqual(len(finished_results), 1)

    def test_task_cancellation(self) -> None:
        """Test cooperative cancellation of a running task."""
        def long_job(cancel_token=None) -> str:
            for _ in range(50):
                if cancel_token and cancel_token.is_set():
                    return "ABORTED"
                time.sleep(0.02)
            return "FINISHED"

        task = self.runner.submit_callable(long_job, name="Long Job")

        # Wait until it starts
        timeout = time.time() + 1.0
        while task.status != TaskStatus.RUNNING and time.time() < timeout:
            app.processEvents()
            time.sleep(0.01)

        # Cancel the task
        task.cancel()
        self.assertTrue(task.is_cancelled)

        # Wait for worker to finish processing cancellation
        timeout = time.time() + 2.0
        while not task.is_finished and time.time() < timeout:
            app.processEvents()
            time.sleep(0.01)

        self.assertEqual(task.status, TaskStatus.CANCELLED)
        self.assertTrue(task.result.is_cancelled)

    def test_task_failure_handling(self) -> None:
        """Test exception capture and error reporting in TaskResult."""
        def faulty_job() -> None:
            raise ValueError("Simulated DSP calculation error")

        error_messages = []
        task = self.runner.submit_callable(
            faulty_job,
            name="Faulty Task",
            on_error=error_messages.append,
        )

        timeout = time.time() + 2.0
        while not task.is_finished and time.time() < timeout:
            app.processEvents()
            time.sleep(0.01)

        self.assertTrue(task.is_failed)
        self.assertEqual(task.status, TaskStatus.FAILED)
        self.assertIn("Simulated DSP calculation error", task.result.error)
        self.assertIsNotNone(task.result.traceback)
        self.assertGreaterEqual(len(error_messages), 1)

    def test_dual_callbacks_and_signals(self) -> None:
        """Test both Qt signals and pure Python native callback registration."""
        def progress_job(on_progress=None) -> str:
            if on_progress:
                on_progress(0.25, "Quarter way")
                time.sleep(0.02)
                on_progress(0.75, "Three quarters")
                time.sleep(0.02)
            return "DONE"

        py_progress_events = []
        qt_progress_events = []
        py_finished_events = []

        task = self.runner.submit_callable(progress_job, name="Progress Job")

        # Connect Python callbacks
        task.add_progress_callback(lambda p, m: py_progress_events.append((p, m)))
        task.add_finished_callback(py_finished_events.append)

        # Connect Qt signals
        task.signals.progress.connect(lambda p, m: qt_progress_events.append((p, m)))

        timeout = time.time() + 2.0
        while not task.is_finished and time.time() < timeout:
            app.processEvents()
            time.sleep(0.01)

        self.assertTrue(task.is_finished)
        self.assertGreaterEqual(len(py_progress_events), 2)
        self.assertGreaterEqual(len(qt_progress_events), 2)
        self.assertEqual(len(py_finished_events), 1)
        self.assertEqual(py_finished_events[0].data, "DONE")

    def test_fifo_queueing(self) -> None:
        """Test that tasks execute sequentially in FIFO order when max_workers=1."""
        execution_order = []

        def make_job(idx: int):
            def job():
                execution_order.append(f"start_{idx}")
                time.sleep(0.03)
                execution_order.append(f"end_{idx}")
                return idx
            return job

        t1 = self.runner.submit_callable(make_job(1), name="Job 1")
        t2 = self.runner.submit_callable(make_job(2), name="Job 2")
        t3 = self.runner.submit_callable(make_job(3), name="Job 3")

        timeout = time.time() + 3.0
        while not (t1.is_finished and t2.is_finished and t3.is_finished) and time.time() < timeout:
            app.processEvents()
            time.sleep(0.01)

        self.assertEqual(
            execution_order,
            ["start_1", "end_1", "start_2", "end_2", "start_3", "end_3"],
            "Tasks did not execute in strict sequential FIFO order",
        )

    def test_submit_processor_execution(self) -> None:
        """Test submit_processor running a real processor through AudioTaskRunner."""
        # Create a short 0.1s sine test wave
        test_file = self.tmp_dir / "test_task_sine.wav"
        sr = 22050
        samples = (np.sin(2 * np.pi * 440 * np.linspace(0, 0.1, int(sr * 0.1))) * 0.5).astype(np.float32)
        sf.write(str(test_file), samples, sr)

        task = self.runner.submit_processor(
            processor="format_converter",
            input_paths=[test_file],
            output_dir=self.tmp_dir,
            options={"output_format": "wav", "bit_depth": 16, "normalize": False},
            name="Test Conversion",
        )

        timeout = time.time() + 15.0
        while not task.is_finished and time.time() < timeout:
            app.processEvents()
            time.sleep(0.02)

        self.assertTrue(
            task.is_finished,
            f"Task did not finish! Status: {task.status}, msg: {task.message}, err: {getattr(task, 'error', None)}, result: {task.result}"
        )
        self.assertEqual(task.status, TaskStatus.COMPLETED)
        self.assertTrue(task.result.is_success)
        self.assertGreaterEqual(len(task.result.output_paths), 1)
        self.assertTrue(task.result.output_paths[0].exists())

    def test_global_singleton(self) -> None:
        """Test get_task_runner returns singleton instance."""
        r1 = get_task_runner()
        r2 = get_task_runner()
        self.assertIs(r1, r2)
        self.assertIsInstance(r1, AudioTaskRunner)


if __name__ == "__main__":
    unittest.main()
