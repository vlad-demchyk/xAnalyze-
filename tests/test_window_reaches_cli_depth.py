"""What the window can ask that only the command line could ask before.

Three of them, and the first is the one that changes an answer rather than a
convenience: a finding on a website names the page, and a page is where to
look and never where to edit. `--repo` has answered that in the CLI for
months; the window had no field for it, so a person working there could not
know the same tool would have named the file.

The other two: `--within`, for the web part or widget delivered into somebody
else's page, and the pre-run notices - what this run is *not* going to reach,
which the CLI has printed since `cli_impl/prerun.py` and the window said
nothing at all about.
"""
from __future__ import annotations

import argparse
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import diagnosis as dx
import repo_pairing
from cli_impl import prerun
from models import TextBlock

try:
    from PySide6.QtWidgets import QApplication

    from analysis_modes import SOURCE_SITE
    from ui.app_state import AppState
    from ui.worker import audit_worker_for
except Exception:  # noqa: BLE001 - no Qt here is a skip, not a failure
    QApplication = None


class Pairing(unittest.TestCase):
    """`repo_pairing` is the join itself, shared by both surfaces."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()

    def write(self, name: str, text: str) -> None:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_a_passage_on_a_page_finds_the_file_that_wrote_it(self):
        self.write("src/Hero.tsx",
                   'export const Hero = () => <h1>Unlock the full potential '
                   'of your workflow</h1>;\n')
        index = repo_pairing.index_for_path(self.root)
        block = TextBlock(block_id="1", page_url="https://x.test/",
                          dom_path="h1",
                          text="Unlock the full potential of your workflow")
        self.assertEqual(repo_pairing.pair_blocks([block], index), 1)
        self.assertTrue(block.source_file.endswith("Hero.tsx"))
        self.assertTrue(block.source_line)

    def test_a_language_guessed_differently_on_each_side_still_matches(self):
        """`block_identity` is (text, language), and the two sides guess the
        language differently: a crawled page takes it from `<html lang>`, a
        `.tsx` file from the sentence. The text is the same text."""
        self.write("src/Hero.tsx", "<h1>Download the report</h1>\n")
        index = repo_pairing.index_for_path(self.root)
        block = TextBlock(block_id="1", page_url="u", dom_path="h1",
                          text="Download the report", language_hint="uk")
        self.assertEqual(repo_pairing.pair_blocks([block], index), 1)

    def test_a_passage_the_checkout_does_not_contain_is_left_alone(self):
        """Not a failure: WordPress writes `<html lang>` and most of `<head>`
        in `wp_head()`, and copy can arrive from a CMS. The checkout is
        genuine and explains none of that passage."""
        self.write("src/Hero.tsx", "export const Hero = () => <h1>Hello</h1>;\n")
        index = repo_pairing.index_for_path(self.root)
        block = TextBlock(block_id="1", page_url="https://x.test/",
                          dom_path="p", text="Something the CMS holds")
        self.assertEqual(repo_pairing.pair_blocks([block], index), 0)
        self.assertEqual(block.source_file, "")

    def test_no_checkout_pairs_nothing_and_says_so(self):
        block = TextBlock(block_id="1", page_url="u", dom_path="p", text="x")
        self.assertEqual(repo_pairing.pair_blocks([block], {}), 0)

    def test_one_passage_repeated_in_the_repo_resolves_to_one_place(self):
        self.write("src/A.tsx", "<p>Read the docs</p>\n")
        self.write("src/B.tsx", "<p>Read the docs</p>\n")
        index = repo_pairing.index_for_path(self.root)
        block = TextBlock(block_id="1", page_url="u", dom_path="p",
                          text="Read the docs")
        repo_pairing.pair_blocks([block], index)
        self.assertIn(block.source_file, {str(self.root / "src" / "A.tsx"),
                                          str(self.root / "src" / "B.tsx")})


class MissedDepthIsData(unittest.TestCase):
    """The CLI prints English lines with flag names in them; a window has
    neither a flag to type nor English to print. One source of truth, two
    renderings."""

    def args(self, **overrides):
        base = dict(repo=None, devserver=False, url=False, no_browser=False,
                    breakpoints=None, no_hints=False)
        base.update(overrides)
        return argparse.Namespace(**base)

    def test_a_site_with_no_checkout_is_a_missed_depth(self):
        found = prerun.missed("audit", "https://x.test", self.args(), is_url=True)
        self.assertIn(prerun.REPO, [code for code, _fields in found])

    def test_naming_the_checkout_answers_it(self):
        found = prerun.missed("audit", "https://x.test",
                              self.args(repo="/tmp/checkout"), is_url=True)
        self.assertNotIn(prerun.REPO, [code for code, _fields in found])

    def test_the_cli_still_prints_its_own_sentences(self):
        lines = prerun.hints("audit", "https://x.test", self.args(), is_url=True)
        self.assertTrue(lines)
        self.assertTrue(all(line.startswith(prerun.PREFIX) for line in lines))
        self.assertIn("--repo", " ".join(lines))

    def test_no_hints_silences_both_renderings(self):
        args = self.args(no_hints=True)
        self.assertEqual(prerun.missed("audit", "https://x.test", args, is_url=True), [])
        self.assertEqual(prerun.hints("audit", "https://x.test", args, is_url=True), [])

    def test_the_window_gets_notices_with_a_move_on_them(self):
        found = prerun.missed("audit", "https://x.test", self.args(), is_url=True)
        notices = dx.diagnose_missed_depth(found)
        self.assertIn(dx.MISSED_REPO, [n.kind for n in notices])
        repo_notice = next(n for n in notices if n.kind == dx.MISSED_REPO)
        self.assertIn(dx.PAIR_REPO, repo_notice.actions)

    def test_every_notice_reads_as_a_sentence_in_every_language(self):
        from i18n.translations import t

        notices = dx.diagnose_missed_depth([
            ("repo", {"target": "https://x.test"}),
            ("devserver", {"stack": "vite", "deps": True}),
            ("browser", {}),
            ("breakpoints", {}),
        ])
        self.assertEqual(len(notices), 4)
        for notice in notices:
            for lang in ("uk", "it", "en"):
                for key in (notice.title_key, notice.body_key):
                    text = t(key, lang, **notice.fields)
                    self.assertNotEqual(text, key, f"{key} has no {lang}")

    def test_an_unknown_code_is_skipped_rather_than_guessed_at(self):
        self.assertEqual(dx.diagnose_missed_depth([("something-new", {})]), [])


@unittest.skipIf(QApplication is None, "PySide6 not available")
class RunChoices(unittest.TestCase):
    def test_the_state_holds_both_new_choices(self):
        state = AppState()
        self.assertEqual(state.paired_repo, "")
        self.assertEqual(state.within, "")
        state.set_paired_repo("  /tmp/checkout  ")
        state.set_within("  .my-webpart  ")
        self.assertEqual(state.paired_repo, "/tmp/checkout")
        self.assertEqual(state.within, ".my-webpart")

    def test_within_reaches_the_audit_worker(self):
        worker, refusal = audit_worker_for(
            SOURCE_SITE, target="https://x.test", depth=0, max_pages=5,
            within=".my-webpart")
        self.assertEqual(refusal, "")
        self.assertEqual(worker.within, ".my-webpart")

    def test_a_settings_ceiling_exists_for_the_folder_walk(self):
        import config

        self.assertEqual(config.Settings().max_files, 5000)


if __name__ == "__main__":
    unittest.main()
