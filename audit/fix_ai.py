"""Filling in the corrections that a rule can shape but not write.

A rule knows the page needs a description; it cannot know what the page is
about. It knows an image has no alternative text; it cannot see the image.
Those corrections come out of `fixer.plan_fixes` with a reason attached
instead of a value, and this is where the value comes from.

Two sources, in this order, because they are not equally trustworthy:

**The document itself, where the answer is in it.** The page's language is
readable from its own text, so it is read rather than asked for. A local
answer costs nothing, needs no account, and cannot hallucinate.

**A model, for the rest.** Only for the parts that are genuinely writing:
a description, a social title, alternative text. Every value a model produces
is recorded as the model's, and the backup taken before the write is what
makes accepting it a reversible decision rather than a leap.

The model is told, in the prompt, to answer `SKIP` when the surrounding text
does not actually say what the answer is. That instruction matters more than
it looks: an image whose purpose is not evident from the page is exactly the
case where an invented description is worse than the missing one, because the
audit stops reporting it.
"""
from __future__ import annotations

import re

from lang_detect import guess_language

#: One line per item, addressed by number, so a batch cannot silently
#: reorder. Same shape as the rewriter's batch protocol.
_MARKER = "<<<{n}>>>"

#: What each rule is actually asking a writer for.
_ASKS = {
    "seo-meta-description": (
        "a search-result description of this page, 120-155 characters, "
        "plain sentence, no quotes around it"),
    "seo-open-graph": (
        "a title for this page as it should appear when the link is shared, "
        "under 60 characters"),
    "image-alt": (
        "alternative text for this image: what a person who cannot see it "
        "would need to know, under 125 characters. Answer SKIP if the page "
        "text does not make the image's content clear"),
    "image-alt-filename": (
        "alternative text for this image, replacing a filename that says "
        "nothing. Answer SKIP if the page text does not make it clear"),
}


def fill_locally(plans: list, page_text: str) -> tuple:
    """Answer what the document itself already answers.

    Returns `(filled, remaining)`. Only the page language for now, and that
    is the point: a value read from the page is not a guess, so it does not
    belong in the same queue as the ones that are.
    """
    filled, remaining = [], []
    language = guess_language(page_text or "")
    for plan in plans:
        if plan.rule_id == "html-lang" and language:
            filled.append(plan.with_text(language) if "…" in plan.replacement
                          else _relang(plan, language))
        else:
            remaining.append(plan)
    return filled, remaining


def _relang(plan, language: str):
    """Put the detected language into `<html lang="…">`."""
    replacement = re.sub(r'lang="[^"]*"', f'lang="{language}"', plan.replacement)
    if replacement == plan.replacement:
        return plan
    filled = plan.with_text("")
    filled.replacement = replacement
    return filled


def describe(plans: list, page_text: str, provider, language: str = "en") -> tuple:
    """Ask a model for the values it can supply. Returns `(filled, left)`.

    One call for the whole batch rather than one per finding: twenty images
    on a page would otherwise be twenty round trips, and the model writes
    better alternative text when it can see the page as a whole anyway.
    """
    askable = [p for p in plans if p.rule_id in _ASKS]
    if not askable or provider is None:
        return [], plans

    context = _context(page_text)
    system = (
        "You are correcting an HTML page. For each numbered item, answer with "
        "the value only - no markup, no quotes, no explanation. Answer SKIP "
        "when the page text does not actually tell you the answer: a wrong "
        "value here is worse than none, because it stops the problem being "
        "reported at all. Write in the page's own language. Reply with the "
        "same markers, each followed by exactly one line."
    )
    lines = [
        "Page text:",
        context,
        "",
        "Items:",
    ]
    for index, plan in enumerate(askable, start=1):
        lines.append(f"{_MARKER.format(n=index)}")
        lines.append(f"Element: {plan.original or plan.replacement.strip()}")
        lines.append(f"Needed: {_ASKS[plan.rule_id]}")
    prompt = "\n".join(lines)
    # `analyze` when the provider has it, because a system prompt is what
    # keeps the answer to bare values; `rewrite` is the fallback for a
    # provider that only knows how to rewrite prose.
    try:
        answer = (provider.analyze(system, prompt)
                  if hasattr(provider, "analyze")
                  else provider.rewrite(f"{system}\n\n{prompt}", language))
    except Exception:  # noqa: BLE001 - a model that failed leaves the file alone
        return [], plans
    values = _split_marked(answer or "", len(askable))
    if values is None:
        return [], plans

    filled, left = [], [p for p in plans if p not in askable]
    for plan, value in zip(askable, values):
        value = value.strip()
        if not value or value.upper() == "SKIP":
            left.append(plan)
            continue
        completed = plan.with_text(value)
        completed.needs_input = ""
        filled.append(completed)
    return filled, left


def _context(page_text: str, limit: int = 4000) -> str:
    text = " ".join((page_text or "").split())
    return text[:limit]


def _split_marked(answer: str, expected: int):
    """Whole-line markers, in order, or nothing.

    Same rule as the rewriter: a marker matched mid-sentence once produced a
    value that was half of the model's prose, so only a line that *is* the
    marker counts.
    """
    lines = answer.splitlines()
    starts = []
    cursor = 0
    for index in range(1, expected + 1):
        marker = _MARKER.format(n=index)
        while cursor < len(lines) and lines[cursor].strip() != marker:
            cursor += 1
        if cursor >= len(lines):
            return None
        starts.append(cursor)
        cursor += 1
    values = []
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        values.append("\n".join(lines[start + 1:end]).strip())
    return values
