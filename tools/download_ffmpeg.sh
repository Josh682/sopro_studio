#!/bin/bash
set -e

# Setup directories
TOOLS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$TOOLS_DIR")"
BIN_DIR="$ROOT_DIR/assets/bin"

mkdir -p "$BIN_DIR"
cd "$BIN_DIR"

echo "Downloading FFmpeg for macOS..."
curl -L -o ffmpeg.zip https://evermeet.cx/ffmpeg/getrelease/zip

echo "Extracting FFmpeg..."
unzip -o ffmpeg.zip
rm ffmpeg.zip

echo "Downloading FFprobe for macOS..."
curl -L -o ffprobe.zip https://evermeet.cx/ffmpeg/getrelease/ffprobe/zip

echo "Extracting FFprobe..."
unzip -o ffprobe.zip
rm ffprobe.zip

# Make executable
chmod +x ffmpeg ffprobe

echo "Successfully downloaded static FFmpeg and FFprobe to $BIN_DIR"
