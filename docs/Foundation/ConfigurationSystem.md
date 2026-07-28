# Configuration System

The Configuration System manages user settings, application defaults, and model configurations. The implementation is based on Qt's `QSettings` class to ensure cross-platform compatibility.

## Utils Config Module

The `utils/config.py` module wraps `QSettings`, initialized with organization `'SoundProcessor'` and application `'SoundProcessor'`.

## AppConfig Dataclass

The `AppConfig` dataclass defines all available configuration keys and their default values:

```python
from dataclasses import dataclass

@dataclass
class AppConfig:
    output_dir: str = "~/Music/SoundProcessor/Output"
    log_level: str = "INFO"
    theme: str = "catppuccin_mocha"
    ffmpeg_path: str = "" # Auto-detect
    default_format: str = "wav"
    default_sample_rate: int = 44100
    default_bit_depth: int = 24
    default_mp3_bitrate: int = 320
    default_normalize: bool = False
    max_worker_threads: int = 4
    stem_model: str = "mel_band_roformer"
    stem_chunk_size: int = 485100
    stem_overlap: float = 0.1
    stem_model_path: str = ""
```

## Settings Read/Write Operations

The `AppConfig` class provides methods to load and save settings:

- **`AppConfig.load()`**: Reads values from `QSettings`. If a key is missing, it falls back to the default value defined in the dataclass.
- **`AppConfig.save()`**: Writes the current state of the dataclass fields to `QSettings`.

## Per-Processor Configuration

Settings specific to individual processors follow a namespace pattern, prefixing the key with the processor ID.
For example, stem separation settings are prefixed with `stem_separator/`:
- `stem_separator/chunk_size`
- `stem_separator/overlap`

## Migration Strategy

To handle future updates gracefully, the configuration system employs a version-tagged settings approach:
- Settings include a `version` key.
- If an unknown key is encountered, it falls back to defaults.
- For version bumps, specific migration functions are executed during the `load()` process to map old keys to new keys or adjust values format before instantiating `AppConfig`.

## Code Example: AppConfig Implementation

```python
from PyQt6.QtCore import QSettings
from dataclasses import dataclass, fields, asdict
import os

@dataclass
class AppConfig:
    output_dir: str = os.path.expanduser("~/Music/SoundProcessor/Output")
    log_level: str = "INFO"
    theme: str = "catppuccin_mocha"
    ffmpeg_path: str = ""
    default_format: str = "wav"
    default_sample_rate: int = 44100
    default_bit_depth: int = 24
    default_mp3_bitrate: int = 320
    default_normalize: bool = False
    max_worker_threads: int = 4
    stem_model: str = "mel_band_roformer"
    stem_chunk_size: int = 485100
    stem_overlap: float = 0.1
    stem_model_path: str = ""
    
    @classmethod
    def load(cls) -> 'AppConfig':
        settings = QSettings('SoundProcessor', 'SoundProcessor')
        config_data = {}
        
        # Check migration here if version key was implemented
        
        for field in fields(cls):
            if settings.contains(field.name):
                # Type cast based on field type
                val = settings.value(field.name)
                if field.type == bool:
                    val = str(val).lower() == 'true'
                elif field.type == int:
                    val = int(val)
                elif field.type == float:
                    val = float(val)
                config_data[field.name] = val
            else:
                config_data[field.name] = field.default
                
        return cls(**config_data)
        
    def save(self):
        settings = QSettings('SoundProcessor', 'SoundProcessor')
        for key, value in asdict(self).items():
            settings.setValue(key, value)
```
