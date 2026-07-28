"""Model registry with lazy loading and lifecycle management.

:class:`ModelManager` is the single source of truth for which separator
models are available in the application.  Models are registered via factory
callables so that no weight I/O happens at import time.  The manager lazily
loads weights on first ``get_model()`` call and caches the loaded instance
for subsequent requests.
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
)

log = logging.getLogger("sound_processor.ai.model_manager")


class ModelManager:
    """Registry and lifecycle manager for AI separator models.

    Usage::

        manager = ModelManager(models_dir=Path("models"))
        manager.register_model("my-model", MyModel)

        # List available models without loading weights
        for meta in manager.list_models():
            print(meta.display_name, meta.stem_names)

        # Lazy-load and retrieve
        model = manager.get_model("my-model")
        stems = model.separate(input_path, output_dir, on_progress, cancel_flag)

    Args:
        models_dir: Directory where model checkpoints and configs are stored.
                    Passed to :meth:`~ai.base_model.BaseSeparatorModel.load`
                    on first use.  Defaults to ``<project_root>/models``.
    """

    def __init__(self, models_dir: Path | None = None) -> None:
        if models_dir is None:
            models_dir = Path(__file__).resolve().parent.parent / "models"
        self._models_dir: Path = models_dir

        # model_id → factory (zero-arg callable returning a BaseSeparatorModel)
        self._registry: dict[str, Callable[[], BaseSeparatorModel]] = {}
        # model_id → fully loaded instance
        self._instances: dict[str, BaseSeparatorModel] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_model(
        self,
        model_id: str,
        factory: type[BaseSeparatorModel] | Callable[[], BaseSeparatorModel],
    ) -> None:
        """Register a model factory under *model_id*.

        Args:
            model_id: Unique slug (e.g. ``"melband-roformer-kim-vocals"``).
            factory:  Zero-arg callable that constructs a fresh
                      :class:`~ai.base_model.BaseSeparatorModel` instance.
                      A class itself is a valid factory.

        Raises:
            ValueError: If *model_id* is already registered.
        """
        with self._lock:
            if model_id in self._registry:
                log.warning("Model '%s' is already registered — overwriting.", model_id)
            self._registry[model_id] = factory
            log.debug("Registered model '%s'.", model_id)

    def unregister_model(self, model_id: str) -> None:
        """Unregister *model_id* and unload any cached instance.

        Args:
            model_id: Model to remove.

        Raises:
            KeyError: If *model_id* is not registered.
        """
        with self._lock:
            if model_id not in self._registry:
                raise KeyError(f"Unknown model: {model_id!r}")
            self._unload_locked(model_id)
            del self._registry[model_id]
            log.debug("Unregistered model '%s'.", model_id)

    # ------------------------------------------------------------------
    # Discovery (no weight loading)
    # ------------------------------------------------------------------

    def list_models(self) -> list[ModelMetadata]:
        """Return lightweight metadata for every registered model.

        Instantiates each model (cheap — no I/O) and reads its
        :attr:`~ai.base_model.BaseSeparatorModel.metadata` attribute.
        Model weights are **not** loaded.

        Returns:
            List of :class:`~ai.base_model.ModelMetadata` objects in
            registration order.
        """
        result: list[ModelMetadata] = []
        with self._lock:
            for model_id, factory in self._registry.items():
                # Use cached instance if available; otherwise build a temp one.
                if model_id in self._instances:
                    result.append(self._instances[model_id].metadata)
                else:
                    try:
                        tmp = factory()
                        result.append(tmp.metadata)
                    except Exception as exc:  # noqa: BLE001
                        log.warning(
                            "Could not read metadata for '%s': %s", model_id, exc
                        )
        return result

    def registered_ids(self) -> list[str]:
        """Return a list of all registered model IDs."""
        with self._lock:
            return list(self._registry.keys())

    def is_registered(self, model_id: str) -> bool:
        """Return ``True`` if *model_id* is registered."""
        with self._lock:
            return model_id in self._registry

    def is_loaded(self, model_id: str) -> bool:
        """Return ``True`` if *model_id* has been loaded into memory."""
        with self._lock:
            instance = self._instances.get(model_id)
            return instance is not None and instance.is_loaded

    # ------------------------------------------------------------------
    # Lazy load & retrieve
    # ------------------------------------------------------------------

    def get_model(self, model_id: str) -> BaseSeparatorModel:
        """Return the loaded model for *model_id*, loading it if necessary.

        Thread-safe.  If two threads call ``get_model`` simultaneously for the
        same *model_id*, only one load is performed.

        Args:
            model_id: ID of the model to retrieve.

        Returns:
            Fully loaded :class:`~ai.base_model.BaseSeparatorModel`.

        Raises:
            KeyError:        If *model_id* is not registered.
            ModelLoadError:  If the model's ``load()`` call fails.
        """
        with self._lock:
            if model_id not in self._registry:
                raise KeyError(f"Unknown model: {model_id!r}")

            if model_id not in self._instances:
                instance = self._registry[model_id]()
                self._instances[model_id] = instance

            instance = self._instances[model_id]

        # Load outside the lock so other threads aren't blocked during I/O.
        if not instance.is_loaded:
            log.info("Loading model '%s' from '%s'…", model_id, self._models_dir)
            try:
                instance.load(self._models_dir)
            except Exception as exc:
                raise ModelLoadError(
                    f"Failed to load model '{model_id}': {exc}"
                ) from exc
            log.info("Model '%s' loaded.", model_id)

        return instance

    # ------------------------------------------------------------------
    # Unload / eviction
    # ------------------------------------------------------------------

    def unload_model(self, model_id: str) -> None:
        """Unload *model_id* from memory (weights freed, instance kept).

        The factory remains registered — the next :meth:`get_model` call will
        reload from disk.

        Args:
            model_id: ID of the model to unload.

        Raises:
            KeyError: If *model_id* is not registered.
        """
        with self._lock:
            if model_id not in self._registry:
                raise KeyError(f"Unknown model: {model_id!r}")
            self._unload_locked(model_id)

    def unload_all(self) -> None:
        """Unload all currently loaded models."""
        with self._lock:
            for model_id in list(self._instances.keys()):
                self._unload_locked(model_id)

    def _unload_locked(self, model_id: str) -> None:
        """Internal unload — must be called with :attr:`_lock` held."""
        instance = self._instances.pop(model_id, None)
        if instance is not None:
            try:
                instance.unload()
            except Exception as exc:  # noqa: BLE001
                log.warning("Error unloading model '%s': %s", model_id, exc)
            log.debug("Unloaded model '%s'.", model_id)

    # ------------------------------------------------------------------
    # Models directory
    # ------------------------------------------------------------------

    @property
    def models_dir(self) -> Path:
        """Directory where model weights are stored / downloaded."""
        return self._models_dir

    @models_dir.setter
    def models_dir(self, path: Path) -> None:
        """Change the models directory.  Unloads all cached models."""
        with self._lock:
            self.unload_all()
            self._models_dir = path
            log.info("ModelManager models_dir changed to '%s'.", path)

    # ------------------------------------------------------------------
    # Dunder
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        """Number of registered models."""
        with self._lock:
            return len(self._registry)

    def __contains__(self, model_id: str) -> bool:
        return self.is_registered(model_id)

    def __repr__(self) -> str:
        with self._lock:
            ids = list(self._registry.keys())
        return f"ModelManager(models={ids}, dir={self._models_dir})"
