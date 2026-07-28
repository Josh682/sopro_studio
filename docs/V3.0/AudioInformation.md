# Audio Information Module

## Overview

The Audio Information module acts as the diagnostic front-end for the Sound Processor tool. Before any audio processing, normalization, or AI enhancement takes place, it is critical to understand the technical properties of the incoming audio file. 

This module provides a robust, fast, and highly detailed inspection of audio files, giving the user (and the application logic) a comprehensive breakdown of the file's encoding, format, and amplitude characteristics.

## Purpose and Use Cases

- **Stem Verification**: When preparing stems for DAW import, it's vital to ensure all stems share the same sample rate and bit depth to prevent drift or resampling artifacts.
- **Delivery Specification Checks**: Quickly verify if a master file meets specific delivery requirements (e.g., exactly 48kHz, 24-bit, -23 LUFS).
- **Processing Decisions**: The application uses this information to determine processing paths (e.g., skipping upsampling if the file is already at 96kHz).

## Displayed Properties

The module extracts and displays the following properties:

1. **Codec**: The underlying audio encoding (e.g., pcm_s24le, flac, aac).
2. **Sample Rate**: In Hz (e.g., 44100, 48000).
3. **Bit Depth**: The resolution of the audio (e.g., 16-bit, 24-bit, 32-bit float).
4. **Channels**: Mono (1), Stereo (2), or multichannel layouts.
5. **Duration**: Precise length in `HH:MM:SS.ms`.
6. **File Size**: In MB.
7. **Peak (dBFS)**: The highest absolute digital sample value.
8. **RMS (dBFS)**: The Root Mean Square of the signal, indicating average energy.
9. **LUFS (Integrated)**: The perceived loudness according to EBU R128.

## Implementation Details

The module relies on a hybrid approach for maximum speed and accuracy. Metadata is extracted via `ffprobe`, while amplitude analysis relies on `numpy` and `pyloudnorm`.

### Metadata Extraction (ffprobe)

We invoke `ffprobe` (part of the ffmpeg suite) to parse file headers without decoding the entire file. This is extremely fast.

```python
import subprocess
import json
from typing import Dict, Any

def get_ffprobe_metadata(filepath: str) -> Dict[str, Any]:
    """
    Extracts audio metadata using ffprobe.
    """
    cmd = [
        'ffprobe',
        '-v', 'quiet',
        '-print_format', 'json',
        '-show_streams',
        '-show_format',
        filepath
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    
    # Extract audio stream
    audio_streams = [s for s in data.get('streams', []) if s.get('codec_type') == 'audio']
    if not audio_streams:
        raise ValueError("No audio stream found.")
        
    return {
        'format': data.get('format', {}),
        'stream': audio_streams[0]
    }
```

### Amplitude Calculation (numpy)

Peak and RMS are calculated directly on the decoded `numpy` arrays.

```python
import numpy as np

def calculate_peak(audio_data: np.ndarray) -> float:
    """Calculates peak level in dBFS."""
    peak_linear = np.max(np.abs(audio_data))
    if peak_linear == 0:
        return -np.inf
    return 20 * np.log10(peak_linear)

def calculate_rms(audio_data: np.ndarray) -> float:
    """Calculates RMS level in dBFS."""
    rms_linear = np.sqrt(np.mean(audio_data**2))
    if rms_linear == 0:
        return -np.inf
    return 20 * np.log10(rms_linear)
```

### The AudioInfo Dataclass

All extracted data is stored in the `AudioInfo` dataclass, which extends the foundational `AudioEngine` types.

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class AudioInfo:
    """
    Comprehensive metadata and technical properties of an audio file.
    """
    filepath: str
    filename: str
    codec: str
    sample_rate: int
    bit_depth: Optional[int]
    channels: int
    duration_seconds: float
    file_size_bytes: int
    
    # Computed metrics (evaluated lazily or on demand)
    peak_dbfs: Optional[float] = None
    rms_dbfs: Optional[float] = None
    integrated_lufs: Optional[float] = None
    
    @property
    def duration_formatted(self) -> str:
        mins, secs = divmod(self.duration_seconds, 60)
        hours, mins = divmod(mins, 60)
        return f"{int(hours):02d}:{int(mins):02d}:{secs:.3f}"
        
    @property
    def file_size_mb(self) -> float:
        return self.file_size_bytes / (1024 * 1024)
```

## User Interface Layout

The UI presents this information in a clean, easily scannable "Card" layout when a single file is dropped.

### Info Card Panel (ASCII Art)

```text
+-------------------------------------------------------------+
| AUDIO INFORMATION                                        [X]|
+-------------------------------------------------------------+
| File: vocal_take_04_comp.wav                                |
| Path: /Users/mac/Audio/Project/Stems/                       |
+-------------------------------------------------------------+
| [FORMAT]                                                    |
| Codec:       PCM (pcm_s24le)                                |
| Sample Rate: 48,000 Hz                                      |
| Bit Depth:   24-bit integer                                 |
| Channels:    1 (Mono)                                       |
|                                                             |
| [TIMING & SIZE]                                             |
| Duration:    00:04:12.350                                   |
| File Size:   34.5 MB                                        |
|                                                             |
| [AMPLITUDE & LOUDNESS]                                      |
| Peak:       -1.2 dBFS    [||||||||||||||||||| ]             |
| RMS:        -18.4 dBFS   [|||||||||           ]             |
| LUFS:       -16.8 LUFS   [||||||||||          ]             |
|                                                             |
| [ Actions ] -> [ Send to Enhancer ]  [ Normalize Loudness ] |
+-------------------------------------------------------------+
```

## Batch Mode Operations

When a folder containing multiple audio files is dropped, the UI switches to a Table View.

1. **Folder Scan**: Recursively finds all supported audio files.
2. **Metadata Extraction**: Runs `ffprobe` concurrently on all files.
3. **Amplitude Analysis**: (Optional/Lazy) Computes peak/RMS/LUFS as the user scrolls or clicks "Analyze All".

### Batch Table Format

The table view allows sorting by any column (e.g., sorting by LUFS to find the quietest stem).

| Filename | SR (Hz) | Bit | Ch | Duration | Size | Peak (dB) | LUFS |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| kick.wav | 48000 | 24 | 1 | 04:12.350 | 12 MB | -0.1 | -12.4 |
| snare.wav| 48000 | 24 | 1 | 04:12.350 | 12 MB | -1.5 | -15.2 |
| synth.wav| 44100 | 16 | 2 | 04:12.350 | 42 MB | -6.0 | -20.1 |

*Note: In the example above, `synth.wav` is highlighted in red in the UI due to sample rate and bit depth mismatch.*

### CSV Export Structure

Users can export the batch information table for record-keeping or delivery manifests.

```csv
File,Path,Codec,SampleRate,BitDepth,Channels,DurationSec,SizeMB,Peak_dBFS,RMS_dBFS,LUFS
kick.wav,/path/to/stems,pcm_s24le,48000,24,1,252.35,12.5,-0.1,-15.4,-12.4
snare.wav,/path/to/stems,pcm_s24le,48000,24,1,252.35,12.5,-1.5,-20.1,-15.2
synth.wav,/path/to/stems,pcm_s16le,44100,16,2,252.35,42.0,-6.0,-24.5,-20.1
```

## Performance Considerations

- For large folders, running `ffprobe` in a multiprocessing pool significantly reduces load times.
- Decoding full files for amplitude analysis is CPU intensive. The UI should display a progress bar and perform this in a background QThread to keep the PyQt6 UI responsive.
