"""AI Denoise Processor with deterministic DSP hum filtering and adaptive spectral subtraction."""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable

import numpy as np
from scipy import signal

from src.core.audio_engine import AudioBuffer, AudioEngine
from src.core.exporter import ExportEngine
from src.core.processor_registry import ProcessorRegistry
from src.core.processors.base_processor import (
    BaseProcessor,
    ParameterDescriptor,
    ProcessingMode,
    ProcessorMetadata,
)
from src.utils.config import AppConfig

log = logging.getLogger("sound_processor.core.processors.denoise")


def detect_hum_fundamental(audio: np.ndarray, sr: int, threshold_db: float = 8.0) -> float | None:
    """Detect whether prominent 50Hz or 60Hz electrical ground hum is present in the signal."""
    mono = np.mean(audio, axis=1) if audio.ndim == 2 else audio
    max_len = int(min(len(mono), sr * 5))
    if max_len < 1024:
        return None
    segment = mono[:max_len]

    # Welch PSD with fine resolution
    nperseg = min(len(segment), 32768)
    if nperseg < 2048:
        return None
    freqs, psd = signal.welch(segment, fs=sr, nperseg=nperseg)

    # Broadband noise floor in 30Hz - 200Hz
    band_mask = (freqs >= 30.0) & (freqs <= 200.0)
    if not np.any(band_mask):
        return None
    median_power = np.median(psd[band_mask]) + 1e-12

    # Check for 50Hz: peak within [49.0, 51.0] must exceed neighbors
    mask_50 = (freqs >= 49.0) & (freqs <= 51.0)
    peak_50 = np.max(psd[mask_50]) if np.any(mask_50) else 0.0
    ratio_50_db = 10.0 * np.log10(peak_50 / median_power) if peak_50 > 0 else -100

    # Check for 60Hz: peak within [59.0, 61.0] must exceed neighbors
    mask_60 = (freqs >= 59.0) & (freqs <= 61.0)
    peak_60 = np.max(psd[mask_60]) if np.any(mask_60) else 0.0
    ratio_60_db = 10.0 * np.log10(peak_60 / median_power) if peak_60 > 0 else -100

    # Verify that 50 or 60 is a local maximum in [45, 55] or [55, 65]
    mask_50_local = (freqs >= 45.0) & (freqs <= 55.0)
    is_50_local_peak = np.any(mask_50_local) and (peak_50 >= np.max(psd[mask_50_local]))

    mask_60_local = (freqs >= 55.0) & (freqs <= 65.0)
    is_60_local_peak = np.any(mask_60_local) and (peak_60 >= np.max(psd[mask_60_local]))

    if ratio_50_db >= threshold_db and is_50_local_peak and ratio_50_db > ratio_60_db:
        return 50.0
    elif ratio_60_db >= threshold_db and is_60_local_peak:
        return 60.0
    return None


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


class DenoiseProcessor(BaseProcessor):
    """Audio denoising processor targeting hiss, electrical hum, fan drone, and background noise."""

    metadata = ProcessorMetadata(
        id="denoise",
        name="AI Denoise",
        description="Removes background hiss, 50/60Hz ground hum, and steady drone using spectral subtraction and notch filters.",
        version="1.0.0",
        category="Restoration",
        tags=["denoise", "hiss", "hum", "noise-reduction"],
    )
    processing_mode = ProcessingMode.FILE

    def __init__(
        self,
        engine: AudioEngine | None = None,
        exporter: ExportEngine | None = None,
        ffmpeg_bin: str | None = None,
    ) -> None:
        app_config = AppConfig()
        self._ffmpeg_bin = ffmpeg_bin or app_config.ffmpeg_path
        self._engine = engine or AudioEngine(ffmpeg_bin=self._ffmpeg_bin)
        self._exporter = exporter or ExportEngine(ffmpeg_bin=self._ffmpeg_bin)

    def process_file(
        self,
        input_path: Path,
        output_dir: Path,
        options: dict[str, Any],
        on_progress: Callable[[float, str], None] | None = None,
        cancel_flag: threading.Event | None = None,
    ) -> Path:
        """Process a single file: load, run denoising, and save."""
        if cancel_flag and cancel_flag.is_set():
            return input_path

        if on_progress:
            on_progress(0.05, f"Loading {input_path.name}...")

        buffer = AudioBuffer.load(input_path, ffmpeg_bin=self._ffmpeg_bin)
        samples = buffer.samples
        sr = buffer.sample_rate
        channels = buffer.channels

        if cancel_flag and cancel_flag.is_set():
            return input_path

        if on_progress:
            on_progress(0.15, "Applying noise reduction...")

        processed_samples = self.enhance(
            audio=samples,
            sr=sr,
            options=options,
            on_progress=on_progress,
            cancel_flag=cancel_flag,
        )

        if cancel_flag and cancel_flag.is_set():
            return input_path

        if on_progress:
            on_progress(0.90, "Exporting denoised audio...")

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = input_path.suffix.lower() if input_path.suffix.lower() in [".wav", ".mp3", ".flac"] else ".wav"
        base_name = f"{input_path.stem}_{self.metadata.id}"
        out_path = output_dir / f"{base_name}{suffix}"
        counter = 1
        while out_path.exists():
            out_path = output_dir / f"{base_name}_{counter}{suffix}"
            counter += 1

        if processed_samples.ndim == 1 and channels > 1:
            processed_samples = np.repeat(processed_samples[:, np.newaxis], channels, axis=1)

        out_buffer = AudioBuffer(
            samples=processed_samples.astype(np.float32),
            sample_rate=sr,
            channels=channels if processed_samples.ndim > 1 else 1,
        )
        exported = out_buffer.save(out_path, ffmpeg_bin=self._ffmpeg_bin)
        if on_progress:
            on_progress(1.0, f"Completed: {exported.name}")
        return exported

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
        if noise_type == "hum_50hz":
            fund = 50.0
            if on_progress:
                on_progress(0.25, f"Filtering electrical hum (50Hz)...")
            processed = apply_hum_notch(processed, sr=sr, fundamental=fund)
            return processed.astype(np.float32)
        elif noise_type == "hum_60hz":
            fund = 60.0
            if on_progress:
                on_progress(0.25, f"Filtering electrical hum (60Hz)...")
            processed = apply_hum_notch(processed, sr=sr, fundamental=fund)
            return processed.astype(np.float32)
        elif noise_type == "auto":
            detected_fund = detect_hum_fundamental(processed, sr=sr)
            if detected_fund:
                if on_progress:
                    on_progress(0.25, f"Detected & filtering electrical hum ({detected_fund:.0f}Hz)...")
                processed = apply_hum_notch(processed, sr=sr, fundamental=detected_fund)

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
