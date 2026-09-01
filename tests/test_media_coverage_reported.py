"""What the image pass read has to reach the report.

`audit.media` opens the images a crawl found and reads what the file says
about how it was made: the IPTC `DigitalSourceType` value that names a model,
the generation parameters Stable Diffusion writes into a PNG text chunk, a
generator's name in EXIF/XMP, and the container marker of a C2PA manifest.
It works under a budget - 40 images and 20 MB per run - so some addresses are
never opened at all.

Measured 2026-09-01 on a live 250-page site: the pass ran, wrote its counts
into `AccessibilityResult.media`, and **nobody read them**. The report showed
no image finding, which on that site is true and unremarkable, and no reader
could tell that from "no image was ever fetched".

That is the exact confusion `audit/media.py` opens by forbidding: an image
nobody fetched has not come back clean, it has not come back.
"""
import unittest

from audit.media import MediaFetchScan


class _Result:
    root = "https://example.test/"
    mode = "web"

    def __init__(self, media=None):
        self.documents = []
        self.media = media
        self.rules_run = []

    def by_rule(self):
        return {}

    def documents_with_issues(self):
        return []


def _payload(media):
    """A minimal briefing payload - everything `_report_markdown` reads."""
    return {
        "generated": "2026-09-01 00:00:00 UTC",
        "root": "https://example.test/", "mode": "web",
        "summary": {"counts": {"minor": 0}, "total": 0,
                    "distinct_problems": 0, "documents": 1,
                    "documents_with_findings": 0, "rules_triggered": 0,
                    "platform_owned": {}},
        "files": [], "problems": [], "by_rule": [], "history": [],
        "saturated_rules": [], "detected_stacks": [],
        "ai_patterns": {}, "typography": {}, "media": media,
        "changed_this_run": {},
    }


def _render(media):
    from cli_impl.reports import _report_markdown

    return _report_markdown(_payload(media), "en")


class TheCoverageReachesThePayload(unittest.TestCase):

    def _coverage(self, scan):
        from cli_impl.reports import _media_coverage

        return _media_coverage(_Result(scan))

    def test_every_number_the_pass_keeps_is_carried(self):
        scan = MediaFetchScan(found=120, checked=40, duplicates=3,
                              skipped_budget=78, skipped_too_large=1,
                              unreachable=1, findings=[("a.png", None)],
                              places={"a.png": ["b.png"]})
        self.assertEqual(self._coverage(scan), {
            "found": 120, "read": 40, "duplicates": 3, "skipped_budget": 78,
            "skipped_too_large": 1, "unreachable": 1, "said_something": 1,
            "places": {"a.png": ["b.png"]},
        })

    def test_a_repeat_is_a_place_not_a_second_problem(self):
        """The same bytes under two addresses are one file used twice. The
        report names both places and counts one finding."""
        text = _render({"found": 3, "read": 2, "duplicates": 1,
                                  "skipped_budget": 0, "skipped_too_large": 0,
                                  "unreachable": 0, "said_something": 0,
                                  "places": {"a.png": ["b.png"]}})
        self.assertIn("same bytes as a file", text)
        self.assertIn("**1**", text)

    def test_no_pass_is_not_a_pass_that_found_nothing(self):
        self.assertEqual(self._coverage(None), {})


class TheCoverageReachesTheBriefing(unittest.TestCase):

    def test_a_quiet_result_says_how_many_files_were_opened(self):
        text = _render({"found": 120, "read": 40, "skipped_budget": 78,
                             "skipped_too_large": 1, "unreachable": 1,
                             "said_something": 0})
        self.assertIn("Image provenance", text)
        self.assertIn("**40** of **120**", text)
        self.assertIn("78", text)
        # And it must not let the silence be read as a verdict.
        self.assertIn("says nothing has said nothing", text)

    def test_nothing_is_printed_when_no_images_were_found(self):
        self.assertNotIn("Image provenance", _render({}))


if __name__ == "__main__":
    unittest.main()
