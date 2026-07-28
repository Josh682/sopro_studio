# Sound Processor v1.0

A cross-platform desktop application for audio format conversion and AI-powered instrument separation.

---

## Features

- **Audio Converter** — Cross-convert between MP3, WAV, and FLAC with format-specific settings (sample rate, bit depth, bitrate, compression)
- **AI Separator** — Stem separation powered by **BS-RoFormer** (6-stem) and **MelBand-RoFormer** (vocals + instrumental), with a dynamic UI that adapts to any registered model
- **Batch Processing** — Drag-and-drop, single file, folder, and batch modes
- **Dark Theme** — Modern PyQt6 interface with Catppuccin Mocha color palette and sidebar navigation

---

## Requirements

- Python 3.10+
- [FFmpeg](https://ffmpeg.org/) (system dependency, path configurable in Settings)

### FFmpeg Installation

| Platform | Command |
| -------- | ------- |
| macOS    | `brew install ffmpeg` |
| Windows  | Download from [ffmpeg.org](https://ffmpeg.org/download.html) or `winget install ffmpeg` |
| Linux    | `sudo apt install ffmpeg` (Debian/Ubuntu) |

---

## Installation

```bash
git clone <repo-url> sound-processor
cd sound-processor

# Create and activate virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

# Install Python dependencies
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

> **Note:** If `melband-roformer-infer` is unavailable on PyPI, install it directly from its GitHub repository.

---

## Running the App

```bash
python main.py
```

The window opens to the **Home** dashboard. Use the left sidebar to navigate between pages.

---

## User Interface Overview

```
┌─────────────────────────────────────────────────────────┐
│  Sound Processor                                        │
│ ┌──────────┐  ┌────────────────────────────────────┐   │
│ │ 🏠 Home  │  │                                    │   │
│ │ 🔄 Conv. │  │         Page Content Area          │   │
│ │ 🧠 Sep.  │  │                                    │   │
│ │ ⚙️ Sett. │  │                                    │   │
│ └──────────┘  └────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

| Sidebar Button | Page | Purpose |
|---|---|---|
| 🏠 Home | Dashboard | Quick stats and app overview |
| 🔄 Converter | Converter Page | Batch audio format conversion |
| 🧠 Separator | Separator Page | AI-powered stem separation |
| ⚙️ Settings | Settings Page | Paths, FFmpeg, and preferences |

---

## First-Time Setup

Before using the app's core features, configure your preferences in **Settings** (⚙️ in the sidebar):

1. **Output Folder** — Where converted files and separated stems will be saved.  
   Default: `<project-root>/outputs/`

2. **FFmpeg Path** — Full path to the `ffmpeg` executable.  
   Leave blank to use system PATH (e.g., if installed via `brew install ffmpeg`).

3. **AI Models Folder** — Directory where AI model weight files are stored.  
   Default: `<project-root>/models/`  
   Model weights are **downloaded automatically** on first use.

4. **Chunk Size** — Audio chunk size (in samples) used during AI inference.  
   Default: `352800` (~8 seconds at 44.1 kHz). Reduce if you hit out-of-memory errors.

Click **Save Settings** after making changes.

---

## How to Use: Audio Converter (🔄)

The Converter page converts one or many audio files between **WAV**, **MP3**, and **FLAC** formats.

### Step-by-Step

**1. Add files**

- **Drag and drop** audio files or a whole folder onto the drop zone.
- Or click the drop zone to open a file browser.
- Added files appear in the **Selected Files** list below the drop zone.
- To clear the list, click **Clear Selection**.

**2. Choose target format**

Select the output format from the **Target Format** dropdown (WAV / MP3 / FLAC).  
The settings panel below updates automatically:

| Format | Available Settings |
|---|---|
| **WAV** | Bit depth: 8-bit, 16-bit, 24-bit, 32-bit float |
| **MP3** | Bitrate: 128 / 192 / 256 / 320 kbps |
| **FLAC** | Compression level: 0 (fastest) → 8 (smallest) |

**3. Optional: Peak Normalise**

Check **Peak Normalise Audio** to normalize each file's loudness to 0 dBFS before encoding.

**4. Choose output folder**

The default destination is from Settings. Click **Change Folder** to pick a different directory for this batch.

**5. Start conversion**

Click **Start Conversion**.  
- A progress bar and ETA appear in the **Progress** panel.
- Live status messages appear in the **Log** panel below.
- Each file is processed independently — an error on one file does not abort the rest.

**6. Cancel (optional)**

Click **Cancel** at any time. The current file finishes cleanly, then processing stops.

### Notes
- Output files are **collision-safe**: if `song.wav` already exists in the output folder, the app creates `song_1.wav`, `song_2.wav`, etc.
- Supported input formats: `.wav`, `.mp3`, `.flac`, `.ogg`, `.m4a`

---

## How to Use: AI Stem Separator (🧠)

The Separator page uses a deep-learning model to split an audio track into individual stems (e.g., vocals and instrumental).

### Step-by-Step

**1. Select a model**

Choose from the **AI Model** dropdown at the top.  
The model's description and expected output stems (e.g., `vocals`, `drums`, etc.) update automatically below.

> **Available Models:**
> - **BS-RoFormer (6 Stems):** Separates into `vocals`, `drums`, `bass`, `guitar`, `piano`, and `other`. Best for full music tracks.
> - **MelBand-RoFormer Kim Vocal:** Produces two stems: `vocals` and `instrumental`.

**2. Load an audio file**

- **Drag and drop** a single audio file onto the drop zone.
- Or click the drop zone to browse for a file.
- The **File Details** panel on the right shows format, sample rate, channels, and duration after loading.

**3. Choose output folder**

The default destination is from Settings. Click **Change Folder** to override for this session.

**4. Run separation**

Click **Separate Stems**.

What happens next:
1. **Model Loading** — On first run, weights are downloaded to your models directory. This can take a few minutes depending on your internet connection. Subsequent runs use the cached weights instantly.
2. **Inference** — The model processes the audio in chunks. Progress is reported in real time. (BS-RoFormer also accumulates chunks efficiently to prevent out-of-memory errors).
3. **Stem Writing** — Each stem is written to the output folder as a separate `.wav` file named `<original-filename>_<stem>.wav`.

Example output for `my_song.mp3` with the BS-RoFormer 6-stem model:
```
outputs/
  my_song_vocals.wav
  my_song_drums.wav
  my_song_bass.wav
  my_song_guitar.wav
  my_song_piano.wav
  my_song_other.wav
```

**5. Monitor progress**

- The **Progress** bar shows overall completion percentage and ETA.
- The **Log** panel shows key milestones: loading, chunk processing, and file writes.

**6. Cancel (optional)**

Click **Cancel** to stop after the current processing chunk. Output files written so far are preserved.

### Tips for Best Results
- Use **lossless sources** (WAV or FLAC) for highest separation quality.
- Very short clips (< 5 seconds) may produce artifacts — the model is optimised for full songs.
- If you run out of memory, reduce the **Chunk Size** in Settings and retry.

---

## How to Use: Settings (⚙️)

| Setting | Description |
|---|---|
| **Output Directory** | Default folder for all converted/separated files |
| **Models Directory** | Where AI weight files are stored |
| **FFmpeg Path** | Path to `ffmpeg` binary (leave blank to use system PATH) |
| **Chunk Size** | Inference chunk size in samples (lower = less RAM, more passes) |

Click **Save Settings** to persist. Click **Restore Defaults** to reset everything.

---

## Log Files

The app writes rotating log files to `<project-root>/logs/sound_processor.log`.  
Each run appends to the log, with automatic rotation at 5 MB (up to 3 backup files kept).  
These are useful for diagnosing errors that may not be fully visible in the UI.

```bash
tail -f logs/sound_processor.log    # follow live on macOS / Linux
```

---

## Project Structure

```
sound-processor/
├── main.py              # Application entry point
├── gui/                 # PySide6 UI (pages + widgets)
│   ├── main_window.py   # Sidebar shell and page switcher
│   ├── home_page.py     # Dashboard overview
│   ├── converter_page.py
│   ├── separator_page.py
│   ├── settings_page.py
│   └── widgets/         # DropZone, LogPanel, ProgressPanel, StemPreview
├── core/                # Audio engine, converter, separator, exporter
├── ai/                  # Model registry and separator implementations
│   ├── base_model.py    # BaseSeparatorModel interface + ModelMetadata
│   ├── model_manager.py # Thread-safe lazy model loader
│   ├── melband.py       # MelBand-RoFormer adapter
│   └── bs_roformer.py   # BS-RoFormer 6-stem adapter
├── workers/             # QThread workers for background processing
│   ├── converter_worker.py
│   └── separator_worker.py
├── utils/               # Config, logging, validators, file utilities
├── models/              # User-downloaded AI weights (gitignored)
├── assets/              # Icons and themes (dark.qss)
├── outputs/             # Default output directory (gitignored)
└── logs/                # Rotating log files (gitignored)
```

---

## AI Models

v1.0 ships with:
- **MelBand-RoFormer Kim vocal model** (`melband-roformer-kim-vocals`), producing two stems: `vocals` and `instrumental`.
- **BS-RoFormer 6-stem model** (`roformer-model-bs-roformer-ep_317_sdr_12.9755`), producing `vocals`, `drums`, `bass`, `guitar`, `piano`, and `other`.

### Adding a Custom Model

New models can be added without touching the UI:

1. Implement the `BaseSeparatorModel` interface in `ai/`:
   ```python
   from ai.base_model import BaseSeparatorModel, ModelMetadata

   class MyModel(BaseSeparatorModel):
       @property
       def metadata(self) -> ModelMetadata: ...
       def load(self) -> None: ...
       def separate(self, audio, sample_rate, **kwargs) -> dict[str, np.ndarray]: ...
   ```

2. Register it in `ai/__init__.py` via `ModelManager.register_model()`.

3. The Separator page will automatically list the new model in the dropdown and show its stems — no UI code changes required.

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `ffmpeg: command not found` | Install FFmpeg or set the full path in Settings → FFmpeg Path |
| Model download hangs / fails | Check your internet connection; try re-clicking **Separate Stems** |
| `Out of memory` during separation | Lower Chunk Size in Settings (try `176400` or `88200`) |
| No audio files appear in batch | Ensure files end in `.wav`, `.mp3`, `.flac`, `.ogg`, or `.m4a` |
| App opens but pages are blank | Run `python main.py` from the terminal and check the log output |
| `PyQt6` import error | Activate your virtual environment: `source .venv/bin/activate` |
| Output stems are silent | Make sure you are separating **music**. If you pass a voice recording to a 6-stem music model, the `drums`, `bass`, `guitar`, and `piano` tracks will correctly contain absolute silence! |

---

## License

TBD
