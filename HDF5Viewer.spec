# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import os
import sys
from pathlib import Path

# Resolve project root from spec file location (cross-platform)
PROJECT_ROOT = Path(SPECPATH)

# Determine path separator based on OS
sep = ';' if sys.platform == 'win32' else ':'

# Data files
datas = [(str(PROJECT_ROOT / 'config.json'), '.')]
datas += collect_data_files('h5py')
datas += collect_data_files('PyQt6')

# Hidden imports
hiddenimports = collect_submodules('PyQt6')
hiddenimports += [
    'h5py',
    'numpy', 'numpy.core', 'numpy.lib',
    'matplotlib', 'matplotlib.backends.backend_qtagg',
]

a = Analysis(
    [str(PROJECT_ROOT / 'main.py')],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='HDF5Viewer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='HDF5Viewer',
)
