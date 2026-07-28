#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate

# Guard: make sure pip's PyQt6 is not shadowing the Homebrew version
PYQT6_LOC=$(python -c "import PyQt6; print(PyQt6.__file__)" 2>/dev/null)
if echo "$PYQT6_LOC" | grep -q "site-packages/PyQt6" && ! echo "$PYQT6_LOC" | grep -q "/opt/homebrew/"; then
    echo ""
    echo "⚠️  WARNING: pip-installed PyQt6 detected at: $PYQT6_LOC"
    echo "   This will cause a 'Could not find Qt platform plugin cocoa' crash."
    echo "   Removing it now and using the Homebrew version instead..."
    echo ""
    pip uninstall -y PyQt6 PyQt6-Qt6 PyQt6-sip 2>/dev/null
fi

export QT_API=pyqt6
python main.py
