# Sopro Studio

A cross-platform desktop application for high-fidelity audio processing, format conversion, and AI-powered instrument separation.

---

## Features

- **Audio Converter** — Cross-convert between MP3, WAV, and FLAC with format-specific settings (sample rate, bit depth, bitrate, compression)
- **AI Separator** — Stem separation powered by **BS-RoFormer** (6-stem) and **MelBand-RoFormer** (vocals + instrumental), with a dynamic UI that adapts to any registered model
- **Key Detection** — Analyze audio to detect the musical key and evaluate confidence scores using the `librosa` Krumhansl-Schmuckler algorithm
- **Pitch Shifter** — Batch transpose audio up or down in semitones without affecting the original tempo
- **Tempo Changer** — Batch stretch or compress audio playback speed to match a target BPM or percentage without altering pitch
- **Batch Processing** — Drag-and-drop, single file, folder, and batch modes across all tools
- **Dark Theme** — Modern PyQt6 interface with Catppuccin Mocha color palette, watermarked backgrounds, and sidebar navigation

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
git clone https://github.com/Josh682/sopro_studio.git
cd sopro_studio

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
│  Sopro Studio                                           │
│ ┌──────────┐  ┌────────────────────────────────────┐    │
│ │ 🏠 Home  │  │                                    │    │
│ │ 🔄 Conv. │  │         Page Content Area          │    │
│ │ 🧠 Sep.  │  │                                    │    │
│ │ 🔗 Comb. │  │                                    │    │
│ │ 🎵 Key   │  │                                    │    │
│ │ ↕️ Pitch │  │                                    │    │
│ │ ⏱️ Tempo │  │                                    │    │
│ │ ⚙️ Sett. │  │                                    │    │
│ └──────────┘  └────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

| Sidebar Button | Page | Purpose |
|---|---|---|
| 🏠 Home | Dashboard | Quick stats and app overview |
| 🔄 Converter | Converter Page | Batch audio format conversion |
| 🧠 Separator | Separator Page | AI-powered stem separation |
| 🔗 Combiner | Combiner Page | Combine multiple audio tracks |
| 🎵 Key Detect | Key Detection | Detect musical key of audio files |
| ↕️ Pitch Shift | Pitch Shifter | Transpose audio pitch (semitones) |
| ⏱️ Tempo Change | Tempo Changer | Stretch/compress playback speed |
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

## Core Tools

### Audio Converter (🔄)
Converts one or many audio files between **WAV**, **MP3**, and **FLAC** formats.
- **WAV**: Bit depth (8, 16, 24, 32-bit)
- **MP3**: Bitrate (128, 192, 256, 320 kbps)
- **FLAC**: Compression level (0 to 8)
- Optional **Peak Normalization** to 0 dBFS before encoding.

### AI Stem Separator (🧠)
Splits an audio track into individual stems (e.g., vocals and instrumental).
- Choose between models like **BS-RoFormer (6 Stems)** and **MelBand-RoFormer**.
- Model weights download automatically.
- Outputs separate `.wav` files for each isolated stem.

### Key Detection (🎵)
Analyzes audio to detect its musical key.
- Displays the primary detected key.
- Shows alternative key candidates and confidence percentages.

### Pitch Shifter (↕️)
Transposes audio up or down without altering the tempo.
- Specify shift in semitones (e.g., +2 for up a whole step).
- Outputs high-quality 24-bit WAV files.

### Tempo Changer (⏱️)
Changes the playback speed of audio without affecting its pitch.
- **BPM Mode**: Input original BPM and target BPM to auto-calculate the rate.
- **Percentage Mode**: Input the exact speed adjustment percentage (e.g., +10%).
- Outputs high-quality 24-bit WAV files.

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
sopro_studio/
├── main.py              # Application entry point
├── src/
│   ├── gui/             # PySide6 UI (pages + widgets)
│   │   ├── main_window.py     # Sidebar shell and page switcher
│   │   ├── home_page.py       # Dashboard overview
│   │   ├── watermarked_page.py# Base class for watermarked background pages
│   │   ├── converter_page.py
│   │   ├── separator_page.py
│   │   ├── combiner_page.py
│   │   ├── key_detection_page.py
│   │   ├── pitch_shift_page.py
│   │   ├── tempo_change_page.py
│   │   ├── settings_page.py
│   │   └── widgets/           # Reusable UI components
│   ├── core/            # Audio engine, processor registry, exporter
│   │   └── processors/        # Base processor and implementations
│   ├── workers/         # QThread workers for background processing
│   └── utils/           # Config, logging, validators, file utilities
├── assets/              # Logos and themes (dark.qss)
├── docs/                # Architecture and feature planning docs
├── outputs/             # Default output directory (gitignored)
└── logs/                # Rotating log files (gitignored)
```

---

## Extending the App

New processors can be easily added to Sopro Studio by subclassing `BaseProcessor` and registering them via `ProcessorRegistry`.

1. Implement your processor logic inheriting from `BaseProcessor`.
2. Register it in `src/core/processors/__init__.py`.
3. Create a new UI page inheriting from `WatermarkedPage`.
4. Connect it to the sidebar in `main_window.py`.

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `ffmpeg: command not found` | Install FFmpeg or set the full path in Settings |
| Model download hangs / fails | Check your internet connection; try re-clicking **Separate Stems** |
| `Out of memory` during separation | Lower Chunk Size in Settings (try `176400` or `88200`) |
| App opens but pages are blank | Run `python main.py` from the terminal and check the log output |
| `PyQt6` import error | Activate your virtual environment: `source .venv/bin/activate` |

---

## License

TBD
