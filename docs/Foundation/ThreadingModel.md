# Threading Model

This document specifies the threading architecture for the Sound Processor project to ensure UI responsiveness and memory safety.

## Core Rule

**ALL heavy work MUST run in `QThread` workers. NEVER execute blocking operations on the UI thread.**

## Signal Communication (`WorkerSignals`)

Communication between background threads and the GUI must occur exclusively via signals.

```python
from qtpy.QtCore import QObject, pyqtSignal

class WorkerSignals(QObject):
    progress = pyqtSignal(int, int)      # current, total
    log_message = pyqtSignal(str, str)   # level, message
    error = pyqtSignal(str, str)         # title, detail
    result = pyqtSignal(object)          # final output data
    finished = pyqtSignal()              # emitted when run() completes
```

## The CRITICAL `finished` Distinction

Understanding thread lifecycle is paramount to preventing crashes.

- **`signals.finished`**: Fires from INSIDE the worker's `run()` method while the thread is still technically executing. **UNSAFE** to call `deleteLater` here, as the thread has not fully stopped.
- **`QThread.finished`**: Fires AFTER the `run()` method has exited and the thread loop has officially stopped. **SAFE** to call `deleteLater` here.

**Pattern:** ALWAYS connect `QThread.finished` → `worker.deleteLater`. NEVER connect `signals.finished` to `deleteLater`.

### Connection Example

```python
# CORRECT
worker = MyWorker()
worker.signals.result.connect(self.handle_result)
worker.finished.connect(worker.deleteLater) # Correct lifecycle management
worker.start()

# WRONG - DO NOT DO THIS
# worker.signals.finished.connect(worker.deleteLater) 
# Reason: deleteLater might execute while run() is still cleaning up, causing a segfault.
```

## Base Worker Pattern

All background tasks should inherit from a common base class or follow this structural pattern:

```python
import threading
from qtpy.QtCore import QThread
from exceptions import CancelledError

class BaseWorker(QThread):
    def __init__(self):
        super().__init__()
        self.signals = WorkerSignals()
        self.cancel_flag = threading.Event()

    def cancel(self):
        """Called from the main thread to request cancellation."""
        self.cancel_flag.set()

    def run(self):
        try:
            self._execute()
        except CancelledError:
            self.signals.log_message.emit("INFO", "Operation was cancelled.")
        except Exception as e:
            self.signals.error.emit("Processing Error", str(e))
        finally:
            self.signals.finished.emit()

    def _execute(self):
        # Override this method in subclasses
        pass
```

## Cancellation Checking

Workers that process data in chunks or iterations must frequently check the `cancel_flag`.

```python
    def _execute(self):
        total_chunks = 100
        for i in range(total_chunks):
            # Check for cancellation before expensive operations
            if self.cancel_flag.is_set():
                raise CancelledError("Processing cancelled by user")
            
            # ... process chunk ...
            self.signals.progress.emit(i + 1, total_chunks)
```

## Memory and GUI Thread Rules

- **Memory Safety**: Do not access Python objects or data structures belonging to a worker after the worker has been deleted or finished. Pass necessary data out via the `result` signal.
- **GUI Thread Rule**: Only `QObject` instances created on the GUI thread can be directly manipulated from the GUI thread. Never call methods on UI widgets (like `setText`) directly from a background worker.
- **Shared State**: If multiple threads must mutate shared state (rare in our architecture), use a `QMutex` to prevent race conditions.
