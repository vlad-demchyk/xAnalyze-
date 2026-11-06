"""A `>` inside a JSX attribute expression does not end the tag (T-1963).

Found by auditing xFormat: `onClick={() => go()}` closed the tag for the
parser, so the `onKeyDown`, `role` and `tabIndex` after it were lost and a
keyboard-operable control drew two findings. The same cut hid real ones too:
`autoFocus` and empty `<button … />` written after an arrow handler.
"""
import unittest

from repo_scanner import mask_jsx_attribute_expressions as mask


class TheMask(unittest.TestCase):
    def test_arrows_and_comparisons_inside_an_attribute_are_hidden(self):
        src = '<div onClick={() => go(a > b)} role="button">x</div>'
        out = mask(src)
        self.assertEqual(len(out), len(src))
        self.assertNotIn(">", out[:out.index('role')])
        self.assertIn('role="button">x</div>', out)

    def test_template_literals_and_nested_braces_are_followed(self):
        src = '<a title={`n${x > 1 ? "s" : ""}`} onClick={() => { if (a) { b(); } }}>t</a>'
        out = mask(src)
        self.assertTrue(out.endswith(">t</a>"))
        self.assertEqual(out.count(">"), 2)

    def test_lines_and_offsets_are_kept(self):
        src = '<div\n  onKeyDown={(e) => {\n    go();\n  }}\n>x</div>'
        out = mask(src)
        self.assertEqual(out.count("\n"), src.count("\n"))
        self.assertEqual(len(out), len(src))

    def test_markup_outside_attributes_is_left_alone(self):
        for src in ('const icons = { home: <img src="/h.png" /> };',
                    '{items.map((i) => <li key={i}>{i}</li>)}'):
            with self.subTest(src):
                self.assertEqual(mask(src), src)


class TheAuditReadsTheWholeTag(unittest.TestCase):
    def _found(self, body, path="src/A.tsx"):
        from audit.engine import _mask_for_audit, analyze_document

        src = "export function A({ go }) { return (\n" + body + "\n); }"
        return sorted(i.rule_id for i in analyze_document(
            _mask_for_audit(src, path), path, source_text=src,
            document_kind="fragment", syntax="jsx").issues
            if i.rule_id.startswith(("jsx-", "control-name")))

    def test_a_keyboard_operable_div_after_an_arrow_is_quiet(self):
        self.assertEqual(self._found(
            '<div onClick={() => go()} onKeyDown={(e) => { if (e.key === "Enter") go(); }} '
            'role="button" tabIndex={0}>Open</div>'), [])

    def test_an_empty_self_closing_button_after_an_arrow_is_found(self):
        self.assertIn("control-name", self._found(
            '<button id="del" onClick={() => remove(item)} />'))


if __name__ == "__main__":
    unittest.main()
