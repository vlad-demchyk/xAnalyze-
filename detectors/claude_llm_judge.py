"""Claude used as an "LLM judge" to flag likely AI-generated passages.

This is NOT the official Claude watermark, and the distinction matters more
now than it did when this file was first written. Claude *does* watermark
its text output — imperceptibly, since 2 August 2026 — but as of this
writing Anthropic has published no way to read that mark: detection is
still "forthcoming technical documentation" (see
`claude_watermark_stub.py`, which is where that lands when it ships).

What this backend does instead is ask a live Claude model to read the text
and flag passages that read as AI-generated, the same way a careful human
reviewer would. It costs a real API call per batch and can be wrong in both
directions.

Request shape notes, because they are easy to get wrong:

* `output_config.format` pins the response to a JSON schema, so the reply
  is parseable by construction rather than by fishing a JSON object out of
  prose. That removed the "model wrote a sentence before the JSON" failure
  mode entirely.
* `effort: "low"` is deliberate. A scan runs this over every block on a
  site, the user is paying per call, and the judgement is a short opinion
  about a short passage — the cheapest tier is the right default here, and
  the model to use is a setting the user controls.
* Only `text` blocks are read out of `response.content`; a response can
  also contain `thinking` blocks, and treating those as output would
  corrupt the parse.
* **There is no `temperature` to set, and that is not an oversight** (`P-08`).
  Sampling parameters — `temperature`, `top_p`, `top_k` — are removed on
  Claude Opus 5, Opus 4.8, Opus 4.7, Sonnet 5 and Fable 5, and sending one
  returns a 400. They still work on Opus 4.6 and older, but pinning the judge
  to a retired model to buy determinism would trade a real capability for a
  property the run can record instead. So this backend does the recordable
  thing: every finding carries the model and the effort that produced it, and
  two runs that disagree can be told apart by configuration rather than
  guessed at. `judgment_cache` fingerprints the same triple, so a changed
  model or effort invalidates the cached verdicts rather than mixing them.
"""
from __future__ import annotations

import json
import os

from models import Confidence, TextBlock, TextSpan, score_to_confidence
from .base import Detector, DetectorUnavailable
from .factory import DetectorFactory

DEFAULT_MODEL = "claude-opus-5"
DEFAULT_BATCH_SIZE = 8

_SYSTEM_PROMPT = (
    "You review website copy and flag passages that read as AI-generated "
    "rather than written by a human, across Ukrainian, Italian, and English. "
    "You will receive several numbered text blocks. For each block, return "
    "the substrings (quoted VERBATIM, exact character-for-character matches "
    "from the block) that you'd flag, each with a score from 0 (clearly "
    "human-written) to 1 (clearly AI-generated) and a one-sentence reason "
    "in the same language as the block. If a block reads as entirely "
    "human-written, return an empty flags list for it.\n"
    "\n"
    "DETECTION RULES — use ALL of these signals:\n"
    "\n"
    "1. STATISTICAL SIGNALS (score 0-1 each):\n"
    "   - Uniformity (weight 0.40): Human writing varies sentence length "
    "(bursty); AI is uniform. Below 3 sentences: not measurable.\n"
    "   - Repetition (weight 0.35): Low type-token ratio = AI repeats words. "
    "Below 20 words: not measurable.\n"
    "   - Dash density (weight 0.25): AI overuses em dashes as commas. "
    "0.3 dashes/100w = normal human, >2/100w = heavy AI-like. "
    "THIS IS A REAL AI SIGNAL, not just typography.\n"
    "\n"
    "2. STRUCTURAL PATTERNS (each hit adds 0.25 to score):\n"
    "   EN: 'not just X but Y', 'it's not about X, it's about Y', "
    "'no X. no Y. just Z.', 'whether you're X or Y', "
    "'take your X to the next level'\n"
    "   UK: 'не просто X а Y', 'справа не в X справа в Y', "
    "'це не просто про X; це про Y', 'жодних X. жодних Y. лише Z.'\n"
    "   IT: 'non solo X ma anche Y', 'non si tratta di X si tratta di Y', "
    "'niente X. niente Y. solo Z.'\n"
    "\n"
    "3. CLICHÉ PHRASES (strong=with space: 0.30, weak=single word: 0.10):\n"
    "   EN strong: 'it's important to note', 'in today's fast-paced world', "
    "'furthermore,', 'in conclusion', 'let's dive in', 'unlock the potential', "
    "'seamless experience', 'comprehensive solution', 'intuitive interface', "
    "'join thousands of', 'satisfied users', 'streamline your workflow'\n"
    "   EN weak: 'delve', 'pivotal', 'realm', 'harness', 'streamline', "
    "'innovative', 'transformative', 'seamless', 'scalable', 'comprehensive', "
    "'robust', 'exceptional', 'unparalleled', 'dynamic', 'intricate', "
    "'nuanced', 'holistic', 'paramount', 'testament'\n"
    "   UK strong: 'варто зазначити', 'у сучасному світі', 'комплексне рішення', "
    "'розкрийте потенціал', 'інтуїтивний інтерфейс', 'задоволених користувачів'\n"
    "   IT strong: 'vale la pena notare', 'nel mondo di oggi', "
    "'soluzione completa', 'interfaccia intuitiva', 'utenti soddisfatti'\n"
    "\n"
    "4. SCORING: Base = weighted avg of measured signals. Each cliché/structural "
    "hit reduces remaining room (diminishing returns). Without at least one "
    "concrete marker (cliché or structural), score capped at 0.32.\n"
    "\n"
    "5. IMPORTANT:\n"
    "   - Em dash density IS a real AI signal, do not dismiss it\n"
    "   - Technical code/docstrings are almost never AI-generated\n"
    "   - Marketing copy, landing pages, onboarding text are prime AI targets\n"
)

# Pins the reply shape. `additionalProperties: false` plus a full `required`
# list is what makes the schema strict rather than advisory.
_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "block_index": {"type": "integer"},
                    "flags": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "quote": {"type": "string"},
                                "score": {"type": "number"},
                                "reason": {"type": "string"},
                            },
                            "required": ["quote", "score", "reason"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["block_index", "flags"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["results"],
    "additionalProperties": False,
}


class ClaudeLLMJudgeDetector(Detector):
    name = "claude-llm-judge"
    display_name = "Claude — LLM-as-judge (live API call)"
    #: A general model, not a word list: no language is out of scope.

    def __init__(self, api_key: str | None = None, model: str = DEFAULT_MODEL,
                 batch_size: int = DEFAULT_BATCH_SIZE, effort: str = "low", **config):
        super().__init__(**config)
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model or DEFAULT_MODEL
        self.batch_size = batch_size
        self.effort = effort
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not self.api_key:
            raise DetectorUnavailable(
                "No Anthropic API key configured. Set ANTHROPIC_API_KEY or "
                "pass api_key= when creating this detector."
            )
        try:
            import anthropic
        except ImportError as exc:
            raise DetectorUnavailable(
                "The 'anthropic' package is not installed. Run: pip install anthropic"
            ) from exc
        self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def analyze_block(self, block: TextBlock) -> list[TextSpan]:
        return self.analyze_blocks([block])

    def analyze_blocks(self, blocks: list[TextBlock]) -> list[TextSpan]:
        client = self._get_client()
        spans: list[TextSpan] = []
        for i in range(0, len(blocks), self.batch_size):
            batch = blocks[i:i + self.batch_size]
            spans.extend(self._analyze_batch(client, batch))
        return spans

    def _analyze_batch(self, client, batch: list[TextBlock]) -> list[TextSpan]:
        numbered = "\n\n".join(f"[{idx}] {b.text}" for idx, b in enumerate(batch))
        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=8000,
                system=_SYSTEM_PROMPT,
                output_config={
                    "effort": self.effort,
                    "format": {"type": "json_schema", "schema": _RESPONSE_SCHEMA},
                },
                messages=[{"role": "user", "content": numbered}],
            )
            if getattr(response, "stop_reason", None) == "refusal":
                return [self._error_span(b, RuntimeError(_refusal_message(response)))
                        for b in batch]
            raw = "".join(
                part.text for part in response.content if getattr(part, "type", "") == "text"
            )
            data = _parse_json_relaxed(raw)
        except Exception as exc:  # noqa: BLE001
            return [self._error_span(b, exc) for b in batch]

        return self._spans_from_payload(data, batch)

    def _spans_from_payload(self, data: dict, batch: list[TextBlock]) -> list[TextSpan]:
        """Map a judged batch onto spans.

        Split out from the request so a second judge backend can reuse it:
        `detectors/xformat_llm_judge.py` sends the same prompt through the
        user's xFormat subscription and lands here with the same payload.
        """
        spans: list[TextSpan] = []
        for result in data.get("results", []):
            idx = result.get("block_index")
            if idx is None or not (0 <= idx < len(batch)):
                continue
            block = batch[idx]
            for flag in result.get("flags", []):
                quote = flag.get("quote", "")
                score = float(flag.get("score", 0.5))
                reason = flag.get("reason", "")
                start = block.text.find(quote) if quote else -1
                if start == -1:
                    # Model paraphrased instead of quoting verbatim; flag whole block low-confidence.
                    start, end = 0, len(block.text)
                    reason = (reason + " (quote not found verbatim; flagging whole block)").strip()
                else:
                    end = start + len(quote)
                spans.append(
                    TextSpan(
                        block_id=block.block_id,
                        start=start,
                        end=end,
                        score=max(0.0, min(1.0, score)),
                        confidence=score_to_confidence(score),
                        detector_name=self.name,
                        explanation=reason,
                        # The judging configuration travels with the finding.
                        # A fresh judgement is not reproducible - no seed and
                        # no temperature are available on the current models
                        # (see the module docstring, `P-08`) - so the next
                        # best thing is that a finding can always say what
                        # produced it.
                        details={"source": "model",
                                 "model": getattr(self, "model", self.name),
                                 "effort": self.effort},
                    )
                )
        return spans


def _refusal_message(response) -> str:
    """A refusal arrives as a normal 200 response with `stop_reason` set, so
    it has to be checked for explicitly — reading `.content` first would
    just produce an empty parse and a confusing "no JSON found" error."""
    details = getattr(response, "stop_details", None)
    category = getattr(details, "category", None) if details else None
    return f"the model declined to answer{f' ({category})' if category else ''}"


def _parse_json_relaxed(raw: str) -> dict:
    """The schema makes the response valid JSON, so this normally parses on
    the first line. The object-extraction fallback stays for models or
    gateways that don't honour `output_config.format` — the xFormat-routed
    judge below can be pointed at any model in that catalog."""
    raw = raw.strip()
    try:
        return json.loads(raw)
    except ValueError:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object found in model response: {raw[:200]!r}")
    return json.loads(raw[start:end + 1])


DetectorFactory.register(ClaudeLLMJudgeDetector.name, ClaudeLLMJudgeDetector)
