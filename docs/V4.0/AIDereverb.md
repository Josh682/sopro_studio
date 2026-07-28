# AI Dereverb Documentation

## 1. Overview and Purpose
The AI Dereverb module is a critical audio preparation tool designed to remove unwanted room reverberation from recordings. In modern music production and audio post-production, a "dry" (reverb-free) signal is highly desirable. If an acoustic guitar or vocal is recorded in an untreated room, the natural reflections of that space are baked into the audio. This prevents the engineer from placing the sound in a new, controlled acoustic space using studio reverb plugins within their DAW. The AI Dereverb module aims to extract only the direct sound, stripping away the reverberant tail.

## 2. Understanding Reverberation
Reverberation consists of thousands of closely spaced echoes resulting from sound waves bouncing off walls, floors, and ceilings. It can be broken down into:
- **Direct Sound:** The sound traveling straight from the source to the microphone.
- **Early Reflections:** The first few bounces off nearby surfaces.
- **Late Reverberation (Tail):** The dense, decaying wash of sound.

Standard gating or expansion techniques often fail to remove reverb effectively because the reverb tail overlaps with the decay of the source material. AI models excel here by learning to separate the structural characteristics of the direct sound from the chaotic nature of the reverb.

## 3. Architecture and Model Backends
The Dereverb module integrates into the broader Enhancement architecture (similar to the Denoise module) and focuses on models specifically trained for this task.

### Planned Backends
1. **MDX-Net (Dereverb Variant):** The Music Demixing (MDX) architecture, while originally designed for stem separation, can be fine-tuned to separate "dry signal" from "reverb signal".
2. **BS-RoFormer (Dereverb Variant):** A Band-Split RoFormer model. Currently one of the most powerful architectures for audio source separation, offering unparalleled clarity when trained for dereverberation.

```python
from dataclasses import dataclass
import numpy as np

@dataclass
class DereverbOptions:
    """Configuration options for the dereverberation process."""
    amount: str = "moderate"  # 'subtle', 'moderate', 'aggressive'
    preserve_warmth: bool = True # Prevents the audio from sounding too thin

class DereverbModelBackend:
    """Implementation sketch for an AI Dereverb backend."""
    
    def __init__(self, model_path: str):
        self.model_path = model_path
        self._is_loaded = False
        
    def load(self):
        print(f"Loading dereverb model from {self.model_path} onto MPS...")
        # Torch load logic here
        self._is_loaded = True
        
    def apply_dereverb(self, audio: np.ndarray, options: DereverbOptions) -> np.ndarray:
        if not self._is_loaded:
            self.load()
            
        # Inference pipeline (pseudocode)
        # 1. Convert to STFT (Short-Time Fourier Transform)
        # 2. Pass magnitude spectrogram through the neural network
        # 3. Network outputs a mask for the direct signal
        # 4. Apply mask and inverse STFT to reconstruct time-domain audio
        
        print(f"Applying {options.amount} dereverberation...")
        processed_audio = audio # placeholder
        
        if options.preserve_warmth:
            # Blend some low-mid frequencies from the original to keep body
            pass
            
        return processed_audio
```

## 4. Use Cases
| Use Case | Description | Recommended Settings |
| :--- | :--- | :--- |
| **Bedroom Vocal Rescue** | Vocal recorded in an untreated bedroom with flutter echo. | Amount: Moderate. Preserve Warmth: On. |
| **Location Dialogue** | Film dialogue captured on a boom mic in a highly reflective space (e.g., a tiled kitchen). | Amount: Aggressive. Preserve Warmth: Off (intelligibility is key). |
| **Sample Preparation** | Using a drum loop that has too much "room" sound, preventing tight programming. | Amount: Subtle to Moderate. |

## 5. Limitations and Quality Expectations

| Limitation | Description | Workaround |
| :--- | :--- | :--- |
| **Information Loss** | If reverb is incredibly dense (e.g., recorded in a cathedral), the direct signal may be irreparably masked. | Cannot be fully fixed; use subtle settings to reduce tail without destroying transients. |
| **Artifacts** | Aggressive settings can cause a "gated" or "pumping" sound, or create phase issues. | Back off the amount slider; manually automate volume envelopes in DAW instead. |
| **Thinning** | Removing all room reflections often makes a sound feel unnatural or "thin". | Enable `preserve_warmth` or blend 10% of the original signal back in. |

## 6. Processing Pipeline (Pseudocode)
```python
def process_dereverb_pipeline(input_file: str, output_file: str, options: DereverbOptions):
    """Full pipeline from disk to disk."""
    import soundfile as sf
    import librosa
    
    # 1. Load Audio
    audio, sr = librosa.load(input_file, sr=None, mono=False)
    
    # 2. Initialize Model
    model = DereverbModelBackend(model_path="models/bs_roformer_dereverb.pt")
    
    # 3. Chunked Processing (to handle memory constraints)
    processed_audio = process_in_chunks(audio, sr, model, options)
    
    # 4. Export
    sf.write(output_file, processed_audio, sr)
```

## 7. User Interface
The UI provides visual feedback via a spectrogram comparison, allowing the user to see the reverb tail being eliminated in the frequency domain.

```text
+-------------------------------------------------------------+
|                     AI Dereverb Module                      |
+-------------------------------------------------------------+
|                                                             |
|  Dereverb Amount:                                           |
|  [ Subtle ]     [ Moderate ]     [ Aggressive ]             |
|                                                             |
|  [x] Preserve Warmth (retains low-mid body)                 |
|                                                             |
+-------------------------------------------------------------+
|  Spectrogram Preview:                                       |
|                                                             |
|  Original:                       Processed:                 |
|  ^ |||:.. .                      ^ |||                      |
|  | ||||::.. .                    | ||||                     |
|  | |||:::....                    | |||                      |
|  | ||::::...                     | ||                       |
|  +--------------> Time           +--------------> Time      |
|                                                             |
|  * Notice the smeared tails (dots) in the original.         |
|                                                             |
|  ( > ) Play Original   ( > ) Play Processed                 |
+-------------------------------------------------------------+
|                                                             |
|                   [ Apply and Export ]                      |
|                                                             |
+-------------------------------------------------------------+
```
