# Shared Features — Sound Processor V1.0

These features are shared across all processors in V1.0 (Converter, Separator, Combiner) and form the interaction foundation of the application.

---

## Batch Processing

Every processor supports operating on multiple files in a single job. Batch mode is not a special mode — it is the default behaviour of all workers.

### How It Works

```
User drops folder or multiple files
    │
    ▼
DropZone.filesDropped([Path, Path, ...])
    │
    ▼
Page builds job list → passes list[Path] to Worker
    │
    ▼
Worker iterates sequentially:
    for i, file in enumerate(files):
        process(file)
        emit progress((i+1)/len(files), message)
```

### Batch Guarantees

- **One failure does not abort the batch.** Each file result (success or error) is logged independently.
- **Sequential processing** — not parallel — to avoid I/O contention and GPU memory conflicts.
- **Cancel mid-batch** is supported: the current file completes, then the job stops cleanly.

---

## Drag & Drop — `gui/widgets/drop_zone.py`

The `DropZone` is a `QLabel` subclass that accepts both drag-and-drop and click-to-browse.

### Events

```python
class DropZone(QLabel):
    filesDropped = Signal(list)   # list[Path] — emitted for both drop and browse

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._set_hover_style(True)

    def dropEvent(self, event):
        paths = [Path(u.toLocalFile()) for u in event.mimeData().urls()]
        expanded = self._expand_dirs(paths)   # recursively find audio files
        self.filesDropped.emit(expanded)

    def mousePressEvent(self, event):
        # Opens QFileDialog on click
        ...
```

### Directory Expansion

When a folder is dropped, `_expand_dirs()` recursively scans for audio files:

```python
AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aiff", ".aif"}

def _expand_dirs(self, paths: list[Path]) -> list[Path]:
    result = []
    for p in paths:
        if p.is_dir():
            result.extend(f for f in p.rglob("*") if f.suffix.lower() in AUDIO_EXTENSIONS)
        elif p.suffix.lower() in AUDIO_EXTENSIONS:
            result.append(p)
    return sorted(result)
```

### Visual States

| State | Appearance |
|-------|-----------|
| Idle | Dashed border, muted text |
| Drag hover | Bright border, accent background tint |
| Files loaded | Shows file count summary |

---

## Queue System

The queue is a simple ordered list managed by each page:

```python
class ConverterPage(QWidget):
    def __init__(self):
        self._queue: list[Path] = []

    def _on_files_dropped(self, paths: list[Path]) -> None:
        self._queue.extend(paths)
        self._refresh_file_list_widget()

    def _on_start_clicked(self) -> None:
        worker = ConverterWorker(files=self._queue, ...)
        worker.start()
```

Files in the queue are displayed in a scrollable list widget. Users can:
- Remove individual files (right-click → Remove)
- Clear all files (Clear button)
- Reorder (drag handles — planned for V1.5)

There is **no global queue** shared between pages — each page manages its own job queue independently.

---

## Progress Tracking — `gui/widgets/progress_panel.py`

The `ProgressPanel` widget displays both per-file and overall job progress.

```python
class ProgressPanel(QWidget):
    def start_job(self, message: str) -> None:
        """Reset bar to 0, show start message."""

    def set_progress(self, fraction: float, message: str) -> None:
        """Update bar (0.0–1.0) and status label. Thread-safe via Qt signals."""

    def set_eta(self, remaining_seconds: float) -> None:
        """Update ETA label: 'ETA: 1m 24s'"""

    def finish_job(self, success: bool, message: str = "") -> None:
        """Set bar to 100%, update status, optionally show result."""
```

### ETA Estimation

ETA is computed using a **rolling average** of per-file processing times:

```python
self._times.append(time.time() - file_start)
avg = sum(self._times[-5:]) / len(self._times[-5:])  # last 5 files
remaining = avg * (total_files - completed_files)
```

---

## Cancellation

All workers support graceful cancellation via `threading.Event`:

```python
class BaseWorker(QRunnable):
    def __init__(self):
        self._cancel_flag = threading.Event()

    def cancel(self) -> None:
        self._cancel_flag.set()
```

Workers check the flag **between files** (batch) and **between chunks** (AI inference):

```python
# Batch loop
for file in files:
    if self._cancel_flag.is_set():
        self.signals.log.emit("⚠ Cancelled by user.")
        break
    process(file)

# Chunk loop (AI inference)
for chunk in chunks:
    if cancel_flag and cancel_flag.is_set():
        return {}   # partial result discarded
    result = model_infer(chunk)
```

### Partial Output Cleanup

When a job is cancelled mid-file, any partially written output file is deleted:

```python
try:
    write_output(temp_path, ...)
    temp_path.rename(final_path)
except (CancelledError, Exception):
    if temp_path.exists():
        temp_path.unlink()
    raise
```

All writes go to a `.tmp` file first, renamed to the final path only on success.

---

## Cross-Platform Support

| Concern | macOS (Primary) | Windows | Linux |
|---------|----------------|---------|-------|
| Qt platform plugin | Homebrew PyQt6 (arm64/tahoe) | pip PyQt6 | pip PyQt6 |
| FFmpeg | `brew install ffmpeg` or PATH | System PATH or bundled | System PATH |
| Path separators | `Path` object always used — never string concatenation | Same | Same |
| Output dirs | `~/Documents/sound-processor/outputs/` | `%USERPROFILE%\Documents\...` | `~/Documents/...` |
| File permissions | Standard POSIX | Standard Win32 | Standard POSIX |

### Path Handling Rules

1. **Always use `pathlib.Path`** — never `os.path.join()` or string `+`
2. **Never hardcode `/Users/mac/...`** — use `Path.home()` or `AppConfig.output_dir`
3. **Detect OS at runtime** via `sys.platform` only for platform-specific behaviour (never for path logic)
