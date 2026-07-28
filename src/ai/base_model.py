"""Base separator model interface and metadata contract.

Every AI stem-separation model in this application implements
:class:`BaseSeparatorModel` and exposes a :class:`ModelMetadata` instance
so that the UI and orchestration layer can discover capabilities (stem names,
sample rate, supported input formats) without loading the model weights.
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ModelMetadata:
    """Immutable runtime metadata exposed by every separator model.

    This object is returned by :meth:`BaseSeparatorModel.load` and is also
    readable before loading (from :attr:`BaseSeparatorModel.metadata`) so that
    the UI can list available models without paying the weight-load cost.

    Attributes:
        model_id:       Unique slug used as registry key
                        (e.g. ``"melband-roformer-kim-vocals"``).
        display_name:   Human-readable name for the UI.
        stem_names:     Ordered tuple of output stem labels returned by
                        :meth:`~BaseSeparatorModel.separate`
                        (e.g. ``("vocals", "instrumental")``).
        output_format:  Container format for all exported stems
                        (``"wav"``, ``"mp3"``, or ``"flac"``).
        sample_rate:    Native operating sample rate of the model in Hz.
        input_formats:  Tuple of accepted input container formats
                        (e.g. ``("wav", "mp3", "flac")``).
        description:    Optional free-text model description shown in the UI.
        requires_gpu:   ``True`` if the model will run significantly slower on
                        CPU (informational — does not block CPU inference).
        chunk_size:     Default overlap-add chunk size in samples.  ``0``
                        means the model decides at runtime.
    """

    model_id: str
    display_name: str
    stem_names: tuple[str, ...]
    output_format: str
    sample_rate: int
    input_formats: tuple[str, ...]
    description: str = ""
    requires_gpu: bool = False
    chunk_size: int = 0


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------

class BaseSeparatorModel(ABC):
    """Common interface for all AI separator models.

    Subclasses must implement :meth:`load` (weight loading + optional
    auto-download) and :meth:`separate` (inference).  All other attributes
    and helpers are provided by this base class.

    Lifecycle:

    1. The model is instantiated by the factory registered with
       :class:`~ai.model_manager.ModelManager` — this must be cheap (no GPU
       allocation, no file I/O).
    2. :meth:`load` is called once with *models_dir* to load weights.
       Calling ``load`` a second time on an already-loaded model is a no-op.
    3. :meth:`separate` may be called as many times as needed.
    4. :meth:`unload` releases GPU/CPU tensors when the model is no longer
       needed (optional — the manager calls this on eviction).
    """

    #: Pre-load metadata so the UI can describe the model without loading it.
    metadata: ModelMetadata

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def load(self, models_dir: Path) -> ModelMetadata:
        """Load model weights from *models_dir* and return metadata.

        Must be idempotent — calling ``load`` on an already-loaded model
        should return :attr:`metadata` immediately without re-loading.

        Args:
            models_dir: Directory containing (or where to download) the
                        model checkpoint and config files.

        Returns:
            :class:`ModelMetadata` for this model.

        Raises:
            :class:`ModelLoadError`: If weights cannot be found or loaded.
        """

    @abstractmethod
    def separate(
        self,
        input_path: Path,
        output_dir: Path,
        on_progress: Callable[[float, str], None] | None,
        cancel_flag: threading.Event | None,
    ) -> dict[str, Path]:
        """Separate *input_path* into stems and write them to *output_dir*.

        Args:
            input_path:  Path to the audio file to separate.
            output_dir:  Directory where output stem files are written.
                         Created automatically if it doesn't exist.
            on_progress: Optional ``(fraction: float, message: str) → None``
                         callback.  Called periodically with values in
                         ``[0.0, 1.0]``.  Must never raise.
            cancel_flag: Optional :class:`threading.Event`.  The model checks
                         this between chunks and raises
                         :class:`SeparationCancelled` when set.

        Returns:
            Mapping of ``stem_name → output_file_path`` for every stem in
            :attr:`~ModelMetadata.stem_names`.

        Raises:
            :class:`SeparationError`:     If inference fails.
            :class:`SeparationCancelled`: If *cancel_flag* is set.
            :class:`ModelNotLoadedError`: If :meth:`load` has not been called.
        """

    # ------------------------------------------------------------------
    # Optional lifecycle hooks (default: no-op)
    # ------------------------------------------------------------------

    def unload(self) -> None:
        """Release model weights and free GPU/CPU memory.

        The default implementation is a no-op.  Override to delete tensors,
        call ``torch.cuda.empty_cache()``, etc.
        """

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def is_loaded(self) -> bool:
        """``True`` when the model weights have been loaded into memory.

        The default implementation always returns ``False``.  Subclasses
        should override this with a real check (e.g. ``return self._model is not None``).
        """
        return False

    @property
    def model_id(self) -> str:
        """Shorthand for ``self.metadata.model_id``."""
        return self.metadata.model_id

    @property
    def stem_names(self) -> tuple[str, ...]:
        """Shorthand for ``self.metadata.stem_names``."""
        return self.metadata.stem_names

    def __repr__(self) -> str:
        loaded = "loaded" if self.is_loaded else "not loaded"
        return f"{self.__class__.__name__}(id={self.model_id!r}, {loaded})"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ModelLoadError(RuntimeError):
    """Raised when model weights cannot be found, downloaded, or loaded."""


class ModelNotLoadedError(RuntimeError):
    """Raised when :meth:`~BaseSeparatorModel.separate` is called before :meth:`~BaseSeparatorModel.load`."""


class SeparationError(RuntimeError):
    """Raised when the inference pass fails for any reason."""


class SeparationCancelled(RuntimeError):
    """Raised when the user cancels an in-progress separation."""
