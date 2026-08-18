"""Which account pays, and how a batched rewrite is cut back apart.

Both are things that go wrong silently. A routing mistake bills the wrong
subscription and nobody notices until an invoice; a batch-splitting mistake
puts one passage's rewrite into another passage's place, which reads as a
plausible sentence and is therefore worse than an error.

Nothing here touches the network or spawns the CLI: the point is the
decision, not the call.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
import rewriter
from llm.claude_code_provider import _split_marked


class ProviderRouting(unittest.TestCase):
    def setUp(self):
        self.settings = config.Settings()
        self._saved = {k: os.environ.get(k) for k in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT")}
        for key in self._saved:
            os.environ.pop(key, None)

    def tearDown(self):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_outside_claude_code_the_configured_provider_is_used(self):
        self.settings.llm_provider = "xformat"
        self.assertEqual(
            rewriter.effective_provider_name(self.settings, allow_auto=True),
            "xformat",
        )

    def test_inside_claude_code_the_cli_uses_the_session_that_launched_it(self):
        os.environ["CLAUDECODE"] = "1"
        self.settings.llm_provider = "xformat"
        name = rewriter.effective_provider_name(self.settings, allow_auto=True)
        # Only meaningful where the CLI is actually installed; where it is
        # not, falling back to the configured provider is the correct answer
        # and is what the assertion below allows.
        from llm.claude_code_provider import find_binary
        self.assertEqual(name, "claude-code" if find_binary() else "xformat")

    def test_the_desktop_app_never_auto_switches(self):
        # allow_auto is False for the GUI: nobody launched it from an agent,
        # so the choice in Settings is a decision, not a default.
        os.environ["CLAUDECODE"] = "1"
        self.settings.llm_provider = "anthropic"
        self.assertEqual(rewriter.effective_provider_name(self.settings), "anthropic")

    def test_an_explicit_provider_beats_the_automatic_one(self):
        os.environ["CLAUDECODE"] = "1"
        self.assertEqual(
            rewriter.effective_provider_name(self.settings, force="xformat",
                                             allow_auto=True),
            "xformat",
        )

    def test_the_preference_can_be_turned_off(self):
        os.environ["CLAUDECODE"] = "1"
        self.settings.prefer_claude_code_in_cli = False
        self.settings.llm_provider = "anthropic"
        self.assertEqual(
            rewriter.effective_provider_name(self.settings, allow_auto=True),
            "anthropic",
        )


class BatchSplitting(unittest.TestCase):
    def test_a_well_formed_answer_is_cut_at_the_markers(self):
        answer = "<<<1>>>\nfirst rewrite\n\n<<<2>>>\nsecond rewrite"
        self.assertEqual(_split_marked(answer, 2), ["first rewrite", "second rewrite"])

    def test_a_missing_marker_gives_up_rather_than_guessing(self):
        # The sequential path then reruns the batch. Returning one rewrite
        # here would silently assign it to the wrong passage.
        self.assertIsNone(_split_marked("<<<1>>>\nonly one", 2))

    def test_an_empty_section_is_not_accepted_as_a_rewrite(self):
        self.assertIsNone(_split_marked("<<<1>>>\n\n<<<2>>>\nsecond", 2))

    def test_marker_text_inside_a_passage_is_not_a_boundary(self):
        # A rewrite may legitimately contain the marker text mid-sentence.
        # Only a line that is nothing but the marker separates passages.
        answer = "<<<1>>>\nsee <<<2>>> below\n<<<2>>>\nsecond"
        self.assertEqual(_split_marked(answer, 2), ["see <<<2>>> below", "second"])

    def test_markers_out_of_order_are_rejected(self):
        self.assertIsNone(_split_marked("<<<2>>>\nsecond\n<<<1>>>\nfirst", 2))


if __name__ == "__main__":
    unittest.main()
