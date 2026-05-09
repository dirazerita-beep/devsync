#!/usr/bin/env bash
# ============================================================
#  build-distributable.sh
#
#  One-click builder for macOS / Linux. Run this script (or
#  double-click it from your file manager) to bundle the
#  devsync GUI into a single executable, placed in the
#  "Hasil Build" folder.
#
#  PyInstaller can only build for the host platform, so:
#    - run on macOS to produce a macOS binary
#    - run on Linux to produce a Linux ELF binary
#  Use build-distributable.bat on Windows to produce .exe.
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# --- Find a Python 3.8+ interpreter -----------------------------------------
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

# --- Install build dependencies --------------------------------------------
echo
echo "[1/4] Installing build dependencies (PyInstaller + devsync)..."
echo

"$PY" -m pip install --disable-pip-version-check --quiet --upgrade pip wheel
"$PY" -m pip install --disable-pip-version-check --quiet pyinstaller
"$PY" -m pip install --disable-pip-version-check --quiet -e .

# --- Clean previous build outputs ------------------------------------------
echo "[2/4] Cleaning previous build outputs."
rm -rf "Hasil Build" build-cache

# --- Build with PyInstaller ------------------------------------------------
echo
echo "[3/4] Bundling devsync-gui with PyInstaller. This is the slow step."
echo

"$PY" -m PyInstaller \
    --noconfirm \
    --windowed \
    --onefile \
    --name devsync-gui \
    --collect-all ttkbootstrap \
    --collect-all PIL \
    --hidden-import PIL._tkinter_finder \
    --distpath "Hasil Build" \
    --workpath "build-cache" \
    --specpath "build-cache" \
    devsync_gui.py

# --- Drop a usage note next to the binary ----------------------------------
echo "[4/4] Adding 'Cara Pakai.txt' so end users know what to do."
if [ -f "dist-resources/Cara Pakai.txt" ]; then
    cp "dist-resources/Cara Pakai.txt" "Hasil Build/"
fi

# --- Clean intermediate files ----------------------------------------------
rm -rf build-cache

# --- Done ------------------------------------------------------------------
cat <<EOF

=====================================================================
 Build sukses!

 Output     : "$SCRIPT_DIR/Hasil Build/devsync-gui"

 Distribusi : zip seluruh folder "Hasil Build" lalu kirim ke user.
              Contoh:
                  cd "$SCRIPT_DIR"
                  zip -r devsync-gui.zip "Hasil Build"

              User extract zip dan double-click devsync-gui (atau
              jalankan ./devsync-gui dari terminal).
=====================================================================

EOF
