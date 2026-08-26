"""The three screens around a write (artboard 3j).

Each replaced a message box, and each is here for something a message box
could not do: say which files, say why this row is different, and say what
happened in four numbers that are not the same number.
"""
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QDialog
    import backups
    import replacements
    from file_writer import ReplacementPlan, apply_replacements
    from ui.window_parts.action_dialogs import (DecisionDialog,
                                                WriteConfirmDialog,
                                                WriteOutcomeDialog)
except Exception:  # noqa: BLE001 - no Qt here is a skip, not a failure
    QApplication = None


def _row(path, line, selected=True):
    return replacements.Replacement(f"{path}:{line}", "was", "becomes",
                                    replacements.MECHANICAL,
                                    replacements.TEXT, plan=object(),
                                    selected=selected, path=path, line=line)


@unittest.skipIf(QApplication is None, "PySide6 not available")
class Confirming(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_it_counts_the_rows_per_file_not_in_total(self):
        rows = [_row("a/Hero.tsx", 1), _row("a/Hero.tsx", 2),
                _row("a/uk.json", 3)]
        dialog = WriteConfirmDialog(rows, "en", root="a")
        # The button promises the total; the list breaks it down, which is
        # the thing somebody checks before saying yes.
        self.assertIn("3", dialog.write_btn.text())
        self.assertEqual(replacements.by_file(rows, "a"),
                         [("Hero.tsx", 2), ("uk.json", 1)])

    def test_an_unticked_row_is_not_counted(self):
        rows = [_row("a/Hero.tsx", 1), _row("a/uk.json", 2, selected=False)]
        self.assertEqual(replacements.by_file(rows, "a"), [("Hero.tsx", 1)])

    def test_the_backup_is_on_unless_it_is_switched_off(self):
        dialog = WriteConfirmDialog([_row("a.py", 1)], "en")
        self.assertTrue(dialog.backup)
        dialog.backup_switch.setChecked(False)
        self.assertFalse(dialog.backup)


@unittest.skipIf(QApplication is None, "PySide6 not available")
class Deciding(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    class _Plan:
        path, start, end, line, kind = "F.tsx", 0, 1, 264, "replace"
        original = '<img src="/i.svg">'
        replacement = '<img src="/i.svg" alt="…">'
        rule_id, needs_input = "image-alt", "somebody has to look at it"

        def with_text(self, text):
            filled = Deciding._Plan()
            filled.replacement = self.replacement.replace("…", text)
            filled.needs_input = ""
            return filled

    def _item(self):
        return replacements.Replacement(
            "F.tsx:264 · image-alt", '<img src="/i.svg">',
            '<img src="/i.svg" alt="…">', replacements.DECISION,
            replacements.MARKUP, plan=self._Plan(),
            reason="somebody has to look at it")

    def test_an_empty_answer_is_not_an_answer(self):
        """Accepting it would write the placeholder the rule still carries."""
        item = self._item()
        dialog = DecisionDialog(item, "en")
        dialog._on_self()
        self.assertEqual(dialog.result(), 0)  # still open
        self.assertEqual(item.source, replacements.DECISION)

    def test_writing_the_value_answers_it(self):
        item = self._item()
        dialog = DecisionDialog(item, "en")
        dialog.value_edit.setText("A magnifying glass")
        dialog._on_self()
        self.assertEqual(dialog.choice, DecisionDialog.SELF)
        self.assertEqual(item.source, replacements.ANSWERED)
        self.assertIn("A magnifying glass", item.after)

    def test_marking_it_decorative_is_a_claim_the_person_makes(self):
        item = self._item()
        dialog = DecisionDialog(item, "en")
        dialog._on_decorative()
        self.assertEqual(dialog.choice, DecisionDialog.DECORATIVE)
        self.assertEqual(item.source, replacements.ANSWERED)

    def test_handing_it_to_the_model_leaves_the_row_untouched(self):
        """The screen that owns the provider does that, not this dialog."""
        item = self._item()
        dialog = DecisionDialog(item, "en")
        dialog._on_model()
        self.assertEqual(dialog.choice, DecisionDialog.MODEL)
        self.assertEqual(item.source, replacements.DECISION)


@unittest.skipIf(QApplication is None, "PySide6 not available")
class Reporting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_undo_puts_the_files_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "page.html")
            Path(path).write_text("before", encoding="utf-8")
            result = apply_replacements([ReplacementPlan(
                file_path=path, abs_start=0, abs_end=6,
                original_text="before", new_text="after")])
            self.assertEqual(result.passages_applied, 1)
            self.assertEqual(Path(path).read_text(encoding="utf-8"), "after")

            outcome = replacements.WriteOutcome(
                written=1, files_changed=[path],
                backups=backups.existing_for([path]))
            dialog = WriteOutcomeDialog(outcome, "en")
            self.assertTrue(dialog.undo_btn.isEnabled())
            dialog._on_undo()
            self.assertTrue(dialog.undo_requested)
            self.assertEqual(Path(path).read_text(encoding="utf-8"), "before")

    def test_without_a_backup_there_is_nothing_to_undo(self):
        outcome = replacements.WriteOutcome(written=1, files_changed=["a"])
        dialog = WriteOutcomeDialog(outcome, "en")
        self.assertFalse(dialog.undo_btn.isEnabled())

    def test_a_write_without_backups_leaves_none(self):
        """The switch in the confirmation is a real choice, not decoration."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "page.html")
            Path(path).write_text("before", encoding="utf-8")
            apply_replacements([ReplacementPlan(
                file_path=path, abs_start=0, abs_end=6,
                original_text="before", new_text="after")], backup=False)
            self.assertEqual(Path(path).read_text(encoding="utf-8"), "after")
            self.assertFalse(backups.exists(path))

    def test_the_skipped_detail_is_behind_its_own_button(self):
        outcome = replacements.WriteOutcome(written=1, skipped=["a: stale"])
        dialog = WriteOutcomeDialog(outcome, "en")
        self.assertFalse(dialog.detail_label.isVisibleTo(dialog))
        dialog.show_btn.click()
        self.assertTrue(dialog.detail_label.isVisibleTo(dialog))


if __name__ == "__main__":
    unittest.main()


@unittest.skipIf(QApplication is None, "PySide6 not available")
class Progressing(unittest.TestCase):
    """The screen a batch of billable calls runs behind (artboard 3j)."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _items(self, n=12):
        from models import CodeBlock, Confidence, TextSpan

        return [(CodeBlock(block_id=str(i), file_path="/x/Hero.tsx", start=0,
                           end=1, text="a", line_number=40 + i),
                 TextSpan(block_id=str(i), start=0, end=1, score=0.9,
                          confidence=Confidence.HIGH, detector_name="t"))
                for i in range(n)]

    def _dialog(self, n=12):
        from ui.window_parts.action_dialogs import RewriteProgressDialog

        return RewriteProgressDialog(self._items(n), account="xFormat",
                                     lang="en")

    def test_the_cost_is_exact_not_an_estimate(self):
        """One request is billed per passage, so the number is the length of
        the list rather than a guess with a tilde in front of it."""
        dialog = self._dialog(12)
        self.assertIn("12", dialog.cost.text())
        self.assertIn("xFormat", dialog.cost.text())

    def test_the_log_names_what_is_being_written_now(self):
        dialog = self._dialog(12)
        dialog.set_progress(3, 12)
        self.assertIn("Hero.tsx:43", dialog.log.text())
        self.assertIn("8", dialog.log.text())  # queued behind it

    def test_the_last_line_has_nothing_queued_behind_it(self):
        dialog = self._dialog(2)
        dialog.set_progress(2, 2)
        self.assertNotIn("queued", dialog.log.text())

    def test_stopping_keeps_what_already_came_back(self):
        stopped = []
        dialog = self._dialog(4)
        dialog.stopped.connect(lambda: stopped.append(True))
        dialog.stop_btn.click()
        self.assertEqual(stopped, [True])
        self.assertFalse(dialog.stop_btn.isEnabled())
        self.assertIn("paid", dialog.log.text())
