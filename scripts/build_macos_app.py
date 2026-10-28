#!/usr/bin/env python3
"""Build macOS Application Bundle for Umbra.

Automates the packaging of Umbra into a native standalone macOS application bundle (Umbra.app):
- Generates assets/icons/umbra.icns from brand assets using sips + iconutil.
- Synthesizes Info.plist with microphone and file access permissions.
- Packages FFmpeg/FFprobe binaries and asset directories.
- Configures PyInstaller spec with hidden imports and Qt frameworks.
- Supports --dry-run for CI/CD environment and configuration verification.
"""

from __future__ import annotations

import argparse
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_NAME = "Umbra"
APP_BUNDLE_ID = "com.soundprocessor.umbra"
APP_VERSION = "2.0.0"


def generate_macos_icon(
    source_png: Optional[Path] = None,
    output_icns: Optional[Path] = None,
) -> bool:
    """Compile multi-resolution .icns icon from source PNG using macOS sips and iconutil."""
    if sys.platform != "darwin":
        print("[INFO] Icon compilation via iconutil is only supported on macOS.")
        return False

    if source_png is None:
        source_png = PROJECT_ROOT / "assets" / "sopro_logo_only.png"
    if output_icns is None:
        output_icns = PROJECT_ROOT / "assets" / "icons" / "umbra.icns"

    if not source_png.is_file():
        print(f"[WARNING] Source icon PNG not found at: {source_png}")
        return False

    output_icns.parent.mkdir(parents=True, exist_ok=True)
    iconset_dir = output_icns.parent / "umbra.iconset"
    iconset_dir.mkdir(parents=True, exist_ok=True)

    sizes = [
        (16, "16x16"),
        (32, "16x16@2x"),
        (32, "32x32"),
        (64, "32x32@2x"),
        (128, "128x128"),
        (256, "128x128@2x"),
        (256, "256x256"),
        (512, "256x256@2x"),
        (512, "512x512"),
        (1024, "512x512@2x"),
    ]

    try:
        for px, name in sizes:
            out_file = iconset_dir / f"icon_{name}.png"
            cmd = ["sips", "-z", str(px), str(px), str(source_png), "--out", str(out_file)]
            subprocess.run(cmd, check=True, capture_output=True)

        # Convert iconset to .icns
        cmd_iconutil = ["iconutil", "-c", "icns", str(iconset_dir), "-o", str(output_icns)]
        subprocess.run(cmd_iconutil, check=True, capture_output=True)
        print(f"[SUCCESS] Compiled macOS icon: {output_icns}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to compile .icns icon: {e}")
        return False
    finally:
        if iconset_dir.exists():
            shutil.rmtree(iconset_dir, ignore_errors=True)


def generate_info_plist_dict() -> Dict[str, Any]:
    """Generate the Info.plist dictionary containing app metadata and macOS permissions."""
    return {
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": "Umbra Audio Processor",
        "CFBundleIdentifier": APP_BUNDLE_ID,
        "CFBundleVersion": APP_VERSION,
        "CFBundleShortVersionString": APP_VERSION,
        "CFBundlePackageType": "APPL",
        "CFBundleExecutable": APP_NAME,
        "CFBundleIconFile": "umbra.icns",
        "NSHighResolutionCapable": True,
        "NSSupportsAutomaticGraphicsSwitching": True,
        "NSMicrophoneUsageDescription": "Umbra requires microphone access for audio monitoring, recording, and real-time DSP analysis.",
        "NSDocumentsFolderUsageDescription": "Umbra requires access to documents to load and save processed audio files.",
    }


def write_info_plist(output_path: Path) -> Path:
    """Write formatted Info.plist XML file to disk."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plist_data = generate_info_plist_dict()
    with open(output_path, "wb") as fp:
        plistlib.dump(plist_data, fp)
    return output_path


def get_pyinstaller_spec_config() -> Dict[str, Any]:
    """Return dictionary of PyInstaller build configuration parameters."""
    main_script = PROJECT_ROOT / "main.py"
    assets_dir = PROJECT_ROOT / "assets"
    ffmpeg_bin = PROJECT_ROOT / "assets" / "bin" / "ffmpeg"
    ffprobe_bin = PROJECT_ROOT / "assets" / "bin" / "ffprobe"
    icon_icns = PROJECT_ROOT / "assets" / "icons" / "umbra.icns"
    models_dir = PROJECT_ROOT / "models"

    datas: List[tuple[str, str]] = []
    if assets_dir.is_dir():
        datas.append((str(assets_dir), "assets"))
    if models_dir.is_dir():
        datas.append((str(models_dir), "models"))

    binaries: List[tuple[str, str]] = []
    if ffmpeg_bin.is_file():
        binaries.append((str(ffmpeg_bin), "."))
    if ffprobe_bin.is_file():
        binaries.append((str(ffprobe_bin), "."))

    hidden_imports = [
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtMultimedia",
        "numpy",
        "scipy",
        "scipy.signal",
        "scipy.io.wavfile",
        "soundfile",
        "librosa",
        "src.core.processors",
        "src.core.processor_registry",
        "src.audio.haptics",
        "src.audio.metering",
        "src.audio.player",
    ]

    return {
        "app_name": APP_NAME,
        "main_script": str(main_script),
        "datas": datas,
        "binaries": binaries,
        "hidden_imports": hidden_imports,
        "icon": str(icon_icns) if icon_icns.is_file() else None,
        "info_plist": generate_info_plist_dict(),
    }


def validate_environment() -> Dict[str, bool]:
    """Check required dependencies and assets for macOS packaging."""
    results = {
        "python_version_ok": sys.version_info >= (3, 10),
        "is_macos": sys.platform == "darwin",
        "main_script_exists": (PROJECT_ROOT / "main.py").is_file(),
        "assets_dir_exists": (PROJECT_ROOT / "assets").is_dir(),
        "ffmpeg_bin_exists": (PROJECT_ROOT / "assets" / "bin" / "ffmpeg").is_file(),
        "ffprobe_bin_exists": (PROJECT_ROOT / "assets" / "bin" / "ffprobe").is_file(),
        "pyinstaller_installed": shutil.which("pyinstaller") is not None,
    }
    return results


def run_dry_run() -> int:
    """Perform dry-run verification: validates assets, permissions, and generates configuration."""
    print("==================================================")
    print("      UMBRA macOS PACKAGING VERIFICATION          ")
    print("==================================================")

    env = validate_environment()
    for k, v in env.items():
        status = "✓ OK" if v else "✗ MISSING / FALSE"
        print(f"  [{status}] {k}")

    # Generate Info.plist in build directory
    build_dir = PROJECT_ROOT / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    plist_path = build_dir / "Info.plist"
    write_info_plist(plist_path)
    print(f"\n[INFO] Generated Info.plist at: {plist_path}")

    cfg = get_pyinstaller_spec_config()
    print(f"[INFO] Main script: {cfg['main_script']}")
    print(f"[INFO] Bundled binaries: {len(cfg['binaries'])} ({', '.join(b[0] for b in cfg['binaries'])})")
    print(f"[INFO] Bundled data dirs: {len(cfg['datas'])}")
    print(f"[INFO] Hidden imports: {len(cfg['hidden_imports'])}")
    print(f"[INFO] App Icon: {cfg['icon']}")

    print("\n[SUCCESS] Dry-run validation completed successfully.")
    return 0


def build_app(clean: bool = False) -> int:
    """Execute full PyInstaller build into native macOS application bundle."""
    if not shutil.which("pyinstaller"):
        print("[ERROR] PyInstaller is not installed in the active environment.")
        print("Please install via: pip install pyinstaller")
        return 1

    # Ensure icon exists
    icon_path = PROJECT_ROOT / "assets" / "icons" / "umbra.icns"
    if not icon_path.is_file():
        generate_macos_icon()

    build_dir = PROJECT_ROOT / "build"
    dist_dir = PROJECT_ROOT / "dist"

    if clean:
        print("[INFO] Cleaning build and dist directories...")
        shutil.rmtree(build_dir, ignore_errors=True)
        shutil.rmtree(dist_dir, ignore_errors=True)

    plist_path = build_dir / "Info.plist"
    write_info_plist(plist_path)

    cfg = get_pyinstaller_spec_config()

    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--windowed",
        f"--name={APP_NAME}",
        f"--osx-bundle-identifier={APP_BUNDLE_ID}",
    ]

    if icon_path.is_file():
        cmd.append(f"--icon={icon_path}")

    for src, dst in cfg["datas"]:
        cmd.append(f"--add-data={src}:{dst}")

    for src, dst in cfg["binaries"]:
        cmd.append(f"--add-binary={src}:{dst}")

    for imp in cfg["hidden_imports"]:
        cmd.append(f"--hidden-import={imp}")

    cmd.append(cfg["main_script"])

    print(f"\n[EXEC] Running PyInstaller command:\n{' '.join(cmd)}\n")
    res = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    return res.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Build macOS Application Bundle for Umbra.")
    parser.add_argument("--dry-run", action="store_true", help="Validate environment and spec without building.")
    parser.add_argument("--generate-icon", action="store_true", help="Compile assets/icons/umbra.icns.")
    parser.add_argument("--build", action="store_true", help="Execute full PyInstaller build.")
    parser.add_argument("--clean", action="store_true", help="Clean build/ and dist/ before build.")

    args = parser.parse_args()

    if args.generate_icon:
        success = generate_macos_icon()
        return 0 if success else 1
    elif args.build:
        return build_app(clean=args.clean)
    else:
        # Default or --dry-run
        return run_dry_run()


if __name__ == "__main__":
    sys.exit(main())
