# System Architecture

## Overview

The Sound Processor is designed with a strict layered architecture to ensure separation of concerns, maintainability, and responsiveness. The application consists of several distinct layers, with communication flowing in specific, constrained directions.

## Layered Architecture Diagram

```ascii
+-------------------------------------------------------------+
|                        GUI Layer                            |
|             (PyQt6 Pages, Widgets, MainWindow)              |
+-------------------------------------------------------------+
          | (starts)                        ^ (signals)
          v                                 |
+-------------------------------------------------------------+
|                      Worker Layer                           |
|                (QThread, BaseWorker, etc.)                  |
+-------------------------------------------------------------+
          | (calls)                         ^ (returns/yields)
          v                                 |
+-------------------------------------------------------------+
|                        Core Layer                           |
|      (Processors, ProcessorRegistry, Exporter, Config)      |
+-------------------------------------------------------------+
          | (uses)                          ^ (data)
          v                                 |
+-------------------------------------------------------------+
|              Audio / AI / Utils Layers                      |
| (Loader, Writer, Metadata, AI Models, Logger, Config, ffmpeg)
+-------------------------------------------------------------+
```

## Layer Responsibilities

### 1. GUI Layer
- **Components:** PyQt6 main window, sidebar, feature pages, and reusable widgets (drop zones, progress panels, log panels, etc.).
- **Responsibilities:** 
  - Render the user interface and handle user interactions.
  - Collect input data (files, parameters).
  - Instantiate and start workers from the Worker Layer.
  - Listen to signals emitted by workers to update the UI (progress bars, logs, errors, results).
- **Rule:** The GUI layer must never perform heavy computations or blocking operations.

### 2. Worker Layer
- **Components:** `BaseWorker`, `ProcessorWorker`, and other `QThread`-based worker classes.
- **Responsibilities:**
  - Execute long-running tasks (audio processing, AI inference) on background threads.
  - Wrap calls to the Core Layer.
  - Emit Qt signals (`progress`, `log`, `error`, `finished`) back to the GUI Layer.
- **Rule:** Workers bridge the gap between the synchronous GUI and the synchronous/blocking Core, ensuring the GUI remains responsive.

### 3. Core Layer
- **Components:** Audio processors, processor registry, exporter logic, and core configuration management.
- **Responsibilities:**
  - Orchestrate the actual audio manipulation workflows.
  - Implement the business logic for specific features (e.g., format conversion, stem separation).
  - Delegate specialized tasks to the bottom layers (Audio, AI, Utils).

### 4. Audio, AI, and Utils Layers
- **Components:**
  - **Audio:** Loaders, writers, metadata extractors, interacting with FFmpeg or lower-level audio libraries.
  - **AI:** Wrappers around machine learning models (e.g., source separation, transcription).
  - **Utils:** Logging, configuration parsing, and general utility functions.
- **Responsibilities:**
  - Provide foundational, highly specialized capabilities used by the Core layer.

## Data Flow

When a user initiates a process (e.g., dropping a file and clicking "Process"):
1. **Input:** The GUI layer captures the file path and user-selected parameters.
2. **Dispatch:** The GUI instantiates a specific `QThread` worker, passing the file and parameters.
3. **Execution:** The worker starts running in the background. It initializes the appropriate Core processor.
4. **Processing:** The Core processor utilizes the Audio layer to load the file into a NumPy array (internal float32 buffer), optionally utilizes the AI layer for inference, and then writes the result using the Audio layer.
5. **Feedback:** Throughout the execution, the worker emits signals. The GUI layer catches these signals to update progress bars and log panels.
6. **Completion:** Upon completion, the worker emits a final signal with the output file path. The GUI displays the result to the user.

## Module Dependency Rules

To prevent circular dependencies and maintain clean architecture, strict import rules apply:
- **GUI Layer** can import from **Worker Layer**, **Core Layer**, and **Utils**.
- **Worker Layer** can import from **Core Layer** and **Utils**.
- **Core Layer** can import from **Audio**, **AI**, and **Utils**.
- **Audio, AI, and Utils** are independent and should not import from upper layers.
- **Lower layers must never import from upper layers.**

## Signal/Slot Communication Model

Communication from background threads (Workers) to the main thread (GUI) is handled exclusively via PyQt signals and slots to ensure thread safety.

```ascii
[Worker Thread]                          [Main Thread (GUI)]
      |                                           |
      |---(emit progress_signal(int))------------>|---> update_progress_bar()
      |                                           |
      |---(emit log_signal(str))----------------->|---> append_to_log_panel()
      |                                           |
      |---(emit error_signal(Exception))--------->|---> show_error_dialog()
      |                                           |
      |---(emit finished_signal(result))--------->|---> display_results()
```

## Key Design Decisions

1. **PyQt6 via Homebrew (macOS):** 
   - *Rationale:* Ensures native integration and stability on macOS, avoiding common pip installation conflicts with system libraries.
2. **MPS Acceleration:** 
   - *Rationale:* Leverages Apple Silicon's Metal Performance Shaders for AI model inference, providing significant speedups over CPU processing without requiring NVIDIA GPUs.
3. **QThread over asyncio:**
   - *Rationale:* PyQt6 integrates seamlessly with `QThread`. Since the application involves heavy CPU/GPU bound tasks rather than pure I/O bound tasks, `QThread` provides a simpler and more robust model for parallel execution alongside the GUI event loop.
4. **NumPy float32 Internal Buffer:**
   - *Rationale:* Standardizing on `float32` arrays for all internal audio representation ensures maximum precision during processing and seamless interoperability with PyTorch and other scientific computing libraries.
