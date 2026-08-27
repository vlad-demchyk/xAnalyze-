# XAnalyze

Desktop and headless analyzer: AI-generated text detection, non-keyboard characters, and full website/repository accessibility audit.

[Українська](README_ua.md) | [Italiano](README_it.md)

---

## Why XAnalyze exists

**What it is for.** One run answers two questions about a site or a repository
you are responsible for: *was this text written by a model*, and *does this
page actually work for the people who have to use it* — accessibility, SEO,
performance, best practice. Both answers point at a place (file, line, URL),
not at a score, and most of them arrive with the correction attached.

**The problems it solves**

1. **"Is this copy AI-written?" answered somewhere you can act on.** A web
   detector gives a percentage about a paste. XAnalyze gives the file and the
   line, the signals that fired, the confidence, and — if you ask — the commit
   that last touched that line.
2. **Characters nobody can see.** Zero-width spaces, soft hyphens, homoglyph
   letters and curly punctuation break search, diffs, price strings and
   `grep`. They are found exactly and removed exactly, one character at a
   time, never by reformatting the file.
3. **An audit that stays a PDF.** 52 rules do not stop at naming the defect:
   where the correction follows from the markup, it can be written back to the
   file. Where it does not — alternative text for a photograph, the page's
   language — it is kept out of the automatic path on purpose, because valid
   markup that lies makes the next audit call the page clean.
4. **A "clean" result that is a lie.** A run says what it actually read: how
   many pages, what it could not open, where a limit cut the crawl. Nothing
   found is only good news when you know what was looked at.
5. **Doing it more than once.** A run is an object, not a command: it can be
   paused, continued, listed, compared with the previous run, and it leaves a
   folder of documents rather than terminal scrollback.
6. **Guessing about provenance.** Images and repositories are read for what
   they *say about themselves* — IPTC/XMP fields, generator prompt blocks, a
   signed C2PA manifest, commits authored by an assistant, committed assistant
   configuration — which is a record, not an opinion about pixels.

**Who it is for**

- **Editors and content owners** who need to know what in their site was
  written by a model, and where.
- **Developers and agencies** who answer for someone else's site and have to
  show the state of it, fix what is mechanical, and keep a record of both.
- **Accessibility and QA people**, including anyone working to the European
  accessibility rules, who need findings tied to elements and a report to hand
  over.
- **Teams that cannot send their content anywhere.** Everything except the
  optional model pass runs on your machine; there is no account to create and
  nothing is uploaded.
- **AI coding agents**, which get their own offline scan format and a way to
  hand judgments back (`agent-scan`, `agent-judge`).

---

## Table of Contents

- [Why XAnalyze exists](#why-xanalyze-exists)
- [Features](#features)
- [Limits](#limits)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [CLI Commands](#cli-commands)
  - [fullscan](#fullscan---full-scan)
  - [The four shapes worth remembering](#the-four-shapes-worth-remembering)
  - [Scanning a site you also have the code for](#scanning-a-site-you-also-have-the-code-for)
  - [No live site, but a checkout](#no-live-site-but-a-checkout---fullscan-can-run-it)
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
- [Media Provenance](#media-provenance)
- [Repository Facts](#repository-facts)
- [Reports](#reports)
- [For AI Agents](#for-ai-agents)
  - [Agent-as-Judge Mode](#agent-as-judge-mode)
  - [Reading the output](#reading-the-output)
- [GUI](#gui)
- [TUI (Terminal Interface)](#tui-terminal-interface)
- [Configuration](#configuration)
- [Uninstall](#uninstall)
- [Requirements](#requirements)
- [License](#license)

---

## Features

- **AI pattern detection** — heuristic signals (clichés, structure, burstiness)
  and an embedding pass; both judged against a small corpus, see [Limits](#limits)
- **Non-keyboard characters** — zero-width spaces, homoglyphs, odd spaces,
  styled letters, curly punctuation. Exact, and exactly removable
- **Accessibility, SEO, performance, best practice** — 52 rules; where the
  correction follows from the markup it can be written back
- **Responsive audit** — the same page at 1440 / 834 / 390, merged into one
  list that says which widths saw each finding
- **Browser rendering** — real Chromium for client-side rendered sites
- **Full scan** — both passes in one run, with the browser pass automatic
- **Dev server** — `fullscan --devserver` starts a repo's own Node/Django/Rails
  server and scans the render. Opt-in: one may already be running
- **Media provenance** — what an image says about itself: IPTC/XMP fields,
  generator prompt blocks, a signed C2PA manifest when a reader is installed.
  Never a verdict on the pixels
- **Repository facts** — commits naming an assistant as author, committed
  assistant configuration, a `.env` no ignore rule covers
- **Blame on a finding** — the commit that last touched the line
- **Runs are objects** — pause, continue, list, compare with the previous run
- **Documents** — a report to read (PDF/HTML), a briefing for an agent
  (Markdown/JSON), and the timings, one folder per run
- **Three interfaces, three languages** — CLI, window and terminal interface
  over one core, all of them in Ukrainian, Italian or English

---

**The scan knows what stack it is reading.** A project is identified from its
own marker files - `wp-config.php`, `artisan`, `next.config.mjs`,
`manage.py`, `config/package-solution.json` - and what it turns out to be
decides what is vendored rather than written: WordPress core, Composer
packages, `.svelte-kit/`, SPFx's compiled `lib/`. Detection is evidence, never
a guess: the report names the file that proved it, and a project nothing
matches scans exactly as before. Files whose header says a machine wrote them
(`DO NOT EDIT`, `@generated`) are skipped in any stack.

**A rule that fires on nearly everything is flagged, not trusted.** Findings
spread evenly across every page of a run are the shape of a broken
measurement rather than a broken site, and the run says so next to the count.

## Certainty, and choosing a floor

Every finding says how sure it is. `exact` means the markup settles the
question - there is an `alt` or there is not. `needs-browser` means something
outside the file decides it: a stylesheet, a rendered page, or a vendored
engine reporting that it *could not determine* the answer.

    xanalyze audit ./src --confidence exact

keeps the first kind and drops the second. Both are produced either way and
both are labelled; the floor is a view over one pass, like `--category`, and
never a decision made for the reader. On ten pages of a real site this took
335 findings to 227 without losing a single fact.

## What is checked

`accessibility` (29), `best-practices` (8), `performance` (8), `security` (10), `seo` (8)

`security` reads the markup for what it hands away: a cross-origin frame with
no `sandbox`, a frame granted the camera, a form posting to `http://`, a
third-party script with no `integrity`, a key written into an attribute, a
password field the browser is told to remember. Every one is `exact` by
construction - a security finding that turns out to be wrong costs more trust
than any other kind, so nothing that has to infer is in there.

**Three passes beside the rules, and all three read bytes the run had already
paid for.** The response headers arrived with every page and were being
discarded - `Content-Type` was kept and the rest died with the response - so
a site served with no `Content-Security-Policy`, no `Strict-Transport-Security`,
no compression and no `Cache-Control` was audited as if how it is served were
not part of it. The crawl holds every page at once, which is the only place
the same `<title>`, `description` or `canonical` repeated across pages is
visible: valid markup on each page, a broken site taken together. And the
media pass already downloads each image's header for its provenance fields,
where the pixel dimensions also live, so an image stored at 6000 pixels and
displayed at 600 is a measurement rather than a guess.

None of the three costs a request that was not already made.

## Templates it understands

Fourteen template languages have a **pair** of fixtures in
`tests/fixtures/frameworks`: the same component written the way its framework
says to write it, and written wrong. The correct half must produce no
findings and the broken half must produce the right ones, so this list is a
measured claim rather than an intention:

`alpine`, `angular`, `blade`, `django`, `erb`, `handlebars`, `liquid`, `php`, `razor`, `react`, `svelte`, `thymeleaf`, `twig`, `vue`

That is what the scan is *checked* against. Markup in anything not on this
list is still read - the parser does not refuse it - but nothing has proved
that a correct file in it comes back clean, and a false finding there would
not be caught by the suite.

## Stacks it recognises

A project is identified from its own marker files, and what it turns out to
be decides what is vendored rather than written:

`angular`, `astro`, `beehiiv`, `carrd`, `craft`, `django`, `docusaurus`, `dotnet`, `drupal`, `eleventy`, `ember`, `flutter`, `gatsby`, `ghost`, `hugo`, `jekyll`, `joomla`, `laravel`, `magento`, `nextjs`, `nuxt`, `qwik`, `rails`, `remix`, `shopify`, `silverstripe`, `spfx`, `spring`, `squarespace`, `statamic`, `storybook`, `sveltekit`, `symfony`, `typo3`, `vite`, `wagtail`, `webflow`, `wix`, `wordpress`

**Signatures are scored, not counted.** The method is Wappalyzer's, because
that fingerprint set has been maintained against the whole web for a decade
and this one has not: every signature carries a confidence, and a platform is
named only when the ones that matched add up to 100. A literal only one
platform emits scores 100 alone; something that could be there for another
reason - the string `SPFx`, a Ghost theme class - scores below and has to be
corroborated. Where the markup carries a version it is read out, because
"WordPress" is a guess someone has to verify and "WordPress 7.1" is a fact
they can act on.

Checked against 13 live sites, 10 platforms and 3 hand-built controls:
13 correct, 0 missed, 0 false. Two of those started as failures and both were
worth having - `gohugo.io` writes `<meta name=generator ...>` with no quotes
around the attribute name, which HTML has always allowed and this was blind
to; and `ghost.org` came back as Hugo, which turned out to be true.

**Two places the evidence lives.** A checkout is identified by its marker
files; a crawled site by what it serves - a `<meta name="generator">`, an
asset host a platform owns, a runtime payload it injects. Until now only the
first existed, so a site scan knew nothing about what it was reading while
the same project on disk knew everything. 26 platforms are recognised from
served markup, 6 of which exist only there (`wix`, `squarespace`, `webflow`, `beehiiv`, `carrd`, `typo3`) - they have no checkout to
exclude anything from, and what knowing them buys is different: a finding
inside the shell a platform generates belongs to the platform, not to whoever
writes the content.

Detection is evidence, never a guess: the report names the file that proved
it, ambiguous markers must be corroborated (`config.toml` counts as Hugo only
beside `layouts/` or `archetypes/`), and a project nothing matches scans
exactly as it did before.

**And it changes what the report asks of you.** Every finding on a crawled site
is checked against the code the detected platform injects itself, and one that
sits inside it is named as the platform's: `20 of these are in markup wix
generates: not the site owner's to edit`. Nothing is suppressed - the finding
is real, the script does block rendering - but a person triaging now sees which
part of the list they can act on. Measured: 20 of 565 findings on `wix.com`
(React and core-js polyfill bundles from `static.parastorage.com`), 8 of 179 on
`squarespace.com`, 1 of 12 on `wordpress.org/news`, 1 of 65 on a Shopify store,
and 0 on a hand-built control.

The test for membership is not "did the author type this" but **can the site
owner change it at all**, and measuring is what emptied most of the table. A
CDN is not a platform: `cdn.shopify.com` was in it until a run attributed 20
findings to Shopify, most of them `<video>` elements with no captions whose only
Shopify-ness was where the poster image was hosted - a merchant's own uploads
sit on that host too. A build is the author's: `/_next/static/`, `/_nuxt/` and
`/_app/immutable/` are their own code compiled, so no framework or generator
owns anything. A theme is chosen and editable, so `wp-content/themes/` stays
with the owner while `wp-content/plugins/`, which they cannot edit without
forking it, does not.

## Limits

What the tool is weak at, measured rather than guessed. The tracking for each
lives in the project's `Problems.md`.

**The corpus behind the AI-text detection is small and biased.** Its positive
half was written by models and runs longer than its human half, which is
largely interface strings. The precision figures below are precision *on that
corpus*, not in the wild, and `scripts/calibrate.py --confounds` prints what a
classifier that knows only the length would score, so the difference stays
visible.

**Italian is the weakest of the three languages**, though less so than the
headline number said. Measured recall is now 61.1% Italian against 65.6%
English and 60.0% Ukrainian, up from 27.8% after the Italian phrase list was
brought level with the English one; on the held-out half, the only honest
number, it is 36.4% against 55.0% and 71.4%. Read by length, the weakness was
never uniform: at 25 words or more Italian was already the *best* of the three
(83.3%), and the whole deficit sat in entries of one sentence, where it scored
nothing at all. On one live Italian site the offline detector found nothing
where a model judge found six passages. If Italian copy matters to you, run the
hybrid method rather than the offline one.

`scripts/calibrate.py` prints every figure in word-count bands for this reason:
the human half of the corpus is largely interface strings and its median length
differs by language, so a single recall number does not mean the same thing in
each.

**A model's judgment is not reproducible.** Neither a seed nor a temperature is
exposed by the providers, so two runs over the same text can disagree. The
judgment cache hides this between runs of the same text, and drops entries
after 90 days.

**A repository scan is not a weaker page audit.** Scanning templates misses
what only exists once rendered and reports things a rendered page would not.
Use a URL, or `--devserver`, when the answer has to be about the page.

**An audit at one width has been done at one width.** The mobile navigation of
most sites is not in the desktop DOM at all. Pass all three breakpoints unless
you mean one.

**Typography is noisy on well-set copy.** The category is on by default and
flags deliberate em dashes and curly quotes; `--no-typography` or the Symbols
section in Settings turns it off.

**`--scope technical` does not measure style at all.** The phrase list behind
the style checks is built from marketing copy, and over 7225 comment blocks in
one real repository and 55756 in another it produced zero style findings. The
character checks still run. A quiet technical scan therefore means "not
measured", not "clean", and the scan says so in its own output.

**On a 16-colour terminal two of the four severity steps collapse.**
`sev-high` and `sev-medium` both land on ANSI 7; `critical` and `none` stay
distinct. Every row is still labelled with its severity in words, so nothing is
lost except reading the ramp at a glance. 256 colours show all four.

**Content Credentials need an optional reader.** Without `c2pa-python` and
`cryptography`, XAnalyze reports that a file carries a manifest and says it
could not read it, which is true and less than you want.

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

```bash
xanalyze                                    # the terminal interface
xanalyze fullscan https://example.com       # both passes over a site
xanalyze scan ./src                         # AI patterns and characters
xanalyze audit https://example.com --browser  # accessibility, SEO, speed
xanalyze fix ./src                          # write the character fixes
xanalyze runs                               # what ran, and what can continue
xanalyze update                             # check and install a new version
xanalyze --version
```

Every command checks for a new version once a day and prints one line when
there is one; `--no-update-check` turns that off. The window is a separate
application (`XAnalyze.app`, or `python main.py` from source).

---

## CLI Commands

### `fullscan` - Full Scan

Both passes in one run: AI patterns and characters, plus accessibility, SEO, performance and best practice.

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
| `--repo PATH` | Local checkout behind a URL target. A finding whose passage matches a block found under `PATH` gets `source_file`/`source_line` - the file to fix, not just the page it renders on. Additive: a URL scanned without it works exactly as before |
| `--devserver` | Detect and start a repo's own dev server (`package.json`, `manage.py`, `Gemfile`+`bin/rails`) and scan the rendered site instead of the source. Off by default - the server may already be running elsewhere; already have one running? Pass `--url http://localhost:PORT` instead |
| `--start-command CMD` | Override the detected dev server start command, run without a shell (e.g. `--start-command "npm run dev:custom"`) |
| `--dev-server-port N` | Port to expect, when it can't be read from the server's own output (Django/Rails; Node servers announce their own) |
| `--yes` | Install missing dev server dependencies without asking |
| `--detector DETECTOR` | AI pattern detector: `offline`, `embedding`, `hybrid`, `llm-judge` |
| `--model MODEL` | Model for the AI pass, e.g. `sonnet`, `opus` (only with `--detector ai`/`llm-judge`; ignored by the xFormat subscription, which picks its own) |
| `--effort {low,medium,high}` | How hard the AI pass thinks (default: `low`) |
| `--no-judgment-cache` | Re-ask the model about passages it already judged this machine has seen before (slower; the only way to get a fresh, and possibly different, opinion - the judge is not deterministic) |
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

### The four shapes worth remembering

```bash
# 1. A proper look: ten pages, three widths, a model reading the copy.
xanalyze fullscan mysite.com --max-pages 10 --depth 2 --detector ai --breakpoints all

# 2. A quick look - the defaults: 30 pages, depth 1, desktop only, offline.
xanalyze fullscan mysite.com

# 3. Code: no crawl, no browser. AI-text and characters plus the static audit.
xanalyze fullscan ./my-project

# 4. What ran, and carrying on.
xanalyze runs
xanalyze resume 2026-08-24-1331
```

`--detector ai` (also `llm-judge`, `judge`) says a model reads the copy, not
whose account pays: that comes from your settings, and the run prints the
judge it resolved to. `xanalyze ai status` says what is available.

The defaults are a quick look. A ten-page audit at three widths takes about
five minutes, ~90% of it the browser pass; `timings.md` in the run folder
shows where it went.

---

### Scanning a site you also have the code for

Two different questions. Measured on matched content - one HTML page and the
PHP template that produces it - the rendered page triggered **15** rules the
template could not (`html-lang`, `page-has-h1`, `seo-canonical`,
`link-text-vague`: most of what `wp_head()` writes and a template never
holds), and the template triggered one the page could not.

Scan the site for what it is - `fullscan https://example.com` - because most
of what an accessibility and SEO audit measures is a property of the render.
Add `--repo PATH` to also learn *where* to fix it: a content finding whose
passage matches a block under `PATH` carries `source_file` / `source_line`
into the report, the briefing and the JSON.

---

### No live site, but a checkout - `fullscan` can run it

A repo with `package.json`, Django's `manage.py` or Rails'
`Gemfile`+`bin/rails` can start its own dev server and be scanned as the
rendered site. Opt-in, because one may already be running elsewhere and a
second on another port helps nobody:

```bash
xanalyze fullscan ./repo            # static scan; says the server was not started
xanalyze fullscan ./my-vite-app --devserver
# node: dependencies are missing. Run `npm install`? [y/N]
# [devserver] node ready at http://localhost:5173
```

Missing dependencies stop the run and ask before installing; `--yes` skips
the prompt. Once the server answers, the crawl and audit run against it as
against any URL - measured live, 8 accessibility/SEO rules that a static scan
of the same repo cannot produce. `--repo` is set to the checkout
automatically, so content findings still name the file to fix.

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

**Candidates are deduplicated.** The agent pays for every candidate it is
handed, whichever model it runs - that is the point of this path - so the same
header on ten pages was ten times the cost of one answer. It used to be: the
only guard was `block_id`, a fresh uuid per block, which deduplicated nothing
across pages. Measured on a ten-page site: **124 candidates, 68 distinct, 45%
repeats.**

Each candidate now carries `places` and `occurrences`, so the agent can see
that a passage is site-wide - real context when judging a header - and
`agent-judge` gives one verdict to every place it names. Three identical files
produce two candidates and six findings, two per file: nothing is lost, half
the work is.

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

Word lists per language (100+ English, 80+ Ukrainian, 80+ Italian):
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

#### Each passage is read once, and once only

A crawl of ten pages of one site produced 573 text blocks and **236 distinct
texts**. A header and a footer appear on every page, so `Tel. +39 0432 924815`
was read 26 times, the site's email 26 times, a menu label 23 times.

Passages are deduplicated **across the whole run**, not within a page - the
repetition worth removing is exactly the one a single page cannot see. Two
passages are the same when their text matches after whitespace is collapsed
and machine-generated identifiers are masked, so a menu that renders with a
fresh uuid on every page is still one menu. The language hint is part of the
identity, because the same string read as Italian and as English is two
questions and the detectors answer them differently.

Both the offline pass and the judge read that one list. **Nothing is lost:**
every occurrence still produces its own finding with its own page, because a
fix has to visit each page. Deduplication changes what is *asked*, never what
is *reported*.

Verdicts are also kept on disk between runs, and that part is not an
optimisation. The judge is **not deterministic** - two runs of one site with
identical flags returned 6 findings and then 24 - and no route here exposes a
temperature or a seed, so identical output cannot be requested from the model.
It can only be remembered.

Measured on that site, `--detector ai --model sonnet --effort low`:

| | blocks read | requests | wall clock |
|---|---|---|---|
| before | 573 | 72 | 8m 33s |
| first run | 242 | 31 | 3m 42s |
| second run | 0 | 0 | **3.3s** |

The second run's report is byte-for-byte the first run's.

An entry is keyed by the passage, the detector, the model, the effort and the
prompt's own text, so changing any of them invalidates it without anyone
having to bump a version. `--no-judgment-cache` re-asks, because a cached
wrong answer must not be un-fixable. `XANALYZE_JUDGMENT_CACHE` moves the
store; entries older than 90 days are dropped.

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

`scripts/calibrate.py` prints what a classifier that knows *only* the length
scores, and reports precision and recall in word-count bands, so the same
mistake is visible before the next signal is believed; `--confounds` adds the
length distribution the two halves are drawn from. On this corpus that ceiling is 57.9%
precision and the detector reaches 100%, which is what says it is detecting
writing rather than length - **on this corpus**. Its positives were written by
models and its negatives are largely interface strings, so the number is a
statement about the detector against that sample and not about your text. See
[Limits](#limits).

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

### What Counts as Copy

A repository scan reads the strings a person will see - a `placeholder`,
a `t("...")` call, an object key like `title:` - and leaves the rest of
the code alone. Two roles are told apart on purpose, because the string
itself cannot tell you which it is:

- **A tool schema's field descriptions are not copy.** A tool definition
  writes its parameter descriptions under the same `description:` key a
  landing page writes its copy under, and both hold English sentences. The
  object around it is what separates them: a schema declares a `type` from
  the format's own primitives (`string`, `number`, ...) and carries a
  second schema key (`required`, `enum`, `parameters`, ...). Measured on a
  real repository, this is 12% of everything that looked like copy.
- **A quoted example in Markdown is not shipped markup.** Fenced blocks
  and inline backticks are masked before parsing, so a document writing
  `<img src="...">` in a bug report is not reported as a missing `alt`.

The rule stays conservative in both directions: reading a schema
description as copy costs a meaningless verdict, while dropping a real
sentence costs a finding, and those are not the same price.

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
3. **axe-core** — the engine most audits are run with (~27% of WCAG failures detectable automatically, by its own measurement)
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

## Media Provenance

Images are read for what they say about their own making. This is not an
AI-image detector, and the distinction is the whole point: there is no honest
way to look at pixels and say a model drew them. What there is, is a set of
fields generators write into the file themselves.

| Finding | What it means |
|---|---|
| `bp-ai-media-declared` | The file states a model made it — `digitalSourceType: trainedAlgorithmicMedia`, or a prompt block only a local generation stack writes |
| `bp-ai-media-tool` | A generator's name in a tool field. Weaker: an image merely *edited* in a generator's app carries the same string |
| `bp-ai-media-signed` | A C2PA manifest is present but not verified — either no reader is installed, or the manifest failed validation. The reason is printed with the finding |

**The absence of every field above means nothing at all.** A screenshot, a
re-save, or an upload through most platforms strips all of them. A quiet
image is not a verdict that a person made it.

### Content Credentials (C2PA)

A signed manifest is the strongest provenance there is, so it is reported
whether or not it can be read: passing over one silently would show a file
that documents itself as a file that does not.

Reading one needs two optional packages, which carry a native component:

```bash
pip install c2pa-python cryptography
```

Without them the finding says so, in those words, instead of pretending the
file is quiet. **The downloadable bundles carry the reader**, because a frozen
app has no pip: leaving it optional there would have meant absent forever, and
the strongest provenance a file can carry would read as present-and-unread on
every machine that did not build from source. It costs 27 MB of a 1.1 GB
bundle.

When the manifest is read, three outcomes are kept apart, because they are
three different statements:

- **The file declares model-made content** — `trainedAlgorithmicMedia`, read
  both at the top of an assertion payload and inside each `c2pa.actions`
  entry, which is where a generator signing its own output writes it.
- **The manifest does not hold** — the bytes no longer match what was signed
  (`assertion.*`, `claimSignature.*`). Reported as unverified with the code,
  never as a declaration: the signature is the entire value of C2PA.
- **The signer is not on a trust list this build carries**
  (`signingCredential.untrusted`) — a statement about the build, not about
  the file, so it does not withdraw the file's claim.

---

## Repository Facts

A repository scan also reads what the repository says about *itself*, which
is a different question from what its pages do. Nothing here is judged; each
is a fact that is either present or absent.

| Finding | Severity | What it reads |
|---|---|---|
| `sec-env-tracked` | Critical | A `.env` that is already tracked by git — a credential that has been published and needs rotating, not deleting |
| `sec-env-not-ignored` | Serious | A `.env` no ignore rule covers — a credential waiting for the next `git add .` |
| `bp-assistant-commits` | Minor | Commits whose message names an assistant as author |
| `bp-assistant-artifacts` | Minor | Committed assistant configuration: `CLAUDE.md`, `.cursor/`, Copilot instructions |
| `bp-assistant-touched` | Minor | Findings sitting on lines an assistant-authored commit last touched |

Writing code with an assistant is not a defect, and these are reported as
provenance rather than as problems. A folder that is not a git repository
produces no commit findings at all: "no assistant commits found" and "no
history to look at" are opposite statements, and only one of them is true.

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

**What a framework stamps into the markup is not part of the element.**
Comparing the markup literally means one component splits into one finding
per page as soon as anything generates an identifier for it, and twelve real
identifier styles were measured: nine of them split. React's `useId`
(`:r3:`), Emotion (`css-1q2w3e`), styled-components (`sc-bdVaJa`), Svelte and
Astro's scope hashes, Angular's `_ngcontent-`, Radix, MUI and Ember counters
are all masked before the comparison, alongside the UUIDs, hex runs and long
digit runs that were already handled. Masked only inside identifier
attributes - `class`, `id`, `for`, `aria-controls` and friends - never in
`src`, `href`, `alt` or `title`: over-masking merges findings that really are
different, and a wrongly merged problem hides a real one. Tailwind's `mt-4`,
Bootstrap's `col-md-6` and a hand-written `id="email"` are all left alone,
and there is a test for each direction.

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

Agents drive the same commands people do; two exist only for them.

| The user wants | The command |
|---|---|
| Everything about a site or a repo, in one run | `xanalyze fullscan <target>` |
| Accessibility, SEO, performance, best practice | `xanalyze audit <target>` |
| AI-written copy and non-keyboard characters | `xanalyze scan <path>` |
| The character fixes written back | `xanalyze fix <path>` |
| Those writes undone | `xanalyze undo <path>` |
| What was run, and what can be continued | `xanalyze runs` |

`--json` on any of them gives machine-readable output, `--language uk|it|en`
sets the report's language, `--breakpoints desktop,tablet,mobile` chooses the
widths, `--styled-report report.pdf` writes a document to hand over.

### Agent-as-Judge Mode

Two commands split a scan in half so the agent is the model in the middle: no
API key, no subscription, and nothing leaves the machine except into the
agent's own context.

```bash
xanalyze agent-scan ./src --json > passages.json   # offline pass, passages out
#                                                    the agent judges them
xanalyze agent-judge ./src --judgments verdicts.json
```

`agent-scan` writes every passage worth judging with its id, its text and what
the offline signals said. `agent-judge` takes the same ids back with a verdict
each: the judgment is the agent's, the scoring, grouping and documents stay
this tool's. One verdict covers every place a passage occurs - three identical
files are judged once.

### Reading the output

```bash
xanalyze fullscan https://example.com --json > run.json
jq '.audit.issues[] | select(.severity == "critical")' run.json
jq '.findings[] | {score, explanation}' run.json
```

A finding says where it is (`source`, `line`, `selector`), what it is
(`rule_id`, `severity`, `snippet`) and, where the correction follows from the
markup, `fix_snippet`. A responsive run also carries `details.breakpoints`, so
a defect that exists only at one width can be told from one that exists
everywhere.

## GUI

The desktop app answers the same questions as the CLI.

It opens on the **setup screen**: what is looked at, how it is read, what is
looked for, who judges, and a sentence naming what the run will be before you
press anything. Pressing Analyze hands the window to the working layout; the
empty state's "Choose a target" brings it back.

During work the same choices are one row of inline values above the results.

**The controls, in the row or on the setup screen**

1. **Source** — website URL, repository folder, or single HTML file. A bare
   host is accepted here too
2. **Check** — accessibility, AI patterns, or both (both by default)
3. **Method** — offline, embedding, AI, or offline + AI. The AI entries appear
   only when there is an account or a key to pay for them
4. **Scope** (folders) — the copy that ships, comments and docstrings, or both
5. **Depth** (sites) — how far the crawl follows links
6. **Account** — who pays for an AI pass, and whether anyone is signed in

**Bringing the target instead of typing it.** A page saved as one file — or a
folder — can be dropped anywhere on the window: it sets the source and fills
the path, and the setup screen shows what was chosen with its size, so a wrong
export is visible before the run rather than after it. Anything else is refused
by the cursor rather than accepted and ignored.

**The results**, read left to right

7. **Findings list** — severity badge, one row per distinct problem. A problem
   found in several files says how many, rather than repeating itself
8. **Preview** — the rendered page, or the source file, with the finding
   outlined or its line highlighted. Pinnable to `1440`, `834` or `390`, so a
   finding reported at one width can be looked at that width. A width wider
   than the column is scaled down rather than demanded from the window: the
   page still lays out at 1440 while the pixels stay inside the column
9. **Detail** — what was found, why it matters, how to fix it, the element,
   the ready replacement, and every place the same problem appears
10. **Actions** — fix the characters, open the replacement list, rewrite in
    place, undo a write, export the report. *Fix on disk* opens the same list:
    the audit's corrections are read there before they are written, like
    everything else

The window folds one column at a time as it narrows: the detail column first
(it reappears inline under the clicked row), then the preview.

**The replacement list**

Nothing is written to your files by a number in a message box. *Generate
replacement list* opens one screen holding every pending change of the run —
the character fixes, the model's drafts and the audit's markup corrections
together — with four columns: where it is, what it says now, what it would
say, and where the correction came from.

What arrives ticked is the point of the screen:

- **mechanical** — the correction is derived, not composed (one right removal
  for an invisible character, one right attribute for a button with no
  accessible name). Ticked
- **model draft** — a model wrote the replacement, and a fluent sentence is
  not a correct one. Not ticked until you tick it
- **decision** — there is no replacement, only the shape of one. `alt=""` on a
  photograph is valid markup and a lie, so the row shows what has to be
  decided and cannot be ticked here at all

The button says how many rows it is about to write, and *Save to file* writes
the same list as Markdown (`replacements-YYYY-MM-DD.md`) for a review that
happens in a pull request or on somebody else's screen.

Pressing *Write* shows what is about to happen: the files, how many
fragments each of them gets, and a switch for the `.bak` copy kept beside
every file before its first change. What happened comes back as four numbers
that are not the same number — applied, files changed, skipped because the
fragment moved after the scan, errors — with *Undo everything* offered while
those copies are still there.

A decision row has one action of its own, *Decide*, with three ways out: write
the value yourself, mark the image decorative (a claim a person is allowed to
make and the tool is not), or hand it to the model. A decision you answered
becomes an **answered** row — ticked, because you have just made the decision.

*Let the model answer N* hands the open decisions to the configured model. What
it answers becomes a **model draft** — unticked, with a sentence to read —
never a mechanical row, and what the page does not actually say is left as a
decision.

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

The terminal interface is written in the interface language, like the window:
its menu, its forms, its statuses and its footer key hints all come from the
same table, and changing the language in its own Settings rebuilds the screens
in the new one immediately rather than at the next launch.

Navigate with arrow keys or number shortcuts (1-7); `Tab` also moves between
controls. The footer lists the keys the current screen accepts. `Esc` goes
back, `q` quits.

---

## Configuration

### The settings screen

Five sections in a rail — **Account and model**, **General**, **Symbols**,
**Exceptions**, **Advanced** — and one row per decision, with the file every
row is written to named at the bottom of the rail.

The control shape follows the kind of decision: a **switch** for on/off, a
**segmented control** where there are two to four alternatives and seeing them
is the explanation (theme, model effort), a **dropdown** only where the list is
open-ended (language, model). *Symbols* shows what each category actually
catches (`U+200B, U+200D, U+FEFF`) rather than only its name, and the rows go
dead when the character pass itself is switched off.

**Account and model** is three rows, one per account — the xFormat
subscription, your own Anthropic key, the Claude Code session signed in on
this machine — each saying what its own state is, with the choice of which one
a run uses. Everything shown when the screen opens is read locally and
cheaply; the two answers that cost something (the subscription's quota, the
CLI's session) sit behind each row's own *Check*.

**Advanced** also says what the tool has put on this machine: how many model
judgments are cached and where, with a button to clear them, and *Remove
XAnalyze from this machine*, which lists exactly what it would delete —
and what it leaves alone, such as reports already written and run folders.

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

A bare list like this one is read as file patterns: a line before the first
section header that ends in `/` or carries a glob is a path. Anything else
bare is a phrase, which is what people write first. To be explicit, open with
a section header - see **Suppressions** below.

### Suppressions

Suppress specific findings via settings or `.xanalyze-ignore`:
- By CSS selector (exclude regions)
- By rule ID (disable rules)
- By fingerprint (one exact finding, dismissed once, gone after a re-scan)
- By phrase, or by path

Entries go under a section header, and anything before the first header is
read as a phrase, which is what people write first:

```
[rules]
meta-viewport  # we ship a fixed-width admin on purpose

[selectors]
# third-party embeds
#promo-banner
.ads

[fingerprints]
083bea550659aadb  # style · about.md · comprehensive
```

**The file stays yours.** Comments, blank lines and grouping survive a write
from the app: dismissing a finding in the window adds one line to the right
section and leaves everything else where you typed it.

**A note after `#` is a note, not part of the entry.** Write the reason next
to the rule you switched off and the rule is still switched off. Inside
`[selectors]` a `#` that is followed immediately by a name is an id selector
(`#promo-banner`), so a note there needs a space after the `#`.

**Dismissing a finding records what it was.** A fingerprint is a one-way hash
of the finding, so the app writes a readable note beside it. Without that
note, un-hiding a finding later means removing a line of hex and re-scanning
to find out what it did.

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

- Python 3.14+ — earlier versions cannot install the C2PA reader: `c2pa-python`
  declares `Requires-Python >=3.7` and then uses syntax that needs 3.10+, so pip
  installs a version that fails at import
- PySide6 (for GUI)
- sentence-transformers (for embedding detector)
- QtWebEngine (for browser pass)
- `c2pa-python` and `cryptography` — optional, for reading a signed manifest

---

## License

MIT
