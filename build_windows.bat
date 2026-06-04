@echo off
REM HDF5 Viewer - Windows Build Script
REM Requires: conda with Python 3.10+

setlocal enabledelayedexpansion

set ENV_NAME=hdf5viewer_build
set TEMP_ENV=0
set SCRIPT_DIR=%~dp0

REM Ensure we are in the project directory
cd /d "%SCRIPT_DIR%"

echo ========================================
echo HDF5 Viewer - Windows Build
echo ========================================

REM Check conda
where conda >nul 2>&1
if errorlevel 1 (
    echo ERROR: conda not found. Please install Anaconda or Miniconda.
    goto :error
)

echo.
echo conda found. Proceeding...

REM ========================================
REM Step 1: Check or create virtual environment
REM ========================================
echo.
echo Checking virtual environment '%ENV_NAME%'...

conda env list 2>nul | findstr /C:"%ENV_NAME%" >nul 2>&1
if errorlevel 1 (
    echo.
    echo Virtual environment '%ENV_NAME%' not found. Creating new one...
    conda create -n %ENV_NAME% python=3.12 -y
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        goto :error
    )
    set TEMP_ENV=1
    echo.
    echo Virtual environment '%ENV_NAME%' created.
) else (
    echo.
    echo Virtual environment '%ENV_NAME%' found.
    echo Checking if it has a valid Python...
    conda run -n %ENV_NAME% python --version >nul 2>&1
    if errorlevel 1 (
        echo.
        echo WARNING: Existing env '%ENV_NAME%' is broken. Recreating...
        conda env remove -n %ENV_NAME% -y
        conda create -n %ENV_NAME% python=3.12 -y
        if errorlevel 1 (
            echo ERROR: Failed to recreate virtual environment
            goto :error
        )
        set TEMP_ENV=1
        echo.
        echo Virtual environment '%ENV_NAME%' recreated.
    ) else (
        echo Existing env '%ENV_NAME%' is healthy. Reusing it.
    )
)

echo.
echo Verifying environment...
conda run -n %ENV_NAME% python --version

REM ========================================
REM Step 2: Install dependencies
REM ========================================
echo.
echo ========================================
echo Step 2: Installing dependencies...
echo ========================================

echo.
echo [2a] Installing conda packages (numpy, h5py, pyqt6, sip)...
echo This may take a few minutes. Please wait...
echo.

conda install -n %ENV_NAME% numpy h5py pyqt=6 pyqt6-sip sip --solver classic --no-update-deps -y
if errorlevel 1 (
    echo ERROR: Failed to install conda dependencies
    goto :error
)

echo.
echo [2a] Conda packages installed OK.
echo.

echo [2b] Installing pip packages (matplotlib, pyinstaller)...
echo.

conda run -n %ENV_NAME% pip install matplotlib pyinstaller
if errorlevel 1 (
    echo ERROR: Failed to install pip dependencies
    goto :error
)

echo.
echo [2b] Pip packages installed OK.
echo.

REM ========================================
REM Step 3: Clean previous builds
REM ========================================
echo.
echo ========================================
echo Step 3: Cleaning previous builds...
echo ========================================

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
echo Done.

REM ========================================
REM Step 4: Run tests
REM ========================================
echo.
echo ========================================
echo Step 4: Running tests...
echo ========================================

echo.
echo [4a] Core tests...
conda run -n %ENV_NAME% python tests/test_core.py
if errorlevel 1 (
    echo ERROR: Core tests failed
    goto :error
)

echo.
echo [4b] Phase1 tests...
conda run -n %ENV_NAME% python tests/test_phase1.py
if errorlevel 1 (
    echo ERROR: Phase1 tests failed
    goto :error
)

echo.
echo [4c] Final tests...
conda run -n %ENV_NAME% python tests/test_final.py
if errorlevel 1 (
    echo ERROR: Final tests failed
    goto :error
)

echo.
echo All tests passed!

REM ========================================
REM Step 5: Build with PyInstaller
REM ========================================
echo.
echo ========================================
echo Step 5: Building HDF5Viewer.exe...
echo ========================================
echo.

conda run -n %ENV_NAME% pyinstaller HDF5Viewer.spec --noconfirm

if errorlevel 1 (
    echo ERROR: Build failed
    goto :error
)

REM ========================================
REM Step 6: Create launcher script
REM ========================================
echo.
echo Creating launcher...
echo @echo off > dist\HDF5Viewer\HDF5Viewer.bat
echo cd /d "%%~dp0" >> dist\HDF5Viewer\HDF5Viewer.bat
echo start HDF5Viewer.exe %%* >> dist\HDF5Viewer\HDF5Viewer.bat

REM ========================================
REM Step 7: Cleanup temporary environment
REM ========================================
if "!TEMP_ENV!"=="1" (
    echo.
    echo Cleaning up temporary environment '%ENV_NAME%'...
    conda env remove -n %ENV_NAME% -y
    echo Temporary environment removed.
) else (
    echo.
    echo Keeping existing environment '%ENV_NAME%'.
)

REM ========================================
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
goto :end

:error
echo.
echo ========================================
echo BUILD FAILED! Check the error messages above.
echo ========================================

:end
echo.
pause