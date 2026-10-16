"""Audio Restoration Processor implementing a multi-stage repair pipeline."""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable

import numpy as np
from scipy import signal
from scipy.interpolate import CubicSpline

from src.core.audio_engine import AudioBuffer, AudioEngine
from src.core.exporter import ExportEngine
from src.core.processor_registry import ProcessorRegistry
from src.core.processors.base_processor import (
    BaseProcessor,
    ParameterDescriptor,
    ProcessingMode,
    ProcessorMetadata,
)
from src.core.processors.declip_processor import repair_clipping_spline
from src.core.processors.denoise_processor import spectral_subtraction_denoise
from src.utils.config import AppConfig

log = logging.getLogger("sound_processor.core.processors.restoration")

RECORDING_PROFILES: dict[str, list[str]] = {
    "digital": ["clipping", "digital_glitch", "dropout"],
    "tape": ["tape_hiss", "clipping", "dropout"],
    "vinyl": ["vinyl_crackle", "tape_hiss", "clipping"],
    "broadcast": ["digital_glitch", "clipping", "tape_hiss"],
    "custom": ["clipping", "vinyl_crackle", "tape_hiss", "dropout"],
}


def declick_audio(audio: np.ndarray, sr: int, strength: float = 0.5, preserve_transients: bool = True) -> np.ndarray:
    """Detects impulsive clicks and vinyl crackle using high-pass residual analysis and interpolates."""
    if strength <= 0.05:
        return audio

    is_stereo = (audio.ndim == 2)
    channels = audio.shape[1] if is_stereo else 1
    repaired_channels = []

    # Highpass filter to isolate high-frequency click transients (> 3 kHz)
    b, a = signal.butter(2, min(3000.0, sr / 2.0 - 500.0), btype="highpass", fs=sr)

    for ch in range(channels):
        x = audio[:, ch] if is_stereo else audio
        residual = signal.filtfilt(b, a, x, padtype="even")

        # Click detection threshold based on Median Absolute Deviation (MAD)
        med = np.median(residual)
        mad = np.median(np.abs(residual - med)) + 1e-9
        # Sensitivity: lower threshold = more clicks detected
        k = max(3.5, 9.0 - (strength * 5.0))
        click_mask = np.abs(residual - med) > (k * mad)

        # Protect musical transients: ignore long continuous bursts
        if preserve_transients:
            # A click should be very brief (< 2.5 ms = ~110 samples at 44.1k)
            max_click_samples = int(0.0025 * sr)
        else:
            max_click_samples = int(0.0050 * sr)

        # Find click segments
        starts = np.where(np.diff(click_mask.astype(int)) == 1)[0] + 1
        ends = np.where(np.diff(click_mask.astype(int)) == -1)[0] + 1

        if click_mask[0]:
            starts = np.insert(starts, 0, 0)
        if click_mask[-1]:
            ends = np.append(ends, len(x))

        repaired_x = x.copy()
        for s, e in zip(starts, ends):
            duration = e - s
            if 1 <= duration <= max_click_samples:
                # Interpolate across the click with surrounding context
                ctx = max(4, duration * 2)
                ctx_s = max(0, s - ctx)
                ctx_e = min(len(x), e + ctx)
                v_idx = np.concatenate([np.arange(ctx_s, s), np.arange(e, ctx_e)])
                if len(v_idx) >= 4:
                    cs = CubicSpline(v_idx, x[v_idx], bc_type="natural")
                    repaired_x[s:e] = cs(np.arange(s, e))

        repaired_channels.append(repaired_x)

    if is_stereo:
        return np.column_stack(repaired_channels)
    return repaired_channels[0]


def inpaint_dropouts(audio: np.ndarray, sr: int, max_gap_ms: float = 40.0) -> np.ndarray:
    """Detects brief silent dropouts and inpaints using contextual cubic interpolation."""
    max_gap_samples = int((max_gap_ms / 1000.0) * sr)
    min_gap_samples = int(0.002 * sr)  # at least 2ms of dead zero

    is_stereo = (audio.ndim == 2)
    channels = audio.shape[1] if is_stereo else 1
    repaired_channels = []

    for ch in range(channels):
        x = audio[:, ch] if is_stereo else audio
        is_zero = np.abs(x) < 1e-6

        if not np.any(is_zero):
            repaired_channels.append(x)
            continue

        starts = np.where(np.diff(is_zero.astype(int)) == 1)[0] + 1
        ends = np.where(np.diff(is_zero.astype(int)) == -1)[0] + 1

        if is_zero[0]:
            starts = np.insert(starts, 0, 0)
        if is_zero[-1]:
            ends = np.append(ends, len(x))

        repaired_x = x.copy()
        for s, e in zip(starts, ends):
            gap = e - s
            if min_gap_samples <= gap <= max_gap_samples:
                ctx = min(gap, 64)
                ctx_s = max(0, s - ctx)
                ctx_e = min(len(x), e + ctx)
                v_idx = np.concatenate([np.arange(ctx_s, s), np.arange(e, ctx_e)])
                if len(v_idx) >= 4:
                    cs = CubicSpline(v_idx, x[v_idx], bc_type="natural")
                    repaired_x[s:e] = cs(np.arange(s, e))

        repaired_channels.append(repaired_x)

    if is_stereo:
        return np.column_stack(repaired_channels)
    return repaired_channels[0]


class AudioRestorationProcessor(BaseProcessor):
    """Multi-stage audio restoration pipeline for repairing damaged, clipped, or archival recordings."""

    metadata = ProcessorMetadata(
        id="restoration",
        name="Audio Restoration",
        description="Comprehensive restoration suite repairing digital dropouts, vinyl crackle, clipped peaks, and tape hiss.",
        version="1.0.0",
        category="Restoration",
        tags=["restoration", "repair", "vinyl", "tape", "dropout", "declick"],
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
        """Process a single file: load, run restoration pipeline, and save."""
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
            on_progress(0.15, "Applying multi-stage restoration...")

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
            on_progress(0.90, "Exporting restored audio...")

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
                name="recording_type",
                label="Recording Profile",
                type="choice",
                choices=["digital", "tape", "vinyl", "broadcast", "custom"],
                default="digital",
                tooltip="Selects target artifacts suited to the recording medium.",
            ),
            ParameterDescriptor(
                name="restoration_strength",
                label="Restoration Strength",
                type="float",
                default=0.50,
                min=0.1,
                max=1.0,
                tooltip="Global aggressiveness of artifact suppression.",
            ),
            ParameterDescriptor(
                name="preserve_transients",
                label="Preserve Sharp Transients",
                type="bool",
                default=True,
                tooltip="Protects natural musical attacks from being smoothed over during de-clicking.",
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
        rec_type = str(options.get("recording_type", "digital")).lower()
        strength = float(options.get("restoration_strength", 0.50))
        preserve_transients = bool(options.get("preserve_transients", True))

        artifacts = options.get("target_artifacts")
        if not artifacts:
            artifacts = RECORDING_PROFILES.get(rec_type, RECORDING_PROFILES["digital"])

        processed = audio.copy()

        # Stage 1: De-click / De-crackle (Must be done first before smearing)
        if "vinyl_crackle" in artifacts or "digital_glitch" in artifacts:
            if on_progress:
                on_progress(0.20, f"Stage 1/4: De-clicking & removing impulsive crackle ({strength*100:.0f}%)...")
            if cancel_flag and cancel_flag.is_set():
                return audio
            processed = declick_audio(processed, sr=sr, strength=strength, preserve_transients=preserve_transients)

        # Stage 2: Dropout inpainting
        if "dropout" in artifacts:
            if on_progress:
                on_progress(0.40, "Stage 2/4: Inpainting digital dropouts...")
            if cancel_flag and cancel_flag.is_set():
                return audio
            processed = inpaint_dropouts(processed, sr=sr)

        # Stage 3: De-clipping peak reconstruction
        if "clipping" in artifacts:
            if on_progress:
                on_progress(0.60, "Stage 3/4: Reconstructing clipped waveform peaks...")
            if cancel_flag and cancel_flag.is_set():
                return audio
            if processed.ndim == 2:
                repaired_chs = [repair_clipping_spline(processed[:, ch]) for ch in range(processed.shape[1])]
                processed = np.column_stack(repaired_chs)
            else:
                processed = repair_clipping_spline(processed)

        # Stage 4: Tape Hiss / Broadband Noise Removal
        if "tape_hiss" in artifacts:
            if on_progress:
                on_progress(0.80, f"Stage 4/4: Suppressing tape hiss & broadband noise ({strength*100:.0f}%)...")
            if cancel_flag and cancel_flag.is_set():
                return audio
            processed = spectral_subtraction_denoise(
                processed,
                sr=sr,
                strength=strength * 0.8,
                preserve_high_freq=preserve_transients,
                noise_mode="hiss" if rec_type == "tape" else "general",
            )

        # Normalization safety check
        peak = np.max(np.abs(processed))
        if peak > 0.99:
            processed = processed * (0.95 / peak)

        return processed.astype(np.float32)


# Self-register
ProcessorRegistry.register(AudioRestorationProcessor)
