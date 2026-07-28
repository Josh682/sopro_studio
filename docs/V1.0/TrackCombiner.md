# Track Combiner — Sound Processor V1.0

## Purpose

Merge multiple audio files (stems, tracks, layers) into a single mixdown file. The primary use case is **re-combining processed stems** before re-importing them into a DAW, or creating a submix from selected stems without needing to open a DAW at all.

> **Example workflow:** Separate a song into 6 stems → apply AI denoise to the vocals stem → combine all 6 stems back into a clean stereo mix → import into DAW.

---

## Features

### Parallel Stem Merging
Mix N audio files into one by summing their waveforms sample-by-sample:
```
output[t] = stem1[t] + stem2[t] + stem3[t] + ... + stemN[t]
```
All stems are summed in float32 before any normalization or clipping prevention.

### Automatic Sample Rate Matching
Before mixing, all inputs are resampled to the **highest sample rate** found in the file set:
```python
target_sr = max(probe(f).sample_rate for f in input_files)
# All files with lower SR are upsampled via librosa.resample()
```

### Automatic Channel Matching
- Mono files are upmixed to stereo by duplicating the channel: `[L, L]`
- If inputs have mismatched channel counts, all are normalized to stereo before mixing

### Automatic Silence Padding
Shorter files are zero-padded to match the longest file's duration:
```python
max_samples = max(audio.shape[1] for audio in loaded)
padded = np.pad(audio, ((0, 0), (0, max_samples - audio.shape[1])))
```
This ensures all stems stay time-aligned even if they differ slightly in length.

### Clipping Prevention
After summing, the mix is checked for clipping. If `|peak| > 1.0`, peak normalization is applied:
```python
peak = np.max(np.abs(mixed))
if peak > 1.0:
    mixed = mixed / peak * 0.99   # headroom of 0.01
```
A warning is logged noting how much gain reduction was applied.

### Export
The final mix is written via the `ExportEngine` as WAV or FLAC with configurable bit depth.

---

## Core API: `core/combiner.py`

### `CombinerOptions` Dataclass

```python
@dataclass
class CombinerOptions:
    output_format: str = "wav"       # "wav" | "flac"
    bit_depth: int = 24              # 16 | 24 | 32
    output_filename: str = "mix"     # base name (without extension)
    gain_per_track: dict[str, float] = field(default_factory=dict)
                                     # {filename: linear_gain} e.g. {"vocals.wav": 0.8}
    prevent_clipping: bool = True
    normalize_output: bool = False   # full peak normalize to 0 dBFS
```

### `Combiner` Class

```python
class Combiner:
    def combine(
        self,
        input_paths: list[Path],
        output_dir: Path,
        options: CombinerOptions,
        on_progress: Callable[[float, str], None] | None = None,
    ) -> Path:
        """
        Pipeline:
        1. Probe all files → find target_sr and max_duration
        2. Load all files → resample to target_sr
        3. Upmix mono → stereo
        4. Pad to max_duration
        5. Apply per-track gain
        6. Sum all arrays
        7. Prevent clipping (if enabled)
        8. Export to output_dir
        9. Return output_path
        """
```

---

## Worker: `workers/combiner_worker.py`

```python
class CombinerWorker(BaseWorker):
    def run(self) -> None:
        combiner = Combiner()
        self.signals.log.emit(f"Combining {len(self._files)} tracks...")

        try:
            out = combiner.combine(
                self._files,
                self._output_dir,
                self._options,
                on_progress=lambda p, msg: self.signals.progress.emit(p, msg),
            )
            self.signals.log.emit(f"✓ Mix written: {out.name}")
            self.signals.finished.emit({"output": out})

        except Exception as e:
            self.signals.error.emit(str(e))
            self.signals.finished.emit(None)
```

---

## UI Layout: `gui/combiner_page.py`

```
┌──────────────────────────────────────────────────────────┐
│  Track Combiner                                          │
├──────────────────────────────────────────────────────────┤
│  [ Drop stems or tracks here ]                           │
├──────────────────────────────────────────────────────────┤
│  Track List                          Gain               │
│  ─────────────────────────────────────────────          │
│  ▲ ▼  vocals_song.wav               [──●────]  0.8×    │
│  ▲ ▼  drums_song.wav                [─────●──]  1.0×   │
│  ▲ ▼  bass_song.wav                 [─────●──]  1.0×   │
│  ▲ ▼  guitar_song.wav               [────●───]  0.9×   │
│  ▲ ▼  piano_song.wav                [─────●──]  1.0×   │
│  ▲ ▼  other_song.wav                [─────●──]  1.0×   │
│                               [+ Add Files]  [Clear]    │
├──────────────────────────────────────────────────────────┤
│  Output Filename: [ mix ]            Format: [ WAV ▾ ]  │
│  Bit Depth: [ 24-bit ▾ ]            ☑ Prevent Clipping  │
│  Output: [/outputs/]                          [Browse]  │
│  [Combine Tracks]                              [Cancel] │
├──────────────────────────────────────────────────────────┤
│  ████████████████░░░░ 80%                               │
│  Log                                                     │
│  ✓ Resampling drums_song.wav to 44100 Hz               │
│  ✓ Padding guitar_song.wav (+0.3s silence)             │
│  ✓ Peak reduced by 2.1 dB to prevent clipping          │
└──────────────────────────────────────────────────────────┘
```

---

## Use Case Examples

### 1. Re-combine Separated Stems
```
Separate song.wav → vocals.wav, drums.wav, bass.wav, guitar.wav, piano.wav, other.wav
Apply denoise to vocals.wav → vocals_clean.wav
Combine: vocals_clean.wav + drums.wav + bass.wav + guitar.wav + piano.wav + other.wav
→ song_clean_mix.wav  (ready for DAW import)
```

### 2. Create a Submix Stem
```
Select only: drums.wav + bass.wav
Combine → rhythm_section.wav  (a single rhythm stem for DAW)
```

### 3. Layer Multiple Takes
```
vocal_take1.wav + vocal_take2.wav + vocal_take3.wav
→ vocal_layered.wav  (blended doubles/triples)
```

---

## Error Handling

| Error | Handling |
|-------|----------|
| Empty file list | Disable Combine button; show placeholder message |
| Incompatible formats | Probe before mixing; auto-convert via AudioEngine |
| All-silence result | Warn user but still export |
| Disk full | Catch `OSError`; abort with message |
| Single corrupt file | Log error for that file; exclude from mix; continue |
