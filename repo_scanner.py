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
from models import (
    KIND_INJECTED, KIND_MARKUP, KIND_TECHNICAL, CodeBlock, FileResult,
    ScanDiagnostics,
)

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

# Server-side and framework languages that carry no markup of their own but
# still hand strings straight to a person: a Django `render()` context, a
# Laravel `__()` call, a Rails `flash[:notice]`. The tag-based rules
# (`_TAG_GAP_RE`, `_renders_text`) never run on these — there is no markup to
# walk — only the pattern-based injection rules do. See `_extract_blocks`.
BACKEND_EXTENSIONS = (".py", ".php", ".rb", ".erb", ".go", ".java", ".cs")

# Which pattern set a suffix uses. `.erb` shares Ruby's patterns (ERB is
# Rails' template language, embedded straight into `.erb` files) rather than
# having its own entry.
_BACKEND_LANGUAGE = {
    ".py": "py", ".php": "php", ".rb": "rb", ".erb": "rb",
    ".go": "go", ".java": "java", ".cs": "cs",
}

CONTENT_EXTENSIONS = DEFAULT_EXTENSIONS + BACKEND_EXTENSIONS

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

# Measured against ~/repositories/xformat (11.7k content blocks): sampling
# every block between 5 and 16 characters showed real UI copy at every length
# in that band ("Salva", "Model", "Dashboard", "Come funziona"), while the
# noise at the same lengths ("request_failed", "rate_limited", "sk-...",
# "v1") is snake_case/kebab-case, no-space, or otherwise identifier-shaped —
# not short. Raising this threshold would cut legitimate five-letter button
# labels without meaningfully reducing the junk, because length does not
# separate the two populations here; `_looks_technical` does. So the floor
# stays low and the junk is caught by shape instead.
MIN_BLOCK_LEN = 8

# A comment has to be a sentence, not a directive, to be worth judging.
# Longer than a line of copy because `// TODO: fix` and `# noqa` are the
# overwhelming majority of short comments and none of them are prose.
MIN_COMMENT_LEN = 40

# Sensible default excludes, gitignore-style. Editable in the UI before a
# scan; this is just the starting point.
#
# The last five entries were added after running the tool over eight real
# projects in August 2026, where every one of the 107 findings in a WordPress
# site came from a vendored plugin nobody in that project wrote, and a
# SharePoint solution reported the same defect from its deployed copy as well
# as from its source.
#
# Two candidates were deliberately NOT added, and the reason is worth keeping:
# `lib/` and `release/`. They are build output in a SPFx project - which is
# how one en dash in a Cherry Bank address came to be reported four times -
# but `src/lib/` is *source* in most React and Svelte projects, and excluding
# by that name blinded the scanner to 67 real findings in xFormat's own
# `apps/*/src/lib` the moment it was tried. A name cannot tell a build output
# from a source directory; identical content can, which is what the
# cross-file deduplication below does instead.
#
# Every entry here is a default, not a law: `--no-default-excludes` drops the
# lot, and auditing a dependency on purpose is a real thing to want.
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
bower_components/
third_party/
Pods/
ClientSideAssets/
wp-content/plugins/
**/app/plugins/
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
# `#` comments, for the backend languages that use them. Not masked
# unconditionally: `#{...}` is Ruby string interpolation, not a comment, so
# `#` immediately followed by `{` is left alone.
_HASH_COMMENT_RE = re.compile(r"(?<!\$)#(?!\{)[^\n]*")
_HASH_COMMENT_EXTENSIONS = frozenset((".py", ".rb", ".php"))
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
#: A fragment that *begins* in the middle of an expression. JSX puts markup
#: and code in the same braces, so the walk that reads the text between tags
#: also picks up the code between them: `) : doc.indexed_at ? (`,
#: `= useTranslation();  const [open, setOpen] = useState`.
#:
#: Only the opening, and that asymmetry is the measurement rather than a
#: preference. Prose never *starts* with a closing bracket or an assignment;
#: it does routinely *end* with an opening one, because a sentence broken
#: across JSX lines does exactly that - `Languages the provider declares (`
#: is copy, and a rule that also read the ending threw it away.
#:
#: Measured against `~/repositories/XFormat`, 1200 files, 1471 blocks from
#: `.ts`/`.tsx`: this removes 74 of them (5%), every one of them syntax, and
#: removes nothing that reads as prose - across the whole corpus, locale
#: files included, no block that reads as prose begins with any of these.
#: Adding the *ending* rule caught three more and cost one real sentence,
#: which is the wrong trade and is why only the opening is read.
_MID_EXPRESSION_RE = re.compile(r"^\s*(?:[)\]},]|&&|\|\||=[^=]|=>)")
_CODE_LOOKS_LIKE_RE = re.compile(
    r"=>|function\s*\(|\bimport\b|\bexport\b|\breturn\b|;\s*$|^\s*(const|let|var)\b",
    re.IGNORECASE,
)
# HTML entities end with ; — don't let that trigger the code detector
_HTML_ENTITY_RE = re.compile(r"&\w{1,8};")
_ALPHA_RE = re.compile(r"[^\W\d_]", re.UNICODE)  # at least one letter
# A dotted identifier with no spaces: `aiChat.gallery.next`. Only the dotted
# form is treated as a key, because a single word ("Download") is exactly what
# a project using English as its key language writes, and that is real copy.
_KEY_LIKE_RE = re.compile(r"^[A-Za-z_][\w-]*(?:\.[A-Za-z_][\w-]*)+$")


@dataclass
class ScanConfig:
    extensions: tuple[str, ...] | None = None
    ignore_patterns: list[str] = field(default_factory=lambda: _parse_ignore_text(DEFAULT_IGNORE_PATTERNS))
    #: The walk's ceiling. 5000 rather than 500 because the two numbers used
    #: to disagree between callers: the CLI passed 5000 and the window passed
    #: nothing, so the desktop app read 500 files of a 1732-file repository
    #: and said nothing about the other 1232. One default, and a cap that
    #: records itself in `ScanDiagnostics.truncated` when it bites.
    max_files: int = 5000
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
        return CONTENT_EXTENSIONS


def _parse_ignore_text(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]


def is_ignored(rel_path: str, matcher) -> bool:
    """Is this path excluded, by itself or by a folder above it?

    Every ancestor is checked, not just the file: gitignore-style folder
    patterns (`node_modules/`) exclude everything underneath, and matching
    only the file would read a hundred megabytes of dependencies.

    Public because the media pass walks the same tree for image files and
    has to agree with this one about what is out of bounds. Two walks with
    two opinions about `node_modules/` is one walk too many.
    """
    parts = Path(rel_path).parts
    for i in range(1, len(parts)):
        if matcher("/".join(parts[:i]), is_dir=True):
            return True
    return matcher(rel_path, is_dir=False)


def build_matcher(patterns: list[str]):
    """Public name for `_build_matcher`; see `is_ignored`."""
    return _build_matcher(patterns)


def _build_matcher(patterns: list[str]):
    """Returns a callable(relative_posix_path, is_dir) -> bool.
    Uses `pathspec` (gitignore-semantics) when available, falls back to a
    small builtin matcher (dir-prefix + fnmatch) otherwise.
    """
    try:
        import pathspec
        # `gitignore`, not `gitwildmatch`: the latter is deprecated in
        # pathspec and warns once per matcher built, which a scan does per
        # walk. Not swapped on the strength of the warning, though - this
        # decides what every scan reads, and two pattern dialects that
        # disagree about one line would silently change what a run examines.
        # Checked differentially first, over the 36 patterns in
        # `DEFAULT_IGNORE_PATTERNS` and a set of edge cases the project does
        # not use but a user's own `.xanalyze-ignore` might (negation,
        # anchoring, `**`, character classes, escaped `#`, trailing space):
        # zero disagreements. `tests/test_ignore_patterns.py` keeps the
        # behaviour pinned as a table so a future pathspec cannot move it
        # quietly.
        spec = pathspec.PathSpec.from_lines("gitignore", patterns)

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


# Machine-facing shapes that pass every other content check but are not
# something a person reads: identifiers, paths, formats. One rule underlies
# all of them: does this reach a human, or does it only reach a machine?
# `"user_not_found"` is a code; `"Користувача не знайдено"` is content.
_SNAKE_KEBAB_RE = re.compile(r"^[a-z][a-z0-9]*(?:[_.-][a-z0-9]+)+$")
_URL_RE = re.compile(r"^[a-zA-Z][\w+.-]*://|^www\.")
_MIME_RE = re.compile(r"^[a-z]+/[a-z0-9.+-]+$")
# A path: rooted (`/x`, `./x`, `../x`) or at least one `segment/segment`,
# never containing a space — real copy with a slash in it ("AI / ML") has
# spaces around the slash.
_PATH_LIKE_RE = re.compile(r"^(?:\.{1,2}/|/)[\w./-]*$|^[\w.-]+/[\w./-]+$")
_CSS_SELECTOR_RE = re.compile(r"^[.#][\w-]+(?:[ >+~][.#]?[\w-]*)*$")
_DATE_FORMAT_RE = re.compile(r"^(?:%[a-zA-Z]|[YMDHhms]|[\-/:., ])+$")


def _looks_technical(text: str) -> bool:
    """Is this shaped like something a machine reads, not a person?

    Catches what length alone cannot: `"request_failed"` and `"Dashboard"`
    are both plausible lengths for real copy, but only one of them is a key.

    An unresolved `${...}` is included here: a JS template literal or a
    dynamically-built i18n key (`` `cv.check.${check.id}` ``) captured with
    its expression still in it was pulled out mid-expression, not as text a
    reader ever sees. `{{ ... }}` is deliberately NOT treated the same way,
    even though it looks parallel — measured against xformat, `{{name}}` /
    `{{count}}` is i18next's own placeholder syntax sitting inside finished,
    reviewable prose ("Delete «{{name}}» from history?", "{{count}} words
    left"), and filtering on it discarded ~600 real content blocks for a
    handful of actual leaks that `${` alone already catches.
    """
    if "${" in text:
        return True
    if _URL_RE.match(text):
        return True
    if _MIME_RE.match(text):
        return True
    if _SNAKE_KEBAB_RE.match(text):
        return True
    if " " not in text and _PATH_LIKE_RE.match(text):
        return True
    if _CSS_SELECTOR_RE.match(text):
        return True
    if _DATE_FORMAT_RE.match(text) and re.search(r"[YMDHhms%]", text):
        return True
    return False


def _is_probably_content(text: str) -> bool:
    if len(text) < MIN_BLOCK_LEN:
        return False
    if not _ALPHA_RE.search(text):
        return False
    # HTML entities (&mdash; &#8212; etc.) end with ; which looks like code
    # Strip them before checking
    stripped = _HTML_ENTITY_RE.sub("", text)
    if _CODE_LOOKS_LIKE_RE.search(stripped):
        return False
    if _MID_EXPRESSION_RE.search(stripped):
        return False
    if re.fullmatch(r"[A-Z0-9_]+", text):  # CONSTANT_LIKE_TOKEN
        return False
    if text.startswith(("//", "/*", "#")):
        return False
    if _looks_technical(text):
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
#
# The WordPress family (`_e`, `_x`, `_n`, `_ex`, `_nx`, `_n_noop`, `_nx_noop`,
# and the `esc_html`/`esc_attr` variants of each) was missing everything but
# `__`. Measured on five calls of real theme copy: one found. A theme's
# visible text is written almost entirely through these, so the gap did not
# just miss a few strings - it read as a clean scan while finding almost
# nothing. `_n`/`_nx`/`_n_noop`/`_nx_noop` take a plural as a second string
# argument that this still does not capture - `_string_pattern` grabs one
# quoted string per match - but the singular found here beats the nothing
# found before.
_I18N_CALLS = (
    r"\$?t", r"i18n\.t", r"intl\.formatMessage", r"translate", r"gettext",
    r"__", r"\$tc", r"trans",
    r"esc_html__", r"esc_html_e", r"esc_html_x",
    r"esc_attr__", r"esc_attr_e", r"esc_attr_x",
    r"_ex", r"_nx_noop", r"_nx", r"_n_noop", r"_n", r"_e", r"_x",
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
    #
    # `(?<!:)` excludes a bound prop: Vue's `:placeholder="expr"` and
    # `v-bind:title="expr"` both have a literal `:` immediately before the
    # attribute name, and the quoted "value" there is a JS expression, not
    # rendered text, even when it happens to look like a string.
    _string_pattern(r"(?<!:)\b(?:" + "|".join(_VISIBLE_ATTRIBUTES) + r")\s*="),
    # element.textContent = "All set"
    _string_pattern(r"\.(?:textContent|innerText|innerHTML|placeholder|title|alt)\s*="),
    # t("Welcome back")  /  i18n.t('Welcome back')
    _string_pattern(r"\b(?:" + "|".join(_I18N_CALLS) + r")\s*\("),
    # title: "Welcome back"   (object literals, locale files, config)
    # An optional trailing quote is allowed before the colon so a Python/Ruby
    # dict with a quoted key ('title': '...') matches the same as JS object
    # shorthand (title: '...').
    _string_pattern(r"\b(?:" + "|".join(_CONTENT_KEYS) + r")[\"']?\s*:"),
)

# Backend-language-specific injection sites. Kept separate from
# `_INJECTION_PATTERNS` because they only make sense for the language they
# are named after; a stray `flash[:notice] = "..."` match in a JS file would
# be a false positive, not a find.
_BACKEND_INJECTION_EXTRA: dict[str, tuple[re.Pattern, ...]] = {
    # Django/DRF: JsonResponse({'detail': '...'}), Response(detail='...').
    # `["']?` allows the quoted-dict-key spelling ('detail': '...') as well
    # as the bare kwarg spelling (detail='...').
    # Python gettext shorthand: _("Welcome back"). `(?<![\w.])` keeps this
    # off `self._(...)` / `foo._(...)` attribute access and off `__(...)`,
    # which is matched separately via `_I18N_CALLS`.
    "py": (
        _string_pattern(r"\bdetail[\"']?\s*[:=]"),
        _string_pattern(r"(?<![\w.])_\s*\("),
    ),
    # Laravel: echo "Hello";
    "php": (
        _string_pattern(r"\becho\s+"),
    ),
    # Rails: flash[:notice] = "Saved"
    "rb": (
        _string_pattern(r"flash\[:\w+\]\s*="),
    ),
}

# Python: WELCOME = "Welcome back" — a module-level string constant. Only
# recognised by an ALL_CAPS name, which is the convention these are written
# under; a lowercase `welcome = "..."` is far more often a local variable
# than user-facing copy and is left alone.
_CONSTANT_ASSIGN_RE = re.compile(
    r"^[ \t]*[A-Z][A-Z0-9_]*\s*=\s*"
    r"""(?P<quote>["'])(?P<text>(?:\\.|(?!(?P=quote))[^\\])*)(?P=quote)""",
    re.MULTILINE,
)
# Blade: {{ 'Welcome back' }} — a literal string handed straight to the
# template's echo. `{{ $variable }}` does not match: there is no quote.
_BLADE_LITERAL_RE = re.compile(
    r"""\{\{\s*(?P<quote>["'])(?P<text>(?:\\.|(?!(?P=quote))[^\\])*)(?P=quote)\s*\}\}"""
)
# ERB: <%= 'Welcome back' %> — same idea, Rails' template syntax.
_ERB_LITERAL_RE = re.compile(
    r"""<%=\s*(?P<quote>["'])(?P<text>(?:\\.|(?!(?P=quote))[^\\])*)(?P=quote)\s*%>"""
)


def _collect_string_matches(raw_text: str, masked: str, patterns,
                            file_path: str, blocks: list[CodeBlock], seen: set) -> None:
    """Run each pattern over `masked`, keeping only spans that read as copy.

    Shared by markup-adjacent injection (`_extract_injected_blocks`) and the
    backend-language patterns (`_extract_backend_blocks`): both just capture
    a quoted string in group "text" and need the same content/key/dedup
    filtering before it becomes a `CodeBlock`.
    """
    for pattern in patterns:
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


def _extract_injected_blocks(raw_text: str, masked: str, file_path: str) -> list[CodeBlock]:
    """String literals that become visible copy.

    Runs over `masked` — the text with comment, script and style bodies
    blanked to equal-length spaces — so a commented-out `placeholder="..."`
    is not reported as live copy, while every offset still lines up with the
    original file.
    """
    blocks: list[CodeBlock] = []
    seen: set = set()
    _collect_string_matches(raw_text, masked, _INJECTION_PATTERNS, file_path, blocks, seen)
    return blocks


def _extract_backend_blocks(raw_text: str, masked: str, file_path: str, suffix: str) -> list[CodeBlock]:
    """Copy in a server-side language that has no markup of its own.

    No tag walk runs here — `.py`/`.php`/`.rb`/`.go`/`.java`/`.cs` are not
    tag-based, so `_TAG_GAP_RE` would either match nothing or, worse, match
    something incidental (a `<` comparison). Only the pattern-based sites are
    read: a render() context key, a translation call, a template's literal
    echo, an ALL_CAPS string constant.
    """
    blocks: list[CodeBlock] = []
    seen: set = set()
    language = _BACKEND_LANGUAGE.get(suffix)
    patterns = list(_BACKEND_INJECTION_EXTRA.get(language, ()))
    if language == "py":
        patterns.append(_CONSTANT_ASSIGN_RE)
    elif language == "php":
        patterns.append(_BLADE_LITERAL_RE)
    elif language == "rb":
        patterns.append(_ERB_LITERAL_RE)
    _collect_string_matches(raw_text, masked, patterns, file_path, blocks, seen)
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
        if _MID_EXPRESSION_RE.search(stripped):
            continue
        if _looks_technical(stripped):
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


def mask_code_comments(raw_text: str, file_path: str) -> str:
    """Blank out code comments, keeping every other character where it was.

    Spaces rather than deletion because offsets are load-bearing: block spans,
    `sourceline` and `sourcepos` all index into the original text, and a mask
    that shortened the file would move every one of them. Newlines are kept
    for the same reason one step up - blanking them too keeps every offset
    correct while silently merging a twenty-line comment into one line, and
    then every line number after it is twenty short.

    Public because the audit needs the same masking for the same reason the
    extractor does. A comment that talks about markup - `// on remount ->
    <img> ERR_FILE_NOT_FOUND` - is markup to an HTML parser, and the audit was
    reporting those prose mentions as real elements with no `alt`.
    """
    suffix = Path(file_path).suffix.lower()
    masked = _SCRIPT_STYLE_COMMENT_RE.sub(_blank_but_newlines, raw_text)
    masked = _CODE_COMMENT_RE.sub(_blank_but_newlines, masked)
    if suffix in _HASH_COMMENT_EXTENSIONS:
        masked = _HASH_COMMENT_RE.sub(_blank_but_newlines, masked)
    return masked


def _blank_but_newlines(match) -> str:
    text = match.group(0)
    return "".join("\n" if ch == "\n" else " " for ch in text)


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

    suffix = Path(file_path).suffix.lower()

    masked = mask_code_comments(raw_text, file_path)

    blocks: list[CodeBlock] = []
    if scope in (SCOPE_TECHNICAL, SCOPE_BOTH):
        blocks.extend(_extract_technical_blocks(raw_text, file_path))
    if scope not in (SCOPE_CONTENT, SCOPE_BOTH):
        blocks.sort(key=lambda b: b.start)
        return blocks

    seen_spans: set[tuple[int, int]] = set()

    # Backend languages carry no markup of their own — see BACKEND_EXTENSIONS
    # — so the tag walk is skipped for them entirely rather than run and
    # produce nothing (or, worse, mis-fire on a `<` comparison).
    if suffix not in BACKEND_EXTENSIONS:
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

    if suffix in BACKEND_EXTENSIONS:
        for block in _extract_backend_blocks(raw_text, masked, file_path, suffix):
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


def scan_repo(root_dir: str, config: ScanConfig | None = None, progress_cb=None,
              diagnostics: ScanDiagnostics | None = None) -> list[FileResult]:
    """Walk root_dir, skip anything matched by config.ignore_patterns, and
    extract tag-embedded text from every file with a matching extension.

    progress_cb, if given, is called as progress_cb(relative_path) right
    before each file is read, so a UI can show live progress.

    `diagnostics`, if given, is filled with what the walk saw: how many files
    were opened, how many were skipped and why, and whether the cap stopped
    it early. An out-parameter rather than a changed return type because
    every caller wants the files and only some want the accounting - the same
    shape `cli._collect`'s `missing_out` already uses.
    """
    config = config or ScanConfig()
    root = Path(root_dir).resolve()
    extensions = config.effective_extensions()
    matcher = _build_matcher(config.ignore_patterns)
    diagnostics = diagnostics if diagnostics is not None else ScanDiagnostics()
    diagnostics.limit = config.max_files

    results: list[FileResult] = []
    for path in sorted(root.rglob("*")):
        if len(results) >= config.max_files:
            # Recorded, then stopped. A bare `break` here is what made a
            # partial answer look like a complete one.
            diagnostics.truncated = True
            break
        if path.is_dir():
            continue
        if path.suffix.lower() not in extensions and not is_locale_file(path):
            continue
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            continue

        if is_ignored(rel, matcher):
            diagnostics.skipped_ignored += 1
            continue

        if progress_cb:
            progress_cb(rel)

        try:
            if path.stat().st_size > config.max_file_size_bytes:
                diagnostics.skipped_too_large += 1
                results.append(FileResult(path=str(path), error="file too large, skipped"))
                continue
            raw_text = path.read_text(encoding="utf-8", errors="strict")
        except (OSError, UnicodeDecodeError) as exc:
            diagnostics.unreadable += 1
            results.append(FileResult(path=str(path), error=str(exc)))
            continue

        blocks = _extract_blocks(raw_text, str(path), config.scope)
        diagnostics.files_read += 1
        diagnostics.blocks_found += len(blocks)
        results.append(FileResult(path=str(path), blocks=blocks, raw_text=raw_text))

    return results
