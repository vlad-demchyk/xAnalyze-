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
- **Un report da ogni comando**: `scan`, `audit` e `fullscan` scrivono un briefing e un report impaginato in una cartella datata, e ogni documento si apre dichiarando il comando e i parametri che hanno cambiato ciò che è stato misurato.
- **Un binario, tre superfici**: al primo avvio l'app impacchettata propone di aggiungere il comando `xanalyze` al `PATH`, così CLI e TUI non richiedono un secondo download.

`fullscan` unisce controlli del testo, dei caratteri e del sito. Un repository locale viene analizzato staticamente, salvo usare `--devserver`.

Lo stack viene identificato dai file marcatori o dal markup servito. Entrambi gli elenchi sono verificati contro il codice dalla suite, quindi vivono in [Template che comprende](#template-che-comprende) e [Stack che riconosce](#stack-che-riconosce) invece di essere ripetuti qui.

## Avvio rapido

### GUI macOS

```bash
curl -L -o XAnalyze.app.zip https://github.com/vlad-demchyk/xAnalyze-/releases/latest/download/XAnalyze.app.zip
unzip XAnalyze.app.zip
mv XAnalyze.app /Applications/
```

L'app e la riga di comando sono un unico binario. Al primo avvio la finestra
propone **una volta sola** di creare il collegamento `xanalyze` in
`~/.local/bin`, così CLI e TUI funzionano nel terminale; il rifiuto viene
ricordato e la stessa installazione resta nelle Impostazioni ->
«Comando nel terminale».

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
| `--breakpoints NAMES` | `all`, `desktop`, `tablet`, `mobile`, `reflow` (320 px) o una lista. Senza di esso il passaggio del browser gira a una sola larghezza, 1440x900 - la stessa di `desktop` |
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

Opzioni: `--depth`, `--max-pages`, `--max-files`, `--render`, `--exclude`, `--category`, `--language`, `--no-ignore`, `--json`, `--check`, `--ai`, `--provider`, `--fix`, `--report`, `--browser`, `--breakpoints`, `--site-controls`, `--styled-report`. `--site-controls` recupera separatamente robots.txt e le sitemap dello stesso dominio dichiarate al suo interno.

La quinta scheda della schermata di configurazione, **Cosa mostrare**, porta i parametri che prima esistevano solo nella CLI: le sei categorie dell'audit (`geo` compresa), la soglia di certezza (`--confidence`) e `--site-controls`. L'ambito (`--scope`) sta con i controlli del repository e la tipografia è una categoria di caratteri nelle Impostazioni.

Categoria e certezza sono una **vista su un'unica scansione già fatta**, esattamente come `--category` e `--confidence`: le regole costano poco e condividono un solo parsing, quindi restringere ridisegna l'elenco e il riepilogo senza rifare l'audit, e allargare riporta indietro tutti i rilievi. Il report esportato passa per la stessa vista, così schermo e file non possono dire cose diverse. Quando un filtro nasconde tutto, la schermata vuota lo dice e mostra il conteggio senza filtro invece di dichiarare pulita la pagina. `--site-controls` è di natura diversa - recupera robots.txt e le sitemap che vi sono dichiarate - quindi è una scelta di esecuzione, spenta di default e visibile solo per un sito.

La schermata Audit della TUI ha gli stessi tre parametri, e gli elenchi di larghezze in Audit e Scansione completa contengono tutte le larghezze che l'audit conosce.

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

Ogni passaggio porta un campo `language`, ed è `null` quando il passaggio è troppo breve per essere letto. È una risposta, non un valore mancante: un pulsante di due parole non è inglese solo perché non si è rilevato altro, e un agente a cui si dice il contrario lo giudica con le aspettative sbagliate.

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

`angular`, `astro`, `bedrock`, `beehiiv`, `carrd`, `craft`, `django`, `docusaurus`, `dotnet`, `drupal`, `eleventy`, `ember`, `flutter`, `gatsby`, `ghost`, `hugo`, `jekyll`, `joomla`, `laravel`, `magento`, `nextjs`, `nuxt`, `qwik`, `rails`, `remix`, `shopify`, `silverstripe`, `spfx`, `spring`, `squarespace`, `statamic`, `storybook`, `sveltekit`, `symfony`, `typo3`, `vite`, `wagtail`, `webflow`, `wix`, `wordpress`, `wordpress-plugin`, `wordpress-theme`

Le firme sono pesate, non contate: ognuna porta una confidenza e una piattaforma
viene nominata solo quando le corrispondenze sommano 100, quindi un marcatore che
potrebbe essere lì per un altro motivo va corroborato.

## Analisi

Il detector offline combina segnali statistici, struttura, cliché e regole linguistiche. I detector embedding e basati su modello aggiungono un giudizio indipendente. Ogni risultato contiene posizione, punteggio, spiegazione e certezza.

L'audit copre `accessibility` (36), `best-practices` (13), `geo` (2), `performance` (8), `security` (10), `seo` (8) - numeri che la suite verifica contro il registro delle regole. GEO offre solo segnali consultivi su tipo di articolo, autore e data, non una previsione di posizione nelle risposte AI. La modalità statica legge i file; quella browser vede DOM renderizzato, contenuto client-side, stati responsive e header della risposta. `--repo` collega un audit URL al file sorgente.


**Regole che valgono solo per un tipo di file.** Un controllo viene eseguito
dove ha senso e da nessun'altra parte, e a deciderlo è una prova, non
un'opzione: la sintassi del file, ciò che `audit.medium` dice che il documento
sia e lo stack che il progetto ha dimostrato su disco.

- **React (`.jsx`, `.tsx`)**: `htmlFor` sull'etichetta, un gestore di clic
  senza equivalente da tastiera, un elemento statico reso interattivo,
  `tabIndex` dove non c'è alcuna azione, `autoFocus`, una `<a>` con un gestore
  e senza destinazione e `dangerouslySetInnerHTML`. Un componente non viene mai
  trattato come un elemento del DOM: `<Button>` non è `<button>`, e ciò che
  rende è affare di quel componente.
- **Email**: uno stack di font senza famiglia generica finale, un link senza un
  colore proprio e il preheader mancante. Valgono solo dove il documento è
  stato riconosciuto come email, e le regole da browser lì non vengono
  eseguite.
- **WordPress**: una variabile di template stampata nel markup senza
  `esc_html()`, `esc_attr()` o `esc_url()`. È una best practice con etichetta
  advisory, perché una lettura statica non vede se il valore era già stato
  ripulito. Le installazioni Bedrock sono riconosciute, così il core di
  WordPress in `web/wp/` e le tabelle di traduzione in `web/app/languages/`
  non vengono valutate come se le avesse scritte il progetto.
- **Siti a pagina singola**: un link a `#sezione` quando nessun elemento ha
  quell'id. In un sito fatto di un solo file quella è tutta la navigazione, e
  il browser, quando si rompe, non dice nulla.

**Il passaggio sugli stati** gira nel browser e controlla la pagina nello stato in cui la mette una persona: l'indicatore di focus, le trappole per la tastiera, l'ordine di tabulazione, il contenuto solo al passaggio del mouse, una finestra modale aperta che lascia il focus dietro di sé - e il percorso nel modulo: un campo senza nome accessibile dopo l'esecuzione degli script, un campo chiamato solo dal suo placeholder, un valore che il browser stesso rifiuta senza che nulla lo annunci, e un testo di errore a schermo a cui nessun campo rimanda. Legge e non agisce: non scrive, non clicca e non invia nulla, perché su un sito vero ognuna di queste azioni attiva i gestori della pagina. Riempire un campo per vedere come reagisce il modulo resta quindi fuori portata, come l'INP, che senza input reale non si misura.

### Siti dietro un accesso

Metà di ciò che vale la pena controllare sta dietro un accesso: un'area di amministrazione, un'area personale, una intranet, uno staging sotto autenticazione di base. Due cose distinte, in quest'ordine.

**Lo strumento dice quando sta guardando una porta.** La scansione registra se un indirizzo ha risposto con un accesso invece che con una pagina - un 401 con lo schema che dichiara, un 403 senza, un reindirizzamento a un indirizzo di accesso, un campo password nel markup - e lo riporta come un fatto sulla **scansione**, non come un rilievo sul sito. Un muro che risponde su quaranta indirizzi è una riga sola, e quando tutto ciò che la scansione ha letto era un muro lo dice chiaramente: un riepilogo pulito su nient'altro che moduli di accesso è l'output più fuorviante che questo strumento possa produrre. Il report porta lo stesso paragrafo, perché il report è ciò che una persona consegna a un'altra.

**L'accesso lo fai tu.** `xanalyze login https://example.com/admin` apre una vera finestra del browser sul modulo del sito; 2FA, SSO e captcha funzionano, perché è un browser. Lo strumento non vede mai nome utente o password: viene conservato solo ciò che il sito ha dato a quel browser, in un profilo intitolato all'host, nella cartella dell'app, leggibile solo da te. Le scansioni di quell'host la usano poi in **entrambi** i client: il fetch e il rendering ricevono la stessa sessione, altrimenti il browser vedrebbe l'account e la scansione il modulo di accesso. `--no-session` legge il sito come lo vede un estraneo. `xanalyze login --list` mostra che cosa c'è su questa macchina, `xanalyze login --forget HOST` ne rimuove una, e lo stesso elenco con un pulsante è nelle Impostazioni. Una scansione che era autenticata e ha comunque trovato un muro dice che la sessione è scaduta, invece di segnalare il sito come chiuso. Nella finestra è il pulsante **Accedi al sito**.

Nulla di una sessione raggiunge mai un report, un log, una cartella di scansione o il terminale: il fatto e l'host, mai un valore.

**Due larghezze affiancate.** La colonna di anteprima ha un selettore di larghezza, e un selettore risponde a una larghezza per volta: verificare «si rompe solo su mobile» voleva dire passare avanti e indietro tenendo a mente il layout desktop. Il pulsante di confronto mette in scena insieme la larghezza più ampia e la più stretta tra quelle controllate, entrambe sulla stessa pagina; il selettore continua a comandare il pannello di sinistra, così qualsiasi larghezza può essere messa a confronto con il controllo di reflow a 320 px. La seconda anteprima viene creata solo al primo clic, perché una vista browser è un processo di rendering a sé.

**Da dove iniziare.** Una scansione di una cartella risponde «820 rilievi», e in
cima a quell'elenco ci sono le stesse regole di pagina ripetute in ogni documento.
Il report parte invece dalle tre cose più pesanti per **tipo** di documento -
pagine, componenti, email - ordinate per conseguenza e non per quantità: una
cartella di newsletter e landing page si legge come due elenchi brevi invece che
come uno lungo.

I risultati hanno livello `exact`, `needs-browser` o `advisory`. `exact` significa che il markup risolve la domanda, `advisory` che nulla la risolve e decide una persona: è una scelta redazionale, ed è ciò che sono i segnali GEO.

**L'indeciso non viene mostrato.** `needs-browser` è un motore che dice di non aver potuto stabilire: «l'elemento sta su un'immagine di sfondo», «posizionato in modo assoluto, il colore di sfondo non è determinabile». Misurato su una pagina di python.org con un browser vero: erano **312 su 348** rilievi sul contrasto, e l'intera scansione è passata da 497 a **182** una volta usciti. Un report fatto per due terzi di «non lo sappiamo» non è un elenco su cui si lavora, quindi la scansione dice quanti ne ha lasciati fuori e `--unsettled` li riporta. `--confidence exact` è la vista ancora più stretta: toglie anche gli editoriali.

La provenienza media legge IPTC/XMP e C2PA. I fatti del repository comprendono `.env`, commit e configurazioni degli assistenti AI e blame. Sono informazioni di provenienza, non difetti dell'uso di un assistente.

Su un sito scansionato viene letta **ogni immagine** a cui le pagine fanno riferimento, non un campione. Si scarica solo l'intestazione del file - una richiesta HTTP range dei primi 512 KB, dove stanno quei campi e le dimensioni in pixel e dove si ferma la ricerca del marcatore C2PA - così una fotografia da 6 MB costa 512 KB e dopo la lettura non resta nulla in memoria. Le immagini con byte identici a una già letta vengono riconosciute per hash, analizzate una volta sola e riportate una volta sola con tutti i punti in cui compaiono. Il report dichiara quanti indirizzi sono stati trovati, quanti letti, quanti erano ripetizioni e cosa non è stato scaricato: un'immagine che nessuno ha letto non è risultata pulita, non è arrivata.

### Lavoro consegnato come frammento del sito di qualcun altro

Un **tema o plugin WordPress** viene riconosciuto come lo riconosce WordPress stesso: dall'intestazione `Theme Name:` in `style.css` e `Plugin Name:` nel file PHP principale del plugin, non dai marcatori dell'installazione attorno — un tema consegnato non ne ha. I suoi template sono letti come frammenti, quindi nessuno chiede a `header.php` un canonical o un `<h1>`: il documento si apre lì e si chiude in `footer.php`.

Una **web part SharePoint** è un sottoalbero di una pagina che appartiene al tenant. `--within SELECTOR` restringe l'intero audit a essa: le regole statiche leggono solo quel sottoalbero, ad axe viene passato come contesto `include`, e HTML_CodeSniffer, il passaggio sugli stati e le misurazioni vengono disattivati dichiarandone il motivo — ognuno di essi legge per costruzione l'intero documento. Il sottoalbero è un frammento qualunque fosse il file, quindi le regole di pagina smettono di applicarsi. Un suffisso generato nella classe o nell'id — `CanvasZone_9f8e7d`, `root-137` — non va digitato: il selettore viene riprovato sulla radice del nome, e viene dichiarato quale lettura ha funzionato. Un selettore che non trova nulla è un errore, mai una pagina pulita.

### Markup dentro un template literal

`.ts`, `.js` e `.mjs` sono saltati come file: lì un `<` è un operatore, e `if (a < b)` passato a un parser HTML è un tag aperto che si mangia tutto il resto. Ma una stringa tra backtick non è codice, e una web part SPFx classica ci costruisce dentro tutta la sua interfaccia. Misurato su una soluzione SharePoint reale: lo fanno 72 dei suoi 168 file `.ts`, niente di tutto ciò era mai stato letto, e leggerlo trova 131 cose - 60 controlli senza nome accessibile, 21 immagini senza alt, 24 link che aprono una nuova scheda senza `rel`. Il literal viene analizzato come il frammento che è, `${...}` diventa un valore segnaposto perché l'attributo risulti presente, e ogni risultato indica la riga in cui il literal inizia.

### Molte web part in un solo repository

Una soluzione SharePoint non è un singolo artefatto: i repository su cui è stato misurato ne contengono 30 e 19. Tre domande diverse, tre risposte: una web part **come codice** (la cartella è lo scope, la modalità repository la legge già così), una web part **sul sito** (`--within SELECTOR`), e **le web part di questo repository su tutto il sito** (`--repo PATH --web-parts`). Con un repository indicato e nessun flag di restrizione, la risposta resta l'intero sito e il repository serve a nominare il file dietro un risultato.

`--web-parts` legge i manifest della soluzione - JSONC, con commenti e virgole finali, cioè quello che scrive il generatore SPFx - e trova ogni parte nella pagina tramite il GUID che SharePoint inserisce nel DOM, con fallback sulle radici dei nomi delle classi del CSS module della parte. Ogni risultato dichiara la parte a cui appartiene e come è stata trovata. Una pagina che non ne contiene nessuna non produce nulla: quali parti il tenant abbia messo in pagina non riguarda il repository.

### Cosa l'esecuzione dichiara di non fare

Prima di iniziare, l'esecuzione nomina la profondità che non raggiungerà e il flag che la raggiungerebbe: un sito senza `--repo` riporta la pagina e non il file dietro di essa; un repository senza `--devserver` non viene mai renderizzato, quindi contrasto, ordine di focus, reflow e tutte le misurazioni non girano; `--no-browser` e la larghezza singola predefinita dicono lo stesso di sé. Le righe hanno il prefisso `# [hint]` su stderr, così un agente che guida la CLI può rispondere con il flag invece di accettare il risultato superficiale. È un avviso, mai una domanda - una scansione che si blocca non sta in una pipeline - e `--no-hints` lo silenzia. La TUI mostra le stesse righe nel suo log.

### La lingua del report

Indicata, rilevata o inglese, in quest'ordine. `--language uk|it|en` decide. Senza, decidono le pagine, ma solo se sono scritte in una di quelle tre: `lang_detect` risponde `other` per una lingua di cui questo strumento non ha liste, e un report in `other` non esiste - niente etichette, niente traduzioni, niente consigli. Tutto il resto è inglese, e l'esecuzione dichiara cosa ha scelto e su quanti passaggi leggibili.

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

Il report è disegnato con la palette di XAnalyze, quindi una gravità ha un solo colore qui, nella finestra e nella TUI. Solo due sistemi di colore portano significato, e nessun altro:

* **Gli elementi sono colorati per ruolo.** Il markup citato è evidenziato tag per tag - landmark, controllo interattivo, contenitore di raggruppamento, media, contenuto testuale, metadati del documento - con una legenda stampata una volta sola e limitata ai ruoli effettivamente presenti. Sei ruoli invece di un colore per ogni nome di tag: una tinta che significa «questo è un controllo» si impara, l'hash di un nome no.
* **Rosso e verde sono la direzione del diff, e nient'altro.** Il markup trovato e il markup come dovrebbe essere sono segnati `−` e `+` e colorati di conseguenza; la prosa «come correggere» porta lo stesso verde, perché è la stessa affermazione a parole.

Ogni rilievo dichiara inoltre la propria identità tecnica su una riga - id della regola, motore, elemento, quanti motori concordano, in quanti punti è stato trovato - così una riga si può cercare, silenziare o confrontare con l'esecuzione precedente partendo dalla pagina stampata. Nulla nel documento è troncato con i puntini: la frase di un motore è stampata per intero, e così il nome di una regola in classifica.

Un rilievo non accertato lo dichiara, in entrambi i documenti. `advisory` e `needs-browser` portano un badge nel report grafico e un campo `certainty` nel briefing per agenti, e ciascuno porta la frase che dice che cosa **non** è: «questo nessuno lo verificherà al posto tuo», «aprilo in un browser». `exact` non ha volutamente né l'uno né l'altro: un documento in cui quasi tutte le righe portano una nota di certezza insegna a saltarla. Entrambi i fatti arrivavano fin dall'inizio alla finestra e al terminale, e a nessuno dei due artefatti che una persona consegna a qualcun altro.

## Interfacce

La GUI offre controlli per target, tipo di analisi, detector, scope, profondità, breakpoint, lingua e account. I risultati includono elenco, anteprima, dettagli, correzioni ed esportazione. Le correzioni meccaniche sono selezionate in automatico, le bozze del modello richiedono revisione.

La prima scheda, **Che cosa guardiamo**, dice che cosa è risultata la cartella scelta. Un progetto viene identificato dai propri file marcatori, e ciò che è decide che cosa considerare codice di terzi: ora la finestra applica quelle esclusioni come `xanalyze audit` ha sempre fatto - la stessa cartella WordPress produceva centinaia di rilievi nel core di terze parti dalla finestra e nessuno dalla CLI. Non accade in silenzio. La scheda nomina lo stack, conta i percorsi che salterà, conserva il file marcatore che ha provato ciascuno e offre **Analizzare anche quelli** con un clic, perché un profilo è una prova di proprietà, non una certezza.

La stessa scheda porta **Questi documenti sono**, cioè `--medium` nella finestra. Di default si legge dal markup, il che è quasi sempre corretto; indicalo a mano per un'email che non ha né namespace Outlook né merge tag. Con `email` i controlli solo-browser (canonical, Open Graph, dati strutturati, skip link, landmark, WebP) vengono saltati, quelli di accessibilità no: `image-alt`, `control-name`, `table-headers`, contrasto e lingua sono reali in un client di posta quanto in un browser.

**Ciò che la finestra ora può chiedere e prima poteva chiedere solo la riga di comando.** Tre cose, nella riga avanzata:

- **Il codice dietro questo sito.** Un rilievo su una pagina indica la pagina, e la pagina è dove guardare, mai dove correggere. Indicata la cartella, ogni passaggio presente anche lì riceve il file e la riga: lo stesso abbinamento di `--repo` della CLI, tramite lo stesso modulo. La scansione dice quanti passaggi la cartella ha spiegato: tre su quaranta significa cartella sbagliata, o testo che arriva da un CMS, e una finestra che mostrasse solo i tre abbinati non lo direbbe mai.
- **Solo questa parte della pagina** (`--within`). Un selettore CSS per una web part consegnata o un widget incorporato: il resto del documento è di qualcun altro. Ciò che sta dentro il selettore è per costruzione un frammento, quindi le regole di pagina non si applicano, e un selettore che non trova nulla viene segnalato invece di restituire un risultato pulito.
- **Numero massimo di file nella cartella** (`--max-files`), nelle Impostazioni. La finestra non aveva un limite proprio e leggeva quello predefinito, senza mai dire quale numero avesse troncato un monorepo.

**Prima di una scansione la finestra ora dice che cosa non raggiungerà**: gli stessi avvisi che `cli_impl/prerun.py` stampa per la CLI, dagli stessi dati - nessuna cartella abbinata, un progetto che potrebbe servirsi da solo, un browser disattivato. Ognuno porta con sé l'azione che lo risolve, dove la finestra ne ha una.

La finestra non ha una scansione incrementale. `scan --incremental` riusa i **rilievi** in cache, righe di un file JSON senza alcun `TextSpan` dietro, mentre l'elenco della finestra è costruito sugli span: per ognuno offre una riscrittura, una sostituzione e una scrittura su disco. Riusare la cache lì produrrebbe righe su cui non si può agire, quindi il flag resta di CLI e TUI finché la cache non conterrà gli span.

Eseguire `xanalyze` senza argomenti apre la TUI con Scan, Audit, Full Scan, Reports, Settings, Account, Update, Uninstall e Logs. Navigazione: frecce, tasti numerici, `Tab`, `Esc`, `q`.

**Account** accede all'abbonamento xFormat senza lasciare il terminale. Le impostazioni hanno sempre offerto `xformat` come provider e nella TUI non c'era dove accedere, quindi quella scelta si poteva concretizzare solo dalla finestra o con `xanalyze ai login`. La password non viene salvata: viene scambiata con un token che finisce nel keychain di sistema, e il campo viene svuotato prima della chiamata. Gli altri due provider hanno un accesso proprio e la schermata dice dove, invece di offrire un modulo che non può funzionare.

Le celle delle tabelle vanno a capo invece di essere tagliate. Il dettaglio del log e il target dell'esecuzione venivano tagliati dalla schermata stessa, il che rimuoveva il `key=value` che spiegava la riga e il **dominio** che identificava l'esecuzione.

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
- **Il passaggio offline sulle formulazioni è debole in italiano, e ora lo strumento lo dice durante la scansione.** Sulla metà held-out del corpus trova il 36% dei passaggi AI noti in italiano contro il 55% in inglese e il 71% in ucraino, mentre il detector embedding trova 100%, 85% e 86%. Una scansione la cui pagina risulta in italiano stampa un avviso che nomina il detector migliore e lo ripete nel JSON come `scan.detector_note`. Il passaggio sulle formulazioni resta il predefinito perché è istantaneo, non richiede `torch`, nomina la frase trovata e sa sostituirla offline, e intercetta quattro passaggi held-out che embedding non vede.
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
