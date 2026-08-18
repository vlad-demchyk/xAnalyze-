"""The single offline detector: style/cliché analysis and the non-keyboard
character pass, in one backend.

Why they were merged. They used to be two entries in the detector dropdown
plus a checkbox in Settings, and the combination was confusing for a reason
that has nothing to do with the user: they are not alternatives. One reads
*wording*, the other reads *characters*; both run locally, both cost
nothing, and a passage can be flagged by either or both. Making them
mutually exclusive in the UI meant every scan silently gave up one of two
free signals, and the checkbox that partially undid that was a second way
to express the same choice.

So the detector list is now a real choice between things that are actually
alternatives:

    offline            — this class: everything that runs locally and free
    claude-llm-judge   — a live model reads the text (costs money)
    xformat-llm-judge  — the same, billed to an xFormat subscription
    claude-official-watermark — placeholder; see claude_watermark_stub.py

Which of the two passes contributed a given finding is not lost — it is
recorded in `TextSpan.details["source"]` ("characters" or "style"), which
is what lets the UI group findings, and what lets the character-only fix
button keep working exactly as before.

The character pass can still be narrowed (or switched off entirely) with
`categories=`, because that is a genuine content decision — whether a
correctly-typeset em dash counts as a finding depends on the site.
"""
from __future__ import annotations

from models import TextSpan
from unicode_rules import ALL_CATEGORIES
from .base import Detector
from .factory import DetectorFactory
from .heuristic import HeuristicDetector
from .unicode_anomalies import UnicodeAnomalyDetector

#: Recorded on every span so callers can tell the two passes apart.
SOURCE_STYLE = "style"
SOURCE_CHARACTERS = "characters"


class OfflineDetector(Detector):
    name = "offline"
    display_name = "Offline — wording + non-keyboard characters (free)"
    supported_languages = ("uk", "it", "en")

    def __init__(self, categories: tuple = ALL_CATEGORIES,
                 include_style: bool = True, **config):
        super().__init__(**config)
        self.categories = tuple(categories) if categories else ()
        self.include_style = include_style
        self._style = HeuristicDetector(**config)
        self._characters = (
            UnicodeAnomalyDetector(categories=self.categories, **config)
            if self.categories else None
        )

    def analyze_block(self, block) -> list[TextSpan]:
        spans: list[TextSpan] = []
        if self.include_style:
            spans.extend(self._style.analyze_block(block))
        if self._characters is not None:
            spans.extend(self._characters.analyze_block(block))
        # Both passes already stamp `details["source"]` and their own
        # `detector_name`; the name is rewritten here so a re-analysis that
        # replaces "every span this detector produced" matches all of them.
        for span in spans:
            span.details.setdefault("source", SOURCE_STYLE)
            span.detector_name = self.name
        spans.sort(key=lambda s: (s.start, s.end))
        return spans

    def analyze_blocks(self, blocks: list) -> list[TextSpan]:
        spans: list[TextSpan] = []
        for block in blocks:
            try:
                spans.extend(self.analyze_block(block))
            except Exception as exc:  # noqa: BLE001 - one bad block can't stop a scan
                spans.append(self._error_span(block, exc))
        return spans


DetectorFactory.register(OfflineDetector.name, OfflineDetector)
