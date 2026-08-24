"""One folder per target, one sub-folder per run, and the timings inside it.

The documents used to be timestamped files dropped loose on the Desktop, so
two runs of the same site were impossible to find next to each other - and
the comparison that a second run exists to produce had nowhere to live.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cli_impl import runfolder


class Slug(unittest.TestCase):
    def test_url_keeps_its_host(self):
        self.assertEqual(runfolder.slug_for("https://example.com"),
                         "example.com")

    def test_url_path_joins_the_name(self):
        self.assertEqual(runfolder.slug_for("https://example.com/pricing/"),
                         "example.com-pricing")

    def test_path_keeps_its_last_component(self):
        self.assertEqual(runfolder.slug_for("/Users/me/code/shop"), "shop")
        self.assertEqual(runfolder.slug_for("./site"), "site")

    def test_trailing_separator_is_not_the_name(self):
        self.assertEqual(runfolder.slug_for("/Users/me/code/shop/"), "shop")

    def test_empty_target_still_has_a_name(self):
        self.assertEqual(runfolder.slug_for(""), "scan")

    def test_name_is_bounded(self):
        self.assertLessEqual(len(runfolder.slug_for("a" * 500)), 60)

    def test_separators_never_reach_the_folder_name(self):
        slug = runfolder.slug_for("https://example.com/a/../b?c=1#d")
        self.assertNotIn("/", slug)
        self.assertNotIn("\\", slug)


class Prepare(unittest.TestCase):
    def test_run_folder_sits_under_the_project_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = runfolder.prepare("https://example.com", root=Path(tmp))
            self.assertEqual(folder.project.name, "example.com")
            self.assertEqual(folder.run.parent, folder.project)
            self.assertTrue(folder.run.is_dir())

    def test_documents_are_named_by_kind_not_by_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = runfolder.prepare("x", root=Path(tmp))
            self.assertEqual(folder.report.name, "report.md")
            self.assertEqual(folder.styled_report.name, "report.pdf")
            self.assertEqual(folder.timings.name, "timings.md")
            self.assertEqual(folder.changes.name, "changes.md")

    def test_two_runs_in_the_same_minute_do_not_collide(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = runfolder.prepare("x", root=Path(tmp))
            second = runfolder.prepare("x", root=Path(tmp))
            self.assertNotEqual(first.run, second.run)
            self.assertEqual(first.project, second.project)

    def test_earlier_runs_are_discoverable(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = runfolder.prepare("x", root=Path(tmp))
            second = runfolder.prepare("x", root=Path(tmp))
            self.assertIn(first.run, second.previous_runs())
            self.assertNotIn(second.run, second.previous_runs())

    def test_environment_can_move_the_root(self):
        import os

        with tempfile.TemporaryDirectory() as tmp:
            previous = os.environ.get(runfolder.ROOT_ENV)
            os.environ[runfolder.ROOT_ENV] = tmp
            try:
                folder = runfolder.prepare("https://example.com")
            finally:
                if previous is None:
                    os.environ.pop(runfolder.ROOT_ENV, None)
                else:
                    os.environ[runfolder.ROOT_ENV] = previous
            self.assertEqual(folder.project.parent, Path(tmp))


class TimingsDocument(unittest.TestCase):
    def test_stages_are_recorded_in_order(self):
        timings = runfolder.Timings()
        timings.start("crawl")
        timings.start("audit")
        timings.finish()
        self.assertEqual([name for name, _ in timings.stages()],
                         ["crawl", "audit"])

    def test_open_stage_is_reported_at_its_duration_so_far(self):
        timings = runfolder.Timings()
        timings.start("crawl")
        self.assertEqual(len(timings.stages()), 1)

    def test_finish_twice_does_not_double_count(self):
        timings = runfolder.Timings()
        timings.start("crawl")
        timings.finish()
        timings.finish()
        self.assertEqual(len(timings.stages()), 1)

    def test_document_names_the_stages_and_the_extras(self):
        timings = runfolder.Timings()
        timings.start("crawl")
        timings.finish()
        text = timings.as_markdown("https://example.com",
                                   extra={"findings": 12})
        self.assertIn("crawl", text)
        self.assertIn("findings: 12", text)
        self.assertIn("https://example.com", text)

    def test_written_to_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "timings.md"
            timings = runfolder.Timings()
            timings.note("crawl", 1.5)
            timings.write(path, "x")
            self.assertIn("crawl", path.read_text(encoding="utf-8"))


class Duration(unittest.TestCase):
    def test_seconds(self):
        self.assertEqual(runfolder._duration(9.44), "9.4s")

    def test_minutes(self):
        self.assertEqual(runfolder._duration(93), "1m 33s")

    def test_hours(self):
        self.assertEqual(runfolder._duration(3723), "1h 02m 03s")


if __name__ == "__main__":
    unittest.main()
