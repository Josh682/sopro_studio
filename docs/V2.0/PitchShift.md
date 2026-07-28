# Pitch Shift — Sound Processor V2.0

## Purpose

Transpose audio by a specified number of semitones **without changing its tempo**. The primary DAW preparation use case is matching a stem's key to the project key — e.g. a vocal recorded in A Minor needs to be shifted to C Major before import.

---

## Algorithm

Pitch shifting without tempo change is achieved via a **phase vocoder** implemented in `librosa`:

```
Input Audio
    │
    ├── Time-stretch by factor 2^(semitones/12) using STFT phase vocoder
    │       This changes pitch AND duration temporarily
    │
    └── Resample back to original length
            This restores the original duration, leaving only the pitch change
```

```python
import librosa

def pitch_shift(
    audio: np.ndarray,      # float32, shape (channels, samples)
    sample_rate: int,
    semitones: float,       # -12.0 to +12.0
) -> np.ndarray:
    """
    Shift pitch by `semitones`. Positive = up, negative = down.
    Supports fractional values (e.g. +0.5 = 50 cents sharp).
    Tempo is preserved exactly.
    """
    shifted_channels = []
    for ch in range(audio.shape[0]):
        shifted = librosa.effects.pitch_shift(
            y=audio[ch],
            sr=sample_rate,
            n_steps=semitones,
            bins_per_octave=12,
        )
        shifted_channels.append(shifted)
    return np.stack(shifted_channels)
```

Each channel is processed independently to avoid stereo phase cancellation artifacts.

---

## Parameters

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `semitones` | `float` | −12.0 to +12.0 | Semitones to shift. 12 = one octave. |

**Semitone reference:**

| Interval | Semitones |
|----------|----------|
| 1 octave up | +12 |
| Perfect 5th up | +7 |
| Major 3rd up | +4 |
| 1 semitone up | +1 |
| Unison | 0 |
| 1 semitone down | −1 |
| 1 octave down | −12 |

---

## Target Key Selection

The user can either:

1. **Manual semitone input** — type or slide to the desired shift
2. **Target Key Selection** — pick source key + target key, and the semitone count is calculated automatically

### Automatic Semitone Calculation

```python
CHROMATIC_SCALE = ["C", "C#", "D", "D#", "E", "F",
                    "F#", "G", "G#", "A", "A#", "B"]

def compute_semitones(
    source_key: str,   # e.g. "A"
    source_mode: str,  # "major" | "minor"
    target_key: str,   # e.g. "C"
    target_mode: str,  # "major" | "minor"
) -> int:
    """
    Compute the shortest semitone distance between two keys.
    Relative mode difference (major vs minor) = 3 semitones (minor is 3 below major).
    """
    src_idx = CHROMATIC_SCALE.index(source_key)
    tgt_idx = CHROMATIC_SCALE.index(target_key)

    mode_offset = 0
    if source_mode == "major" and target_mode == "minor":
        mode_offset = -3
    elif source_mode == "minor" and target_mode == "major":
        mode_offset = +3

    delta = (tgt_idx - src_idx + mode_offset) % 12
    if delta > 6:
        delta -= 12   # prefer shortest path (±6 semitones max)
    return delta
```

**Example:**
- Source: A Minor → Target: C Major
- A = index 9, C = index 0
- mode_offset = +3 (minor → major)
- delta = (0 − 9 + 3) % 12 = −6 % 12 = 6 → prefers −6 (shortest path down)
- Result: **−6 semitones** (A Minor → Eb Major, shortest) or use +6 for C Major

When the Key Detection result is available in the session, the source key/mode fields are pre-populated automatically.

---

## Tempo Preservation

Tempo is **guaranteed to be preserved**. The phase vocoder time-stretches then resamples, so the output has:
- The same duration (in seconds) as the input ✅
- A different pitch ✅
- The same BPM ✅

---

## Core Module: `core/pitch_shifter.py`

```python
class PitchShifter:
    def shift(
        self,
        input_path: Path,
        output_dir: Path,
        semitones: float,
        on_progress: Callable[[float, str], None] | None = None,
    ) -> Path:
        """Load, shift, export. Returns output path."""

    def shift_audio(
        self,
        audio: np.ndarray,
        sample_rate: int,
        semitones: float,
    ) -> np.ndarray:
        """Pure function — operates on in-memory audio array."""
```

---

## UI Layout: `gui/pitch_shift_page.py`

```
┌──────────────────────────────────────────────────────────┐
│  Pitch Shift                                             │
├──────────────────────────────────────────────────────────┤
│  [ Drop audio file or folder here ]                      │
├──────────────────────────────────────────────────────────┤
│  Mode: ● Manual Semitones   ○ Target Key                 │
│  ─────────────────────────────────────────────────────   │
│  [ -12 ────────────●──── +12 ]   +3 semitones            │
│                                                          │
│  ── Target Key Mode ──────────────────────────────────   │
│  Source Key: [ A ▾ ] [ Minor ▾ ]  (from Key Detection)  │
│  Target Key: [ C ▾ ] [ Major ▾ ]                        │
│  Computed:  -6 semitones                                 │
├──────────────────────────────────────────────────────────┤
│  Output: [/outputs/]                         [Browse]    │
│  [Shift Pitch]                                [Cancel]   │
├──────────────────────────────────────────────────────────┤
│  ██████████████████████ 100%  Done                       │
│  Log                                                     │
│  ✓ vocals.wav → vocals_+3st.wav                         │
└──────────────────────────────────────────────────────────┘
```

---

## Output Naming

```
input:  vocals.wav
output: vocals_+3st.wav      (manual mode)
        vocals_Cmin.wav      (target key mode)
```

---

## Quality by Shift Amount

| Shift Range | Quality | Notes |
|-------------|---------|-------|
| ±1–3 semitones | Excellent | Transparent on most material |
| ±4–6 semitones | Very Good | Slight formant shift on vocals |
| ±7–9 semitones | Good | Detectable processing on vocals |
| ±10–12 semitones | Acceptable | Robotic artifacts on sustained tones |

### Future Upgrade Path

Replace `librosa` phase vocoder with **Rubber Band Library** (`pyrubberband`) for:
- Higher quality at extreme semitone ranges
- Better formant preservation on vocals
- Faster processing via R3 engine

```python
# Future: pip install pyrubberband
import pyrubberband as rb
shifted = rb.pitch_shift(audio, sample_rate, semitones)
```

---

## Batch Processing

Applies the same semitone shift to all files in the queue. Each output is named individually with the shift suffix.
