"""A code an engine update brings is a note until a person weighs it (T-1963)."""
from __future__ import annotations

import json
import unittest
from unittest import mock

from audit import engine_codes as E
from audit.base import ADVISORY, EXACT, MINOR
from audit.browser import issues_from_axe, issues_from_htmlcs


def _axe(rule_id, impact="critical"):
    return json.dumps({"violations": [{
        "id": rule_id, "impact": impact, "help": "h",
        "nodes": [{"target": ["button"], "html": "<button></button>"}]}]})


def _htmlcs(code):
    return json.dumps({"messages": [{"type": 1, "code": code, "html": "<a></a>",
                                     "msg": "m", "tag": "a"}]})


H37 = "WCAG2AA.Principle1.Guideline1_1.1_1_1.H37"
NEW_HTMLCS = "WCAG2AA.Principle4.Guideline4_1.4_1_9.H999"


class TheBundledVersions(unittest.TestCase):
    def test_the_table_is_recorded_for_the_bundled_engines(self):
        table = E.recorded()
        for engine in (E.AXE, E.HTMLCS):
            with self.subTest(engine):
                self.assertEqual(table[engine]["version"], E.vendored_version(engine))
                self.assertTrue(table[engine]["codes"])

    def test_at_the_recorded_version_every_code_keeps_its_weight(self):
        issue, = issues_from_axe(_axe("brand-new-rule"), "https://s.test/")
        self.assertEqual((issue.severity, issue.confidence), ("critical", EXACT))
        issue, = issues_from_htmlcs(_htmlcs(NEW_HTMLCS), "https://s.test/")
        self.assertEqual(issue.confidence, EXACT)


class AfterAnUpdate(unittest.TestCase):
    """The bundled file moved on; the table still names the old version."""

    def setUp(self):
        old = {engine: dict(entry, version="0.0.1")
               for engine, entry in E.recorded().items()}
        patcher = mock.patch.object(E, "recorded", return_value=old)
        patcher.start()
        self.addCleanup(patcher.stop)
        E._reported.clear()

    def test_a_new_axe_rule_is_a_note(self):
        issue, = issues_from_axe(_axe("brand-new-rule"), "https://s.test/")
        self.assertEqual((issue.severity, issue.confidence), (MINOR, ADVISORY))
        self.assertTrue(issue.details["unverified_engine_code"])

    def test_a_known_axe_rule_keeps_its_weight(self):
        issue, = issues_from_axe(_axe("button-name"), "https://s.test/")
        self.assertEqual((issue.severity, issue.confidence), ("critical", EXACT))

    def test_a_new_htmlcs_code_is_a_note_and_a_known_one_is_not(self):
        new, = issues_from_htmlcs(_htmlcs(NEW_HTMLCS), "https://s.test/")
        self.assertEqual((new.severity, new.confidence), (MINOR, ADVISORY))
        known, = issues_from_htmlcs(_htmlcs(H37), "https://s.test/")
        self.assertEqual(known.confidence, EXACT)

    def test_each_new_code_is_logged_once(self):
        with mock.patch("applog.warning") as warn:
            issues_from_axe(_axe("brand-new-rule"), "https://s.test/a")
            issues_from_axe(_axe("brand-new-rule"), "https://s.test/b")
        warn.assert_called_once()
        self.assertEqual(warn.call_args.kwargs["code"], "brand-new-rule")


class WithoutATable(unittest.TestCase):
    def test_nothing_changes(self):
        with mock.patch.object(E, "recorded", return_value={}):
            self.assertTrue(E.is_known(E.AXE, "anything"))


if __name__ == "__main__":
    unittest.main()
