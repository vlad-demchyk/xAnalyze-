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
  - [agent-scan](#agent-scan---scansione-offline-per-agente)
  - [agent-judge](#agent-judge---unione-giudizi-agente)
  - [update](#update---aggiornamento-automatico)
- [Flag globali](#flag-globali)
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
- [Per agenti AI](#per-agenti-ai)
- [GUI](#gui)
- [TUI (Interfaccia terminale)](#tui-interfaccia-terminale)
- [Configurazione](#configurazione)
- [Disinstallazione](#disinstallazione)
- [Requisiti](#requisiti)
- [Licenza](#licenza)

---

## Funzionalità

- **Rilevamento pattern AI** — euristico (cliché, pattern strutturali, burstiness) e basato su embedding (sentence-transformers)
- **Caratteri non da tastiera** — spazi zero-width, virgolette curly, em dash, omoglifi
- **Audit accessibilità** — regole WCAG, SEO, performance, best practice (52 regole)
- **Scansione completa** — pattern AI + accessibilità in un comando con rendering browser automatico
- **Report stilizzati** — PDF/HTML brandizzati per persone
- **Briefing per agenti** — markdown/JSON per coding agent
- **CLI + GUI + TUI** — un binario, tre interfacce
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

## Utilizzo

### TUI interattivo

Basta digitare `xanalyze` senza argomenti per avviare l'interfaccia terminale interattiva:

```bash
xanalyze
```

Il TUI fornisce un menu con:
- **Scan** — rilevamento pattern AI e caratteri non da tastiera
- **Audit** — controllo accessibilità, SEO, performance
- **Full Scan** — tutto in un'esecuzione
- **Reports** — visualizza risultati precedenti
- **Settings** — ispeziona configurazione
- **Update** — controlla nuove versioni

Navigazione con frecce o tasti rapidi (1-7). Il footer elenca i tasti che lo
schermo accetta. `Esc` torna indietro, `q` esce.

### Comandi CLI

```bash
# Scansione directory per pattern AI
xanalyze scan ./src

# Audit sito per accessibilità
xanalyze audit https://example.com --browser

# Scansione completa (AI + accessibilità + SEO)
xanalyze fullscan https://example.com

# Correggi caratteri non da tastiera
xanalyze fix ./src

# Controlla aggiornamenti
xanalyze update

# Mostra versione
xanalyze --version
```

### Aggiornamento automatico

```bash
# Controlla e installa l'ultima versione
xanalyze update
```

Ogni comando CLI controlla anche gli aggiornamenti una volta al giorno e mostra un suggerimento se esiste una versione più recente. Disattivare con `--no-update-check`.

---

### `fullscan` - Scansione completa

Il comando principale per l'analisi completo. Combina rilevamento pattern AI, audit accessibilità, SEO, performance e best practice in un'unica esecuzione.

**Comportamento automatico per URL e file HTML:**
- Rendering browser abilitato (gestisce React, Vue, Next.js, ecc.)
- Responsive breakpoints: desktop (1440px), tablet (834px), mobile (390px)
- Output JSON per l'agente
- Ogni documento salvato in una cartella per questo target sul Desktop

**Dove finiscono i documenti.** Una cartella per target, una sottocartella per
esecuzione:

```
~/Desktop/XAnalyze/example.com/
    2026-08-24-0930/
        report.md        briefing per l'agente e l'elenco raggruppato dei problemi
        report.pdf       il report brandizzato per una persona
        timings.md       quanto è durata ogni fase
        changes.md       cosa è cambiato dall'esecuzione precedente
    2026-08-24-1145/
        ...
```

`changes.md` appare dalla seconda esecuzione di un target in poi e risponde alla
domanda che una ri-esecuzione sta ponendo: quanti punti sono stati corretti,
quali regole hanno smesso di scattare e quali sono comparse. `XANALYZE_REPORT_ROOT`
sposta la radice delle cartelle fuori dal Desktop.

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

### Le quattro cose che si chiedono davvero

`fullscan` ha molti flag perché sa fare molto. Queste sono le forme da
ricordare; il resto è una variazione di una di queste.

```bash
# 1. "Controlla il mio sito per bene." Dieci pagine, tutte e tre le larghezze,
#    un modello che legge i testi. I quattro flag sono le quattro decisioni:
#    quanto, quanto in profondità, quanto in larghezza, chi legge.
xanalyze fullscan mysite.com --max-pages 10 --depth 2 --detector ai --breakpoints all

# 2. "Controlla velocemente." Default: 30 pagine, profondità 1, solo desktop,
#    offline.
xanalyze fullscan mysite.com

# 3. "Controlla questo codice." Niente crawl, niente browser.
xanalyze fullscan ./my-project

# 4. "Che cosa ho eseguito, e posso riprendere?"
xanalyze runs
xanalyze resume 2026-08-24-1331
```

**`--detector ai`** è la grafia naturale e funziona; `llm-judge` e `judge`
sono la stessa cosa. Nessuna dice a quale account viene addebitato: quello
viene dalle impostazioni, e l'esecuzione stampa il giudice a cui è arrivata
(`# [stage] AI patterns: claude-code-llm-judge`), così la risposta sta nel log
e non nella memoria. `xanalyze ai status` dice che cosa è disponibile.

**I default sono uno sguardo rapido, non accurato.** Profondità 1 e solo
desktop sono scelti perché un `fullscan` senza flag finisca in un minuto o due.
Un audit vero è la ricetta 1, e su un sito di dieci pagine richiede circa
cinque minuti, di cui ~90% è il passaggio col browser a tre larghezze.
`timings.md` lo mostra.

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
| `--incremental` | Rilegge solo i file cambiati dall'ultima scansione con le stesse impostazioni. La cache è indicizzata su data di modifica e dimensione del file **e** su detector, scope e categorie, quindi cambiarne uno rilegge tutto. Un rilievo riproposto dalla cache non può comparire in `--styled-report`, che si costruisce dagli span vivi; l'esecuzione lo dichiara |
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

### `agent-scan` - Scansione offline per agente

Esegue la scansione offline e restituisce i candidati come JSON per la valutazione dell'agente.

```bash
# Modalità semplice: solo candidati
xanalyze agent-scan ./src --json

# Modalità completa: candidati + tutti i blocchi per analisi indipendente
xanalyze agent-scan ./src --full --json

# Soglia personalizzata
xanalyze agent-scan ./src --threshold 0.3 --json
```

---

### `agent-judge` - Unione giudizi agente

Combina la scansione offline con i giudizi LLM dell'agente in un report finale.

```bash
# Unione semplice: l'agente ha valutato i candidati
xanalyze agent-scan ./src --json | xanalyze agent-judge ./src --judgments -

# Unione ibrida: l'agente ha valutato + trovato indipendentemente
xanalyze agent-scan ./src --full --json | xanalyze agent-judge ./src --judgments -
```

---

### `update` - Aggiornamento automatico

Controlla GitHub Releases per una versione più recente e sostituisce il binario CLI sul posto.

```bash
# Controlla e installa aggiornamento
xanalyze update
```

Quando si esegue da source (`python cli.py`), mostra il link di download invece di sostituire.

**Controllo automatico aggiornamenti:** Ogni comando CLI controlla gli aggiornamenti una volta al giorno (non bloccante, stampa una riga su stderr se esiste una versione più recente). Disattivare con `--no-update-check`.

---

## Esecuzioni: pausa, arresto, ripresa

Una scansione completa di un sito grande è un lavoro lungo. Un sito di 192
pagine richiedeva quarantasei minuti, per lo più nel passaggio col browser, ed
era tutto o niente: se qualcosa falliva prima dell'ultima riga, l'esecuzione
non scriveva nulla e quei quarantasei minuti erano persi.

Ora ogni fase si registra nel momento in cui cambia stato, quindi
un'esecuzione che si ferma conserva ciò che ha calcolato e può riprendere.

```bash
# Quali esecuzioni esistono e quali si possono riprendere
xanalyze runs

# Riprendere dalla prima fase non completata
xanalyze resume 2026-08-24-0930

# Chiedere a una scansione in corso di fermarsi al confine della fase successiva
xanalyze pause 2026-08-24-0930
```

Un'esecuzione interrotta esce con codice **3** (non 2, che continua a
significare invocazione sbagliata) e stampa su stdout un blocco leggibile da
una macchina: cosa si è fermato, perché, quali fasi sono complete, quali file
sono già su disco e l'unico comando che prosegue. È questo il punto: un agente
legge il motivo, lo corregge ed emette quel comando. Le fasi completate non
vengono ricalcolate, perché crawl e audit si rileggono dalla cartella.

La GUI mostra lo stesso catalogo nella colonna dei comandi, con **Riprendi**,
**Pausa** e **Apri cartella**. Percorre le stesse cartelle della CLI invece di
tenere un elenco proprio, quindi le due non possono divergere.

### Il watchdog del render

La stampa del PDF è l'unica fase priva di un segnale di avanzamento proprio, ed
era governata da un limite fisso di 30 secondi. Quel limite uccideva un report
di 158 pagine che da solo si stampa in 108 secondi, portandosi via l'intero
risultato dell'esecuzione. Togliere il limite ha tolto anche il pavimento: un
processo di render morto restava appeso per sempre.

Nessuno dei due misurava se il render stesse lavorando, perché il tempo
trascorso non può dirlo. Ora ci si ferma sull'**assenza di progresso**:

| evidenza | cosa succede |
|---|---|
| il processo di render è morto | si ferma subito, con lo stato di uscita nel messaggio |
| l'avanzamento del caricamento è cambiato | si prosegue |
| il processo di render ha usato più CPU del controllo precedente | si prosegue |
| nulla di quanto sopra per 45 secondi | si ferma, nominando la fase e il silenzio |

Un render che sta lavorando non viene mai interrotto, per quanto duri. Se il
processo di render non è osservabile, il messaggio lo dichiara invece di
tornare silenziosamente a essere un timer fisso.

### Quando il PDF non si stampa comunque

La stampa è l'**ultimo** passo di un'esecuzione. Quando può fallire i rilievi
sono già completi e `report.md` è già scritto: un PDF fallito è una conversione
fallita, non un'esecuzione fallita, e non ferma più nulla.

Al suo posto il file che ti aspettavi compare ugualmente, come una pagina
sostitutiva che dice dove si trova il report Markdown e porta i numeri
principali, così da essere un riepilogo utile e non una pagina di scuse. Se
nemmeno quella si stampa, lo stesso avviso viene scritto accanto come `.html`:
un browser lo apre, mentre un PDF da zero byte non lo apre nessuno.

### Come è impaginato il report

Tre cose decidono se un report lungo si legge, e tutte e tre erano sbagliate:

**Le interruzioni di pagina seguono ciò che deve restare unito, non ciò che
sembra ordinato.** `break-inside: avoid` su ogni scheda è la regola ovvia ed è
quella sbagliata: una scheda alta che non entrava nello spazio rimasto passava
intera alla pagina successiva, e lo spazio lasciato restava bianco. Su un report
di 120 rilievi questo costava il **9% delle pagine**. Ciò che deve davvero
valere è più stretto: un titolo non è mai l'ultima cosa di una pagina, una riga
isolata non ne apre né chiude una, e i blocchi piccoli (un campo, una riga di
tabella, una barra del grafico) restano interi. Schede e tabelle possono
spezzarsi.

**Una tabella, non quattro.** I conteggi per categoria, le fasce di confidenza
dei pattern AI e i conteggi dei caratteri erano tre tabelle in tre sezioni
separate dai rilievi, quindi chi si chiedeva "che tipo di cose ha trovato"
doveva tenere a mente tre punti e non li vedeva mai accanto. Rispondono a una
sola domanda e ora stanno in una sola risposta, sotto **Che cosa è stato
trovato**, con una colonna che dice da quale passaggio viene ogni riga.

**L'indice di ciò che è stato esaminato è contesto, non contenuto.** Un crawl di
192 pagine stampava 192 righe numerate in corpo testo prima del primo rilievo,
circa cinque pagine di indice. Ora è una tabella in 8pt, ordinata in modo che le
pagine con più problemi vengano prima, troncata dopo 40 righe mantenendo il
conteggio completo, e collocata **dopo** i rilievi. Stessa esecuzione: **due
pagine invece di cinque**.

La panoramica si apre inoltre con due grafici a barre, per gravità e per
categoria, perché i conteggi in tabella sono esatti ma senza forma, e chi legge
vuole vedere dove sta il peso prima di leggere un numero. Sono CSS puro, senza
script e senza immagini, perché il consumatore è `printToPdf` e il resto a volte
stampa in bianco.

---

## Flag globali

| Flag | Descrizione |
|---|---|
| `--no-update-check` | Salta il controllo automatico giornaliero della versione |

`--no-update-check` è accettato prima del sottocomando e dopo, a qualsiasi
profondità: `xanalyze --no-update-check scan .`, `xanalyze scan . --no-update-check`
e `xanalyze cache stats --no-update-check` funzionano allo stesso modo.
`--version` appartiene al programma, quindi va per prima.
| `--version` | Stampa la versione ed esci |

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

52 regole in 4 categorie: 28 accessibilità, 8 SEO, 8 performance, 8 best practice.
Le regole statiche operano su HTML analizzato; le regole browser su DOM renderizzato.

#### Regole accessibilità (28)

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
| `viewport-fixed-width` | Moderate | 1.4.10 | Nessuna `width:` fissa su un contenitore: costringe a scorrere di lato sul telefono |
| `viewport-tiny-font` | Serious | 1.4.4 | Nessun corpo di testo sotto la soglia leggibile |
| `viewport-touch-target` | Minor | 2.5.8 | Bersagli di tocco abbastanza grandi da centrare |
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

### Un problema, per quante pagine lo portino

Un crawl di trenta pagine che condividono un header trova ogni difetto di quel
header trenta volte. Sono trenta punti e un problema, e i report lo dicono: ogni
problema distinto è elencato una volta, con sotto ogni punto in cui è stato
trovato. Niente viene scartato — una correzione deve visitare ciascuno di quei
punti — ed entrambi i numeri sono riportati, perché rispondono a domande diverse:

```
| critical | serious | moderate | minor | total | distinct problems |
|---|---|---|---|---|---|
| 0 | 3 | 64 | 3 | 70 | 14 |
```

Due rilievi contano come un problema quando regola, gravità e markup incriminato
coincidono. Due immagini diverse senza `alt` restano due problemi; lo stesso logo
condiviso su cinque pagine è uno.

L'elenco completo per documento resta per ciò che analizza invece di leggere:
salva il briefing con estensione `.json` e lo trovi sotto `files`.

### Report stilizzato (PDF/HTML)

Report brandizzato e stampabile per persone:
- Riepilogo con conteggi gravità
- Una scheda per problema distinto, con ogni punto in cui compare
- Frammenti di codice con correzioni
- Indicatori responsive breakpoint

```bash
xanalyze fullscan https://example.com --styled-report report.pdf
```

### Briefing agente (Markdown/JSON)

Briefing strutturato per coding agent:
- Statistiche e conteggi
- L'elenco raggruppato dei problemi, i più gravi e diffusi per primi
- La mappa per documento (forma `.json`)
- Suggerimenti di correzione
- Confronto con l'esecuzione precedente dello stesso target

```bash
xanalyze fullscan https://example.com --report briefing.md
```

### Confronto con l'esecuzione precedente

Ogni esecuzione è registrata per target in `~/.xanalyze/history/`, indicizzata su
cosa è stato scansionato e quale analisi è girata — così una seconda esecuzione
dello stesso target è confrontata con la prima, qualunque sia il nome del report.
`fullscan` scrive il confronto anche come documento a sé, `changes.md`, nella
cartella dell'esecuzione:

```
| | previous | now | change |
|---|---|---|---|
| findings | 70 | 67 | down 3 |

**3 place(s) corrected**, 0 new one(s) appeared.

| rule | previous | now | change |
|---|---|---|---|
| `image-alt` | 5 | 2 | down 3 |
```

*Findings* si muove anche quando il crawl raggiunge un numero diverso di pagine,
e quello non è progresso. *Places corrected* e la tabella per regola sono i
numeri che tracciano il lavoro fatto: una regola scatta in meno punti solo quando
qualcosa è stato davvero corretto.

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

## Per agenti AI

Questa sezione descrive come usare xanalyze da un agente AI (Claude, ChatGPT, Copilot, ecc.) per analizzare siti web e codebase.

### Riferimento rapido

```bash
# Scansione completa di un sito (tutto automatico)
xanalyze fullscan https://example.com

# Scansione completa di un repository
xanalyze fullscan ./my-project

# Controllo rapido accessibilità
xanalyze audit https://example.com --browser --json

# Scansione codice per pattern AI
xanalyze scan ./src --json

# Correzione caratteri non da tastiera
xanalyze fix ./src
```

### Task comuni

#### 1. Analizzare un sito (scansione completa)

```bash
xanalyze fullscan https://example.com
```

**Cosa fa:**
- Crawla il sito (con rendering browser per SPA)
- Esegue audit accessibilità (52 regole)
- Esegue audit SEO
- Esegue audit performance
- Controlla pattern di testo generato da AI
- Controlla caratteri non da tastiera
- Genera output JSON + report PDF + briefing agente

**Output:** JSON su stdout, documenti nella cartella di questo target sul Desktop

#### 2. Analizzare un codebase

```bash
xanalyze fullscan ./my-project
```

**Cosa fa:**
- Scansiona tutti i file markup (HTML, JSX, TSX, Vue, Svelte, ecc.)
- Scansiona file locale (JSON, YAML)
- Scansiona file backend (Python, PHP, Ruby, Go, Java, C#)
- Controlla testo generato da AI in copia e commenti
- Controlla caratteri non da tastiera
- Esegue audit accessibilità su file HTML

#### 3. Controllo rapido accessibilità

```bash
xanalyze audit https://example.com --browser --json
```

**Cosa fa:**
- Carica la pagina in un browser reale (gestisce SPA)
- Esegue axe-core + HTML_CodeSniffer
- Controlla focus tastiera, contrasto, ARIA
- Restituisce JSON con tutti i problemi

#### 4. Controllare categoria specifica

```bash
# Solo problemi di accessibilità
xanalyze audit https://example.com --category accessibility --json

# Solo problemi SEO
xanalyze audit https://example.com --category seo --json

# Solo problemi di performance
xanalyze audit https://example.com --category performance --json
```

#### 5. Scansionare per pattern AI

```bash
xanalyze scan ./src --json
```

**Cosa fa:**
- Scansiona file per frasi cliché, pattern strutturali
- Controlla caratteri non da tastiera (zero-width, omoglifi)
- Restituisce risultati con punteggi e spiegazioni

#### 6. Correzione automatica

```bash
# Correggi caratteri non da tastiera
xanalyze fix ./src

# Auto-correzione problemi accessibilità (dove possibile)
xanalyze audit ./src --fix
```

#### 7. Confronta detector

```bash
xanalyze compare ./src --json
```

**Cosa fa:**
- Esegue diversi detector sugli stessi file
- Confronta i risultati
- Mostra quale detector trova cosa

### Modalità agente-come-giudice

L'agente stesso agisce come giudice LLM (non serve chiave API). Due modalità:

**Semplice — validare i ritrovamenti offline:**
```bash
# Passo 1: scansione offline → candidati
xanalyze agent-scan ./src --json > candidates.json

# Passo 2: l'agente valuta i candidati, restituisce i giudizi
echo '[{"block_id":"...","score":0.8,"reason":"AI cliché"}]' | \
  xanalyze agent-judge ./src --judgments -
```

**Completo — analisi ibrida (l'agente legge tutto):**
```bash
# Passo 1: scansione offline + tutti i blocchi per l'agente
xanalyze agent-scan ./src --full --json > scan.json

# Passo 2: l'agente valuta i candidati E legge i blocchi indipendentemente

# Passo 3: unione con logica ibrida
cat agent_output.json | xanalyze agent-judge ./src --judgments -
```

**Fullscan con agente:**
```bash
xanalyze fullscan ./repo --agent --json
```

**Opzioni LLM Judge:**

| Detector | Comando | Chiave API |
|---|---|---|
| Agente (validazione) | `xanalyze agent-scan ./src --json` | Non necessaria |
| Agente (ibrido completo) | `xanalyze agent-scan ./src --full --json` | Non necessaria |
| Claude API | `xanalyze scan ./src --detector claude-llm-judge` | `ANTHROPIC_API_KEY` |
| xFormat | `xanalyze scan ./src --detector xformat-llm-judge` | Login xFormat |
| Claude Code | `xanalyze scan ./src --detector claude-code-llm-judge` | Sessione Claude Code |
| Hybrid | `xanalyze fullscan URL --detector hybrid` | Opzionale |

### Esempi di workflow agente

#### Esempio 1: Audit e correzione sito

```bash
# Passo 1: Scansione completa
xanalyze fullscan https://example.com --json > scan.json

# Passo 2: Rivedi risultati
cat scan.json | jq '.audit.counts'

# Passo 3: Ottieni problemi dettagliati
cat scan.json | jq '.audit.issues[] | select(.severity == "critical" or .severity == "serious")'

# Passo 4: Genera suggerimenti correzione
xanalyze audit https://example.com --browser --report fixes.md
```

#### Esempio 2: Scansione e pulizia codebase

```bash
# Passo 1: Scansiona per problemi
xanalyze scan ./src --json > scan.json

# Passo 2: Controlla cosa è stato trovato
cat scan.json | jq '.counts'

# Passo 3: Correggi caratteri non da tastiera
xanalyze fix ./src

# Passo 4: Verifica correzioni
xanalyze scan ./src --json | jq '.counts'
```

#### Esempio 3: Integrazione CI/CD

```bash
# In pipeline CI - fallisci su problemi critici
xanalyze fullscan https://staging.example.com --check --json

# Codice uscita 0 = nessun problema critico/grave
# Codice uscita 1 = problemi critici/gravi trovati
```

### Struttura output JSON

```json
{
  "target": "https://example.com",
  "is_url": true,
  "language": "it",
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
          "language": "it"
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

### Livelli di gravità

| Livello | Significato | Azione |
|---|---|---|
| `critical` | Blocca completamente gli utenti | Correggere immediatamente |
| `serious` | Contenuto perso o inutilizzabile | Correggere presto |
| `moderate` | Più difficile da usare | Correggere quando possibile |
| `minor` | Odore, può essere intenzionale | Considerare correzione |

### Codici di uscita

| Codice | Significato |
|---|---|
| 0 | Successo, nessun problema critico/grave (con `--check`) |
| 1 | Problemi critici/gravi trovati (con `--check`) |
| 2 | Errore (argomenti non validi, file non trovato, ecc.) |

### Suggerimenti per agenti

1. **Usa sempre `--json`** per output machine-readable
2. **Usa `--check`** in CI/CD per fallire su problemi critici
3. **Usa `fullscan`** per analisi completa
4. **Usa `audit --browser`** per siti SPA/React/Vue
5. **Usa `scan`** per controllo rapido pattern AI
6. **Usa `fix`** per auto-correzione caratteri non da tastiera
7. **Parsa `summary`** per panoramica rapida
8. **Parsa `audit.issues`** per risultati dettagliati
9. **Controlla `fix_snippet`** per correzioni suggerite
10. **Usa `--language`** per report localizzati

---

## GUI

L'app desktop risponde alle stesse domande della CLI, con i controlli in una
colonna a sinistra e i risultati accanto.

**La colonna dei controlli**

1. **Sorgente** — URL del sito, cartella del repository o singolo file HTML.
   Anche un host senza schema va bene
2. **Controllo** — accessibilità, pattern AI o entrambi (entrambi per default)
3. **Metodo** — offline, embedding, AI oppure offline + AI. Le voci con AI
   compaiono solo quando c'è un account o una chiave che le paghi
4. **Scope** (cartelle) — il testo che arriva all'utente, i commenti e le
   docstring, o entrambi
5. **Profondità** (siti) — quanto lontano il crawl segue i link
6. **Account** — chi paga un passaggio AI, e se qualcuno ha effettuato l'accesso

**I risultati**

7. **Anteprima** — la pagina renderizzata, o il file sorgente, con il rilievo
   evidenziato o la sua riga marcata. Si può fissare a larghezza desktop, tablet
   o mobile, così un rilievo trovato a una larghezza si guarda a quella larghezza
8. **Lista dei rilievi** — badge di gravità, una riga per problema distinto. Un
   problema trovato in più file dice in quanti, invece di ripetersi
9. **Dettaglio** — cosa è stato trovato, perché conta, come correggerlo,
   l'elemento, la sostituzione pronta e ogni punto in cui lo stesso problema
   compare
10. **Azioni** — correggi i caratteri, genera l'elenco delle sostituzioni,
    riscrivi sul posto, scrivi su disco una correzione dell'audit, annullala,
    esporta il report

La finestra ripiega una colonna alla volta mentre si restringe: prima la colonna
dei dettagli (che ricompare sotto la riga cliccata), poi l'anteprima.

---

## TUI (Interfaccia terminale)

Quando si esegue `xanalyze` senza argomenti, si avvia un'interfaccia terminale interattiva:

```bash
xanalyze          # avvia TUI
python cli.py     # stesso, da source
```

Il TUI fornisce:
- **Scan** — configura ed esegui il rilevamento pattern AI
- **Audit** — configura ed esegui audit accessibilità/SEO/performance
- **Full Scan** — analisi combinata in un'esecuzione
- **Reports** — ogni esecuzione registrata; `Enter` apre il report di quella
- **Settings** — leggi e modifica la configurazione
- **Update** — controlla e installa una nuova versione
- **Uninstall** — rimuovi XAnalyze da questa macchina

Ogni esecuzione avviene su un thread di lavoro, così l'interfaccia continua a
rispondere mentre un crawl macina, e il suo avanzamento compare nella riga di
stato. Al termine, il risultato è mostrato nell'interfaccia — un riepilogo, i
documenti scritti e il log completo — non lasciato nel terminale sotto.

Navigazione con frecce o tasti 1-7; anche `Tab` sposta tra i controlli. Il
footer elenca i tasti che lo schermo corrente accetta. `Esc` torna indietro,
`q` esce.

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
