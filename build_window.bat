@echo off
setlocal EnableExtensions
rem =====================================================================
rem  CAPA Desktop - Windows build script
rem  Produces a single-file executable: dist\CAPA.exe
rem
rem  Requirements (on a Windows PC):
rem    - Python 3.10+ installed from https://www.python.org/downloads/
rem      (keep the "tcl/tk and IDLE" optional feature checked)
rem    - Internet access on first run (pip installs PyInstaller)
rem
rem  Usage: double-click this file, or run build_window.bat in a terminal.
rem =====================================================================

title CAPA Desktop - Windows Build
cd /d "%~dp0"

echo.
echo ============================================================
echo  CAPA Desktop - building Windows executable (dist\CAPA.exe)
echo ============================================================
echo.

rem ---------------------------------------------------------------------
rem 1) Locate a usable Python launcher
rem ---------------------------------------------------------------------
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
    echo [ERROR] Python was not found on this PC.
    echo         Install Python 3.10+ from https://www.python.org/downloads/
    echo         and tick "Add python.exe to PATH" during setup.
    goto :fail
)

echo [1/4] Using interpreter: %PY%
%PY% --version

rem ---------------------------------------------------------------------
rem 2) Ensure PyInstaller is installed (upgrade if already present)
rem ---------------------------------------------------------------------
echo [2/4] Checking / installing PyInstaller...
%PY% -m pip install --disable-pip-version-check --quiet --upgrade pyinstaller
if errorlevel 1 (
    echo [ERROR] Could not install PyInstaller. Check your internet connection.
    goto :fail
)

rem ---------------------------------------------------------------------
rem 3) Clean previous build output
rem ---------------------------------------------------------------------
echo [3/4] Cleaning previous build artifacts...
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

rem ---------------------------------------------------------------------
rem 4) Build the one-file windowed executable
rem    --onefile   : single CAPA.exe (no installer needed)
rem    --windowed  : no console window appears when launched
rem    --name CAPA : output file name
rem    --add-data  : bundles capa_app\assets (icons etc.) into the exe
rem ---------------------------------------------------------------------
echo [4/4] Building CAPA.exe with PyInstaller (this can take a minute)...
%PY% -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --name CAPA ^
    --add-data "capa_app\assets;capa_app\assets" ^
    run.py
if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller build failed. Scroll up for the error message.
    goto :fail
)

if not exist "dist\CAPA.exe" (
    echo [ERROR] Build finished but dist\CAPA.exe is missing.
    goto :fail
)

echo.
echo ============================================================
echo  BUILD SUCCEEDED
echo  Executable: %~dp0dist\CAPA.exe
echo.
echo  You can copy CAPA.exe to any Windows 10/11 PC - no Python
echo  installation is required there. Application data is stored
echo  per-user at: %LOCALAPPDATA%\CAPA\capa.db
echo ============================================================
echo.
if /i "%~1"=="--no-pause" exit /b 0
pause
exit /b 0

:fail
echo.
echo Build aborted.
if /i "%~1"=="--no-pause" exit /b 1
pause
exit /b 1
