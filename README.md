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
- **One binary, three surfaces**: the packaged app offers on first launch to put the `xanalyze` command on your `PATH`, so the CLI and the TUI need no second download.

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

The app and the command line are one binary. On its first launch the app
offers, once, to link it as `xanalyze` in `~/.local/bin` so the CLI and the
TUI work in a terminal; declining is remembered, and the same install lives
in Settings -> Command line.

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
| `--breakpoints NAMES` | `all`, `desktop`, `tablet`, `mobile`, `reflow` (320 px), or a list. Without it the browser pass runs at one width, 1440x900 — the same size as `desktop` |
| `--site-controls` | Fetch robots.txt and same-origin declared sitemaps as an opt-in external audit |
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

`accessibility` (29), `best-practices` (8), `geo` (2), `performance` (8), `security` (10), `seo` (8)

- **Accessibility**: names, labels, headings, language, keyboard access, media alternatives, and related rules.
- **SEO**: titles, descriptions, canonicals, headings, links, robots directives, and structured page metadata.
- **GEO readiness**: machine-readable article type, author, and publication date. These are advisory signals, not an AI-answer ranking prediction.
- **Performance**: image dimensions and formats, resource hints, compression, caching, and render-related issues.
- **Security**: insecure forms, unsafe frames, missing script integrity, exposed keys, and password handling.
- **Best practices**: browser and repository hygiene, including assistant provenance facts.

Static analysis reads source files. Browser analysis can inspect rendered DOM, client-side content, responsive states, and response headers. Use `--repo` when a rendered URL also has a local checkout and findings should point to source files.

**The state pass** runs in the browser and checks the page in the state a person puts it in: the focus indicator, keyboard traps, focus order, hover-only content, an open modal that lets focus stay behind it, and the form journey - a field with no accessible name after scripts have run, a field named only by its placeholder, a value the browser itself rejects with nothing announcing it, and error text on screen that no field refers to. It reads and never acts: nothing is typed, clicked or submitted, because on a real site each of those fires the page's own handlers. Filling a field to see what the form does with a wrong value is therefore out of scope, and so is INP, which needs real input to measure.

### Certainty and filters

Findings are labelled `exact`, `needs-browser` or `advisory`. `exact` means the markup settles the question, `advisory` means nothing will settle it and a person decides — an editorial call, which is what the GEO signals are.

**The undecided are not listed.** `needs-browser` is an engine saying it could not tell: "this element is placed on a background image", "absolutely positioned, the background colour cannot be determined". Measured on one page of python.org with a real browser, that was **312 of 348** contrast findings, and the whole run went from 497 findings to **182** once they left. A report two thirds made of "we do not know" is not a list anybody works through, so a run says how many it left out and `--unsettled` brings them back. `--confidence exact` is the stricter view still: it also drops the advisory ones.

`--category`, `--scope`, `--breakpoints`, and `--no-typography` are views over the same scan, not changes to the underlying evidence.

### Media provenance and repository facts

Media provenance reads IPTC/XMP fields, generator prompt blocks, and C2PA manifests when the optional reader is installed. A manifest may be declared, invalid, or signed by an untrusted credential; these outcomes are kept separate.

On a crawled site **every image the pages refer to is read**, not a sample. Only the header is fetched — an HTTP range request for the first 512 KB, which is where those fields and the pixel dimensions live and where the C2PA marker search stops — so a 6 MB photograph costs 512 KB and nothing is kept in memory after it is read. Images whose bytes are identical to one already read are recognised by hash, analysed once, and reported once with every place they appear. The report states how many addresses were found, how many were read, how many were repeats, and what could not be fetched: an image nobody read has not come back clean, it has not come back.

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

It is painted in XAnalyze's own palette, so one severity is one colour here, in the window and in the TUI. Two colour systems carry meaning in it, and nothing else does:

* **Elements are coloured by role.** Quoted markup is inked tag by tag - landmark, interactive control, grouping wrapper, media, running text, document metadata - with a legend printed once, listing only the roles the report actually contains. Six roles rather than one colour per tag name: a hue that means "this is a control" is learnable, a hash of a tag name is not.
* **Red and green are the direction of a diff, and nothing else.** The markup as found and the markup as it should be are marked `−` and `+` and inked accordingly, and the "how to fix" prose carries the same green, because it is the same claim in words.

Each finding also states its technical identity on one line - rule id, engine, element, how many engines agreed, how many places it was found in - so a row can be looked up, suppressed or compared against a previous run from the printed page alone. Nothing in the document is abbreviated with an ellipsis: an engine's sentence is printed whole, and so is a ranked rule name.

A finding that is not settled says so, in both documents. `advisory` and `needs-browser` carry a badge in the styled report and a `certainty` field in the agent briefing, and each carries the sentence saying what it is *not* - "nothing will check this for you", "open it in a browser". `exact` deliberately gets neither: a document where most rows carry a certainty note teaches the reader to skip the note. Both facts reached the window and the terminal from the beginning and neither reached the two artefacts a person hands to somebody else.

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

The setup screen's fifth card, **What to show**, carries the run parameters that used to be CLI-only: the six audit categories (including `geo`), the certainty floor (`--confidence`), and `--site-controls`. The scope selector sits with the repository controls, and typography is a character category in Settings.

Category and certainty are a **view over one finished pass**, exactly as `--category` and `--confidence` are: the rules are cheap and share one parse, so narrowing repaints the list and the summary without re-auditing anything, and widening brings every finding straight back. The exported report is written through the same view, so what is on screen and what is in the file cannot disagree. When a filter hides everything, the empty screen says so and gives the unfiltered count rather than reporting the page as clean. `--site-controls` is different in kind - it fetches robots.txt and the sitemaps declared in it - so it is a run choice, off by default and shown only for a site.

The first card, **What we are looking at**, states what a chosen folder turned out to be. A project is identified from its own marker files, and what it is decides what is treated as vendored: the window now applies those exclusions as `xanalyze audit` always has - the same WordPress folder used to produce hundreds of findings in vendored core from the window and none from the CLI. It is never applied silently. The card names the stack, counts the paths it will skip, carries the marker file that proved each one, and offers **Scan those as well** in one click, because a profile is evidence about ownership rather than a certainty.

The same card carries **These documents are** - the window's `--medium`. It is read off the markup by default, which is right nearly always; set it by hand for an email deliverable that carries neither an Outlook namespace nor a merge tag. On `email` the browser-only checks (canonical, Open Graph, structured data, skip link, landmarks, WebP) are skipped, and the accessibility ones are not: `image-alt`, `control-name`, `table-headers`, contrast and language are as real in a mail client as in a browser.

The TUI's Audit screen carries the same three, plus every breakpoint the audit knows on both the Audit and Full Scan screens.

Mechanical corrections are selected by default. Model drafts require review. Decisions such as photographic alternative text are never presented as automatic fixes.

### TUI

Run `xanalyze` without arguments to open the terminal interface. It provides Scan, Audit, Full Scan, Reports, Settings, Account, Update, Uninstall, and Logs. Runs execute in a worker thread, and the interface supports arrow keys, number shortcuts, `Tab`, `Esc`, and `q`.

**Account** signs in to the xFormat subscription without leaving the terminal. Settings has always offered `xformat` as the provider and the TUI had nowhere to sign in to it, so the setting could only be acted on from the window or from `xanalyze ai login`. The password is never stored: it is exchanged for a token that goes to the OS keychain, and the field is cleared before the call is made. The other two providers own their credentials elsewhere and the screen says so rather than offering a form that cannot work.

Table cells wrap rather than being cut. The log detail and the run target used to be sliced by the screen itself, which removed the `key=value` that explained the line and the **domain** that identified the run.

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
