"""Applying an audit finding to the file it came from.

Seventeen rules already know the correction: a rule that says the image has
no alternative text also knows the tag should read `alt=""`, and a rule that
says the heading jumped two levels knows which level it should be. Until now
that correction could only be read and retyped, which is the part of an audit
people abandon halfway through a long list.

Three things make writing it back safe enough to offer as a button:

**The element is found in the source, not in the parse.** BeautifulSoup
re-serialises what it parsed - quotes normalised, void elements closed - so
the snippet in a finding never matches the file byte for byte. Writing it back
by string search would corrupt whichever similar tag happened to come first.
Instead the tag is located by its line, then confirmed by comparing its
attributes with the ones the finding recorded, so a line holding three `<img>`
tags still resolves to the right one.

**Nothing is guessed.** A finding whose element cannot be located
unambiguously is skipped and *reported as skipped*, with the reason. A silent
partial application would be worse than no button at all: the list would look
handled while the file was only partly changed.

**Every file keeps its first state.** A `.bak` copy is written before the
first change and never overwritten afterwards, so `undo` returns the file to
how it was before the tool ever touched it, not to the state between two runs.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

#: Anchors that mean "put this inside me" rather than "replace me". A finding
#: about the whole document has to hang off something, and these three are
#: what it hangs off.
CONTAINER_ELEMENTS = {"head", "html", "body"}

#: Elements that never have a closing tag, so "replace the whole element"
#: means "replace the opening tag" for them.
VOID_ELEMENTS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}

_ATTRIBUTE = re.compile(
    r"""([a-zA-Z_:@][-a-zA-Z0-9_:.]*)\s*(?:=\s*("[^"]*"|'[^']*'|[^\s>]+))?""")
_TAG_NAME = re.compile(r"<\s*([a-zA-Z][a-zA-Z0-9-]*)")


#: Marks in a correction that mean "someone still has to write this". A rule
#: that suggests `content="…"` is naming the element to add, not the sentence
#: to put in it, and a canonical link needs the site's real address.
PLACEHOLDERS = ("…", "example.com")

#: Corrections that are a *decision* rather than a correction, and why. These
#: never go in unattended even though the markup they produce is valid, because
#: the next audit would then report the page clean while the page is not.
#:
#: This is the difference between a tool that saves work and one that launders
#: a problem into a green result.
DECISION_RULES = {
    "image-alt": (
        'alt="" declares the image decorative, which is a claim about what '
        'the image is for. Applied to a photograph that carries meaning it '
        'hides that meaning permanently, and hides it from the next audit too'
    ),
    "html-lang": (
        "the language in the correction is a default, not a reading of this "
        "page; declaring the wrong one makes a screen reader pronounce every "
        "word in it with the wrong voice"
    ),
    "image-alt-filename": (
        "replacing a filename with real alternative text means describing "
        "what the picture shows, which needs to be looked at"
    ),
}


@dataclass
class FixPlan:
    """One correction, resolved to an exact range of one file."""
    path: str
    start: int
    end: int
    original: str
    replacement: str
    rule_id: str
    line: int | None = None
    #: "replace" swaps the range; "insert" leaves it and puts the text after it.
    kind: str = "replace"
    #: Set when the correction cannot go in unattended - it still has a
    #: placeholder, or it encodes a decision only a person or a model can
    #: make. Holds the reason, shown to whoever is asked to decide.
    needs_input: str = ""

    @property
    def needs_content(self) -> bool:
        return bool(self.needs_input)

    def with_text(self, text: str) -> "FixPlan":
        """The same correction with a placeholder filled in."""
        replacement = self.replacement
        for mark in PLACEHOLDERS:
            replacement = replacement.replace(mark, text) if mark in replacement else replacement
        return FixPlan(path=self.path, start=self.start, end=self.end,
                       original=self.original, replacement=replacement,
                       rule_id=self.rule_id, line=self.line, kind=self.kind,
                       needs_input="")


@dataclass
class SkippedFix:
    """A finding that could not be applied, and why. Reported, never hidden."""
    rule_id: str
    source: str
    line: int | None
    reason: str


@dataclass
class FixResult:
    files_changed: list = field(default_factory=list)
    applied: list = field(default_factory=list)
    skipped: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    backups: list = field(default_factory=list)


# ------------------------------------------------------------------ planning

def plan_fixes(documents, read_text=None) -> tuple:
    """Turn findings into exact edits.

    Returns `(ready, needs_content, skipped)` - three lists rather than one,
    because they need three different answers. `ready` can be written with
    nobody watching. `needs_content` is a correct edit with a hole in it, and
    writing it unattended would put `content="…"` in someone's `<head>`.
    `skipped` never became an edit at all, and says why.

    `documents` are `DocumentReport`s whose `source` is a path on disk. A
    crawled page is skipped by definition: there is no file to write.
    """
    read_text = read_text or _read
    plans: list = []
    skipped: list = []
    cache: dict = {}

    for document in documents:
        path = document.source
        if path.startswith(("http://", "https://")):
            for issue in document.issues:
                skipped.append(SkippedFix(issue.rule_id, path, issue.line,
                                          "this is a page on the web, not a file on disk"))
            continue
        if path not in cache:
            try:
                cache[path] = read_text(path)
            except OSError as exc:
                cache[path] = None
                skipped.append(SkippedFix("", path, None, str(exc)))
        text = cache[path]
        if text is None:
            continue

        for issue in document.issues:
            plan, reason = _plan_one(issue, path, text)
            if plan is None:
                skipped.append(SkippedFix(issue.rule_id, path, issue.line, reason))
            else:
                plans.append(plan)

    plans, skipped = _drop_overlaps(plans, skipped)
    ready = [p for p in plans if not p.needs_input]
    pending = [p for p in plans if p.needs_input]
    return ready, pending, skipped


def _plan_one(issue, path: str, text: str):
    if not issue.fix_snippet:
        return None, "this rule has no ready correction; it needs a decision"
    if issue.engine != "static":
        return None, f"{issue.engine} findings describe the rendered page, not the file"
    if not issue.snippet:
        return None, "the finding does not name an element"

    # `<!DOCTYPE html>` belongs before everything, and is the one correction
    # that is about the file rather than about an element in it.
    if issue.fix_snippet.lstrip().lower().startswith("<!doctype"):
        if re.match(r"\s*<!doctype", text, re.IGNORECASE):
            return None, "the file already starts with a doctype"
        return FixPlan(path=path, start=0, end=0, original="",
                       replacement=issue.fix_snippet + "\n",
                       rule_id=issue.rule_id, line=1, kind="insert"), ""

    wanted = _tag_of(issue.snippet)
    if not wanted:
        return None, "the finding's element could not be read"
    name, attributes = wanted

    located = _locate(text, name, attributes, issue.line)
    if located is None:
        return None, ("the element could not be found in the file; it may have "
                      "changed since the audit ran")
    start, open_end = located

    fixed = _tag_of(issue.fix_snippet)
    # An addition, not a replacement: "this page has no charset" is anchored
    # to `<head>` and asks for a `<meta>`. Recognised by the anchor being a
    # container rather than by the names merely differing - `<h3>` corrected
    # to `<h2>` also names a different element, and that one is a swap.
    if fixed and fixed[0] != name and name in CONTAINER_ELEMENTS:
        indent = _indent_at(text, start)
        return FixPlan(path=path, start=open_end, end=open_end, original="",
                       replacement=f"\n{indent}  {issue.fix_snippet}",
                       rule_id=issue.rule_id, line=issue.line, kind="insert",
                       needs_input=_needs_input(issue.rule_id, issue.fix_snippet)), ""

    # A correction that carries content (`<h2>Title</h2>`) replaces the whole
    # element; one that is only an opening tag replaces only the opening tag.
    if _has_content(issue.fix_snippet) and name not in VOID_ELEMENTS:
        end = _element_end(text, name, open_end)
        if end is None:
            return None, "the element's closing tag could not be found"
    else:
        end = open_end

    original = text[start:end]
    if original == issue.fix_snippet:
        return None, "the file already contains the correction"
    return FixPlan(path=path, start=start, end=end, original=original,
                   replacement=issue.fix_snippet, rule_id=issue.rule_id,
                   line=issue.line,
                   needs_input=_needs_input(issue.rule_id, issue.fix_snippet, original)), ""


def _needs_input(rule_id: str, markup: str, original: str = "") -> str:
    """Empty when the correction can be written unattended; the reason if not."""
    if rule_id in DECISION_RULES:
        return DECISION_RULES[rule_id]
    if _is_placeholder(markup, original):
        return "the correction still has a placeholder where real text belongs"
    return ""


def _is_placeholder(markup: str, original: str = "") -> bool:
    """Does the correction *introduce* a placeholder?

    Compared against what was there before, because a page may legitimately
    already link to `example.com`, and re-writing its own address back into
    the tag is not a hole in the correction.
    """
    return any(mark in (markup or "") and mark not in (original or "")
               for mark in PLACEHOLDERS)


def _drop_overlaps(plans: list, skipped: list) -> tuple:
    """Two corrections to the same bytes cannot both be right.

    Happens when two rules fault the same tag - a link that is both
    `target="_blank"` without `rel` and pointing at `http://`. The first is
    kept and the second is reported, because applying both would write one on
    top of the other and produce a tag neither rule asked for.
    """
    ordered = sorted(plans, key=lambda p: (p.path, p.start, p.end))
    kept: list = []
    for plan in ordered:
        clash = next((k for k in kept
                      if k.path == plan.path
                      and not (plan.end <= k.start or plan.start >= k.end)
                      and not (plan.kind == "insert" and k.kind == "insert"
                               and plan.start != k.start)), None)
        if clash is not None and not (plan.start == plan.end == clash.start == clash.end):
            skipped.append(SkippedFix(
                plan.rule_id, plan.path, plan.line,
                f"overlaps the correction for {clash.rule_id}; fix that one "
                f"first and audit again"))
            continue
        kept.append(plan)
    return kept, skipped


# ------------------------------------------------------------------ applying

def apply_fixes(plans: list, backup: bool = True, write=None) -> FixResult:
    """Write the planned edits. One pass per file, back to front.

    Back to front so that every offset stays valid: an edit near the top
    would otherwise move everything below it.
    """
    result = FixResult()
    write = write or _write
    by_file: dict = {}
    for plan in plans:
        # A last line of defence rather than a check the caller can forget:
        # nothing with a placeholder in it reaches a file through here.
        if plan.needs_input:
            result.skipped.append(SkippedFix(
                plan.rule_id, plan.path, plan.line, plan.needs_input))
            continue
        by_file.setdefault(plan.path, []).append(plan)

    for path, file_plans in by_file.items():
        try:
            text = _read(path)
        except OSError as exc:
            result.errors.append(f"{path}: {exc}")
            continue

        if backup:
            backup_path = path + ".bak"
            try:
                # Only the first backup is kept: a second run must not
                # overwrite the copy of the file as the user last had it.
                if not os.path.exists(backup_path):
                    write(backup_path, text)
                    result.backups.append(backup_path)
            except OSError as exc:
                result.errors.append(
                    f"{path}: could not write a backup ({exc}), leaving the file alone")
                continue

        updated = text
        stale = []
        # Back to front so earlier offsets stay valid. Where an insertion and
        # a replacement start at the same byte - a missing doctype and a
        # `<html>` without a language both begin at offset 0 - the replacement
        # goes first, or the insertion moves the text the replacement is
        # still expecting to find.
        ordered = sorted(file_plans,
                         key=lambda p: (-p.start, 0 if p.kind == "replace" else 1))
        for plan in ordered:
            if plan.kind == "replace" and updated[plan.start:plan.end] != plan.original:
                stale.append(plan)
                continue
            updated = updated[:plan.start] + plan.replacement + updated[plan.end:]
            result.applied.append(plan)

        for plan in stale:
            result.skipped.append(SkippedFix(
                plan.rule_id, path, plan.line,
                "the file changed after the audit ran; audit again"))

        if updated != text:
            try:
                write(path, updated)
                result.files_changed.append(path)
            except OSError as exc:
                result.errors.append(f"{path}: {exc}")
    return result


def restore(paths, remove_backup: bool = True) -> tuple:
    """Put files back the way they were before the first correction.

    Returns `(restored, problems)`. Deliberately not a stack of undo steps:
    the promise is "back to how it was", which one copy per file can keep and
    a stack of partial states cannot.
    """
    restored, problems = [], []
    for path in paths:
        backup_path = path + ".bak"
        if not os.path.exists(backup_path):
            problems.append(f"{path}: no backup was kept, nothing to go back to")
            continue
        try:
            _write(path, _read(backup_path))
            restored.append(path)
            if remove_backup:
                os.unlink(backup_path)
        except OSError as exc:
            problems.append(f"{path}: {exc}")
    return restored, problems


def backups_for(documents) -> list:
    """Which of these documents have a backup waiting to be restored."""
    seen, out = set(), []
    for document in documents:
        path = document.source
        if path in seen or path.startswith(("http://", "https://")):
            continue
        seen.add(path)
        if os.path.exists(path + ".bak"):
            out.append(path)
    return out


# ------------------------------------------------------------------- parsing

def _tag_of(markup: str):
    """`('img', {'src': 'a.png'})` from an opening tag."""
    match = _TAG_NAME.search(markup or "")
    if not match:
        return None
    name = match.group(1).lower()
    body = markup[match.end():]
    close = body.find(">")
    if close != -1:
        body = body[:close]
    attributes = {}
    for attribute, value in _ATTRIBUTE.findall(body):
        attributes[attribute.lower()] = (value or "").strip("\"'")
    return name, attributes


def _has_content(markup: str) -> bool:
    """Is this a whole element rather than just an opening tag?"""
    name = _TAG_NAME.search(markup or "")
    if not name:
        return False
    return f"</{name.group(1).lower()}" in (markup or "").lower()


def _locate(text: str, name: str, attributes: dict, line: int | None):
    """Find one element in the source, and be sure it is the right one.

    The line narrows the search; the attributes confirm it. Both are needed:
    a line can hold several tags of the same name, and attributes alone would
    match an identical tag elsewhere in the file.
    """
    starts = _line_starts(text)
    windows = []
    if line and 1 <= line <= len(starts):
        # The tag starts on its recorded line, but its attributes may run onto
        # the next ones, so the window reaches forward a little.
        begin = starts[line - 1]
        end = starts[min(line + 4, len(starts)) - 1] if line + 4 <= len(starts) else len(text)
        windows.append((begin, end))
    windows.append((0, len(text)))

    pattern = re.compile(r"<\s*" + re.escape(name) + r"(?=[\s/>])", re.IGNORECASE)
    for begin, end in windows:
        best = None
        for match in pattern.finditer(text, begin, end):
            open_end = _open_tag_end(text, match.start())
            if open_end is None:
                continue
            found = _tag_of(text[match.start():open_end])
            if not found:
                continue
            if _matches(found[1], attributes):
                if best is not None:
                    break  # ambiguous inside this window; fall through
                best = (match.start(), open_end)
        if best is not None:
            return best
    return None


def _matches(found: dict, wanted: dict) -> bool:
    """Every attribute the finding recorded is present with the same value.

    Not equality: the parser drops nothing but may normalise, and a tag with
    an extra attribute the finding did not mention is still the same tag.
    """
    for key, value in wanted.items():
        if key not in found:
            return False
        if value and found[key] != value:
            return False
    return True


def _open_tag_end(text: str, start: int):
    """Offset just past the `>` that closes this opening tag, quotes aside."""
    quote = ""
    index = start
    while index < len(text):
        char = text[index]
        if quote:
            if char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
        elif char == ">":
            return index + 1
        index += 1
    return None


def _element_end(text: str, name: str, open_end: int):
    """Offset just past this element's own closing tag, counting nesting."""
    depth = 1
    pattern = re.compile(r"<\s*(/?)\s*" + re.escape(name) + r"(?=[\s/>])",
                         re.IGNORECASE)
    index = open_end
    while index < len(text):
        match = pattern.search(text, index)
        if not match:
            return None
        end = _open_tag_end(text, match.start())
        if end is None:
            return None
        depth += -1 if match.group(1) else 1
        if depth == 0:
            return end
        index = end
    return None


def _indent_at(text: str, offset: int) -> str:
    line_start = text.rfind("\n", 0, offset) + 1
    line = text[line_start:offset]
    return line[:len(line) - len(line.lstrip())]


def _line_starts(text: str) -> list:
    starts = [0]
    for index, char in enumerate(text):
        if char == "\n":
            starts.append(index + 1)
    return starts


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return handle.read()


def _write(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
