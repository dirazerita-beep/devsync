#!/usr/bin/env bash
# One-click launcher for the devsync GUI (Linux / macOS).
#
# Usage:
#   1. Make sure this script is executable (only needed once):
#        chmod +x run-devsync-gui.sh
#   2. Double-click it from your file manager, or run it from a terminal:
#        ./run-devsync-gui.sh
#
# Behaviour:
#   - Always runs from this script's folder, no matter where it is launched
#     from.
#   - Detects a usable Python 3 interpreter.
#   - On first launch, installs devsync and its dependencies in editable mode
#     (`pip install -e .`). Subsequent launches skip the install step.
#   - Starts `devsync_gui` in the background so the terminal can close.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# --- Find a Python 3 interpreter --------------------------------------------
PY=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' >/dev/null 2>&1; then
            PY="$candidate"
            break
        fi
    fi
done

if [ -z "$PY" ]; then
    echo
    echo "[ERROR] Python 3.8+ is required but was not found on PATH."
    echo "        Install it via your package manager (e.g. apt, brew) and"
    echo "        make sure the 'tkinter' / 'python3-tk' module is included."
    echo
    read -r -p "Press Enter to close..." _
    exit 1
fi

# --- First-run check: install only when needed ------------------------------
if ! "$PY" -c 'import devsync, devsync_gui, ttkbootstrap' >/dev/null 2>&1; then
    echo "Installing devsync and its dependencies (first run only)..."
    if ! "$PY" -m pip install --disable-pip-version-check -e .; then
        echo
        echo "[ERROR] Failed to install dependencies. Scroll up for details."
        echo
        read -r -p "Press Enter to close..." _
        exit 1
    fi
fi

# --- Launch GUI -------------------------------------------------------------
# Detach from the terminal so closing the terminal does not kill the GUI.
nohup "$PY" -m devsync_gui >/dev/null 2>&1 &
disown >/dev/null 2>&1 || true
exit 0
