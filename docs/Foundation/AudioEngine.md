# Audio Engine

The Audio Engine manages decoding, encoding, and metadata extraction, serving as the foundational IO layer for the Sound Processor.

## Audio Loader (`audio/loader.py`)

The loader prefers `soundfile` for standard formats and uses a subprocess fallback to `ffmpeg` for unsupported formats (like MP4 audio). Resampling is handled via `librosa`.

```python
import soundfile as sf
import librosa
import numpy as np

def load_audio(path: str, target_sr: int = None, normalize: bool = False) -> tuple[np.ndarray, int]:
    """
    Primary decode with soundfile, FFmpeg fallback, librosa resampling.
    """
    try:
        audio, sr = sf.read(path, dtype='float32')
        # If stereo, transpose to (channels, samples)
        if audio.ndim > 1:
            audio = audio.T
        else:
            audio = np.expand_dims(audio, axis=0)
            
        if target_sr and target_sr != sr:
            audio = librosa.resample(audio, orig_sr=sr, target_sr=target_sr)
            sr = target_sr
            
        if normalize:
            audio = audio / np.max(np.abs(audio))
            
        return audio, sr
    except Exception:
        # FFmpeg fallback logic here
        pass
```

## Audio Writer (`audio/writer.py`)

Handles exporting audio data to disk.

```python
def save_wav(path: str, audio: np.ndarray, sr: int):
    # Ensure shape is (samples, channels) for soundfile
    if audio.ndim > 1:
        audio = audio.T
    sf.write(path, audio, sr)

def save_mp3(path: str, audio: np.ndarray, sr: int, bitrate: str = "320k"):
    # Uses subprocess calling ffmpeg
    pass
    
def save_flac(path: str, audio: np.ndarray, sr: int):
    # ensure shape is (samples, channels)
    if audio.ndim > 1:
        audio = audio.T
    sf.write(path, audio, sr, format='FLAC')

def save_ogg(path: str, audio: np.ndarray, sr: int):
    if audio.ndim > 1:
        audio = audio.T
    sf.write(path, audio, sr, format='OGG')
```

## Metadata Probing (`audio/metadata.py`)

Uses `ffprobe` to extract rich metadata.

```python
from dataclasses import dataclass
import subprocess
import json

@dataclass
class AudioInfo:
    path: str
    format: str
    duration: float
    sample_rate: int
    channels: int
    bit_depth: int
    bit_rate: int
    codec: str
    file_size: int

def probe_audio(path: str) -> AudioInfo:
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout)
    # Parse and return AudioInfo
    # ...
```

## Buffer Convention

Audio buffers are standard `numpy.ndarray` objects:
- **Type:** `float32`
- **Shape:** `(channels, samples)`
- **Range:** `[-1.0, 1.0]`

**Why this convention?** 
This layout precisely matches the expectations of modern machine learning and audio libraries like `torchaudio`, `librosa`, and GPU tensor layouts, minimizing the need for constant transpositions and type conversions.

## Supported Formats

| Format | Extension | Read | Write | Notes |
|---|---|---|---|---|
| Wave | `.wav` | Yes | Yes | Native via soundfile |
| MP3 | `.mp3` | Yes | Yes | Read via ffmpeg, Write via ffmpeg |
| FLAC | `.flac` | Yes | Yes | Native via soundfile |
| Ogg | `.ogg` | Yes | Yes | Native via soundfile |
| M4A/AAC | `.m4a` | Yes | No | Read via ffmpeg fallback |

## FFmpeg Integration

FFmpeg is essential for robust format support. The path resolution checks `shutil.which('ffmpeg')` first, followed by common macOS paths:

```python
import shutil
import os

def get_ffmpeg_path():
    path = shutil.which("ffmpeg")
    if path: return path
    for common_path in ["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"]:
        if os.path.exists(common_path):
            return common_path
    raise FileNotFoundError("FFmpeg not found")
```

Subprocess calls use `timeout` parameters to prevent hanging on corrupt files.

## Streaming Strategy

For large files, a chunked processing approach is used. However, because typical audio files (<500MB) comfortably fit in modern RAM, the default approach is full-file loading. When processing exceptionally large datasets or continuous streams, the framework falls back to generator-based chunking.

## Error Handling

The audio layer implements custom exceptions (e.g., `AudioLoadError`, `FFmpegMissingError`) to provide clear feedback to the upper layers and the UI, ensuring smooth graceful degradation (e.g. failing over to `ffmpeg` if `soundfile` can't parse a header).
