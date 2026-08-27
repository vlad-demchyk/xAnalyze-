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


if __name__ == "__main__":
    unittest.main()
