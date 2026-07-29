"""Background thread for executing any BaseProcessor."""

import logging
import threading
from pathlib import Path
from typing import Any

from qtpy.QtCore import QThread

from src.core.processors.base_processor import BaseProcessor
from src.workers.base_worker import WorkerSignals

log = logging.getLogger("sound_processor.workers.processor_worker")


class ProcessorWorker(QThread):
    """Executes a BaseProcessor in a background thread.
    
    Delegates all audio logic, including batching and I/O, to the processor.
    The worker only manages threading, cancellation flags, and signal routing.
    """

    def __init__(
        self,
        processor: BaseProcessor,
        input_paths: list[Path],
        output_dir: Path,
        options: dict[str, Any],
    ) -> None:
        """Initialize the generic processor worker.
        
        Args:
            processor: The instantiated BaseProcessor.
            input_paths: List of files to process.
            output_dir: Where to save outputs.
            options: Dictionary of processing options.
        """
        super().__init__()
        # macOS Accelerate/OpenBLAS often crashes with SIGBUS in QThread due to the default 512KB stack size.
        # We increase the stack size to 8 MB to prevent this.
        self.setStackSize(8 * 1024 * 1024)
        
        self.signals = WorkerSignals()
        self._processor = processor
        self._input_paths = input_paths
        self._output_dir = output_dir
        self._options = options
        self._cancel_flag = threading.Event()

    def cancel(self) -> None:
        """Signal the worker to cancel processing as soon as possible."""
        self._cancel_flag.set()
        self.signals.log.emit(f"Cancelling {self._processor.metadata.name}...")

    def run(self) -> None:
        """Execute the processor."""
        if not self._input_paths:
            self.signals.log.emit("No input files provided.")
            self.signals.finished.emit({})
            return

        processor_name = self._processor.metadata.name
        self.signals.log.emit(f"Starting {processor_name}...")
        log.info("ProcessorWorker started: %s with %d files", processor_name, len(self._input_paths))

        def progress_cb(fraction: float, message: str) -> None:
            self.signals.progress.emit(fraction, message)
            if message:
                self.signals.log.emit(message)

        try:
            if getattr(self._processor, "processing_mode", None) and self._processor.processing_mode.value == "file":
                results = {}
                total_files = len(self._input_paths)
                for idx, input_path in enumerate(self._input_paths):
                    if self._cancel_flag.is_set():
                        break
                    
                    base_progress = idx / total_files
                    def local_progress(fraction: float, msg: str) -> None:
                        overall = base_progress + (fraction / total_files)
                        progress_cb(overall, f"[{input_path.name}] {msg}")
                        
                    try:
                        out_path = self._processor.process_file(
                            input_path=input_path,
                            output_dir=self._output_dir,
                            options=self._options,
                            on_progress=local_progress,
                            cancel_flag=self._cancel_flag,
                        )
                        if out_path:
                            results[input_path] = out_path
                            self.signals.log.emit(f"Processed: {out_path.name}")
                    except Exception as e:
                        log.exception(f"Error processing {input_path}")
                        results[input_path] = {"error": str(e)}
            else:
                results = self._processor.process(
                    input_paths=self._input_paths,
                    output_dir=self._output_dir,
                    options=self._options,
                    on_progress=progress_cb,
                    cancel_flag=self._cancel_flag,
                )
            
            if self._cancel_flag.is_set():
                self.signals.log.emit(f"{processor_name} cancelled by user.")
            else:
                self.signals.log.emit(f"{processor_name} completed successfully.")
                
            self.signals.finished.emit(results)
            
        except Exception as exc:
            if self._cancel_flag.is_set():
                self.signals.log.emit(f"{processor_name} cancelled during error handling.")
            else:
                err_msg = str(exc)
                log.exception("ProcessorWorker failed in %s: %s", processor_name, err_msg)
                self.signals.log.emit(f"Error in {processor_name}: {err_msg}")
                self.signals.error.emit(f"Error: {err_msg}")
            self.signals.finished.emit({})
