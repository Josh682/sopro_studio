# Audio Converter — Sound Processor V1.0

## Purpose

Convert audio files between WAV, MP3, and FLAC formats with full control over quality parameters. The primary use case is **DAW compatibility preparation** — ensuring stems, samples, and recordings are in the exact format, bit depth, and sample rate required by a project before import.

---

## Conversion Matrix

All 6 cross-format paths are supported:

| Input | Output | Read Engine | Write Engine |
|-------|--------|------------|-------------|
| MP3 | WAV | FFmpeg decode → PCM | soundfile |
| MP3 | FLAC | FFmpeg decode → PCM | soundfile |
| WAV | MP3 | soundfile | FFmpeg encode |
| WAV | FLAC | soundfile | soundfile |
| FLAC | WAV | soundfile | soundfile |
| FLAC | MP3 | soundfile | FFmpeg encode |

MP3 always routes through FFmpeg (no native Python MP3 encoder). WAV ↔ FLAC paths are pure soundfile.

---

## Core API: `core/converter.py`

### `ConvertOptions` Dataclass

```python
@dataclass
class ConvertOptions:
    output_format: str           # "wav" | "mp3" | "flac"
    normalize: bool = False      # Peak normalize before export

    # WAV-specific
    bit_depth: int = 16          # 8 | 16 | 24 | 32 (float)
    sample_rate: int | None = None  # None = preserve source SR

    # MP3-specific
    mp3_bitrate: int = 192       # 128 | 192 | 256 | 320 kbps

    # FLAC-specific
    flac_compression: int = 5    # 0 (fastest) – 8 (smallest file)
```

### `Converter` Class

```python
class Converter:
    def convert(
        self,
        input_path: Path,
        output_dir: Path,
        options: ConvertOptions,
        on_progress: Callable[[float, str], None] | None = None,
    ) -> Path:
        """
        Convert a single audio file.
        Returns the output Path on success.
        Raises ConversionError on failure.
        """

    def convert_batch(
        self,
        input_paths: list[Path],
        output_dir: Path,
        options: ConvertOptions,
        on_progress: Callable[[float, str], None] | None = None,
        cancel_flag: threading.Event | None = None,
    ) -> dict[Path, Path | Exception]:
        """
        Convert multiple files. Returns {input: output_or_exception}.
        A single failure does NOT abort the batch.
        """
```

### Internal Pipeline

```
input_path
    │
    ├─ [if MP3] FFmpeg decode → raw PCM pipe → numpy array
    ├─ [if WAV/FLAC] soundfile.read() → numpy array
    │
    ├─ [optional] librosa.resample() to target_sample_rate
    ├─ [optional] peak normalize
    │
    ├─ [if output WAV/FLAC] soundfile.write()
    └─ [if output MP3] numpy PCM → FFmpeg stdin pipe → .mp3
```

---

## Worker: `workers/converter_worker.py`

Runs all conversion in a `QThread` — the UI never blocks.

```python
class ConverterWorker(BaseWorker):
    def __init__(
        self,
        files: list[Path],
        output_dir: Path,
        options: ConvertOptions,
    ): ...

    def run(self) -> None:
        converter = Converter()
        for i, file in enumerate(self._files):
            if self._cancel_flag.is_set():
                break
            try:
                out = converter.convert(file, self._output_dir, self._options,
                                        on_progress=self._on_chunk_progress)
                self.signals.log.emit(f"✓ {file.name} → {out.name}")
            except ConversionError as e:
                self.signals.error.emit(f"✗ {file.name}: {e}")
            self.signals.progress.emit((i + 1) / len(self._files), f"{i+1}/{len(self._files)}")
        self.signals.finished.emit(self._results)
```

### Signals

| Signal | Payload | Description |
|--------|---------|-------------|
| `progress` | `(float, str)` | Overall batch progress 0.0–1.0 + status |
| `log` | `str` | Per-file success or skip message |
| `error` | `str` | Per-file error (non-fatal, batch continues) |
| `finished` | `dict` | `{input_path: output_path}` for all succeeded files |

---

## UI Layout: `gui/converter_page.py`

```
┌─────────────────────────────────────────────────────┐
│  Audio Converter                                    │
├─────────────────────────────────────────────────────┤
│  [ Drop Zone — drag files or folders here ]         │
│  Accepts: .wav  .mp3  .flac  .ogg  .m4a            │
├──────────────────────────┬──────────────────────────┤
│  Selected Files (3)      │  Export Settings         │
│  ─────────────────────   │  ─────────────────────── │
│  ✓ song.mp3              │  Output Format: [ WAV ▾] │
│  ✓ beat.wav              │                          │
│  ✓ loop.flac             │  Bit Depth:  [ 24-bit ▾] │
│                          │  Sample Rate: [ Keep ▾ ] │
│  [Clear All]             │  ☐ Normalize to 0 dBFS   │
│                          │                          │
│                          │  Output Folder:          │
│                          │  [/outputs/]  [Browse]   │
├──────────────────────────┴──────────────────────────┤
│  [Start Conversion]                      [Cancel]   │
├─────────────────────────────────────────────────────┤
│  ████████████░░░░ 67%   2/3 files   ETA: 3s         │
├─────────────────────────────────────────────────────┤
│  Log                                                │
│  ✓ song.mp3 → song.wav                             │
│  ✓ beat.wav → beat.wav (already WAV, re-encoded)   │
│  ⋯ loop.flac converting...                         │
└─────────────────────────────────────────────────────┘
```

### Format-Specific Settings Panel

The settings panel updates dynamically when **Output Format** changes:

| Format | Settings Shown |
|--------|---------------|
| WAV | Bit Depth (8 / 16 / 24 / 32-float), Sample Rate |
| MP3 | Bitrate (128 / 192 / 256 / 320 kbps) |
| FLAC | Compression Level 0–8 (slider) |

---

## Batch Processing

- Directories dropped on the DropZone are **recursively scanned** for `.wav`, `.mp3`, `.flac`, `.ogg`, `.m4a`
- Files are processed sequentially in the worker (not parallel — avoids I/O contention)
- A single failed file logs an error and continues — does not abort the batch
- Output collision handling: `unique_output_path()` in `utils/file_utils.py` appends `_1`, `_2`, etc.

### Output Naming

```
song.mp3        →  song.wav
song.mp3 (dup)  →  song_1.wav
```

---

## Export Settings Reference

### WAV Bit Depths

| Bit Depth | Range | Use Case |
|-----------|-------|----------|
| 8-bit | 0–255 | Legacy / lo-fi |
| 16-bit | ±32768 | CD quality, default for most DAWs |
| 24-bit | ±8388608 | Studio standard, recommended for DAW import |
| 32-bit float | ±1.0 | Maximum precision, no clipping risk |

### MP3 Bitrates

| Bitrate | Quality | File Size (3min) |
|---------|---------|-----------------|
| 128 kbps | Acceptable | ~2.9 MB |
| 192 kbps | Good | ~4.3 MB |
| 256 kbps | Very Good | ~5.8 MB |
| 320 kbps | Transparent | ~7.2 MB |

### FLAC Compression Levels

| Level | Encode Speed | File Size |
|-------|-------------|-----------|
| 0 | Fastest | Largest |
| 5 | Balanced (default) | Medium |
| 8 | Slowest | Smallest |

Audio quality is **lossless** at all FLAC compression levels — only speed/size trade-off.

---

## Error Handling

| Error | Handling |
|-------|----------|
| Unsupported input format | Validate extension before queuing; show error in log |
| Missing FFmpeg (for MP3) | Detect before processing; link user to Settings |
| Corrupted file | Catch decode exception; log error; continue batch |
| Disk full | Catch `OSError` errno 28; abort with clear message |
| Output permission denied | Catch `PermissionError`; show path in error |
