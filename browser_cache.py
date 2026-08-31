"""What a real browser already said about a page, kept between runs.

The browser pass is the expensive half of an audit and the only half that
costs seconds rather than milliseconds: measured on this machine, 12 s for
one page at four widths against 0.05 s for every static rule over the same
markup. A crawl of thirty pages is six minutes of it, and re-running the
same audit an hour later paid that again for a byte-identical page.

**Keyed on the markup, never on the address.** A URL is not an answer: a
page changes, and a cache keyed on where it lives would serve yesterday's
findings about today's page - the exact failure this project refuses
elsewhere. The crawler has already fetched the markup by the time the
browser pass starts, so the key is a hash of *what was served*, together
with everything else that changes the answer: the widths, the engines that
were asked, the rules that were disabled and the selectors that were
excluded. Change any of those and it is a different question, so it is a
different entry.

**What is not cached.** A page that failed to load: an error is a fact
about one attempt, and the next attempt is entitled to a different one.
Measurements are kept, because they were measured on that same markup, but
they are timings from a machine that was doing something else at the time -
`fresh` says which run they came from, so a reader can tell.

The store is a directory of JSON files, one per key-shape, under the user's
home beside the judgment cache. Same reasoning as there: the same page
audited from two checkouts is the same page.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

#: Where entries live.
CACHE_DIR = Path.home() / ".xanalyze" / "browser"

#: Overrides the location. For CI, for containers and above all for tests:
#: without it a test run writes into the developer's real cache and the next
#: run reads its own leftovers back as browser answers.
DIR_ENV = "XANALYZE_BROWSER_CACHE"

#: How long an entry is honoured. A week: long enough that a working session
#: and the next day's re-check are free, short enough that an engine upgrade
#: or a changed environment does not haunt a report for a month.
MAX_AGE_DAYS = 7

#: Above this the file is rewritten from scratch rather than grown. A crawl
#: of a large site puts a few hundred entries in; a cache nobody prunes is a
#: cache that eventually costs more to read than the pass it saves.
MAX_ENTRIES = 500


def cache_dir() -> Path:
    override = os.environ.get(DIR_ENV)
    return Path(override) if override else CACHE_DIR


def markup_key(markup: str) -> str:
    """The identity of one page: what the server actually sent."""
    return hashlib.sha256((markup or "").encode("utf-8")).hexdigest()[:32]


def _fingerprint(*parts) -> str:
    # A separator that cannot occur inside any of the parts, so ("ab", "c")
    # and ("a", "bc") are two keys rather than one.
    joined = "\x1f".join(str(part) for part in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:20]


def options_key(options, sizes) -> str:
    """Everything besides the markup that changes what comes back.

    Read off the options object rather than listed by hand where possible:
    a new switch that changes the answer and is not in the key is a cache
    that lies, and that is worse than no cache at all.
    """
    return _fingerprint(
        tuple(sorted(getattr(options, "exclude", ()) or ())),
        tuple(sorted(getattr(options, "disabled_rules", ()) or ())),
        bool(getattr(options, "run_axe", True)),
        bool(getattr(options, "run_htmlcs", True)),
        bool(getattr(options, "run_states", True)),
        bool(getattr(options, "run_measurements", True)),
        bool(getattr(options, "allow_local_files", False)),
        int(getattr(options, "settle_ms", 0) or 0),
        tuple((name, width, height) for name, width, height in (sizes or ())),
    )


def _issue_to_record(issue) -> dict:
    return {
        "rule_id": issue.rule_id,
        "severity": issue.severity,
        "selector": issue.selector,
        "line": issue.line,
        "snippet": issue.snippet,
        "details": issue.details or {},
        "fix_snippet": issue.fix_snippet,
        "confidence": issue.confidence,
        "source": issue.source,
        "category": issue.category,
        "owner": issue.owner,
        "engine": issue.engine,
    }


def _record_to_issue(record: dict, source: str):
    from audit.base import Issue

    data = dict(record)
    # The address is the caller's, not the cache's: the same markup can be
    # served at two URLs, and a finding has to point at the page in hand.
    data["source"] = source
    return Issue(**data)


class BrowserCache:
    """Verdicts for one shape of question: these engines, these widths."""

    def __init__(self, options, sizes, directory: Path | None = None) -> None:
        self.key = options_key(options, sizes)
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
        self._dirty = len(self._entries) != len(raw)

    def save(self) -> None:
        if not self._dirty:
            return
        if len(self._entries) > MAX_ENTRIES:
            keep = sorted(self._entries.items(),
                          key=lambda kv: kv[1].get("at", 0), reverse=True)
            self._entries = dict(keep[:MAX_ENTRIES])
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_suffix(".tmp")
            temp.write_text(json.dumps(self._entries, ensure_ascii=False),
                            encoding="utf-8")
            temp.replace(self.path)
            self._dirty = False
        except OSError:
            # A cache that cannot be written is a slow run, not a failed one.
            pass

    # --------------------------------------------------------------- reads
    def get(self, markup: str, source: str):
        """The stored `PageAudit` for this markup, or None."""
        entry = self._entries.get(markup_key(markup))
        if entry is None:
            self.misses += 1
            return None
        from audit.driver import PageAudit

        self.hits += 1
        return PageAudit(
            url=source,
            issues=[_record_to_issue(record, source)
                    for record in entry.get("issues", [])],
            measurements=entry.get("measurements") or {},
            error="",
            engine_errors={},
            html=entry.get("html", "") or "",
        )

    def put(self, markup: str, page_audit) -> None:
        """Remember one page. A failed pass is not remembered."""
        if getattr(page_audit, "error", ""):
            return
        self._entries[markup_key(markup)] = {
            "at": int(time.time()),
            "issues": [_issue_to_record(issue) for issue in page_audit.issues],
            "measurements": getattr(page_audit, "measurements", {}) or {},
            "html": getattr(page_audit, "html", "") or "",
        }
        self._dirty = True

    def summary(self) -> str:
        """One line for stderr, or empty when there is nothing to say."""
        total = self.hits + self.misses
        if not total or not self.hits:
            return ""
        return (f"{self.hits}/{total} page(s) unchanged since a previous run, "
                f"read from cache instead of the browser")
