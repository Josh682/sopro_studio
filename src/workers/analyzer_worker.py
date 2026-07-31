"""Background thread for analyzing audio files."""

import logging
import threading
from pathlib import Path

from qtpy.QtCore import QThread, Signal

from src.core.processors.audio_analyzer import AudioAnalyzer
from src.audio.metadata import AudioInfo

log = logging.getLogger("sound_processor.workers.analyzer_worker")

class AnalyzerWorker(QThread):
    """Executes AudioAnalyzer in a background thread."""

    # Signals
    # progress: fraction (0.0 to 1.0), message
    progress = Signal(float, str)
    # log: message
    log_msg = Signal(str)
    # error: message
    error = Signal(str)
    # finished: mapping of Path -> AudioInfo
    finished_analysis = Signal(dict)

    def __init__(self, input_paths: list[Path]) -> None:
        super().__init__()
        self.setStackSize(8 * 1024 * 1024)
        
        self._input_paths = input_paths
        self._cancel_flag = threading.Event()

    def cancel(self) -> None:
        """Signal the worker to cancel processing."""
        self._cancel_flag.set()
        self.log_msg.emit("Cancelling Audio Analysis...")

    def run(self) -> None:
        """Execute the analyzer for all input paths."""
        if not self._input_paths:
            self.log_msg.emit("No input files provided.")
            self.finished_analysis.emit({})
            return

        self.log_msg.emit(f"Starting analysis for {len(self._input_paths)} files...")
        log.info("AnalyzerWorker started with %d files", len(self._input_paths))

        results: dict[Path, AudioInfo] = {}
        total = len(self._input_paths)

        try:
            for idx, path in enumerate(self._input_paths):
                if self._cancel_flag.is_set():
                    break

                base_progress = idx / total
                
                def local_progress(fraction: float, msg: str) -> None:
                    overall = base_progress + (fraction / total)
                    self.progress.emit(overall, f"[{path.name}] {msg}")

                try:
                    info = AudioAnalyzer.analyze(
                        file_path=path,
                        on_progress=local_progress,
                        cancel_flag=self._cancel_flag,
                    )
                    results[path] = info
                    self.log_msg.emit(f"Analyzed: {path.name}")
                except Exception as e:
                    log.exception("Error analyzing %s", path)
                    self.log_msg.emit(f"Error analyzing {path.name}: {e}")

            if self._cancel_flag.is_set():
                self.log_msg.emit("Analysis cancelled by user.")
            else:
                self.log_msg.emit("Analysis completed successfully.")
                self.progress.emit(1.0, "Analysis complete")
                
            self.finished_analysis.emit(results)
            
        except Exception as exc:
            if self._cancel_flag.is_set():
                self.log_msg.emit("Analysis cancelled during error handling.")
            else:
                err_msg = str(exc)
                log.exception("AnalyzerWorker failed: %s", err_msg)
                self.log_msg.emit(f"Error: {err_msg}")
                self.error.emit(f"Error: {err_msg}")
            self.finished_analysis.emit(results)
