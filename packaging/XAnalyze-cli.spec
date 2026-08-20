# -*- mode: python ; coding: utf-8 -*-
"""CLI build for XAnalyze with browser support.

Run from the repository root:

    venv/bin/pyinstaller packaging/XAnalyze-cli.spec --noconfirm

Produces dist/xanalyze/ directory with executable + dependencies.
QtWebEngine needs to be on disk as separate files to work.
"""
import shutil
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).resolve().parent
DIST = ROOT / "dist"

datas = [
    (str(ROOT / "corpus" / "labelled.jsonl"), "corpus"),
    (str(ROOT / "audit" / "vendor" / "axe.min.js"), "audit/vendor"),
    (str(ROOT / "audit" / "vendor" / "HTMLCS.js"), "audit/vendor"),
    (str(ROOT / "audit" / "vendor" / "axe-LICENSE.txt"), "audit/vendor"),
]

hiddenimports = [
    *collect_submodules("detectors"),
    *collect_submodules("audit"),
    *collect_submodules("llm"),
    "keyring.backends.macOS",
    "keyring.backends.fail",
]

analysis = Analysis(
    [str(ROOT / "app_entry.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "PySide6.QtQuick3D", "PySide6.QtCharts",
        "PySide6.QtDataVisualization", "PySide6.Qt3DCore",
        "PySide6.Qt3DRender", "PySide6.QtMultimediaWidgets",
        "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtSerialPort",
        "PySide6.QtTest", "PySide6.QtDesigner", "tkinter",
    ],
    noarchive=False,
)

pyz = PYZ(analysis.pure)

executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="xanalyze",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

collected = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="xanalyze",
)


# --------------------------------------------------------------- post-build

def repair_webengine_framework(framework_root: Path) -> bool:
    """Put QtWebEngineProcess back where Qt looks for it."""
    stray = framework_root / "Versions" / "Resources"
    if not stray.is_dir():
        return False

    version = framework_root / "Versions" / "A"
    helpers = stray / "Helpers"
    if helpers.is_dir():
        target = version / "Helpers"
        if target.exists():
            shutil.rmtree(target)
        shutil.move(str(helpers), str(target))

    resources = stray / "Resources"
    if resources.is_dir():
        destination = version / "Resources"
        destination.mkdir(parents=True, exist_ok=True)
        for item in resources.iterdir():
            moved = destination / item.name
            if moved.exists():
                if moved.is_dir():
                    shutil.rmtree(moved)
                else:
                    moved.unlink()
            shutil.move(str(item), str(moved))

    shutil.rmtree(stray, ignore_errors=True)
    return True


FRAMEWORK = "PySide6/Qt/lib/QtWebEngineCore.framework"
cli_framework = DIST / "xanalyze" / "_internal" / FRAMEWORK
if cli_framework.exists():
    if repair_webengine_framework(cli_framework):
        print(f"XAnalyze CLI: repaired QtWebEngine framework in {cli_framework}")

    helper = (cli_framework / "Helpers" / "QtWebEngineProcess.app"
              / "Contents" / "MacOS" / "QtWebEngineProcess")
    if not helper.exists():
        raise SystemExit(
            "XAnalyze CLI: QtWebEngineProcess is missing - browser audit "
            f"would not work. Expected at {helper}"
        )
