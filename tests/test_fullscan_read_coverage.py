"""A `fullscan` of a folder has to say what it opened.

`scan --json` has always carried a `read` block - files read, blocks found,
what was skipped and why, whether the walk hit its limit - for one reason,
written at its own definition: `counts.files` counts files among the
*findings*, so a quiet result cannot otherwise say whether it read four
thousand files or none.

`fullscan` collected the same diagnostics and threw them away. Measured
2026-09-01 across seven repositories on this machine: every run reported
`"read": null` while finding hundreds of things, so the JSON said the scan
had opened nothing at all.
"""
import json
import tempfile
import unittest
from pathlib import Path

from cli_impl.fullscan import _read_diagnostics


class _Walk:
    files_read = 226
    blocks_found = 3266
    skipped_ignored = 4
    skipped_too_large = 0
    unreadable = 1
    truncated = False
    limit = 5000


class TheShapeMatchesTheScanCommand(unittest.TestCase):

    def test_every_field_the_scan_command_prints_is_here(self):
        from cli_impl.output import _print_json
        import io
        import contextlib

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            _print_json([], walked=[("/repo", _Walk())])
        from_scan = json.loads(buffer.getvalue())["read"]
        from_fullscan = _read_diagnostics([("/repo", _Walk())])
        self.assertEqual(from_fullscan, from_scan)

    def test_the_numbers_are_the_walk_s_own(self):
        entry = _read_diagnostics([("/repo", _Walk())])[0]
        self.assertEqual(entry["files_read"], 226)
        self.assertEqual(entry["blocks_found"], 3266)
        self.assertEqual(entry["unreadable"], 1)
        self.assertEqual(entry["limit"], 5000)

    def test_no_walk_is_an_empty_list_not_a_zero(self):
        """A single file named on the command line is not a walk: naming it
        is the answer, and inventing `files_read: 0` for it would say the
        opposite of what happened."""
        self.assertEqual(_read_diagnostics([]), [])


class TheFullscanPayloadCarriesIt(unittest.TestCase):

    def test_a_folder_scan_reports_the_files_it_opened(self):
        from cli_impl.fullscan import _scan_local_target

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "page.html").write_text(
                "<html lang='en'><body><p>Some copy for a reader– here"
                "</p></body></html>", encoding="utf-8")

            class _Args:
                paths = [str(root)]
                detector = "offline"
                scope = "both"
                no_unicode = False
                no_typography = False
                incremental = False
                max_files = 5000
                ext = None
                exclude = None
                no_default_excludes = False
                json = True
                agent = False
                medium = None
                confidence = None
                language = "en"
                model = None
                effort = None
                no_judgment_cache = False

            _findings, result, _candidates = _scan_local_target(
                str(root), _Args(), lang="en", agent_mode=False)

        self.assertTrue(result["read"], "the walk was dropped again")
        self.assertEqual(result["read"][0]["root"], str(root))
        self.assertGreaterEqual(result["read"][0]["files_read"], 1)


class ATruncatedWalkIsSaidOutLoud(unittest.TestCase):
    """`scan` prints one line when it stops at the file limit. `fullscan`
    printed nothing, and it is the surface that writes the report."""

    def test_the_limit_is_reported_on_stderr(self):
        import contextlib
        import io
        from unittest import mock

        from cli_impl import fullscan

        class _Walk300(_Walk):
            truncated = True
            limit = 300

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "page.html").write_text("<p>copy</p>", encoding="utf-8")

            class _Args:
                paths = [str(root)]
                detector = "offline"
                scope = "both"
                no_unicode = False
                no_typography = False
                incremental = False
                max_files = 300
                ext = None
                exclude = None
                no_default_excludes = False
                json = True
                agent = False
                medium = None
                confidence = None
                language = "en"
                model = None
                effort = None
                no_judgment_cache = False

            def _collect(paths, args, missing_out=None, diagnostics_out=None):
                if diagnostics_out is not None:
                    diagnostics_out.append((str(root), _Walk300()))
                from cli_impl.scanning import _collect_files as real
                return real(paths, args)

            err = io.StringIO()
            with mock.patch.object(fullscan, "_collect_files", _collect), \
                    contextlib.redirect_stderr(err):
                fullscan._scan_local_target(str(root), _Args(), lang="en",
                                            agent_mode=False)
        self.assertIn("300-file limit", err.getvalue())
        self.assertIn("--max-files", err.getvalue())


if __name__ == "__main__":
    unittest.main()
