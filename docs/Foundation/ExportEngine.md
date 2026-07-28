# Export Engine

The Export Engine is responsible for writing processed audio buffers to disk in various formats. The core implementation is located in `core/exporter.py`.

## Core Responsibility

The `core/exporter.py` module takes a processed audio buffer (NumPy array) along with an `ExportOptions` configuration, writes the audio data to disk in the specified format, and returns the output path(s).

## ExportOptions Configuration

The `ExportOptions` dataclass encapsulates all settings required for exporting audio files:

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

@dataclass
class ExportOptions:
    format: Literal['wav', 'mp3', 'flac', 'ogg', 'aac']
    bit_depth: Literal[16, 24, 32]
    sample_rate: Optional[int]
    mp3_bitrate: Literal[128, 192, 256, 320]
    flac_compression: int # 0-8
    normalize: bool
    normalize_target_lufs: float = -14.0
    output_dir: Path
    filename_template: str
    overwrite: bool
```

## Format-Specific Write Paths

The exporter handles different formats using specific libraries:
- **WAV**: Written using the `soundfile` library.
- **MP3**: Written using an `ffmpeg` subprocess.
- **FLAC**: Written using the `soundfile` library.
- **OGG**: Written using the `soundfile` library.

## Filename Template System

The exporter uses a template system to generate output filenames. Available tokens include:
- `{stem}`: The base name of the file (without extension).
- `{original}`: The original filename.
- `{suffix}`: Any processing suffix (e.g., `_processed`, `_vocals`).
- `{date}`: Current date (YYYYMMDD).
- `{format}`: The output format extension.
- `{sample_rate}`: The output sample rate.

### Example Templates
- `{stem}_processed.{format}` -> `audio_processed.wav`
- `{stem}_{suffix}.{format}` -> `audio_vocals.flac`
- `{date}_{original}.{format}` -> `20260725_audio.mp3`

## Filename Collision Resolution

If `overwrite` is set to `False` in `ExportOptions` and a file with the generated name already exists, the exporter will resolve the collision by appending an incrementing integer (e.g., `_1`, `_2`) to the filename until a unique name is found.

## Batch Export Coordination

During batch processing, the `ProcessorWorker` coordinates with the exporter for each file. The worker:
1. Processes the audio buffer.
2. Calls the exporter with the processed buffer and `ExportOptions`.
3. Reports progress back to the UI via Qt signals after each successful export.

## Code Example: Export Method

```python
import soundfile as sf
import numpy as np
from pathlib import Path
import subprocess

class AudioExporter:
    def export(self, audio_buffer: np.ndarray, options: ExportOptions, original_filename: str, suffix: str = "") -> Path:
        # 1. Output directory creation
        options.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 2. Filename generation and collision resolution
        base_name = options.filename_template.format(
            stem=Path(original_filename).stem,
            original=original_filename,
            suffix=suffix,
            date="20260725", # Use actual date formatting
            format=options.format,
            sample_rate=options.sample_rate or 44100
        )
        
        output_path = options.output_dir / base_name
        
        if not options.overwrite:
            counter = 1
            while output_path.exists():
                name_without_ext = output_path.stem
                if name_without_ext.endswith(f"_{counter - 1}"):
                    name_without_ext = name_without_ext.rsplit("_", 1)[0]
                new_name = f"{name_without_ext}_{counter}{output_path.suffix}"
                output_path = output_path.with_name(new_name)
                counter += 1
                
        # 3. Format-specific writing
        if options.format in ['wav', 'flac', 'ogg']:
            sf.write(output_path, audio_buffer, options.sample_rate or 44100, subtype=self._get_subtype(options))
        elif options.format == 'mp3':
            # Pseudo-code for ffmpeg subprocess
            self._write_mp3(audio_buffer, output_path, options)
            
        return output_path
```
