# Error Handling

This document defines the error handling philosophy, categorization, and implementation details for the Sound Processor project.

## Philosophy

**Never crash the app.** All exceptions must be caught within the worker thread, gracefully handled, and reported back to the UI via signals. The application state must remain stable.

## Error Categories

| Category | Exception Type | Severity | User Message | Recovery Action |
| :--- | :--- | :--- | :--- | :--- |
| File Missing | `FileNotFoundError` | ERROR | "File not found" | Skip file, continue batch |
| Permissions | `PermissionError` | ERROR | "Cannot read/write file" | Skip file, notify user |
| Format | `UnsupportedFormatError` | WARNING | "Format not supported" | Skip file |
| AI Model | `ModelLoadError` | ERROR | "AI model failed to load" | Abort operation |
| Resource | `OutOfMemoryError` / `torch.cuda.OutOfMemoryError` | ERROR | "Out of memory" | Suggest smaller chunk size |
| User Action | `CancelledError` | INFO | "Processing cancelled" | Clean up partial output |
| External Tool| `FFmpegError` | ERROR | "FFmpeg failed" | Show ffmpeg stderr |
| Validation | `ValidationError` | WARNING | "Invalid options" | Show details |

## Custom Exception Hierarchy

Define custom exceptions to cleanly categorize expected failure modes.

```python
# exceptions.py

class SoundProcessorError(Exception):
    """Base exception for all custom Sound Processor errors."""
    pass

class ModelLoadError(SoundProcessorError):
    pass

class UnsupportedFormatError(SoundProcessorError):
    pass

class FFmpegError(SoundProcessorError):
    pass

class CancelledError(SoundProcessorError):
    pass

class ValidationError(SoundProcessorError):
    pass
```

## Worker Error Flow

1. An exception occurs within `BaseWorker._execute()`.
2. It is caught by the broad `except Exception as e:` block in `BaseWorker.run()`.
3. The worker emits `signals.error.emit(title, detail)`.
4. A GUI `ErrorHandler` component connected to this signal processes the error.
5. The error is logged via `LogPanel.append_error()`.
6. Depending on severity, a `QMessageBox` may be presented to the user.

## Audience Context

- **User-Facing**: Errors presented in popups (`QMessageBox`) must be friendly, actionable, and devoid of stack traces.
- **Developer-Facing**: Full stack traces and granular details must be logged to the application log file and the `LogPanel` for debugging purposes.

## Partial Output Cleanup

When an operation fails or is interrupted (e.g., `CancelledError`), the system must not leave corrupted or partial files on disk. The worker's exception handlers or cleanup blocks must delete any partial output files written during the failed run.

## LogPanel Formatting

Errors reported to the `LogPanel` should be visually distinct:
- Use timestamp prefixes: `[14:32:05] ERROR: ...`
- Color code the text: Red for errors, Yellow for warnings.

## Implementation Example

```python
from exceptions import UnsupportedFormatError, CancelledError
import traceback

# Inside a worker class
def _execute(self):
    try:
        # Example processing logic
        if not self.is_supported(self.file_path):
            raise UnsupportedFormatError(f"Format of {self.file_path} is not supported.")
            
        if self.cancel_flag.is_set():
            raise CancelledError()
            
    except UnsupportedFormatError as e:
        self.signals.log_message.emit("WARNING", str(e))
        # Handle gracefully, perhaps continue to next file
    except CancelledError:
        self.signals.log_message.emit("INFO", "User cancelled operation.")
        self.cleanup_partial_files()
        raise # Reraise to be caught by run()
    except Exception as e:
        # Unexpected error
        error_detail = traceback.format_exc()
        self.signals.error.emit("Unexpected Error", error_detail)
        self.cleanup_partial_files()
        raise
```
