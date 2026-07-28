"""BS-RoFormer multi-stem model adapter.

Wraps the ``bs-roformer-infer`` package to provide a clean
:class:`~ai.base_model.BaseSeparatorModel` implementation for the
6-stem BS-RoFormer checkpoint.

All heavy imports (``torch``, ``bs_roformer``) are deferred to
:meth:`BSRoFormerModel.load` and :meth:`BSRoFormerModel.separate` so that
importing this module at application startup costs essentially nothing.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable

from src.ai.base_model import (
    BaseSeparatorModel,
    ModelLoadError,
    ModelMetadata,
    ModelNotLoadedError,
    SeparationCancelled,
    SeparationError,
)

log = logging.getLogger("sound_processor.ai.bs_roformer")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODEL_ID = "roformer-model-bs-roformer-sw-by-jarredou"

#: Default overlap-add chunk size in samples.
#: Users can tune this down to fit smaller VRAM budgets via Settings.
DEFAULT_CHUNK_SIZE = 588_800

#: Model's native sample rate — always 44 100 Hz.
MODEL_SAMPLE_RATE = 44_100

#: BS-RoFormer always operates in stereo internally.
MODEL_CHANNELS = 2


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

class BSRoFormerModel(BaseSeparatorModel):
    """BS-RoFormer 6-stem adapter.

    Wraps ``bs-roformer-infer`` (``demix_track``, ``get_model_from_config``,
    ``ensure_model_assets``) behind the :class:`~ai.base_model.BaseSeparatorModel`
    interface.

    Args:
        chunk_size: Overlap-add chunk size in samples passed to ``demix_track``.
                    Defaults to :data:`DEFAULT_CHUNK_SIZE`. Reduce for
                    GPUs with limited VRAM.
    """

    def __init__(self, chunk_size: int = DEFAULT_CHUNK_SIZE) -> None:
        self.metadata = ModelMetadata(
            model_id=MODEL_ID,
            display_name="BS-RoFormer (6 Stems)",
            stem_names=("vocals", "drums", "bass", "guitar", "piano", "other"),
            output_format="wav",
            sample_rate=MODEL_SAMPLE_RATE,
            input_formats=("wav", "mp3", "flac"),
            description=(
                "Advanced 6-stem separation using BS-RoFormer. "
                "Isolates vocals, drums, bass, guitar, piano, and other instruments."
            ),
            requires_gpu=True,
            chunk_size=chunk_size,
        )
        self._chunk_size = chunk_size
        self._model = None          # torch.nn.Module, set by load()
        self._config = None         # ml_collections.ConfigDict, set by load()
        self._device = None         # torch.device, set by load()

    # ------------------------------------------------------------------
    # BaseSeparatorModel: load
    # ------------------------------------------------------------------

    @property
    def is_loaded(self) -> bool:
        """``True`` once model weights are in memory."""
        return self._model is not None

    def load(self, models_dir: Path) -> ModelMetadata:
        """Download (if needed) and load the BS-RoFormer checkpoint.

        This method is idempotent — a second call is a no-op and returns
        :attr:`metadata` immediately.

        Args:
            models_dir: Directory for storing/finding checkpoint files.

        Returns:
            :class:`~ai.base_model.ModelMetadata` for this model.

        Raises:
            :class:`~ai.base_model.ModelLoadError`: If download or weight
                loading fails.
        """
        if self.is_loaded:
            log.debug("BSRoFormerModel already loaded — skipping.")
            return self.metadata

        log.info("Loading BS-RoFormer from '%s'…", models_dir)

        try:
            import torch
            import yaml
            from ml_collections import ConfigDict
            from bs_roformer.download import ensure_model_assets
            from bs_roformer.utils import get_model_from_config
        except ImportError as exc:
            raise ModelLoadError(
                f"Required package not installed: {exc}. "
                "Run: pip install bs-roformer-infer torch torchaudio"
            ) from exc

        # ---- Resolve device --------------------------------------------
        # Priority: CUDA (Nvidia) > MPS (Apple Silicon Metal) > CPU
        if torch.cuda.is_available():
            device = torch.device("cuda")
            log.info("Using CUDA GPU for inference.")
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            device = torch.device("mps")
            log.info("Using Apple Silicon GPU (MPS) for inference.")
        else:
            device = torch.device("cpu")
            log.warning(
                "No GPU available (CUDA or MPS) — BS-RoFormer will run on CPU, "
                "which may be very slow for long tracks."
            )

        # ---- Auto-download checkpoint + config -------------------------
        try:
            ckpt_path, config_path = ensure_model_assets(
                model=MODEL_ID,
                models_dir=models_dir,
            )
        except Exception as exc:
            raise ModelLoadError(
                f"Failed to download BS-RoFormer assets: {exc}"
            ) from exc

        # ---- Parse YAML config -----------------------------------------
        try:
            config = _load_config(config_path, yaml, ConfigDict)
        except Exception as exc:
            raise ModelLoadError(
                f"Failed to parse model config '{config_path}': {exc}"
            ) from exc

        # ---- Build + load model weights --------------------------------
        try:
            model = get_model_from_config("bs_roformer", config)
            state = torch.load(ckpt_path, map_location="cpu", weights_only=True)
            # Checkpoints may be saved as bare state_dict or wrapped in a dict.
            if isinstance(state, dict) and "state_dict" in state:
                state = state["state_dict"]
            model.load_state_dict(state)
            model.to(device)
            model.eval()
        except Exception as exc:
            raise ModelLoadError(
                f"Failed to load BS-RoFormer weights from '{ckpt_path}': {exc}"
            ) from exc

        self._model = model
        self._config = config
        self._device = device
        log.info(
            "BS-RoFormer loaded on %s (chunk_size=%d).",
            device, self._chunk_size,
        )
        return self.metadata

    # ------------------------------------------------------------------
    # BaseSeparatorModel: separate
    # ------------------------------------------------------------------

    def separate(
        self,
        input_path: Path,
        output_dir: Path,
        on_progress: Callable[[float, str], None] | None = None,
        cancel_flag: threading.Event | None = None,
    ) -> dict[str, Path]:
        """Separate *input_path* into multiple stems.

        Args:
            input_path:  Path to the input audio file (WAV/MP3/FLAC).
            output_dir:  Directory where output WAV files are written.
            on_progress: Optional ``(fraction, message)`` progress callback.
            cancel_flag: Optional :class:`threading.Event`; checked before
                         inference begins and after writing each stem.

        Returns:
            Dictionary mapping stem names to their respective output paths.

        Raises:
            :class:`~ai.base_model.ModelNotLoadedError`: If :meth:`load` was
                not called first.
            :class:`~ai.base_model.SeparationCancelled`: If *cancel_flag* is set.
            :class:`~ai.base_model.SeparationError`: On any inference failure.
        """
        if not self.is_loaded:
            raise ModelNotLoadedError(
                "Call BSRoFormerModel.load(models_dir) before separate()."
            )

        _check_cancel(cancel_flag)
        _progress(on_progress, 0.0, "Preparing input audio…")

        try:
            import torch
            import numpy as np
            from bs_roformer.inference import demix_track
        except ImportError as exc:
            raise SeparationError(f"Missing runtime dependency: {exc}") from exc

        output_dir.mkdir(parents=True, exist_ok=True)

        # ---- Stage 1: Decode + preprocess (0 → 0.15) -------------------
        _progress(on_progress, 0.05, f"Decoding '{input_path.name}'…")
        try:
            mixture = _load_and_preprocess(input_path, MODEL_SAMPLE_RATE)
        except Exception as exc:
            raise SeparationError(
                f"Failed to decode '{input_path.name}': {exc}"
            ) from exc

        _check_cancel(cancel_flag)
        _progress(on_progress, 0.15, "Running BS-RoFormer inference…")

        # ---- Stage 2: Inference (0.15 → 0.85) --------------------------
        # demix_track handles overlap-add chunking internally.
        # We wrap it with a simple chunk-count tracker for progress.
        try:
            sources = _run_demix(
                model=self._model,
                config=self._config,
                device=self._device,
                mixture=mixture,
                chunk_size=self._chunk_size,
                cancel_flag=cancel_flag,
                on_progress=_make_inference_progress_cb(on_progress, cancel_flag),
            )
        except SeparationCancelled:
            raise
        except Exception as exc:
            raise SeparationError(
                f"BS-RoFormer inference failed: {exc}"
            ) from exc

        _check_cancel(cancel_flag)
        _progress(on_progress, 0.87, "Writing stem files…")

        # ---- Stage 3: Write stems (0.87 → 1.0) -------------------------
        stem_paths: dict[str, Path] = {}
        stem_names = list(self.metadata.stem_names)

        try:
            from src.audio.writer import write_wav

            for i, stem_name in enumerate(stem_names):
                _check_cancel(cancel_flag)
                out_path = output_dir / f"{stem_name}_{input_path.stem}.wav"

                # sources is a numpy array shaped (num_stems, channels, frames)
                # or a dict[str, ndarray] depending on demix_track version.
                stem_audio = _extract_stem(sources, i, stem_name, mixture)

                # demix_track returns (channels, frames) — transpose to (frames, channels)
                stem_audio = stem_audio.T  # → (frames, channels)

                write_wav(out_path, stem_audio.astype(np.float32), MODEL_SAMPLE_RATE)
                stem_paths[stem_name] = out_path
                log.debug("Wrote stem '%s' → '%s'", stem_name, out_path)

                frac = 0.87 + (0.13 * (i + 1) / len(stem_names))
                _progress(on_progress, frac, f"Wrote {out_path.name}")

        except (SeparationCancelled, SeparationError):
            raise
        except Exception as exc:
            raise SeparationError(f"Failed to write stems: {exc}") from exc

        _progress(on_progress, 1.0, "Separation complete.")
        log.info(
            "Separation complete for '%s': %s",
            input_path.name,
            {k: str(v) for k, v in stem_paths.items()},
        )
        return stem_paths

    # ------------------------------------------------------------------
    # BaseSeparatorModel: unload
    # ------------------------------------------------------------------

    def unload(self) -> None:
        """Release model weights and free GPU memory."""
        if self._model is not None:
            try:
                import torch
                del self._model
                self._model = None
                self._config = None
                self._device = None
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                log.debug("BSRoFormerModel unloaded.")
            except Exception as exc:  # noqa: BLE001
                log.warning("Error during BSRoFormerModel.unload(): %s", exc)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_config(config_path: Path, yaml, ConfigDict):
    """Parse YAML config, tolerating ``!!python/tuple`` tags."""
    import yaml as _yaml

    class _SafeTupleLoader(_yaml.SafeLoader):
        pass

    _SafeTupleLoader.add_constructor(
        "tag:yaml.org,2002:python/tuple",
        lambda loader, node: loader.construct_sequence(node),
    )

    with open(config_path, "r", encoding="utf-8") as fh:
        raw = _yaml.load(fh, Loader=_SafeTupleLoader)  # noqa: S506

    return ConfigDict(raw)


def _load_and_preprocess(input_path: Path, target_sr: int):
    """Decode *input_path* and return a stereo float32 numpy array.

    Returns an array of shape ``(channels=2, frames)`` at *target_sr*.
    Uses ``audio.loader`` (FFmpeg) for broad format support.
    """
    import numpy as np
    from src.audio.loader import load_audio

    samples, sr = load_audio(input_path, sample_rate=target_sr)

    # Ensure float32
    samples = samples.astype(np.float32)

    # Ensure stereo: (frames,) mono → (frames, 2) → (2, frames)
    if samples.ndim == 1:
        samples = np.stack([samples, samples], axis=1)  # (frames, 2)
    elif samples.shape[1] == 1:
        samples = np.concatenate([samples, samples], axis=1)  # (frames, 2)
    elif samples.shape[1] > 2:
        samples = samples[:, :2]  # take first two channels

    # Transpose to (channels, frames) as demix_track expects
    return samples.T  # (2, frames)


def _run_demix(
    model,
    config,
    device,
    mixture,
    chunk_size: int,
    cancel_flag,
    on_progress: Callable | None,
):
    """Run demixing with a custom CPU-accumulator overlap-add loop.
    
    This avoids Apple Silicon unified memory OOM silent failures when processing
    large 6-stem tracks (which require ~8.8GB for the output tensor alone).
    By accumulating the output on the CPU, we fit within 8GB safely while
    still exploiting the GPU for inference chunks.
    """
    import torch
    import torch.nn as nn
    from bs_roformer.utils import get_windowing_array
    
    # Resolve overlapping params
    N = config.inference.num_overlap
    step = chunk_size // N
    fade_size = chunk_size // 10
    border = chunk_size - step

    # Pre-pad mixture
    mix = torch.from_numpy(mixture)
    if mix.shape[1] > 2 * border and border > 0:
        mix = nn.functional.pad(mix, (border, border), mode='reflect')

    windowing_array_cpu = get_windowing_array(chunk_size, fade_size, "cpu")

    # Allocate massive accumulators on CPU instead of Device
    if config.training.target_instrument is not None:
        req_shape = (1, ) + tuple(mix.shape)
    else:
        req_shape = (len(config.training.instruments),) + tuple(mix.shape)

    result = torch.zeros(req_shape, dtype=torch.float32)
    counter = torch.zeros(req_shape, dtype=torch.float32)

    i = 0
    total_length = mix.shape[1]
    num_chunks = (total_length + step - 1) // step
    chunk_idx = 0

    with torch.no_grad():
        while i < total_length:
            _check_cancel(cancel_flag)
            if on_progress:
                on_progress(chunk_idx, num_chunks)
            chunk_idx += 1

            part = mix[:, i:i + chunk_size]
            length = part.shape[-1]
            
            if length < chunk_size:
                if length > chunk_size // 2 + 1:
                    part = nn.functional.pad(part, pad=(0, chunk_size - length), mode='reflect')
                else:
                    part = nn.functional.pad(part, pad=(0, chunk_size - length, 0, 0), mode='constant', value=0)

            # Move chunk to GPU
            part_dev = part.to(device)
            x_dev = model(part_dev.unsqueeze(0))[0]
            # Immediately move result back to CPU to save VRAM
            x = x_dev.cpu()

            window = windowing_array_cpu.clone()
            if i == 0:
                window[:fade_size] = 1
            elif i + chunk_size >= total_length:
                window[-fade_size:] = 1

            result[..., i:i+length] += x[..., :length] * window[..., :length]
            counter[..., i:i+length] += window[..., :length]
            i += step

        estimated_sources = result / counter
        estimated_sources = estimated_sources.numpy()
        import numpy as np
        np.nan_to_num(estimated_sources, copy=False, nan=0.0)

        if mix.shape[1] > 2 * border and border > 0:
            estimated_sources = estimated_sources[..., border:-border]

    # Map outputs back to instrument keys
    if config.training.target_instrument is None:
        sources_dict = {k: v for k, v in zip(config.training.instruments, estimated_sources)}
    else:
        sources_dict = {k: v for k, v in zip([config.training.target_instrument], estimated_sources)}
        
    return sources_dict


def _extract_stem(sources, index: int, stem_name: str, mixture=None):
    """Extract stem audio from the demix_track return value.

    ``demix_track`` returns either:
    - A ``dict[str, ndarray]`` keyed by instrument name, or
    - An ``ndarray`` of shape ``(num_stems, channels, frames)``.

    This function handles both formats. If a stem is missing (e.g. instrumental
    in a vocals-only model), it computes the residual from the mixture.
    """
    import numpy as np

    if isinstance(sources, dict):
        # Prefer exact key match, then case-insensitive.
        if stem_name in sources:
            return sources[stem_name]
        lower_map = {k.lower(): v for k, v in sources.items()}
        if stem_name.lower() in lower_map:
            return lower_map[stem_name.lower()]
        
        # If stem not found but we have the mixture and this is a single-target model,
        # compute the residual stem by subtracting the generated stem from the mixture.
        if mixture is not None and len(sources) == 1:
            return mixture - next(iter(sources.values()))
            
        # Fall back to positional index.
        values = list(sources.values())
        if index < len(values):
            return values[index]
        raise SeparationError(
            f"demix_track did not return stem '{stem_name}'. "
            f"Available: {list(sources.keys())}"
        )
    else:
        # numpy array (num_stems, channels, frames)
        arr = np.asarray(sources)
        if arr.ndim == 3 and index < arr.shape[0]:
            return arr[index]
        raise SeparationError(
            f"Cannot extract stem '{stem_name}' (index {index}) from "
            f"sources array of shape {arr.shape}."
        )


def _make_inference_progress_cb(
    on_progress: Callable[[float, str], None] | None,
    cancel_flag,
) -> Callable | None:
    """Return a no-op if *on_progress* is None, otherwise a pass-through."""
    if on_progress is None:
        return None

    def _cb(chunk_idx: int, total_chunks: int) -> None:
        _check_cancel(cancel_flag)
        if total_chunks > 0:
            frac = 0.15 + 0.72 * (chunk_idx / total_chunks)
            _progress(
                on_progress, frac,
                f"Processing chunk {chunk_idx}/{total_chunks}…",
            )

    return _cb


def _check_cancel(cancel_flag) -> None:
    """Raise :class:`~ai.base_model.SeparationCancelled` if *cancel_flag* is set."""
    if cancel_flag is not None and cancel_flag.is_set():
        raise SeparationCancelled("Separation cancelled by user.")


def _progress(
    callback: Callable[[float, str], None] | None,
    fraction: float,
    message: str,
) -> None:
    """Safely invoke the progress callback."""
    if callback is not None:
        try:
            callback(fraction, message)
        except SeparationCancelled:
            raise  # let cancel propagate
        except Exception:  # noqa: BLE001
            pass  # never let a UI callback crash inference
