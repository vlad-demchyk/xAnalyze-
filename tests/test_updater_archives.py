"""What an update archive may unpack to, where, and a check that does not wait.

P-19: limits are checked before anything is written.
P-20: the unpacked copy lives in the transaction's folder, which is removed.
P-37: the once-a-day hint has a short timeout and an offline failure is
recorded, so the next command does not pay the timeout again.
"""
from __future__ import annotations

import io
import json
import tarfile
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

import updater


def _zip(path: Path, entries) -> Path:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries:
            zf.writestr(name, data)
    return path


def _tar(path: Path, entries) -> Path:
    with tarfile.open(path, "w:gz") as tf:
        for name, data in entries:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o755
            tf.addfile(info, io.BytesIO(data))
    return path


class ArchiveLimits(TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_a_normal_app_unpacks_into_the_given_folder(self):
        archive = _zip(self.root / "a.zip", [
            ("XAnalyze.app/Contents/Info.plist", b"<plist/>"),
            ("XAnalyze.app/Contents/MacOS/XAnalyze", b"\x7fELF" * 100),
        ])
        dest = self.root / "unpacked"
        app = updater._extract_gui_app(archive, dest)
        self.assertEqual(app, dest / "XAnalyze.app")
        self.assertTrue((app / "Contents" / "Info.plist").is_file())

    def test_a_path_out_of_the_folder_is_refused_before_writing(self):
        archive = _zip(self.root / "a.zip", [("../escape.txt", b"x")])
        dest = self.root / "unpacked"
        with self.assertRaisesRegex(RuntimeError, "unsafe path"):
            updater._extract_gui_app(archive, dest)
        self.assertFalse((self.root / "escape.txt").exists())
        self.assertEqual(list(dest.iterdir()), [])

    def test_an_absolute_path_is_refused(self):
        archive = _zip(self.root / "a.zip", [("/tmp/x", b"x")])
        with self.assertRaisesRegex(RuntimeError, "unsafe path"):
            updater._extract_gui_app(archive, self.root / "u")

    def test_a_zip_bomb_is_refused(self):
        archive = _zip(self.root / "a.zip",
                       [("XAnalyze.app/big", b"\0" * (8 * 1024 * 1024))])
        with self.assertRaisesRegex(RuntimeError, "ratio"):
            updater._extract_gui_app(archive, self.root / "u")

    def test_an_archive_bigger_than_the_ceiling_is_refused(self):
        archive = _zip(self.root / "a.zip", [("XAnalyze.app/x", b"abc" * 100)])
        with mock.patch.object(updater, "_MAX_UNPACKED_BYTES", 100):
            with self.assertRaisesRegex(RuntimeError, "more than allowed"):
                updater._extract_gui_app(archive, self.root / "u")

    def test_too_many_entries_are_refused(self):
        archive = _zip(self.root / "a.zip",
                       [(f"XAnalyze.app/{i}", b"x") for i in range(5)])
        with mock.patch.object(updater, "_MAX_ARCHIVE_ENTRIES", 3):
            with self.assertRaisesRegex(RuntimeError, "too many entries"):
                updater._extract_gui_app(archive, self.root / "u")

    def test_the_cli_binary_unpacks_into_the_given_folder(self):
        archive = _tar(self.root / "c.tar.gz",
                       [("dist/xanalyze", b"#!/bin/sh\necho hi\n" * 50)])
        dest = self.root / "unpacked"
        binary = updater._extract_cli_binary(archive, dest)
        self.assertTrue(binary.is_file())
        self.assertTrue(dest in binary.parents)

    def test_a_tar_path_out_of_the_folder_is_refused(self):
        archive = _tar(self.root / "c.tar.gz", [("../xanalyze", b"x")])
        with self.assertRaisesRegex(RuntimeError, "unsafe path"):
            updater._extract_cli_binary(archive, self.root / "u")
        self.assertFalse((self.root / "xanalyze").exists())


class TheTransactionCleansUp(TestCase):
    def test_do_update_unpacks_inside_the_folder_it_removes(self):
        seen = []

        def extract(archive, dest=None):
            seen.append((archive.parent, dest))
            raise RuntimeError("stop here")

        release = updater.ReleaseInfo(tag="v99.0.0", version="99.0.0",
                                      body="", assets=[], html_url="")
        asset = {"name": "xanalyze-cli.tar.gz", "size": 1,
                 "browser_download_url": "https://github.com/x"}
        manifest = mock.Mock(signature_verified=True)
        with mock.patch.object(updater, "fetch_latest", return_value=release), \
                mock.patch.object(updater, "fetch_update_manifest",
                                  return_value=manifest), \
                mock.patch.object(updater, "_cli_binary_path",
                                  return_value=Path("/nonexistent/xanalyze")), \
                mock.patch.object(updater, "find_cli_asset", return_value=asset), \
                mock.patch.object(updater, "_gui_app_path", return_value=None), \
                mock.patch.object(updater, "find_gui_asset", return_value=None), \
                mock.patch.object(updater, "_asset_integrity"), \
                mock.patch.object(updater, "_download"), \
                mock.patch.object(updater, "_extract_cli_binary", extract):
            updater.do_update()
        (tmp_dir, dest), = seen
        self.assertEqual(dest, tmp_dir / "unpacked")
        self.assertFalse(tmp_dir.exists(), "the transaction folder is removed")


class TheDailyCheck(TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        cache = Path(self._tmp.name) / "update_check.json"
        patcher = mock.patch.object(updater, "_cache_path", return_value=cache)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.cache = cache

    def test_the_quiet_check_uses_the_short_timeout(self):
        calls = []

        def fetch(timeout=15):
            calls.append(timeout)
            raise OSError("offline")

        with mock.patch.object(updater, "fetch_latest", fetch):
            self.assertIsNone(updater.check_for_update(quiet=True))
        self.assertEqual(calls, [updater._QUIET_CHECK_TIMEOUT])

    def test_an_offline_failure_is_recorded_so_the_next_run_does_not_wait(self):
        fetch = mock.Mock(side_effect=OSError("offline"))
        with mock.patch.object(updater, "fetch_latest", fetch):
            updater.check_for_update(quiet=True)
            updater.check_for_update(quiet=True)
        self.assertEqual(fetch.call_count, 1)
        self.assertIsNone(json.loads(self.cache.read_text())["version"])

    def test_the_explicit_check_is_not_cut_short(self):
        fetch = mock.Mock(side_effect=OSError("offline"))
        with mock.patch.object(updater, "fetch_latest", fetch):
            updater.check_for_update(quiet=False)
        fetch.assert_called_once_with()
        self.assertFalse(self.cache.exists())
