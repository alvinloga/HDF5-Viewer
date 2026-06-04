@echo off
REM HDF5 Viewer - Windows Build Launcher
REM Delegates to build_windows.py for full logging and error handling

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

echo ========================================
echo HDF5 Viewer - Windows Build
echo ========================================
echo.
echo All output is logged to build_log.txt
echo.

REM Check conda
where conda >nul 2>&1
if errorlevel 1 (
    echo ERROR: conda not found. Please install Anaconda or Miniconda.
    pause
    exit /b 1
)

REM Run the Python build script with base conda Python
python build_windows.py

if errorlevel 1 (
    echo.
    echo ========================================
    echo BUILD FAILED! Check build_log.txt for details.
    echo ========================================
) else (
    echo.
    echo ========================================
    echo Build completed! Check build_log.txt for details.
    echo ========================================
)

echo.
pause
