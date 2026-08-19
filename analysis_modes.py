"""What to look at, what to look for, and who does the looking.

The window used to ask this as one question with four answers - web page,
repository, site audit, single file - which forced two unrelated choices into
one control. Auditing a site and reading its text are the same source with a
different question asked of it, so picking one of them up front meant picking
the source twice and the analysis never.

Three independent choices replace it:

  source      what is being examined: a site, a repository, one HTML file.
  readers     how it is read: the code as written, the page as a browser
              renders it, or both. Not every source supports both.
  checks      what is being looked for: accessibility, AI-written copy, both.
  methods     who judges: the offline engine, a model, or both.

Keeping them independent is what makes "the same crawl, a different analysis"
expressible at all - and that is the whole point, because re-crawling a site
to change the question is the slowest possible way to answer it.
"""
from __future__ import annotations

from dataclasses import dataclass, field

SOURCE_SITE = "site"
SOURCE_REPO = "repo"
SOURCE_FILE = "file"
SOURCES = (SOURCE_SITE, SOURCE_REPO, SOURCE_FILE)

#: Read the text as it is written: markup, templates, locale files.
READER_CODE = "code"
#: Load it in a real browser and read the rendered result.
READER_BROWSER = "browser"
READERS = (READER_CODE, READER_BROWSER)

CHECK_ACCESSIBILITY = "accessibility"
CHECK_AI_PATTERNS = "ai-patterns"
CHECKS = (CHECK_ACCESSIBILITY, CHECK_AI_PATTERNS)

METHOD_LOCAL = "local"
METHOD_AI = "ai"
METHODS = (METHOD_LOCAL, METHOD_AI)

#: Which readers each source can support at all. A repository has no server to
#: answer a request, so nothing can render it; a site and a self-contained file
#: can be both fetched and rendered, and the difference between those two
#: readings is itself a finding - copy that only exists after hydration.
AVAILABLE_READERS = {
    SOURCE_SITE: (READER_CODE, READER_BROWSER),
    SOURCE_REPO: (READER_CODE,),
    SOURCE_FILE: (READER_CODE, READER_BROWSER),
}


def available_readers(source: str) -> tuple:
    return AVAILABLE_READERS.get(source, (READER_CODE,))


def supports_browser(source: str) -> bool:
    return READER_BROWSER in available_readers(source)


@dataclass
class AnalysisRequest:
    """One run, as the user described it.

    Invalid combinations are not errors to raise at the user: a request is
    normalised into the nearest runnable one, and `notes` records every
    adjustment so the window can say what it did instead of silently doing
    something else.
    """
    source: str = SOURCE_SITE
    target: str = ""
    readers: tuple = (READER_CODE,)
    checks: tuple = CHECKS
    methods: tuple = (METHOD_LOCAL,)
    #: Set by the caller from the account state; a request cannot know on its
    #: own whether anything is signed in.
    ai_available: bool = False
    notes: list = field(default_factory=list)

    def normalised(self) -> "AnalysisRequest":
        notes: list = []
        source = self.source if self.source in SOURCES else SOURCE_SITE
        if source != self.source:
            notes.append(f"unknown source {self.source!r}, using {source}")

        allowed = available_readers(source)
        readers = tuple(r for r in READERS if r in self.readers and r in allowed)
        dropped = [r for r in self.readers if r not in allowed]
        for reader in dropped:
            notes.append(f"{reader} reader is not possible for a {source}")
        if not readers:
            readers = (allowed[0],)
            notes.append(f"nothing left to read with, using {readers[0]}")

        checks = tuple(c for c in CHECKS if c in self.checks)
        if not checks:
            checks = CHECKS
            notes.append("no check chosen, running both")

        methods = tuple(m for m in METHODS if m in self.methods)
        if METHOD_AI in methods and not self.ai_available:
            methods = tuple(m for m in methods if m != METHOD_AI)
            notes.append("no account or key for the AI pass, running offline only")
        if not methods:
            methods = (METHOD_LOCAL,)
            notes.append("no method left, running the offline engine")

        return AnalysisRequest(
            source=source, target=self.target, readers=readers, checks=checks,
            methods=methods, ai_available=self.ai_available, notes=notes,
        )

    # ---------------------------------------------------------------- queries
    #
    # Named questions rather than membership tests at every call site: the
    # window, the worker and the report all ask the same things, and spelling
    # `READER_BROWSER in request.readers` in three places is how the three
    # drift apart.

    @property
    def wants_browser(self) -> bool:
        return READER_BROWSER in self.readers

    @property
    def wants_code(self) -> bool:
        return READER_CODE in self.readers

    @property
    def wants_accessibility(self) -> bool:
        return CHECK_ACCESSIBILITY in self.checks

    @property
    def wants_ai_patterns(self) -> bool:
        return CHECK_AI_PATTERNS in self.checks

    @property
    def wants_local(self) -> bool:
        return METHOD_LOCAL in self.methods

    @property
    def wants_ai(self) -> bool:
        return METHOD_AI in self.methods

    def reuses_extraction(self, previous: "AnalysisRequest | None") -> bool:
        """Can the pages already fetched for `previous` answer this request?

        The expensive half of a run is getting the documents; the analysis over
        them is cheap by comparison. So changing the question - accessibility
        instead of copy, a model instead of the offline engine - must not go
        back to the network, and this is the test for when it may not.
        """
        if previous is None:
            return False
        if (previous.source, previous.target) != (self.source, self.target):
            return False
        # A browser pass reads more than a fetch does, so a run that only
        # fetched cannot answer one that wants the rendered page.
        return set(self.readers).issubset(set(previous.readers))
