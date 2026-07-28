# UI Framework

This document outlines the UI framework, styling principles, and core widgets used in the Sound Processor project.

## Installation

**CRITICAL**: Do not install PyQt6 via `pip` on macOS. The pip version of PyQt6 has known issues with broken audio and multimedia on certain macOS versions. Instead, install PyQt6 via Homebrew, which links correctly against system frameworks.

**Installation Command:**
```bash
brew install pyqt@6
```

**Configuration:**
To make the Homebrew installation accessible to your Python environment, add it to your `PYTHONPATH`:
```bash
export PYTHONPATH=$(brew --prefix pyqt@6)/lib/python3.14/site-packages
```

## Abstraction Layer

We use `qtpy` as an abstraction layer over PyQt6. This provides future-proofing, allowing the application to switch between PyQt5, PyQt6, PySide2, or PySide6 seamlessly if licensing or compatibility requirements change in the future.

## Color System (Catppuccin Mocha)

The application uses the Catppuccin Mocha color palette to provide a modern, comfortable dark mode experience.

| Color Name | Hex Value | Usage / Role |
| :--- | :--- | :--- |
| **Base** | `#1e1e2e` | Main window background |
| **Mantle** | `#181825` | Sidebar background |
| **Crust** | `#11111b` | Deep background / borders |
| **Surface0** | `#313244` | Card / Panel background |
| **Surface1** | `#45475a` | Hover states |
| **Surface2** | `#585b70` | Active states |
| **Overlay0** | `#6c7086` | Disabled text / Borders |
| **Overlay1** | `#7f849c` | Subtle text |
| **Overlay2** | `#9399b2` | Secondary text |
| **Subtext0** | `#a6adc8` | Muted text |
| **Subtext1** | `#bac2de` | Secondary primary text |
| **Text** | `#cdd6f4` | Primary text |
| **Rosewater** | `#f5e0dc` | Accent |
| **Flamingo** | `#f2cdcd` | Accent |
| **Pink** | `#f5c2e7` | Accent |
| **Mauve** | `#cba6f7` | Primary Accent Color |
| **Red** | `#f38ba8` | Error states |
| **Maroon** | `#eba0ac` | Secondary Error |
| **Peach** | `#fab387` | Accent |
| **Yellow** | `#f9e2af` | Warning states |
| **Green** | `#a6e3a1` | Success states |
| **Teal** | `#94e2d5` | Accent |
| **Sky** | `#89dceb` | Accent |
| **Sapphire** | `#74c7ec` | Accent |
| **Blue** | `#89b4fa` | Info states / Links |
| **Lavender** | `#b4befe` | Accent |

## Reusable Widget Library

The application utilizes several custom reusable widgets:

- **DropZone**: A drag-and-drop file input area featuring an animated dashed border to indicate interaction state.
- **ProgressPanel**: A unified progress indicator showing a per-file progress bar alongside an overall batch progress bar.
- **LogPanel**: A scrollable text output area (`QPlainTextEdit`) that displays application logs, dynamically color-coded by log level (Info=Blue, Warning=Yellow, Error=Red).
- **StemPreviewWidget**: A visual component providing a waveform preview of separated audio stems, equipped with integrated playback controls.

## Page Navigation

The main application structure employs a `QMainWindow` with a fixed left sidebar (implemented via a `QListWidget` or custom layout of buttons). The main content area utilizes a `QStackedWidget` to swap between different content pages based on the sidebar selection.

## Stylesheet Approach

Styling is centralized to maintain consistency.
- **Global Styles**: Defined in a central `styles.py` file containing a `STYLESHEET` constant. This is applied globally via `app.setStyleSheet()`.
- **Local Overrides**: Per-widget specific styling can be applied using `widget.setStyleSheet()` when necessary, though this should be minimized in favor of CSS classes (`setProperty('class', '...')`).

## Typography

The application uses standard system fonts optimized for readability and modern appearance.
- **Families**: `['SF Pro Display', 'Helvetica Neue', 'Arial', 'sans-serif']`

*Note: Custom web fonts like 'Outfit' are not used by default to minimize dependencies and ensure reliable rendering.*

## Responsive Layout Guidelines

- **Resizing**: Use `QSplitter` to create adjustable panels (e.g., between the main content and the log panel).
- **Constraints**: Set a reasonable minimum window size to prevent layout breakage. The minimum recommended size is `1100x700`.
- **Layouts**: Exclusively use `QVBoxLayout`, `QHBoxLayout`, and `QGridLayout` to ensure widgets scale gracefully.

## Testability

All significant interactive and structural widgets must have their Object Name explicitly set using `setObjectName('meaningful_id')`. This practice establishes a convention for automated GUI testing and targeted CSS styling.
