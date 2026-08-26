"""The replacement list: what it collects, what it writes, what it refuses.

Artboard 3l turns three separate write buttons into one list read before
anything happens, so the tests here are mostly about *selection*: which rows
arrive ticked, which rows cannot be ticked at all, and that the button's
promised count is the number of edits that actually reach the disk.
"""
import os
import tempfile
import unittest
from pathlib import Path

import replacements
import unicode_rules
from audit.base import Issue
from audit.engine import AccessibilityResult, DocumentReport
from models import (CodeBlock, Confidence, FileResult, RepoAnalysisResult,
                    TextSpan)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ZERO_WIDTH = "​"


def _repo_result(tmp: str, text: str, spans):
    """A one-file repository scan whose block really is that file's text."""
    path = os.path.join(tmp, "hero.json")
    Path(path).write_text(text, encoding="utf-8")
    block = CodeBlock(block_id="b1", file_path=path, start=0, end=len(text),
                      text=text, line_number=1)
    return RepoAnalysisResult(root_dir=tmp,
                              files=[FileResult(path=path, blocks=[block],
                                                raw_text=text)],
                              spans=spans), path


def _span(start, end, replacement=None, confidence=Confidence.HIGH):
    return TextSpan(block_id="b1", start=start, end=end, score=0.9,
                    confidence=confidence, detector_name="test",
                    replacement=replacement)


class Visible(unittest.TestCase):
    """`unicode_rules.visible`, the shared way to show what cannot be seen."""

    def test_names_an_invisible_character(self):
        self.assertEqual(unicode_rules.visible(f"299{ZERO_WIDTH} UAH"),
                         "299<U+200B> UAH")

    def test_leaves_ordinary_text_alone(self):
        self.assertEqual(unicode_rules.visible("299 UAH"), "299 UAH")


class Collecting(unittest.TestCase):
    """Which rows a run produces, and how each of them arrives."""

    def test_a_character_finding_is_mechanical_and_pre_selected(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = f"299{ZERO_WIDTH} UAH"
            result, _ = _repo_result(tmp, text, [_span(3, 4, replacement="")])
            rows = replacements.from_text_result(result, {}, root=tmp)
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row.source, replacements.MECHANICAL)
            self.assertTrue(row.selected)
            self.assertEqual(row.before, "<U+200B>")
            self.assertTrue(row.writable)

    def test_a_model_draft_is_never_pre_selected(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = "In today's digital world, quality matters."
            result, _ = _repo_result(tmp, text, [_span(0, len(text))])
            drafts = {("b1", 0, len(text)): "We check text for AI markers."}
            rows = replacements.from_text_result(result, drafts, root=tmp)
            self.assertEqual([r.source for r in rows], [replacements.DRAFT])
            self.assertFalse(rows[0].selected)
            self.assertTrue(rows[0].writable)

    def test_a_flagged_passage_with_no_draft_is_not_a_row(self):
        """Nothing to write is not a row: the list is what *would* change."""
        with tempfile.TemporaryDirectory() as tmp:
            text = "In today's digital world, quality matters."
            result, _ = _repo_result(tmp, text, [_span(0, len(text))])
            self.assertEqual(replacements.from_text_result(result, {}, tmp), [])

    def test_a_low_confidence_span_is_not_a_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = f"299{ZERO_WIDTH} UAH"
            result, _ = _repo_result(
                tmp, text, [_span(3, 4, replacement="", confidence=Confidence.LOW)])
            self.assertEqual(replacements.from_text_result(result, {}, tmp), [])

    def test_an_audit_correction_is_mechanical_a_decision_is_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "index.html")
            Path(path).write_text(
                '<html lang="en"><body>\n<button class="s"></button>\n'
                '<img src="/icon.svg">\n</body></html>', encoding="utf-8")
            audit = AccessibilityResult(root=tmp, mode="repo", documents=[
                DocumentReport(source=path, issues=[
                    Issue(rule_id="button-name", severity="serious", line=2,
                          snippet='<button class="s"></button>',
                          fix_snippet='<button class="s" aria-label="Search">'
                                      '</button>',
                          engine="static", source=path),
                    Issue(rule_id="image-alt", severity="critical", line=3,
                          snippet='<img src="/icon.svg">',
                          fix_snippet='<img src="/icon.svg" alt="">',
                          engine="static", source=path),
                ])])
            rows, _skipped = replacements.from_audit_result(audit, root=tmp)
            by_rule = {r.where.split(" · ")[-1]: r for r in rows}
            self.assertEqual(by_rule["button-name"].source,
                             replacements.MECHANICAL)
            self.assertTrue(by_rule["button-name"].selected)
            decision = by_rule["image-alt"]
            self.assertEqual(decision.source, replacements.DECISION)
            self.assertFalse(decision.selected)
            self.assertFalse(decision.writable)
            self.assertTrue(decision.reason)

    def test_counts_split_the_list_by_source(self):
        rows = [
            replacements.Replacement("a", "x", "y", replacements.MECHANICAL,
                                     replacements.TEXT, plan=object()),
            replacements.Replacement("b", "x", "y", replacements.DRAFT,
                                     replacements.TEXT, plan=object()),
            replacements.Replacement("c", "x", "", replacements.DECISION,
                                     replacements.MARKUP, plan=object()),
        ]
        self.assertEqual(replacements.counts(rows),
                         {replacements.MECHANICAL: 1, replacements.DRAFT: 1,
                          replacements.DECISION: 1})


class Writing(unittest.TestCase):
    """Only the ticked rows, and exactly the ticked rows, reach the disk."""

    def test_writes_the_selected_row_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = f"299{ZERO_WIDTH} UAH. In today's digital world."
            second = text.index(" In") + 1
            result, path = _repo_result(tmp, text, [
                _span(3, 4, replacement=""),
                _span(second, len(text)),
            ])
            drafts = {("b1", second, len(text)): "We measured it."}
            rows = replacements.from_text_result(result, drafts, root=tmp)
            self.assertEqual(len(rows), 2)

            outcome = replacements.write(rows)
            self.assertEqual(outcome.written, 1)
            after = Path(path).read_text(encoding="utf-8")
            self.assertNotIn(ZERO_WIDTH, after)
            # The draft was not ticked, so the sentence is untouched.
            self.assertIn("In today's digital world.", after)

    def test_a_decision_is_not_written_even_when_marked(self):
        row = replacements.Replacement("a", "<img>", "", replacements.DECISION,
                                       replacements.MARKUP, plan=object(),
                                       reason="what is in the picture")
        row.selected = True
        self.assertEqual(replacements.selected([row]), [])
        self.assertEqual(replacements.write([row]).written, 0)


class LettingTheModelAnswer(unittest.TestCase):
    """A decision a model answered is a draft, not a mechanical row."""

    class _Provider:
        def __init__(self, answer):
            self.answer = answer

        def analyze(self, system, prompt):
            return self.answer

    def _decision_rows(self, tmp):
        path = os.path.join(tmp, "index.html")
        Path(path).write_text('<body>\n<img src="/icon.svg">\n</body>',
                              encoding="utf-8")
        audit = AccessibilityResult(root=tmp, mode="repo", documents=[
            DocumentReport(source=path, issues=[
                Issue(rule_id="image-alt", severity="critical", line=2,
                      snippet='<img src="/icon.svg">',
                      fix_snippet='<img src="/icon.svg" alt="…">',
                      engine="static", source=path)])])
        rows, _ = replacements.from_audit_result(audit, root=tmp)
        return rows

    def test_an_answered_decision_becomes_an_unticked_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = self._decision_rows(tmp)
            self.assertEqual(rows[0].source, replacements.DECISION)
            answered = replacements.fill_decisions(
                rows, self._Provider("<<<1>>>\nA magnifying glass"),
                page_text="Search the site")
            self.assertEqual(answered, 1)
            self.assertEqual(rows[0].source, replacements.DRAFT)
            self.assertIn("A magnifying glass", rows[0].after)
            self.assertFalse(rows[0].selected)
            self.assertTrue(rows[0].writable)

    def test_a_model_that_skips_leaves_the_decision_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = self._decision_rows(tmp)
            answered = replacements.fill_decisions(
                rows, self._Provider("<<<1>>>\nSKIP"), page_text="")
            self.assertEqual(answered, 0)
            self.assertEqual(rows[0].source, replacements.DECISION)
            self.assertFalse(rows[0].writable)


class Exporting(unittest.TestCase):
    """The same list as a file, for a review that happens somewhere else."""

    def test_markdown_names_every_source_and_the_open_decision(self):
        rows = [
            replacements.Replacement("index.html:2 · button-name", "<button>",
                                     '<button aria-label="Search">',
                                     replacements.MECHANICAL,
                                     replacements.MARKUP, plan=object(),
                                     path="/tmp/index.html", line=2),
            replacements.Replacement("index.html:3 · image-alt", "<img>",
                                     '<img alt="">', replacements.DECISION,
                                     replacements.MARKUP, plan=object(),
                                     reason="what the picture shows",
                                     path="/tmp/index.html", line=3),
        ]
        text = replacements.render_markdown(rows)
        self.assertIn("1 mechanical", text)
        self.assertIn("1 need a decision", text)
        self.assertIn("what the picture shows", text)
        self.assertIn('<button aria-label="Search">', text)

    def test_the_file_is_offered_under_the_run_s_date(self):
        import datetime
        self.assertEqual(
            replacements.default_filename(datetime.date(2026, 8, 26)),
            "replacements-2026-08-26.md")


try:
    from PySide6.QtWidgets import QApplication
    from ui.window_parts.replacement_list import ReplacementListDialog
except Exception:  # noqa: BLE001 - no Qt here is a skip, not a failure
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 not available")
class Screen(unittest.TestCase):
    """The screen itself: the promise on the button, and what cannot be ticked."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _dialog(self, skipped=None):
        rows = [
            replacements.Replacement("uk.json", "299<U+200B>", "299",
                                     replacements.MECHANICAL,
                                     replacements.TEXT, plan=object(),
                                     selected=True),
            replacements.Replacement("Hero.tsx:41", "In today's world",
                                     "We measured it", replacements.DRAFT,
                                     replacements.TEXT, plan=object()),
            replacements.Replacement("Feature.tsx:264 · image-alt", "<img>",
                                     '<img alt="">', replacements.DECISION,
                                     replacements.MARKUP, plan=object(),
                                     reason="what the picture shows"),
        ]
        return ReplacementListDialog(rows, skipped=skipped or [], lang="en")

    def test_the_button_says_how_many_it_will_write(self):
        dialog = self._dialog()
        self.assertIn("1", dialog.write_btn.text())
        dialog.rows[1].check.setChecked(True)
        self.assertIn("2", dialog.write_btn.text())
        self.assertIn("2 of 3", dialog.footer.text())

    def test_a_decision_cannot_be_ticked(self):
        dialog = self._dialog()
        self.assertFalse(dialog.rows[2].check.isEnabled())
        self.assertIn("what the picture shows", dialog.rows[2].after.toolTip())

    def test_nothing_selected_disables_the_write_button(self):
        dialog = self._dialog()
        dialog.rows[0].check.setChecked(False)
        self.assertFalse(dialog.write_btn.isEnabled())

    def test_findings_that_never_became_an_edit_are_named(self):
        dialog = self._dialog(skipped=["image-alt: this is a page on the web"])
        self.assertIn("1", dialog.footer.text())
        self.assertIn("never became an edit", dialog.footer.text())

    def test_markup_is_shown_as_text_not_drawn_as_markup(self):
        """`<img src=...>` in a label is an image to Qt unless it is told."""
        from PySide6.QtCore import Qt

        dialog = self._dialog()
        for cell in (dialog.rows[2].before, dialog.rows[2].after):
            self.assertEqual(cell.textFormat(), Qt.TextFormat.PlainText)

    def test_a_long_passage_does_not_push_a_column_out_of_view(self):
        """The measurement the first render of this screen failed.

        A passage of two thousand characters made the row wider than the
        area showing it, so the source column - the answer to "did a model
        write this" - sat off the right-hand edge behind a horizontal
        scrollbar, on every row of the list.
        """
        dialog = self._dialog()
        dialog.rows[1].before.setText("word " * 400)
        dialog.resize(1080, 620)
        dialog.show()
        self.app.processEvents()
        self.app.processEvents()
        viewport = dialog.scroll.viewport().width()
        row = dialog.rows[1]
        self.assertLessEqual(row.width(), viewport)
        chip = row.source
        right_edge = chip.mapTo(row, chip.rect().bottomRight()).x()
        self.assertLessEqual(right_edge, viewport)
        dialog.close()

    def test_the_model_button_appears_only_with_a_decision_and_a_provider(self):
        without = self._dialog()
        self.assertFalse(without.fill_btn.isVisible())
        with_fill = ReplacementListDialog(list(without.items), lang="en",
                                          on_fill=lambda items: 0)
        self.assertIn("1", with_fill.fill_btn.text())

    def test_the_header_counts_all_three_sources(self):
        dialog = self._dialog()
        self.assertIn("1 mechanical", dialog.summary.text())
        self.assertIn("1 model drafts", dialog.summary.text())
        self.assertIn("1 need a decision", dialog.summary.text())


if __name__ == "__main__":
    unittest.main()


@unittest.skipIf(QApplication is None, "PySide6 not available")
class OneWriteSurface(unittest.TestCase):
    """The audit's corrections have one way to reach the disk, not two."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_fix_on_disk_opens_the_list(self):
        from ui.main_window import MainWindow

        window = MainWindow()
        opened = []
        window._open_replacement_list = lambda: opened.append(True)
        window._on_fix_on_disk_clicked()
        self.assertEqual(opened, [True])
        window.close()
        window.deleteLater()

    def test_the_view_model_no_longer_writes_audit_fixes_itself(self):
        """The second surface, named so it cannot come back quietly."""
        from ui.view_model import MainViewModel

        for gone in ("fix_on_disk", "apply_fix_with_ai", "fix_confirm_needed"):
            self.assertFalse(hasattr(MainViewModel, gone), gone)
