"""Which branches of a React component a piece of JSX sits in.

A component writes the same element in several places when only one of them
renders: the two arms of `cond ? <A/> : <B/>`, `{busy && …}` against
`{!busy && …}`, an early `return` for the loading state and the main one.
The HTML parser that every rule reads sees all of them at once, so a
`<h1 id="auth-title">` written in the sign-in and the sign-up arm of one
page looked like a page with two of them - 17 of the 25 problems a run on
`apps/coach/src` reported, and none of them real.

This is not a JavaScript parser and does not try to be one. It tracks just
enough - strings, comments, template literals, brackets, and whether it is in
JS or in JSX - to find three constructs and the span each arm covers:

* a conditional `a ? x : y` - arms 0 and 1, keyed by where the `?` is;
* `{cond && x}` inside a JSX expression container - keyed by `cond` with any
  leading `!` taken off, the arm being whether it was negated;
* a `return` - keyed per file, the arm being the statement itself. Two
  returns are two different render results; nothing in one file proves two
  components that each write an id render on the same page.

`exclusive(a, b)` is then: is there a construct both offsets are inside, on
different arms? A scanner that loses track (unbalanced input) stops adding
constructs, which can only make the answer "not exclusive" - the direction
that keeps a real duplicate reported.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_IDENT = re.compile(r"[\w$]")
#: Words after which `<` opens JSX rather than comparing.
_JSX_AFTER_WORDS = {"return", "yield", "await", "case", "default", "else", "in", "of"}
_JSX_AFTER_CHARS = set("(,=:?&|{[!;}>") | {""}


@dataclass
class Construct:
    kind: str          # "ternary", "and", "return"
    key: str
    arm: object
    start: int
    end: int = -1


@dataclass
class _Frame:
    """One JS expression context: the file's top level or a `{…}` in JSX."""
    container_start: int
    brackets: list = field(default_factory=list)   # open bracket chars
    ternaries: list = field(default_factory=list)  # (depth, construct, phase)
    returns: list = field(default_factory=list)    # (depth, construct)
    and_open: Construct | None = None


def scan(source: str, texts: list | None = None, tags: set | None = None,
         closed: set | None = None) -> list:
    """The constructs of `source`; JSX text runs go into `texts` if given."""
    constructs: list = []
    n = len(source)
    i = 0
    # mode stack: ("js", frame) | ("tag",) | ("children",)
    modes: list = [("js", _Frame(container_start=0))]
    tag_starts: list = []  # where each open "tag" mode began

    def prev_token(index: int) -> str:
        j = index - 1
        while j >= 0 and source[j].isspace():
            j -= 1
        if j < 0:
            return ""
        if _IDENT.match(source[j]):
            k = j
            while k >= 0 and _IDENT.match(source[k]):
                k -= 1
            return source[k + 1:j + 1]
        return source[j]

    def close_ternaries(frame: _Frame, depth: int, at: int) -> None:
        while frame.ternaries and frame.ternaries[-1][0] >= depth:
            _depth, construct, _phase = frame.ternaries.pop()
            construct.end = at

    def close_returns(frame: _Frame, depth: int, at: int) -> None:
        while frame.returns and frame.returns[-1][0] >= depth:
            _depth, construct = frame.returns.pop()
            construct.end = at

    try:
        while i < n:
            mode = modes[-1]
            ch = source[i]
            if mode[0] == "js":
                frame = mode[1]
                if ch in "\"'":
                    end = source.find(ch, i + 1)
                    while end != -1 and source[end - 1] == "\\" and source[end - 2] != "\\":
                        end = source.find(ch, end + 1)
                    i = n if end == -1 else end + 1
                    continue
                if ch == "`":
                    # Template literal; `${` inside is code but rarely JSX.
                    j = i + 1
                    depth = 0
                    while j < n:
                        c = source[j]
                        if c == "\\":
                            j += 2
                            continue
                        if c == "`" and depth == 0:
                            break
                        if source.startswith("${", j):
                            depth += 1
                            j += 2
                            continue
                        if c == "}" and depth:
                            depth -= 1
                        j += 1
                    i = j + 1
                    continue
                if source.startswith("//", i):
                    end = source.find("\n", i)
                    i = n if end == -1 else end + 1
                    continue
                if source.startswith("/*", i):
                    end = source.find("*/", i + 2)
                    i = n if end == -1 else end + 2
                    continue
                if ch == "<" and i + 1 < n and (source[i + 1].isalpha() or source[i + 1] == ">"):
                    before = prev_token(i)
                    if before in _JSX_AFTER_CHARS or before in _JSX_AFTER_WORDS:
                        if tags is not None:
                            tags.add(i)
                        tag_starts.append(i)
                        modes.append(("tag",))
                        i += 1
                        continue
                if ch in "([{":
                    frame.brackets.append(ch)
                    i += 1
                    continue
                if ch in ")]}":
                    depth = len(frame.brackets)
                    if not frame.brackets:
                        if ch == "}" and len(modes) > 1:
                            # The end of a JSX expression container.
                            close_ternaries(frame, 0, i)
                            close_returns(frame, 0, i)
                            if frame.and_open is not None:
                                frame.and_open.end = i
                            modes.pop()
                            i += 1
                            continue
                        return constructs  # unbalanced: stop adding
                    close_ternaries(frame, depth, i)
                    close_returns(frame, depth, i)
                    frame.brackets.pop()
                    i += 1
                    continue
                if ch == "?":
                    if source.startswith("??", i) or source.startswith("?.", i):
                        i += 2
                        continue
                    construct = Construct("ternary", str(i), 0, i)
                    constructs.append(construct)
                    frame.ternaries.append((len(frame.brackets), construct, 0))
                    i += 1
                    continue
                if ch == ":" and frame.ternaries:
                    depth, construct, phase = frame.ternaries[-1]
                    if depth == len(frame.brackets) and phase == 0:
                        construct.end = i
                        alternate = Construct("ternary", construct.key, 1, i)
                        constructs.append(alternate)
                        frame.ternaries[-1] = (depth, alternate, 1)
                    i += 1
                    continue
                if ch in ",;":
                    close_ternaries(frame, len(frame.brackets), i)
                    if ch == ";":
                        close_returns(frame, len(frame.brackets), i)
                    i += 1
                    continue
                if (source.startswith("&&", i) and len(modes) > 1
                        and not frame.brackets and frame.and_open is None):
                    cond = re.sub(r"\s+", "", source[frame.container_start:i])
                    negated = cond.startswith("!")
                    key = cond.lstrip("!")
                    if key.startswith("(") and key.endswith(")"):
                        key = key[1:-1]
                    construct = Construct("and", key, not negated, i)
                    constructs.append(construct)
                    frame.and_open = construct
                    i += 2
                    continue
                if source.startswith("return", i) and (i == 0 or not _IDENT.match(source[i - 1])) \
                        and (i + 6 >= n or not _IDENT.match(source[i + 6])):
                    construct = Construct("return", "return", i, i)
                    constructs.append(construct)
                    frame.returns.append((len(frame.brackets), construct))
                    i += 6
                    continue
                i += 1
                continue

            if mode[0] == "tag":
                if ch in "\"'":
                    end = source.find(ch, i + 1)
                    i = n if end == -1 else end + 1
                    continue
                if ch == "{":
                    modes.append(("js", _Frame(container_start=i + 1)))
                    i += 1
                    continue
                if source.startswith("/>", i):
                    modes.pop()
                    start = tag_starts.pop() if tag_starts else -1
                    if closed is not None and start >= 0:
                        closed.add(start)
                    i += 2
                    continue
                if ch == ">":
                    if tag_starts:
                        tag_starts.pop()
                    modes[-1] = ("children",)
                    i += 1
                    continue
                i += 1
                continue

            # children
            if texts is not None and ch not in "{<":
                end = i
                while end < n and source[end] not in "{<":
                    end += 1
                texts.append((i, end))
                i = end
                continue
            if ch == "{":
                modes.append(("js", _Frame(container_start=i + 1)))
                i += 1
                continue
            if source.startswith("</", i):
                end = source.find(">", i)
                i = n if end == -1 else end + 1
                modes.pop()  # the element whose children these were
                continue
            if ch == "<":
                if tags is not None:
                    tags.add(i)
                tag_starts.append(i)
                modes.append(("tag",))
                i += 1
                continue
            i += 1
    finally:
        for construct in constructs:
            if construct.end == -1:
                construct.end = n
    return constructs


def visible_text(source: str) -> str:
    """The JSX text of a file - what is written between tags, outside `{…}`.

    Everything else in a `.tsx` file is code: `CSS.escape`, `new URL`,
    `JSON.parse`, `const FAQ = …`. An HTML parser reads it all as text.
    """
    runs: list = []
    scan(source, texts=runs)
    return " ".join(source[start:end] for start, end in runs)


class Branches:
    """The constructs of one file, asked about many offsets."""

    def __init__(self, source: str):
        #: Offsets of every `<` that opens a JSX element. A `<string>` the
        #: parser made out of `useState<string>()` is not among them.
        self.tags: set = set()
        #: Those written self-closing (`<div … />`), which an HTML parser
        #: keeps open and makes the parent of whatever follows.
        self.self_closing: set = set()
        self.constructs = scan(source, tags=self.tags, closed=self.self_closing)

    def path(self, offset: int) -> list:
        return [c for c in self.constructs if c.start <= offset < c.end]

    def exclusive(self, first: int, second: int) -> bool:
        one, two = self.path(first), self.path(second)
        for a in one:
            for b in two:
                if a.kind != b.kind or a.key != b.key or a.arm == b.arm:
                    continue
                if a.kind == "return":
                    # Two statements, and neither inside the other: a
                    # `return` in a `.map` callback is part of the outer one.
                    if a.end <= b.start or b.end <= a.start:
                        return True
                    continue
                return True
        return False
