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
"""
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).resolve().parent

datas = [
    (str(ROOT / "ui" / "design" / "xformat-tokens.css"), "ui/design"),
    (str(ROOT / "audit" / "vendor" / "axe.min.js"), "audit/vendor"),
    (str(ROOT / "audit" / "vendor" / "HTMLCS.js"), "audit/vendor"),
    (str(ROOT / "audit" / "vendor" / "axe-LICENSE.txt"), "audit/vendor"),
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
    [str(ROOT / "main.py")],
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
    icon=None,
    bundle_identifier="net.xformat.xanalyze",
    info_plist={
        "CFBundleName": "XAnalyze",
        "CFBundleDisplayName": "XAnalyze",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "0.1.0",
        # Retina: without this the whole UI renders at 1x and looks blurred.
        "NSHighResolutionCapable": True,
        # The app reaches arbitrary sites the user types in, so it needs
        # ordinary outbound HTTP; nothing here serves or listens.
        "NSAppTransportSecurity": {"NSAllowsArbitraryLoads": True},
        "LSMinimumSystemVersion": "12.0",
    },
)
