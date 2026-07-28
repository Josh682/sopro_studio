"""FFmpeg-backed audio loading, writing, and metadata probing.

Public re-exports so callers can do::

    from src.audio import load_audio, write_wav, write_mp3, write_flac, write_audio
    from src.audio import probe, AudioInfo
    from src.audio import LoadError, WriteError, ProbeError
"""

from src.audio.loader import LoadError, load_audio
from src.audio.metadata import AudioInfo, ProbeError, probe
from src.audio.writer import WriteError, write_audio, write_flac, write_mp3, write_wav

__all__ = [
    # loader
    "load_audio",
    "LoadError",
    # metadata
    "probe",
    "AudioInfo",
    "ProbeError",
    # writer
    "write_audio",
    "write_wav",
    "write_mp3",
    "write_flac",
    "WriteError",
]
