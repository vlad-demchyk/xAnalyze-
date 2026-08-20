# XAnalyze (Italiano)

Desktop e headless analyzer: rilevamento di testi generati da AI, caratteri non da tastiera e audit completo dell'accessibilità di siti/repository.

[English](README.md) | [Українська](README_ua.md)

---

## Indice

- [Funzionalità](#funzionalità)
- [Avvio rapido](#avvio-rapido)
- [Comandi CLI](#comandi-cli)
  - [fullscan](#fullscan---scansione-completa)
  - [scan](#scan---rilevamento-pattern-ai)
  - [audit](#audit---accessibilità-seo-performance)
  - [fix](#fix---applica-correzioni)
  - [undo](#undo---annulla-correzioni)
  - [cache](#cache---gestione-cache)
  - [compare](#compare---confronta-detector)
  - [ai](#ai---operazioni-ai)
  - [clean](#clean---filtro-testo)
  - [serve](#serve---server-http-locale)
- [Metodi di rilevamento](#metodi-di-rilevamento)
  - [Rilevamento pattern AI](#rilevamento-pattern-ai)
  - [Caratteri non da tastiera](#caratteri-non-da-tastiera)
  - [Audit accessibilità](#audit-accessibilità)
  - [Audit SEO](#audit-seo)
  - [Audit performance](#audit-performance)
  - [Best practice](#best-practice)
  - [Passaggio browser](#passaggio-browser)
- [Detector](#detector)
- [Report](#report)
- [GUI](#gui)
- [Configurazione](#configurazione)
- [Disinstallazione](#disinstallazione)
- [Requisiti](#requisiti)
- [Licenza](#licenza)

---

## Funzionalità

- **Rilevamento pattern AI** — euristico (cliché, pattern strutturali, burstiness) e basato su embedding (sentence-transformers)
- **Caratteri non da tastiera** — spazi zero-width, virgolette curly, em dash, omoglifi
- **Audit accessibilità** — regole WCAG, SEO, performance, best practice (49 regole)
- **Scansione completa** — pattern AI + accessibilità in un comando con rendering browser automatico
- **Report stilizzati** — PDF/HTML brandizzati per persone
- **Briefing per agenti** — markdown/JSON per coding agent
- **CLI + GUI** — un binario, due interfacce
- **Audit responsive** — test a larghezza desktop, tablet e mobile
- **Rendering browser** — Chromium reale per siti renderizzati lato client (React, Vue, Next.js)

---

## Avvio rapido

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
python cli.py fullscan https://example.com
```

---

## Comandi CLI

### `fullscan` - Scansione completa

Il comando principale per l'analisi completo. Combina rilevamento pattern AI, audit accessibilità, SEO, performance e best practice in un'unica esecuzione.

**Comportamento automatico per URL e file HTML:**
- Rendering browser abilitato (gestisce React, Vue, Next.js, ecc.)
- Responsive breakpoints: desktop (1440px), tablet (834px), mobile (390px)
- Output JSON per l'agente
- Report PDF stilizzato salvato in `~/Desktop`
- Briefing agente (Markdown) salvato in `~/Desktop`

```bash
# Scansione completa di un sito (tutto automatico)
xanalyze fullscan https://xformat.net

# Scansione completa di un repository locale (no browser)
xanalyze fullscan ./my-project

# Solo breakpoint desktop
xanalyze fullscan https://example.com --breakpoints desktop

# Desktop + mobile (senza tablet)
xanalyze fullscan https://example.com --breakpoints desktop,mobile

# Con profondità di crawl
xanalyze fullscan https://example.com --depth 2 --max-pages 50

# Percorsi report personalizzati
xanalyze fullscan https://example.com \
  --styled-report ./reports/site.pdf \
  --report ./reports/agent.md

# Report in italiano
xanalyze fullscan https://example.com --language it
```

**Opzioni:**

| Opzione | Descrizione |
|---|---|
| `target` | URL, directory o file `.html` |
| `--url` | Tratta target come URL anche senza schema |
| `--depth N` | Profondità di crawl (default: 0) |
| `--max-pages N` | Pagine massime (default: 30) |
| `--max-files N` | File massimi (default: 5000) |
| `--ext ...` | Estensioni file da scansionare |
| `--exclude PATTERN` | Pattern gitignore-style di esclusione (ripetibile) |
| `--no-default-excludes` | Non saltare `node_modules/`, `dist/`, `.git/` ecc. |
| `--detector DETECTOR` | Detector pattern AI: `offline`, `embedding`, `hybrid`, `llm-judge` |
| `--scope SCOPE` | Cosa leggere: `content`, `technical`, `both` |
| `--no-typography` | Lasciare em dash e virgolette curly |
| `--breakpoints NAMES` | Responsive breakpoints: `all`, `desktop`, `tablet`, `mobile` |
| `--styled-report PATH` | Percorso report PDF/HTML brandizzato |
| `--report PATH` | Percorso briefing agente (.md o .json) |
| `--check` | Uscita 1 quando trovati problemi critici/gravi |
| `--language LANG` | Lingua report: `uk`, `it`, `en` |

---

### `scan` - Rilevamento pattern AI

Scansiona file per pattern di testo generato da AI e caratteri non da tastiera senza modificarli.

```bash
# Scansiona una directory
xanalyze scan ./src

# Con detector specifico
xanalyze scan ./src --detector offline

# Solo contenuto (non commenti)
xanalyze scan ./src --scope content

# Output JSON per CI/CD
xanalyze scan ./src --json --check

# Scansione incrementale (solo file modificati)
xanalyze scan ./src --incremental

# Report stilizzato
xanalyze scan ./src --styled-report report.pdf --language it
```

**Opzioni:**

| Opzione | Descrizione |
|---|---|
| `paths` | File o directory da scansionare |
| `--ext ...` | Estensioni (default: `.html .htm .xml .jsx .tsx .vue .svelte .js .ts .mjs .cjs`) |
| `--exclude PATTERN` | Pattern gitignore-style aggiuntivo |
| `--no-default-excludes` | Non saltare `node_modules/`, `dist/` ecc. |
| `--max-files N` | File massimi |
| `--detector DETECTOR` | Detector contenuto (vedi [Detector](#detector)) |
| `--provider PROVIDER` | Provider AI: `anthropic`, `xformat`, `claude-code` |
| `--no-unicode` | Salta controllo caratteri non da tastiera |
| `--scope SCOPE` | `content` (copia utente), `technical` (commenti), `both` |
| `--categories CATS` | Separati da virgola: `invisible,space,homoglyph,styled,typography` |
| `--no-typography` | Lasciare em dash e virgolette curly |
| `--no-ignore` | Segnalare tutto, incluso risultati soppressi |
| `--json` | Output JSON |
| `--check` | Uscita 1 quando trovati risultati (per hooks e CI) |
| `--incremental` | Solo file modificati dall'ultima scansione |
| `--styled-report PATH` | Report PDF/HTML brandizzato |
| `--language LANG` | Lingua report: `uk`, `it`, `en` |

---

### `audit` - Accessibilità, SEO, Performance

Esegue audit di URL, file HTML o repository per accessibilità, SEO, performance e best practice.

```bash
# Audit di un sito
xanalyze audit https://example.com

# Audit con rendering browser (per siti SPA/React/Vue)
xanalyze audit https://example.com --browser

# Audit con responsive breakpoints
xanalyze audit https://example.com --browser --breakpoints all

# Solo desktop
xanalyze audit https://example.com --browser --breakpoints desktop

# Audit di un file HTML locale
xanalyze audit ./page.html --browser

# Audit di un repository (no browser)
xanalyze audit ./src

# Solo categoria accessibilità
xanalyze audit https://example.com --category accessibility

# Solo SEO e performance
xanalyze audit https://example.com --category seo performance

# Con passaggio AI (controlla alt text, link text, headings)
xanalyze audit https://example.com --ai

# Auto-correzione problemi noti
xanalyze audit ./src --fix

# Output JSON
xanalyze audit https://example.com --json

# Briefing agente
xanalyze audit https://example.com --report briefing.md
```

**Opzioni:**

| Opzione | Descrizione |
|---|---|
| `target` | URL, directory o file `.html` |
| `--url` | Tratta target come URL anche senza schema |
| `--depth N` | Profondità crawl (default: 0) |
| `--max-pages N` | Pagine massime (default: 30) |
| `--max-files N` | File massimi (default: 5000) |
| `--render MODE` | Rendering browser: `never`, `auto`, `always` |
| `--exclude ...` | Pattern di esclusione |
| `--no-default-excludes` | Non saltare esclusioni default |
| `--category CATS` | Filtra categorie: `accessibility`, `performance`, `seo`, `best-practices` |
| `--language LANG` | Lingua output: `uk`, `it`, `en` |
| `--no-ignore` | Segnalare tutto |
| `--json` | Output JSON |
| `--check` | Uscita 1 su problemi critici/gravi |
| `--ai` | Esegui passaggio AI (costa token) |
| `--provider PROVIDER` | Override provider AI |
| `--fix` | Scrivi correzioni nei file |
| `--report PATH` | Briefing agente (.md o .json) |
| `--browser` | Carica pagine in browser reale |
| `--breakpoints NAMES` | Larghezze responsive: `all`, `desktop`, `tablet`, `mobile` |
| `--styled-report PATH` | Report PDF/HTML brandizzato |

---

### `fix` - Applica correzioni

Sovrascrive caratteri non da tastiera, mantenendo copie `.bak`.

```bash
# Correggi tutti i file in una directory
xanalyze fix ./src

# Correggi file specifici
xanalyze fix ./src/index.html ./src/about.html
```

---

### `undo` - Annulla correzioni

Riporta i file allo stato prima di `fix`.

```bash
# Annulla correzioni in una directory
xanalyze undo ./src

# Annulla file specifici
xanalyze undo ./src/index.html
```

---

### `cache` - Gestione cache

```bash
# Statistiche cache
xanalyze cache stats

# Pulisci cache
xanalyze cache clear

# Percorso file cache
xanalyze cache path
```

---

### `compare` - Confronta detector

Esegue diversi detector sugli stessi file e confronta i risultati.

```bash
xanalyze compare ./src
```

---

### `ai` - Operazioni AI

Gestione account AI e operazioni AI.

```bash
# Stato account
xanalyze ai status

# Accedi all'abbonamento xFormat
xanalyze ai login --email user@example.com

# Esci
xanalyze ai logout

# Elenco app connesse
xanalyze ai apps

# Concedi permesso a un'app
xanalyze ai grant my-app

# Revoca permesso
xanalyze ai revoke my-app

# Riscrivi un passaggio
xanalyze ai rewrite "Testo da riscrivere" --language it

# Riscrivi da stdin
echo "Del testo" | xanalyze ai rewrite
```

---

### `clean` - Filtro testo

Filtra testo da stdin a stdout, correggendo caratteri non da tastiera.

```bash
# Passa testo attraverso il filtro
echo "Testo con \u2018virgolette smart\u2019" | xanalyze clean

# Con suggerimento lingua
cat article.txt | xanalyze clean --language it
```

---

### `serve` - Server HTTP locale

Avvia un server HTTP locale per la modalità agent-as-judge.

```bash
# Avvia su porta default (8765)
xanalyze serve

# Porta personalizzata
xanalyze serve --port 9000

# Bind a tutte le interfacce
xanalyze serve --host 0.0.0.0
```

---

## Integrazione con agenti

**Per agenti LLM (Claude, ChatGPT, Cursor, ecc.):**

Chiedi: "Esegui una scansione completa con AI su https://example.com"

L'agente:
1. Esegue `xanalyze fullscan https://example.com --agent`
2. Ottiene i risultati JSON
3. Analizza i risultati
4. Genera un report

**Non serve una chiave API** — l'agente stesso funge da giudice.

**Come funziona:**
1. Il flag `--agent` avvia un server HTTP locale sulla porta 8765
2. L'agente invia testo a `POST /judge`
3. Il server restituisce un punteggio (0-1) di probabilità AI
4. Il server si arresta automaticamente dopo il completamento

**Endpoints:**
- `POST /judge` — Valuta il testo per pattern AI
- `GET /health` — Controllo salute
- `GET /detectors` — Elenco dei detector disponibili

---

## Metodi di rilevamento

### Rilevamento pattern AI

Combina più segnali per rilevare testo generato da AI:

#### Segnali statistici

1. **Burstiness (Uniformità)** — La scrittura umana varia la lunghezza delle frasi; il testo AI tende a essere uniforme
   - Misurato come coefficiente di variazione delle lunghezze delle frasi
   - Punteggio: 0 (bursty/umano) a 1 (uniforme/simile ad AI)
   - Peso: 40%

2. **Diversità lessicale (Ripetizione)** — Un basso type-token ratio indica formulazione stilistica
   - Misurato su passaggi di 20+ parole
   - Punteggio: 0 (diverso/umano) a 1 (ripetitivo/simile ad AI)
   - Peso: 35%

3. **Densità Em Dash** — Uso eccessivo di em/en dash come sostituto di virgole/parentesi
   - Normale: ~0.3 dash/100 parole; Pesante: >2/100 parole
   - Punteggio: 0 (normale) a 1 (pesante)
   - Peso: 25%

#### Frasi cliché

Elenchi estesi per lingua (100+ inglese, 80+ ucraino, 80+ italiano):
- Aperture e attenuazioni ("è importante notare", "it's important to note")
- Aperture temporali ("nel mondo di oggi", "in today's fast-paced world")
- Buzzword di marketing ("sblocca il potenziale", "unlock the potential")
- Copy di prodotto/interfaccia ("soluzione completa", "comprehensive solution")
- Singole parole marcatrici ("delve", "underscore", "pivotal", "realm")

#### Pattern strutturali

Rilevamento regex di costruzioni preferite dall'AI:
- "Non solo X, ma anche Y" / "Not just X, but Y"
- "Non si tratta di X, si tratta di Y" / "It's not about X, it's about Y"
- "Niente X. Niente Y. Solo Z." / "No X. No Y. Just Z."
- "Che tu sia X o Y" / "Whether you're X or Y"
- "Porta X a un nuovo livello" / "Take your X to the next level"

#### Formula di punteggio

```
base = media_pesata(uniformity, repetition, dashes)
remaining = 1 - base
for each cliché/pattern_strutturale:
    remaining *= (1 - weight)
punteggio = 1 - remaining
```

I segnali statistici senza cliché/pattern strutturali sono limitati a 0.32 per prevenire falsi positivi su testo tecnico.

---

### Caratteri non da tastiera

Rilevamento deterministico di caratteri non prodotti da tastiera:

| Categoria | Esempi | Punteggio |
|---|---|---|
| `invisible` | Spazi zero-width, joiners, trattini morbidi | 0.9 |
| `space` | Spazi non-breaking, spazi en/em | 0.7 |
| `homoglyph` | Cirillico а (U+0430) invece di latino a | 0.8 |
| `styled` | Varianti matematiche bold/italic | 0.6 |
| `typography` | Virgolette curly, em dash (opzionale) | 0.3 |

Ogni anomalia fornisce:
- Codepoint esatti (es. `U+200B`)
- Testo sostitutivo
- Categoria e descrizione

---

### Audit accessibilità

47 regole in 4 categorie. Le regole statiche operano su HTML analizzato; le regole browser su DOM renderizzato.

#### Regole accessibilità (25)

| Rule ID | Gravità | WCAG | Descrizione |
|---|---|---|---|
| `image-alt` | Critical | 1.1.1 | Le immagini devono avere attributo `alt` |
| `image-alt-filename` | Serious | 1.1.1 | `alt` non deve essere un nome file |
| `control-name` | Critical | 4.1.2, 2.4.4 | Elementi interattivi necessitano nomi accessibili |
| `link-text-vague` | Moderate | 2.4.4 | Evitare "clicca qui", "leggi di più" |
| `html-lang` | Serious | 3.1.1 | `<html>` deve avere `lang` |
| `document-title` | Serious | 2.4.2 | La pagina deve avere `<title>` |
| `heading-order` | Moderate | 1.3.1, 2.4.6 | Nessun livello di intestazione saltato |
| `page-has-h1` | Moderate | 1.3.1 | Esattamente un `<h1>` |
| `tabindex-positive` | Serious | 2.4.3 | Nessun `tabindex` positivo |
| `duplicate-id` | Moderate | 4.1.1 | Nessun `id` duplicato |
| `aria-reference-broken` | Serious | 1.3.1, 4.1.2 | I riferimenti ARIA devono funzionare |
| `button-type` | Minor | — | I pulsanti nei form necessitano `type` |
| `media-captions` | Serious | 1.2.2 | Video/audio necessitano sottotitoli |
| `media-autoplay` | Serious | 1.4.2 | Nessun autoplay senza controlli |
| `table-headers` | Serious | 1.3.1 | Tabelle dati necessitano `<th>` |
| `table-scope` | Moderate | 1.3.1 | `<th>` dovrebbe avere `scope` |
| `viewport-zoom` | Serious | 1.4.4 | Non bloccare lo zoom |
| `contrast-inline` | Serious | 1.4.3 | Contrasto colori inline (necessita browser) |
| `landmark-regions` | Moderate | 1.3.1, 2.4.1 | La pagina necessita landmark `<main>` |
| `skip-link` | Moderate | 2.4.1 | Il primo elemento focalizzabile deve saltare al contenuto |
| `form-error-message` | Serious | 3.3.1 | Campi non validi necessitano descrizione errore |
| `hreflang-links` | Minor | 3.1.2 | Siti multilingua necessitano hreflang |
| `breadcrumb-markup` | Minor | 1.3.1, 2.4.8 | I breadcrumb devono usare `<nav>` |
| `language-change` | Minor | 3.1.2 | Testo straniero inline necessita attributo `lang` |
| `abbreviation-expansion` | Minor | 3.1.4 | Le abbreviazioni devono usare `<abbr>` con `title` |

#### Regole solo browser (states pass)

| Rule ID | Gravità | Descrizione |
|---|---|---|
| `keyboard-trap` | Serious | Il focus non può lasciare l'elemento |
| `focus-not-visible` | Serious | Indicatore di focus invisibile |
| `focus-order-mismatch` | Moderate | Ordine tab non corrisponde all'ordine visivo |
| `hover-only-content` | Moderate | Contenuto visibile solo al passaggio mouse |
| `no-skip-link` | Moderate | Nessun link "salta al contenuto" |
| `focus-outside-viewport` | Moderate | Elemento focalizzato fuori schermo |

---

### Audit SEO

| Rule ID | Gravità | Descrizione |
|---|---|---|
| `seo-title-length` | Moderate | Title 15-60 caratteri |
| `seo-meta-description` | Moderate | Meta description 70-160 caratteri |
| `seo-canonical` | Moderate | Esattamente un link canonico |
| `seo-noindex` | Serious | Nessun noindex/nofollow accidentale |
| `seo-open-graph` | Minor | og:title, og:description, og:image |
| `seo-structured-data` | Minor | JSON-LD o microdata presenti |
| `seo-image-dimensions` | Minor | Le immagini necessitano width/height |
| `seo-empty-link` | Moderate | I link necessitano contenuto testuale |

---

### Audit performance

| Rule ID | Gravità | Descrizione |
|---|---|---|
| `perf-render-blocking` | Serious | Max 3 risorse bloccanti in `<head>` |
| `perf-third-party-sync` | Serious | Nessun script terze parti sincrono |
| `perf-large-inline` | Moderate | Inline style/script < 20KB |
| `perf-image-loading` | Minor | Immagini dopo la 3a dovrebbero essere lazy-loaded |
| `perf-font-display` | Moderate | I font necessitano `font-display: swap` |
| `perf-preconnect` | Minor | Preconnect a origin terze parti |
| `perf-layout-shift` | Moderate | Immagini lazy necessitano dimensioni |
| `image-modern-format` | Minor | Preferire WebP/AVIF a PNG/JPG |

---

### Best practice

| Rule ID | Gravità | Descrizione |
|---|---|---|
| `bp-mixed-content` | Serious | Nessuna risorsa HTTP su pagine HTTPS |
| `bp-target-blank` | Moderate | `target="_blank"` necessita `rel="noopener"` |
| `bp-charset` | Moderate | Dichiarare `charset="utf-8"` |
| `bp-doctype` | Moderate | Includere `<!DOCTYPE html>` |
| `bp-inline-handlers` | Minor | Nessun event handler inline |
| `bp-password-field` | Moderate | Campi password necessitano `autocomplete` |
| `bp-deprecated-html` | Minor | Nessun elemento deprecato (`<center>`, `<font>`) |
| `bp-ai-markup-artifact` | Minor | Nessuna classe vendor AI (`claude-*`, `data-gpt-*`) |

---

### Passaggio browser

Quando si usa `--browser` (automatico per `fullscan` su URL):

1. **Caricamento pagina** — Chromium reale tramite QtWebEngine
2. **Attesa settle** — 2500ms dopo il load per l'idratazione SPA
3. **axe-core** — Motore standard del settore per l'accessibilità (~27% copertura)
4. **HTML_CodeSniffer** — Controlli accessibilità aggiuntivi (~20% copertura)
5. **State Pass** — Focus, trap tastiera, contenuto hover-only
6. **Misurazioni** — FCP, tempo di caricamento, dimensione trasferimento, dimensione DOM
7. **Deduplicazione** — Stesse scoperte da più engine raggruppate in una riga

**Responsive Breakpoints:**

| Nome | Larghezza | Altezza |
|---|---|---|
| `desktop` | 1440px | 900px |
| `tablet` | 834px | 1112px |
| `mobile` | 390px | 844px |

Una scoperta vista a più larghezze diventa una riga che registra dove è stata vista. Una scoperta a una larghezza dice "solo su mobile" — utile per problemi specifici del responsive.

---

## Detector

| Detector | Tipo | Costo | Lingue | Descrizione |
|---|---|---|---|---|
| `offline` | Euristico | Gratuito | uk, it, en | Cliché + pattern strutturali + caratteri non da tastiera |
| `embedding` | Semantico | Gratuito | Qualsiasi | Similarità sentence-transformers |
| `claude-llm-judge` | LLM | A pagamento | Qualsiasi | Anthropic Claude API |
| `xformat-llm-judge` | LLM | A pagamento | Qualsiasi | Abbonamento xFormat |
| `claude-code-llm-judge` | LLM | A pagamento | Qualsiasi | Claude Code API |
| `hybrid` | Misto | A pagamento | uk, it, en | Prima offline, poi LLM estende |
| `none` | — | Gratuito | — | Salta rilevamento contenuto |

---

## Report

### Report stilizzato (PDF/HTML)

Report brandizzato e stampabile per persone:
- Riepilogo con conteggi gravità
- Scoperte raggruppate per categoria
- Frammenti di codice con correzioni
- Indicatori responsive breakpoint

```bash
xanalyze fullscan https://example.com --styled-report report.pdf
```

### Briefing agente (Markdown/JSON)

Briefing strutturato per coding agent:
- Statistiche e conteggi
- Scoperte per file
- Suggerimenti di correzione
- Tracciamento modifiche

```bash
xanalyze fullscan https://example.com --report briefing.md
```

### Output JSON

Output machine-readable per pipeline CI/CD:

```bash
xanalyze fullscan https://example.com --json
```

Struttura output:
```json
{
  "target": "https://example.com",
  "is_url": true,
  "language": "it",
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

## GUI

L'app desktop fornisce la stessa funzionalità con un'interfaccia visiva:

1. **Selezione sorgente** — URL sito, cartella repository o singolo file HTML
2. **Selezione reader** — Code (statico) o Browser (renderizzato)
3. **Selezione controlli** — Accessibilità, pattern AI o entrambi
4. **Selezione metodo** — Offline, AI o hybrid
5. **Progresso in tempo reale** — Aggiornamenti stato live
6. **Pannello scoperte** — Lista cliccabile con badge gravità
7. **Pannello dettagli** — Descrizione completa, frammento codice, suggerimento correzione
8. **Pannello anteprima** — Anteprima pagina con problemi evidenziati

---

## Configurazione

### File impostazioni

Posizione: `~/.config/xanalyze/settings.json`

```json
{
  "ui_language": "it",
  "llm_provider": "xformat",
  "max_pages": 30,
  "unicode_categories": ["invisible", "space", "homoglyph"],
  "unicode_check_enabled": true
}
```

### File ignore

Crea `.xanalyze-ignore` nella root del progetto (sintassi gitignore):

```
# Ignora codice vendored
vendor/
third_party/

# Ignora file generati
*.min.js
*.min.css
```

### Soppressioni

Sopprimi scoperte specifiche tramite impostazioni o `.xanalyze-ignore`:
- Per selettore CSS (escludi regioni)
- Per rule ID (disabilita regole)

---

## Disinstallazione

### CLI

```bash
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

---

## Requisiti

- Python 3.9+
- PySide6 (per GUI)
- sentence-transformers (per detector embedding)
- QtWebEngine (per passaggio browser)

---

## Licenza

MIT
