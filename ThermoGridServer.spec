# PyInstaller spec for ThermoGridServer headless build
block_cipher = None

a = Analysis(
    ['server_headless.py'],
    pathex=[],
    binaries=[],
    datas=[('index.html', '.'), ('static', 'static'), ('icons', 'icons')],
    hiddenimports=['anyio','idna','sniffio'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PySide6','PyQt5','tkinter','matplotlib','PIL','numpy','scipy','pydoc','asyncpg'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ThermoGridServer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='icons/app_icon.ico'
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ThermoGridServer'
)
