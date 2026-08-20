# XAnalyze

Desktop and headless analyzer: AI-generated text detection, non-keyboard characters, and full website/repository accessibility audit.

[Українська](#xanalyze-ua) | [Italiano](#xanalyze-it)

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
curl -L -o xanalyze https://github.com/vlad-demchyk/xAnalyze-/releases/latest/download/xanalyze
chmod +x xanalyze
sudo mv xanalyze /usr/local/bin/xanalyze
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

## Requirements

- Python 3.9+
- PySide6 (for GUI)
- sentence-transformers (for embedding detector)

## License

MIT

---

<a id="xanalyze-ua"></a>
# XAnalyze (Українська)

Десктопний та headless аналізатор: виявлення AI-згенерованого тексту, символів без клавіатури та повний аудит доступності сайту/репозиторію.

## Можливості

- **Виявлення AI-патернів** — евристичний (кліше, структурні патерни) та на основі embeddings (sentence-transformers)
- **Символи без клавіатури** — zero-width пробіли, curly quotes, em dash, homoglyphs
- **Аудит доступності** — правила WCAG, SEO, продуктивність, найкращі практики (40+ правил)
- **Повне сканування** — AI-патерни + доступність в одній команді
- **Стилізовані звіти** — брендовані PDF/HTML для людей
- **Брифінги для агентів** — markdown/JSON для coding agents
- **CLI + GUI** — один бінарник, два інтерфейси

## Швидкий старт

### GUI (macOS)

```bash
curl -L -o XAnalyze.app.zip https://github.com/vlad-demchyk/xAnalyze-/releases/latest/download/XAnalyze.app.zip
unzip XAnalyze.app.zip
mv XAnalyze.app /Applications/
```

### CLI (macOS/Linux)

```bash
curl -L -o xanalyze https://github.com/vlad-demchyk/xAnalyze-/releases/latest/download/xanalyze
chmod +x xanalyze
sudo mv xanalyze /usr/local/bin/xanalyze
```

### З вихідного коду

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

## Команди CLI

| Команда | Опис |
|---|---|
| `xanalyze scan` | Звіт про знахідки без зміни файлів |
| `xanalyze fix` | Перезаписати символи без клавіатури |
| `xanalyze audit` | Аудит URL/папки: доступність, SEO, продуктивність |
| `xanalyze fullscan` | Комбіновано: AI-патерни + доступність + звіти |
| `xanalyze compare` | Порівняти детектори на одних файлах |
| `xanalyze cache` | Управління кешем сканування |
| `xanalyze ai` | Операції з AI-провайдерами |
| `xanalyze clean` | Фільтр тексту з stdin до stdout |

## Приклади

```bash
# Повне сканування зі звітами
xanalyze fullscan https://example.com \
  --styled-report report.html \
  --report agent-briefing.md \
  --json

# Тільки AI-патерни
xanalyze scan ./src --detector offline --scope both --json

# Аудит доступності
xanalyze audit https://example.com --browser --breakpoints all
```

## Детектори

| Детектор | Тип | Вартість |
|---|---|---|
| `offline` | Евристичний (кліше + символи) | Безкоштовно |
| `embedding` | Семантична схожість (sentence-transformers) | Безкоштовно |
| `claude-llm-judge` | LLM-as-judge (Anthropic API) | Платно |
| `xformat-llm-judge` | LLM-as-judge (підписка xFormat) | Платно |
| `hybrid` | Offline + LLM judge | Платно |

## Вимоги

- Python 3.9+
- PySide6 (для GUI)
- sentence-transformers (для embedding детектора)

## Ліцензія

MIT

---

<a id="xanalyze-it"></a>
# XAnalyze (Italiano)

Desktop e headless analyzer: rilevamento di testi generati da AI, caratteri non da tastiera e audit completo dell'accessibilità di siti/repository.

## Funzionalità

- **Rilevamento pattern AI** — euristico (cliché, pattern strutturali) e basato su embedding (sentence-transformers)
- **Caratteri non da tastiera** — spazi zero-width, virgolette curly, em dash, omoglifi
- **Audit accessibilità** — regole WCAG, SEO, performance, best practice (40+ regole)
- **Scansione completa** — pattern AI + accessibilità in un comando
- **Report stilizzati** — PDF/HTML brandizzati per persone
- **Briefing per agenti** — markdown/JSON per coding agent
- **CLI + GUI** — un binario, due interfacce

## Avvio rapido

### GUI (macOS)

```bash
curl -L -o XAnalyze.app.zip https://github.com/vlad-demchyk/xAnalyze-/releases/latest/download/XAnalyze.app.zip
unzip XAnalyze.app.zip
mv XAnalyze.app /Applications/
```

### CLI (macOS/Linux)

```bash
curl -L -o xanalyze https://github.com/vlad-demchyk/xAnalyze-/releases/latest/download/xanalyze
chmod +x xanalyze
sudo mv xanalyze /usr/local/bin/xanalyze
```

### Dal codice sorgente

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

## Comandi CLI

| Comando | Descrizione |
|---|---|
| `xanalyze scan` | Report dei risultati senza modificare nulla |
| `xanalyze fix` | Sovrascrivi caratteri non da tastiera |
| `xanalyze audit` | Audit URL/cartella: accessibilità, SEO, performance |
| `xanalyze fullscan` | Combinato: pattern AI + accessibilità + report |
| `xanalyze compare` | Confronta detector sugli stessi file |
| `xanalyze cache` | Gestione cache scansione |
| `xanalyze ai` | Operazioni con provider AI |
| `xanalyze clean` | Filtro testo da stdin a stdout |

## Esempi

```bash
# Scansione completa con report
xanalyze fullscan https://example.com \
  --styled-report report.html \
  --report agent-briefing.md \
  --json

# Solo pattern AI
xanalyze scan ./src --detector offline --scope both --json

# Audit accessibilità
xanalyze audit https://example.com --browser --breakpoints all
```

## Detector

| Detector | Tipo | Costo |
|---|---|---|
| `offline` | Euristico (cliché + caratteri) | Gratuito |
| `embedding` | Similarità semantica (sentence-transformers) | Gratuito |
| `claude-llm-judge` | LLM-as-judge (Anthropic API) | A pagamento |
| `xformat-llm-judge` | LLM-as-judge (abbonamento xFormat) | A pagamento |
| `hybrid` | Offline + LLM judge | A pagamento |

## Requisiti

- Python 3.9+
- PySide6 (per GUI)
- sentence-transformers (per detector embedding)

## Licenza

MIT
