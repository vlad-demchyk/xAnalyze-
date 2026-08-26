# -*- mode: python ; coding: utf-8 -*-
"""CLI build for XAnalyze with browser support.

Run from the repository root:

    venv/bin/pyinstaller packaging/XAnalyze-cli.spec --noconfirm

Produces dist/xanalyze-cli/ holding the `xanalyze` executable plus its
dependencies. QtWebEngine needs to be on disk as separate files to work.

The folder is `xanalyze-cli` and not `xanalyze` because macOS filesystems are
case-insensitive: `dist/xanalyze` and the window build's `dist/XAnalyze` are
one directory, so building both specs in either order silently destroyed the
first one. The installed shim then pointed at an executable that was no longer
there.
"""
import shutil
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

ROOT = Path(SPECPATH).resolve().parent
# `DISTPATH` is what PyInstaller was actually told to write to, which is
# not always ROOT/"dist": a `--distpath` build would otherwise have the
# post-build check look in an empty folder and pass by finding nothing.
DIST = Path(DISTPATH).resolve()

#: One name, read by the collect and by the post-build check below.
COLLECT_NAME = "xanalyze-cli"

datas = [
    (str(ROOT / "corpus" / "labelled.jsonl"), "corpus"),
    (str(ROOT / "audit" / "vendor" / "axe.min.js"), "audit/vendor"),
    (str(ROOT / "audit" / "vendor" / "HTMLCS.js"), "audit/vendor"),
    (str(ROOT / "audit" / "vendor" / "axe-LICENSE.txt"), "audit/vendor"),
    *collect_data_files("textual"),
]

#: The C2PA reader, when the build environment has it. Optional in
#: `requirements.txt` and optional here for the same reason - but a frozen
#: app has no pip, so for anyone who installs a bundle "optional" would mean
#: "absent forever": the strongest provenance a file can carry would be
#: reported as present-and-unread on every machine. The import lives inside
#: a function (`audit.media._c2pa_module`), which PyInstaller does not
#: follow, so it has to be named. 27 MB against a 1.1 GB bundle.
def _c2pa_bundle():
    try:
        import c2pa
    except Exception:  # noqa: BLE001 - building without it is allowed
        return [], []
    from pathlib import Path as _Path
    package = _Path(c2pa.__file__).parent
    binaries = [(str(lib), "c2pa/c2pa")
                for lib in package.rglob("*.dylib")]
    binaries += [(str(lib), "c2pa/c2pa") for lib in package.rglob("*.so")]
    names = collect_submodules("c2pa") + collect_submodules("cryptography")
    return binaries, names


_C2PA_BINARIES, _C2PA_IMPORTS = _c2pa_bundle()

hiddenimports = [
    *collect_submodules("detectors"),
    *collect_submodules("audit"),
    *collect_submodules("llm"),
    *collect_submodules("tui"),
    *collect_submodules("textual"),
    "keyring.backends.macOS",
    "keyring.backends.fail",
    *_C2PA_IMPORTS,
]

analysis = Analysis(
    [str(ROOT / "app_entry.py")],
    pathex=[str(ROOT)],
    binaries=_C2PA_BINARIES,
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
    # Not "xanalyze": see the module docstring. The executable inside keeps
    # its own name, so what the user types is unchanged.
    name=COLLECT_NAME,
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
cli_framework = DIST / COLLECT_NAME / "_internal" / FRAMEWORK
# Not `if it exists`: a missing framework here means the collect went
# somewhere this check does not know about, and silently passing is how
# a broken browser audit ships.
if True:
    if repair_webengine_framework(cli_framework):
        print(f"XAnalyze CLI: repaired QtWebEngine framework in {cli_framework}")

    helper = (cli_framework / "Helpers" / "QtWebEngineProcess.app"
              / "Contents" / "MacOS" / "QtWebEngineProcess")
    if not helper.exists():
        raise SystemExit(
            "XAnalyze CLI: QtWebEngineProcess is missing - browser audit "
            f"would not work. Expected at {helper}"
        )
