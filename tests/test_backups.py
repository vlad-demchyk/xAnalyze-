"""One backup rule, shared by both writers.

The tool writes to disk in two places — the character fixes from the text
scan and the corrections from the audit — and the promise both make is the
same: whatever happens, the file can be put back the way the user had it.
That promise lives here so it cannot drift apart into two versions.
"""
import os
import tempfile
import unittest

import backups


class BackupTests(unittest.TestCase):

    def setUp(self):
        handle, self.path = tempfile.mkstemp(suffix=".html")
        with os.fdopen(handle, "w", encoding="utf-8") as out:
            out.write("original")
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        for path in (self.path, backups.path_for(self.path)):
            if os.path.exists(path):
                os.unlink(path)

    def read(self, path):
        with open(path, encoding="utf-8") as handle:
            return handle.read()

    def test_the_first_copy_is_the_one_kept(self):
        """A second run must not overwrite the first backup, or undo returns
        the file to the state between two runs instead of to the user's."""
        backups.take(self.path, "original")
        second = backups.take(self.path, "already changed once")
        self.assertEqual(second, "")
        self.assertEqual(self.read(backups.path_for(self.path)), "original")

    def test_restore_returns_the_file_and_clears_the_backup(self):
        backups.take(self.path, "original")
        with open(self.path, "w", encoding="utf-8") as out:
            out.write("changed")
        restored, problems = backups.restore([self.path])
        self.assertEqual(restored, [self.path])
        self.assertEqual(problems, [])
        self.assertEqual(self.read(self.path), "original")
        self.assertFalse(os.path.exists(backups.path_for(self.path)))

    def test_a_file_with_no_backup_is_reported_not_silently_skipped(self):
        restored, problems = backups.restore([self.path])
        self.assertEqual(restored, [])
        self.assertIn("nothing to go back to", problems[0])

    def test_existing_for_lists_only_what_can_be_restored(self):
        self.assertEqual(backups.existing_for([self.path]), [])
        backups.take(self.path, "original")
        self.assertEqual(backups.existing_for([self.path, self.path]), [self.path])


class BothWritersUseItTests(unittest.TestCase):
    """The point of the module: neither writer keeps its own copy of the rule."""

    def test_the_audit_writer_goes_through_it(self):
        import audit.fixer as fixer_module
        self.assertIs(fixer_module.backups, backups)

    def test_the_character_writer_goes_through_it(self):
        import file_writer
        self.assertIs(file_writer.backups, backups)


if __name__ == "__main__":
    unittest.main()
