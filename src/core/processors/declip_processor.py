"""Declip Processor for reconstructing clipped and flat-topped audio waveforms."""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable

import numpy as np
from scipy.interpolate import CubicSpline

from src.core.processor_registry import ProcessorRegistry
from src.core.processors.base_enhancement_processor import BaseEnhancementProcessor
from src.core.processors.base_processor import ParameterDescriptor, ProcessorMetadata

log = logging.getLogger("sound_processor.core.processors.declip")


def detect_clipping(audio: np.ndarray, threshold: float = 0.99) -> list[tuple[int, int]]:
    """Identifies regions of audio that exceed the clipping threshold.
    
    Returns a list of (start_idx, end_idx) tuples representing clipped regions.
    """
    is_clipped = np.abs(audio) >= threshold
    if not np.any(is_clipped):
        return []

    transitions = np.diff(is_clipped.astype(int))
    starts = np.where(transitions == 1)[0] + 1
    ends = np.where(transitions == -1)[0] + 1

    if is_clipped[0]:
        starts = np.insert(starts, 0, 0)
    if is_clipped[-1]:
        ends = np.append(ends, len(audio))

    return list(zip(starts, ends))


def repair_clipping_spline(
    audio: np.ndarray,
    threshold: float = 0.99,
    context_samples: int = 14,
    max_gap: int = 256,
) -> np.ndarray:
    """Repairs clipped peaks using cubic spline interpolation based on neighboring context."""
    repaired = audio.copy()
    clipped_regions = detect_clipping(audio, threshold)

    for start, end in clipped_regions:
        gap = end - start
        if gap > max_gap:
            # Overly long flat lines cannot be accurately reconstructed via spline
            continue

        ctx_start = max(0, start - context_samples)
        ctx_end = min(len(audio), end + context_samples)

        valid_indices = np.concatenate([np.arange(ctx_start, start), np.arange(end, ctx_end)])
        if len(valid_indices) < 4:
            continue

        valid_values = audio[valid_indices]
        try:
            cs = CubicSpline(valid_indices, valid_values, bc_type="natural")
            missing_indices = np.arange(start, end)
            repaired[missing_indices] = cs(missing_indices)
        except Exception:
            continue

    return repaired


def repair_clipping_ar(
    audio: np.ndarray,
    threshold: float = 0.99,
    order: int = 8,
    context_samples: int = 32,
    max_gap: int = 256,
) -> np.ndarray:
    """Repairs clipped peaks using bidirectional autoregressive linear prediction."""
    repaired = audio.copy()
    clipped_regions = detect_clipping(audio, threshold)

    for start, end in clipped_regions:
        gap = end - start
        if gap > max_gap:
            continue

        # Check before context
        if start >= context_samples:
            past = audio[start - context_samples : start]
            # Simple autocorrelation / Yule-Walker for AR coefficients
            try:
                r = np.correlate(past, past, mode="full")[len(past) - 1 :]
                R = np.empty((order, order))
                for i in range(order):
                    R[i] = r[abs(i - np.arange(order))]
                rhs = r[1 : order + 1]
                coeffs = np.linalg.pinv(R) @ rhs

                # Forward predict
                pred_fwd = np.zeros(gap)
                buf = past[-order:].tolist()
                for i in range(gap):
                    val = sum(c * b for c, b in zip(coeffs, reversed(buf[-order:])))
                    pred_fwd[i] = val
                    buf.append(val)
            except Exception:
                pred_fwd = None
        else:
            pred_fwd = None

        # Check after context
        if end + context_samples <= len(audio):
            future = audio[end : end + context_samples]
            try:
                r = np.correlate(future, future, mode="full")[len(future) - 1 :]
                R = np.empty((order, order))
                for i in range(order):
                    R[i] = r[abs(i - np.arange(order))]
                rhs = r[1 : order + 1]
                coeffs = np.linalg.pinv(R) @ rhs

                # Backward predict
                pred_bwd = np.zeros(gap)
                buf = future[:order].tolist()
                for i in range(gap):
                    val = sum(c * b for c, b in zip(coeffs, buf[:order]))
                    pred_bwd[gap - 1 - i] = val
                    buf.insert(0, val)
            except Exception:
                pred_bwd = None
        else:
            pred_bwd = None

        # Combine predictions or fall back to spline
        missing_indices = np.arange(start, end)
        if pred_fwd is not None and pred_bwd is not None:
            weights = np.linspace(1.0, 0.0, gap)
            repaired[missing_indices] = weights * pred_fwd + (1.0 - weights) * pred_bwd
        elif pred_fwd is not None:
            repaired[missing_indices] = pred_fwd
        elif pred_bwd is not None:
            repaired[missing_indices] = pred_bwd
        else:
            # Fallback to spline
            ctx_start = max(0, start - 10)
            ctx_end = min(len(audio), end + 10)
            v_idx = np.concatenate([np.arange(ctx_start, start), np.arange(end, ctx_end)])
            if len(v_idx) >= 4:
                cs = CubicSpline(v_idx, audio[v_idx], bc_type="natural")
                repaired[missing_indices] = cs(missing_indices)

    return repaired


class DeclipProcessor(BaseEnhancementProcessor):
    """Audio repair processor for reconstructing clipped waveform peaks."""

    metadata = ProcessorMetadata(
        id="declip",
        name="Declip Repair",
        description="Restores clipped audio peaks and harmonic dynamics using Spline and AR interpolation.",
        version="1.0.0",
        category="Restoration",
        tags=["declip", "repair", "distortion", "waveform"],
    )

    @classmethod
    def get_parameter_descriptors(cls) -> list[ParameterDescriptor]:
        return [
            ParameterDescriptor(
                name="threshold",
                label="Threshold",
                type="float",
                default=0.99,
                min=0.80,
                max=1.0,
                tooltip="Detection threshold for digital clipping.",
            ),
            ParameterDescriptor(
                name="algorithm",
                label="Algorithm",
                type="choice",
                choices=["auto", "spline", "ar_model"],
                default="auto",
                tooltip="Algorithm used to reconstruct missing peak curvature.",
            ),
            ParameterDescriptor(
                name="auto_makeup_gain",
                label="Prevent Re-clipping (-3dB)",
                type="bool",
                default=True,
                tooltip="Applies -3dB headroom makeup gain to prevent reconstructed peaks from exceeding 0dBFS.",
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
        threshold = float(options.get("threshold", 0.99))
        algo = str(options.get("algorithm", "auto")).lower()
        auto_gain = bool(options.get("auto_makeup_gain", True))

        is_stereo = (audio.ndim == 2)
        channels = audio.shape[1] if is_stereo else 1

        if on_progress:
            on_progress(0.2, "Scanning for clipped peaks...")

        # Process each channel
        repaired_channels = []
        for ch in range(channels):
            if cancel_flag and cancel_flag.is_set():
                break

            ch_data = audio[:, ch] if is_stereo else audio
            regions = detect_clipping(ch_data, threshold)
            total_clipped = sum(e - s for s, e in regions)
            severity_pct = (total_clipped / len(ch_data)) * 100 if len(ch_data) > 0 else 0

            log.info("Channel %d: %.2f%% clipped samples (%d regions)", ch, severity_pct, len(regions))

            selected_algo = algo
            if selected_algo == "auto":
                selected_algo = "spline" if severity_pct < 5.0 else "ar_model"

            if on_progress:
                on_progress(
                    0.3 + (ch / channels) * 0.4,
                    f"Ch {ch + 1}: Repairing with {selected_algo.upper()} ({severity_pct:.1f}% clipped)...",
                )

            if selected_algo == "spline":
                rep = repair_clipping_spline(ch_data, threshold=threshold)
            else:
                rep = repair_clipping_ar(ch_data, threshold=threshold)

            repaired_channels.append(rep)

        if is_stereo:
            repaired = np.column_stack(repaired_channels)
        else:
            repaired = repaired_channels[0] if repaired_channels else audio

        # Headroom gain
        if auto_gain:
            if on_progress:
                on_progress(0.85, "Applying -3dB headroom gain...")
            repaired = repaired * 0.7079  # -3 dBFS attenuation to ensure no clipping

        return repaired.astype(np.float32)


# Self-register
ProcessorRegistry.register(DeclipProcessor)
