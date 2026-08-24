"""Verdicts a model has already given, kept so it is never asked twice.

Two problems, one answer.

**Cost.** Deduplicating within a run stops the same header being judged ten
times; it does nothing about the same site being scanned again tomorrow. A
judged passage is a question with a fixed answer, and paying for it a second
time buys nothing.

**Determinism.** The judge is not deterministic: two runs of one site with
identical flags returned 6 findings and then 24. That cannot be fixed at the
source - no route here exposes a temperature or a seed, and the Claude Code
CLI has no flag for either. So identical output cannot be *requested*. It can
only be *remembered*, which is what this does: the second run of a passage
returns exactly what the first run got.

That makes the cache load-bearing rather than an optimisation, and it is why
it stores the whole span list rather than a score: a verdict is what the
report prints, so anything less would drift from what the first run said.

**What invalidates an entry.** The passage, the detector, the model, the
effort, and the prompt. Each of those changes the question; serving an old
answer after any of them changed would be answering a question nobody asked.
The prompt is versioned by its own hash, so editing the rubric in
`detectors/claude_llm_judge.py` invalidates every entry without anyone having
to remember to bump a number.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

#: Where verdicts live. Beside the scan cache and the run history, under the
#: user's home rather than the working directory: the same passage judged from
#: two checkouts of one project is the same passage.
CACHE_DIR = Path.home() / ".xanalyze" / "judgments"

#: Overrides where verdicts are kept. For CI, for a container, and above all
#: for tests: without it a test run writes into the developer's real cache and
#: the *next* test run reads its own leftovers back as model answers, which is
#: how a green suite stops meaning anything.
DIR_ENV = "XANALYZE_JUDGMENT_CACHE"


def cache_dir() -> Path:
    import os

    override = os.environ.get(DIR_ENV)
    return Path(override).expanduser() if override else CACHE_DIR

#: Entries older than this are dropped on load. Long enough that a monthly
#: re-scan still hits, short enough that a model's behaviour changing under a
#: stable name does not haunt someone for a year.
MAX_AGE_DAYS = 90


def _fingerprint(*parts) -> str:
    # A separator no text can contain, so ("ab", "c") and ("a", "bc")
    # cannot fingerprint alike.
    joined = "\x00".join(str(p or "") for p in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:20]


class JudgmentCache:
    """One file per (detector, model, effort, prompt), holding many passages.

    Per configuration rather than one big file, so switching a model does not
    make the file that holds the other model's answers larger and slower for
    no reason - and so clearing one configuration is deleting one file.
    """

    def __init__(self, detector: str, model: str = "", effort: str = "",
                 prompt: str = "", directory: Path | None = None) -> None:
        self.key = _fingerprint(detector, model, effort, prompt)
        self.directory = Path(directory) if directory else cache_dir()
        self.path = self.directory / f"{self.key}.json"
        self._entries: dict = {}
        self._dirty = False
        self.hits = 0
        self.misses = 0
        self._load()

    # ---------------------------------------------------------------- disk
    def _load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(raw, dict):
            return
        cutoff = time.time() - MAX_AGE_DAYS * 86400
        self._entries = {
            key: value for key, value in raw.items()
            if isinstance(value, dict) and value.get("at", 0) >= cutoff
        }
        # Expiring entries is a write, but not one worth doing on a read: the
        # next `save` carries it, and a run that judges nothing new has no
        # reason to touch the disk at all.
        self._dirty = len(self._entries) != len(raw)

    def save(self) -> None:
        if not self._dirty:
            return
        self.directory.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".json.tmp")
        temp.write_text(json.dumps(self._entries, ensure_ascii=False),
                        encoding="utf-8")
        temp.replace(self.path)
        self._dirty = False

    # -------------------------------------------------------------- lookup
    @staticmethod
    def passage_key(text: str, language: str | None = None) -> str:
        from duplicates import mask_generated_ids

        normalised = mask_generated_ids(" ".join((text or "").split()))
        return _fingerprint(normalised, language or "")

    def get(self, text: str, language: str | None = None):
        """The stored verdict, or None. Counts the hit for reporting."""
        entry = self._entries.get(self.passage_key(text, language))
        if entry is None:
            self.misses += 1
            return None
        self.hits += 1
        return entry.get("spans", [])

    def put(self, text: str, spans: list, language: str | None = None) -> None:
        self._entries[self.passage_key(text, language)] = {
            "at": int(time.time()),
            "spans": spans,
        }
        self._dirty = True

    # --------------------------------------------------------------- admin
    def clear(self) -> None:
        self._entries = {}
        self._dirty = True
        self.save()
        self.path.unlink(missing_ok=True)

    def __len__(self) -> int:
        return len(self._entries)

    def summary(self) -> str:
        total = self.hits + self.misses
        if not total:
            return ""
        return (f"{self.hits}/{total} passage(s) already judged, "
                f"{self.misses} sent to the model")


def span_to_record(span) -> dict:
    """A `TextSpan` as plain data. Only what the report reads."""
    confidence = span.confidence
    return {
        "start": span.start,
        "end": span.end,
        "score": span.score,
        "confidence": getattr(confidence, "value", confidence),
        "detector_name": span.detector_name,
        "explanation": span.explanation,
        "details": dict(span.details or {}),
    }


def record_to_span(record: dict, block):
    """The stored verdict, back as a `TextSpan` against `block`.

    Rebuilt against whichever occurrence is being reported, so a cached
    verdict lands on the right page with the right block id - the identity is
    the passage, and the place is not part of it.
    """
    from models import Confidence, TextSpan

    confidence = record.get("confidence")
    try:
        confidence = Confidence(confidence)
    except ValueError:
        from models import score_to_confidence

        confidence = score_to_confidence(float(record.get("score", 0.0)))
    return TextSpan(
        block_id=block.block_id,
        start=int(record.get("start", 0)),
        end=int(record.get("end", 0)),
        score=float(record.get("score", 0.0)),
        confidence=confidence,
        detector_name=record.get("detector_name", ""),
        explanation=record.get("explanation", ""),
        details=dict(record.get("details") or {}),
    )
