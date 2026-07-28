"""AI model registry and separator implementations.

Public re-exports so callers can do::

    from src.ai import ModelManager, MelBandModel
    from src.ai import BaseSeparatorModel, ModelMetadata
    from src.ai import ModelLoadError, SeparationError, SeparationCancelled
"""

from src.ai.base_model import (
    BaseSeparatorModel,
    ModelLoadError,
    ModelMetadata,
    ModelNotLoadedError,
    SeparationCancelled,
    SeparationError,
)
from src.ai.melband import MODEL_ID as MELBAND_MODEL_ID
from src.ai.melband import MelBandModel
from src.ai.model_manager import ModelManager


from src.ai.bs_roformer import MODEL_ID as BS_ROFORMER_MODEL_ID
from src.ai.bs_roformer import BSRoFormerModel


def create_default_manager(models_dir=None) -> ModelManager:
    """Create a :class:`ModelManager` pre-registered with the default v1.0 models.

    This is the recommended way to obtain a ready-to-use manager::

        from src.ai import create_default_manager
        manager = create_default_manager()
        model = manager.get_model("melband-roformer-kim-vocals")

    Args:
        models_dir: Override the default models directory.

    Returns:
        A :class:`ModelManager` with models registered.
    """
    manager = ModelManager(models_dir=models_dir)
    manager.register_model(MELBAND_MODEL_ID, MelBandModel)
    manager.register_model(BS_ROFORMER_MODEL_ID, BSRoFormerModel)
    return manager

__all__ = [
    # Base interface
    "BaseSeparatorModel",
    "ModelMetadata",
    # Exceptions
    "ModelLoadError",
    "ModelNotLoadedError",
    "SeparationError",
    "SeparationCancelled",
    # Registry
    "ModelManager",
    "create_default_manager",
    # Adapters
    "MelBandModel",
    "MELBAND_MODEL_ID",
    "BSRoFormerModel",
    "BS_ROFORMER_MODEL_ID",
]
