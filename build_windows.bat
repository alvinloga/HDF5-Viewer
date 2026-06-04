@echo off
REM HDF5 Viewer - Windows Build Script
REM Requires: conda with Python 3.10+
REM
REM 逻辑：
REM   1. 检查是否存在 hdf5viewer_build 虚拟环境
REM   2. 存在 → 直接使用
REM   3. 不存在 → 新建环境，标记为临时环境
REM   4. 用该环境安装依赖、跑测试、打包
REM   5. 打包完成后，如果是临时环境则删除

setlocal enabledelayedexpansion

set ENV_NAME=hdf5viewer_build
set TEMP_ENV=0

echo ========================================
echo HDF5 Viewer - Windows Build
echo ========================================

REM Check conda
conda --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: conda not found. Please install Anaconda or Miniconda.
    pause
    exit /b 1
)

REM ========================================
REM Step 1: Check or create virtual environment
REM ========================================
echo.
echo Checking virtual environment...

conda env list | findstr /C:"%ENV_NAME%" >nul 2>&1
if errorlevel 1 (
    echo.
    echo Virtual environment '%ENV_NAME%' not found. Creating new one...
    conda create -n %ENV_NAME% python=3.12 -y
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
    set TEMP_ENV=1
    echo.
    echo Virtual environment '%ENV_NAME%' created.
) else (
    echo.
    echo Virtual environment '%ENV_NAME%' found. Using existing environment.
)

REM Activate the environment
echo.
echo Activating environment '%ENV_NAME%'...
call conda activate %ENV_NAME%
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)

REM ========================================
REM Step 2: Install dependencies
REM ========================================
echo.
echo Installing dependencies...

REM C extensions via conda (avoid pip/conda DLL conflicts)
conda install numpy h5py pyqt=6 pyqt6-sip sip --solver classic -y
if errorlevel 1 (
    echo ERROR: Failed to install conda dependencies
    pause
    exit /b 1
)

REM Pure Python packages via pip
pip install matplotlib pyinstaller
if errorlevel 1 (
    echo ERROR: Failed to install pip dependencies
    pause
    exit /b 1
)

REM ========================================
REM Step 3: Clean previous builds
REM ========================================
echo.
echo Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM ========================================
REM Step 4: Run tests
REM ========================================
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

REM ========================================
REM Step 5: Build with PyInstaller
REM ========================================
echo.
echo Building HDF5Viewer.exe...
pyinstaller HDF5Viewer.spec --noconfirm

if errorlevel 1 (
    echo ERROR: Build failed
    pause
    exit /b 1
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
    call conda deactivate
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

pause
