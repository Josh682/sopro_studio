# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[
        ('assets/bin/ffmpeg', 'assets/bin'),
        ('assets/bin/ffprobe', 'assets/bin'),
    ],
    datas=[
        ('assets', 'assets'),
        ('/opt/homebrew/share/qt/plugins/platforms', 'platforms'),
        ('/opt/homebrew/share/qt/plugins/styles', 'styles'),
        ('/opt/homebrew/share/qt/plugins/multimedia', 'multimedia'),
    ],
    hiddenimports=[
        'qtpy',
        'soundfile',
        'librosa',
        'torch',
        'torchaudio',
        'melband_roformer_infer',
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Sopro Studio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/sopro_studio_logo.png',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Sopro Studio',
)

app = BUNDLE(
    coll,
    name='Sopro Studio.app',
    icon='assets/sopro_studio_logo.png',
    bundle_identifier='com.Josh682.soprostudio',
)
