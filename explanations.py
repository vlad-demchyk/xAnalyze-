"""Turns a `TextSpan` into something a person can act on: why it was
flagged, and — when the fix is decided by a rule — what to replace it with.

The detectors record *what fired* as data (`TextSpan.details`); this module
renders that into a sentence in the user's language and pairs it with an
offline replacement from `offline_suggestions`. Splitting it this way is
what lets the UI language be changed after a scan without re-running it,
and keeps `--json` output language-independent.

Honesty rules baked in here, because this is the text the user reads before
deciding whether to rewrite something:

* Every style explanation ends with the reminder that these signals are
  weak. Uniform, cliché-heavy prose is also what careful human marketing
  copy looks like.
* When no rule applies, `suggestion` is None and `suggestion_note` says the
  rewrite needs a model — it never invents a "suggestion" out of the
  statistical signals.
* A character finding says exactly which codepoint was found and exactly
  what it becomes, because that correction is a fact, not an opinion.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import offline_suggestions
from i18n.translations import t

#: Signal strength at which a statistical signal is worth mentioning at all.
#: Below this the number is noise and listing it would pad the explanation
#: with reasons that did not actually drive the score.
SIGNAL_FLOOR = 0.45


@dataclass
class Explanation:
    title: str
    reasons: list = field(default_factory=list)
    caveat: str = ""
    suggestion: str | None = None
    suggestion_note: str = ""

    def as_text(self) -> str:
        parts = [self.title]
        parts.extend(f"• {reason}" for reason in self.reasons)
        if self.caveat:
            parts.append(self.caveat)
        return "\n".join(parts)


def render(span, block_text: str, lang: str = "uk") -> Explanation:
    """Explain one span. `block_text` is the full block the span points
    into, needed because a suggestion is computed from the flagged text."""
    details = span.details or {}
    source = details.get("source")
    if source == "characters":
        return _character_explanation(span, details, lang)
    if source == "style":
        return _style_explanation(span, details, block_text, lang)
    return _opaque_explanation(span, lang)


# ------------------------------------------------------------- characters

def _character_explanation(span, details: dict, lang: str) -> Explanation:
    category = details.get("category", "")
    codepoints = ", ".join(details.get("codepoints", []))
    reasons = [t(f"why_char_{category}", lang)] if category else []
    if codepoints:
        reasons.append(t("why_char_codepoints", lang, codepoints=codepoints))

    original = span.details.get("original", "")
    if span.replacement is None:
        suggestion, note = None, t("suggest_none_rule", lang)
    elif span.replacement == "":
        suggestion, note = "", t("suggest_delete", lang)
    else:
        suggestion, note = span.replacement, t("suggest_exact", lang)

    return Explanation(
        title=t(f"why_char_title_{category}", lang) if category else t("why_char_title", lang),
        reasons=reasons,
        caveat=t("why_char_caveat", lang),
        suggestion=suggestion,
        suggestion_note=note,
    )


# ------------------------------------------------------------------ style

def _style_explanation(span, details: dict, block_text: str, lang: str) -> Explanation:
    reasons = []
    cliches = details.get("cliches") or []
    structural = details.get("structural") or []
    signals = details.get("signals") or {}

    if cliches:
        reasons.append(t("why_cliche", lang, phrases=", ".join(f"«{c}»" for c in cliches)))
    if structural:
        reasons.append(t("why_structural", lang, patterns=", ".join(f"«{s}»" for s in structural)))
    for key, translation_key in (
        ("uniformity", "why_uniformity"),
        ("repetition", "why_repetition"),
        ("dashes", "why_dashes"),
    ):
        value = signals.get(key)
        # None means the passage was too short for this signal to be measured.
        # Reported as nothing rather than as a low value: "uniformity 0.00"
        # claims a measurement that was never taken.
        if value is not None and value >= SIGNAL_FLOOR:
            reasons.append(t(translation_key, lang, value=f"{value:.2f}"))

    if not reasons:
        reasons.append(t("why_weak_combination", lang))

    flagged = block_text[span.start:span.end]
    suggestion = offline_suggestions.suggest(flagged, details.get("language"))
    if suggestion:
        note = t("suggest_offline_wording", lang)
    else:
        # Nothing mechanical to change: the score came from sentence rhythm
        # and word variety, which is a rewrite, not a substitution.
        note = t("suggest_needs_model", lang)

    return Explanation(
        title=t("why_style_title", lang),
        reasons=reasons,
        caveat=t("why_style_caveat", lang),
        suggestion=suggestion,
        suggestion_note=note,
    )


# ----------------------------------------------------------------- other

def _opaque_explanation(span, lang: str) -> Explanation:
    """A detector that doesn't record structured details — the live-model
    judges, whose reason is free prose written by the model itself."""
    return Explanation(
        title=t("why_model_title", lang, detector=span.detector_name),
        reasons=[span.explanation] if span.explanation else [],
        caveat=t("why_model_caveat", lang),
        suggestion=None,
        suggestion_note=t("suggest_needs_model", lang),
    )
