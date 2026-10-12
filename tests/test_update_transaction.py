"""An unsuccessful update must preserve the installed app and report failure."""
import asyncio
import plistlib
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from textual.widgets import Button, Label

import updater
from tui.app import XAnalyzeApp
from tui.screens.update import UpdateScreen


def bundle(path, content):
    executable = path / "Contents/MacOS/XAnalyze"
    executable.parent.mkdir(parents=True)
    executable.write_text(content)
    (path / "Contents/Info.plist").write_bytes(plistlib.dumps({
        "CFBundlePackageType": "APPL", "CFBundleExecutable": "XAnalyze",
    }))
    return path


@pytest.mark.parametrize("failure", ["none", "stage", "install", "rollback", "invalid"])
def test_bundle_transaction(tmp_path, monkeypatch, failure):
    old = bundle(tmp_path / "installed/XAnalyze.app", "old")
    new = bundle(tmp_path / "download/XAnalyze.app", "new")
    rename = Path.rename

    def fail_rename(source, target):
        if source.name == "XAnalyze.app" and source.parent.name.startswith(".xanalyze-"):
            raise OSError("install failed")
        if failure == "rollback" and source.name == "previous.app":
            raise OSError("rollback failed")
        return rename(source, target)

    if failure in ("install", "rollback"):
        monkeypatch.setattr(Path, "rename", fail_rename)
    if failure == "stage":
        monkeypatch.setattr(updater.shutil, "copytree", lambda *a, **k: (_ for _ in ()).throw(OSError("full disk")))
    if failure == "invalid":
        (new / "Contents/Info.plist").write_bytes(plistlib.dumps({}))
    if failure == "none":
        updater._replace_gui_app(old, new)
        binary = old / "Contents/MacOS/XAnalyze"
        assert binary.read_text() == "new"
        assert binary.stat().st_mode & 0o111
    else:
        with pytest.raises((OSError, RuntimeError)):
            updater._replace_gui_app(old, new)
        if failure == "rollback":
            backups = list(old.parent.glob(".xanalyze-update-*/previous.app"))
            assert len(backups) == 1
            assert (backups[0] / "Contents/MacOS/XAnalyze").read_text() == "old"
        else:
            assert (old / "Contents/MacOS/XAnalyze").read_text() == "old"
    if failure != "rollback":
        assert list(old.parent.iterdir()) == [old]


@pytest.mark.parametrize("gui_state, expected", [
    ("ok", 0), ("failure", 3), ("missing", 3), ("absent", 0),
])
def test_update_reports_each_installed_component(tmp_path, monkeypatch, capsys, gui_state, expected):
    release = updater.ReleaseInfo("v9.9.9", "9.9.9", "", [], "https://github.com/release")
    asset = {"name": "asset", "size": 3, "browser_download_url": "https://github.com/asset"}
    monkeypatch.setattr(updater, "fetch_latest", lambda: release)
    monkeypatch.setattr(updater, "fetch_update_manifest", lambda _: updater.UpdateManifest("v9.9.9", {}, True))
    monkeypatch.setattr(updater, "_cli_binary_path", lambda: tmp_path / "cli")
    monkeypatch.setattr(updater, "_gui_app_path", lambda: None if gui_state == "absent" else tmp_path / "app")
    monkeypatch.setattr(updater, "find_cli_asset", lambda _: asset)
    monkeypatch.setattr(updater, "find_gui_asset", lambda _: None if gui_state == "missing" else asset)
    monkeypatch.setattr(updater, "_asset_integrity", lambda *a: None)
    monkeypatch.setattr(updater, "_download", lambda *a: None)
    monkeypatch.setattr(updater, "_extract_cli_binary", lambda p: p)
    monkeypatch.setattr(updater, "_extract_gui_app", lambda p: p)
    monkeypatch.setattr(updater, "_replace_binary", lambda *a: None)

    def replace_gui(*args):
        if gui_state == "failure":
            raise OSError("disk full")

    monkeypatch.setattr(updater, "_replace_gui_app", replace_gui)
    assert updater.do_update() == expected
    output = capsys.readouterr()
    if expected:
        assert "Updated XAnalyze" not in output.out
        assert "not updated: GUI" in output.err
    else:
        assert "Updated XAnalyze" in output.out


@pytest.mark.parametrize("language", ["uk", "it", "en"])
def test_install_confirmation_in_each_language(language):
    async def exercise():
        app = XAnalyzeApp()
        app.lang = language
        async with app.run_test(size=(100, 40)) as pilot:
            screen = UpdateScreen()
            await app.push_screen(screen)
            await pilot.pause()
            screen._release = object()
            screen.query_one("#install", Button).disabled = False
            with patch("tui.runner.start") as start:
                start.return_value.running = True
                start.return_value.new_lines.return_value = []
                await pilot.click("#install")
                assert not start.called
                assert screen._install_armed
                await pilot.pause(0.3)
                await pilot.click("#install")
                assert start.call_count == 1
                assert not screen._install_armed
                await pilot.press("escape")
                assert app.screen is screen
    asyncio.run(exercise())


@pytest.mark.parametrize("exit_code", [0, 2, 3])
def test_tui_runs_worker_and_displays_completion(exit_code):
    def update():
        print("component result", file=sys.stderr)
        print("success" if exit_code == 0 else "failure", file=sys.stderr if exit_code else sys.stdout)
        return exit_code

    async def exercise():
        app = XAnalyzeApp()
        async with app.run_test(size=(100, 40)) as pilot:
            screen = UpdateScreen()
            await app.push_screen(screen)
            await pilot.pause()
            screen._release = object()
            screen.query_one("#install", Button).disabled = False
            with patch.object(updater, "do_update", side_effect=update):
                await pilot.click("#install")
                await pilot.pause(0.3)
                await pilot.click("#install")
                for _ in range(30):
                    await pilot.pause(0.1)
                    if not screen._busy:
                        break
                assert not screen._busy
                assert screen._run is None
                assert screen._release is None
                status = str(screen.query_one("#update-status", Label).render())
                assert ("success" if exit_code == 0 else "failure") in status
                if exit_code:
                    assert screen.tr("tui_update_restart") not in status
    asyncio.run(exercise())
