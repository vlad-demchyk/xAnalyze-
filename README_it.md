# XAnalyze (Italiano)

Desktop e headless analyzer: rilevamento di testi generati da AI, caratteri non da tastiera e audit completo dell'accessibilità di siti/repository.

[English](README.md) | [Українська](README_ua.md)

---

## Perché esiste XAnalyze

**A che cosa serve.** Una sola esecuzione risponde a due domande su un sito o un repository di cui
sei responsabile: *questo testo l'ha scritto un modello* e *questa pagina funziona davvero per le
persone che devono usarla* - accessibilità, SEO, prestazioni, buone pratiche. Entrambe le risposte
indicano un punto preciso (file, riga, indirizzo), non un punteggio, e quasi tutte arrivano con la
correzione già pronta.

**Quali problemi risolve**

1. **"L'ha scritto un'AI?" - con una risposta dove puoi agire.** Un rilevatore web dà una
   percentuale su un testo incollato. XAnalyze dà il file e la riga, i segnali che si sono
   attivati, la confidenza e, se lo chiedi, il commit che ha toccato quella riga per ultimo.
2. **Caratteri che nessuno vede.** Spazi a larghezza zero, trattini morbidi, lettere omoglife e
   virgolette tipografiche rompono ricerca, diff, stringhe di prezzo e `grep`. Vengono trovati con
   precisione e rimossi con precisione, un carattere alla volta, mai riformattando il file.
3. **Un audit che resta un PDF.** 52 regole non si fermano al nome del difetto: dove la correzione
   discende dal markup, può essere riscritta nel file. Dove non discende - il testo alternativo di
   una fotografia, la lingua della pagina - resta fuori dal percorso automatico di proposito: un
   markup valido che mente fa sì che l'audit successivo dichiari la pagina pulita.
4. **Un risultato "pulito" che è una bugia.** L'esecuzione dice che cosa ha letto davvero: quante
   pagine, che cosa non è riuscita ad aprire, dove un limite ha tagliato la scansione. "Nessun
   rilievo" è una buona notizia solo se sai che cosa è stato guardato.
5. **Farlo più di una volta.** Un'esecuzione è un oggetto, non un comando: si può mettere in pausa,
   riprendere, elencare, confrontare con quella precedente, e lascia una cartella di documenti
   invece che righe nel terminale.
6. **Le supposizioni sulla provenienza.** Immagini e repository vengono letti per ciò che
   **dichiarano di sé**: campi IPTC/XMP, blocchi con il prompt del generatore, un manifest C2PA
   firmato, commit con un assistente come autore, configurazione di un assistente committata. È un
   record, non un'opinione sui pixel.

**A chi serve**

- **Redattori e proprietari dei contenuti** che devono sapere che cosa, nel loro sito, l'ha scritto
  un modello, e dove.
- **Sviluppatori e agenzie** che rispondono del sito di qualcun altro e devono mostrarne lo stato,
  correggere ciò che è meccanico e lasciare traccia di entrambe le cose.
- **Chi si occupa di accessibilità e QA**, comprese le persone che lavorano secondo le regole
  europee di accessibilità: servono rilievi legati agli elementi e un report da consegnare.
- **Team che non possono mandare i propri contenuti da nessuna parte.** Tutto, tranne il passaggio
  facoltativo del modello, gira sulla tua macchina; non c'è un account da creare e nulla viene
  caricato.
- **Agenti AI per il codice**, che hanno un formato di scansione offline dedicato e un modo per
  restituire i giudizi (`agent-scan`, `agent-judge`).

---

## Indice

- [Perché esiste XAnalyze](#perché-esiste-xanalyze)
- [Funzionalità](#funzionalità)
- [Limiti](#limiti)
- [Avvio rapido](#avvio-rapido)
- [Utilizzo](#utilizzo)
- [Comandi CLI](#comandi-cli)
  - [fullscan](#fullscan---scansione-completa)
  - [Le quattro forme da ricordare](#le-quattro-forme-da-ricordare)
  - [Scansionare un sito di cui hai anche il codice](#scansionare-un-sito-di-cui-hai-anche-il-codice)
  - [Nessun sito live, ma c'è un checkout](#nessun-sito-live-ma-cè-un-checkout---fullscan-può-avviarlo-da-solo)
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
- [Provenienza dei media](#provenienza-dei-media)
- [Fatti del repository](#fatti-del-repository)
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

- **Rilevamento di pattern AI** — segnali euristici (cliché, struttura,
  «raffiche») e un passaggio su embedding; entrambi misurati contro un corpus
  piccolo, vedi [Limiti](#limiti)
- **Caratteri non da tastiera** — larghezza zero, omoglifi, spazi anomali,
  lettere stilizzate, virgolette tipografiche. Trovati con precisione e rimossi
  con precisione
- **Accessibilità, SEO, prestazioni, buone pratiche** — 52 regole; dove la
  correzione discende dal markup, può essere riscritta nel file
- **Audit responsive** — la stessa pagina a 1440 / 834 / 390, unita in un solo
  elenco che dice quali larghezze hanno visto ogni rilievo
- **Rendering nel browser** — Chromium reale per i siti resi lato client
- **Scansione completa** — entrambi i passaggi in una sola esecuzione, con il
  browser automatico
- **Dev server** — `fullscan --devserver` avvia il server Node/Django/Rails del
  repository e scansiona il render. Va attivato: uno potrebbe già essere in corso
- **Provenienza dei media** — che cosa dichiara un'immagine di sé: campi
  IPTC/XMP, blocchi con il prompt del generatore, un manifest C2PA firmato
  quando c'è un lettore. Mai un verdetto sui pixel
- **Fatti del repository** — commit con un assistente come autore,
  configurazione di un assistente committata, un `.env` che nessuna regola copre
- **Blame su un rilievo** — il commit che ha toccato quella riga per ultimo
- **L'esecuzione è un oggetto** — pausa, ripresa, elenco, confronto con la
  precedente
- **Documenti** — un report da leggere (PDF/HTML), un briefing per un agente
  (Markdown/JSON) e le durate delle fasi, una cartella per esecuzione
- **Tre interfacce, tre lingue** — CLI, finestra e interfaccia terminale su un
  unico nucleo, tutte e tre in ucraino, italiano o inglese

---

**La scansione sa quale stack sta leggendo.** Il progetto viene identificato dai
suoi file marcatori - `wp-config.php`, `artisan`, `next.config.mjs`,
`manage.py`, `config/package-solution.json` - e ciò che risulta essere decide
cosa è codice di terzi anziché scritto qui: il core di WordPress, i pacchetti
Composer, `.svelte-kit/`, la `lib/` compilata di SPFx. Il riconoscimento è una
prova, mai una supposizione: il report nomina il file che lo ha dimostrato, e un
progetto che non corrisponde a nulla viene analizzato esattamente come prima.

**E cambia ciò che il report ti chiede.** Ogni risultato su un sito scansionato
viene confrontato con il codice che la piattaforma riconosciuta inietta da sé, e
quello che ci sta dentro viene nominato come suo: `Di questi 20 sono nel markup
generato da wix: non è il proprietario del sito a modificarlo`. Nulla viene
nascosto - il risultato è reale, lo script blocca davvero il rendering - ma chi
smista la lista vede ora su cosa può agire. Misurato: 20 risultati su 565 su
`wix.com` (bundle React e core-js da `static.parastorage.com`), 8 su 179 su
`squarespace.com`, 1 su 12 su `wordpress.org/news`, 1 su 65 su un negozio
Shopify e 0 su un controllo scritto a mano.

Il criterio non è "l'ha scritto l'autore" ma **il proprietario del sito può
cambiarlo**, ed è la misura ad aver svuotato quasi tutta la tabella. Una CDN non
è una piattaforma: `cdn.shopify.com` c'era finché un'esecuzione non ha attribuito
20 risultati a Shopify, per lo più `<video>` senza sottotitoli il cui unico
tratto Shopify era dove stava l'immagine di anteprima - anche il commerciante
carica lì i propri file. Una build è dell'autore: `/_next/static/`, `/_nuxt/` e
`/_app/immutable/` sono il suo stesso codice compilato, quindi nessun framework
né generatore possiede alcunché. Un tema è scelto e modificabile, quindi
`wp-content/themes/` resta al proprietario, mentre `wp-content/plugins/`, che non
si cambia senza un fork, no. I
file la cui intestazione dice che li ha scritti una macchina (`DO NOT EDIT`,
`@generated`) vengono saltati in qualsiasi stack.

**Una regola che scatta su quasi tutto viene segnalata, non creduta.** Risultati
distribuiti in modo uniforme su ogni pagina di una scansione sono la forma di una
misurazione rotta, non di un sito rotto, e la scansione lo dice accanto al numero.

## Certezza e soglia

Ogni risultato dichiara quanto è certo. `exact` significa che il markup risolve
la domanda: l'attributo `alt` c'è oppure non c'è. `needs-browser` significa che a
deciderlo è qualcosa fuori dal file - un foglio di stile, una pagina renderizzata,
o un motore di terze parti che segnala di **non aver potuto determinare** la
risposta.

    xanalyze audit ./src --confidence exact

tiene il primo tipo ed elimina il secondo. Entrambi vengono prodotti comunque ed
entrambi sono etichettati; la soglia è una vista su una sola scansione, come
`--category`, mai una decisione presa al posto di chi legge. Su dieci pagine di un
sito reale ha portato 335 risultati a 227 senza perdere un solo fatto.

## Cosa viene controllato

`accessibility` (29), `best-practices` (8), `performance` (8), `security` (10), `seo` (8)

`security` legge il markup per ciò che concede: un frame di terze parti senza
`sandbox`, un frame a cui è data la fotocamera, un form che invia a `http://`, uno
script di terze parti senza `integrity`, una chiave scritta in un attributo, un
campo password che il browser deve ricordare. Ognuna è `exact` per costruzione: un
risultato di sicurezza sbagliato costa più fiducia di qualsiasi altro, quindi nulla
che debba dedurre entra lì.

**Tre passaggi accanto alle regole, e tutti e tre leggono byte già pagati dalla
scansione.** Gli header della risposta arrivavano con ogni pagina e venivano
buttati - restava `Content-Type`, il resto moriva con la risposta - quindi un
sito servito senza `Content-Security-Policy`, senza `Strict-Transport-Security`,
senza compressione e senza `Cache-Control` veniva verificato come se il modo in
cui è servito non ne facesse parte. Il crawl tiene tutte le pagine insieme, ed è
l'unico posto in cui si vede lo stesso `<title>`, `description` o `canonical`
ripetuto su più pagine: markup valido su ognuna, sito rotto nell'insieme. E il
passaggio media scarica già l'intestazione di ogni immagine per i campi di
provenienza, dove stanno anche le dimensioni in pixel, quindi un'immagine salvata
a 6000 pixel e mostrata a 600 è una misura, non una supposizione.

Nessuno dei tre costa una richiesta che non fosse già fatta.

## Template che comprende

Quattordici linguaggi di template hanno una **coppia** di fixture in
`tests/fixtures/frameworks`: lo stesso componente scritto come vuole il suo
framework, e scritto male. La metà corretta non deve produrre alcun risultato e
quella rotta deve produrre quelli giusti, quindi questo elenco è un'affermazione
misurata, non un'intenzione:

`alpine`, `angular`, `blade`, `django`, `erb`, `handlebars`, `liquid`, `php`, `razor`, `react`, `svelte`, `thymeleaf`, `twig`, `vue`

È questo ciò contro cui la scansione è **verificata**. Il markup in qualsiasi
cosa non elencata viene comunque letto - il parser non lo rifiuta - ma nulla ha
dimostrato che un file corretto in quel linguaggio torni pulito, e un risultato
falso lì non verrebbe intercettato dalla suite.

## Stack che riconosce

Un progetto viene identificato dai suoi file marcatori, e ciò che risulta essere
decide cosa è codice di terzi anziché scritto qui:

`angular`, `astro`, `beehiiv`, `carrd`, `craft`, `django`, `docusaurus`, `dotnet`, `drupal`, `eleventy`, `ember`, `flutter`, `gatsby`, `ghost`, `hugo`, `jekyll`, `joomla`, `laravel`, `magento`, `nextjs`, `nuxt`, `qwik`, `rails`, `remix`, `shopify`, `silverstripe`, `spfx`, `spring`, `squarespace`, `statamic`, `storybook`, `sveltekit`, `symfony`, `typo3`, `vite`, `wagtail`, `webflow`, `wix`, `wordpress`

**Le firme sono pesate, non contate.** Il metodo è quello di Wappalyzer, perché
quel set di impronte è mantenuto contro tutto il web da un decennio e questo no: ogni
firma porta una confidenza, e una piattaforma viene nominata solo quando quelle che
hanno corrisposto sommano 100. Un letterale che solo una piattaforma emette vale 100 da
solo; qualcosa che potrebbe essere lì per un altro motivo - la stringa `SPFx`, una classe
di un tema Ghost - vale meno e va corroborato. Dove il markup porta una versione, viene
letta: "WordPress" è una supposizione da verificare, "WordPress 7.1" è un fatto su cui
agire.

Verificato su 13 siti reali: 10 piattaforme e 3 controlli costruiti a mano. 13 corretti,
0 mancati, 0 falsi. Due partivano come fallimenti ed entrambi sono serviti: `gohugo.io`
scrive `<meta name=generator ...>` senza virgolette attorno al nome dell'attributo - cosa
che l'HTML ha sempre permesso - e `ghost.org` è tornato come Hugo, il che si è rivelato vero.

**Le prove stanno in due posti.** Un checkout è identificato dai suoi file
marcatori; un sito scansionato da ciò che serve: un `<meta name="generator">`, un
host di asset che una piattaforma possiede, un payload di runtime che inietta. Finora
esisteva solo il primo, quindi una scansione del sito non sapeva nulla di ciò che
leggeva mentre lo stesso progetto su disco sapeva tutto. 26 piattaforme sono
riconosciute dal markup servito, 6 delle quali esistono solo lì (`wix`, `squarespace`, `webflow`, `beehiiv`, `carrd`, `typo3`): non hanno un
checkout da cui escludere qualcosa, e conoscerle serve a un'altra cosa - un risultato
dentro il guscio generato dalla piattaforma appartiene alla piattaforma, non a chi
scrive il contenuto.

Il riconoscimento è una prova, mai una supposizione: il report nomina il file che
lo ha dimostrato, i marcatori ambigui devono essere corroborati (`config.toml`
vale come Hugo solo accanto a `layouts/` o `archetypes/`), e un progetto che non
corrisponde a nulla viene analizzato esattamente come prima.

## Limiti

Dove lo strumento è debole - misurato, non supposto. Il tracciamento di ogni
punto vive nel `Problems.md` del progetto.

**Il corpus dietro il rilevamento dei testi AI è piccolo e sbilanciato.** La sua
metà positiva è stata scritta da modelli ed è più lunga della metà umana, che è
in gran parte stringhe di interfaccia. I numeri di precisione più avanti sono
precisione **su quel corpus**, non nel mondo reale; `scripts/calibrate.py
--confounds` stampa quanto otterrebbe un classificatore che conosce solo la
lunghezza, così la differenza resta visibile.

**L'italiano è la più debole delle tre lingue**, ma meno di quanto dicesse il
numero complessivo. Il recall misurato è ora 61.1% in italiano contro 65.6% in
inglese e 60.0% in ucraino - era 27.8%, finché la lista di frasi italiane non è
stata portata al livello di quella inglese; sulla metà trattenuta, l'unico
numero onesto, è 36.4% contro 55.0% e 71.4%. Letta per lunghezza, la debolezza
non è mai stata uniforme: dalle 25 parole in su l'italiano era già **il
migliore** dei tre (83.3%), e tutto il divario stava nelle voci di una sola
frase, dove non otteneva nulla. Su un sito italiano reale il detector offline
non ha trovato nulla dove un giudice-modello ha trovato sei passaggi. Se ti
interessa il testo italiano, usa il metodo ibrido e non quello offline.

Per questo `scripts/calibrate.py` stampa ogni cifra in fasce di lunghezza: la
metà umana del corpus è fatta soprattutto di stringhe di interfaccia e la sua
lunghezza mediana cambia da lingua a lingua, quindi un solo numero di recall non
significa la stessa cosa in ciascuna.

**Il giudizio di un modello non è riproducibile.** I provider non espongono né
un seed né una temperature, quindi due esecuzioni sullo stesso testo possono non
concordare. La cache dei giudizi lo nasconde tra esecuzioni dello stesso testo e
scarta le voci dopo 90 giorni.

**Una scansione del repository non è un audit di pagina più debole.** Scansionare
i template perde ciò che esiste solo una volta reso e segnala cose che una
pagina resa non avrebbe. Usa un URL, o `--devserver`, quando la risposta deve
riguardare la pagina.

**Un audit a una sola larghezza è stato fatto a una sola larghezza.** La
navigazione mobile della maggior parte dei siti non è affatto nel DOM desktop.
Passa tutti e tre i breakpoint, a meno che non ne intenda uno.

**La tipografia è rumorosa su testi curati.** La categoria è attiva per
impostazione predefinita e segnala trattini e virgolette voluti;
`--no-typography` o la sezione «Simboli» nelle impostazioni la spegne.

**`--scope technical` non misura affatto lo stile.** L'elenco di frasi dietro
i controlli stilistici è costruito su testo di marketing e, su 7225 blocchi di
commento di un repository reale e 55756 di un altro, non ha prodotto alcuna
segnalazione stilistica. I controlli sui caratteri restano attivi. Una scansione
tecnica silenziosa significa quindi «non misurato», non «pulito», e la scansione
lo dice.

**Su un terminale a 16 colori due dei quattro livelli di gravità collassano.**
`sev-high` e `sev-medium` finiscono entrambi su ANSI 7; `critical` e `none`
restano distinti. Ogni riga porta comunque il nome della gravità, quindi si perde
solo la lettura a colpo d'occhio della scala. Con 256 colori si vedono tutti e
quattro.

**Le Content Credentials richiedono un lettore opzionale.** Senza `c2pa-python`
e `cryptography` XAnalyze dice che il file porta un manifest e che non è riuscito
a leggerlo: è vero, ed è meno di quanto vorresti.

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

```bash
xanalyze                                      # l'interfaccia terminale
xanalyze fullscan https://example.com         # entrambi i passaggi su un sito
xanalyze scan ./src                           # pattern AI e caratteri
xanalyze audit https://example.com --browser  # accessibilità, SEO, velocità
xanalyze fix ./src                            # scrive le correzioni dei caratteri
xanalyze runs                                 # che cosa è stato eseguito e che cosa riprendere
xanalyze update                               # cerca e installa una nuova versione
xanalyze --version
```

Ogni comando cerca una nuova versione una volta al giorno e stampa una riga
quando c'è; `--no-update-check` lo disattiva. La finestra è un'applicazione a
parte (`XAnalyze.app`, oppure `python main.py` dal codice).

## Comandi CLI

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
| `--repo PATH` | Checkout locale dietro un target URL. Un rilievo il cui passaggio corrisponde a un blocco trovato sotto `PATH` ottiene `source_file`/`source_line` - il file da correggere, non solo la pagina su cui compare. Additivo: un sito scansionato senza funziona esattamente come prima |
| `--devserver` | Rileva e avvia il server di sviluppo del repo (`package.json`, `manage.py`, `Gemfile`+`bin/rails`) e scansiona il sito reso invece della sorgente. Disattivo per default - il server potrebbe già essere in esecuzione altrove; ne hai già uno avviato? Passa invece `--url http://localhost:PORT` |
| `--start-command CMD` | Sovrascrive il comando di avvio rilevato, eseguito senza shell (es. `--start-command "npm run dev:custom"`) |
| `--dev-server-port N` | Porta da usare, quando non può essere letta dall'output del server (Django/Rails; i server Node annunciano la propria) |
| `--yes` | Installa le dipendenze mancanti del dev server senza chiedere |
| `--detector DETECTOR` | Detector pattern AI: `offline`, `embedding`, `hybrid`, `llm-judge` |
| `--model MODEL` | Modello per il passaggio AI, es. `sonnet`, `opus` (solo con `--detector ai`/`llm-judge`; ignorato dall'abbonamento xFormat, che sceglie da sé) |
| `--effort {low,medium,high}` | Quanto impegno mette il passaggio AI (default: `low`) |
| `--no-judgment-cache` | Richiedi di nuovo al modello passaggi già giudicati su questa macchina (più lento; unico modo per ottenere un'opinione fresca - e possibilmente diversa - dato che il giudice non è deterministico) |
| `--scope SCOPE` | Cosa leggere: `content`, `technical`, `both` |
| `--no-typography` | Lasciare em dash e virgolette curly |
| `--breakpoints NAMES` | Responsive breakpoints: `all`, `desktop`, `tablet`, `mobile` |
| `--styled-report PATH` | Percorso report PDF/HTML brandizzato |
| `--report PATH` | Percorso briefing agente (.md o .json) |
| `--check` | Uscita 1 quando trovati problemi critici/gravi |
| `--language LANG` | Lingua report: `uk`, `it`, `en` |

---

### Le quattro forme da ricordare

```bash
# 1. Per bene: dieci pagine, tre larghezze, un modello che legge il testo.
xanalyze fullscan mysite.com --max-pages 10 --depth 2 --detector ai --breakpoints all

# 2. Al volo - i valori predefiniti: 30 pagine, profondità 1, solo desktop, offline.
xanalyze fullscan mysite.com

# 3. Codice: nessuna scansione del sito, nessun browser. Testo AI e caratteri
#    più l'audit statico.
xanalyze fullscan ./my-project

# 4. Che cosa è stato eseguito, e come riprendere.
xanalyze runs
xanalyze resume 2026-08-24-1331
```

`--detector ai` (anche `llm-judge`, `judge`) dice che un modello legge il testo,
non chi paga: quello viene dalle impostazioni, e l'esecuzione stampa il giudice a
cui è arrivata. `xanalyze ai status` dice che cosa è disponibile.

I valori predefiniti sono un'occhiata veloce. Un audit di dieci pagine a tre
larghezze richiede circa cinque minuti, per il ~90% il passaggio nel browser;
`timings.md` nella cartella dell'esecuzione mostra dove è finito il tempo.

---

### Scansionare un sito di cui hai anche il codice

Sono due domande diverse. Misurato su contenuti appaiati - una pagina HTML e il
template PHP che la produce - la pagina resa ha attivato **15** regole che il
template non poteva dare (`html-lang`, `page-has-h1`, `seo-canonical`,
`link-text-vague`: in gran parte ciò che scrive `wp_head()` e che un template non
contiene), e il template ne ha attivata una che la pagina non poteva dare.

Scansiona il sito per quello che è - `fullscan https://example.com` - perché
quasi tutto ciò che un audit di accessibilità e SEO misura è una proprietà del
render. Aggiungi `--repo PATH` per sapere anche **dove** correggere: un rilievo
sul testo il cui brano corrisponde a un blocco sotto `PATH` porta `source_file` /
`source_line` nel report, nel briefing e nel JSON.

---

### Nessun sito live, ma c'è un checkout - `fullscan` può avviarlo da solo

Un repository con `package.json`, il `manage.py` di Django o
`Gemfile`+`bin/rails` può avviare il proprio dev server ed essere scansionato
come sito reso. Va attivato: uno potrebbe già essere in esecuzione altrove, e un
secondo su un'altra porta non aiuta nessuno:

```bash
xanalyze fullscan ./repo            # scansione statica; dice che il server non è stato avviato
xanalyze fullscan ./my-vite-app --devserver
# node: dependencies are missing. Run `npm install`? [y/N]
# [devserver] node ready at http://localhost:5173
```

Le dipendenze mancanti fermano l'esecuzione e chiedono prima di installare;
`--yes` salta la domanda. Appena il server risponde, scansione e audit girano su
di esso come su qualunque URL - misurato dal vivo: 8 regole di accessibilità e
SEO che una scansione statica dello stesso repository non può produrre. `--repo`
viene impostato automaticamente sul checkout, così i rilievi sul testo continuano
a indicare il file da correggere.

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

### Ogni passaggio viene letto una volta sola

Un crawl di dieci pagine di un sito ha prodotto 573 blocchi di testo e **236
testi distinti**. Header e footer compaiono su ogni pagina, quindi
`Tel. +39 0432 924815` è stato letto 26 volte.

I passaggi vengono deduplicati **sull'intera esecuzione**, non dentro una
pagina: la ripetizione che vale la pena togliere è proprio quella che una
singola pagina non può vedere. Due passaggi sono lo stesso quando il testo
coincide dopo aver compresso gli spazi e mascherato gli identificatori generati
dalla macchina, così un menu con un uuid nuovo a ogni pagina resta un solo
menu. La lingua fa parte dell'identità, perché la stessa stringa letta come
italiana e come inglese è una domanda diversa.

Entrambi i detector leggono quell'unico elenco. **Non si perde nulla:** ogni
occorrenza produce comunque il proprio rilievo con la propria pagina. La
deduplicazione cambia ciò che viene *chiesto*, mai ciò che viene riportato.

I verdetti restano su disco tra le esecuzioni, e quella parte non è
un'ottimizzazione. Il giudice **non è deterministico**: due esecuzioni dello
stesso sito con gli stessi flag hanno dato 6 e poi 24 rilievi, e nessun
percorso qui espone temperatura o seed, quindi un output identico non si può
*chiedere*. Si può solo *ricordare*.

Misurato su quel sito, `--detector ai --model sonnet --effort low`:

| | blocchi letti | richieste | tempo |
|---|---|---|---|
| prima | 573 | 72 | 8m 33s |
| prima esecuzione | 242 | 31 | 3m 42s |
| seconda | 0 | 0 | **3,3s** |

Il report della seconda esecuzione coincide byte per byte con il primo.

`--no-judgment-cache` richiede un parere nuovo, perché una risposta sbagliata
in cache non deve essere incorreggibile. `XANALYZE_JUDGMENT_CACHE` sposta
l'archivio; le voci più vecchie di 90 giorni vengono scartate.

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

### Cosa conta come testo

Una scansione del repository legge le stringhe che una persona vedrà - un
`placeholder`, una chiamata `t("...")`, una chiave di oggetto come `title:`
- e lascia stare il resto del codice. Due ruoli vengono distinti di
proposito, perché la stringa da sola non dice quale sia:

- **Le descrizioni dei campi di uno schema di strumento non sono testo.**
  La definizione di uno strumento scrive le descrizioni dei suoi parametri
  sotto la stessa chiave `description:` con cui una landing page scrive il
  proprio testo, e in entrambi i casi sono frasi in inglese. A separarli è
  l'oggetto attorno: uno schema dichiara un `type` fra i primitivi del
  formato (`string`, `number`, ...) e porta una seconda chiave di schema
  (`required`, `enum`, `parameters`, ...). Misurato su un repository reale:
  è il **12%** di tutto ciò che sembrava testo.
- **Un esempio citato in Markdown non è markup pubblicato.** I blocchi
  delimitati e i backtick vengono mascherati prima dell'analisi, così un
  documento che scrive `<img src="...">` in un resoconto di bug non viene
  segnalato come immagine senza `alt`.

La regola resta prudente in entrambe le direzioni: leggere la descrizione di
uno schema come testo costa un verdetto senza senso, mentre scartare una
frase vera costa una segnalazione, e i due prezzi non sono uguali.

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

## Provenienza dei media

Le immagini vengono lette per ciò che dichiarano sulla propria creazione.
Questo **non** è un rilevatore di immagini generate, e la distinzione è tutto:
non esiste un modo onesto di guardare i pixel e dire che li ha disegnati un
modello. Ciò che esiste è l'insieme di campi che i generatori scrivono da sé
dentro al file.

| Segnalazione | Cosa significa |
|---|---|
| `bp-ai-media-declared` | Il file dichiara di essere stato prodotto da un modello: `digitalSourceType: trainedAlgorithmicMedia`, oppure un blocco di prompt che solo uno stack di generazione locale scrive |
| `bp-ai-media-tool` | Il nome di un generatore in un campo strumento. Più debole: un'immagine soltanto **modificata** nell'app di un generatore porta la stessa stringa |
| `bp-ai-media-signed` | Un manifesto C2PA è presente ma non verificato: o non è installato alcun lettore, o il manifesto non ha superato la validazione. Il motivo viene stampato accanto alla segnalazione |

**L'assenza di tutti i campi qui sopra non significa nulla.** Uno screenshot,
un nuovo salvataggio o un caricamento attraverso la maggior parte delle
piattaforme li elimina tutti. Un'immagine silenziosa non è un verdetto che
l'abbia fatta una persona.

### Content Credentials (C2PA)

Un manifesto firmato è la provenienza più forte che esista, quindi viene
segnalato che si riesca o meno a leggerlo: passarci accanto in silenzio
mostrerebbe un file che documenta se stesso come un file che non lo fa.

Per leggerlo servono due pacchetti opzionali, entrambi con una componente
nativa:

```bash
pip install c2pa-python cryptography
```

Senza di essi la segnalazione lo dice, invece di fingere che il file taccia.
**I bundle scaricabili contengono il lettore**, perché un'app congelata non ha
pip: lasciarlo opzionale lì avrebbe significato assente per sempre, e la
provenienza più forte che un file possa portare si leggerebbe come presente e
non letta su ogni macchina che non compila dal sorgente. Costa 27 MB su un
bundle da 1.1 GB.

Quando il manifesto viene letto, tre esiti restano distinti, perché sono tre
affermazioni diverse:

- **Il file dichiara contenuto prodotto da un modello** -
  `trainedAlgorithmicMedia`, cercato sia in cima al payload di un'asserzione
  sia **dentro ogni** voce `c2pa.actions`, che è dove lo scrive un generatore
  che firma il proprio output.
- **Il manifesto non regge** - i byte non corrispondono più a quanto è stato
  firmato (`assertion.*`, `claimSignature.*`). Riportato come non verificato
  con il codice, mai come dichiarazione: la firma è tutto il valore di C2PA.
- **Il firmatario non è in una lista di fiducia di questa build**
  (`signingCredential.untrusted`) - è un'affermazione sulla build, non sul
  file, quindi non ritira la dichiarazione del file.

---

## Fatti del repository

Una scansione del repository legge anche ciò che il repository dice di **sé**,
che è una domanda diversa da cosa fanno le sue pagine. Qui non si giudica
nulla: ogni voce è un fatto presente oppure assente.

| Segnalazione | Gravità | Cosa legge |
|---|---|---|
| `sec-env-tracked` | Critical | Un `.env` già tracciato da git: credenziali **pubblicate**, da ruotare e non da cancellare |
| `sec-env-not-ignored` | Serious | Un `.env` che nessuna regola di esclusione copre: credenziali in attesa del prossimo `git add .` |
| `bp-assistant-commits` | Minor | Commit il cui messaggio nomina un assistente come autore |
| `bp-assistant-artifacts` | Minor | Configurazione degli assistenti versionata: `CLAUDE.md`, `.cursor/`, istruzioni Copilot |
| `bp-assistant-touched` | Minor | Segnalazioni su righe toccate per ultime da un commit scritto da un assistente |

Scrivere codice con un assistente non è un difetto, e questi risultati sono
riportati come provenienza, non come problemi. Una cartella che non è un
repository git non produce **alcuna** segnalazione sui commit: "nessun commit
di assistenti trovato" e "non c'è storia da guardare" sono affermazioni
opposte, e solo una delle due è vera.

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

**Ciò che un framework stampa nel markup non fa parte dell'elemento.**
Confrontare il markup alla lettera significa che un componente si spezza in un
rilievo per pagina appena qualcosa gli genera un identificatore: dodici stili
reali sono stati misurati e nove si spezzavano. `useId` di React (`:r3:`),
Emotion (`css-1q2w3e`), styled-components (`sc-bdVaJa`), gli hash di scope di
Svelte e Astro, `_ngcontent-` di Angular, i contatori di Radix, MUI ed Ember
vengono mascherati prima del confronto, accanto a UUID e sequenze esadecimali
già gestite. Solo dentro gli attributi identificativi - `class`, `id`, `for`,
`aria-controls` - mai in `src`, `href`, `alt` o `title`: mascherare troppo
unisce rilievi davvero diversi, e un problema unito per errore ne nasconde uno
vero. `mt-4` di Tailwind, `col-md-6` di Bootstrap e un `id="email"` scritto a
mano restano intatti, e c'è un test per ciascuna direzione.

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

Gli agenti usano gli stessi comandi delle persone; due esistono solo per loro.

| Che cosa vuole l'utente | Il comando |
|---|---|
| Tutto su un sito o un repository, in una sola esecuzione | `xanalyze fullscan <target>` |
| Accessibilità, SEO, prestazioni, buone pratiche | `xanalyze audit <target>` |
| Testo scritto da un'AI e caratteri non da tastiera | `xanalyze scan <percorso>` |
| Scrivere le correzioni dei caratteri | `xanalyze fix <percorso>` |
| Annullare quelle scritture | `xanalyze undo <percorso>` |
| Che cosa è stato eseguito e che cosa si può riprendere | `xanalyze runs` |

`--json` su ognuno dà un output leggibile dalla macchina, `--language uk|it|en`
imposta la lingua del report, `--breakpoints desktop,tablet,mobile` sceglie le
larghezze, `--styled-report report.pdf` scrive un documento da consegnare.

### Modalità «l'agente è il giudice»

Due comandi tagliano la scansione a metà perché il modello nel mezzo sia
l'agente stesso: nessuna chiave, nessun abbonamento, e nulla lascia la macchina
se non verso il contesto dell'agente.

```bash
xanalyze agent-scan ./src --json > passages.json   # passaggio offline, brani fuori
#                                                    l'agente li giudica
xanalyze agent-judge ./src --judgments verdicts.json
```

`agent-scan` scrive ogni brano che vale la pena giudicare con il suo id, il suo
testo e ciò che hanno detto i segnali offline. `agent-judge` riprende gli stessi
id con un verdetto ciascuno: il giudizio è dell'agente, il punteggio, il
raggruppamento e i documenti restano di questo strumento. Un verdetto copre ogni
punto in cui il brano compare - tre file identici sono giudicati una volta sola.

### Leggere l'output

```bash
xanalyze fullscan https://example.com --json > run.json
jq '.audit.issues[] | select(.severity == "critical")' run.json
jq '.findings[] | {score, explanation}' run.json
```

Un rilievo dice dove si trova (`source`, `line`, `selector`), che cosa è
(`rule_id`, `severity`, `snippet`) e, dove la correzione discende dal markup,
`fix_snippet`. Un'esecuzione responsive porta anche `details.breakpoints`, così
un difetto che esiste solo a una larghezza si distingue da uno che esiste
ovunque.

## GUI

L'app desktop risponde alle stesse domande della CLI.

Si apre sulla **schermata di impostazione**: che cosa guardiamo, come leggiamo,
che cosa cerchiamo, chi valuta, e una frase che nomina la scansione prima che tu
prema qualcosa. Analizza consegna la finestra al layout di lavoro; il pulsante
"Scegli un obiettivo" dello stato vuoto la riporta indietro.

Durante il lavoro le stesse scelte sono una riga di valori in linea sopra i
risultati.

**I controlli, nella riga o nella schermata di impostazione**

1. **Sorgente** — URL del sito, cartella del repository o singolo file HTML.
   Anche un host senza schema va bene
2. **Controllo** — accessibilità, pattern AI o entrambi (entrambi per default)
3. **Metodo** — offline, embedding, AI oppure offline + AI. Le voci con AI
   compaiono solo quando c'è un account o una chiave che le paghi
4. **Scope** (cartelle) — il testo che arriva all'utente, i commenti e le
   docstring, o entrambi
5. **Profondità** (siti) — quanto lontano il crawl segue i link
6. **Account** — chi paga un passaggio AI, e se qualcuno ha effettuato l'accesso

**L'obiettivo si può portare invece di scriverlo.** Una pagina salvata in un
solo file - o una cartella - si può trascinare ovunque sulla finestra: imposta
la sorgente e compila il percorso, e la schermata di preparazione mostra ciò
che è stato scelto con la sua dimensione, così un export sbagliato si vede
prima dell'esecuzione e non dopo. Tutto il resto viene rifiutato dal cursore,
non accettato e ignorato.

**I risultati**, letti da sinistra a destra

7. **Lista dei rilievi** — badge di gravità, una riga per problema distinto. Un
   problema trovato in più file dice in quanti, invece di ripetersi
8. **Anteprima** — la pagina renderizzata, o il file sorgente, con il rilievo
   evidenziato o la sua riga marcata. Si può fissare a `1440`, `834` o `390`,
   così un rilievo trovato a una larghezza si guarda a quella larghezza. Una
   larghezza più grande della colonna viene ridimensionata invece che pretesa
   dalla finestra: la pagina si dispone ancora a 1440 mentre i pixel restano
   dentro la colonna
9. **Dettaglio** — cosa è stato trovato, perché conta, come correggerlo,
   l'elemento, la sostituzione pronta e ogni punto in cui lo stesso problema
   compare
10. **Azioni** — correggi i caratteri, apri l'elenco delle sostituzioni,
    riscrivi sul posto, annulla una scrittura, esporta il report. *Correggi su
    disco* apre lo stesso elenco: le correzioni dell'audit si leggono lì prima
    di essere scritte, come tutto il resto

La finestra ripiega una colonna alla volta mentre si restringe: prima la colonna
dei dettagli (che ricompare sotto la riga cliccata), poi l'anteprima.

**L'elenco delle sostituzioni**

Nessun file viene scritto per via di un numero in una finestra di dialogo.
*Genera elenco sostituzioni* apre una schermata con tutte le modifiche in
sospeso dell'esecuzione — le correzioni dei caratteri, le bozze del modello e
le correzioni di markup dell'audit insieme — su quattro colonne: dove si trova,
che cosa dice ora, che cosa direbbe e da dove viene la correzione.

Il senso della schermata è che cosa arriva selezionato:

- **meccanica** — la correzione è dedotta, non composta (un solo modo giusto di
  togliere un carattere invisibile, un solo attributo giusto per un pulsante
  senza nome accessibile). Selezionata
- **bozza del modello** — la sostituzione l'ha scritta un modello, e una frase
  scorrevole non è una frase corretta. Non selezionata finché non la selezioni
- **decisione** — non c'è una sostituzione, c'è solo la sua forma. `alt=""` su
  una fotografia è markup valido ed è una bugia, quindi la riga mostra che cosa
  va deciso e qui non si può selezionare

Il pulsante dice quante righe sta per scrivere, e *Salva su file* scrive lo
stesso elenco in Markdown (`replacements-YYYY-MM-DD.md`) per una revisione che
avviene in una pull request o sullo schermo di qualcun altro.

Premere *Scrivi* mostra che cosa sta per succedere: i file, quanti frammenti
ne riceve ciascuno e un interruttore per la copia `.bak` tenuta accanto a ogni
file prima della sua prima modifica. Che cosa è successo torna in quattro
numeri che non sono lo stesso numero - applicate, file modificati, saltate
perché il frammento è cambiato dopo la scansione, errori - con «Annulla tutto»
finché quelle copie ci sono ancora.

Una riga-decisione ha un'azione propria, «Decidi», con tre vie d'uscita:
scrivere tu il valore, segnare l'immagine come decorativa (un'affermazione che
una persona può fare e lo strumento no), oppure passarla al modello. Una
decisione a cui hai risposto diventa una riga **decisa** - selezionata, perché
la decisione l'hai appena presa.

*Fai completare N al modello* consegna le decisioni aperte al modello
configurato. Ciò a cui risponde diventa una **bozza del modello** - non
selezionata e con una frase da leggere - mai una riga meccanica; ciò che la
pagina non dice davvero resta una decisione.

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

L'interfaccia terminale è scritta nella lingua dell'interfaccia, come la
finestra: menu, moduli, stati e suggerimenti dei tasti nel footer vengono dalla
stessa tabella, e cambiare lingua nelle sue Impostazioni ricostruisce le
schermate nella nuova lingua subito, non al prossimo avvio.

Navigazione con frecce o tasti 1-7; anche `Tab` sposta tra i controlli. Il
footer elenca i tasti che lo schermo corrente accetta. `Esc` torna indietro,
`q` esce.

---

## Configurazione

### La schermata delle impostazioni

Cinque sezioni in una barra laterale - **Account e modello**, **Generali**,
**Simboli**, **Eccezioni**, **Avanzate** - e una riga per ogni decisione; il
file in cui ogni riga viene scritta è indicato in fondo alla barra.

La forma del controllo segue il tipo di decisione: un **interruttore** per
acceso/spento, un **controllo segmentato** dove le alternative sono due-quattro
e vederle è la spiegazione (tema, sforzo del modello), un **menu a discesa**
solo dove l'elenco è aperto (lingua, modello). «Simboli» mostra che cosa
intercetta davvero ogni categoria (`U+200B, U+200D, U+FEFF`), non solo il suo
nome, e le righe si disattivano quando il passaggio sui caratteri è spento.

«Account e modello» sono tre righe, una per account - l'abbonamento xFormat,
la tua chiave Anthropic, la sessione Claude Code già autenticata su questa
macchina - ognuna dice qual è il proprio stato, e la scelta è quale di esse
usa l'esecuzione. Tutto ciò che si vede all'apertura è letto in locale e senza
costo; le due risposte che costano qualcosa (la quota dell'abbonamento e la
sessione della CLI) stanno dietro il pulsante «Verifica» della riga stessa.

«Avanzate» dice anche che cosa lo strumento ha lasciato su questa macchina:
quanti giudizi del modello sono in cache e dove, con un pulsante per svuotarla,
e «Rimuovi XAnalyze da questo computer», che elenca esattamente che cosa
verrebbe eliminato - e che cosa resta, come i report già scritti e le cartelle
delle esecuzioni.

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

Un elenco nudo come questo viene letto come pattern di file: una riga prima
della prima intestazione di sezione che finisce con `/` o contiene un glob è
un percorso. Il resto delle righe nude sono frasi, perché è ciò che si scrive
per primo. Per essere espliciti, apri con un'intestazione di sezione: vedi
**Soppressioni** più sotto.

### Soppressioni

Sopprimi scoperte specifiche tramite impostazioni o `.xanalyze-ignore`:
- Per selettore CSS (escludi regioni)
- Per rule ID (disabilita regole)
- Per impronta (una scoperta esatta, nascosta una volta, assente dopo una nuova scansione)
- Per frase o per percorso

Le voci stanno sotto un'intestazione di sezione, e tutto ciò che precede la
prima intestazione viene letto come frase, perché è quello che si scrive per
primo:

```
[rules]
meta-viewport  # l'area admin ha una larghezza fissa di proposito

[selectors]
# incorporamenti di terze parti
#promo-banner
.ads

[fingerprints]
083bea550659aadb  # style · about.md · comprehensive
```

**Il file resta tuo.** Commenti, righe vuote e raggruppamenti sopravvivono a
una scrittura dall'applicazione: nascondere una scoperta nella finestra
aggiunge una riga nella sezione giusta e lascia tutto il resto dove l'hai
scritto.

**Una nota dopo `#` è una nota, non parte della voce.** Scrivi il motivo
accanto alla regola che hai disattivato e la regola resta disattivata. Dentro
`[selectors]` un `#` seguito subito da un nome è un selettore di id
(`#promo-banner`), quindi lì una nota richiede uno spazio dopo il `#`.

**Nascondere una scoperta registra che cosa fosse.** Un'impronta è un hash a
senso unico della scoperta, quindi l'applicazione scrive accanto una nota
leggibile. Senza quella nota, riportare in vista una scoperta significa
cancellare una riga di caratteri esadecimali e rifare la scansione per
scoprire che cosa facesse.

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

- Python 3.14+ - sulle versioni precedenti il lettore C2PA non si installa:
  `c2pa-python` dichiara `Requires-Python >=3.7` e poi usa sintassi che
  richiede 3.10+, quindi pip installa una versione che fallisce all'import
- PySide6 (per GUI)
- sentence-transformers (per detector embedding)
- QtWebEngine (per passaggio browser)
- `c2pa-python` e `cryptography` - opzionali, per leggere un manifesto firmato

---

## Licenza

MIT
