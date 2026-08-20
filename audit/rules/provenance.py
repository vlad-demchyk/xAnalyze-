"""Traces a generator left in the markup itself.

Every other check in this tool reads *text*: the words a person sees, the
characters inside them. This one reads the attributes around that text, and
it exists because the attributes are where a paste from a chat window gives
itself away most reliably. Copy a formatted answer out of a chat UI and the
class names and `data-` hooks that UI used come with it - into the CMS, into
the commit, into production.

Why this is worth a rule when the statistical watermark is not:

* It is **deterministic**. `class="claude-…"` is either in the document or it
  is not. No score, no threshold, no calibration corpus - the finding is a
  fact, in the same sense a zero-width character is a fact.
* It is **not a watermark**, and must never be presented as one. Anthropic's
  text watermark is a keyed bias over token choice; verifying it needs a key
  nobody outside Anthropic has (see `detectors/claude_watermark_stub.py`).
  Markup residue proves a paste happened, not that a model wrote the words.

The honest limit, stated here because it decides the severity: a class token
containing "claude" can also belong to a company, a person or a product with
that name, and a `data-gpt-*` attribute can belong to a homegrown feature
flag. So this is MINOR, the explanation says what it does and does not mean,
and the fix removes the attribute rather than the element.

The rule set was cross-checked against `github.com/OfirYC/claude-watermark-checker`
(MIT), the open detection engine behind claudewatermark.xyz, in August 2026.
Seven of its eight checks - zero-width characters, BOM, NBSP, exotic spaces,
smart punctuation, em dashes - this tool already had in `unicode_rules.py`,
verified codepoint by codepoint. The markup classes are what it had and this
one did not.
"""
from __future__ import annotations

import re

from ..base import BEST_PRACTICES, MINOR, Issue, Rule, RuleRegistry, snippet_of

#: Vendor names that appear in generator-written markup. Matched as a
#: substring of one class token, not of the whole class attribute, so
#: `sidebar-claude-panel` matches and `claudette` does not slip in through a
#: neighbouring token.
_VENDOR_WORDS = ("claude", "chatgpt", "openai", "gemini", "copilot")

#: `data-` attribute prefixes the same generators write. A prefix rather
#: than a substring: `data-claude-artifact` is theirs, `data-updated-by-gpt`
#: is somebody's own field and not this rule's business.
_VENDOR_DATA_PREFIXES = tuple(f"data-{word}" for word in _VENDOR_WORDS) + (
    "data-gpt", "data-anthropic",
)

#: Short tokens are matched whole to keep a word like "gptr" or a hashed
#: class name from counting. Longer vendor words are distinctive enough to
#: match as substrings of a token.
_TOKEN_RE = {word: re.compile(rf"(?:^|[-_]){re.escape(word)}(?:$|[-_\d])", re.I)
             for word in _VENDOR_WORDS}


def _vendor_in_token(token: str) -> str | None:
    for word, pattern in _TOKEN_RE.items():
        if pattern.search(token) or token.lower() == word:
            return word
    return None


class MarkupProvenanceArtifact(Rule):
    """A vendor class name or `data-` attribute left in shipped markup."""

    id = "bp-ai-markup-artifact"
    category = BEST_PRACTICES
    severity = MINOR

    def check(self, document, context) -> list:
        issues = []
        for tag in document.find_all(True):
            findings = self._artifacts(tag)
            if not findings:
                continue
            selector, line = context.locate(tag)
            # One finding per element, not per artifact. A pasted block
            # usually carries a class *and* a data attribute, and two rows
            # pointing at the same element would each offer a fix that
            # leaves the other one behind - so the fix here removes every
            # artifact on the element at once.
            names = [f'class="{name}"' if kind == "class" else name
                     for kind, name, _vendor in findings]
            vendors = sorted({vendor for _kind, _name, vendor in findings})
            issues.append(Issue(
                rule_id=self.id, severity=self.severity,
                category=self.category, selector=selector, line=line,
                snippet=snippet_of(tag), source=context.source,
                details={"element": tag.name, "names": names,
                         "vendor": ", ".join(vendors), "count": len(findings)},
                fix_snippet=_without(tag, findings),
            ))
        return issues

    @staticmethod
    def _artifacts(tag) -> list:
        found = []
        classes = tag.get("class") or []
        if isinstance(classes, str):  # some parsers hand back a raw string
            classes = classes.split()
        for token in classes:
            vendor = _vendor_in_token(token)
            if vendor:
                found.append(("class", token, vendor))
        for name in tag.attrs:
            lowered = name.lower()
            if not lowered.startswith(_VENDOR_DATA_PREFIXES):
                continue
            vendor = next((w for w in _VENDOR_WORDS if w in lowered), "gpt")
            found.append(("attribute", name, vendor))
        return found


def _without(tag, findings) -> str:
    """The same element with every offending class token and attribute gone -
    the element itself is not the problem, and removing it would take the
    content with it."""
    attributes = dict(tag.attrs)
    drop_classes = {name for kind, name, _v in findings if kind == "class"}
    for kind, name, _vendor in findings:
        if kind == "attribute":
            attributes.pop(name, None)
    if drop_classes:
        classes = attributes.get("class") or []
        if isinstance(classes, str):
            classes = classes.split()
        remaining = [c for c in classes if c not in drop_classes]
        if remaining:
            attributes["class"] = remaining
        else:
            attributes.pop("class", None)
    parts = []
    for key, value in attributes.items():
        if isinstance(value, list):
            value = " ".join(value)
        parts.append(f'{key}="{value}"' if value != "" else key)
    joined = (" " + " ".join(parts)) if parts else ""
    return f"<{tag.name}{joined}>"


RuleRegistry.register(MarkupProvenanceArtifact)
