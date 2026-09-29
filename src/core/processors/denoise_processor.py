"""AI Denoise Processor with deterministic DSP hum filtering and adaptive spectral subtraction."""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable

import numpy as np
from scipy import signal

from src.core.processor_registry import ProcessorRegistry
from src.core.processors.base_enhancement_processor import BaseEnhancementProcessor
from src.core.processors.base_processor import ParameterDescriptor, ProcessorMetadata

log = logging.getLogger("sound_processor.core.processors.denoise")


def apply_hum_notch(
    audio: np.ndarray,
    sr: int,
    fundamental: float = 60.0,
    harmonics: int = 8,
    q: float = 30.0,
) -> np.ndarray:
    """Removes electrical hum and its harmonics using high-Q notch filters."""
    filtered = audio.copy()
    nyquist = sr / 2.0

    for i in range(1, harmonics + 1):
        target_f = fundamental * i
        if target_f >= nyquist - 50:
            break

        # Design IIR notch filter
        b, a = signal.iirnotch(target_f, q, sr)
        if filtered.ndim == 2:
            for ch in range(filtered.shape[1]):
                filtered[:, ch] = signal.filtfilt(b, a, filtered[:, ch])
        else:
            filtered = signal.filtfilt(b, a, filtered)

    return filtered


def spectral_subtraction_denoise(
    audio: np.ndarray,
    sr: int,
    strength: float = 0.7,
    preserve_high_freq: bool = True,
    noise_mode: str = "general",
) -> np.ndarray:
    """Performs adaptive spectral subtraction with spectral floor and cross-band smoothing."""
    is_stereo = (audio.ndim == 2)
    channels = audio.shape[1] if is_stereo else 1

    n_fft = 2048
    hop_length = 512
    win = np.hanning(n_fft)

    denoised_channels = []

    for ch in range(channels):
        channel_data = audio[:, ch] if is_stereo else audio

        # STFT
        _, _, Zxx = signal.stft(channel_data, fs=sr, window=win, nperseg=n_fft, noverlap=n_fft - hop_length)
        magnitude = np.abs(Zxx)
        phase = np.angle(Zxx)

        # Estimate noise profile:
        # Find the 10th percentile magnitude across time frames as the stationary noise floor
        noise_profile = np.percentile(magnitude, 15, axis=1, keepdims=True)

        # Tune noise subtraction based on mode
        alpha = 1.0 + (strength * 2.5)  # Over-subtraction factor
        beta = max(0.02, 0.15 - (strength * 0.12))  # Spectral floor factor

        if noise_mode == "hiss":
            # Target higher frequencies more aggressively
            freqs = np.linspace(0, sr / 2, magnitude.shape[0])
            hiss_weight = np.clip((freqs - 2000) / 4000, 0.2, 1.5)[:, np.newaxis]
            subtracted = magnitude - (alpha * noise_profile * hiss_weight)
        elif noise_mode == "fan":
            # Target low-mid rumble/drone
            freqs = np.linspace(0, sr / 2, magnitude.shape[0])
            fan_weight = np.clip(1.5 - (freqs / 3000), 0.3, 1.8)[:, np.newaxis]
            subtracted = magnitude - (alpha * noise_profile * fan_weight)
        else:
            subtracted = magnitude - (alpha * noise_profile)

        # Apply spectral floor to prevent musical noise chirping
        cleaned_mag = np.maximum(subtracted, beta * magnitude)

        # Preserve high frequency "air" if requested (> 8 kHz)
        if preserve_high_freq:
            freqs = np.linspace(0, sr / 2, magnitude.shape[0])
            hf_mask = (freqs >= 8000)[:, np.newaxis]
            blend_factor = 0.35  # Keep 35% of original high-frequency dynamics
            cleaned_mag = np.where(hf_mask, (1.0 - blend_factor) * cleaned_mag + blend_factor * magnitude, cleaned_mag)

        # Reconstruct complex spectrum
        Zxx_clean = cleaned_mag * np.exp(1j * phase)

        # ISTFT
        _, time_series = signal.istft(Zxx_clean, fs=sr, window=win, nperseg=n_fft, noverlap=n_fft - hop_length)

        # Match length
        if len(time_series) > len(channel_data):
            time_series = time_series[: len(channel_data)]
        elif len(time_series) < len(channel_data):
            time_series = np.pad(time_series, (0, len(channel_data) - len(time_series)))

        denoised_channels.append(time_series)

    if is_stereo:
        return np.column_stack(denoised_channels)
    return denoised_channels[0]


class DenoiseProcessor(BaseEnhancementProcessor):
    """Audio denoising processor targeting hiss, electrical hum, fan drone, and background noise."""

    metadata = ProcessorMetadata(
        id="denoise",
        name="AI Denoise",
        description="Removes background hiss, 50/60Hz ground hum, and steady drone using spectral subtraction and notch filters.",
        version="1.0.0",
        category="Restoration",
        tags=["denoise", "hiss", "hum", "noise-reduction"],
    )

    @classmethod
    def get_parameter_descriptors(cls) -> list[ParameterDescriptor]:
        return [
            ParameterDescriptor(
                name="noise_type",
                label="Noise Type",
                type="choice",
                choices=["auto", "hiss", "hum_50hz", "hum_60hz", "fan", "general"],
                default="auto",
                tooltip="Select specific noise profile to target.",
            ),
            ParameterDescriptor(
                name="strength",
                label="Denoise Strength",
                type="float",
                default=0.70,
                min=0.1,
                max=1.0,
                tooltip="Amount of noise attenuation. Higher values remove more noise but may cause artifacts.",
            ),
            ParameterDescriptor(
                name="preserve_high_freq",
                label="Preserve High Frequencies",
                type="bool",
                default=True,
                tooltip="Prevents muffling by preserving natural vocal air above 8kHz.",
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
        noise_type = str(options.get("noise_type", "auto")).lower()
        strength = float(options.get("strength", 0.70))
        preserve_hf = bool(options.get("preserve_high_freq", True))

        processed = audio.copy()

        # Step 1: Handle ground hum
        if noise_type in ["hum_50hz", "hum_60hz"] or noise_type == "auto":
            fund = 50.0 if noise_type == "hum_50hz" else 60.0
            if on_progress:
                on_progress(0.25, f"Filtering electrical hum ({fund:.0f}Hz)...")
            processed = apply_hum_notch(processed, sr=sr, fundamental=fund)

        if noise_type in ["hum_50hz", "hum_60hz"]:
            return processed.astype(np.float32)

        if cancel_flag and cancel_flag.is_set():
            return audio

        # Step 2: Adaptive spectral subtraction
        if on_progress:
            on_progress(0.50, f"Applying spectral subtraction ({noise_type})...")

        mode = "hiss" if noise_type == "hiss" else ("fan" if noise_type == "fan" else "general")
        processed = spectral_subtraction_denoise(
            processed,
            sr=sr,
            strength=strength,
            preserve_high_freq=preserve_hf,
            noise_mode=mode,
        )

        return processed.astype(np.float32)


# Self-register
ProcessorRegistry.register(DenoiseProcessor)
