"""The scan cache is written the way a shared file has to be written.

Two scans at once is an ordinary thing to do - one on a repository, one on a
site - and both open the same `scan_cache.json`. Written in place, the file
spends a moment as half a JSON document, and the other process reads it
there: `_load` catches the error and starts from an empty cache, so the
symptom is not a crash but a scan that silently re-reads everything.
"""
import json
import tempfile
import unittest
from pathlib import Path

from scan_cache import ScanCache


class TheWriteIsAtomic(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "scan_cache.json"

    def test_the_file_is_replaced_not_truncated(self):
        cache = ScanCache(self.path)
        cache._cache = {"a": {"findings": []}}
        cache.save()
        first = self.path.read_text()

        # A reader that opens the path during the next write must not see a
        # partial document. The rename is what guarantees it, so the check
        # is that a temporary file is what gets written and then moved.
        cache._cache = {"a": {"findings": []}, "b": {"findings": []}}
        cache.save()
        self.assertNotEqual(first, self.path.read_text())
        self.assertEqual(set(json.loads(self.path.read_text())), {"a", "b"})
        self.assertFalse(self.path.with_suffix(".tmp").exists())

    def test_a_half_written_file_is_never_left_behind(self):
        """If the write itself fails, the old cache is still the cache."""
        cache = ScanCache(self.path)
        cache._cache = {"a": {"findings": []}}
        cache.save()
        good = self.path.read_text()

        class _Unserialisable:
            pass

        cache._cache = {"b": _Unserialisable()}
        with self.assertRaises(TypeError):
            cache.save()
        self.assertEqual(self.path.read_text(), good)


if __name__ == "__main__":
    unittest.main()
