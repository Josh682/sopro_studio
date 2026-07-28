# Declip

## 1. Overview and Purpose
The **Declip** module is an essential pre-processing audio repair utility designed to reconstruct audio waveforms that have suffered from digital clipping. 

Digital clipping occurs when the amplitude of a recording exceeds the maximum limit (0 dBFS, or ±1.0 in normalized floating-point representation). The waveform peaks are abruptly cut off, resulting in flat-topped waves. This introduces severe harmonic distortion, harsh artifacts, and a loss of original dynamics. 

Applying traditional DAW processing (like EQ, compression, or saturation) to clipped audio typically exacerbates these harsh artifacts. The Declip module restores the natural curvature of these peaks, allowing for clean, artifact-free processing downstream.

## 2. Detection Mechanism
Clipping detection operates by analyzing the waveform in the time domain. 

The algorithm scans for:
1. **Max Amplitude:** Samples reaching the absolute maximum value (typically ±1.0, though users can define a lower threshold if soft-clipping was applied).
2. **Consecutive Runs:** Flat-topped waves consist of multiple consecutive samples at this maximum value. The algorithm identifies the start and end indices of these clipping events.

## 3. Repair Algorithms
The module offers multiple repair algorithms depending on the severity of the clipping and the desired accuracy.

- **Cubic Spline Interpolation:** Ideal for light clipping. It replaces the clipped segment by calculating a smooth mathematical curve (spline) that matches the slope and curvature of the unclipped samples immediately preceding and following the clipped region.
- **Autoregressive (AR) Model Prediction:** Uses statistical modeling to predict the missing waveform data based on the spectral characteristics of the surrounding audio. Highly effective for moderate clipping.
- **DNN-Based Declipping (Optional/Advanced):** Utilizes a Deep Neural Network trained on large datasets of clean and synthetically clipped audio to reconstruct severely damaged waveforms.

## 4. Severity Classification

The module automatically assesses the severity of the clipping by calculating the percentage of clipped samples over a given window.

| Severity Level | Clipped Samples (%) | Recommended Algorithm | Expected Quality |
|----------------|---------------------|-----------------------|------------------|
| **Light**      | < 5%                | Cubic Spline          | Near Perfect     |
| **Moderate**   | 5% – 20%            | AR Model              | Good / Usable    |
| **Severe**     | > 20%               | DNN / AR Model        | **Quality Loss Unavoidable** (See Limitations) |

## 5. Limitations
**Important:** Severe clipping (>20%) involves massive data loss. While algorithms can guess the missing data to smooth out harsh distortion, the original acoustic information is gone. The repaired audio will sound smoother and less harsh, but it will not sound exactly as it would have if recorded properly. Users must be warned when extreme clipping is detected.

## 6. Configuration and Data Structures

### DeclipOptions

```python
from dataclasses import dataclass
from enum import Enum

class SeverityMode(Enum):
    AUTO = "auto"
    LIGHT = "light"
    MODERATE = "moderate"
    SEVERE = "severe"

class DeclipAlgorithm(Enum):
    SPLINE = "spline"
    AR_MODEL = "ar_model"
    DNN = "dnn"

@dataclass
class DeclipOptions:
    """
    Configuration options for the Declip module.
    """
    severity_mode: SeverityMode = SeverityMode.AUTO
    algorithm: DeclipAlgorithm = DeclipAlgorithm.SPLINE
    threshold: float = 0.99  # Normalized amplitude threshold for detection
    auto_makeup_gain: bool = True # Reduce overall gain after declipping to prevent re-clipping
```

### Code Sketch: Detection and Spline Interpolation

```python
import numpy as np
from scipy.interpolate import CubicSpline

def detect_clipping(audio: np.ndarray, threshold: float = 0.99):
    """
    Identifies regions of audio that exceed the clipping threshold.
    Returns a list of (start_idx, end_idx) tuples representing clipped regions.
    """
    is_clipped = np.abs(audio) >= threshold
    # Find transitions (0 to 1, or 1 to 0)
    transitions = np.diff(is_clipped.astype(int))
    
    starts = np.where(transitions == 1)[0] + 1
    ends = np.where(transitions == -1)[0] + 1
    
    # Handle edge cases (clipping at start or end of file)
    if is_clipped[0]: starts = np.insert(starts, 0, 0)
    if is_clipped[-1]: ends = np.append(ends, len(audio))
        
    return list(zip(starts, ends))

def repair_clipping_spline(audio: np.ndarray, threshold: float = 0.99, context_samples: int = 10):
    """
    Repairs clipped audio using cubic spline interpolation.
    """
    repaired_audio = audio.copy()
    clipped_regions = detect_clipping(audio, threshold)
    
    for start, end in clipped_regions:
        # Define the context region around the clipping
        ctx_start = max(0, start - context_samples)
        ctx_end = min(len(audio), end + context_samples)
        
        # Valid data points for interpolation
        valid_indices = np.concatenate([np.arange(ctx_start, start), np.arange(end, ctx_end)])
        valid_values = audio[valid_indices]
        
        if len(valid_indices) < 2:
            continue # Not enough context to interpolate
            
        # Create spline model
        cs = CubicSpline(valid_indices, valid_values)
        
        # Interpolate missing region
        missing_indices = np.arange(start, end)
        repaired_audio[missing_indices] = cs(missing_indices)
        
    return repaired_audio
```

## 7. Visualizing the Repair

```text
BEFORE (Clipped):
      ____
     /    \
    /      \
___/        \___

AFTER (Declipped - Reconstructed Peak):
        /\
       /  \
      /    \
     /      \
    /        \
___/          \___
```

## 8. User Interface Design

The UI provides visual feedback on the severity of the clipping and allows the user to preview the repair before committing.

```text
+-------------------------------------------------------------+
| [ Declip Repair ]                                  [ ? ] [x]|
+-------------------------------------------------------------+
|                                                             |
| Status: MODERATE CLIPPING DETECTED (12% of samples)         |
| [|||||||||||||||||....................................]     |
|                                                             |
| Algorithm:                                                  |
|  (o) Auto-Select (AR Model)                                 |
|  ( ) Cubic Spline (Light)                                   |
|  ( ) DNN AI Repair (Heavy)                                  |
|                                                             |
| Waveform Preview (Zoomed):                                  |
|                                       ___/--\___            |
|       BEFORE: ___/--\___       AFTER:                       |
|                                                             |
| Options:                                                    |
|  [x] Apply -3dB Makeup Gain to prevent re-clipping          |
|                                                             |
|  > [ Play Original ]  > [ Play Repaired ]                   |
|                                                             |
|                                        [ Apply & Render ]   |
+-------------------------------------------------------------+
```
