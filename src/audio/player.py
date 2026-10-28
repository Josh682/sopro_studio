"""AudioPlayerController - Native Audio Transport Engine.

Manages audio playback, seeking, loop boundaries, and high-precision 60 FPS playhead
tracking using QtMultimedia (QMediaPlayer & QAudioOutput).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from src.ui.qt import (
    QAudioOutput,
    QMediaPlayer,
    QObject,
    QTimer,
    QUrl,
    Signal,
)

log = logging.getLogger("sound_processor.audio.player")


def format_timecode(seconds: float) -> str:
    """Format seconds into MM:SS.cc (minutes:seconds.hundredths).
    
    Example:
        74.5 -> "01:14.50"
        0.0  -> "00:00.00"
    """
    if seconds < 0.0:
        seconds = 0.0
    total_hundredths = int(round(seconds * 100))
    hundredths = total_hundredths % 100
    total_seconds = total_hundredths // 100
    secs = total_seconds % 60
    mins = total_seconds // 60
    return f"{mins:02d}:{secs:02d}.{hundredths:02d}"


class AudioPlayerController(QObject):
    """Native QMediaPlayer controller for previewing audio and driving playhead animation."""

    positionChanged = Signal(float)       # current position in seconds
    durationChanged = Signal(float)       # total file duration in seconds
    stateChanged = Signal(str)            # "playing", "paused", "stopped"
    timecodeUpdated = Signal(str, str)    # current_str, duration_str (e.g. "00:12.45", "03:40.00")
    playbackFinished = Signal()           # emitted when end of file / loop completed
    abSwapped = Signal(str)               # "A" or "B"


    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)

        self._player = QMediaPlayer(self)
        self._audio_out = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_out)

        # High-frequency timer (16.6ms ~ 60 FPS) for smooth playhead animation
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(16)
        self._tick_timer.timeout.connect(self._on_tick)

        self._current_path: Optional[Path] = None
        self._duration_sec: float = 0.0
        self._position_sec: float = 0.0
        self._current_state: str = "stopped"

        # Loop boundary range
        self._is_looping: bool = False
        self._loop_start_sec: float = 0.0
        self._loop_end_sec: float = 0.0

        # A/B Comparison Sources
        self._source_a: Optional[Path] = None
        self._source_b: Optional[Path] = None
        self._active_ab: str = "A"

        # Multi-Stem Playback Engine
        self._stem_paths: dict[str, Path] = {}
        self._stem_players: dict[str, QMediaPlayer] = {}
        self._stem_outputs: dict[str, QAudioOutput] = {}
        self._stem_faders: dict[str, float] = {}  # 0.0 to 2.0 (1.0 = 0dB)
        self._stem_solos: dict[str, bool] = {}
        self._stem_mutes: dict[str, bool] = {}

        # Wire native QMediaPlayer signals
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.playbackStateChanged.connect(self._on_playback_state_changed)
        self._player.mediaStatusChanged.connect(self._on_media_status_changed)

    # -------------------------------------------------------------------------
    # Properties & Status
    # -------------------------------------------------------------------------

    @property
    def is_stem_mode(self) -> bool:
        return bool(self._stem_players)

    @property
    def active_ab(self) -> str:
        return self._active_ab


    @property
    def current_file(self) -> Optional[Path]:
        return self._current_path

    @property
    def duration(self) -> float:
        return self._duration_sec

    @property
    def position(self) -> float:
        return self._position_sec

    @property
    def is_playing(self) -> bool:
        return self._current_state == "playing"

    @property
    def is_paused(self) -> bool:
        return self._current_state == "paused"

    @property
    def is_stopped(self) -> bool:
        return self._current_state == "stopped"

    @property
    def is_looping(self) -> bool:
        return self._is_looping

    # -------------------------------------------------------------------------
    # Transport Control API
    # -------------------------------------------------------------------------

    def load(self, path: Path | str) -> bool:
        """Load an audio file into the player engine."""
        p = Path(path).resolve()
        if not p.is_file():
            log.warning("AudioPlayer: file not found: %s", p)
            return False

        self.stop()
        self._current_path = p

        url = QUrl.fromLocalFile(str(p))
        self._player.setSource(url)

        # Resolve duration immediately using metadata or soundfile fallback
        try:
            from src.audio.metadata import probe
            meta = probe(p)
            if meta and meta.duration > 0:
                self._duration_sec = float(meta.duration)
        except Exception:
            try:
                import soundfile as sf
                info = sf.info(str(p))
                self._duration_sec = float(info.duration)
            except Exception:
                pass

        if self._duration_sec > 0:
            self.durationChanged.emit(self._duration_sec)
            self.timecodeUpdated.emit(format_timecode(0.0), format_timecode(self._duration_sec))

        log.info("AudioPlayer: loaded file '%s' (duration=%.2fs)", p.name, self._duration_sec)
        return True

    def play(self) -> None:
        """Start or resume audio playback."""
        if self._current_path is None:
            return

        # If positioned at or beyond loop end or duration, seek to loop start first
        if self._is_looping and self._loop_end_sec > self._loop_start_sec:
            if self._position_sec >= self._loop_end_sec or self._position_sec < self._loop_start_sec:
                self.seek(self._loop_start_sec)
        elif self._duration_sec > 0 and self._position_sec >= self._duration_sec:
            self.seek(0.0)

        self._current_state = "playing"
        self._player.play()
        for sp in self._stem_players.values():
            sp.play()
        self._tick_timer.start()
        self.stateChanged.emit("playing")

    def pause(self) -> None:
        """Pause audio playback."""
        self._current_state = "paused"
        self._player.pause()
        for sp in self._stem_players.values():
            sp.pause()
        self._tick_timer.stop()
        self.stateChanged.emit("paused")

    def stop(self) -> None:
        """Stop playback and rewind to start or loop start."""
        self._current_state = "stopped"
        self._player.stop()
        for sp in self._stem_players.values():
            sp.stop()
        self._tick_timer.stop()
        rewind_pos = self._loop_start_sec if self._is_looping else 0.0
        self._position_sec = rewind_pos
        self.positionChanged.emit(rewind_pos)
        self.timecodeUpdated.emit(format_timecode(rewind_pos), format_timecode(self._duration_sec))
        self.stateChanged.emit("stopped")

    def toggle_play_pause(self) -> None:
        """Toggle between playing and paused states."""
        if self.is_playing:
            self.pause()
        else:
            self.play()

    def seek(self, seconds: float) -> None:
        """Seek player to absolute time offset in seconds."""
        max_dur = self._duration_sec if self._duration_sec > 0 else 3600.0
        clamped_sec = max(0.0, min(max_dur, float(seconds)))
        self._position_sec = clamped_sec

        target_ms = int(clamped_sec * 1000)
        self._player.setPosition(target_ms)
        for sp in self._stem_players.values():
            sp.setPosition(target_ms)

        self.positionChanged.emit(clamped_sec)
        self.timecodeUpdated.emit(format_timecode(clamped_sec), format_timecode(self._duration_sec))


    def set_loop(self, enabled: bool, start_sec: float = 0.0, end_sec: float = 0.0) -> None:
        """Configure loop state and optional active boundary range."""
        self._is_looping = bool(enabled)
        self._loop_start_sec = max(0.0, float(start_sec))
        self._loop_end_sec = max(self._loop_start_sec, float(end_sec))

    def set_volume(self, level: float) -> None:
        """Set output volume (0.0 to 1.0)."""
        clamped_vol = max(0.0, min(1.0, float(level)))
        self._audio_out.setVolume(clamped_vol)

    def get_timecode(self) -> tuple[str, str]:
        """Return (current_timecode, total_duration_timecode)."""
        return format_timecode(self._position_sec), format_timecode(self._duration_sec)

    # -------------------------------------------------------------------------
    # Before / After (A/B) Comparison Engine
    # -------------------------------------------------------------------------

    def swap_source(self, path: Path | str) -> bool:
        """Seamlessly swap playback source while preserving active playhead position.

        If currently playing, playback continues from the exact same position in the new track.
        """
        p = Path(path).resolve()
        if not p.is_file():
            log.warning("AudioPlayer: swap_source file not found: %s", p)
            return False

        pos = self._position_sec
        was_playing = self.is_playing

        self._current_path = p
        url = QUrl.fromLocalFile(str(p))
        self._player.setSource(url)

        # Restore playhead
        self.seek(pos)
        if was_playing:
            self._player.play()
            self._current_state = "playing"
            self._tick_timer.start()
            self.stateChanged.emit("playing")

        log.info("AudioPlayer: swapped source to '%s' at %.2fs", p.name, pos)
        return True

    def load_ab(self, path_a: Path | str, path_b: Path | str) -> bool:
        """Configure dual A/B comparison tracks and load track A as primary."""
        pa = Path(path_a).resolve()
        pb = Path(path_b).resolve()
        if not pa.is_file() or not pb.is_file():
            return False
        self._source_a = pa
        self._source_b = pb
        self._active_ab = "A"
        res = self.load(pa)
        self.abSwapped.emit("A")
        return res

    def set_ab_mode(self, mode: str) -> bool:
        """Switch between A (Raw) and B (Processed) tracks with playhead preservation."""
        mode_upper = mode.upper()
        if mode_upper not in ("A", "B"):
            return False
        if mode_upper == self._active_ab:
            return True
        target_path = self._source_a if mode_upper == "A" else self._source_b
        if not target_path or not target_path.is_file():
            return False
        self._active_ab = mode_upper
        self.swap_source(target_path)
        self.abSwapped.emit(mode_upper)
        return True

    # -------------------------------------------------------------------------
    # Multi-Stem Mixing & Solo/Mute Engine
    # -------------------------------------------------------------------------

    def load_stems(self, stems: dict[str, Path | str]) -> bool:
        """Load multiple stem audio tracks for synchronized playback and mixing."""
        self.stop()
        self._clear_stems()

        valid_stems: dict[str, Path] = {}
        for name, p in stems.items():
            path_obj = Path(p).resolve()
            if path_obj.is_file():
                valid_stems[name.lower()] = path_obj

        if not valid_stems:
            return False

        # Pick first stem as master clock source
        first_name = next(iter(valid_stems))
        first_path = valid_stems[first_name]
        self.load(first_path)

        for name, path_obj in valid_stems.items():
            sub_player = QMediaPlayer(self)
            sub_out = QAudioOutput(self)
            sub_player.setAudioOutput(sub_out)
            sub_player.setSource(QUrl.fromLocalFile(str(path_obj)))

            self._stem_players[name] = sub_player
            self._stem_outputs[name] = sub_out
            self._stem_paths[name] = path_obj
            self._stem_faders[name] = 1.0  # 0 dB
            self._stem_solos[name] = False
            self._stem_mutes[name] = False

        self._update_stem_volumes()
        log.info("AudioPlayer: loaded %d stems (%s)", len(valid_stems), ", ".join(valid_stems.keys()))
        return True

    def _clear_stems(self) -> None:
        """Clean up stem sub-players."""
        for p in self._stem_players.values():
            p.stop()
            p.deleteLater()
        self._stem_players.clear()
        self._stem_outputs.clear()
        self._stem_paths.clear()
        self._stem_faders.clear()
        self._stem_solos.clear()
        self._stem_mutes.clear()

    def set_stem_fader(self, stem_name: str, gain: float) -> None:
        """Set stem volume fader linear gain (0.0 to 2.0)."""
        name = stem_name.lower()
        if name in self._stem_faders:
            self._stem_faders[name] = max(0.0, min(2.0, float(gain)))
            self._update_stem_volumes()

    def set_stem_solo(self, stem_name: str, solo: bool) -> None:
        """Toggle solo state for a stem."""
        name = stem_name.lower()
        if name in self._stem_solos:
            self._stem_solos[name] = bool(solo)
            self._update_stem_volumes()

    def set_stem_mute(self, stem_name: str, mute: bool) -> None:
        """Toggle mute state for a stem."""
        name = stem_name.lower()
        if name in self._stem_mutes:
            self._stem_mutes[name] = bool(mute)
            self._update_stem_volumes()

    def _update_stem_volumes(self) -> None:
        """Calculate and apply hardware volume for all active stems."""
        any_solo = any(self._stem_solos.values())
        for name, out in self._stem_outputs.items():
            solo = self._stem_solos.get(name, False)
            mute = self._stem_mutes.get(name, False)
            fader = self._stem_faders.get(name, 1.0)

            if mute:
                eff = 0.0
            elif any_solo:
                eff = fader if solo else 0.0
            else:
                eff = fader

            # Clamp output to [0.0, 1.0] for QAudioOutput
            out.setVolume(max(0.0, min(1.0, eff)))

    def get_stem_gains(self) -> dict[str, float]:
        """Return effective linear gains of all stems factoring in Solo and Mute."""
        any_solo = any(self._stem_solos.values())
        gains = {}
        for name in self._stem_faders:
            solo = self._stem_solos.get(name, False)
            mute = self._stem_mutes.get(name, False)
            fader = self._stem_faders.get(name, 1.0)
            if mute:
                gains[name] = 0.0
            elif any_solo:
                gains[name] = fader if solo else 0.0
            else:
                gains[name] = fader
        return gains


    # -------------------------------------------------------------------------
    # Internal Event Handlers
    # -------------------------------------------------------------------------

    def _on_tick(self) -> None:
        """60 FPS timer tick for fluid playhead movement and loop enforcement."""
        if not self.is_playing:
            return

        current_ms = self._player.position()
        pos_sec = current_ms / 1000.0
        self._position_sec = pos_sec

        # Check loop boundary
        if self._is_looping and self._loop_end_sec > self._loop_start_sec:
            if pos_sec >= self._loop_end_sec:
                self.seek(self._loop_start_sec)
                return

        self.positionChanged.emit(pos_sec)
        self.timecodeUpdated.emit(format_timecode(pos_sec), format_timecode(self._duration_sec))

    def _on_position_changed(self, pos_ms: int) -> None:
        """Handle position update from native QtMediaPlayer."""
        pos_sec = pos_ms / 1000.0
        self._position_sec = pos_sec

        if self._is_looping and self._loop_end_sec > self._loop_start_sec:
            if pos_sec >= self._loop_end_sec:
                self.seek(self._loop_start_sec)
                return

        self.positionChanged.emit(pos_sec)
        self.timecodeUpdated.emit(format_timecode(pos_sec), format_timecode(self._duration_sec))

    def _on_duration_changed(self, dur_ms: int) -> None:
        """Handle duration resolved by Qt media decoder."""
        if dur_ms > 0:
            self._duration_sec = dur_ms / 1000.0
            self.durationChanged.emit(self._duration_sec)
            self.timecodeUpdated.emit(format_timecode(self._position_sec), format_timecode(self._duration_sec))

    def _on_playback_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        """Sync internal state when media player status changes."""
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._current_state = "playing"
            self._tick_timer.start()
            self.stateChanged.emit("playing")
        elif state == QMediaPlayer.PlaybackState.PausedState:
            self._current_state = "paused"
            self._tick_timer.stop()
            self.stateChanged.emit("paused")
        else:
            self._current_state = "stopped"
            self._tick_timer.stop()
            self.stateChanged.emit("stopped")

    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        """Handle end-of-media or stream completion."""
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self._is_looping and self._loop_end_sec > self._loop_start_sec:
                self.seek(self._loop_start_sec)
                self.play()
            elif self._is_looping:
                self.seek(0.0)
                self.play()
            else:
                self.stop()
                self.playbackFinished.emit()
