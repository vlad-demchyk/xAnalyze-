# XAnalyze (italiano)

Analizzatore desktop e headless per pattern di testo generato dall'AI, caratteri non digitabili e qualità di siti e repository.

[English](README.md) | [Українська](README_ua.md)

## Indice

- [Funzionalità](#funzionalità)
- [Avvio rapido](#avvio-rapido)
- [Utilizzo](#utilizzo)
- [Comandi CLI](#comandi-cli)
- [Template che comprende](#template-che-comprende)
- [Stack che riconosce](#stack-che-riconosce)
- [Analisi](#analisi)
- [Report ed esecuzioni](#report-ed-esecuzioni)
- [Interfacce](#interfacce)
- [Configurazione](#configurazione)
- [Limiti](#limiti)
- [Requisiti](#requisiti)
- [Licenza](#licenza)

## Funzionalità

XAnalyze scansiona siti, file HTML, repository e directory di codice indicando le posizioni esatte dei problemi.

- **Pattern AI**: detector offline, embedding, ibrido o basato su modello per il testo destinato agli utenti.
- **Caratteri**: zero-width, homoglyph, spazi insoliti, lettere stilizzate e tipografia.
- **Audit del sito**: accessibilità, SEO, performance, sicurezza e best practice.
- **Audit browser**: Chromium per applicazioni client-side e controllo responsive a 1440, 834 e 390 px.
- **Fatti del repository**: file `.env` tracciati o non ignorati, configurazioni e commit legati ad assistenti AI, blame dei risultati.
- **Provenienza media**: metadati IPTC/XMP e manifest C2PA opzionali. Sono fatti del file, non un verdetto sui pixel.
- **Cronologia**: pausa, ripresa, confronto e documenti di ogni esecuzione.

`fullscan` unisce controlli del testo, dei caratteri e del sito. Un repository locale viene analizzato staticamente, salvo usare `--devserver`.

Lo stack viene identificato dai file marcatori o dal markup servito. Entrambi gli elenchi sono verificati contro il codice dalla suite, quindi vivono in [Template che comprende](#template-che-comprende) e [Stack che riconosce](#stack-che-riconosce) invece di essere ripetuti qui.

## Avvio rapido

### GUI macOS

```bash
curl -L -o XAnalyze.app.zip https://github.com/vlad-demchyk/xAnalyze-/releases/latest/download/XAnalyze.app.zip
unzip XAnalyze.app.zip
mv XAnalyze.app /Applications/
```

### CLI macOS/Linux

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

python main.py                         # GUI
python cli.py fullscan https://example.com
```

## Utilizzo

```bash
xanalyze                                      # avvia la TUI
xanalyze fullscan https://example.com         # audit completo del sito
xanalyze scan ./src                           # pattern AI e caratteri
xanalyze audit https://example.com --browser  # audit del sito
xanalyze fix ./src                            # applica correzioni ai caratteri
xanalyze runs                                 # elenco e ripresa delle esecuzioni
xanalyze update                               # controlla gli aggiornamenti
xanalyze --version
```

## Comandi CLI

### `fullscan`

```bash
xanalyze fullscan https://xformat.net
xanalyze fullscan ./my-project
xanalyze fullscan https://example.com --depth 2 --max-pages 50
xanalyze fullscan https://example.com --breakpoints desktop,mobile
xanalyze fullscan https://example.com --detector hybrid --language it
xanalyze fullscan https://example.com --styled-report ./reports/site.pdf --report ./reports/agent.md
```

Per URL e HTML il rendering browser è automatico, salvo usare `--no-browser`. Per un'app locale, `--devserver` avvia un server Node, Django o Rails.

| Opzione | Scopo |
|---|---|
| `target` | URL, directory o file HTML |
| `--url` | Tratta il target come URL |
| `--depth N` | Profondità del crawl, predefinita `0` |
| `--max-pages N` | Numero massimo di pagine, predefinito `30` |
| `--max-files N` | Numero massimo di file locali, predefinito `5000` |
| `--ext ...` | Estensioni da analizzare |
| `--exclude PATTERN` | Esclusione aggiuntiva in sintassi gitignore |
| `--no-default-excludes` | Include le directory escluse normalmente |
| `--repo PATH` | Collega i risultati renderizzati ai file sorgente |
| `--devserver` | Avvia il server di sviluppo del repository |
| `--start-command CMD` | Sostituisce il comando del server |
| `--dev-server-port N` | Porta per server Django o Rails |
| `--yes` | Installa dipendenze mancanti senza chiedere |
| `--detector NAME` | `offline`, `embedding`, `hybrid`, `llm-judge` |
| `--model NAME` | Modello del passaggio AI |
| `--effort LEVEL` | `low`, `medium`, `high` |
| `--no-judgment-cache` | Non riutilizza i giudizi in cache |
| `--scope NAME` | `content`, `technical`, `both` |
| `--no-typography` | Ignora em dash e virgolette curve |
| `--breakpoints NAMES` | `all`, `desktop`, `tablet`, `mobile` o una lista |
| `--styled-report PATH` | Report PDF o HTML |
| `--report PATH` | Briefing Markdown o JSON |
| `--check` | Esce con stato 1 per problemi seri |
| `--language LANG` | `uk`, `it`, `en` |
| `--agent` | Prepara candidati offline per l'agente |
| `--no-browser` | Disabilita il rendering browser |

### `scan`

```bash
xanalyze scan ./src
xanalyze scan ./src --detector offline --scope content
xanalyze scan ./src --json --check
xanalyze scan ./src --incremental
xanalyze scan ./src --styled-report report.pdf --language it
```

Le opzioni principali sono `--ext`, `--exclude`, `--max-files`, `--detector`, `--provider`, `--no-unicode`, `--scope`, `--categories`, `--no-typography`, `--no-ignore`, `--json`, `--check`, `--incremental`, `--styled-report` e `--language`. Le categorie sono `invisible`, `space`, `homoglyph`, `styled`, `typography`.

### `audit`

```bash
xanalyze audit https://example.com
xanalyze audit https://example.com --browser --breakpoints all
xanalyze audit ./page.html --browser
xanalyze audit ./src --category accessibility
xanalyze audit https://example.com --category seo performance
xanalyze audit ./src --fix
xanalyze audit https://example.com --json --report briefing.md
```

Opzioni: `--depth`, `--max-pages`, `--max-files`, `--render`, `--exclude`, `--category`, `--language`, `--no-ignore`, `--json`, `--check`, `--ai`, `--provider`, `--fix`, `--report`, `--browser`, `--breakpoints`, `--styled-report`.

### `fix`, `undo`, `runs`, `resume`, `cache`, `compare`

```bash
xanalyze fix ./src
xanalyze undo ./src
xanalyze runs
xanalyze resume 2026-08-24-1331
xanalyze cache stats
xanalyze cache clear
xanalyze cache path
xanalyze compare ./src
```

`fix` crea copie `.bak`, `undo` le ripristina. Lo stato dell'esecuzione viene salvato per poterla riprendere.

### `logs`, `ai`, `clean`

```bash
xanalyze logs --level warning
xanalyze logs --json
xanalyze logs clean
xanalyze ai status
xanalyze ai login
xanalyze ai logout
echo "text" | xanalyze clean --language it
```

I log sono in `$XDG_STATE_HOME/xanalyze/logs` o `~/.local/state/xanalyze/logs`. `XANALYZE_LOG_DIR` cambia il percorso, `XANALYZE_LOG_LEVEL=debug` abilita i dettagli.

### `agent-scan` e `agent-judge`

```bash
xanalyze agent-scan ./src --json > passages.json
xanalyze agent-judge ./src --judgments verdicts.json
```

Il primo comando produce ID e testo dei candidati, il secondo applica i giudizi dell'agente e genera il report.

### `update` e `uninstall`

```bash
xanalyze update
xanalyze uninstall
```

La disinstallazione interattiva mostra i file che verranno rimossi. Usa l'opzione non interattiva solo quando la rimozione è voluta.

## Template che comprende

Quattordici linguaggi di template hanno una **coppia** di fixture in
`tests/fixtures/frameworks`: lo stesso componente scritto come vuole il suo
framework, e scritto male. La metà corretta non deve produrre alcun risultato e
quella rotta deve produrre quelli giusti, quindi questo elenco è
un'affermazione misurata, non un'intenzione:

`alpine`, `angular`, `blade`, `django`, `erb`, `handlebars`, `liquid`, `php`, `razor`, `react`, `svelte`, `thymeleaf`, `twig`, `vue`

È questo ciò contro cui la scansione è **verificata**. Il markup in qualsiasi
cosa non elencata viene comunque letto - il parser non lo rifiuta - ma nulla ha
dimostrato che un file corretto in quel linguaggio torni pulito, e un risultato
falso lì non verrebbe intercettato dalla suite.

## Stack che riconosce

Un progetto viene identificato dai suoi file marcatori, e ciò che risulta essere
decide cosa è codice di terzi anziché scritto qui:

`angular`, `astro`, `beehiiv`, `carrd`, `craft`, `django`, `docusaurus`, `dotnet`, `drupal`, `eleventy`, `ember`, `flutter`, `gatsby`, `ghost`, `hugo`, `jekyll`, `joomla`, `laravel`, `magento`, `nextjs`, `nuxt`, `qwik`, `rails`, `remix`, `shopify`, `silverstripe`, `spfx`, `spring`, `squarespace`, `statamic`, `storybook`, `sveltekit`, `symfony`, `typo3`, `vite`, `wagtail`, `webflow`, `wix`, `wordpress`

Le firme sono pesate, non contate: ognuna porta una confidenza e una piattaforma
viene nominata solo quando le corrispondenze sommano 100, quindi un marcatore che
potrebbe essere lì per un altro motivo va corroborato.

## Analisi

Il detector offline combina segnali statistici, struttura, cliché e regole linguistiche. I detector embedding e basati su modello aggiungono un giudizio indipendente. Ogni risultato contiene posizione, punteggio, spiegazione e certezza.

L'audit copre `accessibility` (29), `best-practices` (8), `performance` (8), `security` (10), `seo` (8) - numeri che la suite verifica contro il registro delle regole. La modalità statica legge i file; quella browser vede DOM renderizzato, contenuto client-side, stati responsive e header della risposta. `--repo` collega un audit URL al file sorgente.

I risultati hanno livello `exact` o `needs-browser`. `--confidence exact` conserva solo i fatti stabiliti dal markup.

La provenienza media legge IPTC/XMP e C2PA. I fatti del repository comprendono `.env`, commit e configurazioni degli assistenti AI e blame. Sono informazioni di provenienza, non difetti dell'uso di un assistente.

## Report ed esecuzioni

Per impostazione predefinita i documenti sono salvati in `~/Desktop/XAnalyze/`; `XANALYZE_REPORT_ROOT` cambia la directory principale.

```text
XAnalyze/example.com/2026-08-24-0930/
  report.md       briefing raggruppato per l'agente
  report.pdf      report per la persona
  timings.md      durata delle fasi
  changes.md      confronto con l'esecuzione precedente
  state.md        stato per la ripresa
  state.json      stato per programmi
```

```bash
xanalyze fullscan https://example.com --styled-report report.pdf
xanalyze fullscan https://example.com --report briefing.md
xanalyze fullscan https://example.com --json > run.json
```

Il report raggruppa lo stesso problema e mantiene tutte le posizioni. Gli identificatori dinamici dei framework vengono normalizzati solo negli attributi identificativi. `changes.md` confronta le esecuzioni; un numero minore di risultati può dipendere da un crawl più breve.

## Interfacce

La GUI offre controlli per target, tipo di analisi, detector, scope, profondità, breakpoint, lingua e account. I risultati includono elenco, anteprima, dettagli, correzioni ed esportazione. Le correzioni meccaniche sono selezionate in automatico, le bozze del modello richiedono revisione.

Eseguire `xanalyze` senza argomenti apre la TUI con Scan, Audit, Full Scan, Reports, Settings, Update e Uninstall. Navigazione: frecce, tasti numerici, `Tab`, `Esc`, `q`.

## Configurazione

File: `~/.config/xanalyze/settings.json`

```json
{
  "ui_language": "it",
  "llm_provider": "xformat",
  "max_pages": 30,
  "unicode_categories": ["invisible", "space", "homoglyph"],
  "unicode_check_enabled": true
}
```

`.xanalyze-ignore` nella root del progetto usa la sintassi gitignore:

```text
vendor/
third_party/
*.min.js
*.min.css
```

Si possono aggiungere le sezioni `[rules]`, `[selectors]`, `[fingerprints]`, oltre a frasi e percorsi. Commenti e righe vuote vengono conservati.

## Limiti

- Il detector AI dipende dal corpus e non dimostra l'autore; i giudizi del modello non sono deterministici.
- L'italiano è più debole sui passaggi brevi; per testi importanti usare hybrid o model-judged.
- **Il rilevamento del testo copre solo ucraino, italiano e inglese.** Un passaggio in un'altra lingua viene dichiarato tale e il passaggio sulle formulazioni e quello embedding non riportano nulla, invece di misurarlo con liste e un insieme di riferimento che quella lingua non la conoscono. Misurato su 257 paragrafi in tedesco, francese, spagnolo, polacco e russo: 249 vengono letti come lingua non supportata. I controlli sui caratteri, sulla tipografia e sull'audit non dipendono dalla lingua e continuano a funzionare, e un detector giudicato da un modello non ha questo limite.
- La scansione statica non vede contenuti creati durante il rendering. Usare URL o `--devserver`.
- Un solo breakpoint non descrive il comportamento responsive. Usare `--breakpoints all`.
- Il controllo tipografico può segnalare punteggiatura intenzionale e può essere disabilitato.
- `--scope technical` misura i segnali di caratteri e tecnici, non lo stile di marketing.
- C2PA richiede i pacchetti opzionali `c2pa-python` e `cryptography`.
- Nei terminali a 16 colori alcuni colori di gravità si fondono, ma le etichette testuali restano.

## Requisiti

- Python 3.14+
- PySide6 per la GUI
- sentence-transformers per il detector embedding
- QtWebEngine per il rendering browser
- `c2pa-python` e `cryptography` per C2PA

## Licenza

MIT
