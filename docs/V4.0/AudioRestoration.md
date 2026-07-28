# Audio Restoration Module (V4.0)

## 1. Overview and Purpose

The Audio Restoration module is a premier, AI-powered feature set for the Sound Processor V4.0 suite. It is specifically designed to recover usable, high-quality audio from degraded, damaged, or legacy recordings. Unlike traditional audio editors that provide manual tools, this feature serves as an intelligent pre-processing step to repair the audio foundation prior to DAW import.

By addressing severe artifacts—such as digital dropouts, harmonic distortion from clipping, and vintage analog degradations—this module ensures that subsequent mixing, mastering, or editing processes operate on pristine source material.

---

## 2. Feature Deep Dive & Technical Depth

The restoration suite is divided into three primary sub-features, each targeting a specific class of audio degradation.

### 2.1. Distortion Repair
**Problem Definition:** Harmonic distortion occurs when an audio signal's amplitude exceeds the maximum limit of a recording system (clipping) or when analog equipment is overdriven. This results in "squared off" waveforms and the introduction of harsh, non-harmonic overtones.
**Restoration Approach:** The Distortion Repair module utilizes declipping algorithms paired with a deep neural network to reconstruct the clipped peaks of the waveform. By analyzing the surrounding unclipped audio, the model predicts the original trajectory of the waveform and synthesizes the missing upper harmonics smoothly, reducing the harshness associated with overdriven recordings.

### 2.2. Damaged Audio Recovery
**Problem Definition:** Damaged audio includes digital dropouts (brief moments of absolute silence or missing data caused by buffer underruns or transmission errors) and digital glitches (sudden, discontinuous jumps in the waveform caused by clocking errors or corrupted packets).
**Restoration Approach:** 
- **Digital Dropouts:** The module uses autoregressive models (like custom RNNs) to seamlessly inpaint missing audio segments. The network analyzes the spectral and temporal context immediately before and after the dropout to synthesize a bridge that is perceptually invisible.
- **Digital Glitches:** A specialized transient detection algorithm identifies unnatural discontinuities. Once isolated, these glitches are smoothed using localized crossfading and phase-aligned spectral interpolation.

### 2.3. Legacy Recording Restoration
**Problem Definition:** Archival and legacy media suffer from specific physical and magnetic degradations:
- **Vinyl Crackle & Clicks:** Brief, high-amplitude broadband noise spikes caused by dust or scratches on vinyl records.
- **Tape Hiss:** A constant, high-frequency broadband noise floor inherent to magnetic tape formulations.
- **Wow & Flutter:** Pitch and time-base fluctuations caused by mechanical irregularities in tape transports or turntables. "Wow" refers to slow variations (under 4 Hz), while "Flutter" refers to fast variations.
**Restoration Approach:** 
- **Crackle/Clicks:** De-clicking involves a two-stage process: detection using high-frequency transient isolation, followed by autoregressive interpolation to fill the gap.
- **Hiss:** Employs a multi-band spectral subtraction method informed by a noise profile, enhanced by an AI model that differentiates between broadband noise and high-frequency musical content.
- **Wow & Flutter:** Utilizes a phase-locked loop (PLL) tracking system to identify the frequency modulation carrier (often a constant bias tone or stable harmonic) and applies an inverse time-warping function to stabilize the pitch.

---

## 3. Data Structures and Options

The module is driven by a highly configurable set of parameters that allow the user (or the AI inference engine) to tailor the processing to the specific recording medium.

```python
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List

class DegradationType(Enum):
    CLIPPING = "clipping"
    DROPOUT = "dropout"
    VINYL_CRACKLE = "vinyl_crackle"
    TAPE_HISS = "tape_hiss"
    WOW_AND_FLUTTER = "wow_and_flutter"
    DIGITAL_GLITCH = "digital_glitch"

class RecordingType(Enum):
    DIGITAL = "digital"
    TAPE = "tape"
    VINYL = "vinyl"
    BROADCAST = "broadcast"
    CUSTOM = "custom"

@dataclass
class RestorationOptions:
    """
    Configuration options for the Audio Restoration pipeline.
    """
    recording_type: RecordingType = RecordingType.DIGITAL
    
    # Global strength of the restoration effect (0.0 to 1.0)
    restoration_strength: float = 0.5 
    
    # Specific artifacts to target. If empty, the system analyzes and auto-selects.
    target_artifacts: List[DegradationType] = field(default_factory=list)
    
    # If True, protects sharp transients from being smoothed over during de-clicking
    preserve_transients: bool = True
    
    # Resolution enhancement level (1-5) using super-resolution models
    ai_enhancement_level: int = 3 
```

---

## 4. Processing Pipeline

The restoration pipeline follows a strict sequential order to prevent one restoration process from interfering with another.

### 4.1. Pipeline Diagram (ASCII)

```text
[ Input Audio ]
      |
      v
+-----------------------+
|  1. Analysis Phase    | ---> Detects clipping, dropouts, noise profiles
+-----------------------+
      |
      v
+-----------------------+
|  2. De-glitch / De-   | ---> Fixes discontinuities and digital errors
|     click Phase       |      (Must be done first to prevent smearing)
+-----------------------+
      |
      v
+-----------------------+
|  3. De-clipping       | ---> Reconstructs clipped peaks
+-----------------------+
      |
      v
+-----------------------+
|  4. Wow & Flutter     | ---> Pitch stabilization
|     Correction        |
+-----------------------+
      |
      v
+-----------------------+
|  5. Tape Hiss Removal | ---> Broadband spectral denoising
+-----------------------+
      |
      v
[ Cleaned Audio ]
```

### 4.2. Pipeline Pseudocode

```python
class AudioRestorationPipeline:
    def __init__(self, options: RestorationOptions):
        self.options = options
        self.models = self._load_models(options)

    def process(self, audio_data: np.ndarray, sr: int) -> np.ndarray:
        # Step 1: Analyze
        detected_artifacts = self._analyze_audio(audio_data, sr)
        
        active_artifacts = self.options.target_artifacts or detected_artifacts

        # Step 2: De-glitch / De-click
        if DegradationType.DIGITAL_GLITCH in active_artifacts or DegradationType.VINYL_CRACKLE in active_artifacts:
            audio_data = self._apply_declick(audio_data, self.options.restoration_strength)

        # Step 3: De-clip
        if DegradationType.CLIPPING in active_artifacts:
            audio_data = self._apply_declip(audio_data, self.options.restoration_strength)

        # Step 4: Pitch Stabilization
        if DegradationType.WOW_AND_FLUTTER in active_artifacts:
            audio_data = self._apply_wow_flutter_correction(audio_data)

        # Step 5: Hiss / Noise reduction
        if DegradationType.TAPE_HISS in active_artifacts:
            audio_data = self._apply_dehiss(audio_data, self.options.restoration_strength)

        # Step 6: Dropout Inpainting
        if DegradationType.DROPOUT in active_artifacts:
            audio_data = self._inpaint_dropouts(audio_data)

        return audio_data
```

---

## 5. Model Backends & Technology Stack

The restoration module utilizes a hybrid approach, combining traditional DSP with state-of-the-art PyTorch models optimized for Apple Silicon (MPS).

- **AudioSR (Audio Super Resolution):** Employed for upsampling and restoring lost high-frequency content in highly degraded or band-limited recordings (e.g., archival AM radio broadcasts).
- **Custom Autoregressive RNN:** Used specifically for digital dropout inpainting. It models the time-series nature of audio to predict missing samples based on past and future context.
- **U-Net Architecture:** Used for broadband noise and tape hiss reduction. It operates on the spectrogram of the audio, masking noise while preserving harmonic content.
- **DSP Phase-Locked Loop (PLL):** For Wow & Flutter correction, traditional DSP is preferred over AI to maintain bit-accurate phase relationships.

---

## 6. Relationship to Other V4.0 Features

Audio Restoration is the **first** line of defense. It operates before Denoise, Dereverb, and Source Separation. Attempting to separate sources on audio with digital dropouts or severe clipping will result in catastrophic artifacts in the separated stems.

### 6.1. V4.0 Feature Ordering (ASCII Diagram)

```text
+-------------------------+
| RAW INPUT AUDIO         |
+-------------------------+
            |
            v
=======================================
| STAGE 1: AUDIO RESTORATION          |  <--- (This Module)
| - De-clip, De-click, Inpaint, Fix   |
=======================================
            |
            v
=======================================
| STAGE 2: DENOISE & DEREVERB         |
| - Remove background room noise      |
| - Suppress room reflections         |
=======================================
            |
            v
=======================================
| STAGE 3: SOURCE SEPARATION          |
| - Stem extraction (Vocals, Drums)   |
=======================================
            |
            v
+-------------------------+
| EXPORT FOR DAW IMPORT   |
+-------------------------+
```

---

## 7. Use Cases

| Use Case | Input Material | Key Restoration Features Used | Benefit |
| :--- | :--- | :--- | :--- |
| **Archival Digitization** | 1960s magnetic tape recording | Tape Hiss removal, Wow & Flutter correction | Rescues historically significant recordings for modern distribution. |
| **Podcast Remastering** | Zoom call with network issues | Digital Glitch repair, Dropout inpainting | Fixes missing words and popping artifacts caused by poor internet connections. |
| **Vintage Sample Prep** | Vinyl record sampled for Hip-Hop | Vinyl Crackle reduction, De-clipping | Provides a clean, punchy sample that won't clash with modern 808s and synths. |
| **Location Sound** | Overdriven lavalier mic | Distortion Repair (De-clip) | Saves a take where the actor yelled unexpectedly and clipped the preamp. |

---

## 8. User Interface (UI) Layout

The UI is built using PyQt6, designed to be intuitive while offering deep control for advanced users.

```text
+-------------------------------------------------------------+
|  AUDIO RESTORATION MODULE                            [ ? ]  |
+-------------------------------------------------------------+
|                                                             |
|  [ PRESETS ]                                                |
|  Recording Type: [ Digital (Default) |v]                    |
|                                                             |
|  [ GLOBAL CONTROLS ]                                        |
|  Restoration Strength:                                      |
|  MIN [========|===============] MAX   ( 35% )               |
|                                                             |
|  [ TARGET ARTIFACTS ] (Auto-detected: 2)                    |
|  [x] Digital Dropouts (Inpainting)                          |
|  [ ] Vinyl Crackle (De-click)                               |
|  [x] Harmonic Distortion (De-clip)                          |
|  [ ] Tape Hiss (Broadband Denoise)                          |
|  [ ] Wow & Flutter (Pitch Stabilize)                        |
|                                                             |
|  [ ADVANCED ]                                               |
|  [x] Preserve Transients                                    |
|  AI Enhancement Level: ( 3 ) [-] [+]                        |
|                                                             |
|  +-------------------------------------------------------+  |
|  | VISUALIZER (Spectrogram / Waveform view)              |  |
|  |                                                       |  |
|  |    |||||      ||||||||      |||       |||||           |  |
|  |   |||||||    ||||||||||    |||||     |||||||          |  |
|  |    |||||      ||||||||      |||       |||||           |  |
|  +-------------------------------------------------------+  |
|                                                             |
|                      [ ANALYZE ]    [ APPLY RESTORATION ]   |
+-------------------------------------------------------------+
```

---

## 9. Limitations and Edge Cases

- **Severe Clipping:** While the model can reconstruct mildly to moderately clipped peaks, audio that is fundamentally "square-waved" for extended periods (e.g., heavily distorted guitar) cannot be fully reconstructed as the original phase information is permanently lost.
- **Inpainting Length:** The dropout inpainting model is highly effective for gaps up to 50 milliseconds. For dropouts exceeding 150 milliseconds, the model may hallucinate unnatural artifacts or repeat previous phonemes in human speech.
- **Compute Intensity:** AudioSR and Wow & Flutter correction are highly compute-intensive. On Apple Silicon (M1/M2/M3), these processes are accelerated via MPS, but may still process at slower-than-realtime speeds depending on the requested resolution enhancement.
- **Musical Wow & Flutter:** The Wow & Flutter algorithm can occasionally misinterpret intentional musical vibrato (e.g., on a violin or synthesizer) as tape flutter. In these scenarios, the feature should be bypassed or the restoration strength heavily reduced.

---

## 10. Implementation Considerations for PyQt6 & Python 3.14

- **Asynchronous Processing:** Given the heavy AI workloads utilizing `torch` and `torchaudio`, all restoration tasks must be offloaded to a background `QThread`. The main UI thread must remain responsive.
- **Memory Management:** AI models (especially U-Net and AudioSR) consume significant VRAM. Implement chunked processing (e.g., 10-second overlapping windows) using `numpy` and `librosa` to prevent memory exhaustion on machines with limited unified memory.
- **File Handling:** Utilize `soundfile` and `ffmpeg` for robust reading/writing of varied audio formats, ensuring 32-bit float internal processing to prevent quantization noise during the multi-stage pipeline.
