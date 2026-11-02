"""A page that says it is still loading is measured when it is done (T-2337).

Coach's /app showed a skeleton under `aria-busy="true"` while its data came
in, and the pass read that: no `<h1>`, and a card whose `aria-labelledby`
pointed at a heading not rendered yet.
"""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

LOADING = """<!DOCTYPE html><html lang="en"><head><title>App</title></head><body>
<main><div role="status" aria-busy="true" id="s">Loading</div></main>
<script>setTimeout(function() {
  document.querySelector('main').innerHTML = '<h1>Loaded</h1>';
}, %d);</script></body></html>"""


def _audit(page: str):
    from audit import browser, driver

    with TemporaryDirectory() as folder:
        path = Path(folder) / "page.html"
        path.write_text(page, encoding="utf-8")
        options = browser.BrowserAuditOptions(
            run_axe=False, run_htmlcs=False, run_states=False,
            run_measurements=False, allow_local_files=True, settle_ms=100,
            capture_html=True, capture_text=False)
        driver.ensure_headless_application()
        runner = driver.BrowserAuditRunner(options)
        try:
            return runner.audit(path.resolve().as_uri())
        finally:
            runner.close()


class InARealBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from audit import driver

        usable, reason = driver.available()
        if not usable:
            raise unittest.SkipTest(reason)

    def test_the_page_is_read_after_it_stops_being_busy(self):
        result = _audit(LOADING % 1200)
        self.assertIn("<h1>Loaded</h1>", result.html)
        self.assertNotIn("busy", result.engine_errors)

    def test_a_page_busy_for_ever_is_measured_anyway_and_says_so(self):
        from audit import driver

        with mock.patch.object(driver, "BUSY_WAIT_MS", 500):
            result = _audit(LOADING % 600000)
        self.assertIn("Loading", result.html)
        self.assertIn("busy", result.engine_errors)


if __name__ == "__main__":
    unittest.main()
