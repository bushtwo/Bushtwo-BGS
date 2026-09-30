# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('icons', 'icons'), ('Bushtwo BGS 64x64 pixels.png', '.'), ('Bushtwo BGS 32x32 pixels.png', '.'), ('Bushtwo BGS 16 x16 pixels.png', '.'), ('Bushtwo BGS 8 x 8 pixels.png', '.'), ('bushtwo_bgs.ico', '.')],
    hiddenimports=[],
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
    a.binaries,
    a.datas,
    [],
    name='Bushtwo BGS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['bushtwo_bgs.ico'],
)
