@echo off
REM HDF5 Viewer - Windows Build Script
REM Requires: Python 3.10+, pip

echo ========================================
echo HDF5 Viewer - Windows Build
echo ========================================

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

REM Install dependencies
echo.
echo Installing dependencies...
pip install PyQt6 h5py numpy pyinstaller
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

REM Clean previous builds
echo.
echo Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM Run tests
echo.
echo Running tests...
python tests/test_core.py
if errorlevel 1 (
    echo ERROR: Core tests failed
    pause
    exit /b 1
)

python tests/test_phase1.py
if errorlevel 1 (
    echo ERROR: Phase1 tests failed
    pause
    exit /b 1
)

python tests/test_final.py
if errorlevel 1 (
    echo ERROR: Final tests failed
    pause
    exit /b 1
)

REM Build with PyInstaller using Windows spec
echo.
echo Building HDF5Viewer.exe...
pyinstaller hdf5viewer_windows.spec --noconfirm

if errorlevel 1 (
    echo ERROR: Build failed
    pause
    exit /b 1
)

REM Create launcher script
echo.
echo Creating launcher...
echo @echo off > dist\HDF5Viewer\HDF5Viewer.bat
echo cd /d "%%~dp0" >> dist\HDF5Viewer\HDF5Viewer.bat
echo start HDF5Viewer.exe %%* >> dist\HDF5Viewer\HDF5Viewer.bat

echo.
echo ========================================
echo Build completed successfully!
echo.
echo Output: dist\HDF5Viewer\HDF5Viewer.exe
echo.
echo To run:
echo   dist\HDF5Viewer\HDF5Viewer.exe [file.h5]
echo.
echo Or double-click:
echo   dist\HDF5Viewer\HDF5Viewer.bat
echo ========================================

pause
