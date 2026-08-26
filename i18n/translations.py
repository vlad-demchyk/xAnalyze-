"""UI string translations for uk / it / en.

Add a new UI language by adding one more dict entry — the UI code never
hardcodes strings, it always looks them up through `t(key)`.
"""
from __future__ import annotations

LANGUAGES = {"uk": "Українська", "it": "Italiano", "en": "English"}

_STRINGS: dict[str, dict[str, str]] = {
    # Window title only (OS title bar / dock / taskbar) — the in-app header
    # already shows the "XAnalyze" wordmark on its own (see main_window's
    # brand_name label), so this needs the name plus what the app does,
    # not the bare name again.
    "app_title": {
        "uk": "XAnalyze — сканер ознак ШІ в тексті",
        "it": "XAnalyze — scanner di contenuti IA",
        "en": "XAnalyze — AI content scanner",
    },
    "url_label": {
        "uk": "URL:",
        "it": "URL:",
        "en": "URL:",
    },
    "url_label_full": {
        "uk": "URL сторінки",
        "it": "URL della pagina",
        "en": "Page URL",
    },
    "url_placeholder": {
        "uk": "https://example.com",
        "it": "https://example.com",
        "en": "https://example.com",
    },
    "depth_label": {
        "uk": "Глибина:",
        "it": "Profondità:",
        "en": "Depth:",
    },
    "depth_label_full": {
        "uk": "Глибина обходу посилань",
        "it": "Profondità di scansione dei link",
        "en": "Link crawl depth",
    },
    "detector_label": {
        "uk": "Детектор:",
        "it": "Rilevatore:",
        "en": "Detector:",
    },
    # The window no longer asks which detector class to build - it asks which
    # account reads the text, and works the detector out from that plus the
    # method. See `MainWindow._detector_for_request`.
    "provider_label": {
        "uk": "Модель:",
        "it": "Modello:",
        "en": "Model:",
    },
    "provider_label_full": {
        "uk": "Чий акаунт читає текст і платить за прохід моделі.",
        "it": "Quale account legge il testo e paga il passaggio del modello.",
        "en": "Whose account reads the text and pays for the model pass.",
    },
    "provider_anthropic": {
        "uk": "Anthropic (свій ключ)",
        "it": "Anthropic (chiave propria)",
        "en": "Anthropic (own key)",
    },
    "provider_xformat": {
        "uk": "Акаунт xFormat",
        "it": "Account xFormat",
        "en": "xFormat account",
    },
    "provider_claude-code": {
        "uk": "Сесія Claude Code",
        "it": "Sessione Claude Code",
        "en": "Claude Code session",
    },
    "ui_language_label": {
        "uk": "Мова:",
        "it": "Lingua:",
        "en": "Lang:",
    },
    "ui_language_label_full": {
        "uk": "Мова інтерфейсу",
        "it": "Lingua dell'interfaccia",
        "en": "Interface language",
    },
    "analyze_button": {
        "uk": "Аналізувати",
        "it": "Analizza",
        "en": "Analyze",
    },
    "cancel_button": {
        "uk": "Скасувати",
        "it": "Annulla",
        "en": "Cancel",
    },
    "status_idle": {
        "uk": "Готово до роботи",
        "it": "Pronto",
        "en": "Ready",
    },
    "status_crawling": {
        "uk": "Обхід сторінок: {url} (рівень {depth})",
        "it": "Scansione pagina: {url} (livello {depth})",
        "en": "Crawling: {url} (depth {depth})",
    },
    "status_detecting": {
        "uk": "Аналіз тексту детектором «{detector}»…",
        "it": "Analisi del testo con «{detector}»…",
        "en": "Analyzing text with '{detector}'…",
    },
    "status_done": {
        "uk": "Готово: {pages} стор., {blocks} фрагментів, {flags} позначено",
        "it": "Fatto: {pages} pagine, {blocks} blocchi, {flags} segnalati",
        "en": "Done: {pages} pages, {blocks} blocks, {flags} flagged",
    },
    # A repository is measured in files, not pages. The web wording was
    # being used for both, so a scan of four hundred files reported "318
    # pages" - the same slip as the summary line asking a repo result for
    # `pages`.
    "status_done_repo": {
        "uk": "Готово: {pages} файлів, {blocks} фрагментів, {flags} позначено",
        "it": "Fatto: {pages} file, {blocks} blocchi, {flags} segnalati",
        "en": "Done: {pages} files, {blocks} blocks, {flags} flagged",
    },
    "repo_preview_header": {
        "uk": "Файли репозиторія", "it": "File del repository",
        "en": "Repository files",
    },
    "status_error": {
        "uk": "Помилка: {error}",
        "it": "Errore: {error}",
        "en": "Error: {error}",
    },
    "flagged_list_header": {
        "uk": "Позначені фрагменти",
        "it": "Frammenti segnalati",
        "en": "Flagged passages",
    },
    "replace_placeholder": {
        "uk": "Впишіть заміну (лише локальна чернетка)…",
        "it": "Scrivi il testo sostitutivo (solo bozza locale)…",
        "en": "Type a replacement (local draft only)…",
    },
    "replace_save": {
        "uk": "Зберегти чернетку",
        "it": "Salva bozza",
        "en": "Save draft",
    },
    "replace_note": {
        "uk": "Заміна не публікується на сайт — це лише локальний чернетковий варіант для копіювання.",
        "it": "La sostituzione non viene pubblicata sul sito — è solo una bozza locale da copiare.",
        "en": "This replacement is not published to the site — it's a local draft you can copy out.",
    },
    "confidence_low": {"uk": "низька", "it": "bassa", "en": "low"},
    "confidence_medium": {"uk": "середня", "it": "media", "en": "medium"},
    "confidence_high": {"uk": "висока", "it": "alta", "en": "high"},
    "source_page": {
        "uk": "Джерело: {url}",
        "it": "Fonte: {url}",
        "en": "Source: {url}",
    },
    "no_flags": {
        "uk": "Підозрілих фрагментів не знайдено.",
        "it": "Nessun frammento sospetto trovato.",
        "en": "No suspicious passages found.",
    },
    "detector_unavailable": {
        "uk": "Детектор недоступний: {reason}",
        "it": "Rilevatore non disponibile: {reason}",
        "en": "Detector unavailable: {reason}",
    },
    "site_preview_header": {
        "uk": "Копія сторінки",
        "it": "Anteprima della pagina",
        "en": "Page preview",
    },
    "detail_original_label": {
        "uk": "Оригінал:",
        "it": "Originale:",
        "en": "Original:",
    },
    "detail_analyze_button": {
        "uk": "Додатковий аналіз",
        "it": "Analisi aggiuntiva",
        "en": "Additional analysis",
    },
    "detail_analyze_tooltip": {
        "uk": "Запустити повторний аналіз лише цього фрагмента поточним детектором",
        "it": "Riavvia l'analisi solo di questo frammento con il rilevatore attuale",
        "en": "Re-run analysis on just this passage with the current detector",
    },
    "detail_refactor_button": {
        "uk": "Рефактор через мій AI",
        "it": "Rifattorizza con la mia IA",
        "en": "Refactor via my AI",
    },
    "detail_refactor_tooltip": {
        "uk": "Надіслати фрагмент до вашого AI-провайдера для перепису",
        "it": "Invia il frammento al tuo provider IA per la riscrittura",
        "en": "Send this passage to your AI provider for rewriting",
    },
    "detail_analyzing": {
        "uk": "Аналізую фрагмент…",
        "it": "Analisi del frammento…",
        "en": "Analyzing passage…",
    },
    "detail_refactor_not_configured": {
        "uk": "Інтеграція з бекендом ще не налаштована. Це запланована функція — див. backend_connector.py.",
        "it": "L'integrazione con il backend non è ancora configurata. Funzione pianificata — vedi backend_connector.py.",
        "en": "Backend integration isn't configured yet. This is a planned feature — see backend_connector.py.",
    },
    "select_prompt": {
        "uk": "Виберіть фрагмент зі списку зліва",
        "it": "Seleziona un frammento dall'elenco",
        "en": "Select a passage from the list",
    },
    "suppression_note": {
        "uk": "Знахідки, про які ви вже вирішили. Особисті записи діють на всі "
              "проєкти; приберіть запис, щоб побачити цю знахідку знову при "
              "наступному скані.",
        "it": "Rilievi su cui hai già deciso. Le voci personali valgono per "
              "ogni progetto; rimuovine una per rivedere quel rilievo alla "
              "prossima scansione.",
        "en": "Findings you've already decided about. Personal entries apply "
              "to every project; remove one to see that finding again on the "
              "next scan.",
    },
    "suppression_add": {"uk": "Додати", "it": "Aggiungi", "en": "Add"},
    "suppression_remove": {
        "uk": "Прибрати вибране",
        "it": "Rimuovi selezionati",
        "en": "Remove selected",
    },
    "suppression_add_placeholder": {
        "uk": "додати…", "it": "aggiungi…", "en": "add…",
    },
    "suppression_rule_placeholder": {
        "uk": "id правила", "it": "id regola", "en": "rule id",
    },
    "suppression_empty": {"uk": "порожньо", "it": "vuoto", "en": "empty"},
    "suppression_fingerprints": {
        "uk": "Точні знахідки",
        "it": "Rilievi esatti",
        "en": "Exact findings",
    },
    "suppression_fingerprints_hint": {
        "uk": "Одна конкретна знахідка, відхилена один раз - переживає "
              "повторний скан і не впливає ні на що інше.",
        "it": "Un singolo rilievo, ignorato una volta: sopravvive a una nuova "
              "scansione e non tocca nient'altro.",
        "en": "One exact finding, dismissed once - survives a re-scan, "
              "nothing else.",
    },
    "suppression_phrases": {
        "uk": "Фрази",
        "it": "Frasi",
        "en": "Phrases",
    },
    "suppression_phrases_hint": {
        "uk": "Слово або фраза більше ніколи не позначається, ніде.",
        "it": "Una parola o frase non viene più segnalata, da nessuna parte.",
        "en": "A word or phrase never flagged again, anywhere.",
    },
    "suppression_rules": {
        "uk": "Правила",
        "it": "Regole",
        "en": "Rules",
    },
    "suppression_rules_hint": {
        "uk": "Ціла перевірка вимкнена - сигнал стилю, категорія символів або "
              "id правила доступності.",
        "it": "Un intero controllo disattivato: un segnale di stile, una "
              "categoria di caratteri o l'id di una regola di accessibilità.",
        "en": "A whole check switched off - a style signal, a character "
              "category, or an accessibility rule id.",
    },
    "suppression_paths": {
        "uk": "Шляхи",
        "it": "Percorsi",
        "en": "Paths",
    },
    "suppression_paths_hint": {
        "uk": "Файл або шаблон URL повністю виключений з аналізу.",
        "it": "Un file o un pattern di URL escluso completamente dall'analisi.",
        "en": "A file or URL pattern excluded from analysis entirely.",
    },
    "suppression_selectors": {
        "uk": "Селектори",
        "it": "Selettori",
        "en": "Selectors",
    },
    "suppression_selectors_hint": {
        "uk": "Частина сторінки виключена - CSS-селектор.",
        "it": "Una parte della pagina esclusa: un selettore CSS.",
        "en": "A part of the page excluded - a CSS selector.",
    },
    # --- Noise control (artboard 3k) ---------------------------------------
    "noise_title": {
        "uk": "Що не показувати",
        "it": "Che cosa non mostrare",
        "en": "What not to show",
    },
    "noise_where": {
        "uk": "записується у .xanalyze-ignore сканованої теки, або у ваші "
              "налаштування для скану сайту",
        "it": "scritto nel .xanalyze-ignore della cartella scansionata, o "
              "nelle tue impostazioni per la scansione di un sito",
        "en": "written to .xanalyze-ignore in the scanned folder, or to your "
              "settings for a site scan",
    },
    "settings_tab_noise": {
        "uk": "Шум", "it": "Rumore", "en": "Noise",
    },
    "noise_count": {
        "uk": "Зараз приховано записів: {count}",
        "it": "Voci attualmente nascoste: {count}",
        "en": "Currently hidden: {count} entries",
    },
    "noise_open": {
        "uk": "Керування шумом…",
        "it": "Gestione del rumore…",
        "en": "Noise control…",
    },
    "noise_hidden": {
        "uk": "Приховані знахідки",
        "it": "Rilievi nascosti",
        "en": "Hidden findings",
    },
    "noise_hidden_hint": {
        "uk": "приберіть запис, і знахідка повернеться при наступному скані",
        "it": "rimuovi una voce e il rilievo torna alla prossima scansione",
        "en": "remove an entry and the finding comes back on the next scan",
    },
    "noise_hidden_empty": {
        "uk": "Нічого не приховано.",
        "it": "Niente di nascosto.",
        "en": "Nothing is hidden.",
    },
    "noise_restore": {
        "uk": "Повернути", "it": "Ripristina", "en": "Restore",
    },
    "noise_paths": {
        "uk": "Файли й папки", "it": "File e cartelle", "en": "Files and folders",
    },
    "noise_paths_hint": {
        "uk": ".gitignore-подібний синтаксис",
        "it": "sintassi in stile .gitignore",
        "en": "gitignore-like syntax",
    },
    "noise_rules": {
        "uk": "Вимкнені правила", "it": "Regole disattivate",
        "en": "Disabled rules",
    },
    "noise_rules_add": {
        "uk": "+ додати", "it": "+ aggiungi", "en": "+ add",
    },
    "noise_origin_personal": {
        "uk": "особистий запис",
        "it": "voce personale",
        "en": "personal entry",
    },
    "noise_origin_project": {
        "uk": ".xanalyze-ignore",
        "it": ".xanalyze-ignore",
        "en": ".xanalyze-ignore",
    },
    "noise_no_project_file": {
        "uk": "Тека для .xanalyze-ignore не вибрана, тож правки йдуть у ваші "
              "особисті налаштування.",
        "it": "Nessuna cartella scelta per .xanalyze-ignore, quindi le "
              "modifiche vanno nelle tue impostazioni personali.",
        "en": "No folder chosen for a .xanalyze-ignore, so edits go to your "
              "personal settings.",
    },
    "ignore_finding": {
        "uk": "Не показувати цю знахідку",
        "it": "Ignora questo rilievo",
        "en": "Ignore this finding",
    },
    "ignore_finding_hint": {
        "uk": "Приховати саме цю знахідку, щоб вона не поверталась при "
              "повторному скані. Запис іде у .xanalyze-ignore у сканованій "
              "теці, або у ваші налаштування, якщо теки немає (скан сайту).",
        "it": "Nascondi esattamente questo rilievo, così non riappare a una "
              "nuova scansione. Salvato in .xanalyze-ignore nella cartella "
              "scansionata, o nelle tue impostazioni quando non c'è una "
              "cartella (scansione di un sito).",
        "en": "Suppress this exact finding at the fingerprint level, so it "
              "does not reappear on a re-scan. Written to .xanalyze-ignore in "
              "the scanned folder, or to your personal settings when there is "
              "no folder to write into (a web scan).",
    },
    "audit_places": {
        "uk": "Знайдено у {count} місцях",
        "it": "Trovato in {count} punti",
        "en": "Found in {count} places",
    },
    "detail_header": {
        "uk": "Деталі знахідки",
        "it": "Dettagli del rilievo",
        "en": "Finding detail",
    },
    # --- the runs catalogue ---
    "settings_cc_model": {
        "uk": "Модель", "it": "Modello", "en": "Model",
    },
    "settings_cc_effort": {
        "uk": "Зусилля", "it": "Sforzo", "en": "Effort",
    },
    # The run summary strip under the controls (artboard 3a). The counted
    # nouns stay plural in every form: the strip is only ever shown after a
    # run, and a run with one finding still reads as a tally, not a sentence.
    # The run-in-progress column (artboard 3g). "Stages" is a section label
    # over a list, so it stays a bare noun in every language.
    "progress_title": {
        "uk": "Прогін іде", "it": "Esecuzione in corso", "en": "Run in progress",
    },
    "progress_stages": {"uk": "Етапи", "it": "Fasi", "en": "Stages"},
    "progress_log": {"uk": "Лог", "it": "Log", "en": "Log"},
    "stage_crawl": {
        "uk": "Обхід посилань", "it": "Scansione dei link", "en": "Crawling links",
    },
    "stage_extract": {
        "uk": "Витяг тексту", "it": "Estrazione del testo", "en": "Extracting text",
    },
    "stage_browser": {
        "uk": "Прохід у браузері", "it": "Passaggio nel browser",
        "en": "Browser pass",
    },
    "stage_detect": {
        "uk": "Пошук у тексті", "it": "Ricerca nel testo", "en": "Checking the text",
    },
    "stage_scan": {
        "uk": "Читання файлів", "it": "Lettura dei file", "en": "Reading files",
    },
    # The run's documents (artboard 3h). The panel names four files and
    # says which are there, so the strings that explain an absent one carry
    # the reason rather than the fact - "not written" is the part the reader
    # can already see.
    # What to do next, per empty state (artboard 3i). Verbs, because each
    # one is the move that follows from the sentence above it.
    # Two runs against each other (artboard 3n). Three sections, because
    # what was fixed, what appeared and what has not moved are acted on
    # differently - the last one is the list that says whether the current
    # approach to it is working at all.
    # What went wrong, in words (artboard 3m). The body says what it means
    # for the result, because that is the part a person decides on - the
    # evidence line beside it carries the numbers and is not translated.
    "diagnosis_blocked_title": {
        "uk": "Сайт не віддає сторінки",
        "it": "Il sito non restituisce le pagine",
        "en": "The site is not serving pages",
    },
    "diagnosis_blocked_body": {
        "uk": "На {refused} з {total} адрес сервер відмовив. Ці сторінки ніхто не "
              "прочитав, тож чистий результат по них нічого не означає.",
        "it": "Il server ha rifiutato {refused} indirizzi su {total}. Quelle "
              "pagine non sono state lette, quindi un risultato pulito su di "
              "esse non significa nulla.",
        "en": "The server refused {refused} of {total} addresses. Nobody read "
              "those pages, so a clean result on them means nothing.",
    },
    "diagnosis_unreachable_title": {
        "uk": "Частина адрес не відповіла",
        "it": "Alcuni indirizzi non hanno risposto",
        "en": "Some addresses did not answer",
    },
    "diagnosis_unreachable_body": {
        "uk": "{count} з {total} сторінок не вдалося завантажити. Решта пройшла; "
              "ці лишились непрочитаними.",
        "it": "{count} pagine su {total} non si sono caricate. Le altre sono "
              "passate; queste sono rimaste non lette.",
        "en": "{count} of {total} pages would not load. The rest went through; "
              "these stayed unread.",
    },
    "diagnosis_render_failed_title": {
        "uk": "Браузер не зміг відкрити сторінку",
        "it": "Il browser non ha aperto la pagina",
        "en": "The browser could not open the page",
    },
    "diagnosis_render_failed_body": {
        "uk": "Рендер {count} з {total} сторінок не завершився. Вони лишились "
              "тільки з кодовим проходом, тож текст, який домальовує JavaScript, "
              "там не перевірявся.",
        "it": "Il rendering di {count} pagine su {total} non e riuscito. Restano "
              "solo con la lettura del codice, quindi il testo aggiunto da "
              "JavaScript non e stato controllato.",
        "en": "Rendering did not finish for {count} of {total} pages. They are "
              "left with the code pass only, so any text JavaScript draws was "
              "not checked.",
    },
    "diagnosis_truncated_title": {
        "uk": "Обхід обрізано лімітом",
        "it": "La scansione si e fermata al limite",
        "en": "The crawl stopped at its limit",
    },
    "diagnosis_truncated_body": {
        "uk": "Прочитано {read} сторінок, а знайдено щонайменше {at_least}. "
              "Чистий результат по решті нічого не означає: їх ніхто не читав.",
        "it": "Lette {read} pagine su almeno {at_least} trovate. Un risultato "
              "pulito sulle altre non significa nulla: nessuno le ha lette.",
        "en": "Read {read} pages of at least {at_least} found. A clean result on "
              "the rest means nothing: nobody read them.",
    },
    "diagnosis_truncated_evidence": {
        "uk": "максимум сторінок за прогін: {limit}",
        "it": "massimo di pagine per esecuzione: {limit}",
        "en": "max pages per run: {limit}",
    },
    "diagnosis_media_unchecked_title": {
        "uk": "Частину зображень не перевірено",
        "it": "Alcune immagini non sono state controllate",
        "en": "Some images were not checked",
    },
    "diagnosis_media_unchecked_body": {
        "uk": "Перевірено {checked} із {found} зображень. Решту ніхто не "
              "відкривав, тож про них не сказано нічого: це не те саме, що "
              "подивитись і нічого не знайти.",
        "it": "Controllate {checked} immagini su {found}. Le altre non le ha "
              "aperte nessuno, quindi su di esse non e stato detto nulla: non "
              "e lo stesso che guardare e non trovare niente.",
        "en": "Checked {checked} of {found} images. Nobody opened the rest, so "
              "nothing has been said about them - which is not the same as "
              "looking and finding nothing.",
    },
    "diagnosis_media_unchecked_evidence": {
        "uk": "не перевірено: {unchecked}",
        "it": "non controllate: {unchecked}",
        "en": "not checked: {unchecked}",
    },
    "diagnosis_unknown_failure_title": {
        "uk": "Прогін зупинився", "it": "L'esecuzione si e fermata",
        "en": "The run stopped",
    },
    "diagnosis_unknown_failure_body": {
        "uk": "Причина не розпізнана, тож нижче те, що сказав сам прогін.",
        "it": "La causa non e riconosciuta, quindi sotto c'e cio che ha detto "
              "l'esecuzione stessa.",
        "en": "The cause was not recognised, so below is what the run itself "
              "said.",
    },
    "diagnosis_retry": {
        "uk": "Спробувати ще раз", "it": "Riprova", "en": "Try again",
    },
    "diagnosis_raise_limit": {
        "uk": "Підняти до {n}", "it": "Alza a {n}", "en": "Raise to {n}",
    },
    "diagnosis_dismiss": {
        "uk": "Сховати", "it": "Nascondi", "en": "Dismiss",
    },
    "comparison_fixed": {
        "uk": "Виправлено", "it": "Corretto", "en": "Fixed",
    },
    "comparison_appeared": {
        "uk": "Зʼявилось", "it": "Comparso", "en": "Appeared",
    },
    "comparison_unchanged": {
        "uk": "Лишилось без змін", "it": "Invariato", "en": "Unchanged",
    },
    "comparison_places": {
        "uk": "{n} місць", "it": "{n} punti", "en": "{n} places",
    },
    "comparison_runs": {
        "uk": "{n} прогонів", "it": "{n} esecuzioni", "en": "{n} runs",
    },
    "comparison_solved": {
        "uk": "Перестали спрацьовувати повністю: {rules}",
        "it": "Non si attivano piu affatto: {rules}",
        "en": "Stopped firing entirely: {rules}",
    },
    "comparison_new_rules": {
        "uk": "Правила, яких раніше не було: {rules}",
        "it": "Regole che prima non c'erano: {rules}",
        "en": "Rules that were not there before: {rules}",
    },
    "comparison_oldest_first": {
        "uk": "Спершу те, що висить найдовше: саме воно є приводом змінити підхід, "
              "а не спробувати ще раз",
        "it": "Prima cio che dura da piu tempo: e questo il motivo per cambiare "
              "approccio, non per riprovare",
        "en": "Longest-standing first: that is what argues for changing the "
              "approach rather than trying again",
    },
    "comparison_measurements": {
        "uk": "Вимірювання, а не перевірки, тому не рахуються ні як виправлене, "
              "ні як нове: {rules}",
        "it": "Misurazioni, non controlli, quindi non contano ne come corretto "
              "ne come nuovo: {rules}",
        "en": "Measurements, not checks, so they count as neither fixed nor "
              "new: {rules}",
    },
    "comparison_document": {
        "uk": "Відкрити changes.md", "it": "Apri changes.md",
        "en": "Open changes.md",
    },
    "comparison_title": {
        "uk": "Що змінилось", "it": "Cosa e cambiato", "en": "What changed",
    },
    "comparison_open": {
        "uk": "Що змінилось", "it": "Cosa e cambiato", "en": "What changed",
    },
    "empty_action_target": {
        "uk": "Обрати ціль", "it": "Scegli un obiettivo", "en": "Choose a target",
    },
    "empty_action_runs": {
        "uk": "Минулий прогін", "it": "Esecuzione precedente", "en": "A past run",
    },
    "empty_action_ai": {
        "uk": "Додати AI-прохід", "it": "Aggiungi il passaggio AI",
        "en": "Add the AI pass",
    },
    "empty_action_report": {
        "uk": "Зберегти звіт", "it": "Salva il report", "en": "Save the report",
    },
    "empty_action_open_page": {
        "uk": "Відкрити сторінку", "it": "Apri la pagina", "en": "Open the page",
    },
    "documents_title": {
        "uk": "Документи прогону", "it": "Documenti dell'esecuzione",
        "en": "Run documents",
    },
    "documents_open": {
        "uk": "Відкрити теку", "it": "Apri la cartella", "en": "Open folder",
    },
    "documents_back": {
        "uk": "До перегляду", "it": "Torna all'anteprima",
        "en": "Back to preview",
    },
    "documents_timings": {
        "uk": "Скільки тривали етапи", "it": "Quanto sono durate le fasi",
        "en": "Where the time went",
    },
    "documents_handoff": {
        "uk": "report.pdf читає людина, report.md читає агент, timings.md "
              "пояснює тривалість. Один прогін, одна тека: наступний ляже "
              "поруч і додасть changes.md.",
        "it": "report.pdf si legge, report.md lo legge un agente, timings.md "
              "spiega la durata. Un'esecuzione, una cartella: la prossima si "
              "affianca e aggiunge changes.md.",
        "en": "report.pdf is for a person, report.md is for an agent, "
              "timings.md explains the duration. One run, one folder: the "
              "next one lands beside it and adds changes.md.",
    },
    "documents_absent_first_run": {
        "uk": "перший прогін цієї цілі", "it": "prima esecuzione di questo obiettivo",
        "en": "first run of this target",
    },
    "documents_absent_not_comparable": {
        "uk": "немає порівнянного прогону", "it": "nessuna esecuzione confrontabile",
        "en": "no comparable run",
    },
    "documents_absent_no_audit": {
        "uk": "доступність не перевірялась", "it": "accessibilita non verificata",
        "en": "accessibility was not checked",
    },
    "summary_findings": {
        "uk": "{count} знахідок",
        "it": "{count} riscontri",
        "en": "{count} findings",
    },
    # The file column of a repository scan (artboard 3f). Files with
    # nothing in them are counted, not listed: four hundred rows with a zero
    # beside them is a directory listing.
    "repo_files_title": {"uk": "Файли", "it": "File", "en": "Files"},
    "repo_files_clean": {
        "uk": "{count} файлів без знахідок",
        "it": "{count} file senza riscontri",
        "en": "{count} files with no findings",
    },
    "summary_files": {
        "uk": "{count} файлів", "it": "{count} file", "en": "{count} files",
    },
    "summary_skipped_ignored": {
        "uk": "{count} пропущено за .xanalyze-ignore",
        "it": "{count} saltati per .xanalyze-ignore",
        "en": "{count} skipped by .xanalyze-ignore",
    },
    "summary_in_files": {
        "uk": "у {count} файлах", "it": "in {count} file",
        "en": "in {count} files",
    },
    "summary_pages": {
        "uk": "{count} стор.",
        "it": "{count} pag.",
        "en": "{count} pages",
    },
    "summary_documents": {
        "uk": "{count} документів",
        "it": "{count} documenti",
        "en": "{count} documents",
    },
    "runs_title": {
        "uk": "Прогони:",
        "it": "Esecuzioni:",
        "en": "Runs:",
    },
    "runs_empty": {
        "uk": "Ще немає збережених прогонів",
        "it": "Nessuna esecuzione registrata",
        "en": "No runs recorded yet",
    },
    "runs_resume": {
        "uk": "Продовжити",
        "it": "Riprendi",
        "en": "Resume",
    },
    "runs_pause": {
        "uk": "Пауза",
        "it": "Pausa",
        "en": "Pause",
    },
    "runs_open": {
        "uk": "Відкрити теку",
        "it": "Apri cartella",
        "en": "Open folder",
    },
    "runs_status_running": {"uk": "виконується", "it": "in corso",
                            "en": "running"},
    "runs_status_paused": {"uk": "на паузі", "it": "in pausa", "en": "paused"},
    "runs_status_failed": {"uk": "зупинено", "it": "interrotta",
                           "en": "stopped"},
    "runs_status_interrupted": {"uk": "перервано", "it": "interrotta",
                                "en": "interrupted"},
    "runs_status_done": {"uk": "завершено", "it": "completata",
                         "en": "complete"},
    "devserver_confirm": {
        "uk": "{stack}: залежності відсутні в {repo}. Встановити їх і запустити сервер?",
        "it": "{stack}: dipendenze mancanti in {repo}. Installarle e avviare il server?",
        "en": "{stack}: dependencies are missing in {repo}. Install them and start the server?",
    },
    "devserver_starting": {
        "uk": "Запускаю сервер розробки…",
        "it": "Avvio il server di sviluppo…",
        "en": "Starting the dev server…",
    },
    "devserver_ready": {
        "uk": "Сервер готовий: {url}",
        "it": "Server pronto: {url}",
        "en": "Server ready: {url}",
    },
    "devserver_failed": {
        "uk": "Сервер не запущено ({reason}); скановано як звичайний код",
        "it": "Server non avviato ({reason}); scansionato come codice statico",
        "en": "The dev server did not start ({reason}); scanned statically instead",
    },
    # The catalogue as a table (artboard 3c). Column heads, the subtitle
    # that tells two runs of one target apart, and the footer that says the
    # list is a window onto the disk rather than the whole of it.
    "runs_col_target": {"uk": "ЦІЛЬ", "it": "OBIETTIVO", "en": "TARGET"},
    "runs_col_state": {"uk": "СТАН", "it": "STATO", "en": "STATE"},
    "runs_col_stage": {"uk": "ЕТАП", "it": "FASE", "en": "STAGE"},
    "runs_col_found": {"uk": "ЗНАХІДОК", "it": "RISCONTRI", "en": "FOUND"},
    "runs_col_when": {"uk": "КОЛИ", "it": "QUANDO", "en": "WHEN"},
    "runs_kind_site": {"uk": "сайт", "it": "sito", "en": "site"},
    "runs_kind_repo": {"uk": "репозиторій", "it": "repository",
                       "en": "repository"},
    "runs_depth": {"uk": "глибина {n}", "it": "profondita {n}",
                   "en": "depth {n}"},
    "runs_source": {
        "uk": "читається з тек на диску",
        "it": "letto dalle cartelle su disco",
        "en": "read from the folders on disk",
    },
    "runs_footer": {
        "uk": "Показано {shown} останніх, решта у {root}",
        "it": "Mostrate le ultime {shown}, il resto in {root}",
        "en": "The last {shown} shown, the rest in {root}",
    },
    "runs_more": {"uk": "Ще", "it": "Altro", "en": "More"},
    "runs_report": {"uk": "Звіт", "it": "Report", "en": "Report"},
    "runs_compare": {"uk": "Порівняти", "it": "Confronta", "en": "Compare"},
    "runs_pause_requested": {
        "uk": "Пауза запрошена: прогін спиниться на межі наступного етапу",
        "it": "Pausa richiesta: si fermerà al confine della fase successiva",
        "en": "Pause requested: the run stops at its next phase boundary",
    },
    "runs_resuming": {
        "uk": "Продовжую прогін {run}…",
        "it": "Ripresa dell'esecuzione {run}…",
        "en": "Resuming run {run}…",
    },
    "runs_resume_done": {
        "uk": "Прогін завершено",
        "it": "Esecuzione completata",
        "en": "The run finished",
    },
    "runs_resume_incomplete": {
        "uk": "Прогін знову спинився: деталі в state.md у теці прогону",
        "it": "L'esecuzione si è fermata di nuovo: dettagli in state.md",
        "en": "The run stopped again: see state.md in the run folder",
    },
    "runs_resume_failed": {
        "uk": "Не вдалось продовжити: {reason}",
        "it": "Ripresa non riuscita: {reason}",
        "en": "Could not resume: {reason}",
    },
    "mode_label": {
        "uk": "Джерело:",
        "it": "Origine:",
        "en": "Source:",
    },
    "mode_web": {
        "uk": "Веб-сторінка",
        "it": "Pagina web",
        "en": "Web page",
    },
    # --- the three independent choices -----------------------------------
    #
    # Source, reading, question, judge. Four controls where there used to be
    # one, because they were never one decision.
    "source_site": {
        "uk": "Сайт", "it": "Sito", "en": "Site",
    },
    "source_repo": {
        "uk": "Репозиторій", "it": "Repository", "en": "Repository",
    },
    "source_file": {
        "uk": "Файл HTML", "it": "File HTML", "en": "HTML file",
    },
    "sign_in_title": {
        "uk": "Акаунт xFormat",
        "it": "Account xFormat",
        "en": "xFormat account",
    },
    "sign_in_hint": {
        "uk": "Вхід дає AI-оцінку за підпискою, без особистого ключа. "
              "Пароль не зберігається - лишаються тільки видані токени.",
        "it": "L'accesso abilita la valutazione AI con l'abbonamento, senza "
              "una chiave personale. La password non viene salvata: restano "
              "solo i token emessi.",
        "en": "Signing in enables the AI assessment on the subscription, with "
              "no personal key. The password is not stored - only the issued "
              "tokens are.",
    },
    "sign_in_switched": {
        "uk": "Увійшли: {detail}. AI-оцінка тепер іде за підпискою.",
        "it": "Accesso effettuato: {detail}. La valutazione AI usa "
              "l'abbonamento.",
        "en": "Signed in: {detail}. The AI assessment now runs on the "
              "subscription.",
    },
    "signed_out_message": {
        "uk": "Вийшли з акаунта. AI-оцінка доступна лише з особистим ключем.",
        "it": "Disconnesso. La valutazione AI richiede una chiave personale.",
        "en": "Signed out. The AI assessment needs a personal key now.",
    },
    "status_reusing_pages": {
        "uk": "Сторінки вже завантажені ({count}), обхід не потрібен",
        "it": "Pagine già scaricate ({count}), nessuna nuova scansione",
        "en": "Pages already fetched ({count}), no new crawl",
    },
    "reader_browser": {
        "uk": "У браузері", "it": "Nel browser", "en": "In a browser",
    },
    "reader_browser_unavailable": {
        "uk": "Репозиторій нічим не віддає сторінку, тож рендерити нічого: "
              "код читається як написаний.",
        "it": "Un repository non serve pagine, quindi non c'è nulla da "
              "renderizzare: il codice si legge come è scritto.",
        "en": "A repository serves no pages, so there is nothing to render: "
              "the code is read as written.",
    },
    "checks_label": {
        "uk": "Оцінка:", "it": "Valutazione:", "en": "Assess:",
    },
    "checks_label_full": {
        "uk": "Що шукати: дефекти доступності й сторінки, ознаки тексту, "
              "написаного моделлю, або і те, і те за один прогін.",
        "it": "Cosa cercare: difetti di accessibilità e di pagina, segni di "
              "testo scritto da un modello, o entrambi in una sola volta.",
        "en": "What to look for: accessibility and page defects, signs of "
              "model-written copy, or both in one run.",
    },
    "check_accessibility": {
        "uk": "Доступність", "it": "Accessibilità", "en": "Accessibility",
    },
    "check_ai_patterns": {
        "uk": "AI-патерни", "it": "Pattern AI", "en": "AI patterns",
    },
    "checks_both": {
        "uk": "Доступність і AI", "it": "Accessibilità e AI",
        "en": "Accessibility and AI",
    },
    "method_label": {
        "uk": "Метод:", "it": "Metodo:", "en": "Method:",
    },
    "method_label_full": {
        "uk": "Хто оцінює: локальний двигун без мережі, лише модель, або "
              "гібрид - локальний прохід, який модель перевіряє й доповнює.",
        "it": "Chi valuta: il motore locale senza rete, solo il modello, o "
              "l'ibrido - il passaggio locale che il modello verifica ed "
              "estende.",
        "en": "Who judges: the offline engine with no network, the model "
              "alone, or the hybrid - the offline pass, checked and extended "
              "by the model.",
    },
    "method_local": {
        "uk": "Локальний двигун", "it": "Motore locale", "en": "Offline engine",
    },
    "method_embedding": {
        "uk": "Семантичний аналіз", "it": "Analisi semantica", "en": "Semantic analysis",
    },
    "method_ai": {
        "uk": "AI", "it": "AI", "en": "AI",
    },
    # "Hybrid", not "both": the two engines no longer run side by side with
    # two lists of findings - the model checks what the offline pass found
    # and adds what it did not, and one merged list comes back. See
    # `detectors/hybrid.py`.
    "method_both": {
        "uk": "Гібрид: локальний і AI",
        "it": "Ibrido: locale e AI",
        "en": "Hybrid: offline and AI",
    },
    "method_ai_unavailable": {
        "uk": "Для AI потрібен ключ або вхід у акаунт xFormat. Прогін іде "
              "локальним двигуном.",
        "it": "L'AI richiede una chiave o l'accesso a un account xFormat. "
              "L'esecuzione usa il motore locale.",
        "en": "The AI pass needs a key or a signed-in xFormat account. "
              "Running the offline engine instead.",
    },
    "mode_repo": {
        "uk": "Репозиторій (код)",
        "it": "Repository (codice)",
        "en": "Repository (code)",
    },
    "fix_on_disk_button": {
        "uk": "Виправити у файлі", "it": "Correggi nel file",
        "en": "Fix in the file",
    },
    "fix_on_disk_tooltip": {
        "uk": "Записати виправлення просто у файли. Перед першою зміною "
              "зберігається копія .bak, тож повернутися можна завжди.",
        "it": "Scrive le correzioni direttamente nei file. Prima della prima "
              "modifica viene salvata una copia .bak, quindi si può sempre "
              "tornare indietro.",
        "en": "Write the corrections straight into the files. A .bak copy is "
              "saved before the first change, so going back is always "
              "possible.",
    },
    "undo_fix_button": {
        "uk": "Відкотити", "it": "Annulla", "en": "Undo",
    },
    "undo_fix_tooltip": {
        "uk": "Повернути файли до стану перед першим виправленням.",
        "it": "Riporta i file allo stato precedente alla prima correzione.",
        "en": "Put the files back the way they were before the first "
              "correction.",
    },
    # One button for two documents; the type is asked at click time. See
    # `MainWindow._on_download_clicked` for why they were not merged into one
    # document as well.
    "reader_browser_empty": {
        "uk": "Браузер відкрив документ, але не побудував жодної розмітки. "
              "Прогін не робився: порожня відповідь не є чистим результатом.",
        "it": "Il browser ha aperto il documento ma non ha costruito alcun "
              "markup. L'analisi non è stata eseguita: una risposta vuota non "
              "è un risultato pulito.",
        "en": "The browser opened the document but built no markup at all. "
              "Nothing was analysed: an empty answer is not a clean result.",
    },
    "download_button": {
        "uk": "Завантажити", "it": "Scarica", "en": "Download",
    },
    "download_tooltip": {
        "uk": "Зберегти звіт: або документ для читання й друку, або брифінг "
              "для агента. Тип запитається після натискання.",
        "it": "Salva un report: il documento da leggere e stampare, oppure il "
              "briefing per l'agente. Il tipo viene chiesto dopo il clic.",
        "en": "Save a report: either the document to read and print, or the "
              "briefing for an agent. The type is asked after the click.",
    },
    "download_which": {
        "uk": "Який звіт зберегти?",
        "it": "Quale report salvare?",
        "en": "Which report do you want?",
    },
    "export_report_button": {
        "uk": "Звіт для агента", "it": "Report per l'agente",
        "en": "Report for an agent",
    },
    "export_report_tooltip": {
        "uk": "Зберегти файл, який можна віддати Claude Code або іншому "
              "агенту: статистика, карта файлів, кожна знахідка з готовим "
              "виправленням і що змінилося з минулого разу.",
        "it": "Salva un file da passare a Claude Code o a un altro agente: "
              "statistiche, mappa dei file, ogni rilievo con la correzione "
              "pronta e che cosa è cambiato dall'ultima volta.",
        "en": "Save a file you can hand to Claude Code or another agent: "
              "statistics, a file map, every finding with its ready "
              "correction, and what changed since last time.",
    },
    "fix_confirm_body": {
        "uk": "Готових до запису виправлень: {ready}.\n\n"
              "Ще {pending} потребують рішення або справжнього тексту - "
              "наприклад, що зображено на картинці або що обіцяє сторінка. "
              "Записати їх може модель.\n\n"
              "«Так» - модель напише і їх. «Ні» - записати лише готові.\n"
              "У будь-якому разі копія .bak зберігається перед першою зміною.",
        "it": "Correzioni pronte da scrivere: {ready}.\n\n"
              "Altre {pending} richiedono una decisione o un testo reale: per "
              "esempio che cosa mostra un'immagine o che cosa promette la "
              "pagina. Può scriverle un modello.\n\n"
              "«Sì» - le scrive anche il modello. «No» - solo quelle "
              "pronte.\nIn entrambi i casi viene salvata una copia .bak "
              "prima della prima modifica.",
        "en": "Corrections ready to write: {ready}.\n\n"
              "Another {pending} need a decision or real text - what an image "
              "shows, what the page promises. A model can write those.\n\n"
              "Yes - let the model write them too. No - write only the ready "
              "ones.\nEither way a .bak copy is saved before the first "
              "change.",
    },
    "fix_nothing_ready": {
        "uk": "Серед знахідок немає таких, які можна записати автоматично.",
        "it": "Tra i rilievi non ce n'è nessuno scrivibile automaticamente.",
        "en": "None of the findings can be written automatically.",
    },
    "fix_done": {
        "uk": "Записано виправлень: {applied} у {files} файл(ах).",
        "it": "Correzioni scritte: {applied} in {files} file.",
        "en": "Wrote {applied} correction(s) in {files} file(s).",
    },
    "fix_done_by_model": {
        "uk": "Написано моделлю, тож варто прочитати: {rules}.",
        "it": "Scritte da un modello, quindi da rileggere: {rules}.",
        "en": "Written by a model, so worth reading: {rules}.",
    },
    "fix_left_alone": {
        "uk": "Не змінено: {count}. Причини:",
        "it": "Non modificati: {count}. Motivi:",
        "en": "Left alone: {count}. Why:",
    },
    "undo_done": {
        "uk": "Повернуто файлів: {files}.",
        "it": "File ripristinati: {files}.",
        "en": "Restored {files} file(s).",
    },
    "export_report_done": {
        "uk": "Звіт збережено: {path}",
        "it": "Report salvato: {path}",
        "en": "Report saved: {path}",
    },
    "app_tagline": {
        "uk": "текст, символи і аудит сторінки",
        "it": "testo, caratteri e audit della pagina",
        "en": "text, characters and page audit",
    },
    "detail_panel_title": {
        "uk": "Знахідка", "it": "Rilievo", "en": "Finding",
    },
    "detail_line": {"uk": "рядок", "it": "riga", "en": "line"},
    "detail_element": {
        "uk": "Елемент у файлі", "it": "Elemento nel file",
        "en": "The element in the file",
    },
    "detail_replacement": {
        "uk": "Готова заміна", "it": "Sostituzione pronta",
        "en": "Ready replacement",
    },
    "detail_fix_this": {
        "uk": "Виправити це", "it": "Correggi questo", "en": "Fix this one",
    },
    "detail_fix_this_tooltip": {
        "uk": "Записати цю заміну у файл. Копія .bak зберігається перед "
              "першою зміною, тож «Відкотити» поверне все як було.",
        "it": "Scrive questa sostituzione nel file. Prima della prima modifica "
              "viene salvata una copia .bak, quindi «Annulla» riporta tutto "
              "com'era.",
        "en": "Write this replacement into the file. A .bak copy is saved "
              "before the first change, so Undo puts everything back.",
    },
    "detail_needs_decision": {
        "uk": "Це рішення, а не механічна заміна - інструмент не питатиме "
              "мовчки.",
        "it": "Questa è una decisione, non una sostituzione meccanica: lo "
              "strumento non la farà in silenzio.",
        "en": "This is a decision, not a mechanical swap - the tool will not "
              "make it silently.",
    },
    "detail_decide_body": {
        "uk": "Цю заміну не можна записати без рішення:\n\n{reason}\n\n"
              "Дозволити моделі написати значення? Копія .bak зберігається "
              "перед зміною, тож відкотити можна завжди.",
        "it": "Questa sostituzione non può essere scritta senza una "
              "decisione:\n\n{reason}\n\nVuoi che sia un modello a "
              "scrivere il valore? Una copia .bak viene salvata prima della "
              "modifica, quindi si può sempre tornare indietro.",
        "en": "This replacement cannot be written without a decision:\n\n"
              "{reason}\n\nLet a model write the value? A .bak copy is "
              "saved before the change, so it can always be undone.",
    },
    "mode_file": {
        "uk": "Один HTML-файл",
        "it": "Un singolo file HTML",
        "en": "A single HTML file",
    },
    "file_path_placeholder": {
        "uk": "Шлях до сторінки, запакованої в один файл",
        "it": "Percorso della pagina raccolta in un unico file",
        "en": "Path to a page packed into one file",
    },
    "no_file_path": {
        "uk": "Виберіть HTML-файл для аналізу.",
        "it": "Scegli un file HTML da analizzare.",
        "en": "Choose an HTML file to analyse.",
    },
    "all_files": {
        "uk": "Усі файли",
        "it": "Tutti i file",
        "en": "All files",
    },
    "mode_audit": {
        "uk": "Аудит сайту",
        "it": "Audit del sito",
        "en": "Site audit",
    },
    "browser_pass_label": {
        "uk": "У браузері",
        "it": "Nel browser",
        "en": "In a browser",
    },
    "browser_pass_tooltip": {
        "uk": "Завантажити кожну сторінку у справжньому браузері та прогнати "
              "axe-core, HTML_CodeSniffer, перевірку клавіатури і фокуса та "
              "виміри завантаження. Бачить те, що домалював JavaScript, але "
              "додає кілька секунд на сторінку.",
        "it": "Carica ogni pagina in un browser reale ed esegue axe-core, "
              "HTML_CodeSniffer, il controllo di tastiera e focus e le "
              "misurazioni di caricamento. Vede ciò che ha reso JavaScript, "
              "ma aggiunge qualche secondo per pagina.",
        "en": "Load every page in a real browser and run axe-core, "
              "HTML_CodeSniffer, the keyboard and focus pass and the load "
              "measurements. Sees what JavaScript rendered, at a cost of a "
              "few seconds per page.",
    },
    "status_auditing": {
        "uk": "Аудит: {target}",
        "it": "Audit: {target}",
        "en": "Auditing {target}",
    },
    "status_browser_pass": {
        "uk": "У браузері: {url}",
        "it": "Nel browser: {url}",
        "en": "In the browser: {url}",
    },
    "empty_audit_clean_title": {
        "uk": "Перевірено, зауважень немає",
        "it": "Controllato, nessun rilievo",
        "en": "Checked, nothing flagged",
    },
    "empty_audit_clean_body": {
        "uk": "Перевірено документів: {documents}. Це означає лише те, що "
              "правила цього інструмента нічого не знайшли. Автоматична "
              "перевірка ловить меншу частину проблем доступності, тож "
              "чистий результат не є доказом доступності сторінки.",
        "it": "Documenti controllati: {documents}. Significa soltanto che le "
              "regole di questo strumento non hanno trovato nulla. Il "
              "controllo automatico intercetta solo una parte dei problemi "
              "di accessibilità: un esito pulito non è una prova.",
        "en": "Documents checked: {documents}. That means only that this "
              "tool's rules found nothing. Automated checking catches a "
              "minority of accessibility problems, so a clean result is not "
              "proof that the page is accessible.",
    },
    "empty_audit_unreadable_title": {
        "uk": "Сторінки не вдалося прочитати",
        "it": "Pagine non leggibili",
        "en": "The pages could not be read",
    },
    "empty_audit_unreadable_body": {
        "uk": "Нічого не перевірено, бо жодну сторінку не вдалося отримати:",
        "it": "Nulla è stato controllato perché nessuna pagina è stata "
              "ottenuta:",
        "en": "Nothing was checked, because no page could be fetched:",
    },
    "audit_found": {
        "uk": "Що знайдено",
        "it": "Che cosa è stato trovato",
        "en": "What was found",
    },
    "audit_why": {
        "uk": "Чому це проблема",
        "it": "Perché è un problema",
        "en": "Why it is a problem",
    },
    "audit_fix": {
        "uk": "Як виправити",
        "it": "Come correggere",
        "en": "How to fix it",
    },
    "audit_caveat": {
        "uk": "Коли це хибне спрацювання",
        "it": "Quando è un falso positivo",
        "en": "When this is a false positive",
    },
    "audit_also_found_by": {
        "uk": "Це саме знайшли також: {engines}",
        "it": "Trovato anche da: {engines}",
        "en": "Also found by: {engines}",
    },
    "repo_path_placeholder": {
        "uk": "Шлях до папки репозиторію",
        "it": "Percorso della cartella del repository",
        "en": "Path to repository folder",
    },
    "browse_button": {
        "uk": "Огляд…",
        "it": "Sfoglia…",
        "en": "Browse…",
    },
    "exclusions_button": {
        "uk": "Фільтр…",
        "it": "Filtro…",
        "en": "Filter…",
    },
    "exclusions_button_full": {
        "uk": "Файли й папки, які виключити з аналізу",
        "it": "File e cartelle da escludere dall'analisi",
        "en": "Files/folders to exclude from analysis",
    },
    "auto_devserver_check": {
        "uk": "Автозапуск сервера",
        "it": "Avvio automatico server",
        "en": "Auto-start server",
    },
    "auto_devserver_check_full": {
        "uk": "Аналіз сам виявляє й піднімає сервер розробки репо (package.json, "
             "manage.py, Gemfile+bin/rails). Вимкнено за замовчуванням: сервер "
             "може вже бути запущений деінде",
        "it": "L'analisi rileva e avvia da sola il server di sviluppo del repo "
             "(package.json, manage.py, Gemfile+bin/rails). Disattivo per "
             "default: il server potrebbe già essere in esecuzione altrove",
        "en": "Analyze detects and starts the repo's own dev server "
             "(package.json, manage.py, Gemfile+bin/rails). Off by default: "
             "it may already be running elsewhere",
    },
    "start_server_button": {
        "uk": "Запустити сервер",
        "it": "Avvia server",
        "en": "Start server",
    },
    "start_server_button_full": {
        "uk": "Виявити й підняти сервер розробки цього репо зараз, і сканувати "
             "рендерений сайт",
        "it": "Rileva e avvia ora il server di sviluppo di questo repo, e "
             "scansiona il sito reso",
        "en": "Detect and start this repo's dev server now, and scan the "
             "rendered site",
    },
    "devserver_none_detected": {
        "uk": "Не знайдено package.json, manage.py ані Gemfile+bin/rails у цьому шляху",
        "it": "Nessun package.json, manage.py o Gemfile+bin/rails trovato in questo percorso",
        "en": "No package.json, manage.py, or Gemfile+bin/rails found at this path",
    },
    "devserver_available": {
        "uk": "Знайдено {stack}, статичний скан коду не дає найкращої точності. "
             "Вкажи URL сервера/сайту, увімкни автозапуск, або натисни "
             "«Запустити сервер»",
        "it": "Rilevato {stack}, la scansione statica del codice non dà la "
             "massima precisione. Indica l'URL del server/sito, attiva "
             "l'avvio automatico, o premi «Avvia server»",
        "en": "{stack} detected - a static code scan won't be as accurate. "
             "Give the server/site URL, turn on auto-start, or click "
             "\"Start server\"",
    },
    "exclusions_dialog_title": {
        "uk": "Файли й папки, які не аналізувати (.gitignore-подібний синтаксис)",
        "it": "File e cartelle da non analizzare (sintassi simile a .gitignore)",
        "en": "Files/folders to skip (.gitignore-style)",
    },
    "status_scanning_repo": {
        "uk": "Скануємо: {path}",
        "it": "Scansione: {path}",
        "en": "Scanning: {path}",
    },
    "generate_list_button": {
        "uk": "Сформувати список замін",
        "it": "Genera elenco sostituzioni",
        "en": "Generate replacement list",
    },
    "auto_replace_button": {
        "uk": "Замінити автоматично у файлах",
        "it": "Sostituisci automaticamente nei file",
        "en": "Auto-replace in files",
    },
    "rewriting_status": {
        "uk": "Генерую заміну {done}/{total}…",
        "it": "Generazione sostituzione {done}/{total}…",
        "en": "Generating replacement {done}/{total}…",
    },
    "confirm_auto_replace": {
        "uk": "Це запише зміни у {n} фрагмент(и/ів) прямо у файли коду (перед цим буде створено .bak-копію кожного зміненого файлу). Продовжити?",
        "it": "Questo scriverà le modifiche in {n} frammenti direttamente nei file di codice (verrà creata una copia .bak di ogni file modificato). Continuare?",
        "en": "This will write changes to {n} passage(s) directly into the code files (a .bak copy of each changed file is made first). Continue?",
    },
    "auto_replace_summary": {
        "uk": "Готово. Застосовано: {applied}. Файлів змінено: {files}. Пропущено (застаріло): {stale}. Помилки: {errors}.",
        "it": "Fatto. Applicati: {applied}. File modificati: {files}. Saltati (obsoleti): {stale}. Errori: {errors}.",
        "en": "Done. Applied: {applied}. Files changed: {files}. Skipped (stale): {stale}. Errors: {errors}.",
    },
    "export_list_prompt": {
        "uk": "Зберегти список замін у файл для ручного перегляду?",
        "it": "Salvare l'elenco delle sostituzioni in un file per la revisione manuale?",
        "en": "Save the replacement list to a file for manual review?",
    },
    "export_list_saved": {
        "uk": "Список збережено: {path}",
        "it": "Elenco salvato: {path}",
        "en": "List saved: {path}",
    },
    # Renamed from `source_file`, which was already the source picker's
    # "HTML file" label. Two different strings under one key, and the later
    # definition won - so the main source dropdown offered a literal
    # "Файл: {path}:{line}" as its third option, in all three languages.
    # `pyflakes` had been reporting the duplicate the whole time.
    "finding_file_line": {
        "uk": "Файл: {path}:{line}",
        "it": "File: {path}:{line}",
        "en": "File: {path}:{line}",
    },
    "no_repo_path": {
        "uk": "Вкажіть шлях до папки репозиторію",
        "it": "Specifica il percorso della cartella del repository",
        "en": "Specify a repository folder path",
    },

    # ----------------------------------------------------------- settings
    "settings_button": {
        "uk": "Налаштування…",
        "it": "Impostazioni…",
        "en": "Settings…",
    },
    "advanced_show": {
        "uk": "Більше…",
        "it": "Altro…",
        "en": "More…",
    },
    "advanced_hide": {
        "uk": "Менше",
        "it": "Meno",
        "en": "Less",
    },
    "settings_title": {
        "uk": "Налаштування",
        "it": "Impostazioni",
        "en": "Settings",
    },
    "settings_tab_general": {
        "uk": "Загальні",
        "it": "Generali",
        "en": "General",
    },
    "settings_tab_provider": {
        "uk": "Переписування",
        "it": "Riscrittura",
        "en": "Rewriting",
    },
    "settings_tab_advanced": {
        "uk": "Додатково",
        "it": "Avanzate",
        "en": "Advanced",
    },
    "settings_max_pages": {
        "uk": "Максимум сторінок за скан",
        "it": "Pagine massime per scansione",
        "en": "Max pages per scan",
    },
    "settings_provider": {
        "uk": "Хто оплачує переписування",
        "it": "Chi paga la riscrittura",
        "en": "Who pays for rewrites",
    },
    "settings_provider_note": {
        "uk": "Детектори працюють локально й безкоштовно. Оплачувані виклики потрібні лише для генерації замін тексту.",
        "it": "I rilevatori funzionano localmente e gratuitamente. Le chiamate a pagamento servono solo per generare le sostituzioni.",
        "en": "Detectors run locally and for free. Paid calls are only used to generate replacement text.",
    },
    "settings_api_key": {
        "uk": "API-ключ",
        "it": "Chiave API",
        "en": "API key",
    },
    "settings_model": {
        "uk": "Модель",
        "it": "Modello",
        "en": "Model",
    },
    "settings_base_url": {
        "uk": "Адреса сервера",
        "it": "URL del server",
        "en": "Server URL",
    },
    "settings_email": {
        "uk": "Пошта",
        "it": "Email",
        "en": "Email",
    },
    "settings_password": {
        "uk": "Пароль",
        "it": "Password",
        "en": "Password",
    },
    "settings_password_hint": {
        "uk": "використовується лише для входу, не зберігається",
        "it": "usata solo per l'accesso, non viene salvata",
        "en": "used only to sign in, never stored",
    },
    "settings_sign_in": {
        "uk": "Увійти",
        "it": "Accedi",
        "en": "Sign in",
    },
    "settings_sign_out": {
        "uk": "Вийти",
        "it": "Esci",
        "en": "Sign out",
    },
    "settings_check": {
        "uk": "Перевірити",
        "it": "Verifica",
        "en": "Check",
    },
    "settings_signed_in": {
        "uk": "Підключено: {detail}",
        "it": "Connesso: {detail}",
        "en": "Connected: {detail}",
    },
    "settings_not_signed_in": {
        "uk": "Не підключено: {detail}",
        "it": "Non connesso: {detail}",
        "en": "Not connected: {detail}",
    },
    "settings_signed_out": {
        "uk": "Ви вийшли з акаунта. Токени видалено.",
        "it": "Disconnesso. Token eliminati.",
        "en": "Signed out. Tokens deleted.",
    },
    "settings_quota": {
        "uk": "залишок квоти: {n}",
        "it": "quota rimanente: {n}",
        "en": "quota left: {n}",
    },
    "settings_need_credentials": {
        "uk": "Введіть пошту й пароль.",
        "it": "Inserisci email e password.",
        "en": "Enter email and password.",
    },
    "settings_storage_keyring": {
        "uk": "Токени зберігаються в системному сховищі ключів.",
        "it": "I token sono salvati nel portachiavi di sistema.",
        "en": "Tokens are stored in the OS keychain.",
    },
    "settings_storage_file": {
        "uk": "Системне сховище ключів недоступне — токени зберігаються у файлі з правами 0600. Встановіть пакет keyring для кращого захисту.",
        "it": "Portachiavi di sistema non disponibile — i token sono salvati in un file con permessi 0600. Installa il pacchetto keyring per maggiore sicurezza.",
        "en": "No OS keychain available — tokens are stored in a 0600 file. Install the 'keyring' package for stronger protection.",
    },
    "settings_endpoints_note": {
        "uk": "Відповідність полів API xformat.net. Порожньо = типові значення. Змінюйте, коли контракт API буде остаточним — код чіпати не треба.",
        "it": "Mappatura dei campi dell'API xformat.net. Vuoto = valori predefiniti. Modificala quando il contratto API sarà definitivo.",
        "en": "Field mapping for the xformat.net API. Empty = defaults. Edit this once the API contract is final — no code changes needed.",
    },
    "settings_show_defaults": {
        "uk": "Показати типові значення",
        "it": "Mostra valori predefiniti",
        "en": "Show defaults",
    },
    "settings_bad_json": {
        "uk": "Некоректний JSON: {error}",
        "it": "JSON non valido: {error}",
        "en": "Invalid JSON: {error}",
    },
    "rewrite_provider_status": {
        "uk": "Переписування: {provider}",
        "it": "Riscrittura: {provider}",
        "en": "Rewrites: {provider}",
    },
    "target_label": {
        "uk": "Що аналізувати:",
        "it": "Cosa analizzare:",
        "en": "Target:",
    },

    # ------------------------------------------- non-keyboard characters
    "fix_unicode_button": {
        "uk": "Виправити символи",
        "it": "Correggi caratteri",
        "en": "Fix characters",
    },
    "fix_unicode_tooltip": {
        "uk": "Замінити символи, яких немає на клавіатурі, на клавіатурні. Працює локально, без запитів до LLM і без витрат.",
        "it": "Sostituisce i caratteri non digitabili con quelli da tastiera. Funziona in locale, senza chiamate LLM e senza costi.",
        "en": "Replace non-keyboard characters with keyboard ones. Runs locally — no LLM calls, no cost.",
    },
    "unicode_fixed_summary": {
        "uk": "Підготовлено виправлень: {n}. Перегляньте їх у списку; у режимі репозиторію їх запише кнопка «Замінити автоматично у файлах».",
        "it": "Correzioni preparate: {n}. Rivedile nell'elenco; in modalità repository verranno scritte da «Sostituisci automaticamente nei file».",
        "en": "Prepared {n} fix(es). Review them in the list; in repository mode they're written by 'Auto-replace in files'.",
    },
    "settings_tab_unicode": {
        "uk": "Символи",
        "it": "Caratteri",
        "en": "Characters",
    },
    "settings_unicode_enabled": {
        "uk": "Шукати символи, яких немає на клавіатурі",
        "it": "Cerca caratteri non digitabili da tastiera",
        "en": "Detect characters not typed on a keyboard",
    },
    "settings_unicode_note": {
        "uk": "Ця перевірка точна й безкоштовна, тож виконується разом із обраним детектором. Символи, звичні для мови (українські «лапки», італійські è à ò), не позначаються.",
        "it": "Questo controllo è esatto e gratuito, quindi viene eseguito insieme al rilevatore scelto. I caratteri normali per la lingua (virgolette ucraine, è à ò italiane) non vengono segnalati.",
        "en": "This check is exact and free, so it runs alongside the selected detector. Characters that are normal for the language (Ukrainian «quotes», Italian è à ò) are not flagged.",
    },
    "settings_cat_invisible": {
        "uk": "Невидимі символи (нульова ширина, мʼякий перенос, мітки напряму)",
        "it": "Caratteri invisibili (larghezza zero, sillabazione morbida, marcatori di direzione)",
        "en": "Invisible characters (zero-width, soft hyphen, direction marks)",
    },
    "settings_cat_space": {
        "uk": "Нетипові пробіли (нерозривний, вузький, ідеографічний)",
        "it": "Spazi atipici (unificatore, stretto, ideografico)",
        "en": "Unusual spaces (non-breaking, narrow, ideographic)",
    },
    "settings_cat_homoglyph": {
        "uk": "Літери з чужої абетки всередині слова (латинська «о» в кирилиці)",
        "it": "Lettere di un altro alfabeto dentro una parola (una «o» latina in cirillico)",
        "en": "Letters from another alphabet inside a word (Latin 'o' in Cyrillic)",
    },
    "settings_cat_styled": {
        "uk": "Стилізовані та повноширинні літери (𝐀𝐁𝐂, Ａ)",
        "it": "Lettere stilizzate e a larghezza intera (𝐀𝐁𝐂, Ａ)",
        "en": "Styled and fullwidth letters (𝐀𝐁𝐂, Ａ)",
    },
    "settings_cat_typography": {
        "uk": "Друкарська пунктуація (— – « » „ “ …)",
        "it": "Punteggiatura tipografica (— – « » „ “ …)",
        "en": "Typographic punctuation (— – « » „ “ …)",
    },
    "settings_cat_typography_note": {
        "uk": "Вимкніть, якщо хочете зберегти правильне тире й лапки в українських та італійських текстах.",
        "it": "Disattiva per mantenere il trattino lungo e le virgolette corrette nei testi ucraini e italiani.",
        "en": "Turn this off to keep proper em dashes and quotation marks in Ukrainian and Italian copy.",
    },
    # ---------------------------------------------------------- explanations
    # Rendered by explanations.py from TextSpan.details. Kept as templates so
    # the same finding reads in whatever language the UI is set to, including
    # after the language is changed post-scan.
    "why_style_title": {
        "uk": "Чому це схоже на текст від AI",
        "it": "Perché sembra testo generato dall'IA",
        "en": "Why this reads as AI-written",
    },
    "why_char_title": {
        "uk": "Символ, якого немає на клавіатурі",
        "it": "Carattere che nessuna tastiera produce",
        "en": "A character no keyboard produces",
    },
    "why_char_title_invisible": {
        "uk": "Невидимий керуючий символ",
        "it": "Carattere di controllo invisibile",
        "en": "Invisible control character",
    },
    "why_char_title_space": {
        "uk": "Незвичайний пробіл",
        "it": "Spazio atipico",
        "en": "Unusual space",
    },
    "why_char_title_homoglyph": {
        "uk": "Літера з чужої абетки в середині слова",
        "it": "Lettera di un altro alfabeto dentro la parola",
        "en": "Letter from another alphabet inside the word",
    },
    "why_char_title_styled": {
        "uk": "Стилізована літера",
        "it": "Lettera stilizzata",
        "en": "Styled letter",
    },
    "why_char_title_typography": {
        "uk": "Друкарська пунктуація",
        "it": "Punteggiatura tipografica",
        "en": "Typographic punctuation",
    },
    "why_char_invisible": {
        "uk": "Символ нічого не показує на екрані, але лишається в тексті: він переживає вичитку, ламає пошук і порівняння рядків. Клавіатура його не набирає, тож він потрапив сюди з машинної обробки.",
        "it": "Non mostra nulla sullo schermo ma resta nel testo: sopravvive alla revisione e rompe ricerca e confronto di stringhe. Nessuna tastiera lo digita, quindi arriva da un passaggio automatico.",
        "en": "It shows nothing on screen yet stays in the text: it survives proofreading and breaks search and string comparison. No keyboard types it, so it arrived from machine processing.",
    },
    "why_char_space": {
        "uk": "Виглядає як звичайний пробіл, але це інший символ. Через нього рядок не переноситься там, де мав би, а пошук по фразі не знаходить її.",
        "it": "Sembra uno spazio normale ma è un altro carattere. Impedisce l'a capo dove servirebbe e la ricerca della frase non la trova.",
        "en": "It looks like a plain space but is a different character. It stops the line breaking where it should, and a search for the phrase fails to find it.",
    },
    "why_char_homoglyph": {
        "uk": "Слово написане двома абетками одночасно: ця літера з іншої, хоч виглядає так само. На екрані непомітно, але слово перестає знаходитись пошуком і підкреслюється перевіркою орфографії.",
        "it": "La parola è scritta con due alfabeti insieme: questa lettera viene dall'altro pur sembrando identica. A schermo non si nota, ma la parola sparisce dalla ricerca e il correttore la segna.",
        "en": "The word is written in two alphabets at once: this letter comes from the other one although it looks identical. Invisible on screen, but the word stops matching search and the spellchecker flags it.",
    },
    "why_char_styled": {
        "uk": "Це не звичайна літера, а її стилізований варіант із математичного або повноширинного блоку. Такі символи вставляють, щоб обійти форматування, і вони не читаються програмами читання з екрана.",
        "it": "Non è una lettera normale ma una variante stilizzata dei blocchi matematici o a larghezza intera. Si usano per aggirare la formattazione e gli screen reader non le leggono.",
        "en": "Not a plain letter but a styled variant from the mathematical or fullwidth block. These get pasted in to fake formatting, and screen readers don't read them.",
    },
    "why_char_typography": {
        "uk": "Правильна друкарська пунктуація, якої немає на клавіатурі. У професійно зверстаному тексті це норма, тож оцінка тут середня; вимкнути перевірку можна в налаштуваннях.",
        "it": "Punteggiatura tipografica corretta ma assente dalla tastiera. In un testo impaginato bene è normale, quindi il punteggio resta medio; si può disattivare nelle impostazioni.",
        "en": "Correct typographic punctuation that isn't on the keyboard. In professionally typeset copy this is normal, so it scores medium; the check can be turned off in Settings.",
    },
    "why_char_codepoints": {
        "uk": "Знайдено: {codepoints}",
        "it": "Trovato: {codepoints}",
        "en": "Found: {codepoints}",
    },
    "why_char_caveat": {
        "uk": "Це точна знахідка, а не здогад: символ або є в тексті, або його немає.",
        "it": "È un riscontro esatto, non una stima: il carattere c'è o non c'è.",
        "en": "This is an exact finding, not a guess: the character is either there or it isn't.",
    },
    "why_cliche": {
        "uk": "Слова й звороти, які мовні моделі вживають значно частіше за людей: {phrases}",
        "it": "Parole ed espressioni che i modelli linguistici usano molto più delle persone: {phrases}",
        "en": "Words and phrases language models reach for far more often than people do: {phrases}",
    },
    "why_structural": {
        "uk": "Шаблонна конструкція «не просто X, а Y» та подібні: {patterns}",
        "it": "Costruzione stereotipata «non solo X, ma anche Y» e simili: {patterns}",
        "en": "A formulaic \"not just X, but Y\"-style construction: {patterns}",
    },
    "why_uniformity": {
        "uk": "Речення майже однакової довжини ({value}). Людина зазвичай чергує довгі й короткі.",
        "it": "Frasi di lunghezza quasi uguale ({value}). Chi scrive a mano alterna lunghe e brevi.",
        "en": "Sentences are nearly all the same length ({value}). People usually mix long and short ones.",
    },
    "why_repetition": {
        "uk": "Мало різних слів на обсяг тексту ({value}): формулювання повторюються.",
        "it": "Poche parole diverse per la lunghezza del testo ({value}): le formule si ripetono.",
        "en": "Few distinct words for this much text ({value}): the phrasing repeats itself.",
    },
    "why_dashes": {
        "uk": "Тире замість ком і дужок трапляється частіше за звичне ({value}).",
        "it": "Trattini lunghi al posto di virgole e parentesi più del normale ({value}).",
        "en": "Dashes stand in for commas and brackets more often than usual ({value}).",
    },
    "why_weak_combination": {
        "uk": "Жоден окремий сигнал не сильний, але разом вони дали оцінку вище порогу.",
        "it": "Nessun singolo segnale è forte, ma insieme superano la soglia.",
        "en": "No single signal is strong, but together they pushed the score over the threshold.",
    },
    "why_style_caveat": {
        "uk": "Це слабкі сигнали, а не доказ. Ретельно написаний людиною текст теж буває рівним і насиченим кліше.",
        "it": "Sono segnali deboli, non una prova. Anche un testo curato scritto da una persona può risultare uniforme e pieno di cliché.",
        "en": "These are weak signals, not proof. Carefully written human copy is often uniform and cliché-heavy too.",
    },
    "why_model_title": {
        "uk": "Оцінка моделі ({detector})",
        "it": "Giudizio del modello ({detector})",
        "en": "Model's judgement ({detector})",
    },
    # The hybrid run's third case: one passage that both engines flagged.
    # Given its own title because "the model said" and "the offline signals
    # said" are two kinds of evidence, and a reader deciding whether to
    # rewrite a sentence is entitled to know both were present.
    "why_agreement_title": {
        "uk": "Обидва двигуни позначили цей фрагмент",
        "it": "Entrambi i motori hanno segnalato questo passaggio",
        "en": "Both engines flagged this passage",
    },
    "why_agreement_caveat": {
        "uk": "Збіг двох двигунів не є доказом: локальні сигнали слабкі за "
              "побудовою, а оцінка моделі лишається думкою.",
        "it": "L'accordo tra i due motori non è una prova: i segnali locali "
              "sono deboli per costruzione e il giudizio del modello resta "
              "un'opinione.",
        "en": "Two engines agreeing is not proof: the offline signals are "
              "weak by construction, and the model's judgement stays an "
              "opinion.",
    },
    "why_agreement_model": {
        "uk": "Модель: {reason}",
        "it": "Modello: {reason}",
        "en": "The model: {reason}",
    },
    "why_model_caveat": {
        "uk": "Це думка моделі, а не водяний знак і не доказ походження тексту.",
        "it": "È l'opinione di un modello, non una filigrana né una prova di origine.",
        "en": "This is a model's opinion, not a watermark and not proof of origin.",
    },
    "suggest_exact": {
        "uk": "Заміна визначена правилом, без запиту до моделі.",
        "it": "Sostituzione decisa da una regola, senza chiamate al modello.",
        "en": "The replacement is fixed by a rule — no model call.",
    },
    "suggest_delete": {
        "uk": "Символ просто видаляється.",
        "it": "Il carattere viene semplicemente rimosso.",
        "en": "The character is simply removed.",
    },
    "suggest_none_rule": {
        "uk": "Для цього символу правила заміни немає.",
        "it": "Per questo carattere non esiste una regola di sostituzione.",
        "en": "There is no replacement rule for this character.",
    },
    "suggest_offline_wording": {
        "uk": "Варіант заміни складено офлайн зі словника простіших формулювань.",
        "it": "L'alternativa è costruita offline da un dizionario di formulazioni più semplici.",
        "en": "The alternative is built offline from a dictionary of plainer wording.",
    },
    "suggest_needs_model": {
        "uk": "Механічної заміни немає: тут потрібне переписування, а його згенерує лише модель.",
        "it": "Nessuna sostituzione meccanica: qui serve una riscrittura, che può produrla solo un modello.",
        "en": "No mechanical replacement: this needs rewriting, and only a model can produce it.",
    },
    "detail_why_header": {
        "uk": "Чому позначено",
        "it": "Perché è stato segnalato",
        "en": "Why it was flagged",
    },
    "detail_suggestion_header": {
        "uk": "Варіант заміни (офлайн)",
        "it": "Alternativa (offline)",
        "en": "Suggested replacement (offline)",
    },
    "detail_use_suggestion": {
        "uk": "Взяти цей варіант",
        "it": "Usa questa alternativa",
        "en": "Use this suggestion",
    },
    # ------------------------------------------------------ crawl diagnostics
    # Rendered by ui/widgets.diagnostics_message from PageDiagnostics.reasons.
    # These answer "the scan finished and found nothing — why?", which is the
    # one question an empty list cannot answer on its own.
    "crawl_reason_js_rendered": {
        "uk": "Сторінка збирається в браузері. Сервер віддав лише каркас застосунку, а текст дописує JavaScript уже після завантаження. Сканер не виконує JavaScript, тож бачити там нічого.",
        "it": "La pagina si costruisce nel browser. Il server ha restituito solo lo scheletro dell'applicazione e il testo viene inserito da JavaScript dopo il caricamento. Lo scanner non esegue JavaScript, quindi non c'è nulla da leggere.",
        "en": "The page is built in the browser. The server returned only an application shell, and the copy is written in by JavaScript after load. This scanner runs no JavaScript, so there is nothing there to read.",
    },
    "crawl_reason_framework": {
        "uk": "Ознаки фреймворку: {framework}.",
        "it": "Indizi del framework: {framework}.",
        "en": "Framework markers: {framework}.",
    },
    "crawl_reason_blocked": {
        "uk": "Сервер відмовив у відповіді (код {status}): захист від ботів, стіна згоди або потрібна авторизація.",
        "it": "Il server ha rifiutato (codice {status}): protezione anti-bot, muro di consenso o autenticazione richiesta.",
        "en": "The server refused (status {status}): a bot check, a consent wall, or authentication is required.",
    },
    "crawl_reason_not_html": {
        "uk": "Це не HTML-сторінка, а {content_type}. Сканер читає текст усередині розмітки.",
        "it": "Non è una pagina HTML ma {content_type}. Lo scanner legge il testo dentro il markup.",
        "en": "This is not an HTML page but {content_type}. The scanner reads text inside markup.",
    },
    "crawl_reason_too_short": {
        "uk": "Текст на сторінці є, але кожен фрагмент коротший за поріг у 20 символів: відкинуто {dropped}. Так виглядають сторінки, де є лише навігація й підписи кнопок.",
        "it": "Il testo c'è ma ogni frammento è sotto la soglia di 20 caratteri: {dropped} scartati. È l'aspetto tipico di una pagina fatta solo di navigazione ed etichette.",
        "en": "There is text, but every piece is under the 20-character threshold: {dropped} dropped. That is what a page of navigation and button labels looks like.",
    },
    "crawl_reason_no_text": {
        "uk": "У розмітці немає текстових вузлів, придатних для читання.",
        "it": "Il markup non contiene nodi di testo leggibili.",
        "en": "The markup holds no readable text nodes.",
    },
    "crawl_reason_redirected": {
        "uk": "Запит перенаправлено на {final_url}.",
        "it": "La richiesta è stata reindirizzata a {final_url}.",
        "en": "The request was redirected to {final_url}.",
    },
    "crawl_reason_already_seen": {
        "uk": "Ця сторінка вже прочитана під іншою адресою, тож удруге її не аналізовано.",
        "it": "Questa pagina è già stata letta a un altro indirizzo, quindi non è stata analizzata di nuovo.",
        "en": "This page was already read at another address, so it was not analysed twice.",
    },
    "crawl_reason_error": {
        "uk": "Запит не вдався: {error}",
        "it": "Richiesta fallita: {error}",
        "en": "The request failed: {error}",
    },
    "crawl_measurements": {
        "uk": "Отримано {bytes} байт HTML, з них {ratio} видимого тексту; придатних елементів {candidates}, узято блоків {kept}.",
        "it": "Ricevuti {bytes} byte di HTML, di cui {ratio} di testo visibile; elementi utili {candidates}, blocchi presi {kept}.",
        "en": "Received {bytes} bytes of HTML, {ratio} of it visible text; {candidates} usable elements, {kept} blocks taken.",
    },
    "crawl_advice_js": {
        "uk": "Що можна зробити: відскануйте репозиторій із вихідним кодом цієї сторінки (режим «Репозиторій»), або збережіть сторінку з браузера вже відрендереною і відскануйте цей файл.",
        "it": "Cosa fare: scansiona il repository con il codice sorgente della pagina (modalità «Repository»), oppure salva la pagina già renderizzata dal browser e scansiona quel file.",
        "en": "What to do: scan the repository this page is built from (Repository mode), or save the rendered page from the browser and scan that file.",
    },
    "empty_no_scan_title": {
        "uk": "Ще нічого не проаналізовано",
        "it": "Non è stato ancora analizzato nulla",
        "en": "Nothing analysed yet",
    },
    "empty_no_scan_body": {
        "uk": "Вкажіть адресу сторінки або теку з кодом і натисніть «Аналізувати». Офлайн-перевірка нічого не коштує і не надсилає текст нікуди.",
        "it": "Indica l'indirizzo di una pagina o una cartella di codice e premi «Analizza». Il controllo offline è gratuito e non invia il testo da nessuna parte.",
        "en": "Point it at a page address or a code folder and press Analyze. The offline check costs nothing and sends the text nowhere.",
    },
    "empty_clean_title": {
        "uk": "Нічого не позначено",
        "it": "Nessuna segnalazione",
        "en": "Nothing flagged",
    },
    "empty_clean_body": {
        "uk": "Перевірено {blocks} фрагментів тексту на {pages} сторінках. Жоден не набрав достатньо сигналів. Це не доказ, що текст писала людина, — лише те, що ця перевірка нічого не знайшла.",
        "it": "Controllati {blocks} frammenti su {pages} pagine. Nessuno ha raccolto segnali sufficienti. Non prova che il testo sia umano: solo che questo controllo non ha trovato nulla.",
        "en": "Checked {blocks} pieces of text across {pages} pages. None gathered enough signal. That is not proof the text is human-written — only that this check found nothing.",
    },
    "empty_no_text_title": {
        "uk": "Сканер не отримав тексту",
        "it": "Lo scanner non ha ricevuto testo",
        "en": "The scanner received no text",
    },
    "empty_no_text_body": {
        "uk": "Сторінку завантажено, але читати не було чого. Причина:",
        "it": "La pagina è stata scaricata ma non c'era nulla da leggere. Motivo:",
        "en": "The page was fetched, but there was nothing to read. Why:",
    },
    "empty_repo_no_text_title": {
        "uk": "У цій теці не знайдено тексту в розмітці",
        "it": "Nessun testo dentro il markup in questa cartella",
        "en": "No text inside markup found in this folder",
    },
    "empty_repo_no_text_body": {
        "uk": "Переглянуто файлів: {files}. Сканер читає текст усередині тегів у .html, .htm, .xml, .jsx, .tsx, .vue і .svelte. Перевірте шлях і список винятків.",
        "it": "File esaminati: {files}. Lo scanner legge il testo dentro i tag in .html, .htm, .xml, .jsx, .tsx, .vue e .svelte. Controlla il percorso e le esclusioni.",
        "en": "Files examined: {files}. The scanner reads text inside tags in .html, .htm, .xml, .jsx, .tsx, .vue and .svelte. Check the path and the exclusion list.",
    },
    "pages_with_problems": {
        "uk": "Сторінок із проблемами: {n}",
        "it": "Pagine con problemi: {n}",
        "en": "Pages with problems: {n}",
    },
    "theme_label": {
        "uk": "Тема:",
        "it": "Tema:",
        "en": "Theme:",
    },
    "theme_auto": {
        "uk": "Як у системі",
        "it": "Come il sistema",
        "en": "Follow system",
    },
    "theme_light": {
        "uk": "Світла",
        "it": "Chiaro",
        "en": "Light",
    },
    "theme_dark": {
        "uk": "Темна",
        "it": "Scuro",
        "en": "Dark",
    },
    # ------------------------------------------------------- repository scope
    "scope_label": {
        "uk": "Читати:",
        "it": "Leggere:",
        "en": "Read:",
    },
    "scope_label_full": {
        "uk": "Який текст брати з репозиторія",
        "it": "Quale testo prendere dal repository",
        "en": "Which text to take from the repository",
    },
    "scope_content": {
        "uk": "Контент для читача",
        "it": "Contenuti per il lettore",
        "en": "Reader-facing content",
    },
    "scope_content_full": {
        "uk": "Текст між тегами плюс рядки, які потрапляють у контент з коду: атрибути placeholder, alt і title, присвоєння textContent, виклики перекладу t(\"...\") і значення ключів на кшталт title: чи description:. Коментарі не читаються.",
        "it": "Testo tra i tag più le stringhe che finiscono nei contenuti dal codice: attributi placeholder, alt e title, assegnazioni a textContent, chiamate di traduzione t(\"...\") e valori di chiavi come title: o description:. I commenti non vengono letti.",
        "en": "Text between tags plus the strings that reach the content from code: placeholder, alt and title attributes, textContent assignments, t(\"...\") translation calls, and values of keys like title: or description:. Comments are not read.",
    },
    "scope_technical": {
        "uk": "Технічний текст",
        "it": "Testo tecnico",
        "en": "Technical text",
    },
    "scope_technical_full": {
        "uk": "Коментарі та docstring-и у коді, перевірені на ті самі AI-патерни. До читача цей текст не потрапляє, тож режим вмикається окремо, і автозаміна тут переписує коментар, а не копірайт.",
        "it": "Commenti e docstring nel codice, controllati sugli stessi pattern IA. Questo testo non arriva al lettore, quindi la modalità si attiva a parte e la sostituzione automatica qui riscrive un commento, non un testo di marketing.",
        "en": "Comments and docstrings in the code, checked for the same AI patterns. None of it reaches a reader, so this mode is turned on deliberately, and auto-replace here rewrites a comment rather than copy.",
    },
    "scope_both": {
        "uk": "І контент, і коментарі",
        "it": "Contenuti e commenti",
        "en": "Content and comments",
    },
    "scope_both_full": {
        "uk": "Обидва набори одночасно. Кожна знахідка підписана типом, щоб було видно, що саме буде переписано.",
        "it": "Entrambi insieme. Ogni riscontro è etichettato per tipo, così si vede cosa verrà riscritto.",
        "en": "Both sets at once. Every finding is labelled with its kind, so it stays clear what would be rewritten.",
    },
    "kind_markup": {
        "uk": "розмітка",
        "it": "markup",
        "en": "markup",
    },
    "kind_injected": {
        "uk": "рядок у коді",
        "it": "stringa nel codice",
        "en": "string in code",
    },
    "kind_technical": {
        "uk": "коментар",
        "it": "commento",
        "en": "comment",
    },
    "confirm_auto_replace_technical": {
        "uk": "Серед них коментарів у коді: {n}. Їх буде переписано у вихідних файлах.",
        "it": "Tra questi ci sono {n} commenti nel codice. Verranno riscritti nei file sorgente.",
        "en": "{n} of these are code comments. They will be rewritten in the source files.",
    },

    # ------------------------------------------------- accessibility findings
    # One entry per rule, in three pieces: what was found, why it matters to
    # the person using the page, and how to fix it. The "why" deliberately
    # describes the consequence rather than quoting a success criterion
    # number - "1.1.1" tells a developer nothing about why to care.
    "a11y_image_alt_title": {
        "uk": "Зображення без атрибута alt",
        "it": "Immagine senza attributo alt",
        "en": "Image with no alt attribute",
    },
    "a11y_image_alt_found": {
        "uk": "Знайдено: <img src=\"{src}\"> без alt.",
        "it": "Trovato: <img src=\"{src}\"> senza alt.",
        "en": "Found: <img src=\"{src}\"> with no alt.",
    },
    "a11y_image_alt_why": {
        "uk": "Програма читання з екрана оголосить лише слово «зображення» і піде далі. Якщо картинка щось значить, читач втратить цей зміст повністю; якщо вона декоративна, він почує зайвий шум. За розміткою неможливо визначити, що з двох, тому виправлення мусить бути свідомим.",
        "it": "Uno screen reader annuncerà solo «immagine» e proseguirà. Se l'immagine ha un significato, chi ascolta lo perde del tutto; se è decorativa, sente rumore inutile. Dal markup non si capisce quale dei due casi sia, quindi la correzione va scelta consapevolmente.",
        "en": "A screen reader announces just \"image\" and moves on. If the picture carries meaning, the listener loses it entirely; if it is decorative, they hear noise. The markup cannot say which, so the fix has to be a deliberate choice.",
    },
    "a11y_image_alt_fix": {
        "uk": "Якщо зображення несе зміст - опишіть його: alt=\"голова команди на сцені\". Якщо воно декоративне - поставте порожній alt=\"\", і воно буде пропущене. Порожній alt і відсутній alt - це різні речі.",
        "it": "Se l'immagine ha un contenuto, descrivilo: alt=\"la responsabile del team sul palco\". Se è decorativa, metti alt=\"\" vuoto e verrà saltata. alt vuoto e alt assente non sono la stessa cosa.",
        "en": "If the image carries content, describe it: alt=\"the team lead on stage\". If it is decorative, give it an empty alt=\"\" and it will be skipped. An empty alt and a missing alt are not the same thing.",
    },
    "a11y_image_alt_filename_title": {
        "uk": "Замість опису в alt стоїть імʼя файлу",
        "it": "Nell'alt c'è il nome del file invece della descrizione",
        "en": "The alt text is a file name, not a description",
    },
    "a11y_image_alt_filename_found": {
        "uk": "Знайдено: alt=\"{alt}\".",
        "it": "Trovato: alt=\"{alt}\".",
        "en": "Found: alt=\"{alt}\".",
    },
    "a11y_image_alt_filename_why": {
        "uk": "Атрибут є, тож автоматичні перевірки мовчать, але читач чує «логотип два ікс крапка пеенге». Це гірше за відсутній alt: помилка захована, а користі нуль.",
        "it": "L'attributo c'è, quindi i controlli automatici tacciono, ma chi ascolta sente «logo due per ics punto png». È peggio di un alt assente: l'errore è nascosto e l'utilità è zero.",
        "en": "The attribute is there, so automated checks stay quiet, but the listener hears \"logo dash two x dot p n g\". That is worse than a missing alt: the error is hidden and the value is nil.",
    },
    "a11y_image_alt_filename_fix": {
        "uk": "Напишіть, що на зображенні або яку функцію воно виконує, а не як називається файл. Для логотипа це назва компанії: alt=\"xFormat\".",
        "it": "Scrivi cosa mostra l'immagine o che funzione ha, non come si chiama il file. Per un logo è il nome dell'azienda: alt=\"xFormat\".",
        "en": "Write what the image shows or what it does, not what the file is called. For a logo that is the company name: alt=\"xFormat\".",
    },
    "a11y_control_name_title": {
        "uk": "Елемент керування без доступного імені",
        "it": "Controllo senza nome accessibile",
        "en": "Control with no accessible name",
    },
    "a11y_control_name_found": {
        "uk": "Знайдено: <{element}> без тексту, aria-label, title і без повʼязаного <label>.",
        "it": "Trovato: <{element}> senza testo, aria-label, title né <label> collegata.",
        "en": "Found: <{element}> with no text, aria-label, title, or associated <label>.",
    },
    "a11y_control_name_why": {
        "uk": "Кнопку чи поле буде оголошено просто як «кнопка» або «редагування тексту», без жодної підказки, що воно робить. Кнопку лише з іконкою людина, яка не бачить екран, натиснути свідомо не може - це блокує задачу, а не ускладнює її.",
        "it": "Il pulsante o il campo verrà annunciato solo come «pulsante» o «casella di testo», senza alcun indizio su cosa faccia. Un pulsante con la sola icona non è utilizzabile consapevolmente da chi non vede lo schermo: blocca l'operazione, non la complica.",
        "en": "The button or field is announced as just \"button\" or \"edit text\", with no hint of what it does. An icon-only button cannot be used deliberately by someone who does not see the screen — that blocks the task rather than slowing it down.",
    },
    "a11y_control_name_fix": {
        "uk": "Для кнопки з іконкою додайте aria-label=\"Закрити\". Для поля - <label for=\"…\">, повʼязану через id. Для посилання - видимий текст усередині. Видимий текст кращий за aria-label, бо ним користуються і зрячі.",
        "it": "Per un pulsante con icona aggiungi aria-label=\"Chiudi\". Per un campo, una <label for=\"…\"> collegata tramite id. Per un link, testo visibile all'interno. Il testo visibile è preferibile ad aria-label, perché serve anche a chi vede.",
        "en": "For an icon button add aria-label=\"Close\". For a field, a <label for=\"…\"> tied to its id. For a link, visible text inside it. Visible text beats aria-label, because sighted users get it too.",
    },
    "a11y_link_text_vague_title": {
        "uk": "Текст посилання не описує ціль",
        "it": "Il testo del link non descrive la destinazione",
        "en": "Link text does not describe its destination",
    },
    "a11y_link_text_vague_found": {
        "uk": "Знайдено: «{text}» -> {href}.",
        "it": "Trovato: «{text}» -> {href}.",
        "en": "Found: \"{text}\" -> {href}.",
    },
    "a11y_link_text_vague_why": {
        "uk": "Програми читання з екрана дозволяють витягнути список усіх посилань сторінки окремо від тексту. У такому списку пʼятнадцять рядків «детальніше» - це пʼятнадцять однакових варіантів, з яких неможливо вибрати.",
        "it": "Gli screen reader permettono di estrarre l'elenco di tutti i link della pagina, fuori dal testo. In quell'elenco quindici righe «leggi di più» sono quindici scelte identiche fra cui è impossibile scegliere.",
        "en": "Screen readers can pull up a list of every link on the page, out of context. In that list, fifteen rows reading \"read more\" are fifteen identical choices with nothing to choose between.",
    },
    "a11y_link_text_vague_fix": {
        "uk": "Напишіть у самому посиланні, куди воно веде: «Тарифи і ціни» замість «детальніше». Якщо дизайн вимагає короткого напису, лишіть його видимим, а повний опис дайте через aria-label.",
        "it": "Scrivi nel link stesso dove porta: «Piani e prezzi» invece di «leggi di più». Se il design impone una scritta breve, lasciala visibile e metti la descrizione completa in aria-label.",
        "en": "Say in the link itself where it goes: \"Plans and pricing\" instead of \"read more\". If the design needs the short label, keep it visible and put the full description in aria-label.",
    },
    "a11y_html_lang_title": {
        "uk": "Мова документа не вказана",
        "it": "La lingua del documento non è dichiarata",
        "en": "The document language is not declared",
    },
    "a11y_html_lang_found": {
        "uk": "У теґа <html> немає атрибута lang.",
        "it": "Il tag <html> non ha l'attributo lang.",
        "en": "The <html> tag has no lang attribute.",
    },
    "a11y_html_lang_why": {
        "uk": "Синтезатор мовлення обирає вимову за мовою документа. Без неї український текст читатиметься правилами тієї мови, яка стоїть у системі користувача, і стане нерозбірливим. Це також ламає перенос слів і автоматичний переклад.",
        "it": "Il sintetizzatore vocale sceglie la pronuncia in base alla lingua del documento. Senza, un testo italiano viene letto con le regole della lingua di sistema dell'utente e diventa incomprensibile. Rompe anche sillabazione e traduzione automatica.",
        "en": "A speech synthesiser picks its pronunciation from the document language. Without it, the text is read using the rules of whatever language the user's system is set to, and becomes unintelligible. It also breaks hyphenation and machine translation.",
    },
    "a11y_html_lang_fix": {
        "uk": "Додайте код мови до кореневого теґа: <html lang=\"uk\">. Якщо на сторінці є фрагмент іншою мовою, позначте і його: <span lang=\"en\">.",
        "it": "Aggiungi il codice lingua al tag radice: <html lang=\"it\">. Se nella pagina c'è un brano in un'altra lingua, marca anche quello: <span lang=\"en\">.",
        "en": "Add the language code to the root tag: <html lang=\"en\">. If part of the page is in another language, mark that too: <span lang=\"uk\">.",
    },
    "a11y_document_title_title": {
        "uk": "Сторінка без заголовка <title>",
        "it": "Pagina senza <title>",
        "en": "Page has no <title>",
    },
    "a11y_document_title_found": {
        "uk": "Теґ <title> відсутній або порожній.",
        "it": "Il tag <title> manca o è vuoto.",
        "en": "The <title> tag is missing or empty.",
    },
    "a11y_document_title_why": {
        "uk": "Заголовок - перше, що оголошується при відкритті сторінки, і єдине, що відрізняє вкладки одна від одної. Без нього людина з десятьма відкритими вкладками не має способу зрозуміти, де вона.",
        "it": "Il titolo è la prima cosa annunciata all'apertura della pagina e l'unica che distingue una scheda dall'altra. Senza, chi ha dieci schede aperte non ha modo di capire dove si trova.",
        "en": "The title is the first thing announced when the page opens, and the only thing that tells one tab from another. Without it, someone with ten tabs open has no way to tell where they are.",
    },
    "a11y_document_title_fix": {
        "uk": "Додайте <title>, що починається з унікальної частини: «Тарифи - xFormat», а не «xFormat - Тарифи». Перші слова чути раніше за решту.",
        "it": "Aggiungi un <title> che inizi con la parte unica: «Prezzi - xFormat», non «xFormat - Prezzi». Le prime parole si sentono prima delle altre.",
        "en": "Add a <title> that starts with the unique part: \"Pricing - xFormat\", not \"xFormat - Pricing\". The first words are heard first.",
    },
    "a11y_heading_order_title": {
        "uk": "Пропущений рівень заголовка",
        "it": "Livello di intestazione saltato",
        "en": "A heading level was skipped",
    },
    "a11y_heading_order_found": {
        "uk": "Знайдено: після h{from} одразу h{to} - «{text}».",
        "it": "Trovato: dopo h{from} arriva subito h{to} - «{text}».",
        "en": "Found: h{from} is followed directly by h{to} - \"{text}\".",
    },
    "a11y_heading_order_why": {
        "uk": "Заголовки - це зміст сторінки, яким незрячі користувачі перегортають її, як зрячі очима. Стрибок з h2 на h4 читається як «тут пропущено цілий розділ», і людина шукає те, чого немає.",
        "it": "Le intestazioni sono l'indice con cui chi non vede scorre la pagina, come gli altri fanno con gli occhi. Un salto da h2 a h4 si legge come «qui manca una sezione», e la persona cerca qualcosa che non esiste.",
        "en": "Headings are the outline blind users skim with, the way sighted users skim with their eyes. A jump from h2 to h4 reads as \"a whole section is missing here\", and the person goes looking for something that is not there.",
    },
    "a11y_heading_order_fix": {
        "uk": "Знижуйте рівень по одному. Якщо рівень обрано заради розміру шрифту - лишіть правильний рівень і задайте розмір стилями.",
        "it": "Scendi di un livello per volta. Se il livello è stato scelto per la dimensione del carattere, tieni il livello corretto e imposta la dimensione con i CSS.",
        "en": "Step down one level at a time. If the level was picked for its font size, keep the correct level and set the size in CSS.",
    },
    "a11y_page_has_h1_title": {
        "uk": "На сторінці немає рівно одного h1",
        "it": "La pagina non ha esattamente un h1",
        "en": "The page does not have exactly one h1",
    },
    "a11y_page_has_h1_found": {
        "uk": "Знайдено заголовків h1: {count}.",
        "it": "Intestazioni h1 trovate: {count}.",
        "en": "h1 headings found: {count}.",
    },
    "a11y_page_has_h1_why": {
        "uk": "h1 називає сторінку цілком. Якщо його немає, у переліку заголовків немає верхівки і незрозуміло, про що сторінка; якщо їх кілька, структура читається як кілька документів, склеєних разом.",
        "it": "L'h1 dà il nome all'intera pagina. Se manca, l'elenco delle intestazioni non ha un vertice e non si capisce di cosa tratti la pagina; se ce ne sono più d'uno, la struttura si legge come più documenti incollati insieme.",
        "en": "The h1 names the whole page. With none, the heading outline has no top and the page's subject is unclear; with several, the structure reads as several documents glued together.",
    },
    "a11y_page_has_h1_fix": {
        "uk": "Лишіть один h1 - головний заголовок сторінки, а решту опустіть до h2.",
        "it": "Tieni un solo h1, l'intestazione principale della pagina, e porta gli altri a h2.",
        "en": "Keep one h1 — the page's main heading — and move the others down to h2.",
    },
    "a11y_tabindex_positive_title": {
        "uk": "Додатний tabindex ламає порядок фокуса",
        "it": "Un tabindex positivo rompe l'ordine di focus",
        "en": "A positive tabindex breaks the focus order",
    },
    "a11y_tabindex_positive_found": {
        "uk": "Знайдено: <{element} tabindex=\"{value}\">.",
        "it": "Trovato: <{element} tabindex=\"{value}\">.",
        "en": "Found: <{element} tabindex=\"{value}\">.",
    },
    "a11y_tabindex_positive_why": {
        "uk": "Будь-який додатний tabindex висмикує елемент з природного порядку і ставить його попереду всього, що має tabindex 0 - зокрема попереду посилання «перейти до вмісту». Один такий атрибут перебудовує клавіатурний шлях усієї сторінки.",
        "it": "Qualsiasi tabindex positivo estrae l'elemento dall'ordine naturale e lo mette davanti a tutto ciò che ha tabindex 0, incluso il link «vai al contenuto». Un solo attributo così riorganizza il percorso da tastiera dell'intera pagina.",
        "en": "Any positive tabindex pulls the element out of document order and puts it ahead of everything with tabindex 0 — including the skip link. One such attribute re-orders the keyboard path of the whole page.",
    },
    "a11y_tabindex_positive_fix": {
        "uk": "Поставте tabindex=\"0\" і впорядкуйте елементи в самій розмітці: порядок фокуса має збігатися з порядком читання. tabindex=\"-1\" лишіть для елементів, на які фокус ставить лише скрипт.",
        "it": "Metti tabindex=\"0\" e ordina gli elementi nel markup: l'ordine di focus deve coincidere con quello di lettura. Lascia tabindex=\"-1\" solo per elementi messi a fuoco via script.",
        "en": "Set tabindex=\"0\" and order the elements in the markup itself: focus order should match reading order. Keep tabindex=\"-1\" for elements only ever focused by script.",
    },
    "a11y_duplicate_id_title": {
        "uk": "Ідентифікатор повторюється",
        "it": "Identificatore duplicato",
        "en": "Duplicate identifier",
    },
    "a11y_duplicate_id_found": {
        "uk": "Знайдено: id=\"{id}\" зустрічається більше одного разу.",
        "it": "Trovato: id=\"{id}\" compare più di una volta.",
        "en": "Found: id=\"{id}\" occurs more than once.",
    },
    "a11y_duplicate_id_why": {
        "uk": "Атрибути for, aria-labelledby і aria-describedby знаходять лише перший елемент із таким id. Через дублікат усі підписи мовчки прикріплюються до одного елемента, а другий лишається без імені - при цьому розмітка виглядає правильною.",
        "it": "Gli attributi for, aria-labelledby e aria-describedby trovano solo il primo elemento con quell'id. Con un duplicato tutte le etichette si attaccano silenziosamente a un solo elemento e l'altro resta senza nome, mentre il markup sembra corretto.",
        "en": "The for, aria-labelledby and aria-describedby attributes resolve to the first element with that id only. A duplicate silently attaches every reference to one element and leaves the other unnamed — while the markup looks correct.",
    },
    "a11y_duplicate_id_fix": {
        "uk": "Зробіть ідентифікатори унікальними в межах документа. Для повторюваних компонентів додавайте суфікс від даних, а не порядковий номер, який може збігтися.",
        "it": "Rendi gli identificatori unici nel documento. Per i componenti ripetuti aggiungi un suffisso derivato dai dati, non un numero progressivo che può ripetersi.",
        "en": "Make identifiers unique within the document. For repeated components, derive the suffix from the data rather than from a counter that can collide.",
    },
    "a11y_aria_reference_broken_title": {
        "uk": "Посилання aria вказує в нікуди",
        "it": "Un riferimento aria punta nel vuoto",
        "en": "An aria reference points at nothing",
    },
    "a11y_aria_reference_broken_found": {
        "uk": "Знайдено: {attribute} посилається на id, яких немає: {missing}.",
        "it": "Trovato: {attribute} rimanda a id inesistenti: {missing}.",
        "en": "Found: {attribute} references ids that do not exist: {missing}.",
    },
    "a11y_aria_reference_broken_why": {
        "uk": "Зламане aria-labelledby гірше за його відсутність: браузер не підставляє запасний варіант, тож елемент лишається зовсім без імені, а розмітка при цьому виглядає так, ніби доступність продумана.",
        "it": "Un aria-labelledby rotto è peggio della sua assenza: il browser non applica alcun ripiego, quindi l'elemento resta del tutto senza nome mentre il markup sembra curato sul fronte accessibilità.",
        "en": "A broken aria-labelledby is worse than none: the browser applies no fallback, so the element ends up with no name at all — while the markup looks like accessibility was considered.",
    },
    "a11y_aria_reference_broken_fix": {
        "uk": "Звірте id: часта причина - елемент рендериться за умовою, а посилання лишилось. Якщо цілі немає, замініть на aria-label з текстом.",
        "it": "Verifica gli id: causa frequente è un elemento reso condizionalmente mentre il riferimento è rimasto. Se la destinazione non esiste, sostituisci con aria-label testuale.",
        "en": "Check the ids: the usual cause is an element rendered conditionally while the reference stayed. If the target does not exist, replace it with a plain aria-label.",
    },
    "a11y_button_type_title": {
        "uk": "Кнопка у формі без type",
        "it": "Pulsante nel form senza type",
        "en": "Button in a form with no type",
    },
    "a11y_button_type_found": {
        "uk": "Знайдено: <button> усередині <form> без атрибута type.",
        "it": "Trovato: <button> dentro <form> senza attributo type.",
        "en": "Found: <button> inside a <form> with no type attribute.",
    },
    "a11y_button_type_why": {
        "uk": "Усередині форми кнопка за замовчуванням має type=\"submit\". Тому кнопка «очистити» чи «показати пароль» відправляє форму при натисканні Enter - найчастіше саме з клавіатури, тобто саме в тих, хто мишею не користується.",
        "it": "Dentro un form il pulsante ha per default type=\"submit\". Così un pulsante «pulisci» o «mostra password» invia il form premendo Invio, cioè proprio da tastiera, cioè proprio a chi non usa il mouse.",
        "en": "Inside a form a button defaults to type=\"submit\". So a \"clear\" or \"show password\" button submits the form on Enter — which is the keyboard path, which is exactly the people who do not use a mouse.",
    },
    "a11y_button_type_fix": {
        "uk": "Вкажіть type явно: type=\"button\" для дій, що не відправляють форму, type=\"submit\" для тієї єдиної, що відправляє.",
        "it": "Indica type esplicitamente: type=\"button\" per le azioni che non inviano, type=\"submit\" per quell'unico che invia.",
        "en": "Set type explicitly: type=\"button\" for actions that do not submit, type=\"submit\" for the one that does.",
    },
    "a11y_media_captions_title": {
        "uk": "Відео чи аудіо без субтитрів",
        "it": "Video o audio senza sottotitoli",
        "en": "Video or audio with no captions",
    },
    "a11y_media_captions_found": {
        "uk": "Знайдено: <{element}> з доріжками субтитрів: {tracks}.",
        "it": "Trovato: <{element}> con tracce di sottotitoli: {tracks}.",
        "en": "Found: <{element}> with caption tracks: {tracks}.",
    },
    "a11y_media_captions_why": {
        "uk": "Без субтитрів увесь зміст запису недоступний людям, які не чують, і будь-кому, хто дивиться без звуку. Якщо це єдине місце, де сказано щось важливе, воно просто відсутнє для частини аудиторії.",
        "it": "Senza sottotitoli tutto il contenuto della registrazione è inaccessibile a chi non sente e a chiunque guardi senza audio. Se è l'unico posto in cui viene detta una cosa importante, per una parte del pubblico semplicemente non esiste.",
        "en": "Without captions the entire content of the recording is unavailable to people who do not hear, and to anyone watching with the sound off. If it is the only place something important is said, it simply is not there for part of the audience.",
    },
    "a11y_media_captions_fix": {
        "uk": "Додайте <track kind=\"captions\" srclang=\"uk\" src=\"…\" default>. Для аудіо дайте текстову розшифровку поруч із плеєром - вона ще й індексується пошуком.",
        "it": "Aggiungi <track kind=\"captions\" srclang=\"it\" src=\"…\" default>. Per l'audio metti una trascrizione accanto al player: viene anche indicizzata dai motori di ricerca.",
        "en": "Add <track kind=\"captions\" srclang=\"en\" src=\"…\" default>. For audio, put a transcript next to the player — it gets indexed by search engines too.",
    },
    "a11y_media_autoplay_title": {
        "uk": "Автовідтворення без керування",
        "it": "Riproduzione automatica senza controlli",
        "en": "Autoplay with no controls",
    },
    "a11y_media_autoplay_found": {
        "uk": "Знайдено: <{element} autoplay> без controls і без muted.",
        "it": "Trovato: <{element} autoplay> senza controls e senza muted.",
        "en": "Found: <{element} autoplay> with no controls and no muted.",
    },
    "a11y_media_autoplay_why": {
        "uk": "Звук, якого людина не просила і який неможливо зупинити, перекриває мовлення програми читання з екрана. Користувач при цьому не чує навіть того, як знайти кнопку зупинки - бо вона теж озвучується.",
        "it": "Un suono non richiesto e non arrestabile copre la voce dello screen reader. L'utente non sente nemmeno come trovare il pulsante di stop, perché anche quello viene pronunciato a voce.",
        "en": "Sound the visitor did not ask for and cannot stop covers the screen reader's own speech. They cannot even hear how to find the stop button, because that is announced by speech too.",
    },
    "a11y_media_autoplay_fix": {
        "uk": "Приберіть autoplay, або додайте controls, або запускайте без звуку (muted) і дайте кнопку ввімкнення звуку.",
        "it": "Togli autoplay, oppure aggiungi controls, oppure avvia senza audio (muted) offrendo un pulsante per attivarlo.",
        "en": "Drop autoplay, or add controls, or start muted and offer a button to turn the sound on.",
    },
    "a11y_table_headers_title": {
        "uk": "Таблиця даних без заголовків стовпців",
        "it": "Tabella di dati senza intestazioni",
        "en": "Data table with no header cells",
    },
    "a11y_table_headers_found": {
        "uk": "Знайдено: <table> з {rows} рядками і жодного <th>.",
        "it": "Trovato: <table> con {rows} righe e nessun <th>.",
        "en": "Found: a <table> with {rows} rows and no <th>.",
    },
    "a11y_table_headers_why": {
        "uk": "Зряча людина зіставляє клітинку зі стовпцем поглядом угору. Незряча читає таблицю по клітинці, і без <th> кожне значення оголошується голим числом без назви стовпця: «10» замість «Ціна: 10».",
        "it": "Chi vede associa la cella alla colonna con un'occhiata verso l'alto. Chi non vede legge cella per cella e, senza <th>, ogni valore viene annunciato come numero nudo senza il nome della colonna: «10» invece di «Prezzo: 10».",
        "en": "A sighted reader matches a cell to its column with a glance upwards. A blind reader goes cell by cell, and without <th> every value is announced as a bare number with no column name: \"10\" instead of \"Price: 10\".",
    },
    "a11y_table_headers_fix": {
        "uk": "Замініть клітинки шапки на <th scope=\"col\">, а заголовки рядків - на <th scope=\"row\">. Додайте <caption> з призначенням таблиці. Якщо таблиця використана для верстки - краще перейти на CSS-сітку, а тимчасово поставити role=\"presentation\".",
        "it": "Sostituisci le celle di intestazione con <th scope=\"col\"> e quelle di riga con <th scope=\"row\">. Aggiungi una <caption> che dica a cosa serve la tabella. Se la tabella serve per l'impaginazione, passa a una griglia CSS e nel frattempo metti role=\"presentation\".",
        "en": "Turn header cells into <th scope=\"col\"> and row headers into <th scope=\"row\">. Add a <caption> saying what the table is for. If the table is doing layout, move to a CSS grid and mark it role=\"presentation\" meanwhile.",
    },
    "a11y_viewport_zoom_title": {
        "uk": "Масштабування сторінки заблоковане",
        "it": "Lo zoom della pagina è bloccato",
        "en": "Page zoom is blocked",
    },
    "a11y_viewport_zoom_found": {
        "uk": "Знайдено: <meta name=\"viewport\" content=\"{content}\">.",
        "it": "Trovato: <meta name=\"viewport\" content=\"{content}\">.",
        "en": "Found: <meta name=\"viewport\" content=\"{content}\">.",
    },
    "a11y_viewport_zoom_why": {
        "uk": "Це один рядок, який робить сайт непридатним для всіх, хто збільшує текст - а це не лише люди зі слабким зором, а й будь-хто на сонці або в дорозі. Обхідного шляху в користувача немає.",
        "it": "È una riga sola che rende il sito inutilizzabile per chiunque ingrandisca il testo, non solo chi ha problemi di vista ma anche chi legge al sole o in movimento. L'utente non ha alcuna via d'uscita.",
        "en": "It is a single line that makes the site unusable for anyone who enlarges text — not only people with low vision but anyone in bright sun or on the move. The user has no way around it.",
    },
    "a11y_viewport_zoom_fix": {
        "uk": "Приберіть user-scalable=no і maximum-scale. Робочий варіант: content=\"width=device-width, initial-scale=1\".",
        "it": "Togli user-scalable=no e maximum-scale. Versione corretta: content=\"width=device-width, initial-scale=1\".",
        "en": "Remove user-scalable=no and maximum-scale. The working version is content=\"width=device-width, initial-scale=1\".",
    },
    "a11y_contrast_inline_title": {
        "uk": "Замалий контраст тексту",
        "it": "Contrasto del testo insufficiente",
        "en": "Text contrast is too low",
    },
    "a11y_contrast_inline_found": {
        "uk": "Знайдено: {foreground} на {background}, співвідношення {ratio} замість потрібних {required}.",
        "it": "Trovato: {foreground} su {background}, rapporto {ratio} invece dei {required} richiesti.",
        "en": "Found: {foreground} on {background}, ratio {ratio} against the required {required}.",
    },
    "a11y_contrast_inline_why": {
        "uk": "Світло-сірий на білому виглядає стримано на моніторі дизайнера і зникає на дешевому екрані, при яскравому світлі й для більшості людей за сорок. Порогом 4.5:1 позначено межу, за якою текст перестає читатися, а не смак.",
        "it": "Il grigio chiaro su bianco sembra sobrio sul monitor del designer e sparisce su uno schermo economico, in piena luce e per la maggior parte delle persone oltre i quarant'anni. La soglia 4.5:1 segna il punto in cui il testo smette di essere leggibile, non una questione di gusto.",
        "en": "Light grey on white looks restrained on a designer's monitor and disappears on a cheap screen, in bright light, and for most people over forty. The 4.5:1 threshold marks where text stops being readable — it is not a matter of taste.",
    },
    "a11y_contrast_inline_fix": {
        "uk": "Затемніть текст або освітліть тло, доки співвідношення не буде щонайменше 4.5:1 для звичайного тексту і 3:1 для великого (від 24px, або 19px жирним).",
        "it": "Scurisci il testo o schiarisci lo sfondo finché il rapporto non è almeno 4.5:1 per il testo normale e 3:1 per quello grande (da 24px, o 19px in grassetto).",
        "en": "Darken the text or lighten the background until the ratio is at least 4.5:1 for body text and 3:1 for large text (24px and up, or 19px bold).",
    },
    "a11y_viewport_fixed_width_title": {
        "uk": "Елемент зафіксований шириною, що ширша за телефон",
        "it": "Elemento bloccato a una larghezza più ampia dello schermo del telefono",
        "en": "An element is pinned to a width wider than a phone",
    },
    "a11y_viewport_fixed_width_found": {
        "uk": "Знайдено оголошення width: {width_px}px при ширині екрана телефону близько {mobile_viewport}px.",
        "it": "Trovata una dichiarazione width: {width_px}px con uno schermo telefonico di circa {mobile_viewport}px.",
        "en": "Found a width declaration of {width_px}px against a phone viewport of about {mobile_viewport}px.",
    },
    "a11y_viewport_fixed_width_why": {
        "uk": "Фіксована ширина у сотні пікселів означає, що на телефоні елемент виходить за екран, і сторінку доводиться гортати вбік, читаючи текст шматками. WCAG 1.4.10 вимагає, щоб уміст перебудовувався без горизонтальної прокрутки - заміна width на max-width лишає широкий макет на великому екрані і дозволяє стиснення на малому.",
        "it": "Una larghezza fissa di centinaia di pixel fa sì che su telefono l'elemento esca dallo schermo e la pagina vada fatta scorrere di lato per leggere il testo a pezzi. La WCAG 1.4.10 richiede che il contenuto si riorganizzi senza scorrimento orizzontale: sostituire width con max-width mantiene il layout largo sul grande schermo e permette la compressione su quello piccolo.",
        "en": "A fixed width of hundreds of pixels means that on a phone the element runs off the screen and the page has to be scrolled sideways to read text in fragments. WCAG 1.4.10 requires content to reflow without horizontal scrolling - swapping width for max-width keeps the wide layout on large screens while allowing it to shrink on small ones.",
    },
    "a11y_viewport_fixed_width_fix": {
        "uk": "Замініть width на max-width для цього значення, або задайте ширину у відсотках чи через flex/grid, якщо фіксовані пікселі не потрібні за задумом.",
        "it": "Sostituisci width con max-width per questo valore, oppure imposta la larghezza in percentuale o tramite flex/grid se i pixel fissi non sono necessari al progetto.",
        "en": "Replace width with max-width for this value, or size the element in percentages or via flex/grid if fixed pixels are not part of the design.",
    },
    "a11y_viewport_tiny_font_title": {
        "uk": "Розмір шрифту менший за читабельний",
        "it": "Dimensione del font inferiore alla soglia leggibile",
        "en": "Font size below the readable threshold",
    },
    "a11y_viewport_tiny_font_found": {
        "uk": "Знайдено font-size {font_px}px при рекомендованому мінімумі {minimum_recommended}px.",
        "it": "Trovato font-size {font_px}px contro un minimo consigliato di {minimum_recommended}px.",
        "en": "Found font-size {font_px}px against a recommended minimum of {minimum_recommended}px.",
    },
    "a11y_viewport_tiny_font_why": {
        "uk": "Шрифт менший за 10px на телефоні не читається без жесту збільшення, а користувачі старшого віку просто відкладають таку сторінку. Браузерний мінімум не рятує: він застосовується не скрізь, а зум всієї сторінки ламає макет. WCAG 1.4.4 вимагає, щоб текст масштабувався до 200% без втрати умісту.",
        "it": "Un font sotto i 10px su telefono non si legge senza gesti di zoom, e gli utenti meno giovani semplicemente abbandonano la pagina. Il minimo del browser non basta: non si applica ovunque e lo zoom dell'intera pagina rompe il layout. La WCAG 1.4.4 richiede che il testo sia ridimensionabile fino al 200% senza perdita di contenuto.",
        "en": "Text under 10px on a phone cannot be read without pinch-zooming, and older users simply put such a page down. The browser's minimum size does not save you: it does not apply everywhere, and full-page zoom breaks the layout. WCAG 1.4.4 requires text to resize up to 200% without loss of content.",
    },
    "a11y_viewport_tiny_font_fix": {
        "uk": "Підніміть розмір щонайменше до 10-12px; справжній дрібний текст (юридичні примітки, підписи) робіть читабельним, а не формально присутнім.",
        "it": "Porta la dimensione ad almeno 10-12px; il testo volutamente piccolo (note legali, didascalie) deve restare leggibile, non solo formalmente presente.",
        "en": "Raise the size to at least 10-12px; deliberately small text (legal notes, captions) should stay readable, not merely present.",
    },
    "a11y_viewport_touch_target_title": {
        "uk": "Кнопка чи посилання завмалі для пальця",
        "it": "Pulsante o link troppo piccolo per un dito",
        "en": "A button or link is too small for a finger",
    },
    "a11y_viewport_touch_target_found": {
        "uk": "Знайдено інтерактивний елемент із оголошеними розмірами {declared} при мінімумі WCAG {wcag_minimum}px (рекомендовано близько {recommended}px).",
        "it": "Trovato un elemento interattivo con dimensioni dichiarate {declared} contro un minimo WCAG di {wcag_minimum}px (consigliati circa {recommended}px).",
        "en": "Found an interactive element with declared sizes of {declared} against the WCAG minimum of {wcag_minimum}px (about {recommended}px recommended).",
    },
    "a11y_viewport_touch_target_why": {
        "uk": "Ціль у 20 пікселів промахується пальцем особливо в дорозі: поруч стоїть сусідня ціль, і натискання потрапляє не туди. Стандарт 2.5.8 задає межу 24px, але мобільні платформи радять близько 44px, бо реальний палець ширше за курсор.",
        "it": "Un bersaglio di 20 pixel viene mancato col dito soprattutto in movimento: il bersaglio vicino è adiacente e il tocco finisce nel posto sbagliato. Lo standard 2.5.8 fissa il minimo a 24px, ma le piattaforme mobili consigliano circa 44px, perché un dito reale è più largo di un cursore.",
        "en": "A 20-pixel target gets missed by a finger especially on the move: neighbouring targets sit close together and taps land on the wrong one. Standard 2.5.8 sets the floor at 24px, but mobile platforms recommend around 44px because a real finger is wider than a cursor.",
    },
    "a11y_viewport_touch_target_fix": {
        "uk": "Збільшіть саму ціль або додайте прозорий відступ навколо (padding), щоб загальна область дотику була щонайменше 24px, а краще 44px.",
        "it": "Ingrandisci il bersaglio stesso oppure aggiungi un margine trasparente intorno (padding) affinché l'area totale di tocco sia almeno 24px, meglio ancora 44px.",
        "en": "Enlarge the target itself or add transparent spacing around it (padding) so the total touch area is at least 24px, better still 44px.",
    },
    # ---------------------------------------------------------------- SEO
    "a11y_seo_title_length_title": {
        "uk": "Заголовок сторінки поза робочою довжиною",
        "it": "Titolo della pagina fuori dalla lunghezza utile",
        "en": "Page title outside the useful length",
    },
    "a11y_seo_title_length_found": {
        "uk": "Заголовок має {length} символів при робочому діапазоні {min}-{max}: «{title}».",
        "it": "Il titolo ha {length} caratteri, l'intervallo utile è {min}-{max}: «{title}».",
        "en": "The title is {length} characters against a useful range of {min}-{max}: \"{title}\".",
    },
    "a11y_seo_title_length_why": {
        "uk": "Заголовок є першим рядком у результатах пошуку, у вкладці браузера і у закладці. Надто короткий не відрізняє сторінку від сусідніх, надто довгий обрізається, і обрізається саме кінець, де зазвичай стоїть найточніше слово. Це не штраф від пошуковика, а межа показу: те, що не вміщується, просто не бачить жодна людина.",
        "it": "Il titolo è la prima riga nei risultati di ricerca, nella scheda del browser e nei preferiti. Troppo corto non distingue la pagina dalle altre, troppo lungo viene troncato, e viene troncata proprio la fine, dove di solito sta la parola più precisa. Non è una penalità del motore di ricerca, è un limite di visualizzazione: ciò che non entra non lo legge nessuno.",
        "en": "The title is the first line in a search result, in the browser tab and in a bookmark. Too short and it does not tell this page apart from its neighbours; too long and it is truncated - and what gets cut is the end, where the most specific word usually sits. This is not a ranking penalty, it is a display limit: what does not fit is seen by nobody.",
    },
    "a11y_seo_title_length_fix": {
        "uk": "Тримайте {min}-{max} символів і ставте на початок те, що відрізняє цю сторінку, а назву сайту в кінець: «Оренда авто в Києві - Назва». Заголовок має описувати сторінку, а не сайт.",
        "it": "Resta tra {min} e {max} caratteri e metti all'inizio ciò che distingue questa pagina, il nome del sito alla fine: «Noleggio auto a Kiev - Nome». Il titolo descrive la pagina, non il sito.",
        "en": "Keep it between {min} and {max} characters, and put what makes this page different first, the site name last: \"Car hire in Kyiv - Brand\". The title describes the page, not the site.",
    },
    "a11y_seo_meta_description_title": {
        "uk": "Опис сторінки відсутній або поза робочою довжиною",
        "it": "Meta description assente o fuori dalla lunghezza utile",
        "en": "Meta description missing or outside the useful length",
    },
    "a11y_seo_meta_description_found": {
        "uk": "Довжина meta description: {length} символів при діапазоні {min}-{max}. Нуль означає, що тега немає взагалі.",
        "it": "Lunghezza della meta description: {length} caratteri, intervallo utile {min}-{max}. Zero significa che il tag non c'è affatto.",
        "en": "Meta description length: {length} characters against a range of {min}-{max}. Zero means the tag is absent entirely.",
    },
    "a11y_seo_meta_description_why": {
        "uk": "Це другий рядок у результатах пошуку і текст, який показує кожен месенджер при вставленні посилання. Коли опису немає, пошуковик збирає уривок сам з першого-ліпшого тексту сторінки, і це часто меню або юридична примітка. Тобто рядок усе одно буде показаний, питання лише в тому, писали його ви чи ні.",
        "it": "È la seconda riga nei risultati di ricerca e il testo che ogni messaggistica mostra quando si incolla il link. Se la description manca, il motore compone lo snippet da solo prendendo il primo testo disponibile, che spesso è il menu o una nota legale. La riga viene mostrata comunque: l'unica domanda è se l'hai scritta tu.",
        "en": "This is the second line of a search result and the text every chat app shows when someone pastes the link. With no description the engine writes the snippet itself from whatever text comes first, which is often the menu or a legal notice. The line gets shown either way; the only question is whether you wrote it.",
    },
    "a11y_seo_meta_description_fix": {
        "uk": "Додайте <meta name=\"description\" content=\"…\"> на {min}-{max} символів: одне-два речення про те, що людина отримає саме на цій сторінці. Не переказ заголовка і не список ключових слів.",
        "it": "Aggiungi <meta name=\"description\" content=\"…\"> di {min}-{max} caratteri: una o due frasi su cosa trova la persona proprio in questa pagina. Non una parafrasi del titolo né un elenco di parole chiave.",
        "en": "Add a <meta name=\"description\" content=\"…\"> of {min}-{max} characters: one or two sentences about what a person gets on this particular page. Not a restatement of the title, and not a keyword list.",
    },
    "a11y_seo_canonical_title": {
        "uk": "Канонічне посилання відсутнє або їх кілька",
        "it": "Link canonical assente o duplicato",
        "en": "Canonical link missing or duplicated",
    },
    "a11y_seo_canonical_found": {
        "uk": "Тегів <link rel=\"canonical\"> на сторінці: {count}. Правильна кількість - рівно один.",
        "it": "Tag <link rel=\"canonical\"> nella pagina: {count}. Il numero corretto è esattamente uno.",
        "en": "Number of <link rel=\"canonical\"> tags on the page: {count}. The correct number is exactly one.",
    },
    "a11y_seo_canonical_why": {
        "uk": "Та сама сторінка майже завжди доступна за кількома адресами: з www і без, з параметрами відстеження, зі слешем у кінці і без. Без канонічного посилання пошуковик рахує їх різними сторінками і ділить вагу між ними. Два канонічні теги гірші за жодного: система обирає один сама або ігнорує обидва, і цей вибір сайту вже не належить.",
        "it": "La stessa pagina è quasi sempre raggiungibile a più indirizzi: con e senza www, con parametri di tracciamento, con e senza slash finale. Senza canonical il motore le considera pagine diverse e divide il peso tra loro. Due tag canonical sono peggio di nessuno: il sistema ne sceglie uno da solo o li ignora entrambi, e quella scelta non appartiene più al sito.",
        "en": "The same page is nearly always reachable at several addresses: with and without www, with tracking parameters, with and without a trailing slash. With no canonical the engine treats them as separate pages and splits the weight between them. Two canonicals are worse than none: the system picks one itself or ignores both, and that choice no longer belongs to the site.",
    },
    "a11y_seo_canonical_fix": {
        "uk": "Лишіть один тег у <head> із повною абсолютною адресою тієї версії, яку вважаєте основною: <link rel=\"canonical\" href=\"https://example.com/page\">. Відносний шлях тут не працює надійно.",
        "it": "Lascia un solo tag nel <head> con l'indirizzo assoluto completo della versione che consideri principale: <link rel=\"canonical\" href=\"https://example.com/page\">. Un percorso relativo qui non è affidabile.",
        "en": "Leave one tag in <head> with the full absolute address of the version you consider primary: <link rel=\"canonical\" href=\"https://example.com/page\">. A relative path is not reliable here.",
    },
    "a11y_seo_noindex_title": {
        "uk": "Сторінка закрита від індексації",
        "it": "Pagina esclusa dall'indicizzazione",
        "en": "Page blocked from indexing",
    },
    "a11y_seo_noindex_found": {
        "uk": "Знайдено директиву robots зі значенням: {content}.",
        "it": "Trovata una direttiva robots con valore: {content}.",
        "en": "Found a robots directive with the value: {content}.",
    },
    "a11y_seo_noindex_why": {
        "uk": "Це найдорожча помилка з усіх у цьому списку, і водночас найтихіша: сторінка виглядає нормально, працює нормально і просто відсутня в пошуку. Майже завжди це директива з тестового середовища, яка поїхала в реліз разом із кодом. Поки вона діє, решта роботи над цією сторінкою не має значення.",
        "it": "È l'errore più costoso di questo elenco e insieme il più silenzioso: la pagina sembra normale, funziona normalmente e semplicemente non esiste nella ricerca. Quasi sempre è una direttiva dell'ambiente di test finita in produzione insieme al codice. Finché è attiva, tutto il resto del lavoro su questa pagina non conta.",
        "en": "This is the most expensive mistake in the list and also the quietest: the page looks fine, works fine, and is simply absent from search. It is nearly always a staging directive that shipped along with the code. While it holds, none of the other work on this page matters.",
    },
    "a11y_seo_noindex_fix": {
        "uk": "Якщо сторінка публічна - приберіть цей тег або поставте content=\"index, follow\". Якщо вона справді має бути прихованою, лишіть, але переконайтесь, що це свідоме рішення для саме цієї адреси, а не глобальний шаблон.",
        "it": "Se la pagina è pubblica, rimuovi il tag o metti content=\"index, follow\". Se deve davvero restare nascosta, lascialo, ma verifica che sia una scelta consapevole per questo indirizzo e non un template globale.",
        "en": "If the page is public, remove the tag or set content=\"index, follow\". If it genuinely should stay hidden, keep it, but check that this is a deliberate decision for this address and not a global template.",
    },
    "a11y_seo_open_graph_title": {
        "uk": "Немає розмітки для прев'ю посилання",
        "it": "Manca il markup per l'anteprima del link",
        "en": "No markup for link previews",
    },
    "a11y_seo_open_graph_found": {
        "uk": "Відсутні теги Open Graph: {missing}.",
        "it": "Tag Open Graph mancanti: {missing}.",
        "en": "Missing Open Graph tags: {missing}.",
    },
    "a11y_seo_open_graph_why": {
        "uk": "Коли посиланням діляться в месенджері чи соцмережі, картку прев'ю збирають саме з цих тегів. Без них показується гола адреса або випадковий уривок з випадковою картинкою зі сторінки. Різниця у кліках тут велика, і вона стосується найтеплішого трафіку - того, що прийшов за особистою рекомендацією.",
        "it": "Quando il link viene condiviso in una chat o sui social, l'anteprima si costruisce proprio da questi tag. Senza di essi si vede l'indirizzo nudo oppure un frammento casuale con un'immagine casuale della pagina. La differenza nei clic è grande e riguarda il traffico più caldo: quello arrivato per raccomandazione personale.",
        "en": "When a link is shared in a chat app or on social media, the preview card is built from exactly these tags. Without them the recipient sees a bare address, or a random excerpt with a random image from the page. The difference in clicks is large, and it applies to the warmest traffic there is - the kind that arrives on a personal recommendation.",
    },
    "a11y_seo_open_graph_fix": {
        "uk": "Додайте в <head> три теги: og:title, og:description і og:image з абсолютною адресою картинки приблизно 1200x630. Заголовок і опис можуть відрізнятися від пошукових - тут вони пишуться для людини, яка вже отримала посилання від знайомого.",
        "it": "Aggiungi nel <head> tre tag: og:title, og:description e og:image con l'URL assoluto di un'immagine di circa 1200x630. Titolo e descrizione possono differire da quelli per la ricerca: qui si scrive per una persona che ha già ricevuto il link da un conoscente.",
        "en": "Add three tags to <head>: og:title, og:description and og:image with an absolute image URL around 1200x630. The title and description may differ from the search ones - here you are writing for someone who already got the link from a person they know.",
    },
    "a11y_seo_structured_data_title": {
        "uk": "На сторінці немає структурованих даних",
        "it": "Nella pagina non ci sono dati strutturati",
        "en": "No structured data on the page",
    },
    "a11y_seo_structured_data_found": {
        "uk": "Не знайдено ані JSON-LD (<script type=\"application/ld+json\">), ані мікророзмітки itemscope.",
        "it": "Non è stato trovato né JSON-LD (<script type=\"application/ld+json\">) né microdata itemscope.",
        "en": "Neither JSON-LD (<script type=\"application/ld+json\">) nor itemscope microdata was found.",
    },
    "a11y_seo_structured_data_why": {
        "uk": "Структуровані дані є єдиним способом сказати машині прямо, чим є ця сторінка: статтею, товаром, рецептом, організацією, подією. Без них і пошуковик, і асистент здогадуються з тексту. Саме з цієї розмітки збираються розширені результати з ціною, рейтингом чи датою, і саме її читають AI-відповіді, коли вирішують, кого процитувати.",
        "it": "I dati strutturati sono l'unico modo per dire a una macchina, in modo esplicito, che cosa è questa pagina: un articolo, un prodotto, una ricetta, un'organizzazione, un evento. Senza di essi sia il motore di ricerca sia l'assistente devono indovinare dal testo. Da questo markup nascono i risultati arricchiti con prezzo, valutazione o data, ed è quello che leggono le risposte AI quando decidono chi citare.",
        "en": "Structured data is the only way to tell a machine outright what this page is: an article, a product, a recipe, an organisation, an event. Without it both the search engine and the assistant have to guess from the prose. Rich results with a price, a rating or a date are built from this markup, and it is what AI answers read when deciding whom to cite.",
    },
    "a11y_seo_structured_data_fix": {
        "uk": "Додайте один блок JSON-LD із типом, що відповідає сторінці: Article для тексту, Product для товару, Organization для головної. Описуйте лише те, що справді є на сторінці - розмітка, яка обіцяє рейтинг, якого користувач не бачить, карається окремо.",
        "it": "Aggiungi un blocco JSON-LD con il tipo che corrisponde alla pagina: Article per un testo, Product per un prodotto, Organization per la home. Descrivi solo ciò che è davvero nella pagina: un markup che promette una valutazione invisibile all'utente viene sanzionato a parte.",
        "en": "Add one JSON-LD block with the type that matches the page: Article for a text, Product for an item, Organization for the home page. Describe only what is actually on the page - markup promising a rating the visitor cannot see is penalised in its own right.",
    },
    "a11y_seo_image_dimensions_title": {
        "uk": "Зображення без заданих розмірів",
        "it": "Immagine senza dimensioni dichiarate",
        "en": "Image with no declared dimensions",
    },
    "a11y_seo_image_dimensions_found": {
        "uk": "У <img src=\"{src}\"> немає ані width і height, ані aspect-ratio у стилях.",
        "it": "In <img src=\"{src}\"> mancano sia width e height sia aspect-ratio negli stili.",
        "en": "The <img src=\"{src}\"> has neither width and height nor an aspect-ratio in its styles.",
    },
    "a11y_seo_image_dimensions_why": {
        "uk": "Поки картинка не завантажилась, браузер не знає, скільки місця їй лишити, тому не лишає нічого. Коли вона приходить, увесь текст під нею стрибає вниз. Людина в цей момент уже читає або тягнеться до кнопки, і натискає не туди. Це найпоширеніша причина поганого показника стабільності макета.",
        "it": "Finché l'immagine non è caricata il browser non sa quanto spazio riservarle, quindi non ne riserva affatto. Quando arriva, tutto il testo sotto salta verso il basso. In quel momento la persona sta già leggendo o sta per premere un pulsante, e finisce per premere altrove. È la causa più comune di un cattivo punteggio di stabilità del layout.",
        "en": "Until the image loads the browser does not know how much room to leave for it, so it leaves none. When it arrives, everything below jumps down. By then the person is already reading, or reaching for a button, and taps the wrong thing. This is the most common cause of a poor layout-stability score.",
    },
    "a11y_seo_image_dimensions_fix": {
        "uk": "Вкажіть справжні пікселі оригіналу в width і height: <img src=\"…\" width=\"800\" height=\"600\">. CSS далі може розтягувати картинку як завгодно - атрибути потрібні лише для співвідношення сторін, за яким браузер резервує місце заздалегідь.",
        "it": "Indica i pixel reali dell'originale in width e height: <img src=\"…\" width=\"800\" height=\"600\">. Il CSS può poi ridimensionare l'immagine come vuoi: gli attributi servono solo per il rapporto d'aspetto con cui il browser riserva lo spazio in anticipo.",
        "en": "Give the real pixel size of the original in width and height: <img src=\"…\" width=\"800\" height=\"600\">. CSS can still scale the image however you like - the attributes only supply the aspect ratio the browser uses to reserve the space up front.",
    },
    "a11y_seo_empty_link_title": {
        "uk": "Посилання без тексту",
        "it": "Link senza testo",
        "en": "Link with no text",
    },
    "a11y_seo_empty_link_found": {
        "uk": "Посилання на {href} не містить ані тексту, ані зображення, ані aria-label.",
        "it": "Il link a {href} non contiene né testo, né immagine, né aria-label.",
        "en": "The link to {href} contains no text, no image and no aria-label.",
    },
    "a11y_seo_empty_link_why": {
        "uk": "Текст посилання є єдиним поясненням того, куди воно веде - і для людини, і для пошукової системи, яка з нього розуміє, про що цільова сторінка. Порожнє посилання не передає нічого нікуди, а для того, хто йде по сторінці клавіатурою, воно ще й стає зупинкою без назви: фокус десь є, а що це - невідомо.",
        "it": "Il testo del link è l'unica spiegazione di dove porta, sia per la persona sia per il motore di ricerca, che da lì capisce di cosa parla la pagina di destinazione. Un link vuoto non trasmette nulla a nessuno, e per chi naviga da tastiera diventa una fermata senza nome: il focus è da qualche parte, ma su che cosa non si sa.",
        "en": "Link text is the only account of where the link goes - both for a person and for a search engine, which reads it to understand what the target page is about. An empty link conveys nothing to anyone, and for someone moving through the page by keyboard it becomes a stop with no name: the focus is somewhere, but on what is anybody's guess.",
    },
    "a11y_seo_empty_link_fix": {
        "uk": "Дайте посиланню видимий текст, що описує ціль. Якщо за задумом це іконка без підпису, додайте aria-label=\"…\" з тією ж назвою, яку сказали б уголос: aria-label=\"Ми у Facebook\", а не \"посилання\".",
        "it": "Dai al link un testo visibile che descriva la destinazione. Se per scelta è un'icona senza etichetta, aggiungi aria-label=\"…\" con lo stesso nome che diresti a voce: aria-label=\"Siamo su Facebook\", non \"link\".",
        "en": "Give the link visible text that describes the destination. If it is deliberately an unlabelled icon, add aria-label=\"…\" with the same name you would say out loud: aria-label=\"We are on Facebook\", not \"link\".",
    },
    # -------------------------------------------------------- Performance
    "a11y_perf_render_blocking_title": {
        "uk": "Забагато ресурсів блокують перший показ сторінки",
        "it": "Troppe risorse bloccano la prima visualizzazione",
        "en": "Too many resources block the first paint",
    },
    "a11y_perf_render_blocking_found": {
        "uk": "У <head> знайдено {count} {files_noun} при розумній межі {budget}.",
        "it": "Nel <head> ci sono {count} {files_noun}, il limite ragionevole è {budget}.",
        "en": "Found {count} {files_noun} in <head> against a sensible budget of {budget}.",
    },
    "a11y_perf_render_blocking_why": {
        "uk": "Скрипт без async чи defer і звичайний файл стилів зупиняють розбір документа: браузер не малює жодного пікселя, доки не завантажить і не виконає кожен з них. Тобто час до першого слова на екрані дорівнює сумі найповільніших запитів, і на мобільному зв'язку це секунди білого екрана при цілком робочому сайті.",
        "it": "Uno script senza async o defer e un foglio di stile normale fermano l'analisi del documento: il browser non disegna un solo pixel finché non ha scaricato ed eseguito ognuno di essi. Il tempo fino alla prima parola sullo schermo è quindi la somma delle richieste più lente, e su rete mobile sono secondi di schermo bianco con un sito perfettamente funzionante.",
        "en": "A script without async or defer, and an ordinary stylesheet, stop the parser: the browser paints no pixel until it has fetched and run every one of them. Time to the first word on screen is therefore the sum of the slowest requests, and on a mobile connection that is seconds of white screen in front of a perfectly working site.",
    },
    "a11y_perf_render_blocking_fix": {
        "uk": "Скриптам у <head> додайте defer, а тим, що не потрібні для першого екрана - async. Стилі розділіть: критичні для першого екрана вставте інлайново, решту підключіть з media=\"print\" і перемкніть на all після завантаження. Мета - лишити в <head> не більше {budget} блокувальних запитів.",
        "it": "Aggiungi defer agli script nel <head> e async a quelli non necessari alla prima schermata. Dividi gli stili: quelli critici per la prima schermata inseriscili inline, il resto caricalo con media=\"print\" e passa ad all dopo il caricamento. L'obiettivo è lasciare nel <head> non più di {budget} richieste bloccanti.",
        "en": "Give scripts in <head> a defer, and async to those not needed for the first screen. Split the styles: inline what the first screen needs and load the rest with media=\"print\", switching it to all once it has arrived. The target is no more than {budget} blocking requests in <head>.",
    },
    "a11y_perf_third_party_sync_title": {
        "uk": "Сторонній скрипт завантажується синхронно",
        "it": "Script di terze parti caricato in modo sincrono",
        "en": "Third-party script loaded synchronously",
    },
    "a11y_perf_third_party_sync_found": {
        "uk": "Скрипт з чужого домену {host} підключений без async і без defer: {src}.",
        "it": "Uno script dal dominio esterno {host} è incluso senza async e senza defer: {src}.",
        "en": "A script from the external host {host} is included with neither async nor defer: {src}.",
    },
    "a11y_perf_third_party_sync_why": {
        "uk": "Такий тег віддає чужому серверу право зупинити показ вашої сторінки. Якщо аналітика, чат підтримки чи рекламна мережа відповідатиме повільно або не відповість зовсім, відвідувач дивитиметься на порожнє вікно, і жодна оптимізація власного коду цього не змінить. Це єдина точка відмови, яка не належить команді сайту.",
        "it": "Un tag così concede a un server esterno il diritto di fermare la visualizzazione della tua pagina. Se l'analytics, la chat di supporto o il network pubblicitario risponde lentamente o non risponde affatto, il visitatore guarda una finestra vuota, e nessuna ottimizzazione del proprio codice lo cambia. È un punto di guasto unico che non appartiene al team del sito.",
        "en": "A tag like this hands an outside server the power to stop your page from rendering. If the analytics, the support chat or the ad network answers slowly - or not at all - the visitor stares at an empty window, and no amount of optimising your own code changes that. It is a single point of failure that does not belong to the site's team.",
    },
    "a11y_perf_third_party_sync_fix": {
        "uk": "Додайте defer, якщо порядок виконання важливий, або async, якщо ні. Скрипти, потрібні лише після взаємодії (чат, віджет відгуків), підключайте за подією, а не одразу при завантаженні.",
        "it": "Aggiungi defer se l'ordine di esecuzione conta, oppure async se non conta. Gli script necessari solo dopo un'interazione (chat, widget di recensioni) caricali su evento, non subito al caricamento.",
        "en": "Add defer if execution order matters, async if it does not. Scripts only needed after an interaction (a chat widget, a review embed) should be loaded on that event rather than at page load.",
    },
    "a11y_perf_large_inline_title": {
        "uk": "Завеликий інлайновий блок коду або стилів",
        "it": "Blocco inline di codice o stili troppo grande",
        "en": "Oversized inline code or style block",
    },
    "a11y_perf_large_inline_found": {
        "uk": "Блок <{element}> містить {bytes} байтів при межі {budget}.",
        "it": "Il blocco <{element}> contiene {bytes} byte, il limite è {budget}.",
        "en": "The <{element}> block holds {bytes} bytes against a budget of {budget}.",
    },
    "a11y_perf_large_inline_why": {
        "uk": "Інлайновий блок економить один запит, і саме тому в нього поступово переїжджає все. Але він приходить у кожній відповіді сервера, ніколи не кешується між сторінками і розбирається в головному потоці до першого показу. Після певного розміру економія на запиті стає меншою за втрату на розборі, а на повторних відвідинах цей код завантажується знову і знову.",
        "it": "Un blocco inline risparmia una richiesta, ed è proprio per questo che ci finisce dentro tutto, poco a poco. Ma arriva in ogni risposta del server, non viene mai messo in cache tra le pagine e viene analizzato nel thread principale prima della prima visualizzazione. Oltre una certa dimensione il risparmio sulla richiesta diventa minore della perdita nell'analisi, e a ogni nuova visita quel codice si scarica di nuovo.",
        "en": "An inline block saves one request, which is exactly why everything gradually migrates into it. But it ships in every server response, is never cached across pages, and is parsed on the main thread before the first paint. Past a certain size the saved request costs less than the parsing, and on every repeat visit that code is downloaded all over again.",
    },
    "a11y_perf_large_inline_fix": {
        "uk": "Винесіть блок в окремий файл і підключіть його посиланням - тоді він кешується і не приходить з кожною сторінкою. Інлайновим лишайте тільки те, що справді потрібне для першого екрана, у межах {budget} байтів.",
        "it": "Sposta il blocco in un file separato e collegalo: così viene messo in cache e non arriva con ogni pagina. Lascia inline solo ciò che serve davvero alla prima schermata, entro {budget} byte.",
        "en": "Move the block into its own file and link to it - then it is cached and does not travel with every page. Keep inline only what the first screen genuinely needs, within {budget} bytes.",
    },
    "a11y_perf_image_loading_title": {
        "uk": "Зображення нижче першого екрана без відкладеного завантаження",
        "it": "Immagine sotto la prima schermata senza caricamento differito",
        "en": "Below-the-fold image without lazy loading",
    },
    "a11y_perf_image_loading_found": {
        "uk": "У <img src=\"{src}\"> немає loading=\"lazy\", хоча зображення стоїть далеко від початку сторінки.",
        "it": "In <img src=\"{src}\"> manca loading=\"lazy\", pur trovandosi lontano dall'inizio della pagina.",
        "en": "The <img src=\"{src}\"> has no loading=\"lazy\", although it sits well below the start of the page.",
    },
    "a11y_perf_image_loading_why": {
        "uk": "За замовчуванням браузер тягне всі зображення одразу, разом із тими, до яких відвідувач ніколи не догортає. Вони змагаються за канал із тим, що видно зараз, тому головна картинка на екрані з'являється пізніше. На мобільному тарифі це ще й прямі витрати людини за трафік, який вона не побачила.",
        "it": "Per impostazione predefinita il browser scarica subito tutte le immagini, comprese quelle fino a cui il visitatore non arriverà mai. Competono per la banda con ciò che è visibile adesso, quindi l'immagine principale compare più tardi. Su una tariffa mobile è anche un costo diretto per traffico che la persona non ha visto.",
        "en": "By default the browser fetches every image at once, including the ones the visitor never scrolls to. They compete for bandwidth with what is on screen now, so the main image appears later. On a metered mobile plan it is also money spent on data the person never saw.",
    },
    "a11y_perf_image_loading_fix": {
        "uk": "Додайте loading=\"lazy\" до зображень нижче першого екрана. Першим 2-3 картинкам його не ставте: там відкладення лише сповільнює найбільший видимий елемент, тобто робить гірше саме там, де вимірюється швидкість.",
        "it": "Aggiungi loading=\"lazy\" alle immagini sotto la prima schermata. Non metterlo alle prime 2-3: lì il differimento rallenta soltanto l'elemento visibile più grande, cioè peggiora proprio dove la velocità viene misurata.",
        "en": "Add loading=\"lazy\" to images below the first screen. Do not put it on the first two or three: there, deferring only slows the largest visible element - it makes things worse exactly where speed is measured.",
    },
    "a11y_perf_font_display_title": {
        "uk": "Шрифт без стратегії показу тексту",
        "it": "Font senza strategia di visualizzazione del testo",
        "en": "Font with no text-display strategy",
    },
    "a11y_perf_font_display_found": {
        "uk": "Шрифт підключено без font-display і без параметра display: {href}.",
        "it": "Font caricato senza font-display e senza il parametro display: {href}.",
        "en": "The font is loaded with no font-display and no display parameter: {href}.",
    },
    "a11y_perf_font_display_why": {
        "uk": "Без вказаної стратегії браузер до трьох секунд ховає текст, доки чекає на шрифт. Сторінка в цей час технічно завантажена, але слів на ній немає - людина дивиться на порожні блоки і часто йде, вирішивши, що сайт зламаний. Ховати вміст заради накреслення шрифту майже ніколи не є правильним обміном.",
        "it": "Senza una strategia dichiarata il browser nasconde il testo fino a tre secondi mentre aspetta il font. In quel momento la pagina è tecnicamente caricata, ma non ci sono parole: la persona guarda blocchi vuoti e spesso se ne va convinta che il sito sia rotto. Nascondere il contenuto per il disegno del carattere non è quasi mai uno scambio corretto.",
        "en": "With no strategy declared the browser hides the text for up to three seconds while it waits for the font. The page is technically loaded, but has no words on it - the visitor looks at empty blocks and often leaves, concluding the site is broken. Hiding content for the sake of a typeface is almost never the right trade.",
    },
    "a11y_perf_font_display_fix": {
        "uk": "Додайте font-display: swap у @font-face, а до посилання на Google Fonts - параметр &display=swap. Текст одразу покажеться запасним шрифтом і перемалюється, коли прийде основний. Для дуже помітної різниці накреслень підійде optional: тоді шрифт застосується лише з наступного візиту.",
        "it": "Aggiungi font-display: swap in @font-face e il parametro &display=swap al link di Google Fonts. Il testo compare subito con il font di riserva e viene ridisegnato quando arriva quello principale. Se la differenza tra i caratteri è molto marcata, usa optional: il font si applicherà dalla visita successiva.",
        "en": "Add font-display: swap to @font-face, and &display=swap to the Google Fonts URL. The text shows immediately in the fallback face and is repainted when the real one arrives. Where the two faces differ sharply, optional works better: the font then applies from the next visit onwards.",
    },
    "a11y_perf_preconnect_title": {
        "uk": "Немає підказок на з'єднання зі сторонніми доменами",
        "it": "Mancano suggerimenti di connessione ai domini esterni",
        "en": "No connection hints for third-party hosts",
    },
    "a11y_perf_preconnect_found": {
        "uk": "Сторінка звертається до {count} {domains_noun} без preconnect чи dns-prefetch: {hosts}.",
        "it": "La pagina contatta {count} {domains_noun} senza preconnect o dns-prefetch: {hosts}.",
        "en": "The page reaches {count} {domains_noun} with no preconnect or dns-prefetch: {hosts}.",
    },
    "a11y_perf_preconnect_why": {
        "uk": "Перш ніж завантажити перший байт з чужого домену, браузер має знайти адресу в DNS, встановити з'єднання і домовитись про шифрування. Це три послідовні подорожі мережею, і на мобільному зв'язку разом вони дають кількасот мілісекунд ще до початку завантаження - і так для кожного домену окремо.",
        "it": "Prima di scaricare il primo byte da un dominio esterno, il browser deve risolvere l'indirizzo via DNS, stabilire la connessione e negoziare la cifratura. Sono tre viaggi di rete consecutivi e, su rete mobile, insieme costano centinaia di millisecondi prima ancora che inizi il download, e questo per ogni dominio separatamente.",
        "en": "Before the first byte arrives from an external host, the browser has to resolve the address over DNS, open a connection and negotiate encryption. That is three consecutive round trips, and on a mobile connection they add up to several hundred milliseconds before the download even starts - separately for every host.",
    },
    "a11y_perf_preconnect_fix": {
        "uk": "Додайте у <head> <link rel=\"preconnect\" href=\"https://домен\"> для двох-трьох найважливіших чужих доменів (шрифти, головний CDN). Робити це для всіх підряд не варто: кожне зайве з'єднання теж займає ресурси, тому решті достатньо dns-prefetch.",
        "it": "Aggiungi nel <head> <link rel=\"preconnect\" href=\"https://dominio\"> per i due o tre domini esterni più importanti (font, CDN principale). Non farlo per tutti: ogni connessione superflua consuma risorse, per gli altri basta dns-prefetch.",
        "en": "Add <link rel=\"preconnect\" href=\"https://host\"> to <head> for the two or three most important external hosts (fonts, the main CDN). Do not do it for all of them: every extra connection costs resources too, so dns-prefetch is enough for the rest.",
    },
    "a11y_perf_layout_shift_title": {
        "uk": "Елемент без зарезервованого місця зсуває макет",
        "it": "Elemento senza spazio riservato che sposta il layout",
        "en": "Element with no reserved space shifts the layout",
    },
    "a11y_perf_layout_shift_found": {
        "uk": "Елемент <{element}> не має ані розмірів, ані aspect-ratio, тому місце під нього не резервується.",
        "it": "L'elemento <{element}> non ha dimensioni né aspect-ratio, quindi non viene riservato spazio.",
        "en": "The <{element}> has neither dimensions nor an aspect-ratio, so no space is reserved for it.",
    },
    "a11y_perf_layout_shift_why": {
        "uk": "Елемент, розмір якого стає відомим лише після завантаження, з'являється у вже прочитаному місці і зсуває все нижче. Найдорожчий наслідок - не естетичний: людина натискає кнопку в момент, коли та поїхала вниз, і потрапляє в іншу. Для реклами й вбудованих плеєрів це трапляється найчастіше, бо їхня висота приходить ззовні.",
        "it": "Un elemento la cui dimensione si conosce solo dopo il caricamento compare in un punto già letto e sposta tutto ciò che sta sotto. La conseguenza più costosa non è estetica: la persona preme un pulsante nell'istante in cui questo scende e ne colpisce un altro. Con la pubblicità e i player incorporati succede più spesso, perché la loro altezza arriva dall'esterno.",
        "en": "An element whose size is only known after it loads appears in a place already being read and pushes everything below it down. The costly consequence is not aesthetic: someone taps a button at the moment it moves and hits a different one. Ads and embedded players cause this most often, because their height comes from outside.",
    },
    "a11y_perf_layout_shift_fix": {
        "uk": "Задайте width і height, або зарезервуйте місце через aspect-ratio у CSS чи контейнер фіксованої висоти. Для вбудованих плеєрів і банерів найнадійніше - обгортка з відомим співвідношенням сторін, бо самі вони своїх розмірів наперед не повідомляють.",
        "it": "Imposta width e height, oppure riserva lo spazio con aspect-ratio nel CSS o con un contenitore di altezza fissa. Per player incorporati e banner la soluzione più solida è un wrapper con rapporto d'aspetto noto, dato che da soli non dichiarano le proprie dimensioni.",
        "en": "Set width and height, or reserve the space with an aspect-ratio in CSS or a container of fixed height. For embedded players and banners the most reliable answer is a wrapper with a known aspect ratio, since they do not announce their own size in advance.",
    },
    # ------------------------------------------------------ Best practices
    "a11y_bp_mixed_content_title": {
        "uk": "Незахищений ресурс на захищеній сторінці",
        "it": "Risorsa non sicura in una pagina sicura",
        "en": "Insecure resource on a secure page",
    },
    "a11y_bp_mixed_content_found": {
        "uk": "Елемент <{element}> завантажується через http на сторінці https: {url}.",
        "it": "L'elemento <{element}> viene caricato via http in una pagina https: {url}.",
        "en": "The <{element}> is loaded over http on an https page: {url}.",
    },
    "a11y_bp_mixed_content_why": {
        "uk": "Один незахищений файл знімає гарантію з усієї сторінки: його вміст можна підмінити в дорозі, і для скрипта це означає чужий код у вашому домені. Браузери вже блокують такі скрипти повністю і поступово беруться за зображення. Сторінка працює сьогодні і перестане після оновлення браузера, яке ніхто з команди не контролює.",
        "it": "Un solo file non sicuro toglie la garanzia all'intera pagina: il suo contenuto può essere sostituito lungo il percorso e, per uno script, questo significa codice altrui nel tuo dominio. I browser bloccano già del tutto questi script e si stanno occupando gradualmente delle immagini. La pagina funziona oggi e smetterà dopo un aggiornamento del browser che nessuno nel team controlla.",
        "en": "A single insecure file removes the guarantee from the whole page: its contents can be swapped in transit, and for a script that means someone else's code running on your domain. Browsers already block such scripts outright and are steadily tightening on images. The page works today and stops working after a browser update nobody on the team controls.",
    },
    "a11y_bp_mixed_content_fix": {
        "uk": "Змініть адресу на https. Якщо чужий сервер не підтримує https - перенесіть файл до себе або замініть постачальника; лишати як є означає чекати на день, коли ресурс просто зникне зі сторінки.",
        "it": "Cambia l'indirizzo in https. Se il server esterno non supporta https, ospita il file da te o cambia fornitore: lasciarlo com'è significa aspettare il giorno in cui la risorsa sparirà dalla pagina.",
        "en": "Change the address to https. If the external server does not support https, host the file yourself or change supplier; leaving it is waiting for the day the resource simply vanishes from the page.",
    },
    "a11y_bp_target_blank_title": {
        "uk": "Посилання у нову вкладку без rel=\"noopener\"",
        "it": "Link a nuova scheda senza rel=\"noopener\"",
        "en": "New-tab link without rel=\"noopener\"",
    },
    "a11y_bp_target_blank_found": {
        "uk": "Посилання на {href} має target=\"_blank\", але не має rel=\"noopener\" чи \"noreferrer\".",
        "it": "Il link a {href} ha target=\"_blank\" ma non rel=\"noopener\" o \"noreferrer\".",
        "en": "The link to {href} has target=\"_blank\" but no rel=\"noopener\" or \"noreferrer\".",
    },
    "a11y_bp_target_blank_why": {
        "uk": "Відкрита сторінка отримує посилання назад на вашу вкладку через window.opener і може перевести її на іншу адресу, поки людина читає нову. Це класичний сценарій підміни сторінки входу. Сучасні браузери підставляють noopener самі, але старі версії і вбудовані вікна всередині застосунків - ні, і саме там така підміна найнепомітніша.",
        "it": "La pagina aperta riceve un riferimento alla tua scheda tramite window.opener e può portarla a un altro indirizzo mentre la persona legge quella nuova. È lo scenario classico di sostituzione della pagina di accesso. I browser moderni aggiungono noopener da soli, ma le versioni vecchie e le finestre incorporate nelle app no, ed è proprio lì che la sostituzione passa più inosservata.",
        "en": "The opened page gets a handle on your tab through window.opener and can navigate it elsewhere while the person is reading the new one. That is the classic login-page swap. Modern browsers imply noopener themselves, but older versions and in-app webviews do not - and those are exactly where such a swap goes unnoticed.",
    },
    "a11y_bp_target_blank_fix": {
        "uk": "Додайте rel=\"noopener noreferrer\" до кожного посилання з target=\"_blank\". Заразом подумайте, чи потрібна нова вкладка взагалі: рішення відкривати її замість людини забирає в неї кнопку «назад».",
        "it": "Aggiungi rel=\"noopener noreferrer\" a ogni link con target=\"_blank\". Già che ci sei, valuta se la nuova scheda serva davvero: deciderla al posto della persona le toglie il pulsante «indietro».",
        "en": "Add rel=\"noopener noreferrer\" to every link with target=\"_blank\". While you are there, consider whether the new tab is needed at all: deciding it on someone's behalf takes their back button away.",
    },
    # Shown when a finding is about the document rather than about an element
    # in it: nothing on screen can be outlined, and saying so beats a click
    # that appears to do nothing.
    # Width names, and the two sentences that report them. Words rather than
    # pixel counts: "1440" is a number the reader has to interpret, "desktop"
    # is the thing they were already thinking about.
    "breakpoint_tooltip": {
        "uk": "Показати прев'ю на ширині {name} ({width} px) - тій самій, на "
              "якій браузерний прохід шукав знахідки",
        "it": "Mostra l'anteprima alla larghezza {name} ({width} px), la "
              "stessa a cui il passaggio nel browser ha cercato",
        "en": "Show the preview at the {name} width ({width} px) - the same "
              "one the browser pass looked at",
    },
    "status_browser_pass_widths": {
        "uk": "Браузерний прохід на {n} ширинах: {url}",
        "it": "Passaggio nel browser a {n} larghezze: {url}",
        "en": "Browser pass at {n} widths: {url}",
    },
    # Said whenever a repository walk stopped at its cap. The one thing a
    # partial result must never do is look like a complete one.
    "finding_copies": {
        "uk": "ще у {n} файлах", "it": "in altri {n} file",
        "en": "in {n} more file(s)",
    },
    "scan_truncated": {
        "uk": "Прочитано лише {files} файлів: спрацювало обмеження в {limit}. "
              "Усе за цією межею не переглядалось, тож це не висновок про "
              "весь репозиторій.",
        "it": "Letti solo {files} file: è scattato il limite di {limit}. "
              "Tutto ciò che sta oltre non è stato esaminato, quindi questa "
              "non è una conclusione sull'intero repository.",
        "en": "Only {files} files were read: the {limit}-file limit stopped "
              "the walk. Nothing past it was examined, so this is not a "
              "statement about the whole repository.",
    },
    "breakpoint_desktop": {"uk": "десктоп", "it": "desktop", "en": "desktop"},
    "breakpoint_tablet": {"uk": "планшет", "it": "tablet", "en": "tablet"},
    "breakpoint_mobile": {"uk": "мобільний", "it": "mobile", "en": "mobile"},
    "a11y_breakpoint_only": {
        "uk": "Знайдено лише на одній ширині: {breakpoints}.",
        "it": "Trovato a una sola larghezza: {breakpoints}.",
        "en": "Found at one width only: {breakpoints}.",
    },
    "a11y_breakpoint_seen": {
        "uk": "Знайдено на ширинах: {breakpoints}.",
        "it": "Trovato alle larghezze: {breakpoints}.",
        "en": "Found at these widths: {breakpoints}.",
    },
    "audit_document_level": {
        "uk": "Ця знахідка стосується документа загалом, окремого елемента для підсвітки немає.",
        "it": "Questa segnalazione riguarda il documento nel suo insieme: non c'è un elemento da evidenziare.",
        "en": "This finding is about the document as a whole - there is no single element to highlight.",
    },
    # Media provenance (`audit/media.py`). Every one of these is worded as
    # "the file says", never as "this is AI": what was read is a statement
    # the file makes about itself, and the absence of one means nothing at
    # all - a screenshot or a re-save strips every field involved.
    # What the repository reveals about itself (`audit/repo_facts.py`).
    # Two of these are provenance and two are security, and the wording
    # keeps them apart: writing code with an assistant is not a defect, and
    # a credential in the working tree is not a style preference.
    # `git blame` on a finding's line (`audit/repo_facts.py`). The caveat
    # travels with the fact every time it is shown: an unqualified
    # name-and-date beside a finding reads as an accusation, and blame does
    # not support one.
    "audit_arrived": {
        "uk": "Рядок востаннє змінено", "it": "Riga modificata l'ultima volta",
        "en": "Line last changed",
    },
    "audit_arrived_assistant": {
        "uk": "Цей коміт називає асистента співавтором.",
        "it": "Questo commit indica un assistente come coautore.",
        "en": "That commit names an assistant as a co-author.",
    },
    "audit_arrived_caveat": {
        "uk": "Це коміт, який востаннє торкнувся рядка, а не обовʼязково той, "
              "що створив проблему: переформатування, перейменування чи "
              "переміщений блок так само забирають рядок на себе.",
        "it": "E il commit che ha toccato la riga per ultimo, non "
              "necessariamente quello che ha creato il problema: una "
              "riformattazione, una rinomina o un blocco spostato prendono la "
              "riga su di se allo stesso modo.",
        "en": "This is the commit that last touched the line, not necessarily "
              "the one that created the problem: a reformat, a rename or a "
              "moved block take the line over just the same.",
    },
    "a11y_bp_assistant_touched_title": {
        "uk": "Частина знахідок у рядках з асистентських комітів",
        "it": "Alcuni riscontri su righe di commit con assistente",
        "en": "Some findings sit on lines from assistant commits",
    },
    "a11y_bp_assistant_touched_found": {
        "uk": "{count} із {read} знахідок, які вдалось привʼязати до рядка, "
              "стоять у рядках, востаннє змінених комітами, що називають "
              "асистента співавтором.",
        "it": "{count} dei {read} riscontri collegabili a una riga si trovano "
              "su righe toccate per ultime da commit che indicano un assistente "
              "come coautore.",
        "en": "{count} of the {read} findings that could be placed on a line "
              "sit on lines last touched by commits naming an assistant as a "
              "co-author.",
    },
    "a11y_bp_assistant_touched_why": {
        "uk": "Це не звинувачення і не оцінка: `git blame` називає коміт, який "
              "востаннє торкнувся рядка, а не той, що створив проблему. "
              "Показано тому, що це єдина точна відповідь на питання про "
              "походження, яку взагалі можна отримати, і тому, що вона своя для "
              "кожного проєкту: у одному це нічого не означає, у іншому це "
              "привід подивитись, як приймається така робота.",
        "it": "Non e un'accusa ne una valutazione: `git blame` nomina il commit "
              "che ha toccato la riga per ultimo, non quello che ha creato il "
              "problema. Viene mostrato perche e l'unica risposta esatta sulla "
              "provenienza che si possa ottenere, e perche significa cose "
              "diverse in progetti diversi.",
        "en": "Not an accusation and not a judgement: `git blame` names the "
              "commit that last touched a line, not the one that created the "
              "problem. It is shown because it is the only exact answer about "
              "provenance available at all, and because it means different "
              "things in different projects - nothing in one, and a reason to "
              "look at how that work is reviewed in another.",
    },
    "a11y_bp_assistant_touched_fix": {
        "uk": "Дії не потрібно. Якщо число здається великим, дивіться не на "
              "інструмент, а на те, як така робота переглядається перед злиттям.",
        "it": "Non serve alcuna azione. Se il numero sembra alto, guardate non "
              "lo strumento ma come quel lavoro viene rivisto prima del merge.",
        "en": "No action needed. If the number looks high, the thing to look at "
              "is not the tool but how that work gets reviewed before it lands.",
    },
    "a11y_sec_env_tracked_title": {
        "uk": "Файл із секретами вже в історії git",
        "it": "Un file con segreti e gia nella storia di git",
        "en": "A secrets file is already in git history",
    },
    "a11y_sec_env_tracked_found": {
        "uk": "{path} відстежується git, тобто він є в кожній копії репозиторія.",
        "it": "{path} e tracciato da git, quindi si trova in ogni copia del "
              "repository.",
        "en": "{path} is tracked by git, so it is in every copy of the "
              "repository.",
    },
    "a11y_sec_env_tracked_why": {
        "uk": "Це вже опубліковано. Видалення файлу цього не скасує: він "
              "лишається в кожному клоні й у кожному записі історії, і будь-хто, "
              "хто мав доступ, має ці значення.",
        "it": "E gia pubblicato. Cancellare il file non lo annulla: resta in "
              "ogni clone e in ogni voce della storia, e chiunque abbia avuto "
              "accesso possiede quei valori.",
        "en": "This is already published. Deleting the file does not undo it: "
              "it stays in every clone and every history entry, and anyone who "
              "had access has those values.",
    },
    "a11y_sec_env_tracked_fix": {
        "uk": "Змініть ці облікові дані. Прибирання файлу з історії має сенс "
              "лише після того, і саме в такому порядку.",
        "it": "Cambiate quelle credenziali. Rimuovere il file dalla storia ha "
              "senso solo dopo, e in quest'ordine.",
        "en": "Rotate those credentials. Removing the file from history is "
              "worth doing only afterwards, and in that order.",
    },
    "a11y_sec_env_not_ignored_title": {
        "uk": "Файл із секретами не в ігнорі",
        "it": "Un file con segreti non e ignorato",
        "en": "A secrets file is not ignored",
    },
    "a11y_sec_env_not_ignored_found": {
        "uk": "{path} лежить у робочій теці, і жодне правило ігнорування його "
              "не покриває.",
        "it": "{path} si trova nella cartella di lavoro e nessuna regola di "
              "ignore lo copre.",
        "en": "{path} is in the working tree and no ignore rule covers it.",
    },
    "a11y_sec_env_not_ignored_why": {
        "uk": "Ще не опубліковано, і саме тому це варто читати зараз: "
              "наступний `git add .` забере його з собою, і тоді буде пізно.",
        "it": "Non e ancora pubblicato, ed e proprio per questo che vale la "
              "pena leggerlo adesso: il prossimo `git add .` se lo porta via.",
        "en": "Not published yet, which is exactly why this is worth reading "
              "now: the next `git add .` takes it along, and then it is too "
              "late.",
    },
    "a11y_sec_env_not_ignored_fix": {
        "uk": "Додайте його до `.gitignore`.",
        "it": "Aggiungetelo a `.gitignore`.",
        "en": "Add it to `.gitignore`.",
    },
    "a11y_bp_assistant_commits_title": {
        "uk": "В історії є коміти, написані з асистентом",
        "it": "La storia contiene commit scritti con un assistente",
        "en": "The history contains commits written with an assistant",
    },
    "a11y_bp_assistant_commits_found": {
        "uk": "{count} із {read} прочитаних комітів називають асистента "
              "співавтором.",
        "it": "{count} dei {read} commit letti indicano un assistente come "
              "coautore.",
        "en": "{count} of the {read} commits read name an assistant as a "
              "co-author.",
    },
    "a11y_bp_assistant_commits_why": {
        "uk": "Це запис, а не здогад: так написано в самих комітах. І це не "
              "дефект. Писати код з асистентом нормально, а інструмент, який "
              "каже інакше, вказує людям, як їм працювати. Показано тому, що "
              "походження коду буває питанням, і відповідь на нього тут точна, "
              "на відміну від будь-якого класифікатора.",
        "it": "E un dato registrato, non una supposizione: lo dicono i commit "
              "stessi. E non e un difetto. Scrivere codice con un assistente va "
              "bene, e uno strumento che dice il contrario sta dicendo alle "
              "persone come lavorare. Viene mostrato perche la provenienza del "
              "codice a volte e una domanda, e qui la risposta e esatta.",
        "en": "This is a record, not a guess: the commits say so themselves. "
              "And it is not a defect. Writing code with an assistant is fine, "
              "and a tool that says otherwise is telling people how to work. "
              "It is shown because the provenance of code is sometimes a "
              "question, and here the answer is exact - unlike any "
              "classifier's.",
    },
    "a11y_bp_assistant_commits_fix": {
        "uk": "Дії не потрібно. Якщо ваш проєкт вимагає позначати такий внесок, "
              "це місце, де видно, що вже позначено.",
        "it": "Non serve alcuna azione. Se il vostro progetto richiede di "
              "dichiarare questo contributo, qui si vede cosa e gia dichiarato.",
        "en": "No action needed. If your project requires declaring this kind "
              "of contribution, this is where you can see what already is.",
    },
    "a11y_bp_assistant_artifacts_title": {
        "uk": "У репозиторії є конфігурація AI-інструментів",
        "it": "Il repository contiene configurazioni di strumenti AI",
        "en": "The repository carries AI tool configuration",
    },
    "a11y_bp_assistant_artifacts_found": {
        "uk": "Знайдено {count}: {names}.",
        "it": "Trovati {count}: {names}.",
        "en": "Found {count}: {names}.",
    },
    "a11y_bp_assistant_artifacts_why": {
        "uk": "Самі по собі вони нешкідливі й часто корисні. Варто подивитись "
              "з іншої причини: такі файли зазвичай містять контекст проєкту, "
              "який писали для інструмента, а не для читача, і разом із ним "
              "інколи внутрішні шляхи, імена систем і робочі домовленості.",
        "it": "Di per se sono innocui e spesso utili. Vale la pena guardarli "
              "per un altro motivo: contengono di solito contesto di progetto "
              "scritto per uno strumento e non per un lettore, e insieme a "
              "quello a volte percorsi interni, nomi di sistemi e accordi di "
              "lavoro.",
        "en": "They are harmless in themselves and often useful. They are worth "
              "a look for a different reason: such files usually hold project "
              "context written for a tool rather than for a reader, and with it "
              "sometimes internal paths, system names and working arrangements.",
    },
    "a11y_bp_assistant_artifacts_fix": {
        "uk": "Прочитайте їх як опубліковані. Якщо там є те, чого ви не "
              "публікували б, приберіть це звідти або файл з індексу.",
        "it": "Leggeteli come se fossero pubblicati. Se contengono qualcosa che "
              "non pubblichereste, toglietelo o togliete il file dall'indice.",
        "en": "Read them as published. If they hold anything you would not "
              "publish, take it out - or take the file out of the index.",
    },
    "a11y_bp_ai_media_declared_title": {
        "uk": "Файл каже, що його згенеровано",
        "it": "Il file dichiara di essere generato",
        "en": "The file states it was generated",
    },
    "a11y_bp_ai_media_declared_found": {
        "uk": "У полі {marker} записано, що зображення зробила модель.",
        "it": "Il campo {marker} dichiara che l'immagine e stata prodotta da "
              "un modello.",
        "en": "The {marker} field records that a model produced this image.",
    },
    "a11y_bp_ai_media_declared_why": {
        "uk": "Це заява самого файлу, а не висновок перевірки: так його "
              "підписав генератор. Зворотне не діє. Відсутність такого поля "
              "не означає, що зображення зняла людина: скріншот, "
              "пересохранення або завантаження через більшість соцмереж "
              "стирають усі ці поля.",
        "it": "E una dichiarazione del file stesso, non una conclusione "
              "dell'analisi: cosi l'ha firmato il generatore. Il contrario "
              "non vale. L'assenza di questo campo non significa che la foto "
              "sia di una persona: uno screenshot, un nuovo salvataggio o il "
              "caricamento su molte piattaforme cancellano tutti questi campi.",
        "en": "This is the file's own statement, not a conclusion the check "
              "drew: the generator signed it that way. The reverse does not "
              "hold. The absence of such a field does not mean a person took "
              "the picture - a screenshot, a re-save, or an upload through "
              "most platforms strips every one of these fields.",
    },
    "a11y_bp_ai_media_declared_fix": {
        "uk": "Дія залежить від контексту, а не від інструмента: якщо "
              "зображення має бути позначене як згенероване, позначте його; "
              "якщо ні, лишіть. Прибирати саме поле не варто, бо воно і є "
              "тим, що робить походження перевірним.",
        "it": "Cosa fare dipende dal contesto, non dallo strumento: se "
              "l'immagine va dichiarata come generata, dichiaratela; "
              "altrimenti lasciatela. Non conviene rimuovere il campo: e "
              "proprio cio che rende verificabile la provenienza.",
        "en": "What to do depends on the context, not on the tool: if the "
              "image should be labelled as generated, label it; if not, leave "
              "it. Removing the field itself is rarely right - it is the "
              "thing that makes the provenance checkable at all.",
    },
    "a11y_bp_ai_media_tool_title": {
        "uk": "У файлі є назва генератора",
        "it": "Il file contiene il nome di un generatore",
        "en": "The file names a generator",
    },
    "a11y_bp_ai_media_tool_found": {
        "uk": "Поле {marker} називає {tool}.",
        "it": "Il campo {marker} nomina {tool}.",
        "en": "The {marker} field names {tool}.",
    },
    "a11y_bp_ai_media_tool_why": {
        "uk": "Слабший факт, ніж попередній: поле каже, яка програма "
              "торкалась файлу, а не звідки взялись пікселі. Зображення, "
              "відредаговане в застосунку генератора, несе той самий рядок.",
        "it": "Un fatto piu debole del precedente: il campo dice quale "
              "programma ha toccato il file, non da dove vengono i pixel. "
              "Un'immagine modificata nell'app di un generatore porta la "
              "stessa stringa.",
        "en": "A weaker fact than the one above: the field says which program "
              "touched the file, not where the pixels came from. An image "
              "edited in a generator's own app carries the same string.",
    },
    "a11y_bp_ai_media_tool_fix": {
        "uk": "Перевірте, чи це те, чим ви вважали цей файл. Правки в коді "
              "тут немає.",
        "it": "Verificate che sia cio che pensavate fosse questo file. Non "
              "c'e una correzione nel codice.",
        "en": "Check whether this is what you took the file to be. There is "
              "no code change here.",
    },
    "a11y_bp_ai_media_signed_title": {
        "uk": "Є підписані Content Credentials, не прочитані",
        "it": "Content Credentials presenti, non lette",
        "en": "Content Credentials present, unread",
    },
    "a11y_bp_ai_media_signed_found": {
        "uk": "Файл несе маніфест C2PA. Не прочитано: {value}.",
        "it": "Il file contiene un manifesto C2PA. Non letto: {value}.",
        "en": "The file carries a C2PA manifest. Not read: {value}.",
    },
    "a11y_bp_ai_media_signed_why": {
        "uk": "Підписаний маніфест є найсильнішим доказом походження, який "
              "взагалі буває, і мовчазно його пропустити означало б показати "
              "файл, що сам себе документує, як файл без документів. Прочитати "
              "підпис ця збірка не може, тож вона каже, що він є, і не вдає, "
              "що знає його зміст.",
        "it": "Un manifesto firmato e la prova di provenienza piu forte che "
              "esista, e ignorarlo in silenzio farebbe sembrare un file che si "
              "documenta da solo un file senza documenti. Questa build non sa "
              "leggere la firma, quindi dice che c'e e non finge di conoscerne "
              "il contenuto.",
        "en": "A signed manifest is the strongest provenance there is, and "
              "passing over it silently would show a file that documents "
              "itself as a file that does not. This build cannot read the "
              "signature, so it says one is there and does not pretend to "
              "know what it says.",
    },
    "a11y_bp_ai_media_signed_fix": {
        "uk": "Відкрийте файл переглядачем Content Credentials, щоб побачити "
              "підписаний ланцюг.",
        "it": "Aprite il file con un lettore di Content Credentials per vedere "
              "la catena firmata.",
        "en": "Open the file in a Content Credentials viewer to see the signed "
              "chain.",
    },
    "a11y_bp_ai_markup_artifact_title": {
        "uk": "Слід генератора в розмітці",
        "it": "Traccia del generatore nel markup",
        "en": "Generator trace left in the markup",
    },
    # The artifacts are listed as the markup tokens themselves rather than
    # described in words: a developer reading `class="claude-..."` already
    # knows what it is, and a translated noun for it would add nothing.
    "a11y_bp_ai_markup_artifact_found": {
        "uk": "Елемент <{element}> має {names} з назвою постачальника ({vendor}).",
        "it": "L'elemento <{element}> ha {names} con il nome del fornitore ({vendor}).",
        "en": "The <{element}> element carries {names}, named after a vendor ({vendor}).",
    },
    "a11y_bp_ai_markup_artifact_why": {
        "uk": "Такі імена класів і data-атрибути пишуть інтерфейси чатів, а не ваш шаблон: вони потрапляють у сторінку разом із вставленою відповіддю. Це факт про походження розмітки, а не про авторство тексту - і це не водяний знак: офіційний знак Anthropic живе у виборі слів і перевіряється лише ключем, якого немає ні в кого поза Anthropic. Клас із таким словом може належати й вашому власному коду, тому це слабкий за наслідками, але точний за фактом сигнал.",
        "it": "Questi nomi di classe e attributi data li scrivono le interfacce di chat, non il tuo template: finiscono nella pagina insieme alla risposta incollata. È un fatto sull'origine del markup, non sull'autore del testo - e non è una filigrana: il marchio ufficiale di Anthropic vive nella scelta delle parole e si verifica solo con una chiave che nessuno ha fuori da Anthropic. Una classe con quella parola può appartenere anche al tuo codice, quindi il segnale è debole per conseguenze ma esatto come fatto.",
        "en": "Class names and data attributes like these are written by chat interfaces, not by your template: they arrive in the page along with a pasted answer. It is a fact about where the markup came from, not about who wrote the words - and it is not a watermark: Anthropic's official mark lives in word choice and can only be verified with a key nobody outside Anthropic holds. A class with that word in it can equally belong to your own code, which is why this is weak in consequence and exact in fact.",
    },
    "a11y_bp_ai_markup_artifact_fix": {
        "uk": "Приберіть саме цей клас або атрибут, а не елемент: вміст лишається, зникає тільки слід. Якщо назва належить вашому власному коду, додайте її у винятки, щоб не бачити цю знахідку щоразу.",
        "it": "Rimuovi proprio quella classe o quell'attributo, non l'elemento: il contenuto resta, sparisce solo la traccia. Se il nome appartiene al tuo codice, aggiungilo alle eccezioni per non rivedere questa segnalazione ogni volta.",
        "en": "Remove that class token or attribute, not the element: the content stays, only the trace goes. If the name belongs to your own code, add it to the exceptions so the finding stops coming back.",
    },
    "a11y_bp_charset_title": {
        "uk": "Кодування сторінки не оголошено",
        "it": "Codifica della pagina non dichiarata",
        "en": "Page encoding not declared",
    },
    "a11y_bp_charset_found": {
        "uk": "У <head> немає ані <meta charset>, ані http-equiv=\"content-type\".",
        "it": "Nel <head> non c'è né <meta charset> né http-equiv=\"content-type\".",
        "en": "The <head> has neither a <meta charset> nor an http-equiv=\"content-type\".",
    },
    "a11y_bp_charset_why": {
        "uk": "Без оголошеного кодування браузер вгадує його за першими байтами і помиляється саме на тому тексті, заради якого цей інструмент існує: українські й італійські літери перетворюються на нечитабельний набір символів. Пошукова система бачить те саме сміття, тому сторінка ще й індексується зіпсованою.",
        "it": "Senza una codifica dichiarata il browser la indovina dai primi byte e sbaglia proprio sul testo per cui questo strumento esiste: le lettere ucraine e italiane diventano una sequenza illeggibile. Il motore di ricerca vede la stessa spazzatura, quindi la pagina viene anche indicizzata rovinata.",
        "en": "With no declared encoding the browser guesses from the first bytes, and it guesses wrong on exactly the text this tool exists for: Ukrainian and Italian letters turn into an unreadable run of symbols. The search engine sees the same garbage, so the page is indexed broken as well.",
    },
    "a11y_bp_charset_fix": {
        "uk": "Поставте <meta charset=\"utf-8\"> найпершим рядком у <head>, у межах перших 1024 байтів документа: далі браузер уже прийме рішення сам.",
        "it": "Metti <meta charset=\"utf-8\"> come prima riga nel <head>, entro i primi 1024 byte del documento: oltre, il browser avrà già deciso da solo.",
        "en": "Put <meta charset=\"utf-8\"> as the very first line in <head>, within the first 1024 bytes of the document: past that the browser has already decided on its own.",
    },
    "a11y_bp_doctype_title": {
        "uk": "Немає оголошення типу документа",
        "it": "Manca la dichiarazione del tipo di documento",
        "en": "No document type declaration",
    },
    "a11y_bp_doctype_found": {
        "uk": "Перед <html> немає рядка <!DOCTYPE html>.",
        "it": "Prima di <html> manca la riga <!DOCTYPE html>.",
        "en": "There is no <!DOCTYPE html> line before <html>.",
    },
    "a11y_bp_doctype_why": {
        "uk": "Без doctype браузер переходить у режим сумісності зі старими сайтами, де розміри рахуються за правилами двадцятирічної давнини. Сучасний CSS у ньому поводиться інакше, і найгірше те, що поводиться по-різному в різних браузерах - тобто помилка виглядає як випадкове розсипання макета в когось одного.",
        "it": "Senza doctype il browser passa in modalità di compatibilità con i vecchi siti, dove le dimensioni si calcolano con regole di vent'anni fa. Il CSS moderno vi si comporta diversamente e, cosa peggiore, in modo diverso da browser a browser: l'errore appare quindi come un layout che si sfalda a caso solo per qualcuno.",
        "en": "Without a doctype the browser drops into quirks mode, where sizes follow twenty-year-old rules. Modern CSS behaves differently there and, worse, differently between browsers - so the bug shows up as a layout that falls apart at random for one person only.",
    },
    "a11y_bp_doctype_fix": {
        "uk": "Додайте <!DOCTYPE html> найпершим рядком файлу, до будь-яких коментарів і порожніх рядків. Інших значень цього рядка сьогодні не потрібно.",
        "it": "Aggiungi <!DOCTYPE html> come primissima riga del file, prima di qualsiasi commento o riga vuota. Oggi non servono altri valori.",
        "en": "Add <!DOCTYPE html> as the very first line of the file, before any comments or blank lines. No other value of this line is needed today.",
    },
    "a11y_bp_inline_handlers_title": {
        "uk": "Обробник події прописаний прямо в розмітці",
        "it": "Gestore di evento scritto direttamente nel markup",
        "en": "Event handler written inline in the markup",
    },
    "a11y_bp_inline_handlers_found": {
        "uk": "Елемент <{element}> має атрибут {handler} з кодом усередині.",
        "it": "L'elemento <{element}> ha l'attributo {handler} con del codice al suo interno.",
        "en": "The <{element}> carries a {handler} attribute with code inside it.",
    },
    "a11y_bp_inline_handlers_why": {
        "uk": "Такі атрибути змушують політику безпеки вмісту дозволяти 'unsafe-inline', а це саме та зміна, після якої CSP перестає бути захистом і стає формальністю: браузер більше не може відрізнити ваш код від впровадженого. Плюс код у розмітці не проходить складання, не мінімізується і не бачиться інструментами перевірки.",
        "it": "Questi attributi costringono la Content Security Policy a consentire 'unsafe-inline', ed è proprio la modifica dopo cui la CSP smette di essere una difesa e diventa una formalità: il browser non può più distinguere il tuo codice da quello iniettato. Inoltre il codice nel markup non passa dalla build, non viene minificato e sfugge agli strumenti di analisi.",
        "en": "Such attributes force a Content Security Policy to allow 'unsafe-inline', which is the single change that turns a CSP from a defence into a formality: the browser can no longer tell your code from injected code. On top of that, code in markup skips the build, is never minified, and is invisible to your linters.",
    },
    "a11y_bp_inline_handlers_fix": {
        "uk": "Перенесіть код у скрипт і привʼяжіть його через addEventListener за селектором. Якщо інлайновий обробник лишається свідомо, дайте йому nonce або хеш у CSP, а не загальний дозвіл на весь інлайн.",
        "it": "Sposta il codice in uno script e collegalo con addEventListener tramite un selettore. Se un gestore inline resta per scelta, dagli un nonce o un hash nella CSP, non un permesso generico per tutto l'inline.",
        "en": "Move the code into a script file and attach it with addEventListener by selector. If an inline handler stays on purpose, give it a nonce or a hash in the CSP rather than a blanket allowance for all inline code.",
    },
    "a11y_bp_password_field_title": {
        "uk": "Поле пароля, яке не бачить менеджер паролів",
        "it": "Campo password che il gestore di password non riconosce",
        "en": "Password field a password manager cannot see",
    },
    "a11y_bp_password_field_found": {
        "uk": "Поле type=\"password\" має проблеми: {problems}.",
        "it": "Il campo type=\"password\" presenta i problemi: {problems}.",
        "en": "The type=\"password\" field has these problems: {problems}.",
    },
    "a11y_bp_password_field_why": {
        "uk": "Поза формою і без підказки autocomplete менеджер паролів не розпізнає поле, тому не пропонує ані зберегти, ані підставити пароль. Наслідок не технічний, а людський: люди вигадують пароль, який зможуть запам'ятати, тобто слабший, і повторюють його на інших сайтах. Заповнення вручну ще й ламає роботу з клавіатури і на мобільному.",
        "it": "Fuori da un form e senza il suggerimento autocomplete, il gestore di password non riconosce il campo e quindi non propone né di salvare né di inserire la password. La conseguenza non è tecnica ma umana: le persone inventano una password che riescono a ricordare, cioè più debole, e la riusano su altri siti. La compilazione manuale rompe anche l'uso da tastiera e da mobile.",
        "en": "Outside a form and with no autocomplete hint, a password manager does not recognise the field, so it offers neither to save nor to fill. The consequence is human rather than technical: people invent a password they can remember, which is a weaker one, and reuse it elsewhere. Typing by hand also breaks keyboard and mobile use.",
    },
    "a11y_bp_password_field_fix": {
        "uk": "Загорніть поле у <form> - навіть якщо відправка йде через JavaScript - і додайте autocomplete=\"current-password\" для входу або \"new-password\" для реєстрації і зміни пароля. Поле логіна поруч має отримати autocomplete=\"username\".",
        "it": "Racchiudi il campo in un <form>, anche se l'invio avviene via JavaScript, e aggiungi autocomplete=\"current-password\" per l'accesso o \"new-password\" per la registrazione e il cambio password. Il campo dell'utente accanto deve avere autocomplete=\"username\".",
        "en": "Wrap the field in a <form> - even when submission happens through JavaScript - and add autocomplete=\"current-password\" for sign-in or \"new-password\" for registration and password changes. The username field beside it should get autocomplete=\"username\".",
    },
    "a11y_bp_deprecated_html_title": {
        "uk": "Застарілий елемент розмітки",
        "it": "Elemento di markup obsoleto",
        "en": "Obsolete markup element",
    },
    "a11y_bp_deprecated_html_found": {
        "uk": "Знайдено <{element}>. Сучасна заміна: {replacement}.",
        "it": "Trovato <{element}>. Sostituzione moderna: {replacement}.",
        "en": "Found <{element}>. The modern replacement: {replacement}.",
    },
    "a11y_bp_deprecated_html_why": {
        "uk": "Ці теги прибрані зі стандарту, і браузери підтримують їх лише зі співчуття до старих сайтів. Підтримка не гарантована, поведінка різна, а частина з них не має жодного зрозумілого значення для програм читання з екрана. Крім того, вони змішують оформлення з вмістом, тому змінити вигляд без правки розмітки стає неможливо.",
        "it": "Questi tag sono stati rimossi dallo standard e i browser li supportano solo per compassione verso i vecchi siti. Il supporto non è garantito, il comportamento varia e alcuni non hanno alcun significato comprensibile per gli screen reader. Inoltre mescolano presentazione e contenuto, quindi cambiare l'aspetto senza toccare il markup diventa impossibile.",
        "en": "These tags were removed from the standard and browsers keep them only out of sympathy for old sites. Support is not guaranteed, behaviour varies, and several of them carry no meaning a screen reader can convey. They also mix presentation into the content, so changing the look becomes impossible without editing the markup.",
    },
    "a11y_bp_deprecated_html_fix": {
        "uk": "Замініть на {replacement}. Якщо тег лише оформлював текст, приберіть його і перенесіть вигляд у CSS; якщо він щось означав, візьміть семантичний елемент з тим самим значенням.",
        "it": "Sostituisci con {replacement}. Se il tag serviva solo a impaginare il testo, rimuovilo e sposta l'aspetto nel CSS; se aveva un significato, usa l'elemento semantico che lo esprime.",
        "en": "Replace it with {replacement}. If the tag was only styling text, drop it and move the look into CSS; if it meant something, use the semantic element that carries that meaning.",
    },
    # --- пояснення для двигунів, чий текст не наш -------------------------
    "a11y_engine_found": {
        "uk": "Знайшов {engine}, правило {rule}. Текст нижче - його власний, "
              "англійською.",
        "it": "Trovato da {engine}, regola {rule}. Il testo qui sotto è suo, "
              "in inglese.",
        "en": "Found by {engine}, rule {rule}.",
    },
    "a11y_engine_incomplete": {
        "uk": "{engine} не зміг вирішити сам і позначив це як таке, що "
              "потребує ручної перевірки. Це не обовʼязково помилка.",
        "it": "{engine} non ha potuto decidere e lo ha segnato come da "
              "verificare a mano. Non è necessariamente un errore.",
        "en": "{engine} could not decide and marked this as needing a manual "
              "check. It is not necessarily a defect.",
    },

    # --- становий прохід: наші правила, наші пояснення ---------------------
    "a11y_state:keyboard_trap_title": {
        "uk": "Клавіатурна пастка", "it": "Trappola per la tastiera",
        "en": "Keyboard trap",
    },
    "a11y_state:keyboard_trap_found": {
        "uk": "Елемент перехоплює Tab і не пропускає фокус далі.",
        "it": "L'elemento intercetta Tab e non lascia proseguire il focus.",
        "en": "The element swallows Tab and does not let focus move on.",
    },
    "a11y_state:keyboard_trap_why": {
        "uk": "Людина, яка користується лише клавіатурою, застрягає тут "
              "назавжди: вийти можна хіба що закривши вкладку. Це найважча з "
              "можливих перешкод, бо вона зупиняє не одну дію, а весь сеанс.",
        "it": "Chi usa solo la tastiera resta bloccato qui per sempre: si esce "
              "solo chiudendo la scheda. È l'ostacolo più grave possibile, "
              "perché non blocca una singola azione ma l'intera sessione.",
        "en": "Someone using only a keyboard is stuck here for good; the way "
              "out is closing the tab. This is the worst obstacle there is, "
              "because it stops not one action but the whole session.",
    },
    "a11y_state:keyboard_trap_fix": {
        "uk": "Не скасовуйте подію Tab. Якщо фокус тримається навмисно (модальне "
              "вікно), додайте вихід по Escape і повертайте фокус туди, звідки "
              "вікно відкрили.",
        "it": "Non annullare l'evento Tab. Se il focus è trattenuto di "
              "proposito (una finestra modale), aggiungi l'uscita con Escape e "
              "riporta il focus da dove la finestra è stata aperta.",
        "en": "Do not cancel the Tab event. If focus is held on purpose (a "
              "modal), add an Escape exit and return focus to whatever opened "
              "it.",
    },
    "a11y_state:focus_not_visible_title": {
        "uk": "Фокус не видно", "it": "Il focus non si vede",
        "en": "The focus ring is invisible",
    },
    "a11y_state:focus_not_visible_found": {
        "uk": "Елемент отримав фокус, але жодна його властивість не змінилась: "
              "ані обведення, ані тінь, ані колір рамки.",
        "it": "L'elemento ha ricevuto il focus ma nessuna sua proprietà è "
              "cambiata: né contorno, né ombra, né colore del bordo.",
        "en": "The element took focus but nothing about it changed: no "
              "outline, no shadow, no border colour.",
    },
    "a11y_state:focus_not_visible_why": {
        "uk": "Людина, яка ходить сторінкою з клавіатури, не бачить, де вона "
              "зараз. Сторінка формально працює, але користуватися нею "
              "доводиться навпомацки. Це найчастіша клавіатурна проблема, і "
              "статична перевірка її не бачить: `outline: none` майже завжди "
              "живе в таблиці стилів, а не в розмітці.",
        "it": "Chi naviga da tastiera non vede dove si trova. La pagina "
              "funziona formalmente, ma la si usa a tentoni. È il problema di "
              "tastiera più comune e un controllo statico non lo vede: "
              "`outline: none` sta quasi sempre nel foglio di stile, non nel "
              "markup.",
        "en": "Someone moving through the page by keyboard cannot see where "
              "they are. The page technically works, but has to be used by "
              "feel. This is the most common keyboard problem, and a static "
              "check cannot see it: `outline: none` almost always lives in a "
              "stylesheet, not in the markup.",
    },
    "a11y_state:focus_not_visible_fix": {
        "uk": "Приберіть `outline: none` або дайте заміну: `:focus-visible` з "
              "видимим обведенням чи тінню, контрастною до тла.",
        "it": "Rimuovi `outline: none` oppure dai un sostituto: "
              "`:focus-visible` con un contorno o un'ombra visibile, in "
              "contrasto con lo sfondo.",
        "en": "Remove `outline: none` or replace it: a `:focus-visible` rule "
              "with a visible outline or shadow that contrasts with the "
              "background.",
    },
    "a11y_state:focus_order_mismatch_title": {
        "uk": "Порядок фокуса не збігається з порядком читання",
        "it": "L'ordine del focus non segue l'ordine di lettura",
        "en": "Focus order does not follow reading order",
    },
    "a11y_state:focus_order_mismatch_found": {
        "uk": "Фокус кілька разів стрибає вгору сторінкою замість того, щоб "
              "рухатись донизу.",
        "it": "Il focus salta più volte verso l'alto invece di scendere.",
        "en": "Focus jumps back up the page several times instead of moving "
              "down it.",
    },
    "a11y_state:focus_order_mismatch_why": {
        "uk": "Той, хто не бачить сторінки цілком, будує її мапу з порядку "
              "обходу. Коли порядок стрибає, мапа виходить неправильною, і "
              "людина губиться там, де зряча людина просто дивиться нижче.",
        "it": "Chi non vede l'intera pagina se ne costruisce la mappa "
              "dall'ordine di attraversamento. Se l'ordine salta, la mappa "
              "esce sbagliata e la persona si perde dove una vedente "
              "guarderebbe semplicemente più in basso.",
        "en": "Someone who cannot see the whole page builds their map of it "
              "from the order they move through it. When the order jumps, the "
              "map comes out wrong, and they get lost where a sighted person "
              "would simply look further down.",
    },
    "a11y_state:focus_order_mismatch_fix": {
        "uk": "Приведіть порядок у розмітці до порядку на екрані. Не "
              "виправляйте це через `tabindex` із додатними значеннями: так "
              "проблема лише переміщується.",
        "it": "Allinea l'ordine nel markup a quello sullo schermo. Non "
              "correggerlo con `tabindex` positivi: così il problema si "
              "sposta soltanto.",
        "en": "Bring the order in the markup in line with the order on "
              "screen. Do not patch it with positive `tabindex` values: that "
              "only moves the problem.",
    },
    "a11y_state:hover_only_content_title": {
        "uk": "Вміст зʼявляється лише під мишею",
        "it": "Contenuto visibile solo al passaggio del mouse",
        "en": "Content that only appears on hover",
    },
    "a11y_state:hover_only_content_found": {
        "uk": "Прихований блок відкривається наведенням, але не має "
              "рівноцінного відкриття з клавіатури.",
        "it": "Un blocco nascosto si apre al passaggio del mouse ma non ha "
              "un equivalente da tastiera.",
        "en": "A hidden block opens on hover but has no keyboard equivalent.",
    },
    "a11y_state:hover_only_content_why": {
        "uk": "Без миші цього вмісту не існує зовсім. Якщо там пункти меню, "
              "частина сайту стає недосяжною - і не лише для клавіатури, а й "
              "для сенсорного екрана, де наведення немає.",
        "it": "Senza mouse quel contenuto non esiste affatto. Se contiene voci "
              "di menu, una parte del sito diventa irraggiungibile: non solo "
              "da tastiera, ma anche su touch, dove il passaggio del mouse non "
              "esiste.",
        "en": "Without a mouse that content does not exist at all. If it holds "
              "menu items, part of the site becomes unreachable - not only "
              "from a keyboard but on touch, where there is no hover.",
    },
    "a11y_state:hover_only_content_fix": {
        "uk": "Відкривайте те саме на `:focus-within` або кнопкою з "
              "`aria-expanded`, яку можна натиснути з клавіатури.",
        "it": "Apri lo stesso contenuto con `:focus-within` o con un pulsante "
              "con `aria-expanded` azionabile da tastiera.",
        "en": "Open the same content on `:focus-within`, or from a button "
              "with `aria-expanded` that a keyboard can operate.",
    },
    "a11y_state:no_skip_link_title": {
        "uk": "Немає посилання «перейти до вмісту»",
        "it": "Manca il link «vai al contenuto»",
        "en": "No skip link",
    },
    "a11y_state:no_skip_link_found": {
        "uk": "У шапці й навігації {navLinks} посилань, а способу оминути їх "
              "немає.",
        "it": "Nell'intestazione e nella navigazione ci sono {navLinks} link e "
              "non c'è modo di saltarli.",
        "en": "The header and navigation hold {navLinks} links, and there is "
              "no way past them.",
    },
    "a11y_state:no_skip_link_why": {
        "uk": "Кожен візит із клавіатури починається з проходу через усе меню "
              "наново. На кожній сторінці. Це не помилка, а щоденний податок "
              "на користування сайтом.",
        "it": "Ogni visita da tastiera comincia riattraversando tutto il menu. "
              "Su ogni pagina. Non è un errore, è una tassa quotidiana "
              "sull'uso del sito.",
        "en": "Every keyboard visit starts by tabbing through the whole menu "
              "again. On every page. It is not an error so much as a daily tax "
              "on using the site.",
    },
    "a11y_state:no_skip_link_fix": {
        "uk": "Додайте першим у `<body>` посилання на якір основного вмісту. "
              "Воно може бути прихованим, поки не отримає фокус.",
        "it": "Aggiungi come primo elemento di `<body>` un link all'ancora del "
              "contenuto principale. Può restare nascosto finché non riceve il "
              "focus.",
        "en": "Add a link to the main content anchor as the first thing in "
              "`<body>`. It can stay hidden until it takes focus.",
    },
    "a11y_state:focus_outside_viewport_title": {
        "uk": "Фокус іде за межі видимої області",
        "it": "Il focus finisce fuori dall'area visibile",
        "en": "Focus lands outside the visible area",
    },
    "a11y_state:focus_outside_viewport_found": {
        "uk": "Елемент отримує фокус, перебуваючи поза екраном.",
        "it": "L'elemento riceve il focus mentre si trova fuori schermo.",
        "en": "The element takes focus while it is off screen.",
    },
    "a11y_state:focus_outside_viewport_why": {
        "uk": "Фокус зникає з очей: людина натискає Tab і не бачить нічого "
              "нового, хоча наступне натискання вже стосується елемента, якого "
              "вона не бачила. Так зазвичай поводяться закриті меню, які "
              "прибрали зсувом, а не з дерева фокуса.",
        "it": "Il focus sparisce dalla vista: si preme Tab e non cambia nulla "
              "di visibile, mentre la pressione successiva agisce già su un "
              "elemento mai visto. È il comportamento tipico dei menu chiusi "
              "spostati fuori schermo invece che tolti dall'ordine di focus.",
        "en": "Focus disappears from sight: the user presses Tab, sees nothing "
              "change, and their next keystroke already acts on an element "
              "they never saw. This is what closed menus do when they are "
              "moved off screen instead of taken out of the focus order.",
    },
    "a11y_state:focus_outside_viewport_fix": {
        "uk": "Прибирайте приховане з порядку фокуса: `display: none`, "
              "`visibility: hidden` або `inert` замість зсуву за край екрана.",
        "it": "Togli ciò che è nascosto dall'ordine di focus: `display: none`, "
              "`visibility: hidden` o `inert` invece di spostarlo oltre il "
              "bordo.",
        "en": "Take hidden things out of the focus order: `display: none`, "
              "`visibility: hidden` or `inert` rather than moving them past "
              "the edge.",
    },
    "a11y_state:state_pass_title": {
        "uk": "Перевірка станів не завершилась",
        "it": "Il controllo degli stati non è terminato",
        "en": "The state pass did not finish",
    },
    "a11y_state:state_pass_found": {
        "uk": "Прохід по станах сторінки впав: {engine_error}",
        "it": "Il passaggio sugli stati della pagina è fallito: {engine_error}",
        "en": "The pass over the page's states failed: {engine_error}",
    },
    "a11y_state:state_pass_why": {
        "uk": "Перевірки фокуса, клавіатурних пасток і вмісту під мишею для "
              "цієї сторінки не виконано, тож їхня відсутність у списку нічого "
              "не означає.",
        "it": "I controlli su focus, trappole per la tastiera e contenuto al "
              "passaggio del mouse non sono stati eseguiti per questa pagina: "
              "la loro assenza dall'elenco non significa nulla.",
        "en": "The focus, keyboard-trap and hover checks did not run for this "
              "page, so their absence from the list means nothing.",
    },
    "a11y_state:state_pass_fix": {
        "uk": "Спробуйте ще раз; якщо повторюється - сторінка, ймовірно, "
              "перевизначає щось, на що спирається перевірка.",
        "it": "Riprova; se si ripete, la pagina probabilmente ridefinisce "
              "qualcosa su cui il controllo si appoggia.",
        "en": "Try again; if it repeats, the page is probably overriding "
              "something the check relies on.",
    },
    # --- нові правила accessibility (2026-08-20) ---
    "a11y_landmark_regions_title": {
        "uk": "Сторінка без основної області (landmark)",
        "it": "Pagina senza area principale (landmark)",
        "en": "Page without main landmark region",
    },
    "a11y_landmark_regions_found": {
        "uk": "На сторінці немає <main> або ARIA-ролі main. Знайдені області: {found}.",
        "it": "La pagina non ha <main> né un ruolo ARIA main. Aree trovate: {found}.",
        "en": "The page has no <main> or ARIA role main. Found regions: {found}.",
    },
    "a11y_landmark_regions_why": {
        "uk": "Програма читання з екрана не має способу перейти до основного вмісту: користувач змушений табулювати через всю навігацію на кожній сторінці. Landmark-області - це те, як незряча людина «бачить» структуру сторінки.",
        "it": "Lo screen reader non ha un modo per saltare al contenuto principale: l'utente deve tabulare attraverso tutta la navigazione su ogni pagina. Le aree landmark sono il modo in cui una persona non vedente «vede» la struttura della pagina.",
        "en": "A screen reader has no way to jump to the main content: the user must tab through the entire navigation on every page. Landmark regions are how a blind person «sees» the page structure.",
    },
    "a11y_landmark_regions_fix": {
        "uk": "Обгорніть основний вміст сторінки у <main>. Навігацію обгорніть у <nav>, шапку у <header>, підвал у <footer>. Це не змінює вигляд, але дає програмі читання карту сторінки.",
        "it": "Racchiudi il contenuto principale in <main>. Avvolgi la navigazione in <nav>, l'intestazione in <header>, il piè di pagina in <footer>. Non cambia l'aspetto ma dà allo screen reader una mappa della pagina.",
        "en": "Wrap the main content in <main>. Wrap navigation in <nav>, the header in <header>, the footer in <footer>. This does not change the look but gives the screen reader a map of the page.",
    },
    "a11y_skip_link_title": {
        "uk": "Немає посилання «перейти до вмісту»",
        "it": "Manca il link «vai al contenuto»",
        "en": "No «skip to content» link",
    },
    "a11y_skip_link_found": {
        "uk": "Перші 10 посилань на сторінці не ведуть до якоря на основному вмісті.",
        "it": "I primi 10 link sulla pagina non portano a un'ancora sul contenuto principale.",
        "en": "The first 10 links on the page do not point to an anchor on the main content.",
    },
    "a11y_skip_link_why": {
        "uk": "Клавіатурний користувач на кожній сторінці змушений проходити через всю навігацію, перш ніж дістатися до вмісту. Це 10-20 натискань Tab на кожному переході, і для людини з обмеженою моторикою це реальна перешкода.",
        "it": "Un utente da tastiera è costretto a passare attraverso tutta la navigazione prima di raggiungere il contenuto su ogni pagina. Sono 10-20 pressioni di Tab a ogni transizione, e per chi ha limitazioni motorie è un ostacolo reale.",
        "en": "A keyboard user must tab through the entire navigation before reaching the content on every page. That is 10-20 Tab presses per transition, and for someone with limited motor ability it is a real barrier.",
    },
    "a11y_skip_link_fix": {
        "uk": "Додайте першим елементом у <body> посилання <a href=\"#main\" class=\"skip-link\">Перейти до вмісту</a>, яке веде до id основного блоку. Воно може бути прихованим і з'являтися лише при фокусі (Tab).",
        "it": "Aggiungi come primo elemento in <body> un link <a href=\"#main\" class=\"skip-link\">Vai al contenuto</a> che punta all'id del blocco principale. Può essere nascosto e comparire solo al focus (Tab).",
        "en": "Add as the first element in <body> a link <a href=\"#main\" class=\"skip-link\">Skip to content</a> pointing to the main block's id. It can be hidden and appear only on focus (Tab).",
    },
    "a11y_form_error_message_title": {
        "uk": "Поле з помилкою без опису помилки",
        "it": "Campo con errore senza descrizione dell'errore",
        "en": "Field with error but no error description",
    },
    "a11y_form_error_message_found": {
        "uk": "Поле <{element}> має aria-invalid=\"true\", але не має aria-describedby або aria-errormessage.",
        "it": "Il campo <{element}> ha aria-invalid=\"true\" ma non ha aria-describedby né aria-errormessage.",
        "en": "The <{element}> field has aria-invalid=\"true\" but no aria-describedby or aria-errormessage.",
    },
    "a11y_form_error_message_why": {
        "uk": "Програма читання з екрана оголосить «неправильне поле», але не скаже що саме не так. Користувач знає що помилився, але не знає як виправити, і змушений вгадувати або просити допомоги зрячої людини.",
        "it": "Lo screen reader annuncerà «campo non valido» ma non dirà cosa c'è di sbagliato. L'utente sa di aver sbagliato ma non come correggere, e deve indovinare o chiedere aiuto a una persona vedente.",
        "en": "A screen reader will announce «invalid field» but will not say what is wrong. The user knows they made a mistake but not how to fix it, and must either guess or ask a sighted person for help.",
    },
    "a11y_form_error_message_fix": {
        "uk": "Додайте до поля aria-describedby=\"error-id\", де error-id - id елемента з текстом помилки. Або використовуйте aria-errormessage=\"error-id\" для явного зв'язку.",
        "it": "Aggiungi al campo aria-describedby=\"error-id\", dove error-id è l'id dell'elemento con il testo dell'errore. Oppure usa aria-errormessage=\"error-id\" per un collegamento esplicito.",
        "en": "Add to the field aria-describedby=\"error-id\" where error-id is the id of the element with the error text. Or use aria-errormessage=\"error-id\" for an explicit link.",
    },
    "a11y_table_scope_title": {
        "uk": "Заголовки таблиці без атрибута scope",
        "it": "Intestazioni di tabella senza attributo scope",
        "en": "Table headers without scope attribute",
    },
    "a11y_table_scope_found": {
        "uk": "Таблиця має {th_count} заголовків <th>, але жоден не має scope. {rows} рядків.",
        "it": "La tabella ha {th_count} intestazioni <th> ma nessuna ha scope. {rows} righe.",
        "en": "The table has {th_count} <th> headers but none has scope. {rows} rows.",
    },
    "a11y_table_scope_why": {
        "uk": "Без scope програма читання з екрана не знає чи заголовок стовпця, чи рядка. У складній таблиці це означає, що користувач чує значення «42» без розуміння до якого стовпця воно належить.",
        "it": "Senza scope lo screen reader non sa se l'intestazione è di colonna o di riga. In una tabella complessa significa che l'utente sente il valore «42» senza sapere a quale colonna appartiene.",
        "en": "Without scope a screen reader does not know if the header is for a column or a row. In a complex table this means the user hears the value «42» without knowing which column it belongs to.",
    },
    "a11y_table_scope_fix": {
        "uk": "Додайте до заголовків стовпців scope=\"col\", до заголовків рядків - scope=\"row\". Це одна мить і миттєво робить таблицю зрозумілою для програми читання.",
        "it": "Aggiungi alle intestazioni di colonna scope=\"col\" e alle intestazioni di riga scope=\"row\". È un attimo e rende la tabella immediatamente comprensibile allo screen reader.",
        "en": "Add scope=\"col\" to column headers and scope=\"row\" to row headers. It takes a moment and instantly makes the table understandable to a screen reader.",
    },
    "a11y_hreflang_links_title": {
        "uk": "Мультимовний сайт без hreflang",
        "it": "Sito multilingua senza hreflang",
        "en": "Multilingual site without hreflang",
    },
    "a11y_hreflang_links_found": {
        "uk": "Сторінка має мову {lang} і посилання на іншомовні версії, але немає hreflang-тегів у <head>.",
        "it": "La pagina ha la lingua {lang} e link a versioni in altre lingue, ma non ci sono tag hreflang nel <head>.",
        "en": "The page has language {lang} and links to other-language versions, but no hreflang tags in <head>.",
    },
    "a11y_hreflang_links_why": {
        "uk": "Пошуковик не знає яка версія сторінки для якої мови, тому може показати українську сторінку італійському користувачу або навпаки. Це псує досвід і знижує рейтинг у локальному пошуку.",
        "it": "Il motore di ricerca non sa quale versione della pagina è per quale lingua, quindi può mostrare la pagina ucraina a un utente italiano o viceversa. Questo rovina l'esperienza e abbassa il ranking nella ricerca locale.",
        "en": "The search engine does not know which version of the page is for which language, so it may show the Ukrainian page to an Italian user or vice versa. This ruins the experience and lowers local search ranking.",
    },
    "a11y_hreflang_links_fix": {
        "uk": "Додайте у <head> посилання <link rel=\"alternate\" hreflang=\"uk\" href=\"...\" /> для кожної мовної версії. Також додайте hreflang=\"x-default\" для версії за замовчуванням.",
        "it": "Aggiungi nel <head> i link <link rel=\"alternate\" hreflang=\"uk\" href=\"...\" /> per ogni versione linguistica. Aggiungi anche hreflang=\"x-default\" per la versione predefinita.",
        "en": "Add to <head> links <link rel=\"alternate\" hreflang=\"uk\" href=\"...\" /> for each language version. Also add hreflang=\"x-default\" for the default version.",
    },
    "a11y_breadcrumb_markup_title": {
        "uk": "Хлібні крихти поза семантикою",
        "it": "Breadcrumb fuori dalla semantica",
        "en": "Breadcrumb outside semantic markup",
    },
    "a11y_breadcrumb_markup_found": {
        "uk": "Елемент з класом «breadcrumb» або «breadcrumbs» не обгорнутий у <nav>.",
        "it": "L'elemento con classe «breadcrumb» o «breadcrumbs» non è racchiuso in <nav>.",
        "en": "An element with class «breadcrumb» or «breadcrumbs» is not wrapped in <nav>.",
    },
    "a11y_breadcrumb_markup_why": {
        "uk": "Програма читання з екрана не розпізнає цей блок як навігацію, тому не пропонує його як landmark і не оголошує його призначення. Користувач бачить список посилань, але не знає що це шлях по сайту.",
        "it": "Lo screen reader non riconosce questo blocco come navigazione, quindi non lo offre come landmark e non ne annuncia lo scopo. L'utente vede un elenco di link ma non sa che è un percorso nel sito.",
        "en": "A screen reader does not recognise this block as navigation, so it does not offer it as a landmark and does not announce its purpose. The user sees a list of links but does not know it is a path through the site.",
    },
    "a11y_breadcrumb_markup_fix": {
        "uk": "Обгорніть хлібні крихти у <nav aria-label=\"breadcrumb\"> зі списком <ol>. Це не змінює вигляд, але дає програмі читання розуміння що це таке.",
        "it": "Racchiudi il breadcrumb in <nav aria-label=\"breadcrumb\"> con una lista <ol>. Non cambia l'aspetto ma dà allo screen reader la comprensione di cosa sia.",
        "en": "Wrap the breadcrumb in <nav aria-label=\"breadcrumb\"> with an <ol> list. This does not change the look but gives the screen reader understanding of what it is.",
    },
    "a11y_language_change_title": {
        "uk": "Іншомовний текст без атрибута мови",
        "it": "Testo in altra lingua senza attributo lingua",
        "en": "Foreign-language text without language attribute",
    },
    "a11y_language_change_found": {
        "uk": "Текст іншою мовою ({detected_script}) всередині сторінки мовою {page_lang} не має атрибута lang.",
        "it": "Testo in un'altra lingua ({detected_script}) dentro una pagina in {page_lang} non ha l'attributo lang.",
        "en": "Text in another language ({detected_script}) inside a {page_lang} page has no lang attribute.",
    },
    "a11y_language_change_why": {
        "uk": "Програма читання з екрана вимовляє іншомовний текст з вимовою мови сторінки. Українське слово «привіт» в англійській сторінці буде прочитане як набір англійських літер, і навпаки. Це робить текст незрозумілим.",
        "it": "Lo screen reader pronuncia il testo straniero con la pronuncia della lingua della pagina. La parola ucraina «привіт» in una pagina inglese verrà letta come un insieme di lettere inglesi, e viceversa. Questo rende il testo incomprensibile.",
        "en": "A screen reader pronounces foreign text with the page language's pronunciation. The Ukrainian word «привіт» in an English page will be read as a sequence of English letters, and vice versa. This makes the text unintelligible.",
    },
    "a11y_language_change_fix": {
        "uk": "Додайте до елемента з іншомовним текстом атрибут lang=\"{suggested_lang}\". Наприклад: <span lang=\"uk\">Привіт</span>.",
        "it": "Aggiungi all'elemento con il testo straniero l'attributo lang=\"{suggested_lang}\". Ad esempio: <span lang=\"uk\">Привіт</span>.",
        "en": "Add to the element with foreign text the attribute lang=\"{suggested_lang}\". For example: <span lang=\"uk\">Привіт</span>.",
    },
    "a11y_abbreviation_expansion_title": {
        "uk": "Абревіатура без розшифровки",
        "it": "Abbreviazione senza espansione",
        "en": "Abbreviation without expansion",
    },
    "a11y_abbreviation_expansion_found": {
        "uk": "Абревіатура «{abbreviation}» не обгорнута у <abbr> з атрибутом title.",
        "it": "L'abbreviazione «{abbreviation}» non è racchiusa in <abbr> con attributo title.",
        "en": "The abbreviation «{abbreviation}» is not wrapped in <abbr> with a title attribute.",
    },
    "a11y_abbreviation_expansion_why": {
        "uk": "Програма читання з екрана не може правильно вимовити абревіатуру без розшифровки. «WCAG» буде прочитане як «вкаг» або «дабл-ю-сі-е-джі», і жоден варіант не дає зрозуміти що це за стандарт.",
        "it": "Lo screen reader non può pronunciare correttamente un'abbreviazione senza espansione. «WCAG» verrà letto come «вкаг» o «doppio-vu-ci-a-gi», e nessuna delle due opzioni fa capire che standard sia.",
        "en": "A screen reader cannot pronounce an abbreviation correctly without expansion. «WCAG» will be read as «вкаг» or «double-u-see-ay-gee», and neither option makes clear what standard it is.",
    },
    "a11y_abbreviation_expansion_fix": {
        "uk": "Обгорніть абревіатуру у <abbr title=\"Повна назва\">{abbreviation}</abbr>. При першому використанні на сторінці краще написати повну назву з абревіатурою в дужках.",
        "it": "Racchiudi l'abbreviazione in <abbr title=\"Nome completo\">{abbreviation}</abbr>. Al primo uso nella pagina è meglio scrivere il nome completo con l'abbreviazione tra parentesi.",
        "en": "Wrap the abbreviation in <abbr title=\"Full name\">{abbreviation}</abbr>. On first use on the page it is better to write the full name with the abbreviation in parentheses.",
    },
    # --- нові правила performance (2026-08-20) ---
    "a11y_image_modern_format_title": {
        "uk": "Зображення у застарілому форматі",
        "it": "Immagine in formato obsoleto",
        "en": "Image in legacy format",
    },
    "a11y_image_modern_format_found": {
        "uk": "Зображення <img src=\"{src}\"> у форматі PNG/JPG без srcset.",
        "it": "L'immagine <img src=\"{src}\"> è in formato PNG/JPG senza srcset.",
        "en": "The image <img src=\"{src}\"> is in PNG/JPG format without srcset.",
    },
    "a11y_image_modern_format_why": {
        "uk": "WebP і AVIF стискають зображення на 25-50% краще за PNG/JPG при тій самій якості. Без srcset браузер не може обрати оптимальний розмір для пристрою, тому мобільний телефон завантажує зображення для десктопу.",
        "it": "WebP e AVIF comprimono le immagini del 25-50% meglio di PNG/JPG alla stessa qualità. Senza srcset il browser non può scegliere la dimensione ottimale per il dispositivo, quindi un telefono scarica l'immagine per desktop.",
        "en": "WebP and AVIF compress images 25-50% better than PNG/JPG at the same quality. Without srcset the browser cannot choose the optimal size for the device, so a phone downloads the desktop image.",
    },
    "a11y_image_modern_format_fix": {
        "uk": "Конвертуйте зображення у WebP або AVIF і додайте srcset з кількома розмірами. Сучасні інструменти збірки роблять це автоматично.",
        "it": "Converti le immagini in WebP o AVIF e aggiungi srcset con più dimensioni. Gli strumenti di build moderni lo fanno automaticamente.",
        "en": "Convert images to WebP or AVIF and add srcset with multiple sizes. Modern build tools do this automatically.",
    },
    "a11y_needs_browser": {
        "uk": "Часткова перевірка: без запуску браузера видно лише те, що є в самій розмітці. Решту треба звірити на живій сторінці.",
        "it": "Verifica parziale: senza eseguire un browser si vede solo ciò che è nel markup. Il resto va controllato sulla pagina reale.",
        "en": "Partial check: without running a browser only what is in the markup is visible. The rest needs checking on the live page.",
    },
    "a11y_rule_error": {
        "uk": "Правило {rule} впало на цьому документі",
        "it": "La regola {rule} è fallita su questo documento",
        "en": "Rule {rule} failed on this document",
    },
    "a11y_rule_error_title": {
        "uk": "Правило {rule} впало",
        "it": "La regola {rule} è fallita",
        "en": "Rule {rule} failed",
    },
    "a11y_summary": {
        "uk": "Критичних {critical}, серйозних {serious}, помірних {moderate}, дрібних {minor} на {documents} {documents_noun}",
        "it": "Critici {critical}, seri {serious}, moderati {moderate}, minori {minor} su {documents} {documents_noun}",
        "en": "{critical} critical, {serious} serious, {moderate} moderate, {minor} minor across {documents} {documents_noun}",
    },
    "severity_critical": {"uk": "критично", "it": "critico", "en": "critical"},
    "severity_serious": {"uk": "серйозно", "it": "serio", "en": "serious"},
    "severity_moderate": {"uk": "помірно", "it": "moderato", "en": "moderate"},
    "severity_minor": {"uk": "дрібно", "it": "minore", "en": "minor"},
}


def t(key: str, lang: str = "uk", **kwargs) -> str:
    entry = _STRINGS.get(key)
    if entry is None:
        return key
    template = entry.get(lang) or entry.get("en") or key
    return template.format(**kwargs) if kwargs else template


def plural(n: int, lang: str, one: str, few: str, many: str | None = None) -> str:
    """The noun form that agrees with `n`, in whichever of the three
    languages the interface is showing.

    Ukrainian needs all three forms - "1 документ", "2 документи",
    "5 документів" - and the well-known exception that 11-14 take the
    "many" form even though they end in 1-4 (`11 документів`, not
    `11 документ`). Italian and English only distinguish one from the rest,
    so `few` is what they use whenever `n != 1`; `many` exists only for the
    languages that need a third form; a caller that also has no need for a
    third form (a case where "few" and "many" are the same word, such as
    `на 2 документах` and `на 5 документах`) can simply pass the same string
    as both, and the entire calculation still runs.
    """
    if lang != "uk":
        return one if n == 1 else few
    many = many if many is not None else few
    if n % 100 in (11, 12, 13, 14):
        return many
    if n % 10 == 1:
        return one
    if n % 10 in (2, 3, 4):
        return few
    return many
