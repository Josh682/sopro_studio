"""Voice Enhancement Processor for speech clarity, presence boost, and de-essing."""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable

import numpy as np
from scipy import signal

from src.core.processor_registry import ProcessorRegistry
from src.core.processors.base_enhancement_processor import BaseEnhancementProcessor
from src.core.processors.base_processor import ParameterDescriptor, ProcessorMetadata

log = logging.getLogger("sound_processor.core.processors.voice_enhancement")

PRESETS: dict[str, dict[str, Any]] = {
    "podcast": {
        "clarity_strength": 0.70,
        "de_ess_strength": 0.40,
        "enhance_presence": True,
    },
    "voiceover": {
        "clarity_strength": 0.50,
        "de_ess_strength": 0.60,
        "enhance_presence": True,
    },
    "vocal": {
        "clarity_strength": 0.80,
        "de_ess_strength": 0.50,
        "enhance_presence": True,
    },
    "custom": {
        "clarity_strength": 0.50,
        "de_ess_strength": 0.30,
        "enhance_presence": True,
    },
}


def apply_mud_reduction(audio: np.ndarray, sr: int, strength: float = 0.5) -> np.ndarray:
    """Attenuates boxy lower-mid resonances (220Hz - 480Hz) to improve speech clarity."""
    if strength <= 0.01:
        return audio

    center_freq = 340.0
    q = 1.2
    # Gain reduction in dB proportional to strength (up to -6 dB)
    gain_db = -6.0 * np.clip(strength, 0.0, 1.0)
    gain_linear = 10.0 ** (gain_db / 40.0)  # gentle dip

    # Peaking / notch filter
    b, a = signal.iirpeak(center_freq, q, sr)
    # Blend: original - (1 - gain_linear) * filtered_peak
    filtered_peak = signal.filtfilt(b, a, audio, axis=0)
    return audio - (1.0 - gain_linear) * filtered_peak


def apply_presence_boost(audio: np.ndarray, sr: int, boost_db: float = 2.5) -> np.ndarray:
    """Enhances the 2.5kHz - 4.5kHz presence band for speech intelligibility."""
    center_freq = 3200.0
    q = 1.0
    gain_linear = 10.0 ** (boost_db / 20.0)

    b, a = signal.iirpeak(center_freq, q, sr)
    peak = signal.filtfilt(b, a, audio, axis=0)
    return audio + (gain_linear - 1.0) * 0.4 * peak


def apply_de_essing(audio: np.ndarray, sr: int, strength: float = 0.4) -> np.ndarray:
    """Dynamic split-band de-esser targeting harsh sibilance in 6.5kHz - 11kHz."""
    if strength <= 0.01:
        return audio

    # Isolate sibilance band using bandpass filter
    low_cut = 6500.0
    high_cut = min(11500.0, sr / 2.0 - 500.0)
    if low_cut >= high_cut:
        return audio

    b, a = signal.butter(4, [low_cut, high_cut], btype="bandpass", fs=sr)
    sibilance_band = signal.filtfilt(b, a, audio, axis=0)

    # Compute short-term RMS envelope of the sibilant energy
    window_samples = int(0.015 * sr)  # 15 ms envelope window
    if window_samples > 0:
        kernel = np.ones(window_samples) / window_samples
        if audio.ndim == 2:
            env = np.column_stack([
                np.sqrt(np.convolve(sibilance_band[:, ch] ** 2, kernel, mode="same") + 1e-9)
                for ch in range(audio.shape[1])
            ])
        else:
            env = np.sqrt(np.convolve(sibilance_band**2, kernel, mode="same") + 1e-9)
    else:
        env = np.abs(sibilance_band)

    # Threshold: above 75th percentile of active audio
    active_env = env[env > 1e-4]
    if len(active_env) == 0:
        return audio

    thresh = np.percentile(active_env, 75)
    # Gain attenuation factor when sibilant envelope exceeds threshold
    excess = np.maximum(0.0, env - thresh)
    attenuation = np.clip(1.0 - (excess / (thresh + 1e-5)) * (strength * 1.5), 0.25, 1.0)

    # Apply dynamic attenuation only to sibilant band
    corrected_sibilance = sibilance_band * (attenuation - 1.0)
    return audio + corrected_sibilance


class VoiceEnhancementProcessor(BaseEnhancementProcessor):
    """Audio enhancement processor tailored for dialogue, podcasting, and vocal production."""

    metadata = ProcessorMetadata(
        id="voice_enhancement",
        name="Voice Enhancement",
        description="Improves vocal clarity, reduces lower-mid boxiness, tames harsh sibilance, and lifts speech presence.",
        version="1.0.0",
        category="Enhancement",
        tags=["voice", "speech", "clarity", "de-ess", "podcast"],
    )

    @classmethod
    def get_parameter_descriptors(cls) -> list[ParameterDescriptor]:
        return [
            ParameterDescriptor(
                name="target_use",
                label="Target Preset",
                type="choice",
                choices=["podcast", "voiceover", "vocal", "custom"],
                default="podcast",
                tooltip="Pre-tuned profile for specific vocal application.",
            ),
            ParameterDescriptor(
                name="clarity_strength",
                label="Clarity & Mud Reduction",
                type="float",
                default=0.70,
                min=0.0,
                max=1.0,
                tooltip="Amount of lower-mid boxiness attenuation.",
            ),
            ParameterDescriptor(
                name="de_ess_strength",
                label="De-essing Strength",
                type="float",
                default=0.40,
                min=0.0,
                max=1.0,
                tooltip="Intensity of harsh 's' and 'sh' frequency suppression.",
            ),
            ParameterDescriptor(
                name="enhance_presence",
                label="Enhance Presence (2.5 - 4.5 kHz)",
                type="bool",
                default=True,
                tooltip="Brings vocals forward in the mix for higher intelligibility.",
            ),
        ]

    def enhance(
        self,
        audio: np.ndarray,
        sr: int,
        options: dict[str, Any],
        on_progress: Callable[[float, str], None] | None = None,
        cancel_flag: threading.Event | None = None,
    ) -> np.ndarray:
        target_use = str(options.get("target_use", "podcast")).lower()
        preset_vals = PRESETS.get(target_use, PRESETS["podcast"])

        clarity = float(options.get("clarity_strength", preset_vals["clarity_strength"]))
        de_ess = float(options.get("de_ess_strength", preset_vals["de_ess_strength"]))
        presence = bool(options.get("enhance_presence", preset_vals["enhance_presence"]))

        processed = audio.copy()

        # Step 1: Mud reduction (220-480 Hz)
        if on_progress:
            on_progress(0.25, f"Reducing lower-mid boxiness ({clarity*100:.0f}%)...")
        if cancel_flag and cancel_flag.is_set():
            return audio
        processed = apply_mud_reduction(processed, sr=sr, strength=clarity)

        # Step 2: Presence boost (2.5-4.5 kHz)
        if presence:
            if on_progress:
                on_progress(0.50, "Boosting vocal presence & articulation...")
            if cancel_flag and cancel_flag.is_set():
                return audio
            processed = apply_presence_boost(processed, sr=sr, boost_db=2.5)

        # Step 3: De-essing (6.5-11 kHz)
        if de_ess > 0.01:
            if on_progress:
                on_progress(0.75, f"Suppressing harsh sibilance ({de_ess*100:.0f}%)...")
            if cancel_flag and cancel_flag.is_set():
                return audio
            processed = apply_de_essing(processed, sr=sr, strength=de_ess)

        # Protect against clipping
        peak = np.max(np.abs(processed))
        if peak > 0.99:
            processed = processed * (0.95 / peak)

        return processed.astype(np.float32)


# Self-register
ProcessorRegistry.register(VoiceEnhancementProcessor)
