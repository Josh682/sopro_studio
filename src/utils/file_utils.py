"""File and path utilities: directory creation, collision-safe naming, temp files."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Generator


# ---------------------------------------------------------------------------
# Directory helpers
# ---------------------------------------------------------------------------

def ensure_dir(path: Path) -> Path:
    """Create *path* (and all parents) if it doesn't exist. Returns *path*."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_remove(path: Path) -> bool:
    """Delete *path* without raising if it is missing. Returns True if deleted."""
    try:
        path.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def safe_rmtree(path: Path) -> bool:
    """Recursively delete *path* without raising. Returns True if successful."""
    try:
        shutil.rmtree(path, ignore_errors=True)
        return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Collision-safe naming
# ---------------------------------------------------------------------------

def unique_output_path(directory: Path, stem: str, suffix: str) -> Path:
    """Return a non-colliding output path inside *directory*.

    Tries ``<stem><suffix>`` first; if that exists appends ``_1``, ``_2``, …
    until a free name is found.

    Args:
        directory: Target directory (need not exist yet).
        stem:      Base filename without extension (e.g. ``"vocals"``).
        suffix:    Extension including leading dot (e.g. ``".wav"``).

    Returns:
        A :class:`~pathlib.Path` that does not currently exist on disk.
    """
    candidate = directory / f"{stem}{suffix}"
    if not candidate.exists():
        return candidate
    counter = 1
    while True:
        candidate = directory / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def sanitize_filename(name: str, replacement: str = "_") -> str:
    """Replace characters illegal in filenames across platforms.

    Strips leading/trailing whitespace and replaces ``< > : " / \\ | ? *``
    and ASCII control characters with *replacement*.

    Args:
        name:        Raw filename string (without directory components).
        replacement: String to substitute for each illegal character.

    Returns:
        A cleaned filename string safe for Windows, macOS, and Linux.
    """
    illegal = set('<>:"/\\|?*')
    sanitized = "".join(
        replacement if (c in illegal or ord(c) < 32) else c for c in name
    )
    sanitized = sanitized.strip()
    # Prevent reserved Windows device names (NUL, CON, PRN, …)
    reserved = {
        "CON", "PRN", "AUX", "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
    stem = sanitized.rsplit(".", 1)[0].upper()
    if stem in reserved:
        sanitized = f"_{sanitized}"
    return sanitized or replacement


# ---------------------------------------------------------------------------
# Temporary file helpers
# ---------------------------------------------------------------------------

@contextmanager
def temp_wav_file(suffix: str = ".wav", dir: Path | None = None) -> Generator[Path, None, None]:
    """Context manager that yields a temporary file path and deletes it on exit.

    Args:
        suffix: File extension for the temp file (default ``.wav``).
        dir:    Directory to create the temp file in. Defaults to the OS temp dir.

    Yields:
        :class:`~pathlib.Path` pointing to a temporary file that already exists
        (zero bytes) so FFmpeg / soundfile can open it.
    """
    fd, raw_path = tempfile.mkstemp(suffix=suffix, dir=str(dir) if dir else None)
    path = Path(raw_path)
    try:
        os.close(fd)
        yield path
    finally:
        path.unlink(missing_ok=True)


def get_file_size_mb(path: Path) -> float:
    """Return the size of *path* in megabytes. Returns 0.0 if the file is missing."""
    try:
        return path.stat().st_size / (1024 * 1024)
    except OSError:
        return 0.0


def stem_with_suffix(path: Path, new_suffix: str) -> str:
    """Return the filename stem of *path* with *new_suffix* appended.

    Example::

        >>> stem_with_suffix(Path("song.mp3"), ".wav")
        'song.wav'
    """
    return f"{path.stem}{new_suffix}"


def reveal_in_file_manager(path: Path | str) -> bool:
    """Reveal *path* in the platform's default file manager.

    - macOS: ``open -R <path>``
    - Windows: ``explorer /select,<path>``
    - Linux: ``xdg-open <parent_dir>``

    Returns True if the launch command succeeded, False otherwise.
    """
    p = Path(path).resolve()
    if not p.exists():
        if not p.parent.exists():
            return False
        p = p.parent

    try:
        if sys.platform == "darwin":
            subprocess.run(["open", "-R", str(p)], check=True, capture_output=True)
            return True
        elif sys.platform == "win32":
            subprocess.run(["explorer", f"/select,{str(p)}"], check=True, capture_output=True)
            return True
        else:
            target = str(p) if p.is_dir() else str(p.parent)
            subprocess.run(["xdg-open", target], check=True, capture_output=True)
            return True
    except Exception:
        return False

