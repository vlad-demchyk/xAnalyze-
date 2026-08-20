"""Which account pays for `scan --detector llm-judge`, and what happens when
it cannot pay.

Both halves come from a live run on 2026-08-19: on a machine with a signed-in
Claude Code session, `scan --detector claude-llm-judge` failed with "No
Anthropic API key configured" while `audit --ai` worked; and pointing the
same scan at an xFormat plan whose weekly allowance was spent printed "No
findings" and exited 0.
"""
from __future__ import annotations

import argparse
import unittest
from unittest import mock

import cli
import detectors  # noqa: F401 - registers the detectors
from detectors.factory import DetectorFactory
from models import Confidence, TextBlock, TextSpan


def _args(**kwargs):
    defaults = {"detector": "llm-judge", "provider": None}
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


class DetectorRoutingTests(unittest.TestCase):
    def _with_effective(self, name):
        return mock.patch("rewriter.effective_provider_name", return_value=name)

    def test_llm_judge_follows_the_session_that_is_already_paying(self):
        with self._with_effective("claude-code"):
            detector = cli._create_detector(_args())
        self.assertEqual(detector.name, "claude-code-llm-judge")

    def test_llm_judge_follows_a_subscription_when_that_is_the_account(self):
        with self._with_effective("xformat"):
            detector = cli._create_detector(_args())
        self.assertEqual(detector.name, "xformat-llm-judge")

    def test_the_override_reaches_the_routing(self):
        with mock.patch("rewriter.effective_provider_name") as effective:
            effective.return_value = "xformat"
            cli._create_detector(_args(provider="xformat"))
        self.assertEqual(effective.call_args.kwargs["force"], "xformat")

    def test_an_explicitly_named_judge_is_still_honoured(self):
        detector = cli._create_detector(_args(detector="xformat-llm-judge"))
        self.assertEqual(detector.name, "xformat-llm-judge")

    def test_the_anthropic_judge_gets_the_key_from_settings_too(self):
        with mock.patch("config.get_anthropic_api_key", return_value="from-keychain"):
            detector = cli._create_detector(_args(detector="claude-llm-judge",
                                                  provider="anthropic"))
        self.assertEqual(detector.api_key, "from-keychain")

    def test_every_provider_has_a_judge(self):
        for name in cli.JUDGE_BY_PROVIDER.values():
            self.assertIn(name, DetectorFactory.available(), name)


class UnjudgedBlockTests(unittest.TestCase):
    """A block nobody could read is not a clean block."""

    def _error_spans(self, message="the plan's weekly allowance is used up"):
        block = TextBlock(block_id="b1", page_url="a.html", dom_path="p",
                          text="some copy")
        detector = DetectorFactory.create("claude-code-llm-judge")
        return [detector._error_span(block, RuntimeError(message))]

    def test_an_error_span_is_marked_as_an_error_not_as_a_weak_finding(self):
        span = self._error_spans()[0]
        self.assertTrue((span.details or {}).get("error"))

    def test_the_reason_is_printed_once_per_distinct_error(self):
        spans = self._error_spans() * 3
        with mock.patch("sys.stderr") as err:
            count = cli._report_detector_errors(spans)
        self.assertEqual(count, 3)
        written = "".join(str(c.args[0]) for c in err.write.call_args_list
                          if c.args and isinstance(c.args[0], str))
        self.assertEqual(written.count("weekly allowance"), 1)

    def test_a_clean_run_reports_nothing(self):
        span = TextSpan(block_id="b1", start=0, end=4, score=0.9,
                        confidence=Confidence.HIGH, detector_name="x")
        self.assertEqual(cli._report_detector_errors([span]), 0)


if __name__ == "__main__":
    unittest.main()
