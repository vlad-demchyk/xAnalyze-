# XAnalyze

Desktop and headless analyzer for AI-written text patterns, non-keyboard characters, and website or repository quality.

[Українська](README_ua.md) | [Italiano](README_it.md)

## Contents

- [What it does](#what-it-does)
- [Quick start](#quick-start)
- [Usage](#usage)
- [CLI commands](#cli-commands)
- [Templates it understands](#templates-it-understands)
- [Stacks it recognises](#stacks-it-recognises)
- [Analysis](#analysis)
- [Reports and runs](#reports-and-runs)
- [Interfaces](#interfaces)
- [Configuration](#configuration)
- [Limits](#limits)
- [Requirements](#requirements)
- [License](#license)

## What it does

XAnalyze scans a website, HTML file, repository, or source directory and reports exact locations rather than only aggregate scores.

### Scan types

- **AI pattern detection**: heuristic, embedding, hybrid, or model-judged signals in user-facing copy.
- **Character checks**: zero-width characters, homoglyphs, unusual spaces, styled letters, and typography characters.
- **Website audit**: accessibility, SEO, performance, security, and best-practice rules.
- **Browser audit**: Chromium rendering for client-side applications and responsive checks at 1440, 834, and 390 px.
- **Repository facts**: tracked or unignored `.env` files, assistant-related commits or configuration, and blame for findings.
- **Media provenance**: IPTC/XMP metadata and optional C2PA manifests. This is file evidence, not a verdict about pixels.
- **Run history**: pause, resume, compare, and inspect the documents produced by each run.

### Combined scan

`fullscan` combines text, character, and website checks. A URL is analyzed as rendered content when browser rendering is enabled. A local repository is scanned statically unless `--devserver` is supplied.

### Detected stacks and templates

The scanner identifies a stack from marker files or served markup and excludes generated or vendored code when ownership is clear. The two lists are checked against the code by the suite, so they live in [Templates it understands](#templates-it-understands) and [Stacks it recognises](#stacks-it-recognises) rather than being repeated here.

## Quick start

### macOS GUI

```bash
curl -L -o XAnalyze.app.zip https://github.com/vlad-demchyk/xAnalyze-/releases/latest/download/XAnalyze.app.zip
unzip XAnalyze.app.zip
mv XAnalyze.app /Applications/
```

### macOS/Linux CLI

```bash
curl -L -o xanalyze-cli.tar.gz https://github.com/vlad-demchyk/xAnalyze-/releases/latest/download/xanalyze-cli-macos-arm64.tar.gz
tar -xzf xanalyze-cli.tar.gz
echo 'export PATH="$PWD/xanalyze:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

### From source

```bash
git clone https://github.com/vlad-demchyk/xAnalyze-.git
cd xAnalyze-
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python main.py                         # GUI
python cli.py fullscan https://example.com
```

## Usage

```bash
xanalyze                                      # launch the TUI
xanalyze fullscan https://example.com         # combined website scan
xanalyze scan ./src                           # AI patterns and characters
xanalyze audit https://example.com --browser  # website audit
xanalyze fix ./src                            # apply character fixes
xanalyze runs                                 # list and resume runs
xanalyze update                               # check for an update
xanalyze --version
```

The application checks for updates once per day. Use `--no-update-check` to disable it.

## CLI commands

### `fullscan`

Runs AI pattern, character, accessibility, SEO, performance, and best-practice checks.

```bash
xanalyze fullscan https://xformat.net
xanalyze fullscan ./my-project
xanalyze fullscan https://example.com --depth 2 --max-pages 50
xanalyze fullscan https://example.com --breakpoints desktop,mobile
xanalyze fullscan https://example.com --detector hybrid --language uk
xanalyze fullscan https://example.com --styled-report ./reports/site.pdf --report ./reports/agent.md
```

For URLs and HTML files, browser rendering is automatic unless `--no-browser` is used. For a local application, `--devserver` detects and starts a Node, Django, or Rails server before scanning it.

| Option | Purpose |
|---|---|
| `target` | URL, directory, or HTML file |
| `--url` | Treat the target as a URL |
| `--depth N` | URL crawl depth, default `0` |
| `--max-pages N` | Maximum URL pages, default `30` |
| `--max-files N` | Maximum local files, default `5000` |
| `--ext ...` | File extensions to scan |
| `--exclude PATTERN` | Additional gitignore-style exclusion |
| `--no-default-excludes` | Include default excluded directories |
| `--repo PATH` | Match rendered findings to source files |
| `--devserver` | Start the repository's development server |
| `--start-command CMD` | Override the detected server command |
| `--dev-server-port N` | Port for Django or Rails servers |
| `--yes` | Install missing server dependencies without prompting |
| `--detector NAME` | `offline`, `embedding`, `hybrid`, or `llm-judge` |
| `--model NAME` | Model used by the AI pass |
| `--effort LEVEL` | AI effort: `low`, `medium`, or `high` |
| `--no-judgment-cache` | Do not reuse cached model judgments |
| `--scope NAME` | `content`, `technical`, or `both` |
| `--no-typography` | Ignore em dashes and curly quotes |
| `--breakpoints NAMES` | `all`, `desktop`, `tablet`, `mobile`, or a list |
| `--styled-report PATH` | PDF or HTML report |
| `--report PATH` | Markdown or JSON agent briefing |
| `--check` | Exit with status 1 when serious findings exist |
| `--language LANG` | `uk`, `it`, or `en` |
| `--agent` | Produce offline candidates for agent judging |
| `--no-browser` | Disable browser rendering |

### `scan`

Scans files without modifying them.

```bash
xanalyze scan ./src
xanalyze scan ./src --detector offline --scope content
xanalyze scan ./src --json --check
xanalyze scan ./src --incremental
xanalyze scan ./src --styled-report report.pdf --language uk
```

Useful options include `--ext`, `--exclude`, `--max-files`, `--detector`, `--provider`, `--no-unicode`, `--scope`, `--categories`, `--no-typography`, `--no-ignore`, `--json`, `--check`, `--incremental`, `--styled-report`, and `--language`.

`--categories` accepts `invisible`, `space`, `homoglyph`, `styled`, and `typography`.

### `audit`

Audits a URL, HTML file, or repository.

```bash
xanalyze audit https://example.com
xanalyze audit https://example.com --browser --breakpoints all
xanalyze audit ./page.html --browser
xanalyze audit ./src --category accessibility
xanalyze audit https://example.com --category seo performance
xanalyze audit ./src --fix
xanalyze audit https://example.com --json --report briefing.md
```

Important options: `--depth`, `--max-pages`, `--max-files`, `--render`, `--exclude`, `--category`, `--language`, `--no-ignore`, `--json`, `--check`, `--ai`, `--provider`, `--fix`, `--report`, `--browser`, `--breakpoints`, and `--styled-report`.

### `fix` and `undo`

`fix` applies exact non-keyboard-character corrections and keeps `.bak` copies. `undo` restores those copies.

```bash
xanalyze fix ./src
xanalyze fix ./src/index.html ./src/about.html
xanalyze undo ./src
xanalyze undo ./src/index.html
```

### `runs`, `resume`, `cache`, and `compare`

```bash
xanalyze runs
xanalyze resume 2026-08-24-1331
xanalyze cache stats
xanalyze cache clear
xanalyze cache path
xanalyze compare ./src
```

Runs store their state and documents so an interrupted scan can continue.

### `logs`

```bash
xanalyze logs
xanalyze logs --level warning
xanalyze logs --contains crawl
xanalyze logs --run RUN_ID
xanalyze logs --json
xanalyze logs path
xanalyze logs clean
xanalyze logs clear
```

Logs are JSON Lines under `$XDG_STATE_HOME/xanalyze/logs` or `~/.local/state/xanalyze/logs`. Set `XANALYZE_LOG_DIR` to move them and `XANALYZE_LOG_LEVEL=debug` for per-page records. Files older than 14 days are removed and the remaining logs are limited to 20 MB.

### `ai`

```bash
xanalyze ai status
xanalyze ai login
xanalyze ai logout
xanalyze ai apps
xanalyze ai grant APP_ID
xanalyze ai revoke APP_ID
xanalyze ai rewrite "Text to rewrite"
```

AI passes can use an xFormat subscription, an Anthropic key, or a Claude Code session, depending on local settings.

### `clean`

```bash
echo "text" | xanalyze clean
echo "text" | xanalyze clean --language uk
```

### `agent-scan` and `agent-judge`

These commands let an agent judge candidate passages without an API key in XAnalyze.

```bash
xanalyze agent-scan ./src --json > passages.json
xanalyze agent-judge ./src --judgments verdicts.json
```

`agent-scan` emits passage IDs, text, and offline signals. `agent-judge` applies the agent's verdicts while keeping XAnalyze's scoring, grouping, and reports.

Each passage carries a `language` field, and it is `null` when the passage is too short to read. That is an answer, not a missing value: a two-word button is not English merely because nothing else was detectable, and an agent told otherwise judges it against the wrong expectations.

### `update` and `uninstall`

```bash
xanalyze update
xanalyze uninstall
```

The interactive uninstall lists the files it will remove. Use the non-interactive option only when the removal is intentional.

## Templates it understands

Fourteen template languages have a **pair** of fixtures in
`tests/fixtures/frameworks`: the same component written the way its framework
says to write it, and written wrong. The correct half must produce no findings
and the broken half must produce the right ones, so this list is a measured
claim rather than an intention:

`alpine`, `angular`, `blade`, `django`, `erb`, `handlebars`, `liquid`, `php`, `razor`, `react`, `svelte`, `thymeleaf`, `twig`, `vue`

That is what the scan is *checked* against. Markup in anything not on this list
is still read - the parser does not refuse it - but nothing has proved that a
correct file in it comes back clean, and a false finding there would not be
caught by the suite.

## Stacks it recognises

A project is identified from its own marker files, and what it turns out to be
decides what is treated as vendored rather than written here:

`angular`, `astro`, `beehiiv`, `carrd`, `craft`, `django`, `docusaurus`, `dotnet`, `drupal`, `eleventy`, `ember`, `flutter`, `gatsby`, `ghost`, `hugo`, `jekyll`, `joomla`, `laravel`, `magento`, `nextjs`, `nuxt`, `qwik`, `rails`, `remix`, `shopify`, `silverstripe`, `spfx`, `spring`, `squarespace`, `statamic`, `storybook`, `sveltekit`, `symfony`, `typo3`, `vite`, `wagtail`, `webflow`, `wix`, `wordpress`

Signatures are scored, not counted: each carries a confidence and a platform is
named only when the matches add up to 100, so a string that could be there for
another reason has to be corroborated.

## Analysis

### AI pattern detection

The offline detector combines statistical signals, repeated structure, cliché phrases, and language-aware rules. Embedding and model-backed detectors add a second judgment. Results include the passage, location, score, explanation, and confidence.

The agent-judge workflow is useful when the agent should make the final language judgment while XAnalyze handles extraction and reporting.

### Non-keyboard characters

The character pass reports exact code points and locations, including zero-width spaces, soft hyphens, homoglyphs, unusual spaces, styled Unicode letters, em dashes, and curly quotes. `fix` removes or replaces only the selected spans. It does not reformat files.

Use `--scope content` for user-facing copy, `--scope technical` for comments and docstrings, or `--scope both` for both.

### Website audit

How many rules each category actually has, which is a claim the suite checks:

`accessibility` (29), `best-practices` (8), `performance` (8), `security` (10), `seo` (8)

- **Accessibility**: names, labels, headings, language, keyboard access, media alternatives, and related rules.
- **SEO**: titles, descriptions, canonicals, headings, links, robots directives, and structured page metadata.
- **Performance**: image dimensions and formats, resource hints, compression, caching, and render-related issues.
- **Security**: insecure forms, unsafe frames, missing script integrity, exposed keys, and password handling.
- **Best practices**: browser and repository hygiene, including assistant provenance facts.

Static analysis reads source files. Browser analysis can inspect rendered DOM, client-side content, responsive states, and response headers. Use `--repo` when a rendered URL also has a local checkout and findings should point to source files.

### Certainty and filters

Findings are labelled `exact` or `needs-browser`. Use `--confidence exact` when only facts settled by markup should remain. `--category`, `--scope`, `--breakpoints`, and `--no-typography` are views over the same scan, not changes to the underlying evidence.

### Media provenance and repository facts

Media provenance reads IPTC/XMP fields, generator prompt blocks, and C2PA manifests when the optional reader is installed. A manifest may be declared, invalid, or signed by an untrusted credential; these outcomes are kept separate.

Repository facts include tracked `.env` files, unignored `.env` files, assistant-named commits, committed assistant configuration, and findings last touched by assistant-authored commits. These are reported as provenance, not as defects in using an assistant.

## Reports and runs

### Output files

Each target gets a folder under `~/Desktop/XAnalyze/` by default. Set `XANALYZE_REPORT_ROOT` to change the location.

```text
XAnalyze/example.com/2026-08-24-0930/
  report.md       grouped agent briefing
  report.pdf      human-readable report
  timings.md      stage timings
  changes.md      comparison with the previous run
  state.md        resumable state
  state.json      machine-readable state
```

### Styled report

```bash
xanalyze fullscan https://example.com --styled-report report.pdf
```

The PDF or HTML report contains severity and category counts, grouped problems, locations, snippets, fixes, and responsive indicators.

### Agent briefing and JSON

```bash
xanalyze fullscan https://example.com --report briefing.md
xanalyze fullscan https://example.com --json > run.json
```

The briefing groups identical problems and keeps the per-document map. JSON keeps every finding and is suitable for CI/CD. `--language uk|it|en` controls report language.

### Grouping and comparison

The report lists a repeated problem once and nests all locations under it. Findings are grouped by rule, severity, and normalized offending markup. Dynamic framework identifiers are normalized only in identifier attributes, so genuinely different elements remain separate.

Subsequent runs of the same target are compared using `changes.md`. A lower finding count can also mean that fewer pages were crawled, so use the corrected-place and per-rule counts when measuring progress.

## Interfaces

### GUI

The desktop application provides setup controls for target, analysis type, detector, scope, crawl depth, breakpoints, language, and account. Results show the finding list, source or rendered preview, details, fixes, replacement review, and report export.

Mechanical corrections are selected by default. Model drafts require review. Decisions such as photographic alternative text are never presented as automatic fixes.

### TUI

Run `xanalyze` without arguments to open the terminal interface. It provides Scan, Audit, Full Scan, Reports, Settings, Update, and Uninstall. Runs execute in a worker thread, and the interface supports arrow keys, number shortcuts, `Tab`, `Esc`, and `q`.

## Configuration

### Settings file

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

### Ignore file

Create `.xanalyze-ignore` in the project root using gitignore syntax:

```text
vendor/
third_party/
*.min.js
*.min.css
```

Suppressions can also be grouped by rule, selector, fingerprint, phrase, or path:

```text
[rules]
meta-viewport

[selectors]
.ads

[fingerprints]
083bea550659aadb
```

Comments and blank lines are preserved when the application updates this file.

## Limits

- AI-text detection is corpus-dependent. It is not proof of authorship, and model judgments are not deterministic.
- **The offline wording pass is weak in Italian, and the tool now says so during a run.** On the held-out corpus it finds 36% of known AI passages in Italian against 55% in English and 71% in Ukrainian, while the embedding detector finds 100%, 85% and 86%. A scan whose page reads as Italian prints a warning naming the better detector, and repeats it in the JSON as `scan.detector_note`. The wording pass is still the default because it is instant, needs no `torch`, names the phrase it matched, and can replace it offline - and it catches four held-out passages the embedding detector misses.
- **Text detection covers Ukrainian, Italian and English only.** A passage in any other language is named as such and the wording and embedding passes report nothing for it, rather than scoring it against lists and a reference set that do not speak it. Measured on 257 paragraphs in German, French, Spanish, Polish and Russian: 249 are read as unsupported. The character, typography and audit checks are language-independent and keep running, and a model-judged detector is not restricted this way.
- A repository scan cannot see content created only at render time. Use a URL or `--devserver` for page behavior.
- A single breakpoint cannot describe responsive behavior. Use `--breakpoints all` when mobile or tablet matters.
- Typography checks can flag intentional punctuation. Disable them with `--no-typography` or Settings.
- `--scope technical` measures character and technical content signals, not marketing style.
- C2PA details require the optional `c2pa-python` and `cryptography` packages.
- On 16-color terminals, some severity colors collapse, but severity labels remain textual.

## Requirements

- Python 3.14+
- PySide6 for the GUI
- sentence-transformers for embedding detection
- QtWebEngine for browser rendering
- `c2pa-python` and `cryptography` for optional C2PA reading

## License

MIT
