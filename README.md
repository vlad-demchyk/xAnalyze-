# XAnalyze

Desktop and headless analyzer: AI-generated text detection, non-keyboard characters, and full website/repository accessibility audit.

[Українська](README_ua.md) | [Italiano](README_it.md)

---

## Features

- **AI Pattern Detection** — heuristic (clichés, structural patterns, burstiness) and embedding-based (sentence-transformers)
- **Non-keyboard Characters** — zero-width spaces, curly quotes, em dashes, homoglyphs
- **Accessibility Audit** — WCAG rules, SEO, performance, best practices (40+ rules)
- **Full Scan** — combined AI patterns + accessibility in one command
- **Styled Reports** — branded PDF/HTML for humans
- **Agent Briefings** — markdown/JSON for coding agents
- **CLI + GUI** — one binary, two interfaces

## Quick Start

### GUI (macOS)

```bash
curl -L -o XAnalyze.app.zip https://github.com/vlad-demchyk/xAnalyze-/releases/latest/download/XAnalyze.app.zip
unzip XAnalyze.app.zip
mv XAnalyze.app /Applications/
```

### CLI (macOS/Linux)

```bash
curl -L -o ~/bin/xanalyze https://github.com/vlad-demchyk/xAnalyze-/releases/latest/download/xanalyze
chmod +x ~/bin/xanalyze
echo 'export PATH="$HOME/bin:$PATH"' >> ~/.zshrc
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
python cli.py fullscan https://example.com --json
```

## CLI Commands

| Command | Description |
|---|---|
| `xanalyze scan` | Report findings without changing anything |
| `xanalyze fix` | Rewrite non-keyboard characters in place |
| `xanalyze audit` | Audit URL/folder: accessibility, SEO, performance |
| `xanalyze fullscan` | Combined: AI patterns + accessibility + reports |
| `xanalyze compare` | Compare detectors on same files |
| `xanalyze cache` | Manage scan cache |
| `xanalyze ai` | Account and AI-backed operations |
| `xanalyze clean` | Filter text from stdin to stdout |

## Examples

```bash
# Full scan with reports
xanalyze fullscan https://example.com \
  --styled-report report.html \
  --report agent-briefing.md \
  --json

# AI patterns only
xanalyze scan ./src --detector offline --scope both --json

# Accessibility audit
xanalyze audit https://example.com --browser --breakpoints all
```

## Detectors

| Detector | Type | Cost |
|---|---|---|
| `offline` | Heuristic (clichés + characters) | Free |
| `embedding` | Semantic similarity (sentence-transformers) | Free |
| `claude-llm-judge` | LLM-as-judge (Anthropic API) | Paid |
| `xformat-llm-judge` | LLM-as-judge (xFormat subscription) | Paid |
| `hybrid` | Offline + LLM judge | Paid |

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

## Requirements

- Python 3.9+
- PySide6 (for GUI)
- sentence-transformers (for embedding detector)

## License

MIT
