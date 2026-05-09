@echo off
setlocal EnableDelayedExpansion
title devsync distributable builder

REM ============================================================
REM  build-distributable.bat
REM
REM  One-click builder. Double-click this file to bundle the
REM  devsync GUI into a single Windows executable, placed in the
REM  "Hasil Build" folder. End users can then download / extract
REM  that folder and run devsync-gui.exe with no Python install.
REM ============================================================

cd /d "%~dp0"

REM --- Find a Python interpreter ---------------------------------------
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo.
    echo [ERROR] Python 3.8+ is required but was not found on PATH.
    echo Install Python from https://www.python.org/downloads/ and make sure
    echo "tcl/tk and IDLE" stays checked during the installer's "Optional Features"
    echo step, then re-run this builder.
    echo.
    pause
    exit /b 1
)

REM --- Install build dependencies --------------------------------------
echo.
echo [1/4] Installing build dependencies (PyInstaller + devsync). This can
echo       take a minute on the very first run.
echo.

%PY% -m pip install --disable-pip-version-check --quiet --upgrade pip wheel
if errorlevel 1 (
    echo [ERROR] Failed to upgrade pip / wheel.
    pause
    exit /b 1
)

%PY% -m pip install --disable-pip-version-check --quiet pyinstaller
if errorlevel 1 (
    echo [ERROR] Failed to install pyinstaller.
    pause
    exit /b 1
)

%PY% -m pip install --disable-pip-version-check --quiet -e .
if errorlevel 1 (
    echo [ERROR] Failed to install devsync and its dependencies.
    pause
    exit /b 1
)

REM --- Clean previous build outputs ------------------------------------
echo [2/4] Cleaning previous build outputs.
if exist "Hasil Build" rmdir /s /q "Hasil Build"
if exist "build-cache" rmdir /s /q "build-cache"

REM --- Build with PyInstaller ------------------------------------------
echo.
echo [3/4] Bundling devsync-gui.exe with PyInstaller. This is the slow step.
echo.

%PY% -m PyInstaller ^
    --noconfirm ^
    --windowed ^
    --onefile ^
    --name devsync-gui ^
    --collect-all ttkbootstrap ^
    --collect-all PIL ^
    --hidden-import PIL._tkinter_finder ^
    --distpath "Hasil Build" ^
    --workpath "build-cache" ^
    --specpath "build-cache" ^
    devsync_gui.py
if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller failed. Scroll up for the actual error.
    echo.
    pause
    exit /b 1
)

REM --- Drop a usage note next to the .exe ------------------------------
echo [4/4] Adding "Cara Pakai.txt" so end users know what to do.
if exist "dist-resources\Cara Pakai.txt" (
    copy /Y "dist-resources\Cara Pakai.txt" "Hasil Build\" >nul
)

REM --- Clean intermediate files ----------------------------------------
if exist "build-cache" rmdir /s /q "build-cache"

REM --- Done ------------------------------------------------------------
echo.
echo =====================================================================
echo  Build sukses!
echo.
echo  Output file : "%CD%\Hasil Build\devsync-gui.exe"
echo.
echo  Distribusi  : klik kanan folder "Hasil Build" di File Explorer,
echo                pilih "Send to" -^> "Compressed (zipped) folder",
echo                lalu kirim file zip itu ke user.
echo                User extract zip dan double-click devsync-gui.exe.
echo =====================================================================
echo.
pause
exit /b 0
