#!/usr/bin/env python3
"""HDF5 Viewer - Windows Build Script (Python)

This script is called by build_windows.bat.
All build logic lives here for better error handling and logging.
"""

import subprocess
import sys
import os
import shutil
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
LOG_FILE = PROJECT_ROOT / "build_log.txt"
ENV_NAME = "hdf5viewer_build"
TEMP_ENV = False

# Keep track of start time
START_TIME = time.time()


def log(msg: str):
    """Print to both console and log file."""
    print(msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")
        f.flush()


def run_cmd(cmd: list, description: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run a command, logging output to log file, brief status to console."""
    log(f"\n[{description}] Running: {' '.join(cmd)}")

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*60}\n")
        f.write(f"CMD: {' '.join(cmd)}\n")
        f.write(f"{'='*60}\n")
        f.flush()

        result = subprocess.run(
            cmd,
            stdout=f,
            stderr=subprocess.STDOUT,
            text=True,
        )

    if check and result.returncode != 0:
        log(f"[{description}] FAILED (exit code {result.returncode})")
        raise RuntimeError(f"{description} failed with exit code {result.returncode}")

    log(f"[{description}] OK")
    return result


def main():
    global TEMP_ENV

    # Initialize log
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write("HDF5 Viewer - Windows Build Log\n")
        f.write(f"Start time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 60 + "\n\n")

    log("=" * 60)
    log("HDF5 Viewer - Windows Build")
    log("=" * 60)

    # ========================================
    # Step 1: Check or create virtual environment
    # ========================================
    log("\n[Step 1] Checking virtual environment...")

    env_list = subprocess.run(
        ["conda", "env", "list"],
        capture_output=True, text=True,
    )

    env_exists = ENV_NAME in env_list.stdout

    if env_exists:
        log(f"[Step 1] Environment '{ENV_NAME}' found. Checking health...")

        health_check = subprocess.run(
            ["conda", "run", "-n", ENV_NAME, "python", "--version"],
            capture_output=True, text=True,
        )

        if health_check.returncode != 0:
            log(f"[Step 1] Environment is broken. Recreating...")
            run_cmd(["conda", "env", "remove", "-n", ENV_NAME, "-y"], "Step 1 - Remove broken env")
            run_cmd(["conda", "create", "-n", ENV_NAME, "python=3.12", "-y"], "Step 1 - Create new env")
            TEMP_ENV = True
            log(f"[Step 1] Environment '{ENV_NAME}' recreated.")
        else:
            log(f"[Step 1] Environment '{ENV_NAME}' is healthy. Reusing.")
    else:
        log(f"[Step 1] Environment '{ENV_NAME}' not found. Creating...")
        run_cmd(["conda", "create", "-n", ENV_NAME, "python=3.12", "-y"], "Step 1 - Create env")
        TEMP_ENV = True
        log(f"[Step 1] Environment '{ENV_NAME}' created.")

    # Verify
    run_cmd(["conda", "run", "-n", ENV_NAME, "python", "--version"], "Step 1 - Verify Python")

    # ========================================
    # Step 2: Install dependencies
    # ========================================
    log("\n[Step 2] Installing dependencies...")

    run_cmd(
        ["conda", "install", "-n", ENV_NAME,
         "numpy", "h5py", "pyqt=6", "pyqt6-sip", "sip",
         "--solver", "classic", "-y"],
        "Step 2a - Conda packages (numpy, h5py, pyqt6, sip)",
    )

    run_cmd(
        ["conda", "run", "-n", ENV_NAME, "pip", "install", "matplotlib", "pyinstaller"],
        "Step 2b - Pip packages (matplotlib, pyinstaller)",
    )

    # ========================================
    # Step 3: Clean previous builds
    # ========================================
    log("\n[Step 3] Cleaning previous builds...")

    for d in ["build", "dist"]:
        p = PROJECT_ROOT / d
        if p.exists():
            shutil.rmtree(p)
            log(f"[Step 3] Removed {d}/")

    log("[Step 3] Done.")

    # ========================================
    # Step 4: Run tests
    # ========================================
    log("\n[Step 4] Running tests...")

    for test_file in ["test_core.py", "test_phase1.py", "test_final.py"]:
        test_path = PROJECT_ROOT / "tests" / test_file
        run_cmd(
            ["conda", "run", "-n", ENV_NAME, "python", str(test_path)],
            f"Step 4 - {test_file}",
        )

    log("[Step 4] All tests passed!")

    # ========================================
    # Step 5: Build with PyInstaller
    # ========================================
    log("\n[Step 5] Building HDF5Viewer.exe...")

    run_cmd(
        ["conda", "run", "-n", ENV_NAME, "--cwd", str(PROJECT_ROOT),
         "pyinstaller", str(PROJECT_ROOT / "HDF5Viewer.spec"), "--noconfirm"],
        "Step 5 - PyInstaller build",
    )

    log("[Step 5] Build completed.")

    # ========================================
    # Step 6: Create launcher script
    # ========================================
    log("\n[Step 6] Creating launcher...")

    launcher_dir = PROJECT_ROOT / "dist" / "HDF5Viewer"
    launcher = launcher_dir / "HDF5Viewer.bat"
    launcher.write_text('@echo off\ncd /d "%~dp0"\nstart HDF5Viewer.exe %*\n')

    log("[Step 6] Done.")

    # ========================================
    # Step 7: Cleanup temporary environment
    # ========================================
    if TEMP_ENV:
        log(f"\n[Step 7] Cleaning up temporary environment '{ENV_NAME}'...")
        run_cmd(["conda", "env", "remove", "-n", ENV_NAME, "-y"], "Step 7 - Remove temp env")
        log("[Step 7] Temporary environment removed.")
    else:
        log(f"\n[Step 7] Keeping existing environment '{ENV_NAME}'.")

    # ========================================
    # Done
    # ========================================
    elapsed = time.time() - START_TIME
    log("\n" + "=" * 60)
    log("Build completed successfully!")
    log(f"Output: dist/HDF5Viewer/HDF5Viewer.exe")
    log(f"Log: {LOG_FILE}")
    log(f"Time: {elapsed:.1f}s")
    log("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        elapsed = time.time() - START_TIME
        log("\n" + "=" * 60)
        log(f"BUILD FAILED!")
        log(f"Error: {e}")
        log(f"Log: {LOG_FILE}")
        log(f"Time: {elapsed:.1f}s")
        log("=" * 60)
        sys.exit(1)
