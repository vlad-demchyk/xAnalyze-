"""Detector for characters no keyboard produces — see unicode_rules.py for
the rule tables and the reasoning behind them.

Unlike the statistical detectors, this one is deterministic: a zero-width
joiner either is or isn't in the text. That has two consequences worth
knowing:

* Its findings need no verification and no model call.
* Its fix needs no model call either. `unicode_rules.clean_text` produces
  the corrected text directly, so the whole flag-and-replace loop runs
  offline and free.
"""
from __future__ import annotations

from lang_detect import guess_language
from models import TextSpan, score_to_confidence
from unicode_rules import ALL_CATEGORIES, CATEGORY_SCORES, find_anomalies
from .base import Detector
from .factory import DetectorFactory


class UnicodeAnomalyDetector(Detector):
    name = "unicode-anomalies"
    display_name = "Non-keyboard characters (offline, exact)"
    supported_languages = ("uk", "it", "en")

    def __init__(self, categories: tuple[str, ...] = ALL_CATEGORIES, **config):
        super().__init__(**config)
        self.categories = tuple(categories) if categories else ALL_CATEGORIES

    def analyze_block(self, block) -> list[TextSpan]:
        language = block.language_hint or guess_language(block.text)
        spans: list[TextSpan] = []
        for anomaly in find_anomalies(block.text, language, self.categories):
            score = CATEGORY_SCORES.get(anomaly.category, 0.5)
            spans.append(
                TextSpan(
                    block_id=block.block_id,
                    start=anomaly.start,
                    end=anomaly.end,
                    score=score,
                    confidence=score_to_confidence(score),
                    detector_name=self.name,
                    explanation=f"[{anomaly.category}] {anomaly.description}",
                    replacement=anomaly.replacement,
                    details={
                        "source": "characters",
                        "category": anomaly.category,
                        "codepoints": [f"U+{ord(ch):04X}" for ch in anomaly.original],
                        "language": language,
                    },
                )
            )
        return spans


# Composed by `detectors/offline.py` rather than registered separately — see
# the note there on why the two offline passes stopped being alternatives.
# The retired name still resolves, so `--detector unicode-anomalies` and an
# older settings.json keep working.
DetectorFactory.register_alias(UnicodeAnomalyDetector.name, "offline")
