#!/bin/bash
# Launcher for the Sopro Studio GUI containing V4.0 Enhancement & Repair Tools
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON_EXEC="$SCRIPT_DIR/.venv/bin/python"
elif [ -f "$SCRIPT_DIR/.venv312/bin/python" ]; then
    PYTHON_EXEC="$SCRIPT_DIR/.venv312/bin/python"
else
    PYTHON_EXEC="python3"
fi

echo "Launching Sopro Studio with V4.0 Audio Enhancement & Repair Suite..."
exec "$PYTHON_EXEC" -c "
import sys
from qtpy.QtWidgets import QApplication
from src.gui.main_window import MainWindow

app = QApplication.instance() or QApplication(sys.argv)
win = MainWindow()
win.show()
sys.exit(app.exec())
"
