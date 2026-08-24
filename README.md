# XAnalyze

Desktop and headless analyzer: AI-generated text detection, non-keyboard characters, and full website/repository accessibility audit.

[Українська](README_ua.md) | [Italiano](README_it.md)

---

## Table of Contents

- [Features](#features)
- [Quick Start](#quick-start)
- [CLI Commands](#cli-commands)
  - [fullscan](#fullscan---full-scan)
  - [scan](#scan---ai-patterns-detection)
  - [audit](#audit---accessibility-seo-performance)
  - [fix](#fix---apply-fixes)
  - [undo](#undo---revert-fixes)
  - [cache](#cache---manage-scan-cache)
  - [compare](#compare---compare-detectors)
  - [ai](#ai---ai-backed-operations)
  - [clean](#clean---filter-text)
  - [agent-scan](#agent-scan---offline-scan-for-agent)
  - [agent-judge](#agent-judge---merge-agent-judgments)
  - [update](#update---self-update)
- [Runs: pause, stop, continue](#runs-pause-stop-continue)
  - [The render watchdog](#the-render-watchdog)
  - [When the PDF still cannot be printed](#when-the-pdf-still-cannot-be-printed)
- [Global Flags](#global-flags)
- [Detection Methods](#detection-methods)
  - [AI Pattern Detection](#ai-pattern-detection)
  - [Non-keyboard Characters](#non-keyboard-characters)
  - [Accessibility Audit](#accessibility-audit)
  - [SEO Audit](#seo-audit)
  - [Performance Audit](#performance-audit)
  - [Best Practices](#best-practices)
  - [Browser Pass](#browser-pass)
- [Detectors](#detectors)
- [Reports](#reports)
- [For AI Agents](#for-ai-agents)
  - [How Users Ask](#how-users-ask)
  - [Agent-as-Judge Mode](#agent-as-judge-mode)
  - [Command Reference](#command-reference-with-user-requests)
  - [Workflow Examples](#workflow-examples)
- [GUI](#gui)
- [TUI (Terminal Interface)](#tui-terminal-interface)
- [Configuration](#configuration)
- [Uninstall](#uninstall)
- [Requirements](#requirements)
- [License](#license)

---

## Features

- **AI Pattern Detection** — heuristic (clichés, structural patterns, burstiness) and embedding-based (sentence-transformers)
- **Non-keyboard Characters** — zero-width spaces, curly quotes, em dashes, homoglyphs
- **Accessibility Audit** — WCAG rules, SEO, performance, best practices (52 rules)
- **Full Scan** — combined AI patterns + accessibility in one command with automatic browser rendering
- **Styled Reports** — branded PDF/HTML for humans
- **Agent Briefings** — markdown/JSON for coding agents
- **CLI + GUI + TUI** — one binary, three interfaces
- **Responsive Audit** — test at desktop, tablet, and mobile widths
- **Browser Rendering** — real Chromium for client-side rendered sites (React, Vue, Next.js)

---

## Quick Start

### GUI (macOS)

```bash
curl -L -o XAnalyze.app.zip https://github.com/vlad-demchyk/xAnalyze-/releases/latest/download/XAnalyze.app.zip
unzip XAnalyze.app.zip
mv XAnalyze.app /Applications/
```

### CLI (macOS/Linux)

```bash
curl -L -o xanalyze-cli.tar.gz https://github.com/vlad-demchyk/xAnalyze-/releases/latest/download/xanalyze-cli-macos-arm64.tar.gz
tar -xzf xanalyze-cli.tar.gz
echo 'export PATH="$PWD/xanalyze:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

### From Source

```bash
git clone https://github.com/vlad-demchyk/xAnalyze-.git
cd xAnalyze-
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# GUI
python main.py

# CLI
python cli.py fullscan https://example.com
```

---

## Usage

### Interactive TUI

Just type `xanalyze` with no arguments to launch the interactive terminal interface:

```bash
xanalyze
```

The TUI provides a menu-driven interface with:
- **Scan** — detect AI-generated text patterns and non-keyboard characters
- **Audit** — check accessibility, SEO, performance, best practices
- **Full Scan** — everything in one run
- **Reports** — view previous analysis results
- **Settings** — inspect configuration
- **Update** — check for new versions
- **Uninstall** — remove XAnalyze from this machine

Navigate with arrow keys or number shortcuts (1-7). The footer lists the keys
each screen accepts. `Esc` goes back, `q` quits.

### CLI Commands

```bash
# Scan a directory for AI patterns
xanalyze scan ./src

# Audit a website for accessibility
xanalyze audit https://example.com --browser

# Full scan (AI + accessibility + SEO)
xanalyze fullscan https://example.com

# Fix non-keyboard characters in place
xanalyze fix ./src

# Check for updates
xanalyze update

# Remove XAnalyze from this machine
xanalyze uninstall

# Show version
xanalyze --version
```

### Self-Update

```bash
# Check and install the latest version
xanalyze update
```

Every CLI command also checks for updates once a day and prints a hint if a newer version is available. Suppress with `--no-update-check`.

---

## CLI Commands

### `fullscan` - Full Scan

The primary command for comprehensive analysis. Combines AI pattern detection, accessibility audit, SEO, performance, and best practices in one run.

**Automatic behavior for URLs and HTML files:**
- Browser rendering enabled (handles React, Vue, Next.js, etc.)
- Responsive breakpoints: desktop (1440px), tablet (834px), mobile (390px)
- JSON output for agent consumption
- Every document saved into a folder for this target on your Desktop

**Where the documents go.** One folder per target, one sub-folder per run:

```
~/Desktop/XAnalyze/example.com/
    2026-08-24-0930/
        report.md        agent briefing, and the grouped problem list
        report.pdf       the branded report for a person
        timings.md       how long each stage took
        changes.md       what changed since the previous run
        state.md         which stage the run reached, and how to continue it
        state.json       the same, for a machine
    2026-08-24-1145/
        ...
```

`changes.md` appears from the second run of a target onward and answers the
question a re-run is asking: how many places were corrected, which rules
stopped firing, and which appeared. Set `XANALYZE_REPORT_ROOT` to put the
folders somewhere other than the Desktop.

```bash
# Full scan of a website (everything automatic)
xanalyze fullscan https://xformat.net

# The scheme is optional - this is the same run as above
xanalyze fullscan xformat.net

# Full scan of a local repository (no browser, code analysis only)
xanalyze fullscan ./my-project

# Desktop breakpoint only
xanalyze fullscan https://example.com --breakpoints desktop

# Desktop + mobile (skip tablet)
xanalyze fullscan https://example.com --breakpoints desktop,mobile

# With crawl depth
xanalyze fullscan https://example.com --depth 2 --max-pages 50

# Custom report paths
xanalyze fullscan https://example.com \
  --styled-report ./reports/site.pdf \
  --report ./reports/agent.md

# Ukrainian language reports
xanalyze fullscan https://example.com --language uk
```

**Options:**

| Option | Description |
|---|---|
| `target` | URL, directory, or `.html` file. A bare host (`example.com`) is read as a URL when there is no such file or directory |
| `--url` | Treat target as a URL even when it looks like a path |
| `--depth N` | Crawl depth for URLs (default: 0) |
| `--max-pages N` | Max pages to crawl (default: 30) |
| `--max-files N` | Max files to scan (default: 5000) |
| `--ext ...` | File extensions to scan |
| `--exclude PATTERN` | Gitignore-style exclude pattern (repeatable) |
| `--no-default-excludes` | Don't skip `node_modules/`, `dist/`, `.git/` etc. |
| `--detector DETECTOR` | AI pattern detector: `offline`, `embedding`, `hybrid`, `llm-judge` |
| `--scope SCOPE` | What to read: `content`, `technical`, `both` |
| `--no-typography` | Leave em dashes and curly quotes alone |
| `--breakpoints NAMES` | Responsive breakpoints: `all`, `desktop`, `tablet`, `mobile`, or comma-separated |
| `--styled-report PATH` | Branded PDF/HTML report path |
| `--report PATH` | Agent briefing path (.md or .json) |
| `--check` | Exit 1 when critical/serious issues found |
| `--language LANG` | Report language: `uk`, `it`, `en` |
| `--agent` | Run offline scan and output candidates for agent to judge (no API key) |
| `--no-browser` | Static fetch only: no browser rendering and no browser pass |

---

### `scan` - AI Patterns Detection

Scans files for AI-generated text patterns and non-keyboard characters without modifying them.

```bash
# Scan a directory
xanalyze scan ./src

# Scan with specific detector
xanalyze scan ./src --detector offline

# Scan only content (not comments)
xanalyze scan ./src --scope content

# JSON output for CI/CD
xanalyze scan ./src --json --check

# Incremental scan (only changed files)
xanalyze scan ./src --incremental

# Styled report
xanalyze scan ./src --styled-report report.pdf --language uk
```

**Options:**

| Option | Description |
|---|---|
| `paths` | Files or directories to scan |
| `--ext ...` | Extensions to scan (default: `.html .htm .xml .jsx .tsx .vue .svelte .js .ts .mjs .cjs`) |
| `--exclude PATTERN` | Extra gitignore-style exclude pattern |
| `--no-default-excludes` | Don't skip `node_modules/`, `dist/`, etc. |
| `--max-files N` | Maximum files to scan |
| `--detector DETECTOR` | Content detector (see [Detectors](#detectors)) |
| `--provider PROVIDER` | AI provider: `anthropic`, `xformat`, `claude-code` |
| `--no-unicode` | Skip non-keyboard character pass |
| `--scope SCOPE` | `content` (user-facing copy), `technical` (comments), `both` |
| `--categories CATS` | Comma-separated: `invisible,space,homoglyph,styled,typography` |
| `--no-typography` | Leave em dashes and curly quotes alone |
| `--no-ignore` | Report everything, including suppressed findings |
| `--json` | Machine-readable JSON output |
| `--check` | Exit 1 when anything is found (for hooks and CI) |
| `--incremental` | Re-read only files that changed since the last scan with the same settings. The cache is keyed on the file's modification time and size *and* on the detector, scope and categories, so changing any of those re-reads everything. A finding replayed from the cache cannot appear in `--styled-report`, which is built from live spans; the run says so when that happens |
| `--styled-report PATH` | Branded PDF/HTML report |
| `--language LANG` | Report language: `uk`, `it`, `en` |

---

### `audit` - Accessibility, SEO, Performance

Audits a URL, HTML file, or repository for accessibility, SEO, performance, and best practices issues.

```bash
# Audit a website
xanalyze audit https://example.com

# Audit with browser rendering (for SPA/React/Vue sites)
xanalyze audit https://example.com --browser

# Audit with responsive breakpoints
xanalyze audit https://example.com --browser --breakpoints all

# Desktop only
xanalyze audit https://example.com --browser --breakpoints desktop

# Audit a local HTML file
xanalyze audit ./page.html --browser

# Audit a repository (no browser)
xanalyze audit ./src

# Only accessibility category
xanalyze audit https://example.com --category accessibility

# Only SEO and performance
xanalyze audit https://example.com --category seo performance

# With AI pass (checks alt text, link text, headings)
xanalyze audit https://example.com --ai

# Auto-fix known issues
xanalyze audit ./src --fix

# JSON output
xanalyze audit https://example.com --json

# Agent briefing
xanalyze audit https://example.com --report briefing.md
```

**Options:**

| Option | Description |
|---|---|
| `target` | URL, directory, or `.html` file |
| `--url` | Treat target as URL even without scheme |
| `--depth N` | Crawl depth (default: 0) |
| `--max-pages N` | Max pages to crawl (default: 30) |
| `--max-files N` | Max files to scan (default: 5000) |
| `--render MODE` | Browser rendering: `never`, `auto`, `always` |
| `--exclude ...` | Exclude patterns |
| `--no-default-excludes` | Don't skip default excludes |
| `--category CATS` | Filter categories: `accessibility`, `performance`, `seo`, `best-practices` |
| `--language LANG` | Output language: `uk`, `it`, `en` |
| `--no-ignore` | Report everything |
| `--json` | JSON output |
| `--check` | Exit 1 on critical/serious issues |
| `--ai` | Run AI pass (costs tokens) |
| `--provider PROVIDER` | AI provider override |
| `--fix` | Write corrections back to files |
| `--report PATH` | Agent briefing (.md or .json) |
| `--browser` | Load pages in real browser |
| `--breakpoints NAMES` | Responsive widths: `all`, `desktop`, `tablet`, `mobile` |
| `--styled-report PATH` | Branded PDF/HTML report |

---

### `fix` - Apply Fixes

Rewrites non-keyboard characters in place, keeping `.bak` copies.

```bash
# Fix all files in a directory
xanalyze fix ./src

# Fix specific files
xanalyze fix ./src/index.html ./src/about.html
```

---

### `undo` - Revert Fixes

Puts files back the way they were before `fix` wrote to them.

```bash
# Undo fixes in a directory
xanalyze undo ./src

# Undo specific files
xanalyze undo ./src/index.html
```

---

### `cache` - Manage Scan Cache

```bash
# Show cache statistics
xanalyze cache stats

# Clear the cache
xanalyze cache clear

# Show cache file path
xanalyze cache path
```

---

### `compare` - Compare Detectors

Runs different detectors on the same files and compares results.

```bash
xanalyze compare ./src
```

---

### `ai` - AI-Backed Operations

Manage AI account and run AI-backed operations.

```bash
# Check account status
xanalyze ai status

# Sign in to xFormat subscription
xanalyze ai login --email user@example.com

# Sign out
xanalyze ai logout

# List connected apps
xanalyze ai apps

# Grant permission to an app
xanalyze ai grant my-app

# Revoke permission
xanalyze ai revoke my-app

# Rewrite a passage
xanalyze ai rewrite "The text to rewrite" --language uk

# Rewrite from stdin
echo "Some text" | xanalyze ai rewrite
```

---

### `clean` - Filter Text

Filters text from stdin to stdout, fixing non-keyboard characters.

```bash
# Pipe text through cleaner
echo "Some text with \u2018smart quotes\u2019" | xanalyze clean

# With language hint
cat article.txt | xanalyze clean --language uk
```

---

### `agent-scan` - Offline Scan for Agent

Runs offline scan and outputs candidate blocks as JSON for the agent to judge.

```bash
# Simple mode: candidates only
xanalyze agent-scan ./src --json

# Full mode: candidates + all blocks for independent agent analysis
xanalyze agent-scan ./src --full --json

# Custom threshold
xanalyze agent-scan ./src --threshold 0.3 --json
```

---

### `agent-judge` - Merge Agent Judgments

Combines offline scan with agent's LLM judgments into a final report.

```bash
# Simple merge: agent judged candidates
xanalyze agent-scan ./src --json | xanalyze agent-judge ./src --judgments -

# Hybrid merge: agent judged + found independently
xanalyze agent-scan ./src --full --json | xanalyze agent-judge ./src --judgments -
```

---

### `update` - Self-Update

Checks GitHub Releases for a newer version and replaces the CLI binary in place.

```bash
# Check and install update
xanalyze update
```

When running from source (`python cli.py`), prints the download link instead of replacing.

**Automatic update check:** Every CLI command checks for updates once a day (non-blocking, prints a one-line hint to stderr if a newer version exists). Suppress with `--no-update-check`.

---

### `uninstall` - Remove XAnalyze

Removes everything the app put on this machine: the `xanalyze` command on PATH, `/Applications/XAnalyze.app` when present, the config directory (`~/.config/xanalyze`, plus the pre-rename `~/.config/ai-content-scanner`) and saved keychain entries.

```bash
# Interactive: list what was found, ask before removing
xanalyze uninstall

# Remove without asking
xanalyze uninstall --yes

# Only list what would be removed
xanalyze uninstall --dry-run
```

Never touched: `.xanalyze/` run-history folders and `.xanalyze-ignore` files inside your repositories, `.bak` backups, and reports already written to your Desktop.

---

## Runs: pause, stop, continue

A full scan of a large site is a long job. A 192-page site took forty-six
minutes, most of it in the browser pass, and it used to be all-or-nothing: if
anything failed before the last line, the run wrote nothing at all and the
forty-six minutes were gone.

Every run now records each stage as it happens, so a run that stops keeps what
it computed and can be continued.

```bash
# What runs exist, and which can be continued
xanalyze runs

# Continue one from its first unfinished stage
xanalyze resume 2026-08-24-0930

# Ask a running scan to stop at its next stage boundary
xanalyze pause 2026-08-24-0930
```

```
run               status    stage     age       target
2026-08-24-1204   stopped   reports   4m ago    https://example.com
2026-08-24-0930   complete  -         3h ago    https://example.com
```

A stopped run exits with code **3** (not 2, which still means the invocation
was wrong) and prints a machine-readable block on stdout:

```json
{
  "incomplete": true,
  "run": "~/Desktop/XAnalyze/example.com/2026-08-24-1204",
  "state": {
    "stopped_in": "reports",
    "stopped_because": "styled report: [Errno 13] Permission denied",
    "completed_phases": ["scan", "crawl", "audit", "browser"],
    "remaining_phases": ["reports", "documents"],
    "artifacts": ["…/checkpoint-audit.json", "…/report.md"],
    "resume_with": "xanalyze resume …/2026-08-24-1204",
    "action_required": true
  }
}
```

That block is the point: an agent can read what stopped, fix it, and issue the
one command that continues. Finished stages are not recomputed - the crawl and
the audit are reloaded from the run folder, so a resume costs the stages that
did not finish and nothing else.

The GUI shows the same catalogue in its control column, with **Resume**,
**Pause** and **Open folder**. It walks the same run folders the CLI does
rather than keeping a list of its own, so the two can never disagree.

### The render watchdog

Printing the PDF is the one stage with no progress signal of its own, and it
used to be governed by a fixed 30-second ceiling. That ceiling killed a
158-page report which finishes in 108 seconds when left alone, and took the
whole run's output with it. Removing the ceiling removed the floor too: a
render process that died simply hung forever.

Neither measured whether the render was working, because elapsed time cannot.
What runs now stops on the absence of progress:

| evidence | what happens |
|---|---|
| the render process died | stops at once, with the exit status in the message |
| load progress moved | keeps going |
| the render process used more CPU than at the last check | keeps going |
| none of the above for 45 seconds | stops, naming the stage and the silence |

A render that is working is never interrupted, however long it takes. When the
render process cannot be watched at all, the message says so rather than
quietly becoming a fixed timer again.

### When the PDF still cannot be printed

Printing is the **last** step of a run. By the time it can fail, the findings
are complete and `report.md` is already written - so a failed PDF is a failed
conversion, not a failed run, and it no longer stops anything.

Instead the file you expected still appears, as a one-page stand-in that says
where the Markdown report is and carries the headline numbers, so it is a
usable summary rather than a page of apology. If even that will not print, the
same notice is written as `.html` beside it: a browser opens that, and nothing
opens a zero-byte PDF.

---

## Global Flags

| Flag | Description |
|---|---|
| `--no-update-check` | Skip the automatic daily version check |
| `--version` | Print version and exit |

`--no-update-check` is accepted before the subcommand and after it, at any
depth - `xanalyze --no-update-check scan .`, `xanalyze scan . --no-update-check`
and `xanalyze cache stats --no-update-check` all work. `--version` belongs to
the program, so it goes first.

---

## Detection Methods

### AI Pattern Detection

Combines multiple signals to detect AI-generated text:

#### Statistical Signals

1. **Burstiness (Uniformity)** — Human writing varies sentence length; AI text tends to be uniform
   - Measured as coefficient of variation of sentence lengths
   - Score: 0 (bursty/human) to 1 (uniform/AI-like)
   - Weight: 40%

2. **Lexical Diversity (Repetition)** — Low type-token ratio indicates formulaic phrasing
   - Measured over passages of 20+ words
   - Score: 0 (diverse/human) to 1 (repetitive/AI-like)
   - Weight: 35%

3. **Em Dash Density** — Overuse of em/en dashes as comma/parentheses replacement
   - Normal: ~0.3 dashes/100 words; Heavy: >2/100 words
   - Score: 0 (normal) to 1 (heavy)
   - Weight: 25%

#### Cliché Phrases

Extensive word lists per language (100+ English, 80+ Ukrainian, 80+ Italian):
- Padding/hedging openers ("it's important to note")
- Temporal openers ("in today's fast-paced world")
- Marketing buzzwords ("unlock the potential", "seamless experience")
- Product/interface copy ("comprehensive solution", "intuitive interface")
- Single overused words ("delve", "underscore", "pivotal", "realm")

#### Structural Patterns

Regex-based detection of AI-favorite constructions:
- "Not just X, but Y"
- "It's not about X, it's about Y"
- "No X. No Y. Just Z."
- "Whether you're X or Y"
- "Take your X to the next level"

#### Scoring Formula

```
base = weighted_average(uniformity, repetition, dashes)
remaining = 1 - base
for each cliché/structural match:
    remaining *= (1 - weight)
score = 1 - remaining
```

Statistical signals alone (without cliché/structural matches) are capped at 0.32 to prevent false positives on technical text.

#### What reaches the report

Below **0.33** a passage is `low` confidence and is not reported as an AI
pattern - the cap above puts every statistics-only finding there deliberately.
Character findings are different and are always reported whatever they score: a
wrong dash is a fact about the text, not a probability, so a low score there
means "a small defect", not "probably nothing".

This threshold used to be applied only when scanning a folder. Scanning a
website skipped it, so a crawl listed every passage the detector had ever
looked at: a real 192-page run reported **10,976 "AI text patterns"** of which
10,946 scored `low`, most of them 0.00. Both paths now apply the same rule, and
that run reports 30. The removed rows were also most of the reason its
artifacts came to 14 MB of JSON and a 117 MB PDF.

#### What this does not do

There is no dependency parser here, and the sentence-structure features named
in the 2026 detection literature (dependency-relation n-grams, clause
regularity, parataxis) are **not** implemented. They were prototyped and
rejected on evidence rather than skipped:

- Clause coordination looked decisive - model entries averaged 4.2 coordinating
  conjunctions per 100 words against a human median of 0.00, in all three
  languages. It was measuring length. The model half of the corpus runs to a
  median of 19 words and the human half to 9, because the human half is largely
  interface strings. Conditioned on entries of 25 words or more, the difference
  **reverses**: humans coordinate more than models do.
- Clause regularity and opening uniformity need three or more sentences, and
  almost no entry in the corpus has them - so they cannot be validated here at
  all.

`scripts/calibrate.py --confounds` prints the length distribution and what a
classifier that knows *only* the length scores, so the same mistake is visible
before the next signal is believed. On this corpus that ceiling is 57.9%
precision; the detector reaches 100%, which is what says it is detecting
writing rather than length.

---

### Non-keyboard Characters

Deterministic detection of characters no keyboard produces:

| Category | Examples | Score |
|---|---|---|
| `invisible` | Zero-width spaces, joiners, soft hyphens | 0.9 |
| `space` | Non-breaking spaces, en/em spaces | 0.7 |
| `homoglyph` | Cyrillic а (U+0430) instead of Latin a | 0.8 |
| `styled` | Mathematical bold/italic variants | 0.6 |
| `typography` | Curly quotes, em dashes (optional) | 0.3 |

Each anomaly provides:
- Exact codepoints (e.g., `U+200B`)
- Replacement text
- Category and description

---

### Accessibility Audit

52 rules across 4 categories: 28 accessibility, 8 SEO, 8 performance, 8 best
practices. Static rules run on parsed HTML; browser rules run on the rendered DOM.

#### Accessibility Rules (28)

| Rule ID | Severity | WCAG | Description |
|---|---|---|---|
| `image-alt` | Critical | 1.1.1 | Images must have `alt` attribute |
| `image-alt-filename` | Serious | 1.1.1 | `alt` must not be a filename |
| `control-name` | Critical | 4.1.2, 2.4.4 | Interactive elements need accessible names |
| `link-text-vague` | Moderate | 2.4.4 | Avoid "click here", "read more" |
| `html-lang` | Serious | 3.1.1 | `<html>` must have `lang` attribute |
| `document-title` | Serious | 2.4.2 | Page must have `<title>` |
| `heading-order` | Moderate | 1.3.1, 2.4.6 | No skipped heading levels |
| `page-has-h1` | Moderate | 1.3.1 | Exactly one `<h1>` |
| `tabindex-positive` | Serious | 2.4.3 | No positive `tabindex` |
| `duplicate-id` | Moderate | 4.1.1 | No duplicate `id` attributes |
| `aria-reference-broken` | Serious | 1.3.1, 4.1.2 | ARIA references must resolve |
| `button-type` | Minor | — | Buttons in forms need `type` |
| `media-captions` | Serious | 1.2.2 | Video/audio need captions |
| `media-autoplay` | Serious | 1.4.2 | No autoplay without controls |
| `table-headers` | Serious | 1.3.1 | Data tables need `<th>` |
| `table-scope` | Moderate | 1.3.1 | `<th>` should have `scope` |
| `viewport-zoom` | Serious | 1.4.4 | Don't block zoom |
| `viewport-fixed-width` | Moderate | 1.4.10 | No fixed `width:` on a container - it forces sideways scrolling on a phone |
| `viewport-tiny-font` | Serious | 1.4.4 | No font size below the readable floor |
| `viewport-touch-target` | Minor | 2.5.8 | Tap targets large enough to hit |
| `contrast-inline` | Serious | 1.4.3 | Inline color contrast (needs browser) |
| `landmark-regions` | Moderate | 1.3.1, 2.4.1 | Page needs `<main>` landmark |
| `skip-link` | Moderate | 2.4.1 | First focusable element should skip to content |
| `form-error-message` | Serious | 3.3.1 | Invalid fields need error descriptions |
| `hreflang-links` | Minor | 3.1.2 | Multilingual sites need hreflang |
| `breadcrumb-markup` | Minor | 1.3.1, 2.4.8 | Breadcrumbs should use `<nav>` |
| `language-change` | Minor | 3.1.2 | Inline foreign text needs `lang` attribute |
| `abbreviation-expansion` | Minor | 3.1.4 | Abbreviations should use `<abbr>` with `title` |

#### Browser-Only Rules (states pass)

| Rule ID | Severity | Description |
|---|---|---|
| `keyboard-trap` | Serious | Focus cannot leave element |
| `focus-not-visible` | Serious | Focus indicator invisible |
| `focus-order-mismatch` | Moderate | Tab order doesn't match visual order |
| `hover-only-content` | Moderate | Content only visible on hover |
| `no-skip-link` | Moderate | No skip-to-content link |
| `focus-outside-viewport` | Moderate | Focused element off-screen |

---

### SEO Audit

| Rule ID | Severity | Description |
|---|---|---|
| `seo-title-length` | Moderate | Title 15-60 characters |
| `seo-meta-description` | Moderate | Meta description 70-160 characters |
| `seo-canonical` | Moderate | Exactly one canonical link |
| `seo-noindex` | Serious | No accidental noindex/nofollow |
| `seo-open-graph` | Minor | og:title, og:description, og:image |
| `seo-structured-data` | Minor | JSON-LD or microdata present |
| `seo-image-dimensions` | Minor | Images need width/height |
| `seo-empty-link` | Moderate | Links need text content |

---

### Performance Audit

| Rule ID | Severity | Description |
|---|---|---|
| `perf-render-blocking` | Serious | Max 3 blocking resources in `<head>` |
| `perf-third-party-sync` | Serious | No synchronous third-party scripts |
| `perf-large-inline` | Moderate | Inline style/script < 20KB |
| `perf-image-loading` | Minor | Images past 3rd should be lazy-loaded |
| `perf-font-display` | Moderate | Fonts need `font-display: swap` |
| `perf-preconnect` | Minor | Preconnect to third-party origins |
| `perf-layout-shift` | Moderate | Lazy images need dimensions |
| `image-modern-format` | Minor | Prefer WebP/AVIF over PNG/JPG |

---

### Best Practices

| Rule ID | Severity | Description |
|---|---|---|
| `bp-mixed-content` | Serious | No HTTP resources on HTTPS pages |
| `bp-target-blank` | Moderate | `target="_blank"` needs `rel="noopener"` |
| `bp-charset` | Moderate | Declare `charset="utf-8"` |
| `bp-doctype` | Moderate | Include `<!DOCTYPE html>` |
| `bp-inline-handlers` | Minor | No inline event handlers |
| `bp-password-field` | Moderate | Password fields need `autocomplete` |
| `bp-deprecated-html` | Minor | No deprecated elements (`<center>`, `<font>`) |
| `bp-ai-markup-artifact` | Minor | No AI vendor classes (`claude-*`, `data-gpt-*`) |

---

### Browser Pass

When `--browser` is used (automatic for `fullscan` on URLs):

1. **Page Loading** — Real Chromium via QtWebEngine
2. **Settle Wait** — 2500ms after load for SPA hydration
3. **axe-core** — Industry-standard accessibility engine (~27% coverage alone)
4. **HTML_CodeSniffer** — Additional accessibility checks (~20% coverage alone)
5. **State Pass** — Focus, keyboard traps, hover-only content
6. **Measurements** — FCP, load time, transfer size, DOM size
7. **Deduplication** — Same findings from multiple engines collapsed into one row

**Responsive Breakpoints:**

| Name | Width | Height |
|---|---|---|
| `desktop` | 1440px | 900px |
| `tablet` | 834px | 1112px |
| `mobile` | 390px | 844px |

A finding seen at multiple widths becomes one row recording where it was seen. A finding at one width says "only at mobile" — useful for responsive-specific issues.

---

## Detectors

| Detector | Type | Cost | Languages | Description |
|---|---|---|---|---|
| `offline` | Heuristic | Free | uk, it, en | Clichés + structural patterns + non-keyboard characters |
| `embedding` | Semantic | Free | Any | Sentence-transformers similarity |
| `claude-llm-judge` | LLM | Paid | Any | Anthropic Claude API |
| `xformat-llm-judge` | LLM | Paid | Any | xFormat subscription |
| `claude-code-llm-judge` | LLM | Paid | Any | Claude Code API |
| `agent-llm-judge` | LLM | Free | uk, it, en | Agent-as-judge (offline fallback) |
| `hybrid` | Mixed | Paid | uk, it, en | Offline first, then LLM extends |
| `none` | — | Free | — | Skip content detection |

---

## Reports

### One problem, however many pages carry it

A crawl of thirty pages that share a header finds that header's every fault
thirty times. That is thirty places and one problem, and the reports say so:
each distinct problem is listed once, with every place it was found under it.
Nothing is dropped - a fix has to visit each of those places - and both
numbers are reported, because they answer different questions:

```
| critical | serious | moderate | minor | total | distinct problems |
|---|---|---|---|---|---|
| 0 | 3 | 64 | 3 | 70 | 14 |
```

Two findings count as one problem when the rule, the severity and the
offending markup all match. Two different images missing `alt` stay two
problems; the same shared logo on five pages is one.

The complete per-document listing is still there for anything that parses
rather than reads: write the briefing with a `.json` suffix and it is under
`files`.

### How the report is laid out

Three things decide whether a long report is readable, and all three were got
wrong first:

**Page breaks follow what must stay together, not what looks tidy.**
`break-inside: avoid` on every finding card is the obvious rule and the wrong
one: a tall card that did not fit in the remainder of a page moved to the next
page whole, and the space it left stayed blank. On a report of 120 findings
that cost **9% of its pages** to white space. What actually has to hold is
narrower - a heading is never the last thing on a page, a stray line never
opens or closes one, and small blocks (a field, a table row, a chart bar) stay
whole. Cards and tables may break.

**One table, not four.** The category counts, the AI-pattern confidence bands
and the character tallies used to be three tables in three sections, separated
by the findings - so a reader asking "what kind of thing did this find" had to
hold three places at once and never saw them side by side. They answer one
question and now sit in one answer, under **What was found**, with a column
saying which pass each row came from.

**The index of what was examined is context, not content.** A 192-page crawl
printed 192 numbered lines in body type before the first finding - about five
printed pages of index. It is now a table in 8pt, sorted so the pages carrying
the most problems come first, cut off after 40 rows with the full count still
stated, and placed *after* the findings. Same run: **two pages instead of
five**.

The overview also opens with two bar charts - by severity and by category -
because counts in a table are exact and shapeless, and a reader wants to see
where the weight is before reading a number. They are plain CSS, no script and
no image, because `printToPdf` is the consumer and anything else sometimes
prints blank.

### Styled Report (PDF/HTML)

Branded, print-ready report for humans:
- Summary with severity counts
- One card per distinct problem, with every place it appears
- Code snippets with fixes
- Responsive breakpoint indicators

```bash
xanalyze fullscan https://example.com --styled-report report.pdf
```

### Agent Briefing (Markdown/JSON)

Structured briefing for coding agents:
- Statistics and counts
- The grouped problem list, worst and most widespread first
- The per-document file map (`.json` form)
- Fix suggestions
- Change tracking against the previous run of the same target

```bash
xanalyze fullscan https://example.com --report briefing.md
```

### Comparison With The Previous Run

Every run is recorded per target in `~/.xanalyze/history/`, keyed on what was
scanned and which analysis ran - so a second run of the same target is
compared with the first whatever the report is called. `fullscan` also writes
the comparison as its own document, `changes.md`, in the run folder:

```
| | previous | now | change |
|---|---|---|---|
| findings | 70 | 67 | down 3 |

**3 place(s) corrected**, 0 new one(s) appeared.

| rule | previous | now | change |
|---|---|---|---|
| `image-alt` | 5 | 2 | down 3 |
```

*Findings* also moves when the crawl reaches a different number of pages,
which is not progress. *Places corrected* and the per-rule table are the
numbers that track work done: a rule fires in fewer places only when
something was actually fixed.

### JSON Output

Machine-readable output for CI/CD pipelines:

```bash
xanalyze fullscan https://example.com --json
```

Output structure:
```json
{
  "target": "https://example.com",
  "is_url": true,
  "language": "en",
  "scan": {
    "findings": [...],
    "counts": {"total": 5, "style": 3, "characters": 2}
  },
  "audit": {
    "counts": {"critical": 0, "serious": 2, "moderate": 5, "minor": 3},
    "issues": [...]
  },
  "summary": {
    "total_findings": 15,
    "ai_patterns": 3,
    "characters": 2,
    "accessibility": 5,
    "seo": 3,
    "performance": 1,
    "best_practices": 1
  }
}
```

`audit.issues` is the complete list, one entry per place. The grouped view
lives in the briefing (`--report`), under `problems`, next to
`summary.distinct_problems`.

---

## For AI Agents

This section describes how to use xanalyze from an AI agent (Claude, ChatGPT, Copilot, etc.) to analyze websites and codebases.

### How Users Ask

Users ask agents in natural language. Here's how each request maps to a command:

#### fullscan — Full Analysis

| User says | Agent runs |
|---|---|
| "Scan my website for accessibility issues" | `xanalyze fullscan https://example.com` |
| "Check https://xformat.net for problems" | `xanalyze fullscan https://xformat.net` |
| "Analyze my codebase for AI-generated text" | `xanalyze fullscan ./my-project` |
| "Run a full audit on this site" | `xanalyze fullscan https://example.com` |
| "Is my site accessible?" | `xanalyze fullscan https://example.com` |
| "Check my landing page for SEO" | `xanalyze fullscan https://example.com` |
| "Scan my React app" | `xanalyze fullscan https://myapp.com` |
| "Audit this Next.js site" | `xanalyze fullscan https://mysite.com` |
| "Check mobile responsiveness" | `xanalyze fullscan https://example.com --breakpoints mobile` |
| "Desktop only check" | `xanalyze fullscan https://example.com --breakpoints desktop` |
| "Scan in Ukrainian" | `xanalyze fullscan https://example.com --language uk` |

#### audit — Accessibility/SEO/Performance

| User says | Agent runs |
|---|---|
| "Check accessibility of this page" | `xanalyze audit https://example.com --browser` |
| "Audit SEO on my site" | `xanalyze audit https://example.com --category seo` |
| "Check performance issues" | `xanalyze audit https://example.com --category performance` |
| "Is my site WCAG compliant?" | `xanalyze audit https://example.com --browser` |
| "Check this HTML file" | `xanalyze audit ./page.html --browser` |
| "Audit my repo for a11y" | `xanalyze audit ./src` |
| "Fix accessibility issues" | `xanalyze audit ./src --fix` |
| "Check with AI analysis" | `xanalyze audit https://example.com --ai` |

#### scan — AI Pattern Detection

| User says | Agent runs |
|---|---|
| "Check if my text sounds AI-generated" | `xanalyze scan ./src` |
| "Scan for clichés in my copy" | `xanalyze scan ./src --detector offline` |
| "Check comments for AI patterns" | `xanalyze scan ./src --scope technical` |
| "Scan only user-facing text" | `xanalyze scan ./src --scope content` |
| "Find non-keyboard characters" | `xanalyze scan ./src` |
| "Check for zero-width spaces" | `xanalyze scan ./src --categories invisible` |
| "Scan with AI detector" | `xanalyze scan ./src --detector llm-judge` |
| "Incremental scan (changed files only)" | `xanalyze scan ./src --incremental` |

#### fix — Apply Fixes

| User says | Agent runs |
|---|---|
| "Fix non-keyboard characters" | `xanalyze fix ./src` |
| "Clean up smart quotes" | `xanalyze fix ./src` |
| "Replace zero-width spaces" | `xanalyze fix ./src` |
| "Fix typography in my files" | `xanalyze fix ./src` |

#### undo — Revert Fixes

| User says | Agent runs |
|---|---|
| "Undo the fixes" | `xanalyze undo ./src` |
| "Revert changes" | `xanalyze undo ./src` |
| "Put files back" | `xanalyze undo ./src` |

#### compare — Compare Detectors

| User says | Agent runs |
|---|---|
| "Compare different detectors" | `xanalyze compare ./src` |
| "Which detector is best?" | `xanalyze compare ./src` |
| "Test offline vs AI detector" | `xanalyze compare ./src` |

#### cache — Manage Cache

| User says | Agent runs |
|---|---|
| "Show cache stats" | `xanalyze cache stats` |
| "Clear the cache" | `xanalyze cache clear` |
| "Where is the cache?" | `xanalyze cache path` |

#### ai — AI Operations

| User says | Agent runs |
|---|---|
| "Check my AI account status" | `xanalyze ai status` |
| "Sign in to xFormat" | `xanalyze ai login` |
| "Sign out" | `xanalyze ai logout` |
| "Rewrite this text" | `xanalyze ai rewrite "text"` |
| "Make this sound human" | `xanalyze ai rewrite "text" --language en` |

#### clean — Filter Text

| User says | Agent runs |
|---|---|
| "Clean this text" | `echo "text" \| xanalyze clean` |
| "Fix characters in stdin" | `cat file.txt \| xanalyze clean` |

### Agent-as-Judge Mode

The agent itself acts as the LLM judge (no API key needed). Two modes:

**Simple — validate offline findings:**
```bash
# Step 1: offline scan → candidates
xanalyze agent-scan ./src --json > candidates.json

# Step 2: agent judges candidates, pipes back
echo '[{"block_id":"...","score":0.8,"reason":"AI cliché"}]' | \
  xanalyze agent-judge ./src --judgments -
```

**Full — hybrid analysis (agent reads everything):**
```bash
# Step 1: offline scan + all blocks for agent
xanalyze agent-scan ./src --full --json > scan.json

# Step 2: agent judges candidates AND reads blocks independently

# Step 3: merge with hybrid logic
cat agent_output.json | xanalyze agent-judge ./src --judgments -
```

**Fullscan with agent:**
```bash
xanalyze fullscan ./repo --agent --json
# Outputs: audit + offline candidates + detection rules + instructions
```

**LLM Judge Options:**

| Detector | Command | API Key |
|---|---|---|
| Agent (validate) | `xanalyze agent-scan ./src --json` | Not needed |
| Agent (full hybrid) | `xanalyze agent-scan ./src --full --json` | Not needed |
| Claude API | `xanalyze scan ./src --detector claude-llm-judge` | `ANTHROPIC_API_KEY` |
| xFormat | `xanalyze scan ./src --detector xformat-llm-judge` | xFormat login |
| Claude Code | `xanalyze scan ./src --detector claude-code-llm-judge` | Claude Code session |
| Hybrid | `xanalyze scan ./src --detector hybrid` | Optional |

### Command Reference with User Requests

#### `fullscan` — "Scan my site"

```bash
# User: "Scan my website for all issues"
xanalyze fullscan https://example.com

# User: "Check my site, desktop only"
xanalyze fullscan https://example.com --breakpoints desktop

# User: "Scan with 2 levels deep"
xanalyze fullscan https://example.com --depth 2

# User: "Scan my codebase"
xanalyze fullscan ./my-project

# User: "Generate PDF report"
xanalyze fullscan https://example.com --styled-report report.pdf

# User: "Scan in Italian"
xanalyze fullscan https://example.com --language it
```

**Output:** JSON to stdout, PDF + MD reports to `~/Desktop`

#### `audit` — "Check accessibility"

```bash
# User: "Is my site accessible?"
xanalyze audit https://example.com --browser

# User: "Check SEO only"
xanalyze audit https://example.com --category seo --json

# User: "Audit this HTML file"
xanalyze audit ./page.html --browser

# User: "Fix what you can"
xanalyze audit ./src --fix

# User: "Check with AI analysis"
xanalyze audit https://example.com --ai --json
```

#### `scan` — "Check for AI text"

```bash
# User: "Does my copy sound AI-generated?"
xanalyze scan ./src --json

# User: "Check only comments"
xanalyze scan ./src --scope technical --json

# User: "Use AI detector"
xanalyze scan ./src --detector llm-judge --json

# User: "Check for zero-width characters"
xanalyze scan ./src --categories invisible --json
```

#### `fix` — "Fix the issues"

```bash
# User: "Fix non-keyboard characters"
xanalyze fix ./src

# User: "Clean up my files"
xanalyze fix ./src
```

#### `undo` — "Revert changes"

```bash
# User: "Undo the fixes"
xanalyze undo ./src
```

### Workflow Examples

#### Example 1: "Audit my website and tell me what to fix"

```bash
# Step 1: Full scan
xanalyze fullscan https://example.com --json > scan.json

# Step 2: Show critical issues
cat scan.json | jq '.audit.issues[] | select(.severity == "critical")'

# Step 3: Show fix suggestions
cat scan.json | jq '.audit.issues[] | {rule, snippet, fix_snippet}'
```

#### Example 2: "Check my codebase for AI patterns and fix them"

```bash
# Step 1: Scan
xanalyze scan ./src --json > scan.json

# Step 2: Show findings
cat scan.json | jq '.findings[] | {score, explanation}'

# Step 3: Fix characters
xanalyze fix ./src

# Step 4: Verify
xanalyze scan ./src --json | jq '.counts'
```

#### Example 3: "Is my React app accessible on mobile?"

```bash
# Step 1: Full scan with mobile breakpoint
xanalyze fullscan https://myapp.com --breakpoints mobile --json

# Step 2: Show mobile-specific issues
# (issues with "breakpoints": ["mobile"] in details)
```

#### Example 4: "Check SEO and generate a report"

```bash
# Step 1: Audit SEO
xanalyze audit https://example.com --category seo --json

# Step 2: Generate styled report
xanalyze audit https://example.com --category seo --styled-report seo-report.pdf
```

### JSON Output Structure

```json
{
  "target": "https://example.com",
  "is_url": true,
  "language": "en",
  "scan": {
    "findings": [
      {
        "source": "style",
        "score": 0.85,
        "confidence": "high",
        "explanation": "cliché: unlock the potential; style-uniformity=0.72",
        "details": {
          "signals": {"uniformity": 0.72, "repetition": 0.45, "dashes": 0.3},
          "cliches": ["unlock the potential"],
          "language": "en"
        }
      }
    ],
    "counts": {"total": 5, "style": 3, "characters": 2}
  },
  "audit": {
    "counts": {"critical": 0, "serious": 2, "moderate": 5, "minor": 3},
    "issues": [
      {
        "rule": "image-alt",
        "category": "accessibility",
        "severity": "critical",
        "selector": "html > body > main > img",
        "snippet": "<img src=\"hero.jpg\">",
        "fix_snippet": "<img src=\"hero.jpg\" alt=\"\">"
      }
    ]
  },
  "summary": {
    "total_findings": 15,
    "ai_patterns": 3,
    "characters": 2,
    "accessibility": 5,
    "seo": 3,
    "performance": 1,
    "best_practices": 1
  }
}
```

### Severity Levels

| Level | Meaning | User says | Action |
|---|---|---|---|
| `critical` | Blocks users completely | "This is broken" | Fix immediately |
| `serious` | Content lost or unusable | "This doesn't work" | Fix soon |
| `moderate` | Harder to use | "This is annoying" | Fix when possible |
| `minor` | Smell, may be intentional | "This could be better" | Consider fixing |

### Exit Codes

| Code | Meaning |
|---|---|
| 0 | Success, no critical/serious issues (with `--check`) |
| 1 | Critical/serious issues found (with `--check`) |
| 2 | Error (invalid arguments, file not found, etc.) |

### Tips for Agents

1. **Always use `--json`** for machine-readable output
2. **Use `--check`** in CI/CD to fail on critical issues
3. **Use `fullscan`** for comprehensive analysis
4. **Use `audit --browser`** for SPA/React/Vue sites
5. **Use `scan`** for quick AI pattern check
6. **Use `fix`** to auto-correct non-keyboard characters
7. **Parse `summary`** for quick overview
8. **Parse `audit.issues`** for detailed findings
9. **Check `fix_snippet`** for suggested corrections
10. **Use `--language`** for localized reports

---

## GUI

The desktop app answers the same questions as the CLI, with the controls in a
column on the left and the results beside them.

**The controls column**

1. **Source** — website URL, repository folder, or single HTML file. A bare
   host is accepted here too
2. **Check** — accessibility, AI patterns, or both (both by default)
3. **Method** — offline, embedding, AI, or offline + AI. The AI entries appear
   only when there is an account or a key to pay for them
4. **Scope** (folders) — the copy that ships, comments and docstrings, or both
5. **Depth** (sites) — how far the crawl follows links
6. **Account** — who pays for an AI pass, and whether anyone is signed in

**The results**

7. **Preview** — the rendered page, or the source file, with the finding
   outlined or its line highlighted. Pinnable to desktop, tablet or mobile
   width, so a finding reported at one width can be looked at that width
8. **Findings list** — severity badge, one row per distinct problem. A problem
   found in several files says how many, rather than repeating itself
9. **Detail** — what was found, why it matters, how to fix it, the element,
   the ready replacement, and every place the same problem appears
10. **Actions** — fix the characters, generate a replacement list, rewrite in
    place, write an audit correction to disk, undo it, export the report

The window folds one column at a time as it narrows: the detail column first
(it reappears inline under the clicked row), then the preview.

---

## TUI (Terminal Interface)

When you run `xanalyze` with no arguments, an interactive terminal interface launches:

```bash
xanalyze          # launch TUI
python cli.py     # same, from source
```

The TUI provides:
- **Scan** — configure and run AI pattern detection
- **Audit** — configure and run accessibility/SEO/performance audit
- **Full Scan** — combined analysis in one run
- **Reports** — every recorded run; Enter opens that run's report
- **Settings** — read and change the configuration
- **Update** — check for and install a new version
- **Uninstall** — remove XAnalyze from this machine

Every run happens on a worker thread, so the interface keeps answering while a
crawl grinds, and its progress appears on the status line. When it finishes,
the result is shown in the interface - a summary, the documents that were
written, and the full log - not left in the terminal underneath.

Navigate with arrow keys or number shortcuts (1-7); `Tab` also moves between
controls. The footer lists the keys the current screen accepts. `Esc` goes
back, `q` quits.

---

## Configuration

### Settings File

Location: `~/.config/xanalyze/settings.json`

```json
{
  "ui_language": "uk",
  "llm_provider": "xformat",
  "max_pages": 30,
  "unicode_categories": ["invisible", "space", "homoglyph"],
  "unicode_check_enabled": true
}
```

### Ignore File

Create `.xanalyze-ignore` in project root (gitignore syntax):

```
# Ignore vendored code
vendor/
third_party/

# Ignore generated files
*.min.js
*.min.css
```

### Suppressions

Suppress specific findings via settings or `.xanalyze-ignore`:
- By CSS selector (exclude regions)
- By rule ID (disable rules)

---

## Uninstall

### CLI

```bash
rm ~/bin/xanalyze
```

### GUI

```bash
rm -rf /Applications/XAnalyze.app
```

### Config and cache

```bash
rm -rf ~/.config/xanalyze
rm -rf ~/.xanalyze
```

---

## Requirements

- Python 3.9+
- PySide6 (for GUI)
- sentence-transformers (for embedding detector)
- QtWebEngine (for browser pass)

---

## License

MIT
