"""A fresh judgement says what produced it.

`P-08`: the judge is not reproducible and cannot be made so. Sampling
parameters are removed on every model this tool defaults to - `temperature`
on `claude-opus-5` returns a 400 - and there is no seed. Two runs over the
same passage may therefore disagree, and the only way to tell a code change
from model drift is for each finding to carry the configuration that made it.

So this is the case that keeps that record honest. It is cheap and it is
easy to drop during a refactor, which is exactly why it is asserted rather
than left to the docstring.
"""
from __future__ import annotations

import unittest
from unittest import mock

from detectors.claude_llm_judge import ClaudeLLMJudgeDetector
from models import TextBlock


class _Part:
    type = "text"

    def __init__(self, text):
        self.text = text


class _Response:
    stop_reason = "end_turn"

    def __init__(self, payload):
        self.content = [_Part(payload)]


class TheFindingCarriesItsConfiguration(unittest.TestCase):
    def _judge_once(self, model: str, effort: str):
        judge = ClaudeLLMJudgeDetector(api_key="test-key", model=model, effort=effort)
        block = TextBlock(block_id="b1", text="Unlock the full potential of your workflow.",
                          page_url="https://example.com/", dom_path="body > p")
        payload = ('{"results": [{"block_index": 0, "flags": [{"quote": "full potential", '
                   '"score": 0.9, "reason": "marketing register"}]}]}')
        client = mock.Mock()
        client.messages.create.return_value = _Response(payload)
        with mock.patch.object(judge, "_get_client", return_value=client):
            spans = judge.analyze_blocks([block])
        return spans, client.messages.create.call_args.kwargs

    def test_the_model_and_effort_reach_the_span(self):
        spans, _ = self._judge_once("claude-opus-5", "low")
        self.assertTrue(spans)
        self.assertEqual(spans[0].details["model"], "claude-opus-5")
        self.assertEqual(spans[0].details["effort"], "low")

    def test_a_different_effort_is_visible_in_the_record(self):
        """Otherwise two runs at different settings look identical."""
        _, low = self._judge_once("claude-opus-5", "low")
        spans, _ = self._judge_once("claude-opus-5", "high")
        self.assertEqual(spans[0].details["effort"], "high")
        self.assertEqual(low["output_config"]["effort"], "low")

    def test_no_sampling_parameter_is_sent(self):
        """`temperature`, `top_p` and `top_k` are 400s on this model family.

        Asserted so nobody 'fixes' the non-determinism by adding one and
        discovers it only when a live call fails.
        """
        _, sent = self._judge_once("claude-opus-5", "low")
        for parameter in ("temperature", "top_p", "top_k"):
            with self.subTest(parameter=parameter):
                self.assertNotIn(parameter, sent)


class TheProviderPathCarriesItToo(unittest.TestCase):
    """The two judges that bill an account rather than an API key.

    `ProviderLLMJudgeDetector` skips `ClaudeLLMJudgeDetector.__init__` on
    purpose - that constructor looks for an Anthropic key this path never
    uses - and in skipping it, it skipped `self.effort` while inheriting the
    span mapping that stamps it. So both `claude-code-llm-judge` and
    `xformat-llm-judge` raised `AttributeError` the moment a model returned a
    flag, and **only** then: a verdict with no flags builds no span and
    touches nothing. Found 2026-08-31 by running the judge on a live page,
    which is the first thing that ever handed it a non-empty verdict.
    """

    PAYLOAD = ('{"results": [{"block_index": 0, "flags": [{"quote": "full '
               'potential", "score": 0.9, "reason": "marketing register"}]}]}')

    def _judge(self, name):
        from detectors.factory import DetectorFactory

        judge = DetectorFactory.create(name)
        block = TextBlock(block_id="b1",
                          text="Unlock the full potential of your workflow.",
                          page_url="https://example.com/", dom_path="body > p")
        provider = mock.Mock()
        provider.analyze.return_value = self.PAYLOAD
        with mock.patch.object(judge, "_get_provider", return_value=provider):
            return judge.analyze_blocks([block])

    def test_a_flagged_passage_produces_a_span_not_a_crash(self):
        for name in ("claude-code-llm-judge", "xformat-llm-judge"):
            with self.subTest(name):
                spans = self._judge(name)
                self.assertEqual(len(spans), 1)
                self.assertNotIn("error", spans[0].details)
                self.assertEqual(spans[0].details["source"], "model")
                # Both fields are present; neither names a setting this path
                # has, because it has none.
                self.assertIn("effort", spans[0].details)
                self.assertIn("model", spans[0].details)

    def test_one_unreadable_batch_does_not_end_the_scan(self):
        """The mapping used to sit outside the `try` that exists for this."""
        from detectors.factory import DetectorFactory

        judge = DetectorFactory.create("claude-code-llm-judge")
        blocks = [TextBlock(block_id=f"b{i}", text="Some text here to judge.",
                            page_url="https://example.com/", dom_path="p")
                  for i in range(2)]
        provider = mock.Mock()
        provider.analyze.return_value = '{"results": [{"block_index": 0, "flags": "not a list"}]}'
        with mock.patch.object(judge, "_get_provider", return_value=provider):
            spans = judge.analyze_blocks(blocks)
        self.assertEqual(len(spans), len(blocks))
        for span in spans:
            self.assertIn("error", span.details)


if __name__ == "__main__":
    unittest.main()
