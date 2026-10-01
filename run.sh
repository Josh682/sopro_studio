#!/bin/bash
set -e

# Resolve repository root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Prioritize .venv312 (Python 3.12 with PySide6 6.8.3)
if [ -f "$SCRIPT_DIR/.venv312/bin/python" ]; then
    PYTHON_EXEC="$SCRIPT_DIR/.venv312/bin/python"
    PLUGINS_DIR="$SCRIPT_DIR/.venv312/lib/python3.12/site-packages/PySide6/Qt/plugins"
elif [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON_EXEC="$SCRIPT_DIR/.venv/bin/python"
    PLUGINS_DIR="$SCRIPT_DIR/.venv312/lib/python3.12/site-packages/PySide6/Qt/plugins"
else
    PYTHON_EXEC="python3"
    PLUGINS_DIR="$SCRIPT_DIR/.venv312/lib/python3.12/site-packages/PySide6/Qt/plugins"
fi

# Fix macOS hidden-flag issue: pip install PySide6 marks .dylib files with
# UF_HIDDEN, causing Qt's QDir (default filters) to skip them during plugin
# discovery. This is idempotent — chflags nohidden on non-hidden files is a no-op.
PYSIDE6_DIR="$(dirname "$PLUGINS_DIR")"
if [ -d "$PYSIDE6_DIR" ]; then
    chflags -R nohidden "$PYSIDE6_DIR" 2>/dev/null || true
fi

export QT_API=pyside6
exec "$PYTHON_EXEC" "$SCRIPT_DIR/main.py" "$@"
