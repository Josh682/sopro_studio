#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Prioritize .venv312 containing PySide6 (Python 3.12)
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

if [ -d "$PLUGINS_DIR/platforms" ]; then
    export QT_PLUGIN_PATH="$PLUGINS_DIR"
    export QT_QPA_PLATFORM_PLUGIN_PATH="$PLUGINS_DIR/platforms"
fi

export QT_API=pyside6
exec "$PYTHON_EXEC" "$SCRIPT_DIR/main.py" "$@"
