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

        # Wire native QMediaPlayer signals
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.playbackStateChanged.connect(self._on_playback_state_changed)
        self._player.mediaStatusChanged.connect(self._on_media_status_changed)

    # -------------------------------------------------------------------------
    # Properties & Status
    # -------------------------------------------------------------------------

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
        self._tick_timer.start()
        self.stateChanged.emit("playing")

    def pause(self) -> None:
        """Pause audio playback."""
        self._current_state = "paused"
        self._player.pause()
        self._tick_timer.stop()
        self.stateChanged.emit("paused")

    def stop(self) -> None:
        """Stop playback and rewind to start or loop start."""
        self._current_state = "stopped"
        self._player.stop()
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
