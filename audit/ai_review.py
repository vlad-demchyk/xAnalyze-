"""The AI pass over accessibility: the judgements a rule cannot make.

A rule can prove an `alt` attribute is absent. It cannot tell whether
`alt="image of a chart"` actually describes the chart, whether a heading
matches the section under it, or whether a link's text describes where it
goes. Those need reading comprehension, and that is the whole scope of this
pass — it deliberately does **not** re-check anything the offline rules
already decide, because paying a model to re-confirm that an attribute is
missing is money spent on a question already answered exactly.

What it is given is therefore a *digest*, not the page: the elements whose
text needs judging, already extracted. That keeps the request small enough
to be cheap on a large site and keeps the model's attention on the one thing
it is better at than a regular expression.

Findings from here are marked `confidence = "ai"` and severity is capped at
`serious`: a model's opinion should never outrank a fact when the report is
sorted by what to fix first.
"""
from __future__ import annotations

import json
import re

from .base import MODERATE, SERIOUS, Issue

#: Stamped on `Issue.confidence` so the report can label these as opinion.
AI_JUDGEMENT = "ai"

_SYSTEM_PROMPT = (
    "You review web accessibility, specifically the parts that require "
    "reading comprehension rather than markup validation. You will receive a "
    "JSON list of elements taken from one page. For each one, decide whether "
    "its text does the job it needs to do:\n"
    "- img: does the alt text describe what the image conveys, or is it "
    "generic filler ('image', 'photo', 'graphic', 'icon')?\n"
    "- link: does the text describe the destination when read on its own, "
    "out of the surrounding sentence?\n"
    "- heading: does it describe the content that follows it?\n"
    "- button: does the label say what the action does?\n"
    "Flag only real problems. An alt text that is short but specific is "
    "fine. Write the reason and the suggested wording in the same language "
    "as the element's own text. Respond with ONLY JSON in exactly this "
    'shape: {"findings": [{"index": 0, "problem": "...", "suggestion": "..."}]}'
)

#: How many elements go in one request. Small enough that one failed batch
#: loses little, large enough that a page is not dozens of round trips.
DEFAULT_BATCH_SIZE = 25

_WHITESPACE_RE = re.compile(r"\s+")


def _text_of(tag) -> str:
    return _WHITESPACE_RE.sub(" ", " ".join(tag.stripped_strings)).strip()


def collect_candidates(document, context) -> list:
    """The elements whose *wording* is worth a second opinion.

    Only elements that already have text: something missing entirely is the
    offline rules' job, and sending it here would duplicate a finding the
    user has already been given with an exact fix.
    """
    candidates = []

    for tag in document.find_all("img"):
        alt = (tag.get("alt") or "").strip()
        if not alt:
            continue  # missing alt is `image-alt`, already reported exactly
        selector, line = context.locate(tag)
        candidates.append({
            "kind": "img", "text": alt, "context": (tag.get("src") or "")[:80],
            "selector": selector, "line": line, "tag": tag,
        })

    for tag in document.find_all("a", href=True):
        text = _text_of(tag)
        if not text:
            continue
        selector, line = context.locate(tag)
        candidates.append({
            "kind": "link", "text": text, "context": (tag.get("href") or "")[:80],
            "selector": selector, "line": line, "tag": tag,
        })

    for tag in document.find_all(re.compile(r"^h[1-6]$")):
        text = _text_of(tag)
        if not text:
            continue
        selector, line = context.locate(tag)
        candidates.append({
            "kind": "heading", "text": text,
            # The first stretch of what follows, so the model can judge
            # whether the heading actually describes it.
            "context": _following_text(tag)[:300],
            "selector": selector, "line": line, "tag": tag,
        })

    for tag in document.find_all("button"):
        text = _text_of(tag) or (tag.get("aria-label") or "").strip()
        if not text:
            continue
        selector, line = context.locate(tag)
        candidates.append({
            "kind": "button", "text": text, "context": "",
            "selector": selector, "line": line, "tag": tag,
        })

    return candidates


def _following_text(heading) -> str:
    parts = []
    for sibling in heading.next_siblings:
        name = getattr(sibling, "name", None)
        if name and re.match(r"^h[1-6]$", name):
            break  # the next section starts here
        if name:
            parts.append(_text_of(sibling))
        if sum(len(p) for p in parts) > 400:
            break
    return " ".join(p for p in parts if p).strip()


class AIAccessibilityReview:
    """Runs the wording judgements through whichever LLM provider is set up.

    Provider-agnostic on purpose: the same pass runs on a personal Anthropic
    key or on an xFormat subscription, exactly like the rewrite path, so a
    user with either one gets the whole feature.
    """

    def __init__(self, provider=None, settings=None, batch_size: int = DEFAULT_BATCH_SIZE):
        self.provider = provider
        self.settings = settings
        self.batch_size = batch_size

    def _get_provider(self):
        if self.provider is None:
            import rewriter
            self.provider = rewriter.build_provider(self.settings)
        return self.provider

    def review_document(self, document, context) -> list:
        candidates = collect_candidates(document, context)
        if not candidates:
            return []
        provider = self._get_provider()

        issues = []
        for start in range(0, len(candidates), self.batch_size):
            batch = candidates[start:start + self.batch_size]
            issues.extend(self._review_batch(provider, batch, context))
        return issues

    def _review_batch(self, provider, batch: list, context) -> list:
        payload = json.dumps(
            [{"index": i, "kind": c["kind"], "text": c["text"], "context": c["context"]}
             for i, c in enumerate(batch)],
            ensure_ascii=False,
        )
        try:
            # `analyze` when the provider has one (the xFormat backend routes
            # analysis and rewriting to different features and prices);
            # `rewrite` is the universal fallback.
            if hasattr(provider, "analyze"):
                raw = provider.analyze(_SYSTEM_PROMPT, payload)
            else:
                raw = provider.rewrite(_SYSTEM_PROMPT + "\n\n" + payload, None)
            data = _parse_json_relaxed(raw)
        except Exception as exc:  # noqa: BLE001 - a failed batch is not a failed audit
            return [Issue(
                rule_id="ai-review", severity=MODERATE, source=context.source,
                confidence=AI_JUDGEMENT, details={"batch_error": str(exc)},
            )]

        issues = []
        for finding in data.get("findings", []):
            index = finding.get("index")
            if not isinstance(index, int) or not (0 <= index < len(batch)):
                continue
            candidate = batch[index]
            issues.append(Issue(
                rule_id=f"ai-{candidate['kind']}-wording",
                # Capped at serious: an opinion must not outrank a fact when
                # the report is sorted by what to fix first.
                severity=SERIOUS if candidate["kind"] == "img" else MODERATE,
                selector=candidate["selector"], line=candidate["line"],
                snippet=candidate["text"][:160], source=context.source,
                confidence=AI_JUDGEMENT,
                details={
                    "kind": candidate["kind"],
                    "text": candidate["text"],
                    "problem": str(finding.get("problem", ""))[:400],
                    "suggestion": str(finding.get("suggestion", ""))[:400],
                },
            ))
        return issues


def _parse_json_relaxed(raw: str) -> dict:
    raw = (raw or "").strip()
    try:
        return json.loads(raw)
    except ValueError:
        pass
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object in model response: {raw[:200]!r}")
    return json.loads(raw[start:end + 1])
