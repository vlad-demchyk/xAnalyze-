# XAnalyze (Italiano)

Desktop e headless analyzer: rilevamento di testi generati da AI, caratteri non da tastiera e audit completo dell'accessibilità di siti/repository.

[English](README.md) | [Українська](README_ua.md)

---

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

## Disinstallazione

### CLI

```bash
rm /usr/local/bin/xanalyze
# o se installato in ~/bin:
rm ~/bin/xanalyze
```

### GUI

```bash
rm -rf /Applications/XAnalyze.app
```

### Config e cache

```bash
rm -rf ~/.config/xanalyze
rm -rf ~/.xanalyze
```

## Requisiti

- Python 3.9+
- PySide6 (per GUI)
- sentence-transformers (per detector embedding)

## Licenza

MIT
