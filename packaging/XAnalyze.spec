# -*- mode: python ; coding: utf-8 -*-
"""macOS bundle for XAnalyze.

Run from the repository root:

    venv/bin/pyinstaller packaging/XAnalyze.spec --noconfirm

Three things about this build are deliberate.

**QtWebEngine ships.** It is the single largest thing in the bundle by a wide
margin, and it cannot be dropped: it draws the page preview, and it is also the
engine the audit pass injects axe-core and HTML_CodeSniffer into. Excluding it
to make the download smaller would remove two features rather than shrink one.

**Data files keep their repository-relative paths.** `ui/tokens.py` and
`audit/browser.py` both locate their assets from `__file__`, so the design
tokens and the vendored engines are placed at the same relative paths inside the
bundle rather than flattened. That way the frozen app and a `python main.py` run
read the same files by the same code path, and there is no "works from source
only" branch to maintain.

**The keychain backend is named explicitly.** `keyring` picks its backend at
runtime by scanning entry points, which a frozen app has none of, so the macOS
backend has to be imported by name or the app silently falls back to a
plain-text credential file.

**The entry point is `app_entry.py`, not `main.py`.** One frozen executable
serves both the GUI and the `xanalyze` CLI command (installed via a button in
Settings, see `cli_install.py`), told apart at runtime by the name it was
invoked as (see `app_entry.py`'s docstring for why this beats building two
executables and merging them with PyInstaller's `MERGE()`).
"""
import shutil
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).resolve().parent
#: Where PyInstaller writes the build. Needed by the post-build repair below.
DIST = ROOT / "dist"

datas = [
    (str(ROOT / "ui" / "design" / "xformat-tokens.css"), "ui/design"),
    (str(ROOT / "audit" / "vendor" / "axe.min.js"), "audit/vendor"),
    (str(ROOT / "audit" / "vendor" / "HTMLCS.js"), "audit/vendor"),
    (str(ROOT / "audit" / "vendor" / "axe-LICENSE.txt"), "audit/vendor"),
    (str(ROOT / "ui" / "design" / "assets"), "ui/design/assets"),
]

hiddenimports = [
    # Registered by import side effect; PyInstaller follows the package
    # __init__ files, but naming them keeps a future lazy import from
    # quietly dropping a detector or a rule out of the build.
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
        # Nothing here imports these, and each drags in a large Qt module.
        "PySide6.QtQuick3D", "PySide6.QtCharts", "PySide6.QtDataVisualization",
        "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.QtMultimediaWidgets",
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
    name="XAnalyze",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
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
    name="XAnalyze",
)

app = BUNDLE(
    collected,
    name="XAnalyze.app",
    icon=str(ROOT / "packaging" / "XAnalyze.icns"),
    bundle_identifier="net.xformat.xanalyze",
    info_plist={
        "CFBundleName": "XAnalyze",
        "CFBundleDisplayName": "XAnalyze",
        "CFBundleShortVersionString": "0.6.0",
        "CFBundleVersion": "0.6.0",
        # Retina: without this the whole UI renders at 1x and looks blurred.
        "NSHighResolutionCapable": True,
        # The app reaches arbitrary sites the user types in, so it needs
        # ordinary outbound HTTP; nothing here serves or listens.
        "NSAppTransportSecurity": {"NSAllowsArbitraryLoads": True},
        "LSMinimumSystemVersion": "12.0",
    },
)


# --------------------------------------------------------------- post-build

import os

# Create xanalyze CLI copy inside the bundle
macos_dir = DIST / "XAnalyze.app" / "Contents" / "MacOS"
cli_copy = macos_dir / "xanalyze"
gui_exe = macos_dir / "XAnalyze"
if gui_exe.exists() and not cli_copy.exists():
    import shutil
    shutil.copy2(str(gui_exe), str(cli_copy))
    print(f"XAnalyze: created CLI copy at {cli_copy}")


def repair_webengine_framework(framework_root: Path) -> bool:
    """Put `QtWebEngineProcess` back where Qt looks for it.

    PyInstaller flattens `QtWebEngineCore.framework` and drops the helper and
    the Chromium resources into a stray `Versions/Resources/` instead of
    `Versions/A/`. The framework's own `Helpers -> Versions/Current/Helpers`
    symlink is then dangling, and Qt reports:

        The following paths were searched for Qt WebEngine Process ...
        but could not find it.

    The consequence is not cosmetic. Without the helper process, every
    `QWebEngineView` stays blank, so the frozen app loses both the site
    preview and the entire browser audit pass - while a `python main.py` run
    from the checkout works perfectly, which is exactly how this survived a
    previous build being called verified.

    Fixed here rather than in a wrapper script so that building the spec is
    enough on its own.
    """
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
            # Info.plist is written by PyInstaller into A/Resources already;
            # Qt's own copy is the authoritative one for the framework.
            if moved.exists():
                if moved.is_dir():
                    shutil.rmtree(moved)
                else:
                    moved.unlink()
            shutil.move(str(item), str(moved))

    shutil.rmtree(stray, ignore_errors=True)
    return True


FRAMEWORK = "PySide6/Qt/lib/QtWebEngineCore.framework"
for root in (DIST / "XAnalyze" / "_internal" / FRAMEWORK,
             DIST / "XAnalyze.app" / "Contents" / "Frameworks" / FRAMEWORK):
    if repair_webengine_framework(root):
        print(f"XAnalyze: repaired QtWebEngine framework in {root}")

# A build whose browser cannot start is not a build worth shipping, so this is
# checked rather than assumed.
helper = (DIST / "XAnalyze.app" / "Contents" / "Frameworks" / FRAMEWORK
          / "Helpers" / "QtWebEngineProcess.app" / "Contents" / "MacOS"
          / "QtWebEngineProcess")
if not helper.exists():
    raise SystemExit(
        "XAnalyze: QtWebEngineProcess is missing from the bundle - the site "
        "preview and the browser audit pass would both be dead. Expected it "
        f"at {helper}"
    )
