"""AI Dereverb Processor for suppressing room reverberation and extracting dry direct sound."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
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

log = logging.getLogger("sound_processor.core.processors.dereverb")


def apply_wiener_dereverb(
    audio: np.ndarray,
    sr: int,
    amount: str = "moderate",
    preserve_warmth: bool = True,
) -> np.ndarray:
    """Suppresses diffuse late reverberation using spectral decay gating."""
    is_stereo = (audio.ndim == 2)
    channels = audio.shape[1] if is_stereo else 1

    # Map amount to aggressiveness parameters
    if amount == "subtle":
        decay_factor = 0.88
        gain_floor = 0.55
        suppress_scale = 1.2
    elif amount == "aggressive":
        decay_factor = 0.75
        gain_floor = 0.15
        suppress_scale = 2.5
    else:  # moderate
        decay_factor = 0.82
        gain_floor = 0.30
        suppress_scale = 1.8

    n_fft = 2048
    hop_length = 512
    win = np.hanning(n_fft)

    dereverbed_channels = []

    for ch in range(channels):
        channel_data = audio[:, ch] if is_stereo else audio

        # STFT
        _, _, Zxx = signal.stft(channel_data, fs=sr, window=win, nperseg=n_fft, noverlap=n_fft - hop_length)
        magnitude = np.abs(Zxx)
        phase = np.angle(Zxx)

        n_freqs, n_frames = magnitude.shape

        # Reverb tail tracking:
        # Reverb decays exponentially. We model the estimated reverberant energy
        # as a recursive one-pole smoother following the signal decay.
        reverb_estimate = np.zeros_like(magnitude)
        running_tail = magnitude[:, 0].copy()

        for t in range(n_frames):
            cur_mag = magnitude[:, t]
            # Tail decays by decay_factor, or resets upwards on sharp transients
            running_tail = np.maximum(running_tail * decay_factor, cur_mag * 0.15)
            # Reverb is predominantly present when current frame is decaying
            is_decaying = cur_mag < running_tail * 1.5
            reverb_estimate[:, t] = np.where(is_decaying, running_tail, cur_mag * 0.05)

        # Wiener-like gain mask: G = (Mag^2 - Reverb^2) / Mag^2
        direct_energy = np.maximum(0.0, magnitude**2 - (suppress_scale * reverb_estimate)**2)
        gain_mask = np.sqrt(direct_energy / (magnitude**2 + 1e-9))
        gain_mask = np.clip(gain_mask, gain_floor, 1.0)

        # Smooth gain mask across time to prevent flutter artifacts
        gain_mask = signal.medfilt2d(gain_mask, kernel_size=[1, 3])

        # Preserve warmth: Protect low frequencies (< 350 Hz) from being thinned
        if preserve_warmth:
            freqs = np.linspace(0, sr / 2, n_freqs)
            warmth_mask = (freqs <= 350)[:, np.newaxis]
            # Keep original low frequencies prominent
            gain_mask = np.where(warmth_mask, np.maximum(gain_mask, 0.85), gain_mask)

        # Apply mask
        clean_Zxx = magnitude * gain_mask * np.exp(1j * phase)

        # ISTFT
        _, time_series = signal.istft(clean_Zxx, fs=sr, window=win, nperseg=n_fft, noverlap=n_fft - hop_length)

        # Match length
        if len(time_series) > len(channel_data):
            time_series = time_series[: len(channel_data)]
        elif len(time_series) < len(channel_data):
            time_series = np.pad(time_series, (0, len(channel_data) - len(time_series)))

        dereverbed_channels.append(time_series)

    if is_stereo:
        return np.column_stack(dereverbed_channels)
    return dereverbed_channels[0]


class DereverbProcessor(BaseProcessor):
    """Audio dereverberation processor for removing room reflections and flutter echoes."""

    metadata = ProcessorMetadata(
        id="dereverb",
        name="AI Dereverb",
        description="Removes room reverb tails and early reflections to recover a dry, studio-quality sound.",
        version="1.0.0",
        category="Restoration",
        tags=["dereverb", "reverb-removal", "dry", "room-acoustics"],
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
        """Process a single file: load, run dereverberation, and save."""
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
            on_progress(0.15, "Suppression of room reflections...")

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
            on_progress(0.90, "Exporting dereverbed audio...")

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
                name="amount",
                label="Dereverb Amount",
                type="choice",
                choices=["subtle", "moderate", "aggressive"],
                default="moderate",
                tooltip="Level of reverberation suppression.",
            ),
            ParameterDescriptor(
                name="preserve_warmth",
                label="Preserve Warmth",
                type="bool",
                default=True,
                tooltip="Retains low-mid body below 350Hz to prevent the audio from sounding thin.",
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
        amount = str(options.get("amount", "moderate")).lower()
        preserve_warmth = bool(options.get("preserve_warmth", True))

        if on_progress:
            on_progress(0.3, f"Estimating room reflection tails ({amount})...")

        if cancel_flag and cancel_flag.is_set():
            return audio

        processed = apply_wiener_dereverb(
            audio,
            sr=sr,
            amount=amount,
            preserve_warmth=preserve_warmth,
        )

        return processed.astype(np.float32)


# Self-register
ProcessorRegistry.register(DereverbProcessor)
