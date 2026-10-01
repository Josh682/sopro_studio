#!/usr/bin/env python3
"""Manual testing script for all 5 V4.0 Audio Enhancement & Repair Features.

Usage:
    .venv/bin/python test_v4_manual.py [path/to/audio_file.wav]
"""

import sys
from pathlib import Path
import soundfile as sf

from src.core.processors.declip_processor import DeclipProcessor
from src.core.processors.denoise_processor import DenoiseProcessor
from src.core.processors.dereverb_processor import DereverbProcessor
from src.core.processors.voice_enhancement_processor import VoiceEnhancementProcessor
from src.core.processors.restoration_processor import AudioRestorationProcessor


def main():
    # Use provided file or default test_sine.wav
    if len(sys.argv) > 1:
        input_path = Path(sys.argv[1])
    else:
        input_path = Path("test_sine.wav")

    if not input_path.exists():
        print(f"Error: File '{input_path}' not found!")
        sys.exit(1)

    output_dir = Path("src/outputs")
    output_dir.mkdir(parents=True, exist_ok=True)

    data, sr = sf.read(str(input_path))
    duration = len(data) / sr if sr else 0
    print("=" * 60)
    print(f"🎵 TESTING V4.0 FEATURES WITH: {input_path.name}")
    print(f"   Sample Rate: {sr} Hz | Duration: {duration:.2f}s | Channels: {1 if data.ndim == 1 else data.shape[1]}")
    print("=" * 60)

    # 1. Declip Repair
    print("\n[1/5] Running Declip Repair (Spline peak reconstruction)...")
    declip = DeclipProcessor()
    out1 = declip.process_file(input_path, output_dir, {"threshold": 0.95})
    print(f"      ✓ Output saved: {out1}")

    # 2. AI Denoise
    print("\n[2/5] Running AI Denoise (Spectral gating)...")
    denoise = DenoiseProcessor()
    out2 = denoise.process_file(input_path, output_dir, {"strength": 0.50, "noise_mode": "general"})
    print(f"      ✓ Output saved: {out2}")

    # 3. AI Dereverb
    print("\n[3/5] Running AI Dereverb (Spectral decay suppression)...")
    dereverb = DereverbProcessor()
    out3 = dereverb.process_file(input_path, output_dir, {"room_size": "medium", "reverberance": 0.50})
    print(f"      ✓ Output saved: {out3}")

    # 4. Voice Enhancement
    print("\n[4/5] Running Voice Enhancement (Broadcast clarity EQ & de-ess)...")
    voice = VoiceEnhancementProcessor()
    out4 = voice.process_file(input_path, output_dir, {"profile": "broadcast", "clarity_boost": 0.60})
    print(f"      ✓ Output saved: {out4}")

    # 5. Audio Restoration Pipeline
    print("\n[5/5] Running Complete Restoration Pipeline (De-click, Dropout, De-clip, Hiss)...")
    restoration = AudioRestorationProcessor()
    out5 = restoration.process_file(input_path, output_dir, {"recording_type": "digital", "restoration_strength": 0.50})
    print(f"      ✓ Output saved: {out5}")

    print("\n" + "=" * 60)
    print(f"✅ ALL 5 V4.0 FEATURES TESTED SUCCESSFULLY!")
    print(f"   Outputs generated in: {output_dir.resolve()}/")
    print("=" * 60)


if __name__ == "__main__":
    main()
