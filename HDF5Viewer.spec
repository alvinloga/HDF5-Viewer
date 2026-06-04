# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_submodules

datas = [('/home/alvin/Desktop/hdf5-viewer/config.json', '.')]
hiddenimports = ['PyQt6.QtWidgets', 'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.sip', 'h5py', 'numpy', 'numpy.core', 'numpy.lib', 'matplotlib', 'matplotlib.backends.backend_qtagg']
datas += collect_data_files('PyQt6')
datas += collect_data_files('h5py')
datas += collect_data_files('matplotlib')
hiddenimports += collect_submodules('PyQt6')


a = Analysis(
    ['/home/alvin/Desktop/hdf5-viewer/main.py'],
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
