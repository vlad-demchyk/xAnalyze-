"""Local-folder scanner: walks a repository, extracts the human-facing text
that sits inside markup tags in source files (HTML/XML/JSX/TSX/Vue/Svelte —
Android `strings.xml`, iOS-style templates, web components, etc.), and keeps
exact file offsets so a flagged passage can be written straight back into
the file it came from.

What counts as "content inside tags":
    <h1>Welcome back</h1>              -> "Welcome back"
    <string name="ok">OK</string>      -> "OK"
    <p>Hello, {userName}!</p>          -> "Hello," and "!" as separate runs
                                           (the {expression} in between is
                                           code, not content, and is skipped)

Known limitation: this is a regex-based extractor, not a real HTML/JSX
parser. It's deliberately simple so it works uniformly across every
tag-based file type without a different parser per language. It will miss
text built up through string concatenation or template literals outside of
tags, and can occasionally mis-split unusual nesting. Treat it the same way
as the detectors themselves: a starting point for a human to review, not a
guaranteed-complete extraction.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from lang_detect import guess_language
from models import KIND_INJECTED, KIND_MARKUP, KIND_TECHNICAL, CodeBlock, FileResult

# ---------------------------------------------------------------- scopes
#
# Two different questions get asked of a repository, and mixing them makes
# both answers worse:
#
#   SCOPE_CONTENT   — text the user will read. Markup between tags, plus the
#                     copy that never sits between tags at all: a
#                     placeholder="" attribute, a `.textContent =`
#                     assignment, a t("...") translation call. Comments are
#                     excluded, because a comment is not content and
#                     flagging one as "AI-written website copy" is noise.
#   SCOPE_TECHNICAL — comments and docstrings, examined on purpose. This is
#                     where an assistant's writing actually accumulates in a
#                     codebase, and it is worth being able to look at — but
#                     it must be a deliberate choice, since none of it ships
#                     to a reader and none of it should ever be auto-fixed
#                     as if it were copy.
#
# They are separate scopes rather than one big scan for a practical reason
# as well: `fix` and "auto-replace in files" write to disk, and rewriting a
# comment is a different decision from rewriting a heading.
SCOPE_CONTENT = "content"
SCOPE_TECHNICAL = "technical"
SCOPE_BOTH = "both"

# Extensions worth scanning for tag-embedded content, plus the script files
# where injected copy lives.
DEFAULT_EXTENSIONS = (
    ".html", ".htm", ".xml", ".jsx", ".tsx", ".vue", ".svelte",
    ".js", ".ts", ".mjs", ".cjs",
)

# Where a localised product keeps its copy. The files are ordinary JSON or
# YAML and would be meaningless to scan wholesale — `package.json` and
# `tsconfig.json` are not copy — so they are recognised by location and name
# instead of by extension alone. This is the shortest useful version of the
# extraction map: a project that keeps its strings anywhere near convention
# is read, and nothing else is.
LOCALE_SUFFIXES = (".json", ".yml", ".yaml")
_LOCALE_DIRS = frozenset((
    "locales", "locale", "lang", "langs", "i18n", "translations",
    "translation", "messages", "strings",
))
# `en.json`, `uk-UA.json`, `pt_BR.yml`: a bare language tag as the file name.
_LOCALE_NAME_RE = re.compile(r"^[a-z]{2,3}(?:[-_][A-Za-z]{2,4})?$")


def is_locale_file(path) -> bool:
    """Is this a file of user-facing strings rather than configuration?"""
    p = Path(path)
    if p.suffix.lower() not in LOCALE_SUFFIXES:
        return False
    if any(part.lower() in _LOCALE_DIRS for part in p.parts[:-1]):
        return True
    return bool(_LOCALE_NAME_RE.match(p.stem))


# Comments are worth reading in far more file types than copy is.
TECHNICAL_EXTENSIONS = DEFAULT_EXTENSIONS + (
    ".py", ".css", ".scss", ".less", ".go", ".rs", ".java", ".kt", ".php",
    ".rb", ".sh", ".sql", ".c", ".h", ".cpp", ".cs", ".swift", ".yml",
    ".yaml", ".toml",
)

MIN_BLOCK_LEN = 8

# A comment has to be a sentence, not a directive, to be worth judging.
# Longer than a line of copy because `// TODO: fix` and `# noqa` are the
# overwhelming majority of short comments and none of them are prose.
MIN_COMMENT_LEN = 40

# Sensible default excludes, gitignore-style. Editable in the UI before a
# scan; this is just the starting point.
DEFAULT_IGNORE_PATTERNS = """\
.git/
node_modules/
dist/
build/
out/
.next/
.nuxt/
.svelte-kit/
target/
vendor/
venv/
.venv/
env/
__pycache__/
.pytest_cache/
.mypy_cache/
.idea/
.vscode/
coverage/
*.min.js
*.min.css
*.map
package-lock.json
yarn.lock
pnpm-lock.yaml
ios/Pods/
android/build/
android/.gradle/
.gradle/
*.egg-info/
"""

_SCRIPT_STYLE_COMMENT_RE = re.compile(
    r"<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>|<!--.*?-->",
    re.IGNORECASE | re.DOTALL,
)
# Comments in code. Masked for the content scope for the same reason script
# bodies are: a comment is not copy, and `// the user sees this` sitting next
# to JSX was being collected as if the user saw the comment too. The technical
# scope reads the original text, so nothing is lost by blanking them here.
_CODE_COMMENT_RE = re.compile(
    r"/\*.*?\*/|(?<![:\w])//[^\n]*",
    re.DOTALL,
)
# Text that a browser will render sits between the `>` that closes an element
# tag and the `<` that opens the next one. Matching a bare `>` instead is what
# made a `.tsx` file read as copy: `useState<boolean>(false)` and `a > b` end
# in the same character, so the code after them was collected as prose.
#
# The tag itself is therefore matched, not just its closing bracket. An
# attribute value may contain `>` (`onClick={a > b ? f : g}`), so quoted
# strings and braced expressions are consumed as units.
_TAG_GAP_RE = re.compile(
    r"""(?<![\w)\]])<(?P<closing>/?)(?P<name>[A-Za-z][\w.:-]*)"""
    # The attribute region. Each alternative starts with a character the others
    # exclude, so at every position exactly one of them can apply. Written that
    # way on purpose: an alternation whose branches can all match the same
    # character has to try every combination before it can fail, and on a file
    # with an unclosed `<` that is exponential - one 4 KB component hung the
    # whole scan.
    r"""(?:[^<>"'{]|"[^"]*"|'[^']*'|\{[^{}]*\})*/?>"""
    r"""(?P<gap>[^<>]{1,2000})(?=<)""",
    re.DOTALL,
)

# Element names a browser actually renders. A lowercase name outside this set
# is a TypeScript generic parameter (`<boolean>`, `<string>`) far more often
# than an element, and treating it as one is the whole bug.
_HTML_TAGS = frozenset("""
a abbr address area article aside audio b base bdi bdo blockquote body br
button canvas caption cite code col colgroup data datalist dd del details dfn
dialog div dl dt em embed fieldset figcaption figure footer form h1 h2 h3 h4
h5 h6 head header hgroup hr html i iframe img input ins kbd label legend li
link main map mark menu meta meter nav noscript object ol optgroup option
output p param picture pre progress q rp rt ruby s samp script section select
slot small source span strong style sub summary sup table tbody td template
textarea tfoot th thead time title tr track u ul var video wbr
""".split())

# Single letters and the conventional generic names. `<T>` is a type
# parameter; a component called `T` is not a thing anyone ships.
_GENERIC_PARAM_RE = re.compile(r"^[A-Z][0-9]?$|^(?:T[A-Z]\w*|K|V|U|R|S|E|P)$")


def _renders_text(name: str) -> bool:
    """Would a browser render the text that follows this tag?"""
    if name.islower() or name[0].isdigit():
        # Custom elements always contain a hyphen, which is what the spec
        # requires of them, so an unknown hyphenless lowercase name is not one.
        return name in _HTML_TAGS or "-" in name
    if _GENERIC_PARAM_RE.match(name):
        return False
    # A capitalised name is a framework component, and its children are copy.
    return name[0].isupper()

_JS_EXPR_RE = re.compile(r"\{[^{}]*\}")
_CODE_LOOKS_LIKE_RE = re.compile(
    r"=>|function\s*\(|\bimport\b|\bexport\b|\breturn\b|;\s*$|^\s*(const|let|var)\b",
    re.IGNORECASE,
)
_ALPHA_RE = re.compile(r"[^\W\d_]", re.UNICODE)  # at least one letter
# A dotted identifier with no spaces: `aiChat.gallery.next`. Only the dotted
# form is treated as a key, because a single word ("Download") is exactly what
# a project using English as its key language writes, and that is real copy.
_KEY_LIKE_RE = re.compile(r"^[A-Za-z_][\w-]*(?:\.[A-Za-z_][\w-]*)+$")


@dataclass
class ScanConfig:
    extensions: tuple[str, ...] | None = None
    ignore_patterns: list[str] = field(default_factory=lambda: _parse_ignore_text(DEFAULT_IGNORE_PATTERNS))
    max_files: int = 500
    max_file_size_bytes: int = 2_000_000
    scope: str = SCOPE_CONTENT

    def effective_extensions(self) -> tuple:
        """Which files to open, given the scope.

        Left as None by default so the scope decides: comments are worth
        reading in Python, Go and CSS, which hold no markup at all and would
        be pointless to open when looking for copy.
        """
        if self.extensions:
            return tuple(self.extensions)
        if self.scope in (SCOPE_TECHNICAL, SCOPE_BOTH):
            return TECHNICAL_EXTENSIONS
        return DEFAULT_EXTENSIONS


def _parse_ignore_text(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]


def _build_matcher(patterns: list[str]):
    """Returns a callable(relative_posix_path, is_dir) -> bool.
    Uses `pathspec` (gitignore-semantics) when available, falls back to a
    small builtin matcher (dir-prefix + fnmatch) otherwise.
    """
    try:
        import pathspec
        spec = pathspec.PathSpec.from_lines("gitwildmatch", patterns)

        def matcher(rel_path: str, is_dir: bool) -> bool:
            check = rel_path + "/" if is_dir else rel_path
            return spec.match_file(check)

        return matcher
    except ImportError:
        import fnmatch

        dir_patterns = [p.rstrip("/") for p in patterns if p.endswith("/")]
        glob_patterns = [p for p in patterns if not p.endswith("/")]

        def matcher(rel_path: str, is_dir: bool) -> bool:
            parts = Path(rel_path).parts
            for dp in dir_patterns:
                if dp in parts:
                    return True
            name = Path(rel_path).name
            for gp in glob_patterns:
                if fnmatch.fnmatch(name, gp) or fnmatch.fnmatch(rel_path, gp):
                    return True
            return False

        return matcher


def _is_probably_content(text: str) -> bool:
    if len(text) < MIN_BLOCK_LEN:
        return False
    if not _ALPHA_RE.search(text):
        return False
    if _CODE_LOOKS_LIKE_RE.search(text):
        return False
    if re.fullmatch(r"[A-Z0-9_]+", text):  # CONSTANT_LIKE_TOKEN
        return False
    if text.startswith(("//", "/*", "#")):
        return False
    return True


def _is_key_like(text: str) -> bool:
    """Is this a translation key rather than the text it stands for?

    `t("aiChat.gallery.next")` names a string; the string itself lives in a
    locale file. Judging the key as prose is how "refine" got reported as a
    cliché three times over — the key was never written for a reader.
    """
    return bool(_KEY_LIKE_RE.match(text))


def _is_markup_run(text: str) -> bool:
    """Rendered text, as opposed to the remains of a JSX expression.

    What is left of `{items.map(...)}` once the balanced parts are cut out
    still carries a brace, and rendered copy almost never does. The check is
    deliberately not in `_is_probably_content`: a locale string may hold
    `{count}` on purpose.
    """
    return "{" not in text and "}" not in text and _is_probably_content(text)


def _extract_literal_runs(span_text: str, span_start: int) -> list[tuple[int, int, str]]:
    """Split a >...< gap on {expression} boundaries and yield the literal
    text runs in between, as (absolute_start, absolute_end, text)."""
    runs: list[tuple[int, int, str]] = []
    cursor = 0
    for m in _JS_EXPR_RE.finditer(span_text):
        _emit_run(runs, span_text, span_start, cursor, m.start())
        cursor = m.end()
    _emit_run(runs, span_text, span_start, cursor, len(span_text))
    return runs


def _emit_run(runs: list, span_text: str, span_start: int, local_start: int, local_end: int) -> None:
    chunk = span_text[local_start:local_end]
    stripped = chunk.strip()
    if not stripped:
        return
    lead = len(chunk) - len(chunk.lstrip())
    trail = len(chunk) - len(chunk.rstrip())
    abs_start = span_start + local_start + lead
    abs_end = span_start + local_end - trail
    runs.append((abs_start, abs_end, stripped))


# --------------------------------------------------------------- injected copy
#
# Copy that reaches the user without ever sitting between two tags. Each
# pattern below captures the string literal in group "text", so one routine
# turns them all into blocks with exact offsets.

# Attributes that are rendered to, or read out to, a person. `value` and
# `name` are deliberately absent: they are far more often identifiers than
# copy, and a scanner that flags every form field name is one people turn off.
_VISIBLE_ATTRIBUTES = (
    "placeholder", "alt", "title", "aria-label", "aria-placeholder",
    "aria-description", "aria-roledescription", "label", "tooltip",
    "helperText", "helper-text", "errorText", "error-text", "subtitle",
    "caption", "summary",
)

# Object keys whose values are copy in config-driven and localised UIs.
_CONTENT_KEYS = (
    "title", "subtitle", "heading", "subheading", "description", "label",
    "placeholder", "message", "text", "body", "caption", "tooltip", "hint",
    "error", "errorMessage", "successMessage", "confirmText", "cancelText",
    "cta", "ctaLabel", "buttonText", "emptyState", "helpText",
)

# Translation helpers. Matching the call rather than the file means an inline
# t("...") and a locale module are both found, without hardcoding a project's
# folder layout.
_I18N_CALLS = (
    r"\$?t", r"i18n\.t", r"intl\.formatMessage", r"translate", r"gettext",
    r"__", r"\$tc", r"trans",
)


def _string_pattern(prefix: str) -> re.Pattern:
    """Compile `prefix` followed by a quoted string, captured as `text`.

    The quote character is captured and back-referenced, so an apostrophe
    inside a double-quoted string ("don't") doesn't end the match early —
    and natural copy is full of apostrophes.
    """
    return re.compile(
        prefix + r"""\s*(?P<quote>["'`])(?P<text>(?:\\.|(?!(?P=quote))[^\\])*)(?P=quote)""",
        re.IGNORECASE | re.DOTALL,
    )


_INJECTION_PATTERNS = (
    # placeholder="Search the docs"   /   alt='Team photo'
    _string_pattern(r"\b(?:" + "|".join(_VISIBLE_ATTRIBUTES) + r")\s*="),
    # element.textContent = "All set"
    _string_pattern(r"\.(?:textContent|innerText|innerHTML|placeholder|title|alt)\s*="),
    # t("Welcome back")  /  i18n.t('Welcome back')
    _string_pattern(r"\b(?:" + "|".join(_I18N_CALLS) + r")\s*\("),
    # title: "Welcome back"   (object literals, locale files, config)
    _string_pattern(r"\b(?:" + "|".join(_CONTENT_KEYS) + r")\s*:"),
)


def _extract_injected_blocks(raw_text: str, masked: str, file_path: str) -> list[CodeBlock]:
    """String literals that become visible copy.

    Runs over `masked` — the text with comment, script and style bodies
    blanked to equal-length spaces — so a commented-out `placeholder="..."`
    is not reported as live copy, while every offset still lines up with the
    original file.
    """
    blocks: list[CodeBlock] = []
    seen: set = set()
    for pattern in _INJECTION_PATTERNS:
        for match in pattern.finditer(masked):
            start, end = match.span("text")
            text = match.group("text")
            stripped = text.strip()
            if not stripped or not _is_probably_content(stripped):
                continue
            if _is_key_like(stripped):
                continue
            # Trim the offsets to the stripped text, so a replacement written
            # back to the file never swallows the surrounding whitespace.
            start += len(text) - len(text.lstrip())
            end -= len(text) - len(text.rstrip())
            if (start, end) in seen or raw_text[start:end] != stripped:
                continue
            seen.add((start, end))
            blocks.append(
                _make_code_block(raw_text, file_path, start, end, stripped, KIND_INJECTED)
            )
    return blocks


# ------------------------------------------------------------ technical text
#
# Comments and docstrings, read only when asked for. Every pattern captures
# the prose in group "text", so a block covers the words and not the `//` or
# `/**` around them — a replacement then rewrites the sentence and leaves the
# comment syntax intact.
_COMMENT_PATTERNS = (
    # /* block */ and /** jsdoc */; the leading " * " decoration is stripped below
    re.compile(r"/\*+(?P<text>.*?)\*/", re.DOTALL),
    re.compile(r"<!--(?P<text>.*?)-->", re.DOTALL),
    re.compile(r'"""(?P<text>.*?)"""', re.DOTALL),
    re.compile(r"'''(?P<text>.*?)'''", re.DOTALL),
    # // line comment — not after ':' or a word char, so a URL's // is safe
    re.compile(r"(?<![:\w])//(?P<text>[^\n]*)"),
    # '#' comment, only at the start of a line: mid-line it is a URL
    # fragment, a CSS colour or a shell variable far more often than a comment
    re.compile(r"^[ \t]*#(?!!)(?P<text>[^\n]*)", re.MULTILINE),
)

_COMMENT_DECORATION_RE = re.compile(r"^[ \t]*[*#/]+[ \t]?", re.MULTILINE)
# Machine-readable comment bodies: directives, annotations, licence headers,
# task markers. None of these are prose and all of them are everywhere.
_COMMENT_NOISE_RE = re.compile(
    r"^\s*(?:@\w+|eslint|prettier|ts-|noqa|type:|pragma|pylint|flake8|"
    r"SPDX-|Copyright|TODO\b|FIXME\b|HACK\b|XXX\b|https?://)",
    re.IGNORECASE,
)


def _extract_technical_blocks(raw_text: str, file_path: str) -> list[CodeBlock]:
    blocks: list[CodeBlock] = []
    seen: set = set()
    for pattern in _COMMENT_PATTERNS:
        for match in pattern.finditer(raw_text):
            start, end = match.span("text")
            body = match.group("text")
            # The cleaned copy is only used to decide whether this is prose
            # worth judging; the offsets stay anchored to the raw match.
            cleaned = _COMMENT_DECORATION_RE.sub("", body).strip()
            if len(cleaned) < MIN_COMMENT_LEN:
                continue
            if _COMMENT_NOISE_RE.match(cleaned):
                continue
            if not _ALPHA_RE.search(cleaned):
                continue
            lead = len(body) - len(body.lstrip())
            trail = len(body) - len(body.rstrip())
            start, end = start + lead, end - trail
            if start >= end or (start, end) in seen:
                continue
            seen.add((start, end))
            # The block text is exactly what the file holds at those offsets:
            # file_writer re-checks that before writing, so storing a
            # prettified version here would make every write a no-op.
            blocks.append(
                _make_code_block(raw_text, file_path, start, end,
                                 raw_text[start:end], KIND_TECHNICAL)
            )
    return blocks


def _make_code_block(raw_text: str, file_path: str, start: int, end: int,
                     text: str, kind: str) -> CodeBlock:
    return CodeBlock(
        block_id=str(uuid.uuid4()),
        file_path=file_path,
        start=start,
        end=end,
        text=text,
        line_number=raw_text.count("\n", 0, start) + 1,
        # Tagged here so a rewrite request can tell the model which language
        # to answer in — without it, Ukrainian copy comes back in English.
        language_hint=guess_language(text),
        kind=kind,
    )


# `"key": "value"` at any depth. A regex rather than a JSON parse because the
# offsets have to point into the original file: a fix writes back to them, and
# `json.loads` throws the positions away.
_LOCALE_PAIR_RE = re.compile(
    r'"(?:\\.|[^"\\])*"\s*:\s*"(?P<text>(?:\\.|[^"\\])*)"'
)
# YAML: `key: value`, quoted or bare, one per line.
_LOCALE_YAML_RE = re.compile(
    r'^[ \t]*[\w.-]+:[ \t]+(?P<text>(?:"[^"\n]*"|\'[^\'\n]*\'|[^\n#]+?))[ \t]*$',
    re.MULTILINE,
)


def _extract_locale_blocks(raw_text: str, file_path: str) -> list[CodeBlock]:
    """Every string a locale file hands to the interface.

    This is copy in the strictest sense: it exists only to be read by a
    person, and in a localised product it is *all* of the copy — the
    components hold keys, not sentences.
    """
    pattern = (_LOCALE_YAML_RE if Path(file_path).suffix.lower() in (".yml", ".yaml")
               else _LOCALE_PAIR_RE)
    blocks: list[CodeBlock] = []
    seen: set = set()
    for match in pattern.finditer(raw_text):
        start, end = match.span("text")
        text = match.group("text")
        if text[:1] in ("\"", "'") and text[-1:] == text[:1] and len(text) > 1:
            start, end, text = start + 1, end - 1, text[1:-1]
        stripped = text.strip()
        if not stripped or (start, end) in seen:
            continue
        # The length floor that protects the code paths does not apply here:
        # "Save" and "Функції" are eight characters of nothing to a heuristic
        # and a whole button to a reader, and in a locale file every value is
        # copy by construction.
        if not _ALPHA_RE.search(stripped) or _is_key_like(stripped):
            continue
        if _CODE_LOOKS_LIKE_RE.search(stripped):
            continue
        start += len(text) - len(text.lstrip())
        end -= len(text) - len(text.rstrip())
        if raw_text[start:end] != stripped:
            continue
        seen.add((start, end))
        blocks.append(
            _make_code_block(raw_text, file_path, start, end, stripped, KIND_INJECTED)
        )
    return blocks


def _extract_blocks(raw_text: str, file_path: str,
                    scope: str = SCOPE_CONTENT) -> list[CodeBlock]:
    """Extract the text this scope asks for, with exact file offsets.

    `SCOPE_CONTENT` returns markup text plus injected copy; `SCOPE_TECHNICAL`
    returns comments and docstrings; `SCOPE_BOTH` returns all of it, tagged
    by `CodeBlock.kind` so the two never get confused downstream — which
    matters most at write time, where rewriting a comment and rewriting a
    heading are different decisions.
    """
    # Mask out script/style/comment bodies with spaces (same length, so
    # offsets stay valid) so their contents are never mistaken for copy.
    if is_locale_file(file_path):
        # A locale file has no markup and no comments worth judging; the whole
        # of it is copy, so neither the tag walk nor the comment pass applies.
        if scope in (SCOPE_CONTENT, SCOPE_BOTH):
            return _extract_locale_blocks(raw_text, file_path)
        return []

    masked = _SCRIPT_STYLE_COMMENT_RE.sub(lambda m: " " * len(m.group(0)), raw_text)
    masked = _CODE_COMMENT_RE.sub(lambda m: " " * len(m.group(0)), masked)

    blocks: list[CodeBlock] = []
    if scope in (SCOPE_TECHNICAL, SCOPE_BOTH):
        blocks.extend(_extract_technical_blocks(raw_text, file_path))
    if scope not in (SCOPE_CONTENT, SCOPE_BOTH):
        blocks.sort(key=lambda b: b.start)
        return blocks

    seen_spans: set[tuple[int, int]] = set()
    for gap in _TAG_GAP_RE.finditer(masked):
        if not _renders_text(gap.group("name")):
            continue
        gap_text = gap.group("gap")
        gap_start = gap.start("gap")
        for start, end, text in _extract_literal_runs(gap_text, gap_start):
            if not _is_markup_run(text):
                continue
            if (start, end) in seen_spans:
                continue
            if raw_text[start:end] != text:
                continue  # defensive: offsets must line up with the ORIGINAL file
            seen_spans.add((start, end))
            blocks.append(
                _make_code_block(raw_text, file_path, start, end, text, KIND_MARKUP)
            )

    # Copy that never sits between two tags: attributes, DOM assignments,
    # translation calls, content-keyed object literals. Skipped where markup
    # already claimed the same characters, so a value is never reported twice.
    for block in _extract_injected_blocks(raw_text, masked, file_path):
        if (block.start, block.end) in seen_spans:
            continue
        seen_spans.add((block.start, block.end))
        blocks.append(block)

    blocks.sort(key=lambda b: b.start)
    return blocks


def scan_file(path: str, scope: str = SCOPE_CONTENT) -> FileResult:
    """Scan a single file, ignoring extension and exclusion rules.

    Used by the CLI, where naming a file explicitly is an instruction to
    look at it rather than a candidate to be filtered.
    """
    p = Path(path)
    try:
        raw_text = p.read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeDecodeError) as exc:
        return FileResult(path=str(p), error=str(exc))
    return FileResult(path=str(p), blocks=_extract_blocks(raw_text, str(p), scope),
                      raw_text=raw_text)


def scan_repo(root_dir: str, config: ScanConfig | None = None, progress_cb=None) -> list[FileResult]:
    """Walk root_dir, skip anything matched by config.ignore_patterns, and
    extract tag-embedded text from every file with a matching extension.

    progress_cb, if given, is called as progress_cb(relative_path) right
    before each file is read, so a UI can show live progress.
    """
    config = config or ScanConfig()
    root = Path(root_dir).resolve()
    extensions = config.effective_extensions()
    matcher = _build_matcher(config.ignore_patterns)

    results: list[FileResult] = []
    for path in sorted(root.rglob("*")):
        if len(results) >= config.max_files:
            break
        if path.is_dir():
            continue
        if path.suffix.lower() not in extensions and not is_locale_file(path):
            continue
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            continue

        # Check every ancestor directory too, not just the file itself,
        # since gitignore-style dir patterns (e.g. "node_modules/") should
        # exclude everything underneath.
        parts = Path(rel).parts
        skip = False
        for i in range(1, len(parts)):
            ancestor = "/".join(parts[:i])
            if matcher(ancestor, is_dir=True):
                skip = True
                break
        if skip or matcher(rel, is_dir=False):
            continue

        if progress_cb:
            progress_cb(rel)

        try:
            if path.stat().st_size > config.max_file_size_bytes:
                results.append(FileResult(path=str(path), error="file too large, skipped"))
                continue
            raw_text = path.read_text(encoding="utf-8", errors="strict")
        except (OSError, UnicodeDecodeError) as exc:
            results.append(FileResult(path=str(path), error=str(exc)))
            continue

        blocks = _extract_blocks(raw_text, str(path), config.scope)
        results.append(FileResult(path=str(path), blocks=blocks, raw_text=raw_text))

    return results
