# Logging

The logging subsystem provides comprehensive tracking of application state, errors, and user-facing events. It is implemented in `utils/logger.py`.

## Design and Location

The logging system utilizes standard Python `logging` with a `RotatingFileHandler`.
- **Log File Location**: `logs/sound_processor.log`
- **Rotation**: `maxBytes=5MB`, `backupCount=3`

## Logger Naming Convention

Every module should instantiate its own logger using the `__name__` attribute to maintain a clear module hierarchy in the logs.
```python
import logging
logger = logging.getLogger(__name__)
```

## Log Levels

- **DEBUG**: Internal state, buffer shapes, model parameters, fine-grained execution flow.
- **INFO**: User-visible milestones (e.g., file loaded, processing started, file saved).
- **WARNING**: Recoverable issues (e.g., FFmpeg fallback used, model running on CPU instead of GPU).
- **ERROR**: Operation failed, but the application can continue running (e.g., failed to process a specific file in a batch).
- **CRITICAL**: Unrecoverable errors that may require the application to exit.

## Standard Vocabulary

To ensure consistency, log messages should use standard prefixes:
- `[LOAD]`: File loading events.
- `[PROCESS]`: Audio processing events.
- `[EXPORT]`: File writing and export events.
- `[MODEL]`: ML model loading and inference events.
- `[WORKER]`: Threading and worker lifecycle events.
- `[CONFIG]`: Settings and configuration events.

## GUI Integration (LogPanel)

Workers running in background threads emit log lines to the main GUI `LogPanel` via Qt signals.
- **Signal**: `WorkerSignals.log_message(str, str)` where the arguments are `(level, message)`.
- The `LogPanel` widget subscribes to these signals and appends colored text based on the log level (e.g., red for ERROR, yellow for WARNING).

## Setup Example

```python
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys

def setup_logging(log_level_str: str = "INFO"):
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "sound_processor.log"
    
    numeric_level = getattr(logging, log_level_str.upper(), logging.INFO)
    
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # File Handler
    file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3)
    file_handler.setFormatter(formatter)
    
    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # Root Logger Configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
```

## Using Logger in a Worker

```python
import logging
from PyQt6.QtCore import QRunnable, pyqtSignal, QObject

logger = logging.getLogger(__name__)

class WorkerSignals(QObject):
    log_message = pyqtSignal(str, str) # level, message

class AudioWorker(QRunnable):
    def __init__(self, filename):
        super().__init__()
        self.filename = filename
        self.signals = WorkerSignals()
        
    def run(self):
        msg = f"[PROCESS] Starting processing for {self.filename}"
        logger.info(msg)
        self.signals.log_message.emit("INFO", msg)
        
        try:
            # Simulated processing
            logger.debug(f"[PROCESS] Buffer shape: (44100, 2)")
            
            msg = f"[EXPORT] Successfully saved {self.filename}"
            logger.info(msg)
            self.signals.log_message.emit("INFO", msg)
        except Exception as e:
            msg = f"[ERROR] Failed to process {self.filename}: {e}"
            logger.error(msg, exc_info=True)
            self.signals.log_message.emit("ERROR", msg)
```
