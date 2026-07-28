# Processor Framework

The Sound Processor project utilizes a robust, extensible Processor pattern. Every audio transformation or analysis module implements a common interface, allowing the core application to discover, configure, and execute processors uniformly.

## Extensible Processor Pattern

The architecture is built around the `BaseProcessor` abstract base class (ABC). This ensures that any new audio processing capability conforms to a standard API.

### `ProcessorMetadata` Dataclass

Each processor must define its metadata using the `ProcessorMetadata` dataclass:

```python
from dataclasses import dataclass

@dataclass
class ProcessorMetadata:
    id: str
    name: str
    description: str
    version: str
    category: str
    tags: list[str]
```

### `BaseProcessor` Interface

The `BaseProcessor` defines the core contract for all processors:

```python
from abc import ABC, abstractmethod
from typing import ClassVar
import numpy as np

class BaseProcessor(ABC):
    metadata: ClassVar[ProcessorMetadata]

    @abstractmethod
    def process(self, audio: np.ndarray, sample_rate: int, options: dict) -> np.ndarray | dict:
        """Process the audio array with the given options."""
        pass

    def validate_options(self, options: dict) -> None:
        """Optional: Validate options before processing."""
        pass

    @classmethod
    def get_parameter_descriptors(cls) -> list['ParameterDescriptor']:
        """Optional: Return descriptors for UI generation."""
        return []
```

### `ParameterDescriptor` Dataclass

To enable dynamic UI generation, processors can expose parameters via `ParameterDescriptor`:

```python
from dataclasses import dataclass
from typing import Any, Optional

@dataclass
class ParameterDescriptor:
    name: str
    label: str
    type: str  # 'float', 'int', 'bool', 'choice'
    default: Any
    min: Optional[float] = None
    max: Optional[float] = None
    choices: Optional[list[str]] = None
    tooltip: str = ""
```

## UI Auto-Adaptation

The UI layer uses `get_parameter_descriptors()` to dynamically generate configuration forms. For example, if a descriptor specifies `type: 'float'`, the UI renders a slider or spin box; if `type: 'choice'`, it renders a dropdown menu.

## Processor Registry

Processors are managed by the `ProcessorRegistry`, a singleton responsible for auto-discovery. It uses `importlib` to scan the processor modules and register any subclass of `BaseProcessor`.

```python
import importlib
import pkgutil

class ProcessorRegistry:
    _instance = None
    _processors = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register(self, processor_class):
        self._processors[processor_class.metadata.id] = processor_class

    def discover(self, package):
        for _, name, _ in pkgutil.iter_modules(package.__path__):
            importlib.import_module(f"{package.__name__}.{name}")
```

## `ProcessorWorker`

To keep the UI responsive, processors run in a separate thread using `ProcessorWorker`, a QThread wrapper.

```python
from PyQt6.QtCore import QThread, pyqtSignal

class ProcessorWorker(QThread):
    progress = pyqtSignal(int)
    log = pyqtSignal(str)
    error = pyqtSignal(str)
    result = pyqtSignal(object)

    def __init__(self, processor: BaseProcessor, audio, sample_rate, options):
        super().__init__()
        self.processor = processor
        self.audio = audio
        self.sample_rate = sample_rate
        self.options = options

    def run(self):
        try:
            res = self.processor.process(self.audio, self.sample_rate, self.options)
            self.result.emit(res)
        except Exception as e:
            self.error.emit(str(e))
```

## Adding a New Processor

1. **Create file:** Create a new Python file in the processors directory.
2. **Implement:** Subclass `BaseProcessor` and define `ProcessorMetadata`.
3. **Register:** Ensure it's imported (often handled by auto-discovery).

```python
# example_processor.py
from foundation import BaseProcessor, ProcessorMetadata, ParameterDescriptor
import numpy as np

class GainProcessor(BaseProcessor):
    metadata = ProcessorMetadata(
        id="gain_processor",
        name="Gain",
        description="Adjusts the volume of the audio.",
        version="1.0.0",
        category="utility",
        tags=["volume", "gain"]
    )

    @classmethod
    def get_parameter_descriptors(cls):
        return [
            ParameterDescriptor(name="gain_db", label="Gain (dB)", type="float", default=0.0, min=-60.0, max=24.0)
        ]

    def process(self, audio: np.ndarray, sample_rate: int, options: dict):
        gain_db = options.get("gain_db", 0.0)
        multiplier = 10 ** (gain_db / 20.0)
        return audio * multiplier
```

## Category Taxonomy

Processors fall into one of these standard categories:
- **conversion:** Format or sample rate changes.
- **separation:** Stem extraction, vocal isolation.
- **utility:** Gain, trimming, basic editing.
- **enhancement:** Noise reduction, EQ, compression.
- **analysis:** BPM detection, spectral analysis.
