"""Repo mode reads source files as fragments, not as finished pages.

Both halves of that statement are checked here, because getting either one
wrong is what filled a real report with noise: a component is not missing a
doctype, and `onClick={close}` is not an inline event handler.
"""
import unittest

from audit import engine
from audit.base import RuleRegistry, is_binding
from models import FileResult


COMPONENT = (
    'export function Panel({ onClose }) {\n'
    '  return <div className="panel">\n'
    '    <button onClick={onClose} aria-label="Close">x</button>\n'
    '    <label htmlFor="q">Search</label>\n'
    '    <input id="q" onChange={update} value={query} />\n'
    '  </div>;\n'
    '}\n'
)

PAGE = (
    '<!DOCTYPE html><html lang="en"><head><title>Real page</title></head>'
    '<body><h1>Real page</h1><button onclick="go()">Go</button></body></html>'
)


def _run(path, text):
    return engine.analyze_files([FileResult(path=path, raw_text=text)], root=".")


def _rules(result):
    return {issue.rule_id for issue in result.issues()}


class Bindings(unittest.TestCase):
    def test_expression_kinds_are_recognised(self):
        self.assertEqual(is_binding("{onClose}"), "expression")
        self.assertEqual(is_binding("{{ title }}"), "mustache")
        self.assertEqual(is_binding("${url}"), "template")

    def test_a_literal_value_is_not_a_binding(self):
        self.assertEqual(is_binding("go()"), "")
        self.assertEqual(is_binding(""), "")
        self.assertEqual(is_binding(None), "")


class Fragments(unittest.TestCase):
    def test_a_component_is_not_missing_a_doctype_or_a_title(self):
        found = _rules(_run("src/Panel.tsx", COMPONENT))
        for rule in ("bp-doctype", "document-title", "html-lang", "page-has-h1"):
            self.assertNotIn(rule, found)

    def test_a_framework_handler_is_not_an_inline_handler(self):
        self.assertNotIn("bp-inline-handlers", _rules(_run("src/Panel.tsx", COMPONENT)))

    def test_a_field_labelled_with_htmlFor_counts_as_labelled(self):
        self.assertNotIn("control-name", _rules(_run("src/Panel.tsx", COMPONENT)))


class Pages(unittest.TestCase):
    def test_an_html_file_is_still_judged_as_a_page(self):
        # The same run over a real page must keep every page-level rule, or
        # the fix would have traded noise for blindness.
        result = _run("public/index.html", '<html><body><p>hi</p></body></html>')
        found = _rules(result)
        self.assertIn("bp-doctype", found)
        self.assertIn("document-title", found)

    def test_a_real_inline_handler_is_still_reported(self):
        self.assertIn("bp-inline-handlers", _rules(_run("public/index.html", PAGE)))

    def test_page_level_rules_exist_and_are_a_minority(self):
        rules = RuleRegistry.all_rules()
        page_level = [r.id for r in rules if getattr(r, "page_level", False)]
        self.assertTrue(page_level)
        self.assertLess(len(page_level), len(rules))


if __name__ == "__main__":
    unittest.main()
