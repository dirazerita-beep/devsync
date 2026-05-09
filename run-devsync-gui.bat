@echo off
setlocal EnableDelayedExpansion
title devsync launcher

REM --- Always work from this script's folder so the launcher works no matter
REM     where it is double-clicked from.
cd /d "%~dp0"

REM --- Find a Python interpreter.
set "PY="
set "PYW="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
where pyw >nul 2>nul && set "PYW=pyw -3"
if not defined PYW (
    where pythonw >nul 2>nul && set "PYW=pythonw"
)

if not defined PY (
    echo.
    echo [ERROR] Python 3.8+ is required but was not found on PATH.
    echo Install Python from https://www.python.org/downloads/ and make sure
    echo "tcl/tk and IDLE" stays checked during the installer's "Optional Features"
    echo step. Then re-run this launcher.
    echo.
    pause
    exit /b 1
)

REM --- First-run check: only install if devsync_gui or ttkbootstrap is missing.
%PY% -c "import devsync, devsync_gui, ttkbootstrap" >nul 2>nul
if errorlevel 1 (
    echo Installing devsync and its dependencies. This only happens the first time...
    %PY% -m pip install --disable-pip-version-check -e .
    if errorlevel 1 (
        echo.
        echo [ERROR] Failed to install dependencies. Scroll up to see the error.
        echo.
        pause
        exit /b 1
    )
)

REM --- Launch the GUI. Use pythonw if available so no console window stays open.
if defined PYW (
    start "" %PYW% -m devsync_gui
) else (
    start "" %PY% -m devsync_gui
)

endlocal
exit /b 0
