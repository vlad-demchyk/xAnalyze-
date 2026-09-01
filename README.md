# XAnalyze

Finds AI-written copy, invisible characters, and accessibility, SEO, performance
and security defects in a website, an HTML file or a repository - and reports the
exact line, not a score.

[Українська](README_ua.md) | [Italiano](README_it.md)

## What it is for

You are handed a page, a theme, a web part or a repository and have to answer
three questions: is this copy machine-written, does the markup carry characters
no keyboard produces, and is the thing accessible and correct. XAnalyze answers
all three in one run and names the file and line behind every answer.

It is one binary with three surfaces - a desktop window, a terminal interface
and a command line - over one core, so the three cannot disagree about what a
run measured.

## Install

**macOS app**

```bash
curl -L -o XAnalyze.app.zip https://github.com/vlad-demchyk/xAnalyze-/releases/latest/download/XAnalyze.app.zip
unzip XAnalyze.app.zip && mv XAnalyze.app /Applications/
```

On first launch the app offers once to link itself as `xanalyze` in
`~/.local/bin`, so the CLI and the TUI need no second download. The bundle is
not signed yet: the first launch needs Control-click -> Open.

**CLI only**

```bash
curl -L -o xanalyze-cli.tar.gz https://github.com/vlad-demchyk/xAnalyze-/releases/latest/download/xanalyze-cli-macos-arm64.tar.gz
tar -xzf xanalyze-cli.tar.gz && export PATH="$PWD/xanalyze:$PATH"
```

**From source**

```bash
git clone https://github.com/vlad-demchyk/xAnalyze-.git && cd xAnalyze-
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python main.py                                  # window
python cli.py fullscan https://example.com      # command line
python cli.py                                   # terminal interface
```

## Use it

```bash
xanalyze                                      # terminal interface
xanalyze fullscan https://example.com         # everything, in one run
xanalyze fullscan ./my-project                # the same, over a checkout
xanalyze scan ./src                           # AI patterns and characters only
xanalyze audit ./page.html                    # website rules only
xanalyze fix ./src                            # apply character fixes (.bak kept)
xanalyze runs                                 # list, resume, compare
```

`fullscan` is the answer to "check this". A URL is crawled and rendered; a
folder is read as source unless `--devserver` starts the project's own server;
a single HTML file is read as the finished page it is.

### Commands

| Command | What it does |
|---|---|
| `fullscan TARGET` | AI patterns, characters and every website rule, plus reports |
| `scan PATHS` | AI patterns and non-keyboard characters, changing nothing |
| `audit TARGET` | website rules only, over a URL, an HTML file or a folder |
| `fix` / `undo` | apply exact character corrections; restore the `.bak` copies |
| `runs` / `resume` / `compare` | a run is an object: list it, continue it, diff it against the last |
| `login URL` | sign in to a site by hand, in a real browser, so a run can read behind it |
| `logs` | what a run actually did, as JSON Lines |
| `ai` | the account behind the model passes: `status`, `login`, `rewrite` |
| `agent-scan` / `agent-judge` | hand candidate passages to an agent and take its verdicts back |
| `clean` | filter text from stdin to stdout |
| `update` / `uninstall` | self-update from the latest release; remove everything |

`xanalyze COMMAND --help` prints every option. The ones worth knowing:

| Option | Purpose |
|---|---|
| `--depth N`, `--max-pages N` | how far a crawl goes, and how many pages |
| `--repo PATH` | the checkout behind a site, so a finding names the file and not only the page |
| `--devserver` | start the project's own dev server and audit the rendered site |
| `--breakpoints all` | audit every width; without it, one width (1440x900) |
| `--no-browser` | the static reading only, and much faster |
| `--detector NAME` | `offline` (default, free), `embedding`, `hybrid`, `ai` |
| `--category`, `--confidence` | narrow what is reported; both are views over one pass |
| `--within SELECTOR` | audit only this part of the page - a delivered widget or web part |
| `--report PATH`, `--styled-report PATH` | agent briefing (`.md`/`.json`) and human report (`.pdf`/`.html`) |
| `--json`, `--check` | machine-readable output; exit 1 on serious findings |
| `--language uk\|it\|en` | report language; detected from the pages otherwise |
| `--project NAME` | one project inside a folder that holds several, by folder name or path |
| `--start-command CMD`, `--dev-server-port N` | what to run instead of the detected script, and the port to expect |
| `--no-session` | read a site the way a stranger does, ignoring any stored sign-in |
| `--profile-defaults` | switch on what the detected stack asks for (see below) |

## What it checks

**AI-written copy.** The offline pass reads sentence rhythm, repeated
structure and cliche phrases, and names the phrase it matched so a finding can
be argued with. An embedding pass and a model-judged pass are available for a
second opinion. None of it is proof of authorship.

**Non-keyboard characters.** Zero-width characters, homoglyphs, unusual
spaces, styled letters and typography characters - each one exact, and each one
fixable in place.

**Website rules**, by category, with the count the test suite enforces:

`accessibility` (36), `best-practices` (13), `geo` (2), `performance` (8), `security` (10), `seo` (8)

A rule runs where it means something and nowhere else, decided on evidence:
the file's syntax (JSX rules only in `.jsx`/`.tsx`), what the document is for
(email rules only on an email), and which stack the project proved on disk
(the WordPress escaping rule only in WordPress).

**In a browser**, when one is available: axe-core and HTML_CodeSniffer, the
page in the state a person puts it in - focus indicator, keyboard traps, focus
order, hover-only content, an open modal, the form journey - and the same page
at several widths. It reads and never acts: nothing is typed, clicked or
submitted.

**Provenance, not verdicts.** IPTC/XMP fields and C2PA manifests in every
image a page refers to (only the first 512 KB of each is fetched), and
repository facts: tracked `.env` files, assistant-named commits, committed
assistant configuration. Reported as facts about origin, never as defects.

**Certainty.** Every finding is `exact`, `needs-browser` or `advisory`. The
undecided are not listed by default - on one real page that was 312 of 348
contrast findings - and the run says how many it left out. `--unsettled`
brings them back; `--confidence exact` drops the advisory ones too.

## The target decides what to ask

A project announces what it is, and that decides more than which folders to
skip. An SPFx checkout knows it ships web parts and cannot know which site
they land on. A Vite or Next app read off disk is templates the bundler has
not run, where `<App />` is not a heading. One self-contained HTML file has no
second page to crawl to, so width is the only axis left.

Each of those becomes a parameter, and each arrives with the stack that asked
for it and the marker file that proved that stack: "enabled, because ..." is a
sentence you can disagree with, not a silent default. **Anything you set
yourself is never overwritten.**

The window and the terminal form apply it - the control is ticked, the reason
is under it, one click undoes it. The command line does not: a command line is
a contract, and a run that started a dev server because it found a
`vite.config.ts` would not be the run the script author wrote. There the same
suggestions are printed as `# [profile]` lines on stderr, and
`--profile-defaults` asks for them to be applied.

The same reading decides which fields exist at all: `--depth` needs an
address, `--incremental` needs files on disk, and a control that reaches
nothing for this target is not shown - nor read, so a `--devserver` ticked for
a repository does not follow you to a single file.

A folder holding several projects is asked about rather than merged: twenty
SPFx solutions in one directory are twenty deliverables. `--project NAME`, and
the picker the window and the terminal form show, audit one of them on its own
- the scan, the ignore file and the dev server all follow it, so they cannot
end up describing different projects. A repository that proves something of
its own is still one project: Bedrock's `web/` is that project's docroot, not
a second project.

**A monorepo has more than one dev server, and they are not the same run.**
The root's `dev` script starts, or orchestrates, the applications under it;
each application has a script of its own. `--devserver` was picking silently.
Now the run says which one it would start and that naming a project starts
that project's instead - measured on a real workspace, where the root
declares `workspaces: ["apps/*"]` and each of four applications declares its
own `dev`. `--start-command` overrides the script where neither is right.

## Work delivered as a fragment of somebody else's site

A **WordPress theme or plugin** is recognised the way WordPress recognises it
- the `Theme Name:` header in `style.css`, the `Plugin Name:` header in the
main PHP file - and its templates are read as fragments, so nothing asks
`header.php` for a canonical link or an `<h1>`.

A **SharePoint web part** is one subtree of a page the tenant owns.
`--within SELECTOR` confines the audit to it and switches off, with the reason
printed, everything that reads the whole document by construction. A generated
class suffix (`root-137`) need not be typed: the selector is retried against
the stem. `--repo PATH --web-parts` works the other way - it reads the
solution's manifests and finds this repository's parts wherever they appear on
the site.

Markup inside a **template literal** is audited too. `.ts` and `.js` are
skipped as files - a `<` in them is an operator - but a backtick string is not
code, and a classic SPFx part builds its whole interface in one. Measured on a
real solution: 72 of its 168 `.ts` files, and 131 findings nobody had read.

## Sites behind a login

`xanalyze login https://example.com/admin` opens a real browser on the site's
own form. 2FA, SSO and captchas all work, because it is a browser. XAnalyze
never sees a username or a password: what is kept is what the site handed that
browser, per host, readable only by you. `--no-session` reads the site the way
a stranger does; `login --list` and `login --forget HOST` manage what is
stored. Nothing about a session ever reaches a report, a log or the terminal.

A crawl also records when an address answered with a door rather than a page,
and says so plainly - a clean summary over nothing but sign-in forms is the
most misleading output this tool can produce.

## Reports

Every command writes a dated run folder, `~/Desktop/XAnalyze/` by default
(`XANALYZE_REPORT_ROOT` moves it):

```text
XAnalyze/example.com/2026-09-02-0930/
  report.md     grouped briefing for an agent
  report.pdf    report for a person
  timings.md    stage timings
  changes.md    what changed since the last run
  state.json    resumable state
```

Every document opens by naming the command and the parameters that changed
what was measured. A repeated problem is listed once with its locations nested
under it. `--json` keeps every finding, for CI.

## Interfaces

**Window** (`python main.py`, or the app). A setup screen for the target and
the run, then the finding list beside a source or rendered preview, with
fixes, replacement review and report export. Two widths can be put on screen
at once, to settle "this only breaks on mobile".

**Terminal** (`xanalyze` with no arguments). Scan, Audit, Full Scan, Reports,
Settings, Account, Update, Logs. Arrow keys, number shortcuts, `Tab`, `Esc`,
and `Ctrl+R` to run.

Mechanical corrections are selected by default; model drafts always require
review; judgement calls such as photographic alt text are never presented as
automatic fixes.

## Configuration

Settings live in `~/.config/xanalyze/settings.json` - language, provider,
`max_pages`, character categories.

`.xanalyze-ignore` in a project root uses gitignore syntax, and can also
suppress by rule, selector or fingerprint:

```text
vendor/
*.min.js

[rules]
meta-viewport

[fingerprints]
083bea550659aadb
```

## Templates it understands

Fourteen template languages have a **pair** of fixtures in
`tests/fixtures/frameworks`: the same component written the way its framework
says to, and written wrong. The correct half must produce no findings and the
broken half must produce the right ones, so this is a measured claim:

`alpine`, `angular`, `blade`, `django`, `erb`, `handlebars`, `liquid`, `php`, `razor`, `react`, `svelte`, `thymeleaf`, `twig`, `vue`

Markup in anything not on this list is still read - the parser does not refuse
it - but nothing has proved that a correct file in it comes back clean.

## Stacks it recognises

A project is identified from its own marker files, and what it turns out to be
decides what is treated as vendored rather than written here:

`angular`, `astro`, `bedrock`, `beehiiv`, `carrd`, `craft`, `django`, `docusaurus`, `dotnet`, `drupal`, `eleventy`, `ember`, `flutter`, `gatsby`, `ghost`, `hugo`, `jekyll`, `joomla`, `laravel`, `magento`, `nextjs`, `nuxt`, `qwik`, `rails`, `remix`, `shopify`, `silverstripe`, `spfx`, `spring`, `squarespace`, `statamic`, `storybook`, `sveltekit`, `symfony`, `typo3`, `vite`, `wagtail`, `webflow`, `wix`, `wordpress`, `wordpress-plugin`, `wordpress-theme`

Detection is evidence: a profile names the file that proved it, the exclusions
it implies are stated rather than applied silently, and one click scans them
anyway.

## Limits

- AI-text detection is corpus-dependent. It is not proof of authorship, and
  model judgments are not deterministic.
- **Text detection covers Ukrainian, Italian and English only.** A passage in
  another language is named as such and left unscored rather than measured
  against lists that do not speak it. Character and website checks are
  language-independent.
- **The offline wording pass is weak in Italian**: on the held-out corpus it
  finds 36% of known AI passages there, against 55% in English and 71% in
  Ukrainian, while the embedding pass finds 100%, 85% and 86%. A run over
  Italian pages says so and names the better detector.
- A folder scan cannot see content that exists only after rendering. Use a URL
  or `--devserver`.
- One width cannot describe responsive behaviour. Use `--breakpoints all`.
- Typography checks can flag intentional punctuation (`--no-typography`).
- C2PA reading needs the optional `c2pa-python` and `cryptography` packages.

## Building a release

```bash
make version        # what config.py says
make rebuild-all    # both bundles, at that version
make package        # the two archives `xanalyze update` looks for
```

`make package` refuses to run over a stale bundle. Neither archive is signed
or notarised yet.

## Requirements

Python 3.14+, PySide6 for the window, QtWebEngine for browser rendering,
sentence-transformers for the embedding detector, and `c2pa-python` with
`cryptography` for optional C2PA reading.

## License

MIT
