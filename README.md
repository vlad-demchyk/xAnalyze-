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
  - [serve](#serve---local-http-server)
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
- [GUI](#gui)
- [Configuration](#configuration)
- [Uninstall](#uninstall)
- [Requirements](#requirements)
- [License](#license)

---

## Features

- **AI Pattern Detection** — heuristic (clichés, structural patterns, burstiness) and embedding-based (sentence-transformers)
- **Non-keyboard Characters** — zero-width spaces, curly quotes, em dashes, homoglyphs
- **Accessibility Audit** — WCAG rules, SEO, performance, best practices (49 rules)
- **Full Scan** — combined AI patterns + accessibility in one command with automatic browser rendering
- **Styled Reports** — branded PDF/HTML for humans
- **Agent Briefings** — markdown/JSON for coding agents
- **CLI + GUI** — one binary, two interfaces
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

## CLI Commands

### `fullscan` - Full Scan

The primary command for comprehensive analysis. Combines AI pattern detection, accessibility audit, SEO, performance, and best practices in one run.

**Automatic behavior for URLs and HTML files:**
- Browser rendering enabled (handles React, Vue, Next.js, etc.)
- Responsive breakpoints: desktop (1440px), tablet (834px), mobile (390px)
- JSON output for agent consumption
- Styled PDF report saved to `~/Desktop`
- Agent briefing (Markdown) saved to `~/Desktop`

```bash
# Full scan of a website (everything automatic)
xanalyze fullscan https://xformat.net

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
| `target` | URL, directory, or `.html` file |
| `--url` | Treat target as URL even without scheme |
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
| `--agent` | Start agent judge server (no API key needed) |
| `--agent-port PORT` | Port for agent judge server (default: 8765) |

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
| `--incremental` | Only scan files changed since last scan |
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

### `serve` - Local HTTP Server

Starts a local HTTP server for agent-as-judge mode.

```bash
# Start server on default port (8765)
xanalyze serve

# Custom port
xanalyze serve --port 9000

# Bind to all interfaces
xanalyze serve --host 0.0.0.0
```

---

## Agent Integration

**For LLM agents (Claude, ChatGPT, Cursor, etc.):**

Just ask: "Run a full scan with AI on https://example.com"

The agent will:
1. Run `xanalyze fullscan https://example.com --agent`
2. Get the JSON results
3. Analyze findings
4. Generate a report

**No API key needed** — the agent itself acts as the judge.

**How it works:**
1. `--agent` flag starts a local HTTP server on port 8765
2. Agent sends text to `POST /judge` endpoint
3. Server returns a score (0-1) indicating AI likelihood
4. Server stops automatically after scan completes

**Endpoints:**
- `POST /judge` — Judge text for AI patterns
- `GET /health` — Health check
- `GET /detectors` — List available detectors

**Example curl:**
```bash
curl -X POST http://localhost:8765/judge \
  -H 'Content-Type: application/json' \
  -d '{"text": "It is worth noting that this comprehensive solution..."}'
```

**LLM Judge Options:**

| Detector | Command | API Key |
|---|---|---|
| Agent (default) | `xanalyze fullscan URL --agent` | Not needed |
| Claude API | `xanalyze fullscan URL --detector claude-llm-judge` | `ANTHROPIC_API_KEY` |
| xFormat | `xanalyze fullscan URL --detector xformat-llm-judge` | xFormat login |
| Claude Code | `xanalyze fullscan URL --detector claude-code-llm-judge` | Claude Code session |
| Hybrid | `xanalyze fullscan URL --detector hybrid` | Optional |

**Full examples:**
```bash
# Agent as judge (no API key)
xanalyze fullscan https://example.com --agent

# Claude API judge
xanalyze fullscan https://example.com --detector claude-llm-judge

# xFormat subscription judge
xanalyze fullscan https://example.com --detector xformat-llm-judge

# Claude Code session judge
xanalyze fullscan https://example.com --detector claude-code-llm-judge

# Hybrid: offline + judge
xanalyze fullscan https://example.com --detector hybrid

# Agent with custom port
xanalyze fullscan https://example.com --agent --agent-port 9000
```

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

47 rules across 4 categories. Static rules run on parsed HTML; browser rules run on rendered DOM.

#### Accessibility Rules (25)

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
| `hybrid` | Mixed | Paid | uk, it, en | Offline first, then LLM extends |
| `none` | — | Free | — | Skip content detection |

---

## Reports

### Styled Report (PDF/HTML)

Branded, print-ready report for humans:
- Summary with severity counts
- Findings grouped by category
- Code snippets with fixes
- Responsive breakpoint indicators

```bash
xanalyze fullscan https://example.com --styled-report report.pdf
```

### Agent Briefing (Markdown/JSON)

Structured briefing for coding agents:
- Statistics and counts
- File-by-file findings
- Fix suggestions
- Change tracking

```bash
xanalyze fullscan https://example.com --report briefing.md
```

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

---

## For AI Agents

This section describes how to use xanalyze from an AI agent (Claude, ChatGPT, Copilot, etc.) to analyze websites and codebases.

### Quick Reference

```bash
# Full scan of a website (everything automatic)
xanalyze fullscan https://example.com

# Full scan of a repository
xanalyze fullscan ./my-project

# Quick accessibility check
xanalyze audit https://example.com --browser --json

# Scan code for AI patterns
xanalyze scan ./src --json

# Fix non-keyboard characters
xanalyze fix ./src
```

### Common Tasks

#### 1. Analyze a Website (Full Scan)

```bash
xanalyze fullscan https://example.com
```

**What it does:**
- Crawls the website (with browser rendering for SPA)
- Runs accessibility audit (49 rules)
- Runs SEO audit
- Runs performance audit
- Checks for AI-generated text patterns
- Checks for non-keyboard characters
- Generates JSON output + PDF report + agent briefing

**Output:** JSON to stdout, reports saved to `~/Desktop`

#### 2. Analyze a Codebase

```bash
xanalyze fullscan ./my-project
```

**What it does:**
- Scans all markup files (HTML, JSX, TSX, Vue, Svelte, etc.)
- Scans locale files (JSON, YAML)
- Scans backend files (Python, PHP, Ruby, Go, Java, C#)
- Checks for AI-generated text in copy and comments
- Checks for non-keyboard characters
- Runs accessibility audit on HTML files

#### 3. Quick Accessibility Check

```bash
xanalyze audit https://example.com --browser --json
```

**What it does:**
- Loads page in real browser (handles SPA)
- Runs axe-core + HTML_CodeSniffer
- Checks keyboard focus, contrast, ARIA
- Returns JSON with all issues

#### 4. Check Specific Category

```bash
# Only accessibility issues
xanalyze audit https://example.com --category accessibility --json

# Only SEO issues
xanalyze audit https://example.com --category seo --json

# Only performance issues
xanalyze audit https://example.com --category performance --json
```

#### 5. Scan for AI Patterns Only

```bash
xanalyze scan ./src --json
```

**What it does:**
- Scans files for cliché phrases, structural patterns
- Checks for non-keyboard characters (zero-width, homoglyphs)
- Returns findings with scores and explanations

#### 6. Fix Issues Automatically

```bash
# Fix non-keyboard characters
xanalyze fix ./src

# Auto-fix accessibility issues (where possible)
xanalyze audit ./src --fix
```

#### 7. Compare Detectors

```bash
xanalyze compare ./src --json
```

**What it does:**
- Runs multiple detectors on same files
- Compares results
- Shows which detector finds what

### Agent Workflow Examples

#### Example 1: Audit and Fix a Website

```bash
# Step 1: Full scan
xanalyze fullscan https://example.com --json > scan.json

# Step 2: Review findings
cat scan.json | jq '.audit.counts'

# Step 3: Get detailed issues
cat scan.json | jq '.audit.issues[] | select(.severity == "critical" or .severity == "serious")'

# Step 4: Generate fix suggestions
xanalyze audit https://example.com --browser --report fixes.md
```

#### Example 2: Scan and Clean a Codebase

```bash
# Step 1: Scan for issues
xanalyze scan ./src --json > scan.json

# Step 2: Check what was found
cat scan.json | jq '.counts'

# Step 3: Fix non-keyboard characters
xanalyze fix ./src

# Step 4: Verify fixes
xanalyze scan ./src --json | jq '.counts'
```

#### Example 3: CI/CD Integration

```bash
# In CI pipeline - fail on critical issues
xanalyze fullscan https://staging.example.com --check --json

# Exit code 0 = no critical/serious issues
# Exit code 1 = critical/serious issues found
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

| Level | Meaning | Action |
|---|---|---|
| `critical` | Blocks users completely | Fix immediately |
| `serious` | Content lost or unusable | Fix soon |
| `moderate` | Harder to use | Fix when possible |
| `minor` | Smell, may be intentional | Consider fixing |

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

The desktop app provides the same functionality with a visual interface:

1. **Source Selection** — Website URL, repository folder, or single HTML file
2. **Reader Selection** — Code (static) or Browser (rendered)
3. **Check Selection** — Accessibility, AI patterns, or both
4. **Method Selection** — Offline, AI, or hybrid
5. **Real-time Progress** — Live status updates
6. **Findings Panel** — Clickable list with severity badges
7. **Detail Panel** — Full description, code snippet, fix suggestion
8. **Preview Panel** — Page preview with highlighted issues

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
