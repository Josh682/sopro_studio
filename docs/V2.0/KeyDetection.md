# Key Detection — Sound Processor V2.0

## Purpose

Automatically detect the **musical key** (tonic + mode) and **BPM** of any audio file. This is a pre-processing analysis step for DAW session preparation — knowing the key of a stem before importing it into a DAW ensures it is in the right key for the project, and informs the Pitch Shift tool about the correct transposition amount.

---

## Algorithm

### Key Detection — Krumhansl-Schmuckler

```
Input Audio (mono mix)
    │
    ├── librosa.feature.chroma_cqt()   ← Constant-Q chromagram, 12 pitch bins
    │       CQT captures harmonic content more accurately than STFT chroma
    │
    ├── chroma.mean(axis=1)            ← Average pitch class energy over time
    │       Result: 12-element vector (C, C#, D, D#, E, F, F#, G, G#, A, A#, B)
    │
    ├── Correlate against 24 key profiles
    │       12 major keys × Krumhansl major profile
    │       12 minor keys × Krumhansl minor profile
    │
    └── Best correlation → key result
```

```python
import librosa
import numpy as np

# Key profile vectors (Krumhansl-Schmuckler, 1990)
MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09,
                           2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53,
                           2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

def detect_key(audio_mono: np.ndarray, sample_rate: int) -> "KeyResult":
    chroma = librosa.feature.chroma_cqt(y=audio_mono, sr=sample_rate)
    profile = chroma.mean(axis=1)

    major_scores = [np.corrcoef(np.roll(MAJOR_PROFILE, i), profile)[0, 1] for i in range(12)]
    minor_scores = [np.corrcoef(np.roll(MINOR_PROFILE, i), profile)[0, 1] for i in range(12)]

    best_major = int(np.argmax(major_scores))
    best_minor = int(np.argmax(minor_scores))

    if major_scores[best_major] >= minor_scores[best_minor]:
        tonic, mode, confidence = NOTES[best_major], "major", major_scores[best_major]
    else:
        tonic, mode, confidence = NOTES[best_minor], "minor", minor_scores[best_minor]

    return KeyResult(tonic=tonic, mode=mode, confidence=float(confidence))
```

### BPM Estimation

```python
def estimate_bpm(audio_mono: np.ndarray, sample_rate: int) -> float:
    tempo, _ = librosa.beat.beat_track(y=audio_mono, sr=sample_rate)
    return round(float(tempo), 1)
```

Both are computed together in a single `analyze()` call to avoid loading audio twice.

---

## Data Models: `core/music_analyzer.py`

### `KeyResult`

```python
@dataclass
class KeyResult:
    tonic:      str          # e.g. "A", "C#", "Bb"
    mode:       str          # "major" or "minor"
    confidence: float        # Pearson correlation, ~0.5–1.0

    @property
    def display(self) -> str:
        return f"{self.tonic} {self.mode.capitalize()}"   # "A Minor"

    @property
    def is_reliable(self) -> bool:
        return self.confidence >= 0.75
```

### `TempoResult`

```python
@dataclass
class TempoResult:
    bpm:         float    # e.g. 128.4
    beat_frames: np.ndarray  # beat positions in frames
```

### `MusicAnalyzer`

```python
class MusicAnalyzer:
    def analyze(
        self,
        input_path: Path,
        on_progress: Callable[[float, str], None] | None = None,
    ) -> tuple[KeyResult, TempoResult]:
        """Load audio, run key + BPM detection, return both results."""
```

---

## Major / Minor Detection

The algorithm tests all 24 keys (12 major + 12 minor) and selects the highest-correlating match. The `mode` field is always either `"major"` or `"minor"` — relative keys (e.g. C Major vs A Minor) will be resolved to whichever has the higher correlation score for the given audio.

---

## Confidence Score

The confidence is a **Pearson correlation coefficient** between the audio's pitch class profile and the winning key's theoretical profile.

| Confidence | Interpretation |
|------------|---------------|
| 0.90–1.00 | Very reliable |
| 0.75–0.89 | Reliable |
| 0.60–0.74 | Uncertain — audio may be atonal or modulating |
| < 0.60 | Unreliable — do not use for automatic pitch shift |

When `confidence < 0.75`, the UI shows a warning: *"Low confidence — verify key manually."*

---

## Batch Detection

The Batch Key Detection mode processes an entire folder and exports a CSV report:

```csv
filename,key,mode,confidence,bpm
vocals_song1.wav,A,minor,0.91,128.4
drums_song1.wav,N/A,N/A,0.42,128.3
bass_song1.wav,A,minor,0.88,128.4
```

Percussive files (like drums) often return low confidence — this is expected and noted in the report.

---

## UI Layout: `gui/key_detection_page.py`

```
┌─────────────────────────────────────────────────────┐
│  Key Detection                                      │
├─────────────────────────────────────────────────────┤
│  [ Drop audio file or folder here ]                 │
├─────────────────────────────────────────────────────┤
│  Results                                            │
│  ┌──────────────────────────────────────────────┐  │
│  │  🎵  Key:  A Minor           BPM:  128.4     │  │
│  │  Confidence: ████████████░░  91%             │  │
│  │  ⚠ Reliable — safe to use for pitch shift    │  │
│  └──────────────────────────────────────────────┘  │
│  [→ Send to Pitch Shift]                            │
├─────────────────────────────────────────────────────┤
│  Batch Mode — Results Table                         │
│  File              Key      BPM   Confidence        │
│  vocals.wav        A min   128.4   91%              │
│  bass.wav          A min   128.3   88%              │
│  drums.wav         —       128.4   42% ⚠            │
│  [Export CSV]                                       │
└─────────────────────────────────────────────────────┘
```

---

## Accuracy Notes & Limitations

- Accuracy on pop/rock/electronic music: ~75–85%
- Minimum recommended duration: **30 seconds** (shorter clips reduce accuracy)
- Purely percussive audio (drums, loops): confidence will be low — expected behaviour
- Tracks with key changes: reports the **dominant key** only; no section segmentation
- Chromatic/atonal music: unreliable by design
- Future improvement: replace with a neural key detector (e.g. Essentia's KeyExtractor or KeyFinder)
