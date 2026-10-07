# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec. Run from the repo root:

    pyinstaller packaging/pyinstaller.spec

Produces a one-dir build at dist/RVTripVisualizer/ - packaging/windows/
setup.iss and packaging/linux/build_appimage.sh both wrap that folder into
an installer.
"""
import sys
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent
SRC = ROOT / "src"
ASSETS = SRC / "rv_trip_visualizer" / "assets"
ICON_ICO = ROOT / "packaging" / "icons" / "icon.ico"

a = Analysis(
    [str(SRC / "rv_trip_visualizer" / "__main__.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=[(str(ASSETS), "rv_trip_visualizer/assets")],
    hiddenimports=["shapely", "openpyxl"],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RVTripVisualizer",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(ICON_ICO) if sys.platform == "win32" else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="RVTripVisualizer",
)
