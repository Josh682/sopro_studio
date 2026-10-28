"""Audio Metering DSP Engine & Physical Galvanometer Ballistics Simulation.

Implements RMS chunk extraction, True Peak detection, and second-order spring-damper
ballistic needle physics adhering to DESIGN.md Section 6.3 and 6.4.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

from src.ui.qt import QObject, Signal

log = logging.getLogger("sound_processor.audio.metering")


class BallisticNeedle:
    """Second-order spring-damper physical galvanometer needle simulation.
    
    Formula per DESIGN.md Section 6.3:
        theta_target = clip(((VU_dB + 20) / 23) * 80 deg - 40 deg, -40 deg, +40 deg)
        v_{t+1} = (v_t + (theta_target - theta_t) * stiffness) * damping
        theta_{t+1} = theta_t + v_{t+1}
    """

    def __init__(
        self,
        stiffness: float = 0.20,
        damping: float = 0.70,
        min_angle: float = -40.0,
        max_angle: float = 40.0,
        vu_ref_db: float = -18.0,
    ) -> None:
        self.stiffness = float(stiffness)
        self.damping = float(damping)
        self.min_angle = float(min_angle)
        self.max_angle = float(max_angle)
        self.vu_ref_db = float(vu_ref_db)

        self.angle: float = self.min_angle
        self.velocity: float = 0.0

    def reset(self) -> None:
        """Reset needle to resting pin position with zero velocity."""
        self.angle = self.min_angle
        self.velocity = 0.0

    def update(self, dbfs: float) -> float:
        """Step the physics simulation for a given input in dBFS.
        
        Args:
            dbfs: Audio level in decibels relative to full scale (e.g. -18.0).
            
        Returns:
            Current needle angle in degrees [-40.0, +42.0].
        """
        # Convert dBFS to analog VU scale: 0 VU = vu_ref_db (-18 dBFS)
        vu_db = dbfs - self.vu_ref_db

        # Map VU dB (-20 to +3) to physical arc (-40 deg to +40 deg, 80 deg total span)
        if vu_db <= -20.0:
            theta_target = self.min_angle
        elif vu_db >= 3.0:
            theta_target = self.max_angle
        else:
            norm = (vu_db + 20.0) / 23.0
            theta_target = norm * 80.0 - 40.0

        # Physical spring-damper acceleration and velocity integration
        accel = (theta_target - self.angle) * self.stiffness
        self.velocity = (self.velocity + accel) * self.damping
        self.angle += self.velocity

        # Mechanical peg stops: allow slight mechanical overshoot up to +42 deg before settling
        if self.angle < self.min_angle:
            self.angle = self.min_angle
            self.velocity = 0.0
        elif self.angle > self.max_angle + 2.0:
            self.angle = self.max_angle + 2.0
            self.velocity = 0.0

        return self.angle


class AudioMeterEngine(QObject):
    """Real-time audio metering DSP engine.
    
    Processes moving audio chunks around the active playhead, calculates stereo
    RMS & True Peak levels, and drives ballistic galvanometer needle physics.
    """

    levelsUpdated = Signal(float, float, float, float)  # (rms_l_db, rms_r_db, peak_l_db, peak_r_db)
    ballisticsUpdated = Signal(float, float)            # (angle_l_deg, angle_r_deg)
    clipDetected = Signal(bool, bool)                   # (clip_l, clip_r)
    stemLevelsUpdated = Signal(dict)                    # {stem_name: rms_db}

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)

        self._samples: Optional[np.ndarray] = None  # shape (N, 2), float32
        self._sample_rate: int = 44100
        self._duration_sec: float = 0.0

        # Multi-Stem Samples Storage
        self._stem_samples: dict[str, np.ndarray] = {}
        self._stem_sample_rate: int = 44100

        # Independent physical needles for Left and Right channels
        self._needle_l = BallisticNeedle(stiffness=0.20, damping=0.70)
        self._needle_r = BallisticNeedle(stiffness=0.20, damping=0.70)


        # Clip detector state (with 500ms release hold)
        self._clip_hold_sec: float = 0.50
        self._last_clip_time_l: float = -1.0
        self._last_clip_time_r: float = -1.0

        self._current_pos: float = 0.0

    # -------------------------------------------------------------------------
    # Audio Buffer Management
    # -------------------------------------------------------------------------

    def load_file(self, path: Path | str) -> bool:
        """Load audio samples into the metering engine from a file."""
        p = Path(path).resolve()
        if not p.is_file():
            log.warning("AudioMeterEngine: file not found: %s", p)
            return False

        try:
            import soundfile as sf
            data, sr = sf.read(str(p), dtype="float32", always_2d=True)
            self.set_audio_data(data, sr)
            return True
        except Exception as e:
            log.error("AudioMeterEngine: failed to load '%s': %s", p, e)
            return False

    def set_audio_data(self, samples: np.ndarray, sample_rate: int) -> None:
        """Set raw audio samples for metering.
        
        Args:
            samples: 2D array of shape (N, channels) or 1D mono array.
            sample_rate: Sample rate in Hz.
        """
        arr = np.asarray(samples, dtype=np.float32)
        if arr.ndim == 1:
            # Mono to dual stereo
            arr = np.column_stack((arr, arr))
        elif arr.ndim == 2 and arr.shape[1] == 1:
            arr = np.column_stack((arr[:, 0], arr[:, 0]))
        elif arr.ndim == 2 and arr.shape[1] > 2:
            arr = arr[:, :2]  # First two channels

        self._samples = arr
        self._sample_rate = max(1000, int(sample_rate))
        self._duration_sec = float(len(arr)) / float(self._sample_rate)

        self.reset()
        log.info("AudioMeterEngine: loaded %d samples @ %d Hz (%.2fs)", len(arr), self._sample_rate, self._duration_sec)

    def reset(self) -> None:
        """Reset needles and indicators to resting state."""
        self._needle_l.reset()
        self._needle_r.reset()
        self._last_clip_time_l = -1.0
        self._last_clip_time_r = -1.0
        self._current_pos = 0.0

        self.levelsUpdated.emit(-80.0, -80.0, -80.0, -80.0)
        self.ballisticsUpdated.emit(self._needle_l.min_angle, self._needle_r.min_angle)
        self.clipDetected.emit(False, False)
        if self._stem_samples:
            self.stemLevelsUpdated.emit({s: -80.0 for s in self._stem_samples})

    # -------------------------------------------------------------------------
    # Multi-Stem Metering Management
    # -------------------------------------------------------------------------

    def load_stems(self, stem_files: dict[str, Path | str]) -> bool:
        """Load audio buffers for stems from audio files."""
        import soundfile as sf
        stems_dict = {}
        target_sr = 44100
        for name, p in stem_files.items():
            path_obj = Path(p).resolve()
            if path_obj.is_file():
                try:
                    data, sr = sf.read(str(path_obj), dtype="float32", always_2d=True)
                    stems_dict[name.lower()] = data
                    target_sr = sr
                except Exception as e:
                    log.warning("AudioMeterEngine: failed loading stem %s: %s", name, e)

        if not stems_dict:
            return False

        self.set_stem_samples(stems_dict, target_sr)
        return True

    def set_stem_samples(self, stems: dict[str, np.ndarray], sample_rate: int) -> None:
        """Store stem waveform arrays for real-time per-stem RMS calculation."""
        self._stem_samples = stems
        self._stem_sample_rate = max(1000, int(sample_rate))
        self.reset()
        log.info("AudioMeterEngine: loaded %d stems for metering @ %d Hz", len(stems), sample_rate)

    def process_stem_playhead(
        self,
        pos_sec: float,
        stem_gains: Optional[dict[str, float]] = None,
        window_ms: float = 50.0,
    ) -> dict[str, float]:
        """Compute RMS levels in dBFS for each active stem around current playhead.

        Args:
            pos_sec: Current audio playhead in seconds.
            stem_gains: Optional linear gain map {stem_name: gain_float}.
            window_ms: Analysis window in ms.

        Returns:
            Dictionary mapping stem_name to dBFS level.
        """
        if not self._stem_samples:
            return {}

        gains = stem_gains or {}
        half_win_sec = (window_ms / 1000.0) / 2.0
        start_sec = max(0.0, float(pos_sec) - half_win_sec)
        end_sec = float(pos_sec) + half_win_sec

        start_idx = int(start_sec * self._stem_sample_rate)
        end_idx = int(end_sec * self._stem_sample_rate)

        results: dict[str, float] = {}
        for name, samples in self._stem_samples.items():
            gain = max(0.0, float(gains.get(name, 1.0)))
            if gain <= 1e-4 or end_idx <= start_idx or start_idx >= len(samples):
                results[name] = -80.0
                continue

            chunk = samples[start_idx:min(len(samples), end_idx)]
            if len(chunk) == 0:
                results[name] = -80.0
                continue

            # Downmix or mean square
            mean_sq = float(np.mean(chunk ** 2))
            rms = math.sqrt(mean_sq) * gain
            rms_db = 20.0 * math.log10(max(rms, 1e-4))
            results[name] = max(-80.0, min(6.0, rms_db))

        self.stemLevelsUpdated.emit(results)
        return results


    # -------------------------------------------------------------------------
    # Real-time Meter Processing
    # -------------------------------------------------------------------------

    def process_playhead(self, pos_sec: float, window_ms: float = 50.0) -> Tuple[float, float, float, float]:
        """Compute RMS & Peak levels and step ballistic needles for the given playhead time.
        
        Args:
            pos_sec: Current audio position in seconds.
            window_ms: Audio analysis window in milliseconds (default: 50ms).
            
        Returns:
            Tuple of (rms_l_db, rms_r_db, peak_l_db, peak_r_db).
        """
        self._current_pos = max(0.0, float(pos_sec))

        if self._samples is None or len(self._samples) == 0:
            # Silent resting state
            ang_l = self._needle_l.update(-80.0)
            ang_r = self._needle_r.update(-80.0)
            self.levelsUpdated.emit(-80.0, -80.0, -80.0, -80.0)
            self.ballisticsUpdated.emit(ang_l, ang_r)
            self.clipDetected.emit(False, False)
            return -80.0, -80.0, -80.0, -80.0

        # Slice moving window: [pos - window/2, pos + window/2]
        half_win_sec = (window_ms / 1000.0) / 2.0
        start_sec = max(0.0, self._current_pos - half_win_sec)
        end_sec = min(self._duration_sec, self._current_pos + half_win_sec)

        start_idx = int(start_sec * self._sample_rate)
        end_idx = int(end_sec * self._sample_rate)

        if end_idx <= start_idx or start_idx >= len(self._samples):
            chunk = np.zeros((1, 2), dtype=np.float32)
        else:
            chunk = self._samples[start_idx:end_idx]

        # Calculate Left & Right RMS
        mean_sq_l = float(np.mean(chunk[:, 0] ** 2))
        mean_sq_r = float(np.mean(chunk[:, 1] ** 2))

        rms_l = math.sqrt(mean_sq_l)
        rms_r = math.sqrt(mean_sq_r)

        rms_l_db = 20.0 * math.log10(max(rms_l, 1e-5))
        rms_r_db = 20.0 * math.log10(max(rms_r, 1e-5))

        # Calculate True Peak
        peak_l = float(np.max(np.abs(chunk[:, 0]))) if len(chunk) > 0 else 0.0
        peak_r = float(np.max(np.abs(chunk[:, 1]))) if len(chunk) > 0 else 0.0

        peak_l_db = 20.0 * math.log10(max(peak_l, 1e-5))
        peak_r_db = 20.0 * math.log10(max(peak_r, 1e-5))

        # Check clipping threshold (-0.1 dBFS)
        if peak_l_db > -0.1:
            self._last_clip_time_l = self._current_pos
        if peak_r_db > -0.1:
            self._last_clip_time_r = self._current_pos

        clip_l = (self._current_pos - self._last_clip_time_l <= self._clip_hold_sec) and (self._last_clip_time_l >= 0.0)
        clip_r = (self._current_pos - self._last_clip_time_r <= self._clip_hold_sec) and (self._last_clip_time_r >= 0.0)

        # Step ballistic needle physics
        ang_l = self._needle_l.update(rms_l_db)
        ang_r = self._needle_r.update(rms_r_db)

        # Emit live telemetry signals
        self.levelsUpdated.emit(rms_l_db, rms_r_db, peak_l_db, peak_r_db)
        self.ballisticsUpdated.emit(ang_l, ang_r)
        self.clipDetected.emit(clip_l, clip_r)

        return rms_l_db, rms_r_db, peak_l_db, peak_r_db
