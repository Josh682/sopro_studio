"""Cross-platform path resolution for bundled resources and application data."""

import os
import sys
from pathlib import Path


APP_NAME = "Sopro Studio"


def is_bundled() -> bool:
    """Return True if the application is running as a PyInstaller bundle."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def resource_path(relative_path: str | Path) -> Path:
    """
    Get the absolute path to a resource.
    Works for dev and for PyInstaller.
    """
    if is_bundled():
        # PyInstaller extracts data into a temporary folder _MEIPASS
        base_path = Path(getattr(sys, "_MEIPASS"))
    else:
        # During dev, resources are relative to the project root (src/../)
        base_path = Path(__file__).resolve().parent.parent.parent
        
    return base_path / relative_path


def user_data_dir() -> Path:
    """
    Get the OS-specific application data directory.
    - macOS: ~/Library/Application Support/Sopro Studio
    - Windows: %LOCALAPPDATA%/Sopro Studio
    - Linux: ~/.local/share/Sopro Studio
    """
    home = Path.home()
    if sys.platform == "darwin":
        path = home / "Library" / "Application Support" / APP_NAME
    elif sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA", str(home / "AppData" / "Local"))
        path = Path(local_app_data) / APP_NAME
    else:
        # Linux / fallback
        xdg_data = os.environ.get("XDG_DATA_HOME", str(home / ".local" / "share"))
        path = Path(xdg_data) / APP_NAME
        
    path.mkdir(parents=True, exist_ok=True)
    return path


def models_dir() -> Path:
    path = user_data_dir() / "models"
    path.mkdir(parents=True, exist_ok=True)
    return path


def logs_dir() -> Path:
    path = user_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_dir() -> Path:
    path = user_data_dir() / "config"
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_dir() -> Path:
    path = user_data_dir() / "cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def outputs_dir() -> Path:
    """User-facing outputs directory, placed in Documents for easy access."""
    path = Path.home() / "Documents" / APP_NAME / "Outputs"
    path.mkdir(parents=True, exist_ok=True)
    return path
