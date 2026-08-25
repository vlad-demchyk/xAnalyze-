"""The terminal interface, driven for real.

Four defects are pinned here, all reported from using the thing:

1. A target without `https://` was refused.
2. Every screen ended with "See results in terminal" and showed no result.
3. Arrow keys did nothing - Textual binds only `tab` by default.
4. Clicking a report did nothing - the table had no selection handler.

Driven through Textual's own `run_test` pilot rather than by poking widgets,
because three of the four were about key and mouse handling and only a real
event loop exercises that.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import unittest
from pathlib import Path
from unittest import mock

from textual.widgets import Button, Checkbox, DataTable, Input, Label, Select

from tui.app import XAnalyzeApp
from tui import runner as tui_runner
from tui.runner import RunResult


def run(coroutine):
    """Drive one async test body. The suite is `unittest`, not pytest-asyncio."""
    return asyncio.new_event_loop().run_until_complete(coroutine)


class Runner(unittest.TestCase):
    """The capture layer that replaced "see results in terminal"."""

    def test_stdout_is_captured_and_parsed(self):
        def command(_args):
            print(json.dumps({"counts": {"total": 3}}))
            return 0

        result = self._run(command)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.payload(), {"counts": {"total": 3}})

    def test_progress_lines_are_reported_as_they_happen(self):
        import sys

        def command(_args):
            print("# [stage crawl]", file=sys.stderr)
            print("# [crawl done] 2 page(s)", file=sys.stderr)
            print("{}")
            return 0

        seen: list = []
        self._run(command, on_progress=seen.append)
        self.assertIn("# [stage crawl]", seen)
        self.assertIn("# [crawl done] 2 page(s)", seen)

    def test_report_paths_come_from_what_was_announced(self):
        import sys

        def command(_args):
            print("# report: /tmp/a/report.md", file=sys.stderr)
            print("# styled report: /tmp/a/report.pdf", file=sys.stderr)
            print("# run folder: /tmp/a", file=sys.stderr)
            print("{}")
            return 0

        result = self._run(command)
        self.assertEqual(result.report_paths(),
                         ["/tmp/a/report.md", "/tmp/a/report.pdf", "/tmp/a"])

    def test_an_exception_is_reported_not_swallowed(self):
        def command(_args):
            raise RuntimeError("boom")

        result = self._run(command)
        self.assertFalse(result.ok)
        self.assertIn("boom", result.error)

    def test_streams_are_restored_afterwards(self):
        """The capture is process-wide, so it must always be undone."""
        import sys

        before = sys.stdout

        def command(_args):
            raise RuntimeError("boom")

        self._run(command)
        self.assertIs(sys.stdout, before)

    def test_non_json_output_yields_no_payload(self):
        def command(_args):
            print("No findings.")
            return 0

        self.assertIsNone(self._run(command).payload())

    def _run(self, command, on_progress=None):
        """Run `command` through the runner and wait for it, without an app."""
        run = tui_runner.start(command, argparse.Namespace())
        run.join(timeout=10)
        self.assertIsNotNone(run.result, "the run never finished")
        if on_progress is not None:
            for line in run.new_lines():
                on_progress(line)
        return run.result


class ArrowNavigation(unittest.TestCase):
    """Defect 3: arrows did nothing, though the README promised them."""

    def test_down_moves_focus_forward(self):
        async def body():
            app = XAnalyzeApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                app.screen.focus_next()
                await pilot.pause()
                first = app.focused
                await pilot.press("down")
                await pilot.pause()
                return first, app.focused

        first, second = run(body())
        self.assertIsNotNone(first)
        self.assertIsNot(first, second)

    def test_up_moves_focus_back(self):
        async def body():
            app = XAnalyzeApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                app.screen.focus_next()
                await pilot.pause()
                first = app.focused
                await pilot.press("down")
                await pilot.press("up")
                await pilot.pause()
                return first, app.focused

        first, back = run(body())
        self.assertIs(first, back)

    def test_footer_shows_the_key_hints(self):
        """The bindings existed; nothing displayed them."""
        from textual.widgets import Footer

        async def body():
            app = XAnalyzeApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                return len(app.screen.query(Footer))

        self.assertEqual(run(body()), 1)


class MenuNavigation(unittest.TestCase):
    def test_number_shortcut_opens_the_screen(self):
        async def body():
            app = XAnalyzeApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("4")
                await pilot.pause()
                return app.screen.__class__.__name__

        self.assertEqual(run(body()), "ReportsScreen")

    def test_escape_returns_to_the_menu(self):
        async def body():
            app = XAnalyzeApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("2")
                await pilot.pause()
                await pilot.press("escape")
                await pilot.pause()
                return app.screen.__class__.__name__

        self.assertEqual(run(body()), "MainMenuScreen")

    def test_every_menu_entry_has_a_screen(self):
        from tui.screens.main_menu import MENU

        async def body():
            app = XAnalyzeApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                missing = []
                for _key, name, _label in MENU:
                    if name not in app._installed_screens:
                        missing.append(name)
                return missing

        self.assertEqual(run(body()), [])


class SchemelessTarget(unittest.TestCase):
    """Defect 1: `example.com` typed into the form must reach the command."""

    def test_fullscan_passes_the_bare_host_through(self):
        async def body():
            app = XAnalyzeApp()
            captured: list = []

            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("3")
                await pilot.pause()
                screen = app.screen
                screen.query_one("#target", Input).value = "example.com"
                with mock.patch.object(screen, "start_run",
                                       side_effect=lambda *a, **k:
                                       captured.append((a, k)) or True):
                    screen._run_fullscan()
                await pilot.pause()
            return captured

        captured = run(body())
        self.assertEqual(len(captured), 1)
        (_command, args), _kwargs = captured[0]
        self.assertEqual(args.target, "example.com")

    def test_the_command_itself_accepts_it(self):
        """The form is only half of it - the CLI has to agree."""
        from cli_impl.auditpass import looks_like_url

        self.assertTrue(looks_like_url("example.com"))

    def test_empty_target_is_refused_with_a_sentence(self):
        async def body():
            app = XAnalyzeApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("3")
                await pilot.pause()
                app.screen._run_fullscan()
                await pilot.pause()
                return str(app.screen.query_one("#fullscan-status", Label)
                           .render())

        self.assertIn("Enter a target", run(body()))


class ResultsScreenShowsTheResult(unittest.TestCase):
    """Defect 2: the result was announced as being somewhere else."""

    def result(self):
        return RunResult(
            0,
            json.dumps({"target": "https://example.com",
                        "summary": {"total_findings": 14, "accessibility": 6}}),
            "# report: /tmp/nope/report.md\n",
        )

    def test_summary_rows_are_built_from_the_payload(self):
        from tui.screens.results import summary_rows

        rows = dict(summary_rows(self.result().payload()))
        self.assertEqual(rows["total findings"], "14")
        self.assertEqual(rows["accessibility"], "6")
        self.assertEqual(rows["target"], "https://example.com")

    def test_no_payload_means_no_rows_rather_than_a_crash(self):
        from tui.screens.results import summary_rows

        self.assertEqual(summary_rows(None), [])

    def test_screen_lists_what_was_written(self):
        from tui.screens.results import ResultsScreen

        async def body():
            app = XAnalyzeApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                app.push_screen(ResultsScreen("Scan of x", self.result()))
                await pilot.pause()
                text = str(app.screen.query_one("#results-paths", Label)
                           .render())
                table = app.screen.query_one("#results-summary", DataTable)
                return text, table.row_count

        text, rows = run(body())
        self.assertIn("/tmp/nope/report.md", text)
        self.assertGreater(rows, 0)

    def test_a_missing_file_cannot_be_opened(self):
        from tui.screens.results import open_in_os

        self.assertIn("Not there", open_in_os("/tmp/definitely-not-here-42"))

    def test_severity_rows_get_four_different_colours_not_one(self):
        """Before this, "critical" and "minor" were the table's default
        foreground - the same colour a run with no findings at all used for
        "target". The severity ramp existing in the palette does nothing for
        anyone if the one screen that lists severities by name never reads
        it."""
        from tui.screens.results import ResultsScreen

        result = RunResult(
            0,
            json.dumps({"counts": {"critical": 3, "serious": 8,
                                    "moderate": 15, "minor": 14}}),
            "",
        )

        async def body():
            app = XAnalyzeApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                app.push_screen(ResultsScreen("Scan of x", result))
                await pilot.pause()
                table = app.screen.query_one("#results-summary", DataTable)
                styles = {}
                for row_key, _ in table.rows.items():
                    cell = table.get_cell(row_key, table.ordered_columns[0].key)
                    label = str(cell)
                    if label in ("critical", "serious", "moderate", "minor"):
                        styles[label] = cell.style
                return styles

        styles = run(body())
        self.assertEqual(set(styles), {"critical", "serious", "moderate", "minor"})
        self.assertEqual(len(set(styles.values())), 4,
                         f"expected four distinct colours, got {styles}")


class ReportsScreenReacts(unittest.TestCase):
    """Defect 4: clicking a row did nothing."""

    def history(self, tmp: Path) -> list:
        return [{
            "at": "2026-01-01 10:00:00 UTC", "root": "/repo", "mode": "repo",
            "counts": {"critical": 1, "minor": 2}, "distinct": 2,
            "documents": 5, "fixed": 0, "report": str(tmp / "report.md"),
        }]

    def test_rows_come_from_the_history(self):
        import tempfile

        from tui.screens import reports as screen_module

        async def body(tmp):
            app = XAnalyzeApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                with mock.patch.object(screen_module, "load_runs",
                                       return_value=self.history(tmp)):
                    await pilot.press("4")
                    await pilot.pause()
                    table = app.screen.query_one("#reports-table", DataTable)
                    detail = str(app.screen.query_one("#report-detail", Label)
                                 .render())
                    return table.row_count, detail

        with tempfile.TemporaryDirectory() as tmp:
            rows, detail = run(body(Path(tmp)))
        self.assertEqual(rows, 1)
        self.assertIn("/repo", detail)

    def test_selecting_a_row_opens_the_report(self):
        import tempfile

        from tui.screens import reports as screen_module

        async def body(tmp):
            app = XAnalyzeApp()
            opened: list = []
            async with app.run_test() as pilot:
                await pilot.pause()
                with mock.patch.object(screen_module, "load_runs",
                                       return_value=self.history(tmp)):
                    with mock.patch.object(screen_module, "open_in_os",
                                           side_effect=lambda p:
                                           opened.append(p) or "ok"):
                        await pilot.press("4")
                        await pilot.pause()
                        await pilot.press("enter")
                        await pilot.pause()
            return opened

        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "report.md").write_text("x", encoding="utf-8")
            opened = run(body(Path(tmp)))
        self.assertEqual(len(opened), 1)
        self.assertTrue(opened[0].endswith("report.md"))

    def test_an_empty_history_says_so_instead_of_nothing(self):
        from tui.screens import reports as screen_module

        async def body():
            app = XAnalyzeApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                with mock.patch.object(screen_module, "load_runs",
                                       return_value=[]):
                    await pilot.press("4")
                    await pilot.pause()
                    return str(app.screen.query_one("#report-status", Label)
                               .render())

        self.assertIn("No runs recorded", run(body()))

    def test_the_list_is_rebuilt_on_every_visit(self):
        """It used to be built once, in `on_mount`, and never again."""
        import tempfile

        from tui.screens import reports as screen_module

        async def body(tmp):
            app = XAnalyzeApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                with mock.patch.object(screen_module, "load_runs",
                                       return_value=[]):
                    await pilot.press("4")
                    await pilot.pause()
                    await pilot.press("escape")
                    await pilot.pause()
                with mock.patch.object(screen_module, "load_runs",
                                       return_value=self.history(tmp)):
                    await pilot.press("4")
                    await pilot.pause()
                    return app.screen.query_one("#reports-table",
                                                DataTable).row_count

        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(run(body(Path(tmp))), 1)


class SettingsAreEditable(unittest.TestCase):
    def test_saving_writes_the_changed_value(self):
        async def body():
            app = XAnalyzeApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("5")
                await pilot.pause()
                screen = app.screen
                screen.query_one("#set-repo_scope", Select).value = "both"
                with mock.patch.object(screen.settings, "save") as save:
                    screen.action_save()
                    await pilot.pause()
                    return save.call_count, screen.settings.repo_scope

        calls, value = run(body())
        self.assertEqual(calls, 1)
        self.assertEqual(value, "both")

    def test_saving_nothing_says_nothing_changed(self):
        async def body():
            app = XAnalyzeApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("5")
                await pilot.pause()
                screen = app.screen
                with mock.patch.object(screen.settings, "save") as save:
                    screen.action_save()
                    await pilot.pause()
                    return save.call_count, str(
                        screen.query_one("#settings-status", Label).render())

        calls, status = run(body())
        self.assertEqual(calls, 0)
        self.assertIn("Nothing changed", status)

    def test_integer_settings_are_saved_as_integers(self):
        async def body():
            app = XAnalyzeApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("5")
                await pilot.pause()
                screen = app.screen
                screen.query_one("#set-crawl_depth", Select).value = "3"
                with mock.patch.object(screen.settings, "save"):
                    screen.action_save()
                return screen.settings.crawl_depth

        self.assertEqual(run(body()), 3)


class OneRunAtATime(unittest.TestCase):
    """The captured streams are process-wide, so overlap must be impossible."""

    def test_a_second_start_is_refused_while_one_is_running(self):
        import threading

        gate = threading.Event()

        async def body():
            app = XAnalyzeApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("1")
                await pilot.pause()
                screen = app.screen
                first = screen.start_run(lambda _a: gate.wait(5) and 0,
                                         argparse.Namespace(), title="x")
                second = screen.start_run(lambda _a: 0,
                                          argparse.Namespace(), title="y")
                gate.set()
                return first, second

        first, second = run(body())
        self.assertTrue(first)
        self.assertFalse(second)

    def test_the_run_button_is_disabled_while_running(self):
        async def body():
            app = XAnalyzeApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("1")
                await pilot.pause()
                screen = app.screen
                screen._set_busy(True)
                await pilot.pause()
                return screen.query_one("#run", Button).disabled

        self.assertTrue(run(body()))


class DevServerConfirm(unittest.TestCase):
    """A repo target with missing dev-server deps asks before `start_run` -
    but only when "Start dev server" is checked. Off by default: the
    server may already be running elsewhere, and starting a second one on a
    different port is a confusing outcome, not a helpful one.
    """

    def _repo_with_missing_deps(self, tmp_path):
        (tmp_path / "package.json").write_text("{}", encoding="utf-8")
        return tmp_path

    def test_unchecked_by_default_scans_statically_even_with_missing_deps(self):
        """The default: no modal, no server, the plain static scan runs -
        `cmd_fullscan` itself says a stack exists, this screen does not ask."""
        import tempfile
        from tui.screens.confirm import ConfirmModal

        async def body():
            with tempfile.TemporaryDirectory() as tmp:
                repo = self._repo_with_missing_deps(Path(tmp))
                app = XAnalyzeApp()
                captured: list = []
                async with app.run_test() as pilot:
                    await pilot.pause()
                    await pilot.press("3")
                    await pilot.pause()
                    screen = app.screen
                    screen.query_one("#target", Input).value = str(repo)
                    self.assertFalse(screen.query_one("#devserver", Checkbox).value)
                    with mock.patch.object(
                            screen, "start_run",
                            side_effect=lambda *a, **k: captured.append((a, k)) or True):
                        screen._run_fullscan()
                    await pilot.pause()
                    pushed_modal = isinstance(app.screen, ConfirmModal)
                return captured, pushed_modal

        captured, pushed_modal = run(body())
        self.assertFalse(pushed_modal)
        self.assertEqual(len(captured), 1)
        (_command, args), _kwargs = captured[0]
        self.assertFalse(args.devserver)

    def test_checked_and_missing_deps_pushes_a_modal_before_running(self):
        import tempfile
        from tui.screens.confirm import ConfirmModal

        async def body():
            with tempfile.TemporaryDirectory() as tmp:
                repo = self._repo_with_missing_deps(Path(tmp))
                app = XAnalyzeApp()
                captured: list = []
                async with app.run_test() as pilot:
                    await pilot.pause()
                    await pilot.press("3")
                    await pilot.pause()
                    screen = app.screen
                    screen.query_one("#target", Input).value = str(repo)
                    screen.query_one("#devserver", Checkbox).value = True
                    with mock.patch.object(
                            screen, "start_run",
                            side_effect=lambda *a, **k: captured.append((a, k)) or True):
                        screen._run_fullscan()
                    await pilot.pause()
                    pushed_modal = isinstance(app.screen, ConfirmModal)
                return captured, pushed_modal

        captured, pushed_modal = run(body())
        self.assertTrue(pushed_modal)
        # start_run must not have been called yet - the question is still open.
        self.assertEqual(captured, [])

    def test_confirming_yes_starts_the_run_with_yes_set(self):
        import tempfile

        async def body():
            with tempfile.TemporaryDirectory() as tmp:
                repo = self._repo_with_missing_deps(Path(tmp))
                app = XAnalyzeApp()
                captured: list = []
                async with app.run_test() as pilot:
                    await pilot.pause()
                    await pilot.press("3")
                    await pilot.pause()
                    screen = app.screen
                    screen.query_one("#target", Input).value = str(repo)
                    screen.query_one("#devserver", Checkbox).value = True
                    with mock.patch.object(
                            screen, "start_run",
                            side_effect=lambda *a, **k: captured.append((a, k)) or True):
                        screen._run_fullscan()
                        await pilot.pause()
                        await pilot.click("#confirm-yes")
                        await pilot.pause()
                return captured

        captured = run(body())
        self.assertEqual(len(captured), 1)
        (_command, args), _kwargs = captured[0]
        self.assertTrue(args.yes)

    def test_confirming_no_still_starts_the_run_static_only(self):
        """Declining the install does not cancel the scan - it falls back
        to the static repo scan, exactly like the CLI path does."""
        import tempfile

        async def body():
            with tempfile.TemporaryDirectory() as tmp:
                repo = self._repo_with_missing_deps(Path(tmp))
                app = XAnalyzeApp()
                captured: list = []
                async with app.run_test() as pilot:
                    await pilot.pause()
                    await pilot.press("3")
                    await pilot.pause()
                    screen = app.screen
                    screen.query_one("#target", Input).value = str(repo)
                    screen.query_one("#devserver", Checkbox).value = True
                    with mock.patch.object(
                            screen, "start_run",
                            side_effect=lambda *a, **k: captured.append((a, k)) or True):
                        screen._run_fullscan()
                        await pilot.pause()
                        await pilot.click("#confirm-no")
                        await pilot.pause()
                return captured

        captured = run(body())
        self.assertEqual(len(captured), 1)
        (_command, args), _kwargs = captured[0]
        self.assertFalse(args.yes)

    def test_checked_and_satisfied_deps_runs_immediately(self):
        import tempfile

        async def body():
            with tempfile.TemporaryDirectory() as tmp:
                repo = Path(tmp)
                (repo / "package.json").write_text("{}", encoding="utf-8")
                (repo / "node_modules").mkdir()
                app = XAnalyzeApp()
                captured: list = []
                async with app.run_test() as pilot:
                    await pilot.pause()
                    await pilot.press("3")
                    await pilot.pause()
                    screen = app.screen
                    screen.query_one("#target", Input).value = str(repo)
                    screen.query_one("#devserver", Checkbox).value = True
                    with mock.patch.object(
                            screen, "start_run",
                            side_effect=lambda *a, **k: captured.append((a, k)) or True):
                        screen._run_fullscan()
                    await pilot.pause()
                return captured

        captured = run(body())
        self.assertEqual(len(captured), 1)

    def test_a_url_target_never_triggers_a_devserver_check(self):
        async def body():
            app = XAnalyzeApp()
            captured: list = []
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("3")
                await pilot.pause()
                screen = app.screen
                screen.query_one("#target", Input).value = "https://example.com"
                with mock.patch.object(
                        screen, "start_run",
                        side_effect=lambda *a, **k: captured.append((a, k)) or True):
                    screen._run_fullscan()
                await pilot.pause()
            return captured

        captured = run(body())
        self.assertEqual(len(captured), 1)


async def _selector_widths_in_sentence(menu_key: str):
    """`([(select_id, width), ...], row_width)` for the `.sentence` row on
    the screen `menu_key` opens from the main menu.

    Textual's `query()` result is a `DOMQuery`, which walks the live DOM the
    first time something reads `.nodes` and caches that - it does not hold a
    snapshot taken at query time. Returning the `DOMQuery` itself out of
    `run_test()`'s `async with` block, the way an early version of this test
    did, defers that first read to *after* the app has torn down and its
    widgets are unmounted, so the query silently finds nothing and every
    assertion in a `for select in (that empty query)` loop never runs - a
    test that always passes without ever having tested anything. Reading the
    widths here, while the app is still mounted, and returning plain tuples
    is what makes the caller's assertions real.
    """
    app = XAnalyzeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press(menu_key)
        await pilot.pause()
        sentence = app.screen.query_one(".sentence")
        widths = [(select.id, select.size.width)
                  for select in sentence.query(Select)]
        return widths, sentence.size.width


class FullscanReadsAsASentence(unittest.TestCase):
    """The redesign's toolbar (artboard 3a) reads "analyze Site · depth 2"
    instead of a form of labelled dropdowns. FullscanScreen's language/
    depth/breakpoints selectors moved into one such sentence; this pins the
    part that actually matters - that they are still the same three
    controls under the same three ids, so nothing about running a scan
    changed underneath the new layout."""

    def test_the_three_selectors_still_answer_to_their_old_ids(self):
        async def body():
            app = XAnalyzeApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("3")
                await pilot.pause()
                screen = app.screen
                return (
                    screen.query_one("#language", Select).value,
                    screen.query_one("#depth", Select).value,
                    screen.query_one("#breakpoints", Select).value,
                )

        language, depth, breakpoints = run(body())
        self.assertEqual(language, "")
        self.assertEqual(depth, "1")
        self.assertEqual(breakpoints, "desktop")

    def test_the_selectors_size_to_their_value_not_to_the_full_row(self):
        """Regression for a real defect found while building this screen:
        `SelectCurrent`'s own default CSS is `width: 1fr`, so without an
        explicit override each selector claimed the sentence's entire
        width and pushed everything after the first one off screen -
        `debug`-rendering the screen showed only the word "language" and
        nothing else in the row."""
        widths, row_width = run(_selector_widths_in_sentence("3"))
        self.assertTrue(widths, "no Select found in the sentence row at all")
        for select_id, width in widths:
            self.assertLess(
                width, row_width // 2,
                f"#{select_id} claimed {width} of a {row_width}-wide row")


class TheOtherFormsBecameSentencesToo(unittest.TestCase):
    """Scan (detector/scope) and Audit (language/depth/breakpoints) got the
    same treatment as Fullscan, for the same reason: one inline sentence
    instead of a stack of labelled dropdowns. This is the width regression
    from `FullscanReadsAsASentence` run against the other two screens,
    because the defect it guards against (`SelectCurrent`'s `width: 1fr`
    swallowing the row) is a property of the shared `.sentence` CSS, not of
    any one screen, and a screen added after this file was last read would
    hit it the same way if that CSS regressed.
    """

    def _selectors_fit_their_row(self, menu_key):
        widths, row_width = run(_selector_widths_in_sentence(menu_key))
        self.assertTrue(widths, "no Select found in the sentence row at all")
        for select_id, width in widths:
            self.assertLess(
                width, row_width // 2,
                f"#{select_id} claimed {width} of a {row_width}-wide row")

    def test_scan_screen_detector_and_scope_fit_their_row(self):
        self._selectors_fit_their_row("1")

    def test_audit_screen_language_depth_and_breakpoints_fit_their_row(self):
        self._selectors_fit_their_row("2")


if __name__ == "__main__":
    unittest.main()
