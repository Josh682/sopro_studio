"""QSettings-backed persistent configuration."""

from pathlib import Path
from typing import Any

try:
    from src.ui.qt import QSettings
except Exception:
    try:
        from PySide6.QtCore import QSettings
    except Exception:
        from qtpy.QtCore import QSettings

from src.utils.paths import outputs_dir, models_dir, resource_path


class AppConfig:
    """Application settings persisted across sessions."""

    ORG = "SoundProcessor"
    APP = "SoundProcessor"

    def __init__(self) -> None:
        self._settings = QSettings(self.ORG, self.APP)

    @property
    def output_dir(self) -> Path:
        return Path(self._settings.value("output_dir", str(outputs_dir())))

    @output_dir.setter
    def output_dir(self, path: Path) -> None:
        self._settings.setValue("output_dir", str(path))

    @property
    def models_dir(self) -> Path:
        return Path(self._settings.value("models_dir", str(models_dir())))

    @models_dir.setter
    def models_dir(self, path: Path) -> None:
        self._settings.setValue("models_dir", str(path))

    @property
    def ffmpeg_path(self) -> str:
        # Check system ffmpeg first (avoids macOS Gatekeeper quarantine delays on bundled binary)
        import shutil
        val = self._settings.value("ffmpeg_path", None)
        system_bin = shutil.which("ffmpeg")
        if val and "assets/bin/ffmpeg" not in str(val) and Path(str(val)).exists():
            return str(val)
        if system_bin:
            return system_bin
        bundled = resource_path("assets/bin/ffmpeg")
        if bundled.exists():
            return str(bundled)
        return "ffmpeg"

    @ffmpeg_path.setter
    def ffmpeg_path(self, path: str) -> None:
        self._settings.setValue("ffmpeg_path", path)

    @property
    def auto_check_updates(self) -> bool:
        # Returns True if missing
        val = self._settings.value("auto_check_updates", True)
        if isinstance(val, str):
            return val.lower() == "true"
        return bool(val)

    @auto_check_updates.setter
    def auto_check_updates(self, check: bool) -> None:
        self._settings.setValue("auto_check_updates", check)

    @property
    def last_update_check(self) -> float:
        # Timestamp in seconds since epoch
        try:
            return float(self._settings.value("last_update_check", 0.0))
        except (ValueError, TypeError):
            return 0.0

    @last_update_check.setter
    def last_update_check(self, timestamp: float) -> None:
        self._settings.setValue("last_update_check", timestamp)

    @property
    def melband_chunk_size(self) -> int:
        return int(self._settings.value("melband_chunk_size", 352800))

    @melband_chunk_size.setter
    def melband_chunk_size(self, size: int) -> None:
        self._settings.setValue("melband_chunk_size", size)

    @property
    def bs_roformer_chunk_size(self) -> int:
        return int(self._settings.value("bs_roformer_chunk_size", 588800))

    @bs_roformer_chunk_size.setter
    def bs_roformer_chunk_size(self, size: int) -> None:
        self._settings.setValue("bs_roformer_chunk_size", size)

    @property
    def last_selected_separator_model(self) -> str:
        return self._settings.value("last_selected_separator_model", "melband-roformer-kim-vocals")

    @last_selected_separator_model.setter
    def last_selected_separator_model(self, model_id: str) -> None:
        self._settings.setValue("last_selected_separator_model", model_id)

    @property
    def last_used_bs_checkpoint(self) -> str:
        return self._settings.value("last_used_bs_checkpoint", "roformer-model-bs-roformer-sw-by-jarredou")

    @last_used_bs_checkpoint.setter
    def last_used_bs_checkpoint(self, checkpoint_id: str) -> None:
        self._settings.setValue("last_used_bs_checkpoint", checkpoint_id)

    def get(self, key: str, default: Any = None) -> Any:
        """Generic config getter fallback."""
        return self._settings.value(key, default)

    def set(self, key: str, value: Any) -> None:
        """Generic config setter fallback."""
        self._settings.setValue(key, value)
