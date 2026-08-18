from pathlib import Path


workspace = Path.cwd()
icon = workspace / "spacemouse_input" / "assets" / "vibe-6dof.ico"

a = Analysis(
    [str(workspace / "release_main.py")],
    pathex=[str(workspace)],
    binaries=[],
    datas=[
        (str(workspace / "config" / "mapping.json"), "config"),
        (str(workspace / "spacemouse_input" / "assets" / "vibe-6dof.png"), "spacemouse_input/assets"),
        (str(icon), "spacemouse_input/assets"),
    ],
    hiddenimports=["PIL._tkinter_finder"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VibeSpaceMouseBridgeForCodex",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch="x86_64",
    icon=str(icon),
    version=str(workspace / "packaging" / "version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="VibeSpaceMouseBridgeForCodex",
)
