"""Both engines over the same text, in one finding list.

The offline pass runs first and costs nothing; the model then reads the same
blocks, which does two things at once: it says whether it sees what the
offline signals saw, and it flags passages the offline pass has no signal
for at all. That is what "hybrid" means here, and it is a third answer, not
a convenience wrapper around the other two - running the two detectors
separately and concatenating their output lists the same passage twice, once
per engine, with no indication that they are the same passage.

Three rules decide the merge, and each exists because of what the alternative
would cost the reader:

**Agreement collapses into one finding, and says so.** A model span that
overlaps an offline style span becomes a single span carrying both records
(`details["offline"]`), because two entries for one sentence is how a list of
findings stops being read.

**Disagreement is not silently resolved.** An offline finding the model did
not confirm stays in the list, marked `agreement: "offline-only"`; the model
not quoting a passage is not evidence the passage is clean, and dropping it
would trade a visible weak finding for an invisible one. The reverse case is
marked `"model-only"`, which is the interesting half: those are the findings
the free engine cannot produce at all.

**Nothing is boosted for agreeing.** The merged span takes the higher of the
two scores, not a sum or an invented bonus - the thresholds were calibrated
on a corpus (see `scripts/calibrate.py`), and a score that means something
different in hybrid runs than in offline runs would quietly invalidate that.

Character findings never merge with anything: they are exact defects on
exact codepoints, they are not a matter of opinion, and no model span can
confirm or contradict them.
"""
from __future__ import annotations

from models import Confidence, TextBlock, TextSpan
from unicode_rules import ALL_CATEGORIES
from .base import Detector
from .factory import DetectorFactory
from .offline import OfflineDetector, SOURCE_STYLE

#: `details["agreement"]` values. Written on every style/model span so the
#: window and the report can say which engine produced a finding without
#: having to know which engines ran.
AGREE_BOTH = "both"
AGREE_OFFLINE_ONLY = "offline-only"
AGREE_MODEL_ONLY = "model-only"

_CONFIDENCE_ORDER = {Confidence.LOW: 0, Confidence.MEDIUM: 1, Confidence.HIGH: 2}


def _stronger(first: Confidence, second: Confidence) -> Confidence:
    return max((first, second), key=lambda c: _CONFIDENCE_ORDER.get(c, 0))


def _overlaps(one: TextSpan, other: TextSpan) -> bool:
    return one.start < other.end and other.start < one.end


class HybridDetector(Detector):
    """The offline detector and a judge, over the same blocks, merged."""

    name = "hybrid"
    display_name = "Hybrid — offline pass, checked and extended by a model"
    #: Not declared here for the same reason as `offline`: each half answers
    #: for itself, and the model half is not calibrated by word list at all.
    #: The offline half already runs the character pass, so the caller must
    #: not run it a second time - see `ui/worker.run_unicode_pass`.
    includes_character_pass = True

    def __init__(self, judge_name: str = "claude-llm-judge",
                 judge_config: dict | None = None,
                 categories: tuple = ALL_CATEGORIES, **config):
        super().__init__(**config)
        self.judge_name = judge_name
        self.categories = tuple(categories) if categories else ()
        self._offline = OfflineDetector(categories=self.categories)
        # Built here rather than lazily inside `analyze_blocks`: an unusable
        # account should be reported before a scan spends time crawling, not
        # after it has already produced half an answer.
        self._judge = DetectorFactory.create(judge_name, **(judge_config or {}))

    def analyze_block(self, block: TextBlock) -> list[TextSpan]:
        return self.analyze_blocks([block])

    def analyze_blocks(self, blocks: list[TextBlock]) -> list[TextSpan]:
        offline_spans = self._offline.analyze_blocks(blocks)
        # `DetectorUnavailable` is deliberately not caught. Falling back to
        # the offline result would hand the user exactly what the hybrid
        # option exists to stop: a run that was asked for a model pass,
        # silently answered without one, and looked successful.
        model_spans = self._judge.analyze_blocks(blocks)
        return self._merge(blocks, offline_spans, model_spans)

    # ------------------------------------------------------------- merging

    def _merge(self, blocks, offline_spans, model_spans) -> list[TextSpan]:
        offline_by_block: dict[str, list[TextSpan]] = {}
        model_by_block: dict[str, list[TextSpan]] = {}
        for span in offline_spans:
            offline_by_block.setdefault(span.block_id, []).append(span)
        for span in model_spans:
            model_by_block.setdefault(span.block_id, []).append(span)

        merged: list[TextSpan] = []
        # Block order, not span order: the list the user reads follows the
        # document, and sorting by block_id would follow a hash instead.
        for block in blocks:
            merged.extend(self._merge_block(
                offline_by_block.pop(block.block_id, []),
                model_by_block.pop(block.block_id, []),
            ))
        # Anything addressed to a block that was not in `blocks` at all can
        # only be a bug in a detector, but dropping it here would hide that
        # bug rather than fix it.
        for leftover in list(offline_by_block.values()) + list(model_by_block.values()):
            merged.extend(leftover)
        return merged

    def _merge_block(self, offline_spans, model_spans) -> list[TextSpan]:
        # The offline pass returns a span for every block it reads, scored
        # 0.0 when nothing fired - the callers are what drop the weak ones
        # (`confidence != LOW` is the rule everywhere else in the app). So
        # "the offline engine flagged this too" has to mean a span that
        # would actually be shown; without this test every model finding in
        # a scanned block would be labelled as confirmed by an engine that
        # in fact reported nothing.
        style = [s for s in offline_spans
                 if (s.details or {}).get("source") == SOURCE_STYLE
                 and s.confidence != Confidence.LOW]
        # By source, not by "everything not in `style`": TextSpan is a
        # dataclass, so two identical character findings compare equal and a
        # membership test would drop one of them. The weak style spans ride
        # along here too, unlabelled: they are not findings, and the caller
        # filters them out on the same rule it always has.
        others = [s for s in offline_spans
                  if (s.details or {}).get("source") != SOURCE_STYLE
                  or s.confidence == Confidence.LOW]

        absorbed: list[int] = []
        result: list[TextSpan] = []
        for span in model_spans:
            # A block the model could not judge covers the whole block by
            # construction (see `Detector._error_span`), so letting it match
            # would swallow every offline finding in that block behind a
            # failure notice.
            if (span.details or {}).get("error"):
                result.append(span)
                continue
            matches = [s for s in style
                       if id(s) not in absorbed and _overlaps(s, span)]
            if matches:
                best = max(matches, key=lambda s: s.score)
                absorbed.extend(id(s) for s in matches)
                result.append(self._agreed(span, best))
            else:
                span.details = {**(span.details or {}), "agreement": AGREE_MODEL_ONLY}
                result.append(span)

        for span in style:
            if id(span) in absorbed:
                continue
            span.details = {**(span.details or {}), "agreement": AGREE_OFFLINE_ONLY}
            result.append(span)

        result.extend(others)
        result.sort(key=lambda s: (s.start, s.end))
        for span in result:
            span.detector_name = self.name
        return result

    def _agreed(self, model_span: TextSpan, offline_span: TextSpan) -> TextSpan:
        """One span for a passage both engines flagged.

        The model's span is the one kept: it quotes what it read, so its
        range is the passage the model actually objected to. The offline
        record rides along whole (`details["offline"]`) so the explanation
        can still list which cliché or which signal fired - that is the
        concrete half of the reason, and the model's prose is the other.
        """
        details = {
            **(model_span.details or {}),
            "agreement": AGREE_BOTH,
            "offline": dict(offline_span.details or {}),
            "offline_score": offline_span.score,
            "model_score": model_span.score,
        }
        return TextSpan(
            block_id=model_span.block_id,
            start=model_span.start,
            end=model_span.end,
            score=max(model_span.score, offline_span.score),
            confidence=_stronger(model_span.confidence, offline_span.confidence),
            detector_name=self.name,
            explanation=model_span.explanation,
            replacement=model_span.replacement,
            details=details,
        )


DetectorFactory.register(HybridDetector.name, HybridDetector)
