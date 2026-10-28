"""Haptics - Synthesized Mechanical Audio Feedback Engine for Umbra.

Zero-asset procedural mechanical sound synthesis:
- Switch Click: 15ms exponentially damped sine wave at 2.1 kHz (tau = 250 s^-1)
  triggered on tactile button and toggle activation.
- Knob Detent Tick: 6ms micro-burst sine wave at 3.5 kHz (tau = 600 s^-1)
  triggered when rotary knobs cross their center 12 o'clock detent.
All audio is synthesized in-memory via NumPy into 16-bit PCM buffers and played
directly through Qt's low-latency QAudioSink without external WAV files.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

try:
    from src.ui.qt import (
        QAudioFormat,
        QAudioSink,
        QByteArray,
        QBuffer,
        QIODevice,
        QObject,
    )
    from PySide6.QtMultimedia import QMediaDevices
except ImportError:
    try:
        from PyQt6.QtMultimedia import QAudioFormat, QAudioSink, QMediaDevices
        from PyQt6.QtCore import QByteArray, QBuffer, QIODevice, QObject
    except ImportError:
        QAudioFormat = None
        QAudioSink = None
        QMediaDevices = None
        QByteArray = None
        QBuffer = None
        QIODevice = None
        QObject = object

log = logging.getLogger("sound_processor.audio.haptics")


def synthesize_switch_click(
    sample_rate: int = 44100,
    frequency: float = 2100.0,
    duration_sec: float = 0.015,
    decay_rate: float = 250.0,
    amplitude: float = 0.35,
) -> bytes:
    """Synthesize 15ms exponentially damped sine wave switch click."""
    num_samples = int(sample_rate * duration_sec)
    t = np.linspace(0, duration_sec, num_samples, endpoint=False, dtype=np.float32)
    envelope = np.exp(-t * decay_rate).astype(np.float32)
    carrier = np.sin(2.0 * np.pi * frequency * t).astype(np.float32)
    sig = carrier * envelope * amplitude
    pcm16 = (sig * 32767.0).astype(np.int16)
    return pcm16.tobytes()


def synthesize_knob_detent(
    sample_rate: int = 44100,
    frequency: float = 3500.0,
    duration_sec: float = 0.006,
    decay_rate: float = 600.0,
    amplitude: float = 0.25,
) -> bytes:
    """Synthesize 6ms micro-burst sine wave knob detent tick."""
    num_samples = int(sample_rate * duration_sec)
    t = np.linspace(0, duration_sec, num_samples, endpoint=False, dtype=np.float32)
    envelope = np.exp(-t * decay_rate).astype(np.float32)
    carrier = np.sin(2.0 * np.pi * frequency * t).astype(np.float32)
    sig = carrier * envelope * amplitude
    pcm16 = (sig * 32767.0).astype(np.int16)
    return pcm16.tobytes()


class HapticsEngine:
    """Procedural mechanical audio feedback player singleton."""

    _instance: Optional[HapticsEngine] = None

    def __init__(self, sample_rate: int = 44100) -> None:
        self.sample_rate = sample_rate
        self._enabled: bool = True
        self._volume: float = 0.7  # Master haptics volume (0.0 to 1.0)

        # Procedurally synthesize mechanical audio buffers
        self.switch_click_bytes = synthesize_switch_click(sample_rate=self.sample_rate)
        self.knob_detent_bytes = synthesize_knob_detent(sample_rate=self.sample_rate)

        # Audio sink components (initialized lazily or if audio device available)
        self._sink: Optional[QAudioSink] = None
        self._click_buffer: Optional[QBuffer] = None
        self._tick_buffer: Optional[QBuffer] = None
        self._init_audio_sink()

    @classmethod
    def get_instance(cls) -> HapticsEngine:
        """Access global HapticsEngine singleton instance."""
        if cls._instance is None:
            cls._instance = HapticsEngine()
        return cls._instance

    def _init_audio_sink(self) -> None:
        """Initialize low-latency QAudioSink stream."""
        if QAudioSink is None or QAudioFormat is None or QMediaDevices is None:
            return

        try:
            device = QMediaDevices.defaultAudioOutput()
            if not device or device.isNull():
                return

            fmt = QAudioFormat()
            fmt.setSampleRate(self.sample_rate)
            fmt.setChannelCount(1)
            fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)

            self._sink = QAudioSink(device, fmt)
            self._sink.setVolume(self._volume)

            # Pre-allocate QBuffers for click and tick
            click_ba = QByteArray(self.switch_click_bytes)
            self._click_buffer = QBuffer()
            self._click_buffer.setData(click_ba)
            self._click_buffer.open(QIODevice.OpenModeFlag.ReadOnly)

            tick_ba = QByteArray(self.knob_detent_bytes)
            self._tick_buffer = QBuffer()
            self._tick_buffer.setData(tick_ba)
            self._tick_buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        except Exception as e:
            log.debug("Haptics audio sink initialization skipped: %s", e)
            self._sink = None

    # --- Configuration ---

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, val: bool) -> None:
        self._enabled = bool(val)

    @property
    def volume(self) -> float:
        return self._volume

    @volume.setter
    def volume(self, val: float) -> None:
        self._volume = max(0.0, min(1.0, float(val)))
        if self._sink is not None:
            try:
                self._sink.setVolume(self._volume)
            except Exception:
                pass

    # --- Trigger Methods ---

    def play_switch_click(self) -> None:
        """Play 15ms mechanical console switch click."""
        if not self._enabled:
            return
        if self._sink is not None and self._click_buffer is not None:
            try:
                self._click_buffer.seek(0)
                self._sink.stop()
                self._sink.start(self._click_buffer)
            except Exception:
                pass

    def play_knob_detent(self) -> None:
        """Play 6ms mechanical knob center detent tick."""
        if not self._enabled:
            return
        if self._sink is not None and self._tick_buffer is not None:
            try:
                self._tick_buffer.seek(0)
                self._sink.stop()
                self._sink.start(self._tick_buffer)
            except Exception:
                pass


# Global API Conveniences

def get_haptics_engine() -> HapticsEngine:
    """Return the global HapticsEngine instance."""
    return HapticsEngine.get_instance()


def play_switch_click() -> None:
    """Trigger procedural mechanical switch click sound."""
    HapticsEngine.get_instance().play_switch_click()


def play_knob_detent() -> None:
    """Trigger procedural mechanical knob detent tick sound."""
    HapticsEngine.get_instance().play_knob_detent()


def set_haptics_enabled(enabled: bool) -> None:
    """Enable or disable tactile audio feedback globally."""
    HapticsEngine.get_instance().enabled = enabled


def is_haptics_enabled() -> bool:
    """Check if tactile audio feedback is currently enabled."""
    return HapticsEngine.get_instance().enabled


def set_haptics_volume(volume: float) -> None:
    """Set master volume (0.0 to 1.0) for tactile audio feedback."""
    HapticsEngine.get_instance().volume = volume


def get_haptics_volume() -> float:
    """Get current master volume for tactile audio feedback."""
    return HapticsEngine.get_instance().volume
