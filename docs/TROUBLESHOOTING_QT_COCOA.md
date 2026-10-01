# Troubleshooting: Resolving macOS Qt Platform Plugin "cocoa" Initialization Errors

> **Target Audience:** Developers, maintainers, and users running or packaging Qt-based Python applications (PySide6 / PyQt6) on macOS (Apple Silicon & Intel).

---

## 1. Problem Overview

When launching the application on macOS via `./run.sh`, `run_app.command`, or `python main.py`:

```console
(.venv) mac@Joshus-Mac sound-processor % ./run.sh
qt.qpa.plugin: Could not find the Qt platform plugin "cocoa" in "/Users/mac/Documents/Developer/Projects/sound-processor/.venv312/lib/python3.12/site-packages/PySide6/Qt/plugins/platforms"
This application failed to start because no Qt platform plugin could be initialized. Reinstalling the application may fix this problem.

zsh: abort      ./run.sh
```

### The Paradox
Checking the reported directory shows that `libqcocoa.dylib` is **physically present**:

```bash
ls -la /Users/mac/Documents/Developer/Projects/sound-processor/.venv312/lib/python3.12/site-packages/PySide6/Qt/plugins/platforms
# Outputs:
# -rwxr-xr-x  1 mac  staff  1896960 Jul 20 23:59 libqcocoa.dylib
# -rwxr-xr-x  1 mac  staff   200464 Jul 20 23:59 libqminimal.dylib
# -rwxr-xr-x  1 mac  staff   300576 Jul 20 23:59 libqoffscreen.dylib
```

Even though the path is valid and `libqcocoa.dylib` exists on disk, Qt aborts with the error above.

---

## 2. Root Cause Analysis

This error stems from one (or a combination) of five root causes on macOS:

### Root Cause 1: macOS File System `UF_HIDDEN` Flag (The Primary Culprit)
* **What happens:** When `pip` extracts the pre-built `PySide6` binary wheel on macOS, or when files are extracted under certain macOS sandbox/security contexts, dynamic libraries (`.dylib`) can be tagged with the BSD `UF_HIDDEN` file flag.
* **Why Qt fails:** Qt's internal plugin discovery engine (`QFactoryLoader` / `QPluginLoader`) iterates plugin directories using `QDir` with default filters (`QDir::NoDotAndDotDot | QDir::AllEntries`). In Qt, standard entry filters **exclude hidden files** (`QDir::Hidden` is omitted). As a result, `QDir` completely skips `libqcocoa.dylib`, treating the directory as empty.
* **Verification:** Run `ls -laO` (the capital `O` flag displays file flags in BSD/macOS `ls`):
  ```bash
  ls -laO .venv312/lib/python3.12/site-packages/PySide6/Qt/plugins/platforms/
  # If affected, you will see 'hidden':
  # -rwxr-xr-x@ 1 mac staff hidden 1896960 Jul 20 23:59 libqcocoa.dylib
  ```

---

### Root Cause 2: Python Version Mismatch & Virtual Environment Fragmentation
* **What happens:** Modern macOS environments (e.g. Homebrew default `python3`) frequently install the newest Python version (e.g., Python 3.14). However, binary wheels for heavy C++ extensions like `PySide6` and `torch` are only compiled and validated for stable Python releases (e.g., Python 3.10 – 3.12).
* **The conflict:** The active shell environment `(.venv)` in the prompt was running Python 3.14 without `PySide6`, while the working `PySide6` installation existed inside `.venv312` (Python 3.12). When a startup script stripped environment variables or invoked mismatched paths, Qt failed to load the runtime libraries.

---

### Root Cause 3: Missing Environment Variables (`QT_PLUGIN_PATH`)
* Qt relies on environment variables or application directory hierarchy to discover plugins. When running scripts using restricted shells or `env -i`, Qt's default path resolution fails to link to the virtual environment's site-packages plugin directory.

---

### Root Cause 4: Pip vs Homebrew PyQt6/PySide6 Shadowing
* If PyQt6 or PySide6 is installed via `pip` inside an environment while another version exists globally in Homebrew (`/opt/homebrew/Cellar/...`), dyld can load mixed symbol definitions. This triggers dynamic linker (`dyld`) aborts or silent plugin load rejections during Cocoa initialization.

---

### Root Cause 5: Frozen PyInstaller Bundles Missing Platform Plugins
* When bundling a standalone macOS `.app` using PyInstaller, `libqcocoa.dylib` is not always copied into the expected bundle frameworks directory unless explicitly defined in `build.spec`.

---

## 3. How It Was Fixed (Permanent Solution)

To ensure this error never happens again and requires zero manual intervention from users, a multi-layer fix was implemented in the repository:

### Fix Layer 1: Automatic `chflags nohidden` in `run.sh`
In [run.sh](file:///Users/mac/Documents/Developer/Projects/sound-processor/run.sh), we automatically detect the Python environment and clear the `UF_HIDDEN` flag from the `PySide6` package before starting the process:

```bash
# Resolve repository root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Prioritize .venv312 (Python 3.12 with PySide6 6.8+)
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
```

---

### Fix Layer 2: Runtime In-Process Flag Clearing in `src/ui/qt.py`
In [src/ui/qt.py](file:///Users/mac/Documents/Developer/Projects/sound-processor/src/ui/qt.py), the application self-heals before importing Qt widgets:

```python
def _fix_pyside6_hidden_flags() -> None:
    """Fix macOS UF_HIDDEN flag on PySide6 .dylib files.

    pip install PySide6 on macOS marks .dylib plugin files with the hidden
    flag (UF_HIDDEN). Qt's QFactoryLoader uses QDir with default filters
    which skip hidden files, so the cocoa platform plugin is invisible
    despite being physically present. We clear the flag recursively.
    """
    try:
        import PySide6
        pyside_dir = Path(PySide6.__file__).parent
        if pyside_dir.is_dir():
            subprocess.run(
                ["chflags", "-R", "nohidden", str(pyside_dir)],
                capture_output=True, timeout=10,
            )
    except Exception:
        pass

_fix_pyside6_hidden_flags()
```

---

### Fix Layer 3: Automatic Interpreter Re-exec in `main.py`
If a user runs `python main.py` directly from an unsupported Python 3.14 environment, [main.py](file:///Users/mac/Documents/Developer/Projects/sound-processor/main.py) detects the absence of PySide6 and seamlessly delegates to `.venv312`:

```python
try:
    from src.ui.qt import QApplication, ...
except ModuleNotFoundError:
    # If neither PySide6 nor PyQt6 is in current interpreter, auto-switch to .venv312
    project_root = Path(__file__).parent.absolute()
    candidate_venvs = [
        project_root / ".venv312" / "bin" / "python",
        project_root / ".venv" / "bin" / "python",
    ]
    for venv_py in candidate_venvs:
        if venv_py.is_file() and sys.executable != str(venv_py):
            res = os.system(f'"{venv_py}" -c "import PySide6" >/dev/null 2>&1')
            if res == 0:
                args = [str(venv_py), str(Path(__file__).resolve())] + sys.argv[1:]
                os.execv(str(venv_py), args)
```

---

### Fix Layer 4: Explicit Plugin Paths in `run_app.command`
In [run_app.command](file:///Users/mac/Documents/Developer/Projects/sound-processor/run_app.command), explicit plugin paths are exported:

```bash
if [ -d "$PLUGINS_DIR/platforms" ]; then
    export QT_PLUGIN_PATH="$PLUGINS_DIR"
    export QT_QPA_PLATFORM_PLUGIN_PATH="$PLUGINS_DIR/platforms"
fi
```

---

## 4. Quick Step-by-Step Recovery Guide (For Any Project Facing This)

If you encounter this error in another project or on a fresh machine, follow this checklist:

### Step 1: Diagnose with `QT_DEBUG_PLUGINS=1`
Run your application with the Qt debug flag to reveal the exact reason why the plugin was rejected:

```bash
QT_DEBUG_PLUGINS=1 ./run.sh
# or
QT_DEBUG_PLUGINS=1 python main.py
```

* If output shows `Checking to see if we can use .../libqcocoa.dylib` followed by an error, it is a dynamic linking/dependency issue.
* If output does **NOT** mention checking `libqcocoa.dylib` at all despite listing the directory, `libqcocoa.dylib` is being ignored due to the `UF_HIDDEN` flag.

### Step 2: Unhide the PySide6 Files
Run the following command in terminal to remove the hidden flag:

```bash
# For a specific venv:
chflags -R nohidden .venv312/lib/python3.12/site-packages/PySide6

# Or dynamically for any active Python interpreter:
python -c "import PySide6, os, subprocess; subprocess.run(['chflags', '-R', 'nohidden', os.path.dirname(PySide6.__file__)])"
```

### Step 3: Verify the Python Environment
Ensure you are using a Python version supported by official Qt wheels (**Python 3.10 to 3.12** on macOS Tahoe/Sequoia/Sonoma):

```bash
# Check version
python3 --version

# If your default is Python 3.14+, create a Python 3.12 environment:
python3.12 -m venv .venv312
source .venv312/bin/activate
pip install -r requirements.txt
```

### Step 4: Verify Plugin Visibility with a One-Liner Test
Test that Cocoa initializes cleanly without launching the full application:

```bash
python -c "from PySide6.QtWidgets import QApplication; app = QApplication([]); print('✅ Qt Cocoa platform plugin loaded successfully!')"
```

---

## 5. Summary Matrix

| Failure Mode | Symptom | Immediate Fix | Repository Prevention |
|---|---|---|---|
| **Hidden Flag (`UF_HIDDEN`)** | `Could not find the Qt platform plugin "cocoa"` even though `libqcocoa.dylib` exists. | `chflags -R nohidden <site-packages>/PySide6` | Included in `run.sh` and `src/ui/qt.py` |
| **Python 3.14 Incompatibility** | `ModuleNotFoundError: No module named 'PySide6'` | Use Python 3.12 (`.venv312`) | `main.py` auto-switches to `.venv312` |
| **Missing Plugin Path** | Qt searches `""` or invalid system directories | Set `export QT_PLUGIN_PATH=...` | Set in `run_app.command` |
| **PyInstaller Bundle Crash** | `Abort trap: 6` on macOS `.app` launch | Add `platforms` & `styles` to `build.spec` | Datas configured in `build.spec` |
