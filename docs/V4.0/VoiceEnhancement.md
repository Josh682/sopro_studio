# Voice Enhancement

## 1. Overview and Purpose
The **Voice Enhancement** module is an AI-powered audio processing utility designed to drastically improve speech and vocal clarity before importing audio into a Digital Audio Workstation (DAW). Unlike general EQ or dynamic processing tools found within a DAW, this feature leverages learned spectral enhancement to address common recording issues specific to the human voice. 

Whether processing dialogue for a podcast, a professional voiceover, or a lead vocal performance, this tool serves to reduce mud/boxiness and enhance presence (2–5kHz), ensuring the output is clear, intelligible, and mix-ready.

## 2. Core Sub-Features

### 2.1 Speech Clarity
Many non-ideal recording environments or entry-level microphones impart a "muddy" or "boxy" quality to vocals, typically concentrated in the lower mid-range (200Hz - 500Hz). 
- **Mud Reduction:** Dynamically identifies and suppresses these resonances without thinning out the fundamental frequency of the voice.
- **Presence Enhancement:** Gently enhances the critical 2–5kHz range where human hearing is most sensitive, lifting the vocal forward in the perceived soundstage.

### 2.2 Vocal Intelligibility
Speech intelligibility relies heavily on the clarity of consonants. 
- **Consonant Clarity:** Emphasizes transient information and specific high-frequency bands critical for understanding speech (e.g., 't', 'k', 'p' sounds).
- **Masking Reduction:** Attenuates frequencies that mask these critical bands.

### 2.3 De-essing
A built-in de-essing algorithm targets harsh sibilance ('s', 'sh' sounds) typically found in the 7–12kHz range. Unlike a standard broadband compressor, this dynamically reduces only the problematic frequencies when sibilance occurs, preserving the overall brightness of the vocal.

## 3. Algorithm & Approach

The core processing relies on a learned spectral enhancement approach. Using a fine-tuned speech enhancement model (implemented via PyTorch/torchaudio), the system analyzes the spectrogram of the input audio, predicts an ideal vocal target, and applies a dynamic spectral mask.

### Processing Chain Diagram
```text
[Raw Input Audio]
       |
       v
[STFT (Spectrogram Analysis)]  <-- (AI Denoise usually precedes this)
       |
       v
[DNN Speech Enhancement Model] ---> [De-Essing Filter (7-12kHz)]
       |                                      |
       v                                      v
[Spectral Mask Generation] <------------------+
       |
       v
[ISTFT (Waveform Synthesis)]
       |
       v
[Clean, Enhanced Output]
```

## 4. Configuration and Data Structures

### VoiceEnhancementOptions
The module is configured via the `VoiceEnhancementOptions` dataclass, allowing the engine to adapt to different source material types.

```python
from dataclasses import dataclass
from enum import Enum

class TargetUse(Enum):
    PODCAST = "podcast"
    VOICEOVER = "voiceover"
    VOCAL_PROD = "vocal"

@dataclass
class VoiceEnhancementOptions:
    """
    Configuration options for the Voice Enhancement module.
    """
    target_use: TargetUse = TargetUse.PODCAST
    clarity_strength: float = 0.5  # Range: 0.0 to 1.0
    de_ess_strength: float = 0.3   # Range: 0.0 to 1.0
    enhance_presence: bool = True
```

### Code Sketch: Spectral Enhancement

```python
import torch
import torchaudio
import numpy as np

class VoiceEnhancer:
    def __init__(self, model_path: str):
        # Load fine-tuned speech enhancement model, optimized for MPS
        self.device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
        self.model = torch.jit.load(model_path).to(self.device)
        self.model.eval()

    def process(self, audio_tensor: torch.Tensor, options: VoiceEnhancementOptions) -> torch.Tensor:
        """
        Applies learned spectral enhancement.
        """
        # 1. Convert to spectrogram
        stft = torchaudio.transforms.Spectrogram(n_fft=1024, hop_length=256).to(self.device)
        spec = stft(audio_tensor.to(self.device))
        
        # 2. Predict enhancement mask
        with torch.no_grad():
            mask = self.model(spec, options.target_use.value)
            
        # Apply clarity strength scaling
        scaled_mask = 1.0 + (mask - 1.0) * options.clarity_strength
        
        # 3. Apply mask
        enhanced_spec = spec * scaled_mask
        
        # 4. De-essing (simplified)
        if options.de_ess_strength > 0:
            enhanced_spec = self._apply_de_essing(enhanced_spec, options.de_ess_strength)
            
        # 5. Inverse STFT
        istft = torchaudio.transforms.InverseSpectrogram(n_fft=1024, hop_length=256).to(self.device)
        output_audio = istft(enhanced_spec)
        
        return output_audio.cpu()

    def _apply_de_essing(self, spec: torch.Tensor, strength: float) -> torch.Tensor:
        # Attenuate specific bins corresponding to 7-12kHz based on energy thresholds
        # Implementation details omitted for brevity
        return spec
```

## 5. Use-Case Presets

| Preset Name   | `target_use` | `clarity_strength` | `de_ess_strength` | Best For... |
|---------------|--------------|--------------------|-------------------|-------------|
| **Podcast**   | `PODCAST`    | 0.7                | 0.4               | General spoken word, internet radio. Maximizes intelligibility. |
| **Voiceover** | `VOICEOVER`  | 0.5                | 0.6               | Professional narration, audiobooks. Smooth, authoritative presence. |
| **Vocal**     | `VOCAL_PROD` | 0.8                | 0.5               | Sung vocals. Cuts through dense musical mixes. |
| **Custom**    | User Defined | User Defined       | User Defined      | Specific edge cases requiring manual tuning. |

## 6. User Interface Design

The UI is designed to be intuitive, allowing users to quickly select a preset and dial in the specific amount of processing required before exporting to their DAW.

```text
+-------------------------------------------------------------+
| [ Voice Enhancement ]                              [ ? ] [x]|
+-------------------------------------------------------------+
|                                                             |
| Target Use Case:                                            |
|  [Podcast]  [Voiceover]  [Musical Vocal]  [Custom]          |
|                                                             |
| Clarity Strength:                                           |
|  [=========|.......................] 30%                    |
|                                                             |
| De-essing (Sibilance Control):                              |
|  [=================|...............] 55%                    |
|                                                             |
| Options:                                                    |
|  [x] Enhance Presence (2-5kHz)                              |
|  [ ] Apply after AI Denoise                                 |
|                                                             |
| Output Preview:                                             |
|  > [ Play Before ]  > [ Play After ]                        |
|                                                             |
|                                        [ Apply & Render ]   |
+-------------------------------------------------------------+
```

## 7. Interaction with Other Modules
- **AI Denoise:** It is highly recommended to run AI Denoise *before* Voice Enhancement. Enhancing a noisy signal will also enhance the noise profile, particularly in the higher presence frequencies.
- **Declip:** Must be run before any spectral processing to ensure accurate frequency analysis.
