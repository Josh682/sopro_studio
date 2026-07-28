# Instrument Separator — Sound Processor V1.0

## Purpose

Use AI models to split a mixed audio file into individual **stems** (vocals, drums, bass, etc.) ready for direct import into a DAW. The system is **model-agnostic** — stem names, count, and capabilities are discovered at runtime from each model's metadata. The UI never hardcodes stem names.

---

## Design Principle: Dynamic Stem Discovery

```python
@dataclass(frozen=True)
class ModelMetadata:
    model_id:      str
    display_name:  str
    description:   str
    stem_names:    tuple[str, ...]   # e.g. ("vocals", "drums", "bass", ...)
    output_format: str               # always "wav"
    sample_rate:   int               # e.g. 44100
    input_formats: tuple[str, ...]   # e.g. ("wav", "mp3", "flac")
```

The `StemPreviewWidget` reads `metadata.stem_names` and rebuilds its display on every model change. **Adding a new 12-stem model requires zero UI code changes.**

---

## Model Interface: `ai/base_model.py`

```python
class BaseSeparatorModel(ABC):

    @property
    @abstractmethod
    def metadata(self) -> ModelMetadata: ...

    @abstractmethod
    def load(self, models_dir: Path) -> None:
        """Download weights if missing, load into memory (GPU/MPS/CPU)."""

    @abstractmethod
    def separate(
        self,
        audio: np.ndarray,         # float32, shape (channels, samples)
        sample_rate: int,
        on_progress: Callable[[float, str], None] | None = None,
        cancel_flag: threading.Event | None = None,
    ) -> dict[str, np.ndarray]:    # {stem_name: audio_array}
        """Return one float32 array per stem."""
```

---

## Model Manager: `ai/model_manager.py`

```python
class ModelManager:
    def register_model(self, model_id: str, factory: type[BaseSeparatorModel]) -> None

    def list_models(self) -> list[ModelMetadata]:
        """Lightweight — returns metadata without loading weights."""

    def get_model(self, model_id: str) -> BaseSeparatorModel:
        """Lazy-instantiate. Weights loaded once per session."""

    def unload_all(self) -> None:
        """Release GPU memory between large jobs."""
```

Models are **loaded once per session** — not once per file. Calling `get_model()` on the same ID returns the cached instance.

---

## Shipped Models (V1.0)

### MelBand-RoFormer — Kim Vocal Model

| Property | Value |
|----------|-------|
| Model ID | `melband-roformer-kim-vocals` |
| Display Name | MelBand-RoFormer (Vocals) |
| Stems | `vocals`, `instrumental` |
| Package | `melband-roformer-infer` |
| Chunk Size | 352,800 samples (~8s at 44.1kHz) |
| VRAM (MPS) | ~2 GB |
| Adapter | `ai/melband.py` |

### BS-RoFormer — 6-Stem Model

| Property | Value |
|----------|-------|
| Model ID | `roformer-model-bs-roformer-ep_317_sdr_12.9755` |
| Display Name | BS-RoFormer (6 Stems) |
| Stems | `vocals`, `drums`, `bass`, `guitar`, `piano`, `other` |
| Package | `bs-roformer-infer` |
| Chunk Size | 588,800 samples (~13s at 44.1kHz) |
| VRAM (MPS) | ~4 GB |
| Adapter | `ai/bs_roformer.py` |

---

## Separator Orchestrator: `core/separator.py`

```python
class Separator:
    def separate(
        self,
        model: BaseSeparatorModel,
        input_path: Path,
        output_dir: Path,
        on_progress: Callable[[float, str], None] | None = None,
        cancel_flag: threading.Event | None = None,
    ) -> dict[str, Path]:
        """
        1. Load + preprocess audio (resample to model SR, mono→stereo if needed)
        2. Call model.separate()
        3. Validate returned stems match metadata.stem_names
        4. Write one WAV per stem via ExportEngine
        5. Return {stem_name: output_path}
        """
```

### Output Naming

```
input:   my_song.mp3
output:  vocals_my_song.wav
         drums_my_song.wav
         bass_my_song.wav
         guitar_my_song.wav
         piano_my_song.wav
         other_my_song.wav
```

---

## Worker: `workers/separator_worker.py`

```
SeparatorWorker.run()
    │
    ├── emit log("Loading model: BS-RoFormer...")
    ├── manager.get_model(model_id)        # lazy load / auto-download
    │
    ├── emit log("Probing input file...")
    ├── audio/metadata.probe(input_path)   # validate format, get info
    │
    ├── emit log("Starting separation...")
    ├── separator.separate(model, ...)
    │       └── model.separate() chunk loop with progress callbacks
    │
    └── emit signals.finished(result_dict)
```

### QThread Cleanup Rule

```python
# CORRECT: deleteLater on QThread.finished (fires after run() exits)
self._thread.finished.connect(self._thread.deleteLater)
self._thread.finished.connect(self._worker.deleteLater)

# WRONG: deleteLater on signals.finished (fires inside run() — thread still alive)
# self._worker.signals.finished.connect(self._thread.deleteLater)  ← CRASH
```

---

## UI Layout: `gui/separator_page.py`

```
┌──────────────────────────────────────────────────────────┐
│  Instrument Separator                                    │
├──────────────────────────────────────────────────────────┤
│  AI Model: [ BS-RoFormer (6 Stems)                   ▾] │
│  Produces: vocals · drums · bass · guitar · piano · other│
├───────────────────────────┬──────────────────────────────┤
│  [ Drop Zone ]            │  File Info                   │
│                           │  Name:   my_song.mp3         │
│                           │  Format: MP3 (192 kbps)      │
│                           │  SR:     44100 Hz            │
│                           │  Ch:     Stereo              │
│                           │  Dur:    3m 42s              │
│                           │  ──────────────────          │
│                           │  Output Stems:               │
│                           │  ○ vocals                    │
│                           │  ○ drums                     │
│                           │  ○ bass                      │
│                           │  ○ guitar                    │
│                           │  ○ piano                     │
│                           │  ○ other                     │
├───────────────────────────┴──────────────────────────────┤
│  Output: [/outputs/]                       [Browse]      │
│  [Separate Stems]                          [Cancel]      │
├──────────────────────────────────────────────────────────┤
│  ██████████████░░░░░░ 68%   ETA: 24s                     │
├──────────────────────────────────────────────────────────┤
│  Log                                                     │
│  ✓ Loading BS-RoFormer model weights...                  │
│  ✓ Processing chunk 5/7...                               │
└──────────────────────────────────────────────────────────┘
```

### `StemPreviewWidget` (`gui/widgets/stem_preview.py`)

Rebuilds its stem chip list whenever `update_stems(stem_names)` is called:

```python
stem_preview.update_stems(("vocals", "drums", "bass", "guitar", "piano", "other"))
# → clears old chips, creates 6 new QLabel chips in a flow layout
```

---

## Memory & Performance

| Model | Chunk Samples | Duration/Chunk | Approx VRAM |
|-------|-------------|---------------|-------------|
| MelBand-RoFormer | 352,800 | ~8s | ~2 GB MPS |
| BS-RoFormer | 588,800 | ~13s | ~4 GB MPS |

- Both use **overlap-add chunking** — long tracks split into windows with crossfade
- BS-RoFormer accumulates partial results on CPU to avoid MPS OOM
- Chunk size is configurable in Settings per model

---

## How to Add a New Model (3 Steps)

```python
# Step 1 — Create ai/my_model.py
class MyModel(BaseSeparatorModel):
    @property
    def metadata(self) -> ModelMetadata:
        return ModelMetadata(
            model_id="my-model-v1",
            display_name="My Custom Model",
            description="9-stem drum kit separator",
            stem_names=("kick", "snare", "hihat", "overhead", "bass",
                        "guitar", "keys", "vocals", "fx"),
            output_format="wav",
            sample_rate=44100,
            input_formats=("wav", "mp3", "flac"),
        )

    def load(self, models_dir: Path) -> None: ...
    def separate(self, audio, sample_rate, ...): ...

# Step 2 — Register in ai/__init__.py
from .my_model import MyModel
manager.register_model("my-model-v1", MyModel)

# Step 3 — Done. UI updates automatically.
```

---

## Error Handling

| Error | Handling |
|-------|----------|
| Model weights missing | Auto-download on first use with progress |
| OOM during inference | Suggest reducing chunk size in Settings |
| Unsupported input format | Probe before processing; show error |
| Cancelled mid-chunk | Clean up partial output files |
| Stem dict mismatch | Raise `SeparationError` with clear message |
