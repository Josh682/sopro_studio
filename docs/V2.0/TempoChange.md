# Tempo Change — Sound Processor V2.0

## Purpose

Change the **playback speed / BPM** of audio without altering its pitch. The primary DAW preparation use case is matching a stem's tempo to the project BPM before import — e.g. a loop recorded at 140 BPM needs to be stretched to 128 BPM to lock with the project grid.

---

## Algorithm

Tempo change without pitch alteration uses **time-stretching** via the phase vocoder in `librosa`:

```
Input Audio
    │
    └── librosa.effects.time_stretch(rate=R)
            Stretches or compresses the time axis by factor R
            using STFT phase vocoder
            Pitch is NOT modified — only duration changes
```

```python
import librosa

def time_stretch(
    audio: np.ndarray,     # float32, shape (channels, samples)
    sample_rate: int,
    rate: float,           # > 1.0 = faster, < 1.0 = slower
) -> np.ndarray:
    """
    Change speed by `rate`. Pitch is preserved.
    rate = target_bpm / source_bpm
    """
    stretched_channels = []
    for ch in range(audio.shape[0]):
        stretched = librosa.effects.time_stretch(y=audio[ch], rate=rate)
        stretched_channels.append(stretched)
    return np.stack(stretched_channels)
```

---

## Rate ↔ BPM Math

$$\text{rate} = \frac{\text{target BPM}}{\text{source BPM}}$$

| Source BPM | Target BPM | Rate | Effect |
|------------|-----------|------|--------|
| 140 | 128 | 0.914× | Slow down (−8.6%) |
| 120 | 128 | 1.067× | Speed up (+6.7%) |
| 100 | 100 | 1.000× | No change |
| 128 | 64 | 0.500× | Half-time |
| 128 | 256 | 2.000× | Double-time |

---

## Two Input Modes

### BPM Mode

User provides source and target BPM; rate is auto-calculated:

```python
def bpm_to_rate(source_bpm: float, target_bpm: float) -> float:
    return target_bpm / source_bpm
```

When **Key Detection** has been run on the file in the same session, the detected BPM pre-fills the Source BPM field automatically.

### Percentage Mode

User provides a percentage change:

```python
def percentage_to_rate(percent_change: float) -> float:
    """e.g. +10% → rate=1.10, -15% → rate=0.85"""
    return 1.0 + (percent_change / 100.0)
```

Both modes control the same underlying `rate` parameter and stay in sync with each other.

---

## Preserve Pitch

Pitch preservation is **guaranteed by the algorithm**. Time-stretching via phase vocoder only modifies the time axis — no resampling occurs. The output will:

- Have a different duration ✅
- Have the same pitch ✅
- Have a different BPM ✅
- Sound identical in key ✅

---

## Core Module: `core/tempo_changer.py`

```python
@dataclass
class TempoChangeOptions:
    mode: str              # "bpm" | "percentage"
    source_bpm: float = 0.0     # required for BPM mode
    target_bpm: float = 0.0     # required for BPM mode
    percent_change: float = 0.0 # required for percentage mode

    @property
    def rate(self) -> float:
        if self.mode == "bpm":
            return self.target_bpm / self.source_bpm
        else:
            return 1.0 + (self.percent_change / 100.0)


class TempoChanger:
    def change_tempo(
        self,
        input_path: Path,
        output_dir: Path,
        options: TempoChangeOptions,
        on_progress: Callable[[float, str], None] | None = None,
    ) -> Path:
        """Load, time-stretch, export. Returns output path."""

    def change_tempo_audio(
        self,
        audio: np.ndarray,
        sample_rate: int,
        rate: float,
    ) -> np.ndarray:
        """Pure function — operates on in-memory audio array."""
```

---

## Combined Pass Optimisation with Pitch Shift

When **both** pitch shift and tempo change are applied in the same session, they are combined into a single processing pass to avoid double-encoding artifacts:

```python
# Combined: stretch then pitch-shift in one pass
def combined_pass(audio, sr, semitones: float, rate: float) -> np.ndarray:
    stretched = librosa.effects.time_stretch(y=audio, rate=rate)
    shifted   = librosa.effects.pitch_shift(y=stretched, sr=sr, n_steps=semitones)
    return shifted

# This is mathematically equivalent to:
# 1. Stretch by rate (changes speed + pitch)
# 2. Pitch-correct back by -semitones
# Result: only tempo changes, pitch stays at +semitones from original
```

The UI offers a **"Process Both"** button when both operations are configured.

---

## UI Layout: `gui/tempo_change_page.py`

```
┌──────────────────────────────────────────────────────────┐
│  Tempo Change                                            │
├──────────────────────────────────────────────────────────┤
│  [ Drop audio file or folder here ]                      │
├──────────────────────────────────────────────────────────┤
│  Mode:  ● BPM     ○ Percentage                           │
│                                                          │
│  ── BPM Mode ────────────────────────────────────────    │
│  Source BPM: [ 140 ]   (from Key Detection if available) │
│  Target BPM: [ 128 ]                                     │
│  Rate:        0.914×   (-8.6%)                           │
│                                                          │
│  ── Percentage Mode ─────────────────────────────────    │
│  Change:  [ -8.6 ] %                                     │
│  New BPM: 128.0  (from 140.0)                            │
├──────────────────────────────────────────────────────────┤
│  Output: [/outputs/]                         [Browse]    │
│  [Change Tempo]                               [Cancel]   │
├──────────────────────────────────────────────────────────┤
│  ████████████████████████ 100%  Done                     │
│  Log                                                     │
│  ✓ loop.wav → loop_128bpm.wav  (140→128 BPM, -8.6%)    │
└──────────────────────────────────────────────────────────┘
```

---

## Output Naming

```
input:  loop.wav
output: loop_128bpm.wav       (BPM mode)
        loop_-8.6pct.wav      (percentage mode)
```

---

## Batch Processing

Applies the same rate to all files in the queue. Each output is named individually with the BPM/percentage suffix.

Batch CSV export (optional):

```csv
filename,source_bpm,target_bpm,rate,output_file
loop1.wav,140,128,0.914,loop1_128bpm.wav
loop2.wav,140,128,0.914,loop2_128bpm.wav
```

---

## Quality Notes

| Rate Range | Quality | Notes |
|------------|---------|-------|
| 0.9× – 1.1× | Excellent | Transparent |
| 0.8× – 1.25× | Very Good | Minor smearing on transients |
| 0.7× – 1.5× | Good | Noticeable on percussive material |
| 0.5× – 2.0× | Acceptable | Audible artifacts; use with caution |
| Outside 0.5×–2.0× | Poor | Not recommended |

---

## Future Upgrade Path

Replace `librosa` phase vocoder with **Rubber Band Library** for significantly better quality at extreme ratios and on transient-rich audio:

```python
# Future: pip install pyrubberband
import pyrubberband as rb
stretched = rb.time_stretch(audio, sample_rate, rate)
```

The R3 engine in Rubber Band 3.x provides near-transparent stretching even at 0.5× and 2.0× rates.
