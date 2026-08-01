#!/bin/bash
set -e

echo "Cleaning previous builds..."
rm -rf build dist

echo "Ensuring build dependencies are installed..."
.venv/bin/pip install pyinstaller pillow

echo "Running PyInstaller..."
.venv/bin/pyinstaller build.spec --clean

echo "Build complete! App is located at dist/Sopro Studio.app"
