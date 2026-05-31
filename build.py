#!/usr/bin/env python3
"""构建脚本 — 打包 HDF5 Viewer"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"

# 版本信息
VERSION = "0.1.0"
APP_NAME = "HDF5Viewer"


def clean():
    """清理构建目录"""
    print("Cleaning build directories...")
    for d in [DIST_DIR, BUILD_DIR]:
        if d.exists():
            shutil.rmtree(d)
    # 清理 .spec 文件
    for spec in PROJECT_ROOT.glob("*.spec"):
        spec.unlink()


def build_linux():
    """构建 Linux 版本"""
    print("=" * 60)
    print("Building Linux version...")
    print("=" * 60)

    # 使用 PyInstaller 打包为目录模式（便于调试）
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--onedir",
        "--windowed",
        "--noconfirm",
        "--clean",
        # 添加隐式导入
        "--hidden-import", "PyQt6.QtWidgets",
        "--hidden-import", "PyQt6.QtCore",
        "--hidden-import", "PyQt6.QtGui",
        "--hidden-import", "h5py",
        "--hidden-import", "numpy",
        "--hidden-import", "numpy.core",
        "--hidden-import", "numpy.lib",
        # 收集 h5py 的数据文件
        "--collect-data", "h5py",
        # 打包配置文件
        "--add-data", f"{PROJECT_ROOT / 'config.json'}:.",
        # 入口文件
        str(PROJECT_ROOT / "main.py"),
    ]

    result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Build failed:\n{result.stderr}")
        return False

    print("Linux build completed successfully!")

    # 创建启动脚本
    launcher = DIST_DIR / APP_NAME / "run.sh"
    launcher.write_text(f"""#!/bin/bash
cd "$(dirname "$0")"
./{APP_NAME} "$@"
""")
    launcher.chmod(0o755)

    print(f"Output: {DIST_DIR / APP_NAME}/")
    return True


def build_windows_spec():
    """创建 Windows 构建的 spec 文件"""
    print("=" * 60)
    print("Windows build spec file already exists: hdf5viewer_windows.spec")
    print("=" * 60)
    print("\nTo build on Windows, run:")
    print("  build_windows.bat")
    print("  or: pyinstaller hdf5viewer_windows.spec")
    return True


def create_portable_package():
    """创建便携版打包"""
    print("=" * 60)
    print("Creating portable package...")
    print("=" * 60)

    portable_dir = DIST_DIR / f"{APP_NAME}-{VERSION}-linux-portable"
    portable_dir.mkdir(parents=True, exist_ok=True)

    # 复制构建产物
    src_dir = DIST_DIR / APP_NAME
    if src_dir.exists():
        shutil.copytree(src_dir, portable_dir / "app", dirs_exist_ok=True)

    # 创建启动脚本
    run_script = portable_dir / "run.sh"
    run_script.write_text(f"""#!/bin/bash
# HDF5 Viewer Portable
cd "$(dirname "$0")/app"
./{APP_NAME} "$@"
""")
    run_script.chmod(0o755)

    # 创建 README
    readme = portable_dir / "README.txt"
    readme.write_text(f"""HDF5 Viewer v{VERSION} - Portable Edition
========================================

Usage:
  ./run.sh [file.h5]

Requirements:
  - Linux x86_64
  - glibc 2.17+
  - X11 or Wayland

Features:
  - VSCode-style interface
  - Multi-tab with Split
  - Large file lazy loading
  - Plugin system

For more info, visit: https://github.com/your-repo/hdf5-viewer
""")

    print(f"Portable package created: {portable_dir}")
    return True


def run_tests():
    """运行测试"""
    print("=" * 60)
    print("Running tests...")
    print("=" * 60)

    tests = [
        "tests/test_core.py",
        "tests/test_phase1.py",
        "tests/test_final.py",
    ]

    for test in tests:
        print(f"\nRunning {test}...")
        result = subprocess.run(
            [sys.executable, test],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"FAILED: {test}")
            print(result.stdout)
            print(result.stderr)
            return False
        else:
            print(f"  PASSED")

    print("\nAll tests passed!")
    return True


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="Build HDF5 Viewer")
    parser.add_argument("--clean", action="store_true", help="Clean build dirs")
    parser.add_argument("--linux", action="store_true", help="Build Linux version")
    parser.add_argument("--windows", action="store_true", help="Create Windows spec")
    parser.add_argument("--portable", action="store_true", help="Create portable package")
    parser.add_argument("--test", action="store_true", help="Run tests")
    parser.add_argument("--all", action="store_true", help="Do everything")

    args = parser.parse_args()

    if args.clean or args.all:
        clean()

    if args.test or args.all:
        if not run_tests():
            sys.exit(1)

    if args.linux or args.all:
        if not build_linux():
            sys.exit(1)

    if args.windows or args.all:
        build_windows_spec()

    if args.portable or args.all:
        create_portable_package()

    if not any([args.clean, args.linux, args.windows, args.portable, args.test, args.all]):
        parser.print_help()


if __name__ == "__main__":
    main()
