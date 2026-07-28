"""QSettings-backed persistent configuration."""

from pathlib import Path

from qtpy.QtCore import QSettings


class AppConfig:
    """Application settings persisted across sessions."""

    ORG = "SoundProcessor"
    APP = "SoundProcessor"

    def __init__(self) -> None:
        self._settings = QSettings(self.ORG, self.APP)

    @property
    def output_dir(self) -> Path:
        default = Path(__file__).resolve().parent.parent / "outputs"
        return Path(self._settings.value("output_dir", str(default)))

    @output_dir.setter
    def output_dir(self, path: Path) -> None:
        self._settings.setValue("output_dir", str(path))

    @property
    def models_dir(self) -> Path:
        default = Path(__file__).resolve().parent.parent / "models"
        return Path(self._settings.value("models_dir", str(default)))

    @models_dir.setter
    def models_dir(self, path: Path) -> None:
        self._settings.setValue("models_dir", str(path))

    @property
    def ffmpeg_path(self) -> str:
        return self._settings.value("ffmpeg_path", "ffmpeg")

    @ffmpeg_path.setter
    def ffmpeg_path(self, path: str) -> None:
        self._settings.setValue("ffmpeg_path", path)

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
