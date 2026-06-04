@echo off
REM HDF5 Viewer - Windows Build Script
REM Requires: conda with Python 3.10+
REM
REM All output is logged to build_log.txt in the project directory.

setlocal enabledelayedexpansion

set ENV_NAME=hdf5viewer_build
set TEMP_ENV=0
set SCRIPT_DIR=%~dp0
set LOG_FILE=%SCRIPT_DIR%build_log.txt

REM Ensure we are in the project directory
cd /d "%SCRIPT_DIR%"

REM Initialize log file
echo ======================================== > "%LOG_FILE%"
echo HDF5 Viewer - Windows Build Log >> "%LOG_FILE%"
echo Start time: %date% %time% >> "%LOG_FILE%"
echo ======================================== >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"

echo ========================================
echo HDF5 Viewer - Windows Build
echo ========================================
echo.
echo Logging to: %LOG_FILE%
echo.

REM ========================================
REM Check conda
REM ========================================
echo [CHECK] Looking for conda...
echo [CHECK] Looking for conda... >> "%LOG_FILE%"

where conda >nul 2>&1
if errorlevel 1 (
    echo ERROR: conda not found. Please install Anaconda or Miniconda.
    echo ERROR: conda not found. >> "%LOG_FILE%"
    goto :error
)

echo [CHECK] conda found.
echo [CHECK] conda found. >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"

REM ========================================
REM Step 1: Check or create virtual environment
REM ========================================
echo.
echo [Step 1] Checking virtual environment '%ENV_NAME%'...
echo [Step 1] Checking virtual environment '%ENV_NAME%'... >> "%LOG_FILE%"

conda env list 2>&1 | findstr /C:"%ENV_NAME%" >nul 2>&1
if errorlevel 1 (
    echo [Step 1] Not found. Creating new environment...
    echo [Step 1] Not found. Creating new environment... >> "%LOG_FILE%"
    
    conda create -n %ENV_NAME% python=3.12 -y >> "%LOG_FILE%" 2>&1
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment. See %LOG_FILE%
        echo ERROR: Failed to create virtual environment. >> "%LOG_FILE%"
        goto :error
    )
    set TEMP_ENV=1
    echo [Step 1] Environment '%ENV_NAME%' created.
    echo [Step 1] Environment '%ENV_NAME%' created. >> "%LOG_FILE%"
) else (
    echo [Step 1] Environment '%ENV_NAME%' found. Checking health...
    echo [Step 1] Environment '%ENV_NAME%' found. Checking health... >> "%LOG_FILE%"
    
    conda run -n %ENV_NAME% python --version >> "%LOG_FILE%" 2>&1
    if errorlevel 1 (
        echo [Step 1] Existing env is broken. Recreating...
        echo [Step 1] Existing env is broken. Recreating... >> "%LOG_FILE%"
        
        conda env remove -n %ENV_NAME% -y >> "%LOG_FILE%" 2>&1
        conda create -n %ENV_NAME% python=3.12 -y >> "%LOG_FILE%" 2>&1
        if errorlevel 1 (
            echo ERROR: Failed to recreate virtual environment. See %LOG_FILE%
            echo ERROR: Failed to recreate virtual environment. >> "%LOG_FILE%"
            goto :error
        )
        set TEMP_ENV=1
        echo [Step 1] Environment '%ENV_NAME%' recreated.
        echo [Step 1] Environment '%ENV_NAME%' recreated. >> "%LOG_FILE%"
    ) else (
        echo [Step 1] Environment '%ENV_NAME%' is healthy. Reusing.
        echo [Step 1] Environment '%ENV_NAME%' is healthy. Reusing. >> "%LOG_FILE%"
    )
)

echo. >> "%LOG_FILE%"

REM ========================================
REM Step 2: Install dependencies
REM ========================================
echo.
echo [Step 2] Installing dependencies...
echo [Step 2] Installing dependencies... >> "%LOG_FILE%"

echo [Step 2a] Installing conda packages (numpy, h5py, pyqt6, sip)...
echo [Step 2a] Installing conda packages (numpy, h5py, pyqt6, sip)... >> "%LOG_FILE%"
echo [Step 2a] This may take a few minutes... >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"

conda install -n %ENV_NAME% numpy h5py pyqt=6 pyqt6-sip sip --solver classic -y >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo ERROR: Failed to install conda dependencies. See %LOG_FILE%
    echo ERROR: Failed to install conda dependencies. >> "%LOG_FILE%"
    goto :error
)

echo [Step 2a] Conda packages installed OK.
echo [Step 2a] Conda packages installed OK. >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"

echo [Step 2b] Installing pip packages (matplotlib, pyinstaller)...
echo [Step 2b] Installing pip packages (matplotlib, pyinstaller)... >> "%LOG_FILE%"

conda run -n %ENV_NAME% pip install matplotlib pyinstaller >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo ERROR: Failed to install pip dependencies. See %LOG_FILE%
    echo ERROR: Failed to install pip dependencies. >> "%LOG_FILE%"
    goto :error
)

echo [Step 2b] Pip packages installed OK.
echo [Step 2b] Pip packages installed OK. >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"

REM ========================================
REM Step 3: Clean previous builds
REM ========================================
echo.
echo [Step 3] Cleaning previous builds...
echo [Step 3] Cleaning previous builds... >> "%LOG_FILE%"

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
echo [Step 3] Done.
echo [Step 3] Done. >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"

REM ========================================
REM Step 4: Run tests
REM ========================================
echo.
echo [Step 4] Running tests...
echo [Step 4] Running tests... >> "%LOG_FILE%"

echo [Step 4a] Core tests...
echo [Step 4a] Core tests... >> "%LOG_FILE%"
conda run -n %ENV_NAME% python tests/test_core.py >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo ERROR: Core tests failed. See %LOG_FILE%
    echo ERROR: Core tests failed. >> "%LOG_FILE%"
    goto :error
)

echo [Step 4b] Phase1 tests...
echo [Step 4b] Phase1 tests... >> "%LOG_FILE%"
conda run -n %ENV_NAME% python tests/test_phase1.py >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo ERROR: Phase1 tests failed. See %LOG_FILE%
    echo ERROR: Phase1 tests failed. >> "%LOG_FILE%"
    goto :error
)

echo [Step 4c] Final tests...
echo [Step 4c] Final tests... >> "%LOG_FILE%"
conda run -n %ENV_NAME% python tests/test_final.py >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo ERROR: Final tests failed. See %LOG_FILE%
    echo ERROR: Final tests failed. >> "%LOG_FILE%"
    goto :error
)

echo [Step 4] All tests passed!
echo [Step 4] All tests passed! >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"

REM ========================================
REM Step 5: Build with PyInstaller
REM ========================================
echo.
echo [Step 5] Building HDF5Viewer.exe...
echo [Step 5] Building HDF5Viewer.exe... >> "%LOG_FILE%"

conda run -n %ENV_NAME% pyinstaller HDF5Viewer.spec --noconfirm >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo ERROR: Build failed. See %LOG_FILE%
    echo ERROR: Build failed. >> "%LOG_FILE%"
    goto :error
)

echo [Step 5] Build completed.
echo [Step 5] Build completed. >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"

REM ========================================
REM Step 6: Create launcher script
REM ========================================
echo [Step 6] Creating launcher...
echo [Step 6] Creating launcher... >> "%LOG_FILE%"

echo @echo off > dist\HDF5Viewer\HDF5Viewer.bat
echo cd /d "%%~dp0" >> dist\HDF5Viewer\HDF5Viewer.bat
echo start HDF5Viewer.exe %%* >> dist\HDF5Viewer\HDF5Viewer.bat

echo [Step 6] Done.
echo [Step 6] Done. >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"

REM ========================================
REM Step 7: Cleanup temporary environment
REM ========================================
if "!TEMP_ENV!"=="1" (
    echo [Step 7] Cleaning up temporary environment '%ENV_NAME%'...
    echo [Step 7] Cleaning up temporary environment '%ENV_NAME%'... >> "%LOG_FILE%"
    conda env remove -n %ENV_NAME% -y >> "%LOG_FILE%" 2>&1
    echo [Step 7] Temporary environment removed.
    echo [Step 7] Temporary environment removed. >> "%LOG_FILE%"
) else (
    echo [Step 7] Keeping existing environment '%ENV_NAME%'.
    echo [Step 7] Keeping existing environment '%ENV_NAME%'. >> "%LOG_FILE%"
)

REM ========================================
echo. >> "%LOG_FILE%"
echo End time: %date% %time% >> "%LOG_FILE%"
echo ======================================== >> "%LOG_FILE%"

echo.
echo ========================================
echo Build completed successfully!
echo.
echo Output: dist\HDF5Viewer\HDF5Viewer.exe
echo Log: %LOG_FILE%
echo.
echo To run:
echo   dist\HDF5Viewer\HDF5Viewer.exe [file.h5]
echo.
echo Or double-click:
echo   dist\HDF5Viewer\HDF5Viewer.bat
echo ========================================
goto :end

:error
echo. >> "%LOG_FILE%"
echo Build failed at: %date% %time% >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"
echo.
echo ========================================
echo BUILD FAILED!
echo.
echo Check the log for details:
echo   %LOG_FILE%
echo ========================================

:end
echo.
pause