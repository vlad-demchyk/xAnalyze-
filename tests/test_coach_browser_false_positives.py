"""Browser-pass false positives found on Coach's landing (T-2337)."""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from audit.base import MINOR

FAQ = """<!DOCTYPE html><html lang="uk"><head><title>FAQ</title><style>
  summary { outline: none; list-style: none; }
  details:has(summary:focus-visible) { outline: 3px solid #4338ca; outline-offset: 2px; }
  .bare:focus { outline: none; }
</style></head><body><main><h1>FAQ</h1>
<details><summary>Скільки коштує?</summary><p>Нічого.</p></details>
<p><a class="bare" href="/x">Без кільця</a></p>
</main></body></html>"""

LOGO = """<!DOCTYPE html><html lang="uk"><head><title>Coach</title><style>
  body { background: #fff; color: #111; }
  .brand-dot { color: #c7d2fe; }
  .pale { color: #c7d2fe; }
</style></head><body><header><a class="brand" href="/" aria-label="Coach">Coach<span class="brand-dot">.</span></a></header>
<main><h1>Головна</h1><p class="pale">Блідий текст, який читають.</p></main></body></html>"""


def _links(n: int, prefix: str) -> str:
    return "".join(f'<p><a href="/{prefix}{i}">{prefix} {i}</a></p>' for i in range(n))


SIDEBAR = ("""<!DOCTYPE html><html lang="uk"><head><title>Docs</title><style>
  body { margin: 0; } .wrap { display: flex; gap: 40px; }
  article { width: 700px; } p { margin: 0 0 120px; }
  aside { width: 240px; } .toc { position: sticky; top: 0; }
  .toc a, .side a { display: block; margin-bottom: 8px; }
</style></head><body><main><h1>Довідка</h1><div class="wrap"><article>"""
           + _links(8, "s") + """</article><aside><nav class="toc" aria-label="На цій сторінці">"""
           + "".join(f'<a href="#s{i}">s {i}</a>' for i in range(7))
           + """</nav></aside></div></main></body></html>""")

COLUMNS = ("""<!DOCTYPE html><html lang="uk"><head><title>Cols</title><style>
  .wrap { display: flex; gap: 40px; } .col { width: 300px; } p { margin: 0 0 80px; }
</style></head><body><main><h1>Колонки</h1><div class="wrap"><div class="col">"""
           + _links(6, "a") + '</div><div class="col">' + _links(6, "b")
           + "</div></div></main></body></html>")

REVERSED = ("""<!DOCTYPE html><html lang="uk"><head><title>Rev</title><style>
  .list { display: flex; flex-direction: column-reverse; } .list a { margin: 0 0 80px; }
</style></head><body><main><h1>Навпаки</h1><div class="list">"""
            + "".join(f'<a href="/r{i}">r {i}</a>' for i in range(6))
            + "</div></main></body></html>")


def _audit(page: str, **engines) -> list:
    from audit import browser, driver

    with TemporaryDirectory() as folder:
        path = Path(folder) / "page.html"
        path.write_text(page, encoding="utf-8")
        options = browser.BrowserAuditOptions(
            run_axe=False, run_measurements=False, allow_local_files=True,
            settle_ms=200, **engines)
        driver.ensure_headless_application()
        runner = driver.BrowserAuditRunner(options)
        try:
            return runner.audit(path.resolve().as_uri()).issues
        finally:
            runner.close()


class InARealBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from audit import driver

        usable, reason = driver.available()
        if not usable:
            raise unittest.SkipTest(reason)

    def test_a_ring_drawn_on_the_details_counts_for_its_summary(self):
        found = [i for i in _audit(FAQ, run_htmlcs=False, run_states=True)
                 if i.rule_id == "state:focus-not-visible"]
        snippets = " ".join(i.snippet for i in found)
        self.assertNotIn("<summary", snippets)
        # The control: a link that really has no visible focus.
        self.assertIn("bare", snippets)

    def test_logo_text_is_exempt_and_body_text_is_not(self):
        contrast = [i for i in _audit(LOGO, run_htmlcs=True, run_states=False)
                    if i.rule_id == "htmlcs:1_4_3"]
        dot = [i for i in contrast if "brand-dot" in i.snippet]
        pale = [i for i in contrast if "pale" in i.snippet]
        self.assertTrue(dot and pale, [i.snippet for i in contrast])
        self.assertEqual(dot[0].severity, MINOR)
        self.assertTrue(dot[0].details["logo"])
        self.assertNotEqual(pale[0].severity, MINOR)


class FocusOrder(unittest.TestCase):
    setUpClass = InARealBrowser.setUpClass

    def mismatches(self, page: str) -> list:
        return [i for i in _audit(page, run_htmlcs=False, run_states=True)
                if i.rule_id == "state:focus-order-mismatch"]

    def test_a_sticky_table_of_contents_after_the_article_is_in_order(self):
        # Coach's help: "On this page" pinned at the top, after the article.
        self.assertEqual(self.mismatches(SIDEBAR), [])

    def test_a_second_column_to_the_right_starts_from_the_top(self):
        self.assertEqual(self.mismatches(COLUMNS), [])

    def test_a_column_shown_in_reverse_is_still_a_mismatch(self):
        self.assertTrue(self.mismatches(REVERSED))


if __name__ == "__main__":
    unittest.main()
