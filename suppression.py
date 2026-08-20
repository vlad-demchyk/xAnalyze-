"""Ignoring findings you have already decided about.

Any detector that flags style will be wrong sometimes, and some of what it
gets right will still be wanted: a company whose product genuinely is
"comprehensive" does not need that word underlined on every page forever. A
tool with no way to say "not this one" gets switched off entirely, so the
suppression list is part of the detector, not an afterthought.

Five levels, from the most surgical to the broadest, because they answer
different questions:

* **fingerprint** — "this exact finding, here, is fine." Survives a
  re-scan, and only this one.
* **phrase** — "never flag this word or phrase at all." For house style.
* **rule** — "switch this check off." A signal (`cliches`, `dashes`), a
  character category (`typography`), or an accessibility rule id
  (`link-text-vague`). One namespace on purpose: the user thinks in terms
  of "the check that keeps bothering me", not in terms of which subsystem
  it came from.
* **path** — "not in this file or on this URL." gitignore-style patterns
  and URL globs — generated files, a vendored theme, a staging domain.
* **selector** — "not inside this part of the page." CSS selectors, which
  is also exactly the shape `axe.run({exclude})` takes, so one list drives
  both the text analysis and the accessibility engine rather than two.

Where the list lives:

1. `Settings.ignore` — the user's own, across every project.
2. `.xanalyze-ignore` in the scanned folder — the project's own, committed
   alongside the code so a team shares one decision instead of each member
   re-dismissing the same finding.

Both are read; neither overrides the other. That is deliberate: a personal
"I never want this" and a project's "we decided this is fine" are both
true at once, and making one win would silently discard a decision.
"""
from __future__ import annotations

import fnmatch
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

#: The file a project keeps its own suppressions in.
IGNORE_FILENAME = ".xanalyze-ignore"

#: Section headers inside that file. A bare line with no section yet is
#: treated as a phrase, because that is what people write first.
_SECTIONS = {
    "phrases": "phrases",
    "phrase": "phrases",
    "rules": "rules",
    "rule": "rules",
    "paths": "paths",
    "path": "paths",
    "selectors": "selectors",
    "selector": "selectors",
    "fingerprints": "fingerprints",
    "fingerprint": "fingerprints",
}

_SECTION_RE = re.compile(r"^\[(?P<name>[\w-]+)\]\s*$")


@dataclass
class Suppressions:
    """Everything the user has said they do not want to be told about."""
    phrases: list = field(default_factory=list)
    rules: list = field(default_factory=list)
    paths: list = field(default_factory=list)
    selectors: list = field(default_factory=list)
    fingerprints: list = field(default_factory=list)

    def __post_init__(self):
        # Phrases and rules are matched case-insensitively; paths and
        # selectors are not, because file systems and CSS are not.
        self._phrases_lower = {p.strip().lower() for p in self.phrases if p.strip()}
        self._rules = {r.strip() for r in self.rules if r.strip()}
        self._fingerprints = {f.strip() for f in self.fingerprints if f.strip()}

    # ------------------------------------------------------------- loading

    @classmethod
    def from_dict(cls, data: dict | None) -> "Suppressions":
        data = data or {}
        return cls(
            phrases=list(data.get("phrases") or []),
            rules=list(data.get("rules") or []),
            paths=list(data.get("paths") or []),
            selectors=list(data.get("selectors") or []),
            fingerprints=list(data.get("fingerprints") or []),
        )

    def to_dict(self) -> dict:
        return {
            "phrases": list(self.phrases),
            "rules": list(self.rules),
            "paths": list(self.paths),
            "selectors": list(self.selectors),
            "fingerprints": list(self.fingerprints),
        }

    @classmethod
    def parse(cls, text: str) -> "Suppressions":
        """Read the `.xanalyze-ignore` format.

        Deliberately the simplest thing that can be edited by hand and read
        in a diff — sections in brackets, one entry per line, `#` comments.
        A config format nobody can read without documentation is a config
        format nobody maintains.
        """
        buckets = {"phrases": [], "rules": [], "paths": [], "selectors": [],
                   "fingerprints": []}
        current = "phrases"
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            match = _SECTION_RE.match(line)
            if match:
                current = _SECTIONS.get(match.group("name").lower(), current)
                continue
            buckets[current].append(line)
        return cls(**buckets)

    @classmethod
    def load(cls, settings=None, root: str | None = None) -> "Suppressions":
        """The user's list and the project's list, merged."""
        merged = {"phrases": [], "rules": [], "paths": [], "selectors": [],
                  "fingerprints": []}

        if settings is not None:
            for key, values in cls.from_dict(getattr(settings, "ignore", None)).to_dict().items():
                merged[key].extend(values)

        for path in _ignore_files(root):
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            for key, values in cls.parse(text).to_dict().items():
                merged[key].extend(values)

        # De-duplicate while keeping the order they were written in, so the
        # settings dialog shows the list back the way the user typed it.
        for key, values in merged.items():
            seen = set()
            merged[key] = [v for v in values if not (v in seen or seen.add(v))]
        return cls(**merged)

    # ------------------------------------------------------------ matching

    def ignores_rule(self, rule_id: str) -> bool:
        return bool(rule_id) and rule_id in self._rules

    def ignores_phrase(self, phrase: str) -> bool:
        return phrase.strip().lower() in self._phrases_lower

    def ignores_fingerprint(self, value: str) -> bool:
        return value in self._fingerprints

    def ignores_path(self, source: str) -> bool:
        """Match a file path or a URL against the path patterns.

        One list handles both because the user is expressing the same thing
        either way — "not this part of the site" — and asking them to keep
        two lists that differ only in whether the string starts with http
        would be a distinction that serves the code, not them.
        """
        if not source or not self.paths:
            return False
        candidates = {source}
        # A path also matches on its tail, so "src/generated/" works without
        # the user having to write out an absolute path.
        posix = source.replace("\\", "/")
        candidates.add(posix)
        candidates.add(Path(posix).name)
        for pattern in self.paths:
            pattern = pattern.strip()
            if not pattern:
                continue
            if pattern.endswith("/"):
                if f"/{pattern.rstrip('/')}/" in f"/{posix}/":
                    return True
                continue
            if any(fnmatch.fnmatch(c, pattern) for c in candidates):
                return True
            if pattern in posix:
                return True
        return False

    def ignores_selector(self, selector: str) -> bool:
        if not selector or not self.selectors:
            return False
        return any(s.strip() and s.strip() in selector for s in self.selectors)

    def is_empty(self) -> bool:
        return not any((self.phrases, self.rules, self.paths, self.selectors,
                        self.fingerprints))

    # --------------------------------------------------------------- writing

    def render(self) -> str:
        """The inverse of `parse`: back into the section format on disk.

        Round-trips through `parse` losslessly for content (comments are the
        one thing not preserved - there is nowhere to put them back once the
        file has been read into a dataclass).
        """
        sections = (
            ("fingerprints", self.fingerprints),
            ("phrases", self.phrases),
            ("rules", self.rules),
            ("paths", self.paths),
            ("selectors", self.selectors),
        )
        lines: list = []
        for name, values in sections:
            if not values:
                continue
            lines.append(f"[{name}]")
            lines.extend(values)
            lines.append("")
        return "\n".join(lines).rstrip() + "\n" if lines else ""


def _ignore_files(root: str | None):
    """The project's ignore file, if the scanned folder has one.

    Only the root of the scan is checked, not every directory: nested
    ignore files would mean a finding's fate depends on which folder the
    scan happened to start from, which is a rule nobody can hold in mind.
    """
    if not root:
        return []
    path = Path(root)
    if path.is_file():
        path = path.parent
    candidate = path / IGNORE_FILENAME
    return [candidate] if candidate.is_file() else []


# ------------------------------------------------------------- fingerprints

def fingerprint(source: str, text: str, kind: str = "") -> str:
    """A stable id for one finding, so "ignore this one" survives a re-scan.

    Built from the source document, the flagged text and the kind of finding
    — deliberately **not** from character offsets, which shift the moment a
    line is added above and would make every dismissal expire on the next
    edit.
    """
    payload = "␟".join((kind or "", source or "", " ".join((text or "").split())))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def span_fingerprint(span, block) -> str:
    source = getattr(block, "file_path", None) or getattr(block, "page_url", "") or ""
    text = block.text[span.start:span.end]
    kind = (span.details or {}).get("source", span.detector_name)
    return fingerprint(source, text, kind)


def issue_fingerprint(issue) -> str:
    return fingerprint(issue.source, issue.snippet or issue.selector, issue.rule_id)


def add_fingerprint_to_ignore_file(root: str, value: str) -> Path:
    """Append one "ignore this exact finding" line to the project's ignore
    file, creating it if it does not exist yet.

    Read-modify-write through `parse`/`render` rather than a raw text append,
    so a fingerprint added next to a file that already has a `[rules]` or
    `[phrases]` section lands in the right one instead of at the end under
    whatever section happened to be last. Idempotent: the same finding
    dismissed twice is still one line.
    """
    path = Path(root)
    if path.is_file():
        path = path.parent
    ignore_path = path / IGNORE_FILENAME
    existing = (Suppressions.parse(ignore_path.read_text(encoding="utf-8"))
                if ignore_path.is_file() else Suppressions())
    if value not in existing.fingerprints:
        existing.fingerprints.append(value)
    ignore_path.write_text(existing.render(), encoding="utf-8")
    return ignore_path


# ----------------------------------------------------------------- filtering

def filter_spans(spans: list, blocks_by_id: dict, suppressions: Suppressions) -> list:
    """Drop text findings the user has already decided about.

    Phrase suppression is applied *inside* a finding rather than to the
    whole finding: a sentence flagged for three clichés, one of which is
    house style, should still be reported for the other two — but with a
    lower score, because part of the reason for the score just went away.
    """
    if suppressions.is_empty():
        return spans

    kept = []
    for span in spans:
        block = blocks_by_id.get(span.block_id)
        if block is None:
            kept.append(span)
            continue

        source = getattr(block, "file_path", None) or getattr(block, "page_url", "") or ""
        if suppressions.ignores_path(source):
            continue
        if suppressions.ignores_selector(getattr(block, "dom_path", "")):
            continue
        if suppressions.ignores_fingerprint(span_fingerprint(span, block)):
            continue

        details = span.details or {}
        source_kind = details.get("source")
        if source_kind == "characters":
            if suppressions.ignores_rule(details.get("category", "")):
                continue
        elif source_kind == "style":
            span = _apply_style_suppressions(span, suppressions)
            if span is None:
                continue
        kept.append(span)
    return kept


def _apply_style_suppressions(span, suppressions: Suppressions):
    """Remove suppressed signals from a style finding and re-score it.

    Returns None when nothing is left to say. Re-scoring rather than
    dropping matters: leaving the original score after removing the reason
    for it would show a "high confidence" finding whose explanation no
    longer contains anything.
    """
    from models import score_to_confidence

    details = dict(span.details or {})
    original_cliches = list(details.get("cliches") or [])
    original_structural = list(details.get("structural") or [])
    signals = dict(details.get("signals") or {})

    cliches = [c for c in original_cliches if not suppressions.ignores_phrase(c)]
    structural = original_structural if not suppressions.ignores_rule("structural") else []
    for signal in list(signals):
        if suppressions.ignores_rule(signal):
            signals[signal] = 0.0

    removed = (len(original_cliches) - len(cliches)) > 0 \
        or len(structural) != len(original_structural) \
        or signals != (details.get("signals") or {})
    if not removed:
        return span

    # Scored by the detector's own function rather than by a copy of its
    # formula. The copy had already drifted once: it still averaged in a
    # missing signal as zero after the detector had learned to leave one out,
    # and it still weighed a phrase the same as a single word.
    from detectors.heuristic import combine_score

    score = combine_score(
        uniformity=signals.get("uniformity"),
        repetition=signals.get("repetition"),
        dashes=signals.get("dashes"),
        structural=bool(structural),
        cliches=cliches,
    )

    if not cliches and not structural and score < 0.33:
        return None

    details["cliches"] = cliches
    details["structural"] = structural
    details["signals"] = signals
    details["suppressed"] = True

    from dataclasses import replace
    return replace(span, score=score, confidence=score_to_confidence(score),
                   details=details)


def filter_issues(issues: list, suppressions: Suppressions) -> list:
    """Drop accessibility findings the user has already decided about."""
    if suppressions.is_empty():
        return issues
    kept = []
    for issue in issues:
        if suppressions.ignores_rule(issue.rule_id):
            continue
        if suppressions.ignores_path(issue.source):
            continue
        if suppressions.ignores_selector(issue.selector):
            continue
        if suppressions.ignores_fingerprint(issue_fingerprint(issue)):
            continue
        kept.append(issue)
    return kept


#: Everything that can go in the `[rules]` section, for the settings UI to
#: offer as a list rather than making the user guess the spelling.
def known_rule_ids() -> dict:
    from unicode_rules import ALL_CATEGORIES

    ids = {
        "style": ["uniformity", "repetition", "dashes", "structural", "cliches"],
        "characters": list(ALL_CATEGORIES),
    }
    try:
        import audit
        ids["accessibility"] = audit.RuleRegistry.available()
    except Exception:  # noqa: BLE001 - the a11y package is optional at import time
        ids["accessibility"] = []
    return ids
