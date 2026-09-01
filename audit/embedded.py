"""Markup that lives inside a template literal in a `.ts` or `.js` file.

`.ts`, `.js` and `.mjs` are skipped by the repo audit, and the reason is
sound: JSX is not valid in them, so their `<` is an operator, and
`if (a < b)` handed to an HTML parser is an open tag with everything after
it inside it.

But that is a statement about *code*, and a backtick string is not code. A
classic SPFx web part - the kind that does not use React - builds its whole
interface this way:

    private renderHtml(url) {
      let html = `
        <div class="ms-Grid ${styles.wrapper}">
          <h2 class="orangetext">${this.pageTitle}</h1>
        </div>`;
    }

Measured 2026-09-01 on two real SharePoint solutions: **72 of 168** `.ts`
files in one of them build markup like this, and none of it was ever read.
The example above is from that repository, and its `<h2>` closes with
`</h1>`.

So the file is not audited, and the *markup inside its template literals* is
- as fragments, with their line numbers, and with `${...}` replaced by a
placeholder so a parser sees an attribute value rather than a syntax error.
"""
from __future__ import annotations

import re

#: A literal has to contain a real tag before it is worth parsing. Not any
#: `<`: a template string full of `a < b` is arithmetic, and reading it as
#: markup is exactly the mistake this module exists to avoid making.
_HAS_MARKUP = re.compile(
    r"<(?:div|span|section|article|main|nav|header|footer|aside|form|input|"
    r"button|a|img|table|thead|tbody|tr|td|th|ul|ol|li|h[1-6]|p|label|select|"
    r"textarea|iframe|video|audio|svg|picture)\b", re.I)

#: `${...}`, including nested braces one level deep, which is as far as a
#: template expression realistically goes in markup.
_INTERPOLATION = re.compile(r"\$\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}")

#: What an interpolation becomes. A word rather than an empty string: an
#: attribute that reads `class=""` is a claim the file does not make, while
#: `class="expr"` says "something is computed here", which is true and keeps
#: the element valid for every rule that only asks whether an attribute is
#: present. Deliberately not a value any rule matches on.
PLACEHOLDER = "expr"

#: How many literals one file is read for, and how long each may be. A
#: minified bundle that slipped past the exclusions is the case this bounds.
MAX_LITERALS = 40
MAX_LENGTH = 200_000


def _literals(text: str):
    """`(markup, start_offset)` for every backtick string in `text`.

    Walked rather than matched with a regex: a template literal can contain
    an escaped backtick, and a `//` inside one is content, not a comment.
    Nesting inside `${...}` is not followed - a template literal built out
    of another one is not markup this can attribute to a line.
    """
    found = []
    index = 0
    length = len(text or "")
    while index < length:
        char = text[index]
        if char in "'\"":
            quote = char
            index += 1
            while index < length:
                if text[index] == "\\":
                    index += 2
                    continue
                if text[index] == quote:
                    break
                index += 1
            index += 1
            continue
        if char == "/" and index + 1 < length and text[index + 1] == "/":
            while index < length and text[index] not in "\r\n":
                index += 1
            continue
        if char == "/" and index + 1 < length and text[index + 1] == "*":
            end = text.find("*/", index + 2)
            index = length if end == -1 else end + 2
            continue
        if char == "`":
            start = index + 1
            index = start
            while index < length:
                if text[index] == "\\":
                    index += 2
                    continue
                if text[index] == "`":
                    break
                index += 1
            found.append((text[start:index], start))
            index += 1
            continue
        index += 1
    return found


def markup_fragments(text: str, max_literals: int = MAX_LITERALS) -> list:
    """`[(markup, first_line)]` for the template literals that hold markup.

    `first_line` is 1-based and counts lines of the original file, so a
    finding can say where in the `.ts` the element is.
    """
    if not text or len(text) > MAX_LENGTH or "`" not in text:
        return []
    out = []
    for literal, offset in _literals(text):
        if not _HAS_MARKUP.search(literal):
            continue
        out.append((_INTERPOLATION.sub(PLACEHOLDER, literal),
                    text.count("\n", 0, offset) + 1))
        if len(out) >= max_literals:
            break
    return out
