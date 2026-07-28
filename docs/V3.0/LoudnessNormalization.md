# Loudness Normalization

## Overview

The Loudness Normalization module in the Sound Processor project provides robust, AI-powered tools for preparing audio files for streaming, broadcast, and mastering workflows. The core purpose of this module is to normalize audio to strict streaming and broadcast standards before the final import into a Digital Audio Workstation (DAW) or before final delivery.

By conforming to industry standards like EBU R128 and ITU-R BS.1770-4, this tool ensures consistent perceived loudness across different tracks and prevents unexpected level changes for listeners.

## EBU R128 and LUFS Explained

Loudness normalization is not just about making audio louder; it is about perceived loudness. 

### K-Weighting Filter
The human ear is not equally sensitive to all frequencies. The K-weighting filter models this sensitivity by applying a high-pass filter and a high-shelf boost, emphasizing frequencies where human hearing is most sensitive (around 2-5 kHz) and attenuating low frequencies.

### Gated Measurement
To prevent quiet passages or silence from skewing the overall loudness measurement downwards, EBU R128 employs a gating mechanism.
- **Absolute Gate**: -70 LUFS. Any audio below this is ignored.
- **Relative Gate**: -10 LU relative to the ungated measurement. Only audio above this threshold contributes to the final Integrated Loudness.

### Integrated Loudness
This is the total perceived loudness of the entire track, measured in LUFS (Loudness Units relative to Full Scale). One LU is equivalent to one dB.

## Implementation Details

We use the `pyloudnorm` library, which provides a pure Python implementation of ITU-R BS.1770-4 loudness algorithms. This choice eliminates the need for compiled C-extensions in this specific module, ensuring high portability.

### The LoudnessReport Dataclass

Measurements are encapsulated in a `LoudnessReport` dataclass, making it easy to pass and inspect measurement results throughout the application.

```python
from dataclasses import dataclass

@dataclass
class LoudnessReport:
    """
    Encapsulates the results of a loudness measurement.
    """
    integrated_lufs: float
    true_peak_dbtp: float
    loudness_range_lu: float
    short_term_max: float
    momentary_max: float
    sample_peak: float
    
    def __str__(self) -> str:
        return (f"Integrated: {self.integrated_lufs:.1f} LUFS | "
                f"True Peak: {self.true_peak_dbtp:.1f} dBTP | "
                f"LRA: {self.loudness_range_lu:.1f} LU")
```

### API Signatures

The core functionality is exposed via two primary functions:

```python
import numpy as np
import pyloudnorm as pyln
from typing import Optional, Tuple

def measure_loudness(audio_data: np.ndarray, sample_rate: int) -> LoudnessReport:
    """
    Measures the loudness of the provided audio array according to ITU-R BS.1770-4.
    
    Args:
        audio_data: Numpy array of audio samples (shape: samples x channels)
        sample_rate: The sample rate of the audio data
        
    Returns:
        LoudnessReport containing all loudness metrics.
    """
    pass

def normalize_loudness(audio_data: np.ndarray, 
                       sample_rate: int,
                       target_lufs: float,
                       method: str = 'lufs',
                       max_true_peak: Optional[float] = -1.0) -> Tuple[np.ndarray, LoudnessReport]:
    """
    Normalizes the audio data to a specific target level.
    
    Args:
        audio_data: Input audio samples
        sample_rate: Audio sample rate
        target_lufs: Target level in LUFS (or dBFS for peak/RMS)
        method: Normalization method ('lufs', 'rms', 'peak')
        max_true_peak: Maximum true peak limit to prevent clipping
        
    Returns:
        Tuple containing the normalized audio array and the new measurement report.
    """
    pass
```

## Normalization Methods

The module supports three distinct normalization methods:

1. **LUFS (EBU R128)**: The modern standard. Adjusts the gain so the Integrated Loudness matches the target.
2. **RMS**: Adjusts the gain so the Root Mean Square level matches the target. Less accurate for perceived loudness but useful for certain legacy workflows.
3. **Peak**: Adjusts the gain so the highest sample matches the target.

### The Math Behind LUFS Normalization

The gain adjustment required to reach a target LUFS is calculated as:

```
delta_lufs = target_lufs - measured_lufs
gain_linear = 10 ** (delta_lufs / 20)
normalized_audio = audio * gain_linear
```

### True Peak Limiting

Applying linear gain can push inter-sample peaks above 0 dBFS, causing distortion when converted to analog or lossy formats (MP3, AAC).

After the initial gain stage, a lookahead True Peak limiter is applied to ensure that no peaks exceed the `max_true_peak` threshold (typically -1.0 dBTP for streaming).

## Presets Table

Different platforms have different loudness requirements. The UI provides quick presets:

| Preset / Platform | Target LUFS | Max True Peak (dBTP) | Notes |
| :--- | :--- | :--- | :--- |
| **Spotify** | -14.0 LUFS | -1.0 dBTP | Default for most music streaming |
| **YouTube** | -14.0 LUFS | -1.0 dBTP | Normalizes down, does not normalize up |
| **Apple Music** | -16.0 LUFS | -1.0 dBTP | Slightly more dynamic |
| **Tidal** | -14.0 LUFS | -1.0 dBTP | |
| **Broadcast (EBU)**| -23.0 LUFS | -1.0 dBTP | European TV/Radio standard |
| **Broadcast (ATSC)**| -24.0 LUFS | -2.0 dBTP | US TV standard (A/85) |
| **Podcast (Stereo)**| -16.0 LUFS | -1.5 dBTP | AES recommendation |
| **Podcast (Mono)** | -19.0 LUFS | -1.5 dBTP | AES recommendation |
| **CD Mastering** | -9.0 LUFS | -0.1 dBTP | Approximate "loudness war" level |

## Batch Mode Processing

The module supports processing entire folders of audio files simultaneously.

1. **Measurement Phase**: All files are analyzed, and a summary table is presented.
2. **Target Selection**: The user selects a target preset.
3. **Processing Phase**: Files are processed and exported.
4. **Reporting**: An `export_measurement_report.csv` is generated.

### Batch CSV Format

```csv
Filename,Original_LUFS,Target_LUFS,Gain_Applied_dB,Final_LUFS,Final_TruePeak
mix_v1.wav,-18.5,-14.0,4.5,-14.0,-0.8
vocal_stem.wav,-22.1,-14.0,8.1,-14.0,-1.0
bass_stem.wav,-12.0,-14.0,-2.0,-14.0,-4.5
```

## User Interface Flow

The normalization flow in the PyQt6 UI is designed to be informative and deliberate. The user should always see the *current* state before applying changes.

```text
+-------------------------------------------------------------+
|  Loudness Normalization                                     |
+-------------------------------------------------------------+
|  [ Drop File or Folder Here ]                               |
+-------------------------------------------------------------+
|                                                             |
|  Current Measurement:                                       |
|  +-------------------------------------------------------+  |
|  | File: track_01_mixdown.wav                            |  |
|  | Integrated: -18.2 LUFS     True Peak: -3.1 dBTP       |  |
|  | LRA:         4.5 LU        Short Term: -15.0 LUFS     |  |
|  +-------------------------------------------------------+  |
|                                                             |
|  Target Settings:                                           |
|  Preset: [ Spotify (-14 LUFS) v ]                           |
|                                                             |
|  Method: (o) LUFS   ( ) RMS   ( ) Peak                      |
|  Max True Peak: [ -1.0 ] dBTP                               |
|                                                             |
|  [ Analyze Only ]           [ NORMALIZE & EXPORT ]          |
+-------------------------------------------------------------+
```

## Advanced Considerations

- **Memory Management**: For very large files or huge batches, memory mapping (`numpy.memmap`) or chunked processing should be considered to avoid RAM exhaustion.
- **Multiprocessing**: Batch measurement should distribute file analysis across available CPU cores using `concurrent.futures`.

