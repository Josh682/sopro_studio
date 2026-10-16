"""Custom Visual Decks for Slot 2 in Umbra Workspace."""

from typing import Optional

from src.ui.components.custom_stages.analysis_stage import AnalysisStage
from src.ui.components.custom_stages.stem_deck_stage import StemDeckStage
from src.ui.components.custom_stages.waveform_stage import WaveformStage
from src.ui.qt import QWidget


def create_custom_stage(
    module_id: str,
    accent_color: str = "#F59E0B",
    parent: Optional[QWidget] = None,
) -> Optional[QWidget]:
    """Factory creating module-tailored visual stage for Slot 2.

    Args:
        module_id: Unique module identifier (e.g. 'trimmer', 'key_detector', 'separator').
        accent_color: Accent color string hex.
        parent: Parent widget.

    Returns:
        Stage widget, or None if module uses standard InteractiveDeck only.
    """
    if module_id in (
        "pitch_time", "edit", "repair", "clean", "voice",
        "trim", "trimmer", "normalize", "loudness",
        "declip", "denoise", "dereverb", "voice_enhancement", "restoration",
    ):
        return WaveformStage(accent_color=accent_color, parent=parent)
    elif module_id in ("analyze", "detect", "key_detector"):
        return AnalysisStage(accent_color=accent_color, parent=parent)
    elif module_id in ("separator",):
        return StemDeckStage(accent_color=accent_color, parent=parent)
    return None


__all__ = [
    "WaveformStage",
    "AnalysisStage",
    "StemDeckStage",
    "create_custom_stage",
]
