"""The checks that only exist because the file is JSX.

Two things are being defended here, and the second one is the reason the
module was hard to write:

* the findings fire on the JSX spellings (`htmlFor`, `onClick`,
  `dangerouslySetInnerHTML`), which no HTML document has;
* they stay **silent** on a component. An HTML parser lowercases tag names,
  so `<Button onClick={x}>` arrives as `button`, and a rule that believed the
  parser would tell every design system that its button needs a keyboard
  handler it already has.
"""
from __future__ import annotations

import unittest

import audit
from audit.explanations import render


def findings(markup: str, source: str = "Component.tsx", syntax: str = "jsx"):
    report = audit.analyze_document(markup, source, document_kind="fragment",
                                    syntax=syntax)
    return [issue for issue in report.issues if issue.rule_id.startswith("jsx-")]


def rule_ids(markup: str, **kwargs) -> set:
    return {issue.rule_id for issue in findings(markup, **kwargs)}


class SyntaxGate(unittest.TestCase):
    def test_the_pack_is_silent_on_html(self):
        markup = ('<div onclick="go()"><label>Email</label>'
                  '<a onclick="go()">x</a></div>')
        self.assertEqual(findings(markup, "page.html", syntax="html"), [])

    def test_a_tsx_file_is_read_as_jsx(self):
        from audit.engine import _syntax_of

        self.assertEqual(_syntax_of("src/features/A.tsx"), "jsx")
        self.assertEqual(_syntax_of("src/features/A.jsx"), "jsx")
        self.assertEqual(_syntax_of("public/index.html"), "html")


class LabelAssociation(unittest.TestCase):
    def test_a_label_with_neither_htmlfor_nor_a_field_is_reported(self):
        self.assertIn("jsx-label-not-associated", rule_ids("<label>Email</label>"))

    def test_htmlfor_is_an_association(self):
        self.assertEqual(findings('<label htmlFor={id}>Email</label>'), [])

    def test_a_wrapped_field_is_an_association(self):
        self.assertEqual(findings("<label>Email <input /></label>"), [])

    def test_a_wrapped_component_is_assumed_to_render_the_field(self):
        """`<Input />` very probably is the input, and this file cannot see
        inside it. Recall given up on purpose: a false 'your label is broken'
        on a working form is what teaches people to stop reading the list."""
        self.assertEqual(findings("<label>City <Select /></label>"), [])


class KeyboardReachability(unittest.TestCase):
    def test_a_click_handler_on_a_div_is_two_separate_findings(self):
        """Operable and announced are different questions: adding onKeyDown
        makes the div usable by keyboard and still leaves it unreachable."""
        self.assertEqual(rule_ids("<div onClick={go}>go</div>"),
                         {"jsx-click-without-key", "jsx-noninteractive-handler"})

    def test_a_key_handler_answers_only_the_keyboard_question(self):
        self.assertEqual(rule_ids("<div onClick={go} onKeyDown={k}>go</div>"),
                         {"jsx-noninteractive-handler"})

    def test_role_and_tabindex_together_settle_it(self):
        markup = '<div onClick={go} onKeyDown={k} role="button" tabIndex={0}>go</div>'
        self.assertEqual(findings(markup), [])

    def test_a_real_button_is_never_reported(self):
        self.assertEqual(findings("<button onClick={go}>go</button>"), [])

    def test_a_component_is_not_a_tag(self):
        self.assertEqual(findings("<Button onClick={go}>go</Button>"), [])

    def test_a_namespaced_component_is_not_a_tag_either(self):
        self.assertEqual(findings("<Menu.Item onClick={go}>go</Menu.Item>"), [])

    def test_stopping_the_event_is_not_an_action(self):
        """The card inside a click-to-close overlay. Asking for a keyboard
        handler here asks for one for a gesture that does nothing."""
        markup = '<div className="card" onClick={(e) => e.stopPropagation()}>x</div>'
        self.assertEqual(findings(markup), [])

    def test_a_handler_that_stops_the_event_and_then_acts_is_an_action(self):
        markup = '<div onClick={(e) => { e.stopPropagation(); onSave(); }}>x</div>'
        self.assertIn("jsx-click-without-key", rule_ids(markup))


class TabOrder(unittest.TestCase):
    def test_tabindex_on_a_static_element_is_a_stop_with_nothing_behind_it(self):
        self.assertEqual(rule_ids("<li tabIndex={0}>x</li>"),
                         {"jsx-tabindex-on-static"})

    def test_minus_one_is_a_scripted_focus_target_and_not_in_the_tab_order(self):
        self.assertEqual(findings("<div tabIndex={-1}>x</div>"), [])

    def test_an_element_that_does_something_is_the_other_rules_business(self):
        self.assertNotIn("jsx-tabindex-on-static",
                         rule_ids("<div tabIndex={0} onClick={go}>x</div>"))


class AnchorsAndFocus(unittest.TestCase):
    def test_an_anchor_with_a_handler_and_no_href_is_one_finding_not_three(self):
        self.assertEqual(rule_ids("<a onClick={go}>x</a>"),
                         {"jsx-anchor-not-a-link"})

    def test_a_hash_href_is_the_same_thing_with_a_scroll(self):
        self.assertEqual(rule_ids('<a href="#" onClick={go}>x</a>'),
                         {"jsx-anchor-not-a-link"})

    def test_a_real_destination_is_a_link(self):
        self.assertEqual(findings('<a href="/pricing" onClick={go}>x</a>'), [])

    def test_autofocus_is_advice_rather_than_an_error(self):
        found = findings("<input autoFocus />")
        self.assertEqual([issue.rule_id for issue in found], ["jsx-autofocus"])
        self.assertEqual(found[0].confidence, "advisory")


class DangerousHtml(unittest.TestCase):
    def test_written_markup_is_a_best_practice_and_not_an_accessibility_finding(self):
        found = findings('<div dangerouslySetInnerHTML={{ __html: raw }} />')
        self.assertEqual([issue.category for issue in found], ["best-practices"])

    def test_it_stays_out_of_security_because_it_infers(self):
        """`security` was opened on the condition that nothing in it guesses.
        This rule cannot see whether the value was sanitised, so filing it
        there would spend that category's credibility."""
        found = findings('<div dangerouslySetInnerHTML={{ __html: raw }} />')
        self.assertEqual(found[0].confidence, "advisory")
        self.assertNotEqual(found[0].category, "security")


class Wording(unittest.TestCase):
    def test_every_jsx_finding_reads_as_a_sentence_in_every_language(self):
        markup = ("<div><label>Email</label><div onClick={go}>go</div>"
                  "<li tabIndex={0}>x</li><input autoFocus />"
                  "<a onClick={g}>x</a>"
                  '<span dangerouslySetInnerHTML={{ __html: raw }} /></div>')
        found = findings(markup)
        self.assertTrue(found)
        for issue in found:
            for lang in ("uk", "it", "en"):
                explanation = render(issue, lang)
                for field in ("title", "found", "why", "fix"):
                    value = getattr(explanation, field)
                    self.assertTrue(value, f"{issue.rule_id}.{field} is empty")
                    self.assertFalse(value.startswith("a11y_"))

    def test_a_boolean_detail_is_rendered_as_a_word_in_the_users_language(self):
        issue = next(i for i in findings("<div onClick={go}>go</div>")
                     if i.rule_id == "jsx-noninteractive-handler")
        self.assertIs(issue.details["focusable"], False)
        self.assertIn("ні", render(issue, "uk").found)
        self.assertIn("no", render(issue, "en").found)


class SourceSpelling(unittest.TestCase):
    def test_a_comment_inside_a_prop_does_not_lose_the_snippet(self):
        """An apostrophe in `// the plugin's own classes` used to open a
        quote that never closed, so the snippet fell back to the parser's
        re-print - text that is in nobody's file."""
        from bs4 import BeautifulSoup

        from audit.base import remember_source, snippet_of, source_tag_name

        markup = ("<CodeMirror\n  basicSetup={{\n    // the plugin's own\n"
                  "    lineNumbers: false,\n  }}\n  autoFocus={a}\n/>")
        soup = BeautifulSoup(markup, "html.parser")
        remember_source(soup, markup)
        tag = soup.find(attrs={"autofocus": True})
        self.assertEqual(source_tag_name(tag), "CodeMirror")
        self.assertTrue(snippet_of(tag).startswith("<CodeMirror"))


if __name__ == "__main__":
    unittest.main()
