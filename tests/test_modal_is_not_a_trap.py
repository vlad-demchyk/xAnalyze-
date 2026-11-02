"""A dialog that keeps Tab inside it is not a keyboard trap (T-2337).

Coach's welcome tour is `role="dialog" aria-modal="true"`, cycles Tab
through its own buttons and closes on Escape. Its document-level handler
cancels Tab, so every header link behind it was reported as
`state:keyboard-trap` (2.1.2) on /app, /app/student and /app/teacher.
"""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

_TAB_EATER = """<script>
document.addEventListener('keydown', function(e) {
  if (e.key === 'Tab') { e.preventDefault(); }
});
</script>"""

TOUR = """<!DOCTYPE html><html lang="en"><head><title>App</title></head><body>
<header><a href="/a">Home</a> <a href="/b">Lessons</a></header>
<main><h1>App</h1></main>
<div role="dialog" aria-modal="true" aria-labelledby="t" style="position:fixed;top:20px;left:20px;background:#fff;padding:20px">
  <h2 id="t">Welcome</h2><button type="button">Next</button> <button type="button">Skip</button>
</div>""" + _TAB_EATER + "</body></html>"

TRAP = """<!DOCTYPE html><html lang="en"><head><title>App</title></head><body>
<main><h1>App</h1><a href="/a">Home</a> <a href="/b">Lessons</a></main>""" + _TAB_EATER + "</body></html>"

SEALED = """<!DOCTYPE html><html lang="en"><head><title>App</title></head><body>
<main><h1>App</h1><a href="/a">Home</a></main>
<div role="dialog" aria-modal="true" aria-label="Wait" tabindex="0" style="position:fixed;top:20px;left:20px;background:#fff;padding:20px">
  <p>Please wait</p></div>""" + _TAB_EATER + "</body></html>"


def _traps(page: str) -> list:
    from audit import browser, driver

    with TemporaryDirectory() as folder:
        path = Path(folder) / "page.html"
        path.write_text(page, encoding="utf-8")
        options = browser.BrowserAuditOptions(
            run_axe=False, run_htmlcs=False, run_states=True,
            run_measurements=False, allow_local_files=True, settle_ms=200)
        driver.ensure_headless_application()
        runner = driver.BrowserAuditRunner(options)
        try:
            issues = runner.audit(path.resolve().as_uri()).issues
        finally:
            runner.close()
    return [i for i in issues if i.rule_id == "state:keyboard-trap"]


class InARealBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from audit import driver

        usable, reason = driver.available()
        if not usable:
            raise unittest.SkipTest(reason)

    def test_an_open_modal_with_a_way_out_is_not_a_trap(self):
        self.assertEqual(_traps(TOUR), [])

    def test_a_page_that_eats_tab_with_no_modal_is_still_a_trap(self):
        self.assertTrue(_traps(TRAP))

    def test_a_modal_with_no_way_out_is_still_a_trap(self):
        self.assertTrue(_traps(SEALED))


if __name__ == "__main__":
    unittest.main()
