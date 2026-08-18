# AI Content Scanner

Finds text that reads as machine-written — and characters that no keyboard
produces — in Ukrainian, Italian, and English.

Two ways to run it:

* **Desktop app** (`python main.py`) — PySide6, fully native, no browser
  shell. Crawl a **web page** or scan a **local repository folder**, review
  findings in a three-column window, edit and apply replacements.
* **Command line** (`python cli.py`) — the same engine with no GUI, built
  to run *after* an LLM coding agent (Claude Code, Codex, Cursor…) has
  written files. See [Headless / agent mode](#headless--agent-mode).

## Non-keyboard characters

Alongside whichever content detector you pick, an exact, offline pass looks
for characters a person would not type, and knows what each should become:

| Category | Examples | Fix |
|---|---|---|
| `invisible` | zero-width space/joiner, soft hyphen, BOM, direction marks | removed |
| `space` | non-breaking, narrow, hair, ideographic spaces | plain space |
| `homoglyph` | Cyrillic `а` inside a Latin word, Latin `o` inside a Cyrillic one | letter from the word's own alphabet |
| `styled` | `𝐀𝐁𝐂` mathematical bold, `Ａ` fullwidth | plain letter |
| `typography` | `— – " " „ … • ×` | `- ' " ... - x` |

The hard part isn't finding non-ASCII characters — it's *not* flagging the
ones that are correct for the language. Italian keyboards type `è à ò ù`
directly, Ukrainian is Cyrillic throughout and uses «guillemets» as its
standard quotation marks, and an em dash is the correct Ukrainian тире. So
every rule is scoped by script and language: `Купуйте iPhone 15 Pro` and
`Perché è così?` come back clean, while `pаssword` (with a Cyrillic `а`)
does not.

The first four categories have no legitimate use in ordinary copy and are
scored high. `typography` is scored medium and can be switched off in
**Settings → Characters** (or `--no-typography`) if you'd rather keep
proper dashes and quotation marks.

Because each correction is fixed by a rule rather than guessed by a model,
**the whole flag-and-fix loop runs offline and free** — the "Fix
characters" button and `cli.py fix` make no API calls at all.

## Known limitation — read this first

**Claude's text watermark is live. Reading it is not possible yet.** Checked
against Anthropic's own pages on 18 August 2026:

* Claude models launched on or after 2 August 2026 mark their text output
  with an imperceptible watermark (an approach derived from SynthID-Text),
  across the API, Claude, Claude Code and the rest of the surfaces.
* Detection has **not** shipped. Anthropic says it is "working to enable
  users and other third parties to detect Claude's embedded watermarks and
  provenance metadata" and will share the mechanism "in forthcoming
  technical documentation"; a detection API is stated to be coming, with its
  implementation still being worked out. No endpoint, auth scheme or payload
  format has been published.
* C2PA signed provenance metadata *is* verifiable today — but only on
  generated **files** (`.svg`, `.png`, `.jpg`), not on text. This tool reads
  page copy and source files, so that path does not apply to it.

So nobody can honestly ship text-watermark detection today, and a tool that
claims to is running a classifier under a name that isn't one. This app is
upfront about that — it ships working classifiers, plus a wired-but-inert
placeholder for the real thing:

| Detector | Works today? | What it actually does |
|---|---|---|
| `offline` | Yes, fully offline and free | Both free passes in one. **Wording:** style uniformity, lexical diversity, dash density, "not just X but Y" structural patterns, and ~150 per-language cliché words/phrases (uk/it/en). Weak signal. **Characters:** an exact, language-scoped pass for characters no keyboard produces — see above. |
| `claude-llm-judge` | Yes, needs `ANTHROPIC_API_KEY` | Asks a live Claude model to read the text and flag passages that read as AI-generated, like a human reviewer would. Not the watermark — an opinion. |
| `xformat-llm-judge` | Yes, needs an xFormat sign-in | The same judgement, billed to your xFormat subscription instead of a personal key. The model is whatever your plan is entitled to. |
| `claude-official-watermark` | No — raises a clear error | Placeholder for Anthropic's real detector. Fill in `detectors/claude_watermark_stub.py::_call_official_api` once they publish it; nothing else in the app needs to change. |

None of these give you a provable verdict. Treat every flag as "worth a
second look," never as proof.

### Why the two offline modes are one

The style pass and the character pass used to be two entries in the detector
dropdown plus a checkbox in Settings. They are not alternatives: one reads
*wording*, the other reads *characters*, both run locally and free, and a
passage can be flagged by either or both. Making them mutually exclusive
meant every scan silently gave up one of two free signals.

They are now one `offline` detector, and the dropdown is a real choice
between things that genuinely exclude each other — free-and-local versus a
paid model. Which pass produced a finding is still recorded (in
`TextSpan.details["source"]`), which is what keeps the character-only fix
button working. The old names `heuristic` and `unicode-anomalies` still
resolve, so an existing `settings.json` or a `--detector` flag in a git hook
keeps working.

### Why a passage was flagged, and what to replace it with

Clicking a finding shows **Why it was flagged** in your UI language: which
cliché phrases matched, which structural pattern fired, which statistical
signals crossed their threshold — and, for a character finding, the exact
codepoint and exactly what it becomes.

Underneath it, where the correction follows a rule rather than taste, is a
**suggested replacement built offline** — no API call, no cost. Every cliché
in the word lists is paired with the plainer wording a person would have
typed, or deleted outright when it is pure filler, with the capitalisation
and stray punctuation cleaned up afterwards. A test fails if a phrase is
added to the detector without a replacement here.

Where the only signals are statistical — uniform sentence rhythm, low word
variety — there is deliberately **no** suggestion. Those are a property of a
whole passage, not a string that can be swapped out, and a "suggestion"
built from them would be a guess dressed up as a rule. The panel says so and
points at the rewrite button.

### Where the heuristic word/phrase lists came from

Compiled from public write-ups on AI-writing "tells" (August 2026):
Wikipedia's "Signs of AI writing" essay, Grammarly's "Common Words and
Phrases in AI-Generated Text", useaiwriter.com's "300+ AI Words and Phrases
to Avoid", oliviacal.com's "How to Spot AI Writing Tells" (structural
patterns: em-dash overuse, rule-of-three, uniform sentence rhythm),
theinweb.media's Ukrainian AI-marker word list, and fastweb.it's Italian
ChatGPT-tell word list. These are crowd-sourced observations, not a
scientific ground truth — extend or prune the lists in
`detectors/heuristic.py` (`CLICHE_PHRASES`, `STRUCTURAL_PATTERNS`) for your
own content.

## Install & run

```bash
pip install -r requirements.txt
python main.py
```

Detection runs locally and free. Only *generating* replacement text costs
money, and you pick who pays in **Settings → Rewriting**:

| Provider | What it is |
|---|---|
| `anthropic` | Your own Anthropic API key. Read from `ANTHROPIC_API_KEY`, or enter it in Settings (stored in the OS keychain, never in `settings.json`). |
| `xformat` | Your **app.xformat.net subscription** — sign in with email + password in Settings and the calls are billed to your plan instead of a personal key. |

The graphical page preview uses `PySide6.QtWebEngineWidgets` (bundled
Chromium), which is a few hundred MB — that's why the install is heavier
than a typical PySide6 app.

## Headless / agent mode

`cli.py` imports no GUI toolkit, so it runs in a git hook, in CI, in a
container, or as a shell command an LLM agent invokes itself.

```bash
python cli.py scan ./src                 # report, change nothing
python cli.py scan ./src --json          # machine-readable, for an agent to parse
python cli.py scan ./src --check         # exit 1 if anything was found
python cli.py fix  ./src                 # rewrite non-keyboard characters in place
python cli.py fix  ./src --dry-run       # show what would change
echo "text" | python cli.py clean        # filter text on stdin to stdout
```

Exit codes: `0` clean, `1` findings (with `--check`), `2` error — so it
drops straight into a pre-commit hook or a pipeline step.

Useful flags: `--detector heuristic` also runs the style detector (reported,
never auto-applied — only the character fixes are deterministic enough to
apply unattended); `--no-typography` keeps em dashes and curly quotes;
`--categories homoglyph,invisible` narrows the pass; `--exclude` adds
gitignore-style patterns; `--no-backup` skips `.bak` files when the repo is
already in git.

**As a post-step for a coding agent.** Point it at whatever the agent just
wrote:

```bash
# after the agent finishes
python /path/to/cli.py fix ./src --no-backup
```

Or wire it into Claude Code as a `PostToolUse` hook so every file the agent
writes is cleaned immediately. `--json` output has one object per finding
with `file`, `line`, `offset`, `text`, `replacement` and `explanation`,
which is enough for an agent to reason about the changes rather than just
apply them.

`fix` only applies the deterministic character corrections. Style findings
are reported so you (or the agent) can decide, never rewritten silently.

## Auditing: accessibility, SEO, performance, best practices

A second, separate analysis. The text scan asks whether a *person* would
believe a human wrote this; the audit asks whether the *document* is broken.
39 rules of our own across four categories, plus — on request — axe-core and
HTML_CodeSniffer running in a real browser.

Every finding is explained in full, in Ukrainian, Italian or English: what was
found, why it matters *to the person using the page*, and how to fix it.

### Three kinds of target

```bash
python cli.py audit https://example.com --depth 1   # a site, crawled same-domain
python cli.py audit ./src                           # a project folder
python cli.py audit ./page.html                     # one self-contained HTML file
```

The third is for a page **built or exported into a single file** — everything
inlined, no assets beside it. It is deliberately not read as part of a project:
folder mode looks for markup fragments and skips anything with no elements, so
the `<head>` of a packed page — canonical, description, Open Graph, charset —
would never be examined at all. As a page, it gets those rules, plus line
numbers, because you have the file open.

### Adding a real browser

```bash
python cli.py audit https://example.com --browser
python cli.py audit ./page.html --browser
```

`--browser` loads each page in the Chromium that already ships with the app and
runs four passes over it: **axe-core** and **HTML_CodeSniffer** (the two
industry engines — together they find noticeably more than either alone), a
**state pass** that focuses every control and looks for invisible focus rings,
keyboard traps and hover-only menus, and **load measurements** read from the
Performance API.

This is the only way to see what JavaScript actually rendered, and the only way
to judge contrast after the cascade. It costs a few seconds per page. Findings
that two engines agree on are collapsed into one row that names its
corroboration, rather than shown twice.

For a URL the page is fetched normally. For a local file it is opened from
`file://`, and only then is the page allowed to read files beside it on disk —
a page off the network never is.

Not available for a project folder: a browser has nothing to load for a `.jsx`
fragment that was never a page.

### Narrowing and gating

```bash
python cli.py audit ./page.html --category accessibility seo
python cli.py audit ./page.html --language it        # explanations in Italian
python cli.py audit https://example.com --json       # machine-readable
python cli.py audit ./src --check                    # exit 1 on critical or serious
```

`--category` is a *view* over one pass, not a different run, so a narrowed
audit and a full one always agree on what they both report.

Suppressions are shared with the text scan — one `.xanalyze-ignore` governs the
whole tool. Selectors and disabled rules are handed to the engines rather than
filtered out of their output, so an excluded region costs nothing to analyse.

### Writing the corrections back

Seventeen rules do not merely report a problem, they know the corrected
markup. Those corrections can go straight into the file:

```bash
python cli.py audit ./page.html --fix          # write what needs no decision
python cli.py audit ./page.html --fix --ai     # let a model write the rest too
python cli.py undo ./page.html                 # put every file back
```

A `.bak` copy is written before the first change and **never overwritten
afterwards**, so `undo` returns the file to how it was before the tool first
touched it — not to the state between two runs.

Corrections come in two tiers, and the split is the point:

| | examples | written unattended |
|---|---|---|
| follows from the markup | missing doctype, missing charset, a heading that skipped a level, `target="_blank"` without `rel="noopener"`, `http://` that should be `https://` | yes |
| encodes a decision | `alt=""` (which *claims* the image is decorative), the page's description, a canonical URL, alternative text | no — needs a person or `--ai` |

The second tier is held back deliberately. Writing `alt=""` onto a photograph
declares it decorative, hides its meaning from every screen reader, and stops
the next audit reporting it — a green result over an unsolved problem, which
is worse than the red one it replaced.

`--ai` fills those in through whichever provider is configured (inside a Claude
Code session, that is Claude Code itself, so it costs nothing extra). The model
is instructed to answer `SKIP` when the page does not actually say what the
answer is, and a skipped item is left undone rather than invented. Anything the
model wrote is named as the model's in the report.

One thing is read locally rather than asked of anyone: the page's language,
which is in the page's own words. `<html lang>` therefore gets the language the
page is actually written in, not the rule's default.

### Handing the result to a coding agent

```bash
python cli.py audit ./src --report audit.md
python cli.py audit ./src --report audit.json     # same facts, parsed
```

`--json` gives a flat list of findings, which is the right shape for a pipeline
and the wrong shape for an agent about to edit code. `--report` writes a
different document:

* **statistics** — counts by severity, how many documents, how many rules fired;
* **history** — what the numbers were last time, and whether they went up or down (kept in a small `.history.json` beside the report);
* **what this run already changed**, which files, which backups exist, and which values a model wrote;
* **what was deliberately left alone, and why** — so the agent does not "fix" a decision that was held back on purpose;
* **a file map** — every file, every finding, line number, the element, why it matters and the exact replacement markup where one exists.

That is enough for an agent to open the right files and make the right edits
without re-running anything.

### In the window

**Source** in the toolbar picks between *Web page*, *Repository*, *Site audit*
and *A single HTML file*. The last two show a **In a browser** switch; the
findings list is the same three-column layout, and clicking a finding shows the
rendered page beside the explanation.

Under the list, the audit modes offer three buttons: **Fix in the file** (with
the same two tiers as `--fix`, and a prompt asking whether a model should write
the ones that need words), **Undo**, which is only enabled once a backup
exists, and **Report for an agent**, which saves the same briefing `--report`
writes.

## app.xformat.net integration

Sign in once under **Settings → Rewriting**. The password is used to
obtain tokens and is then discarded — only the access/refresh tokens are
kept, in the OS keychain when one is available (`keyring`), otherwise in a
`0600` file, and the dialog tells you which of the two is in use. Sessions
survive restarts; an expired token is refreshed and the request retried
automatically, and only a failed refresh asks you to sign in again.

**The API contract isn't wired to anything final yet.** Since the exact
endpoints weren't settled at build time, every path and JSON field name
lives in `XFormatEndpoints` (`llm/xformat_provider.py`) and can be
overridden as JSON under **Settings → Advanced** — no code change needed.
The defaults assume:

```
POST /api/v1/auth/login     {email, password} -> {access_token, refresh_token, expires_in}
POST /api/v1/auth/refresh   {refresh_token}   -> {access_token, expires_in}
GET  /api/v1/me                               -> {email, plan, quota_remaining}
POST /api/v1/rewrite        {text, language, system} -> {text}
```

`Settings → Advanced → Show defaults` prints the full field map. Dotted
paths work if your responses are nested (`"access_token_field": "data.token"`).
Statuses are handled distinctly: 401/403 → re-auth, 402 → inactive
subscription or quota exhausted, 429 → rate limited.

Adding another provider (OpenAI, a local model) is one class implementing
`LLMProvider` plus a `LLMProviderFactory.register(...)` call — the same
pattern as `detectors/`.

## How it works

1. **Crawl** (`crawler.py`) — fetches the given URL and, up to the depth you
   choose, every same-domain page it links to (depth 0 = just that one
   page). Extracts visible text block-by-block (headings, paragraphs, list
   items, buttons, labels...), each tagged with its source page, the raw
   page HTML (for the preview column), and a best-effort DOM path
   (`tag:nth-of-type(n) > ...`, which doubles as a valid CSS selector).
2. **Detect** (`detectors/`) — every backend implements the same
   `Detector` interface (`detectors/base.py`) and registers itself with
   `DetectorFactory` (`detectors/factory.py`). The app, the UI, and the
   analysis pipeline only ever talk to that interface — swapping or adding
   a backend (OpenAI, a local model, your own service, the real Claude
   watermark API once it exists) means writing one class and registering
   it; nothing else changes.
3. **Review** (`ui/`) — see "Layout" below.

## Layout

The window is a three-column view:

1. **Site preview** — the actual page, rendered (`QWebEngineView`), with
   whichever passage you've selected in column 2 outlined in red and
   scrolled into view (via a small injected stylesheet + `querySelector`
   using the block's DOM path).
2. **Flagged passages** — every medium/high-confidence span, sorted by
   score.
3. **Detail panel** — appears when you click a passage in column 2: the
   original text, an editable draft box, and three actions:
   - **Save draft** — stores your rewrite locally (marks the row with ✎).
     Nothing is written back to your site; copy the result out yourself.
   - **Additional analysis** — re-runs whichever detector is selected at
     the top on just this one passage (useful to double-check a `heuristic`
     flag with `claude-llm-judge` without rescanning the whole site).
   - **Refactor via my AI** — calls `BackendConnector.start_chat()`
     (see below). Wired up, not implemented yet — shows a message
     explaining that, exactly as you asked for a button "we'll add later."

**Responsive breakpoint:** above ~1000px window width you get the full
three columns side by side. Below that, column 3 disappears and clicking a
passage instead expands the detail form inline, directly under that row in
column 2 (an accordion — clicking another row collapses the previous one).
The threshold lives in `ui/main_window.py::WIDE_BREAKPOINT`.

## Repository mode

Switch the **Source** dropdown to "Repository (code)" to scan a local
folder instead of a live URL. Column 1 then shows the raw source file
(monospace, read-only) instead of a rendered page, with the selected
passage's exact character range highlighted.

- **What gets scanned**: `.html`, `.htm`, `.xml`, `.jsx`, `.tsx`, `.vue`,
  `.svelte` files — i.e. content that sits *inside markup tags*
  (`<h1>Welcome back</h1>`, Android `<string name="...">...</string>`,
  JSX children — including splitting `<p>Hello {name}!</p>` into "Hello"
  and "!" around the `{expression}`, which is skipped as code, not copy).
  `<script>`/`<style>` bodies and comments are never scanned. This is a
  regex-based extractor, not a real parser — see the limitation note at
  the top of `repo_scanner.py`.
- **Exclusions** — the "Filter…" button opens a `.gitignore`-style pattern
  list, pre-filled with sensible defaults (`node_modules/`, `.git/`,
  `dist/`, `build/`, `venv/`, `ios/Pods/`, `android/build/`, lockfiles,
  minified files...). Matching uses `pathspec` (real gitignore semantics)
  when installed, with a small built-in fallback otherwise.
- **Two extra buttons** appear in column 2, replacing the web mode's
  single per-passage "Save draft" flow with two bulk actions (both need
  `ANTHROPIC_API_KEY` for any passage that doesn't already have a manual
  draft — there's no offline way to *generate* a rewrite, only to flag):
  - **Generate replacement list** — asks Claude for a natural-sounding
    rewrite of every flagged passage that doesn't already have one, fills
    them in as drafts (editable in column 3 exactly like web mode), then
    offers to export the whole list as a Markdown review file.
  - **Auto-replace in files** — same generation, but after a confirmation
    dialog it writes every result straight into the source files.

### Write safety

Replacements are **span-scoped**. A detector flags a block sentence by
sentence, so editing one sentence replaces exactly that sentence's
characters and leaves the rest of the paragraph untouched — including any
sentences the detector considered human-written. Three guards apply on
every write:

1. A `.bak` copy of each file is made before its first edit in a run (and
   never overwritten afterwards, so your one clean copy stays clean).
2. Each edit re-checks that the text at the recorded offset still matches
   what was scanned; if the file changed underneath the scan, that passage
   is skipped rather than splicing text into the wrong place.
3. Overlapping edits within a file are rejected rather than applied.

The summary dialog reports applied / skipped-stale / skipped-overlap
counts, so nothing is dropped silently.

## Adding a detector

```python
# detectors/my_backend.py
from detectors.base import Detector
from detectors.factory import DetectorFactory

class MyDetector(Detector):
    name = "my-backend"
    display_name = "My Backend"

    def analyze_block(self, block):
        ...  # return list[TextSpan]

DetectorFactory.register(MyDetector.name, MyDetector)
```

Then import it in `detectors/__init__.py` and it shows up in the UI's
detector dropdown automatically.

## Your own backend / chat integration

You mentioned you already have an AI account/backend that could validate
scans and run a chat integration on top of them, but that this is still
undecided. `backend_connector.py` defines the seam for that
(`BackendConnector.validate_scan`, `BackendConnector.start_chat`) with a
no-op implementation (`NullBackendConnector`) wired in by default — that's
what powers the "Refactor via my AI" button's placeholder message today.
When you're ready, implement a real connector against your backend's
actual API and flip `backend_enabled = True` in `config.py`'s `Settings` —
the rest of the app doesn't need to change.

## Packaging as a real desktop app

```bash
pip install pyinstaller
python -m PyInstaller packaging/XAnalyze.spec --noconfirm
hdiutil create -volname XAnalyze -srcfolder dist/XAnalyze.app \
  -ov -format UDZO dist/XAnalyze-0.1.0-arm64.dmg
```

That produces `dist/XAnalyze.app` (~490 MB, most of it Chromium) and a
~200 MB compressed disk image.

The spec does one thing beyond collecting files, and it matters: PyInstaller
flattens `QtWebEngineCore.framework` and leaves `QtWebEngineProcess` where the
framework's own symlink does not point, so the frozen app loses **both** the
page preview and the entire browser audit pass — while `python main.py` from
the checkout keeps working perfectly, which is exactly how a broken build gets
called verified. The spec repairs the layout and then refuses to finish if the
helper is not where Qt will look for it.

The build is ad-hoc signed, not notarised. macOS will therefore quarantine it
on first open; right-click → **Open**, or:

```bash
xattr -dr com.apple.quarantine /Applications/XAnalyze.app
```

## Project layout

```
main.py                        desktop entry point
cli.py                         headless entry point (scan / fix / clean) for agents, hooks, CI
unicode_rules.py               character tables, language scoping, and the deterministic fixer
models.py                      shared dataclasses: web (TextBlock/PageResult/AnalysisResult)
                                and repo (CodeBlock/FileResult/RepoAnalysisResult)
lang_detect.py                 shared uk/it/en language guess used by both extractors
crawler.py                     same-domain crawler with depth control, keeps raw HTML per page
repo_scanner.py                local-folder scanner: tag-content extraction + gitignore-style excludes
file_writer.py                 applies span-scoped replacements back into source files (backups + staleness/overlap guards)
rewriter.py                    builds the configured LLM provider and rewrites passages through it
config.py                      persisted settings; secrets go to the keychain, not settings.json
backend_connector.py           legacy seam for a broader backend integration
detectors/
  base.py                      Detector ABC + DetectorUnavailable
  factory.py                   DetectorFactory (register/create)
  heuristic.py                 offline style + structure + cliché-phrase detector
  unicode_anomalies.py         exact pass for characters no keyboard produces
  claude_llm_judge.py          live Claude API, LLM-as-judge
  claude_watermark_stub.py     placeholder for the real watermark API
llm/
  base.py                      LLMProvider ABC + LLMProviderFactory + shared rewrite prompt
  anthropic_provider.py        billed to your own Anthropic key
  xformat_provider.py          billed to your app.xformat.net subscription (login/refresh/quota)
  credentials.py               OS keychain with a 0600-file fallback
i18n/
  translations.py              uk/it/en UI strings
ui/
  main_window.py                three-column responsive main window, both source modes
  settings_dialog.py            language, provider, credentials, endpoint mapping
  worker.py                    background QThreads (site/repo scan, re-analysis, single + bulk rewrite)
  site_preview.py               builds the JS that highlights the selected element in the web preview
  code_preview.py               highlights the selected character range in the code preview
```

Note: `detectors/*` never import anything web- or repo-specific — they
only read `.block_id` / `.text` / `.language_hint` off whatever's passed
in, and `CodeBlock` exposes those same names. That's what let repository
mode reuse every existing detector (including `claude-llm-judge`)
completely unchanged.
