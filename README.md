# Sopro Studio

> **v1.0.0** — A standalone desktop application for high-fidelity audio processing, format conversion, and AI-powered instrument separation.

---

## Features

- **Audio Converter** — Cross-convert between MP3, WAV, and FLAC with format-specific settings (sample rate, bit depth, bitrate, compression)
- **AI Separator** — Stem separation powered by **BS-RoFormer** (6-stem) and **MelBand-RoFormer** (vocals + instrumental), with a dynamic UI that adapts to any registered model
- **Key Detection** — Analyze audio to detect the musical key and evaluate confidence scores using the `librosa` Krumhansl-Schmuckler algorithm
- **Pitch Shifter** — Batch transpose audio up or down in semitones without affecting the original tempo
- **Tempo Changer** — Batch stretch or compress audio playback speed to match a target BPM or percentage without altering pitch
- **Audio Trimmer** — Precisely trim audio files with interactive playback and batch processing support
- **Batch Processing** — Drag-and-drop, single file, folder, and batch modes across all tools
- **Auto-Updater** — Background update checker via GitHub Releases; notifies you in-app when a new version is available
- **Dark Theme** — Modern PyQt6 interface with Catppuccin Mocha color palette, watermarked backgrounds, and sidebar navigation

---

## Download (macOS)

The easiest way to use Sopro Studio is to download the pre-built `.app` bundle directly — no Python, no terminal required.

1. Go to the [**Releases**](https://github.com/Josh682/sopro_studio/releases) page
2. Download the latest `.dmg` or `.app` zip for macOS
3. Open it and drag **Sopro Studio** to your Applications folder

> **Gatekeeper notice**: On first launch, macOS may warn the app is from an unidentified developer. Right-click the app → **Open** → **Open** to bypass this once.

---

## Running from Source

If you prefer to run from source or contribute to the project:

### Requirements

- Python 3.10+
- [FFmpeg](https://ffmpeg.org/) — required for conversion features

#### FFmpeg Installation

| Platform | Command |
| -------- | ------- |
| macOS    | `brew install ffmpeg` |
| Windows  | `winget install ffmpeg` or download from [ffmpeg.org](https://ffmpeg.org/download.html) |
| Linux    | `sudo apt install ffmpeg` |

### Setup

```bash
git clone https://github.com/Josh682/sopro_studio.git
cd sopro_studio

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

# Install Python dependencies
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

> **Note:** If `melband-roformer-infer` is unavailable on PyPI, install it directly from its GitHub repository.

### Run

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
│ │ ✂️ Trim  │  │                                    │    │
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
| ✂️ Audio Trim | Trimmer Page | Trim audio with interactive player |
| 🎵 Key Detect | Key Detection | Detect musical key of audio files |
| ↕️ Pitch Shift | Pitch Shifter | Transpose audio pitch (semitones) |
| ⏱️ Tempo Change | Tempo Changer | Stretch/compress playback speed |
| ⚙️ Settings | Settings Page | Paths, FFmpeg, preferences, and updates |

---

## First-Time Setup

Before using the app's core features, configure your preferences in **Settings** (⚙️ in the sidebar):

1. **Output Folder** — Where converted files and separated stems will be saved.  
   Default: `~/Documents/Sopro Studio/Outputs/`

2. **FFmpeg Path** — Full path to the `ffmpeg` executable.  
   Leave blank to use system PATH (e.g., if installed via `brew install ffmpeg`).

3. **AI Models Folder** — Directory where AI model weight files are stored.  
   Default: `~/Library/Application Support/Sopro Studio/models/` (macOS)  
   Model weights are **downloaded automatically** on first use.

4. **Chunk Size** — Audio chunk size (in samples) used during AI inference.  
   Default: `352800` (~8 seconds at 44.1 kHz). Reduce if you hit out-of-memory errors.

5. **Check for Updates** — Toggle automatic update checks on startup. You can also trigger a manual check at any time via the **Check for Updates** button in Settings.

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
- Model weights download automatically on first use.
- Outputs separate `.wav` files for each isolated stem.

### Audio Trimmer (✂️)
Precisely trim audio files in either interactive Single mode or Batch mode.
- Set start and end times with optional millisecond-level fade-in/out.
- Interactive mode includes a full media player to listen and mark trim points.

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

## Auto-Updater

Sopro Studio checks for new releases on startup (if enabled in Settings).

- Checks are performed **silently in the background** and never block the UI.
- If a new version is found, an in-app banner appears with the version number, release notes, and a direct download link.
- The updater handles drafts, pre-releases, and network errors gracefully — it will never crash if GitHub is unavailable.
- You can toggle automatic update checks or trigger a manual check from **Settings → Check for Updates**.

---

## Application Data Directories

When running as a standalone app, Sopro Studio stores all user data outside the application bundle, following platform conventions:

| Platform | User Data Path |
|---|---|
| macOS | `~/Library/Application Support/Sopro Studio/` |
| Windows | `%LOCALAPPDATA%\Sopro Studio\` |
| Linux | `~/.local/share/Sopro Studio/` |

Inside the user data directory:

```
Sopro Studio/          ← user data root
├── models/            ← AI model weights (auto-downloaded)
├── logs/              ← rotating application logs
├── config/            ← saved preferences
└── cache/             ← temporary processing cache
```

Outputs are saved to:  
`~/Documents/Sopro Studio/Outputs/`

---

## Building from Source (macOS)

To produce a self-contained `.app` bundle:

```bash
# Install build dependencies
.venv/bin/pip install pyinstaller pillow

# Run the build script
./build_mac.sh
```

The final app will appear at `dist/Sopro Studio.app`. You can double-click it directly from Finder.

> **Note**: The build script bundles Qt platform plugins from your Homebrew installation automatically. Ensure Qt is installed via `brew install qt` if you encounter plugin errors.

---

## Log Files

When running as a standalone app, logs are written to:

| Platform | Log Path |
|---|---|
| macOS | `~/Library/Application Support/Sopro Studio/logs/sound_processor.log` |
| Windows | `%LOCALAPPDATA%\Sopro Studio\logs\sound_processor.log` |
| Linux | `~/.local/share/Sopro Studio/logs/sound_processor.log` |

When running from source:

```bash
tail -f logs/sound_processor.log    # macOS / Linux
```

Logs rotate automatically at 5 MB (up to 3 backup files kept).

---

## Project Structure

```
sopro_studio/
├── main.py              # Application entry point (sets QT_PLUGIN_PATH for bundles)
├── build.spec           # PyInstaller build configuration
├── build_mac.sh         # macOS build script
├── requirements.txt
├── src/
│   ├── __init__.py      # __version__
│   ├── gui/             # PyQt6 UI (pages + widgets)
│   │   ├── main_window.py       # Sidebar shell, page switcher, update banner
│   │   ├── home_page.py
│   │   ├── watermarked_page.py  # Base class for watermarked background pages
│   │   ├── converter_page.py
│   │   ├── separator_page.py
│   │   ├── combiner_page.py
│   │   ├── trimmer_page.py
│   │   ├── key_detection_page.py
│   │   ├── pitch_shift_page.py
│   │   ├── tempo_change_page.py
│   │   ├── settings_page.py     # Includes update toggle and manual check
│   │   └── widgets/             # Reusable UI components
│   ├── core/            # Audio engine, processor registry, exporter
│   │   └── processors/          # BaseProcessor and implementations
│   ├── workers/         # QThread workers for background processing
│   └── utils/           # Config, logging, validators, file utilities
│       ├── paths.py     # Cross-platform resource & data path resolution
│       ├── updater.py   # GitHub Releases update checker (background thread)
│       └── version.py   # Semantic version comparison
├── assets/              # Logos and themes (dark.qss)
└── docs/                # Architecture and feature planning docs
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
| App won't open on macOS | Right-click → **Open** → **Open** to bypass Gatekeeper on first launch |
| `ffmpeg: command not found` | Install FFmpeg or set the full path in Settings |
| Model download hangs / fails | Check your internet connection; try re-clicking **Separate Stems** |
| `Out of memory` during separation | Lower Chunk Size in Settings (try `176400` or `88200`) |
| App opens but pages are blank | Run `python main.py` from terminal and check the log output |
| `PyQt6` import error | Activate your virtual environment: `source .venv/bin/activate` |
| `Could not find Qt platform plugin "cocoa"` | Clear hidden flag on PySide6 dylibs via `chflags -R nohidden` or see [Qt Cocoa Troubleshooting Guide](docs/TROUBLESHOOTING_QT_COCOA.md) |
| Qt platform plugin error on build | Ensure `brew install qt` is done and re-run `./build_mac.sh` |

---

## License

TBD
