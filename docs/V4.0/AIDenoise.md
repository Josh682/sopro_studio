# AI Denoise Documentation

## 1. Overview and Purpose
The AI Denoise module is a core component of the Sound Processor toolkit, designed to prepare audio for Digital Audio Workstation (DAW) import. Rather than acting as a full DAW itself, this module focuses on a crucial pre-processing step: removing unwanted background noise from vocal or instrument recordings. Clean, noise-free audio is essential for effective mixing, as downstream processing like compression and EQ can drastically amplify background noise.

## 2. Targeted Noise Types
The denoiser addresses several common types of audio interference:
- **Hiss Removal:** Targets broad-spectrum, high-frequency tape or microphone preamp hiss.
- **Hum Removal (50/60Hz):** Eliminates low-frequency electrical hum caused by ground loops or unshielded cables, typically centered at 50Hz (Europe/Asia) or 60Hz (Americas) and their harmonics.
- **Fan Noise:** Specifically models and removes the drone of computer fans, air conditioning units, or similar steady-state mechanical noises.
- **General Background Noise:** Handles dynamic background sounds like distant traffic, room ambiance, or chatter.

## 3. Architecture and Model Backends
To achieve state-of-the-art results, the AI Denoise module employs a plugin architecture allowing interchangeable backends.

### Planned Backends:
1.  **Demucs (Noise Model):** A specialized variant of the Demucs architecture trained specifically for denoising rather than stem separation. Excellent for general background noise.
2.  **OpenAI Whisper-style Denoising:** Leveraging representations from robust speech recognition models to isolate clear speech from noisy backgrounds.
3.  **RNNoise:** A recurrent neural network-based approach, exceptionally fast and well-suited for real-time or low-latency applications, particularly effective on voice.
4.  **DSP Hum Filter:** A deterministic, non-AI approach for precise removal of 50/60Hz hum using notch filters.

### System Design
The system uses an abstract base class (`BaseEnhancementModel`) and a registry (`EnhancementManager`) to support lazy loading of heavy AI models (PyTorch) only when required. This keeps the application footprint light during startup.

```python
import abc
from dataclasses import dataclass
from typing import Optional
import numpy as np

@dataclass
class DenoiseOptions:
    """Configuration options for the denoising process."""
    strength: float = 1.0  # 0.0 to 1.0
    noise_type: str = "auto"  # 'auto', 'hiss', 'hum', 'fan', 'bg'
    preserve_high_freq: bool = True

class BaseEnhancementModel(abc.ABC):
    """Abstract base class for all enhancement/denoising models."""
    
    @abc.abstractmethod
    def load_model(self) -> None:
        """Loads the underlying model weights into memory."""
        pass

    @abc.abstractmethod
    def process(self, audio: np.ndarray, sample_rate: int, options: DenoiseOptions) -> np.ndarray:
        """Processes the audio and returns the denoised result."""
        pass
```

### The Enhancement Manager
```python
class EnhancementManager:
    """Manages available enhancement models and their lifecycles."""
    
    def __init__(self):
        self._registry = {}
        self._active_model: Optional[BaseEnhancementModel] = None
        
    def register(self, name: str, model_class: type):
        self._registry[name] = model_class
        
    def get_model(self, name: str) -> BaseEnhancementModel:
        if name not in self._registry:
            raise ValueError(f"Model {name} not found.")
        
        # Lazy loading
        if self._active_model is None or not isinstance(self._active_model, self._registry[name]):
            self._active_model = self._registry[name]()
            self._active_model.load_model()
            
        return self._active_model
```

## 4. Hum Removal (Deterministic DSP)
While AI is excellent for complex noise, electrical hum is best handled mathematically to avoid artifacts. This is achieved using a series of Infinite Impulse Response (IIR) notch filters at the fundamental frequency and its harmonics.

```python
import scipy.signal as signal

def apply_hum_notch(audio: np.ndarray, sr: int, freq: float = 60.0, harmonics: int = 5) -> np.ndarray:
    """Applies notch filters to remove electrical hum and its harmonics."""
    filtered_audio = audio.copy()
    q_factor = 30.0  # High Q for a narrow notch
    
    for i in range(1, harmonics + 1):
        target_f = freq * i
        if target_f >= sr / 2:
            break
            
        # Design notch filter
        b, a = signal.iirnotch(target_f, q_factor, sr)
        filtered_audio = signal.filtfilt(b, a, filtered_audio)
        
    return filtered_audio
```

## 5. Processing Strategy: Chunk-based Inference
Audio files can be large, and processing a 5-minute 96kHz file through a PyTorch model in one pass would exceed the memory limits of many GPUs. We employ a chunk-based processing strategy with crossfading to prevent clicks at chunk boundaries.

```python
def process_in_chunks(audio: np.ndarray, sr: int, model: BaseEnhancementModel, chunk_len_sec: float = 10.0, overlap_sec: float = 1.0) -> np.ndarray:
    """Processes long audio files in overlapping chunks."""
    chunk_size = int(chunk_len_sec * sr)
    overlap = int(overlap_sec * sr)
    step = chunk_size - overlap
    
    output = np.zeros_like(audio)
    window = np.hanning(overlap * 2) # Crossfade window
    
    for start in range(0, len(audio), step):
        end = min(start + chunk_size, len(audio))
        chunk = audio[start:end]
        
        # Pad if last chunk is too small
        if len(chunk) < chunk_size:
            chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
            
        processed_chunk = model.process(chunk)
        
        # Crossfade logic (simplified)
        if start == 0:
            output[start:end] = processed_chunk[:end-start]
        else:
            fade_in = window[:overlap]
            fade_out = window[overlap:]
            # Blend overlapping region
            # ... apply fades and add to output array ...
            
    return output
```

## 6. User Interface
The UI is designed for rapid iteration. Users can select the noise type, adjust the strength, and quickly A/B test the result before committing to the export.

```text
+-------------------------------------------------------------+
|                      AI Denoise Module                      |
+-------------------------------------------------------------+
|                                                             |
|  Target Noise Type:                                         |
|  [ Auto ] [ Hiss ] [ Hum (50/60Hz) ] [ Fan ] [ Background ] |
|                                                             |
|  Denoise Strength:                                          |
|  0.0 [====================|----------] 1.0     (0.72)       |
|                                                             |
|  [x] Preserve High Frequencies (prevents muffling)          |
|                                                             |
+-------------------------------------------------------------+
|                                                             |
|  Preview:                                                   |
|  ( > ) Play   ( || ) Pause                                  |
|                                                             |
|  [   Bypass (Compare Original)   ]                          |
|                                                             |
+-------------------------------------------------------------+
|                                                             |
|                   [ Apply and Export ]                      |
|                                                             |
+-------------------------------------------------------------+
```

## 7. Quality Expectations and Limitations
- **Artifacts:** Pushing the strength slider too high (e.g., > 0.9) on heavily degraded audio may result in "chirping" or underwater-sounding artifacts (musical noise).
- **High-Frequency Loss:** Aggressive denoising can sometimes attenuate the natural "air" or presence in a vocal. The `preserve_high_freq` option mitigates this by blending the high frequencies of the original signal back in, though this may allow some hiss to pass through.
- **Not a Replacement for Good Recording:** While the AI is powerful, it cannot reconstruct frequencies that were entirely masked by loud transient noises (e.g., dropping a book during a vocal take).
