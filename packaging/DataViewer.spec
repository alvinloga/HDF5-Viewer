# -*- mode: python ; coding: utf-8 -*-
"""Data Viewer PyInstaller spec for Windows and Linux CI artifacts."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


PROJECT_ROOT = Path(SPECPATH).parent
ENTRYPOINT = PROJECT_ROOT / "tools" / "pyinstaller_entry.py"

datas = []
datas += collect_data_files("data_viewer.plugins.builtin")
datas += collect_data_files("data_viewer.workspace.schema")
datas += collect_data_files("PyQt6")
datas += collect_data_files("matplotlib")

hiddenimports = []
hiddenimports += collect_submodules("PyQt6")
hiddenimports += collect_submodules("matplotlib.backends")
hiddenimports += collect_submodules("data_viewer.plugins.builtin")
hiddenimports += [
    "h5py",
    "jsonschema",
    "nibabel",
    "numpy",
    "openpyxl",
    "pandas",
    "platformdirs",
    "scipy",
    "yaml",
]

a = Analysis(
    [str(ENTRYPOINT)],
    pathex=[str(PROJECT_ROOT)],
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
    name="DataViewer",
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
    name="DataViewer",
)
