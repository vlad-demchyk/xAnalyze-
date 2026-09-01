"""A local, language-aware heuristic detector.

IMPORTANT — read this before trusting the output:
There is no reliable way to prove arbitrary text was AI-generated. This
detector combines several weak, well-known signals (stylistic uniformity,
lexical diversity, em-dash overuse, "not just X but Y"-style structural
patterns, and lists of words/phrases large language models reach for far
more often than typical human writers) into a single 0..1 score. It WILL
misfire on formal human writing (which is often uniform and cliché-heavy
too) and it WILL miss heavily-edited AI text. Treat every flagged span as
"worth a human look", never as a verdict.

Works fully offline — no API key, no network call.

Word/phrase lists compiled from public write-ups on AI-writing "tells"
(August 2026): Wikipedia's "Signs of AI writing" essay, Grammarly's
"Common Words and Phrases in AI-Generated Text", useaiwriter.com's
"300+ AI Words and Phrases to Avoid", oliviacal.com's "How to Spot AI
Writing Tells", theinweb.media's Ukrainian AI-marker word list, and
fastweb.it's Italian ChatGPT-tell word list. These are crowd-sourced
observations, not a scientific ground truth — extend/prune freely for
your own content.
"""
from __future__ import annotations

import re
import statistics

from models import TextBlock, TextSpan, score_to_confidence
from abbreviations import find_word_before_period, is_abbreviation
from lang_detect import guess_language_safe
from .base import Detector
from .factory import DetectorFactory

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")
_WORD_RE = re.compile(r"[\w'’-]+", re.UNICODE)
_EM_DASH_RE = re.compile(r"[—–]")

# Single words + short phrases large language models reach for far more
# often than typical human writers, grouped by language. Matched with word
# boundaries (case-insensitive), so short items don't false-positive inside
# unrelated longer words. Not exhaustive — extend freely.
#
# **But not by eye.** Audited 2026-08-31 against `corpus/prose.jsonl`, human
# paragraphs about the subjects a scan is actually pointed at - tourism,
# software, usability, marketing.
#
# Six of those paragraphs were being reported, one phrase each: `nuove
# possibilità` and `integrazione` (it), `additionally,` (en), `в епоху`,
# `крім того,` and `феномен` (uk). Eleven more entries matched that human
# text without pushing a paragraph over the line, and each of them caught no
# more positives than it cost: `scalable`, `dynamic`, `holistic`, `bandwidth`
# (en), `efficienza`, `efficiente`, `fondamentale`, `tuttavia,`, `sempre più
# spesso`, `punto di svolta` (it), `у підсумку,` (uk).
#
# All seventeen removed. Held-out recall did not move - en 11/20, it 4/11,
# uk 10/14 before and after - and false alarms on that prose went **6 to 0**.
#
# The pattern is worth naming, because the list invites repeating it: an
# ordinary word of the register a page is written in is not a marker of who
# wrote it. `efficienza` is what an Italian article about productivity is
# made of. A candidate phrase belongs here only after it has been counted on
# both sides.
#
# **Audited again 2026-08-31 against `corpus/promotional.jsonl`** - 466 human
# travel-guide paragraphs from dated Wikivoyage revisions, which is the first
# time this project had human writing in the register a scan is pointed at.
# The encyclopedic yardstick could not see these: four paragraphs crossed the
# line, three of them on one word each - `un vero e proprio` (it),
# `exceptional`, `innovative` (en) - and the fourth on the Italian structural
# pattern below. Counted on both sides first: `un vero e proprio` and
# `exceptional` caught **no** corpus positive at all, and `innovative` caught
# two that still cross without it. All three removed; held-out recall
# unchanged at en 11/20, it 4/11, uk 10/14, and false alarms on that register
# went **4 to 0**.
CLICHE_PHRASES: dict[str, list[str]] = {
    "en": [
        # padding / hedging openers
        "it's important to note", "it is important to note",
        "it is worth mentioning", "it should be noted that",
        # Added 2026-08-31 by the same audit that retired seventeen entries.
        # The hand-written AI sample in `tests/test_heuristic_detector.py`
        # contains six constructions of this kind and the list held **none**
        # of them - it was crossing the threshold on three adjacent
        # adjectives (`comprehensive`, `robust`, `scalable`) instead, which
        # is why retiring one adjective dropped it. Each of these was counted
        # against 985 human entries first: zero hits.
        "it is worth noting", "delves",
        "the intricacies of", "when it comes to", "first and foremost",
        "leverage the power of", "in terms of best practices",
        "there are several key", "has evolved significantly",
        "it is important to understand",
        "it is essential to understand", "one must consider",
        "generally speaking", "broadly speaking", "to some extent", "arguably",
        # temporal / scene-setting openers
        "in today's fast-paced world", "in today's digital age",
        "in the era of", "in a world where", "in this day and age",
        "in the modern era", "in the ever-evolving landscape",
        # transitions overused as sentence openers
        "furthermore,", "moreover,", "nevertheless,",
        "consequently,", "subsequently,", "that being said", "at its core",
        # summary / closing clichés
        "in conclusion", "to summarize", "in summary", "to put it simply",
        "a key takeaway is", "from a broader perspective",
        # engagement hooks
        "let's dive in", "let's explore", "let's unpack", "buckle up",
        "stay tuned", "here's the deal", "picture this", "imagine if",
        "what if i told you",
        # marketing verbs / buzz phrases
        "unlock the potential", "unlock your potential", "seamless experience",
        "look no further", "elevate your", "unleash the power", "game-changer",
        "at the end of the day", "boasts a", "plethora of",
        "navigate the complexities", "a testament to", "whether you're",
        "dive into the world of", "stand the test of time",
        "in the realm of", "shed light on", "cutting-edge",
        # business clichés
        "synergy", "paradigm shift", "low-hanging fruit", "move the needle",
        "boil the ocean", "circle back", "deep dive", "touch base",
        "value-add", "win-win",
        # structural clichés ("No X. No Y. Just Z." is a regex in
        # STRUCTURAL_PATTERNS — a literal here could never match real text)
        "is the new", "in the world of",
        # product and interface copy. A separate register from the article
        # prose the rest of this list was built for, and the one this tool is
        # actually pointed at: landing pages, onboarding, empty states. The
        # entries are phrases rather than words on purpose - a phrase this
        # specific is a register, while the adjective inside it is just an
        # adjective.
        "comprehensive solution", "all your needs", "all-in-one solution",
        "empowering teams", "empowering you to", "empowers you to",
        "seamlessly integrate", "seamlessly integrates", "seamless integration",
        "intuitive interface", "user-friendly interface", "in just a few clicks",
        "in a matter of minutes", "get started in minutes",
        "at the core of everything", "everything you need in one place",
        "join thousands of", "trusted by thousands", "satisfied users",
        "say goodbye to", "designed with you in mind", "built from the ground up",
        "the way it should be",
        "so you can focus on what matters", "focus on what truly matters",
        "we believe that", "our mission is simple", "never looked back",
        "whatever you throw at it", "it just works", "and much more",
        "powerful yet simple", "simple yet powerful",
        "fast-paced digital", "digital landscape", "ever-changing landscape",
        "unlock the full potential", "full potential of your",
        "streamline your workflow", "streamline your workflows",
        "bridges the gap between", "not just about", "modern professional",
        # The vendor register of 2026 marketing copy, added 2026-08-27 as the
        # English side of the Italian entries below. Every one is a phrase, not
        # a word: "robust" is an ordinary adjective and "robust infrastructure"
        # is a sales pitch, and the phrase is what the tool is pointed at.
        "actionable insights", "enterprise-grade", "digital transformation",
        "end-to-end solution", "of all sizes", "grows with your business",
        "adapts to your needs", "every aspect of your", "democratize access",
        "robust infrastructure", "harness the power",
        # single overused words
        "delve", "underscore", "pivotal", "realm", "harness", "illuminate",
        "facilitate", "refine", "bolster", "differentiate", "streamline",
        "revolutionize", "transformative", "seamless",
        "comprehensive", "robust", "stellar",
        "unparalleled", "intricate", "nuanced",
        "paramount", "formidable", "nimble", "supercharge", "turbocharge",
        "amplify", "embark", "uncover", "unveil", "tailor", "hone",
        "foster", "myriad", "countless", "innumerable", "substantial",
        "testament", "tapestry", "indelible", "invaluable", "meticulous",
        "vibrant",
    ],
    "uk": [
        # фрази-кліше
        "у сучасному світі", "не є винятком", "варто зазначити",
        "важливо підкреслити", "зануримося", "розкрити потенціал",
        "розкрийте потенціал", "на завершення", "підсумовуючи",
        "більше того,", "безсумнівно", "це свідчить про",
        "надзвичайно важливо", "широкий спектр", "справжня знахідка",
        "ідеальне рішення", "у світі, де", "незалежно від того",
        "з кожним днем", "перш за все,", "невід'ємна частина",
        "інформаційний ландшафт", "цифровий контент", "справжній феномен",
        "розумний вибір", "оптимальне рішення", "потреби сучасної аудиторії",
        "інноваційні рішення", "максимальна ефективність",
        "більшість користувачів", "ось деякі з них", "особливо корисно",
        # продуктова й інтерфейсна копія - той регістр, на який цей інструмент
        # і спрямований. Фрази, а не слова: фраза такої точності є регістром,
        # тоді як прикметник у ній є просто прикметником.
        "комплексне рішення", "для всіх ваших", "все в одному",
        "даючи змогу", "дозволяючи вам", "безшовно інтегру",
        "інтуїтивний інтерфейс", "зручний інтерфейс", "у кілька кліків",
        "за кілька хвилин", "почати роботу за", "основою всього, що ми",
        "все, що вам потрібно", "приєднуйтесь до тисяч", "задоволених користувачів",
        "забудьте про", "створено з думкою про", "ми переконані, що",
        "наша мета проста", "і багато іншого", "просте й водночас",
        "динамічному цифровому", "цифровому середовищі",
        "розкрийте повний потенціал", "повний потенціал",
        "оптимізувати робочі процеси", "оптимізували роботу",
        "не просто про", "сучасного професіонала", "передовому ai",
        "передові технології", "потужні технології",
        # Доповнення до паритету з англійським списком (2026-08-20). Складене
        # як дзеркало наявних англійських записів, а не з корпусу: список,
        # дописаний із текстів, на яких його ж і міряють, вимірює память.
        # Свідомо НЕ додані загальні сполучники ("отже,", "таким чином,") і
        # звичайні слова на кшталт "надійний" чи "ключовий": для української
        # немає людського пулу, тож precision не міряється, і ціна хибного
        # спрацювання тут вища за ціну пропуску.
        # хеджування і зачини
        "варто зауважити", "слід зазначити", "важливо зазначити", "необхідно розуміти",
        "загалом кажучи", "певною мірою",
        # часові зачини
        "у сучасному цифровому", "у наш час", "сьогодні, коли",
        "у світі, що швидко змінюється", "дедалі більше",
        # підсумки
        "підсумовуючи вищесказане", "одним словом,",
        # гачки уваги
        "розберімося", "уявіть собі", "а що, якщо", "залишайтеся з нами",
        "давайте розглянемо", "давайте зануримось",
        # маркетингові звороти
        "не шукайте далі", "вивільніть потенціал", "нові можливості",
        "справжня революція", "проривне рішення", "на новий рівень",
        "гнучке рішення", "запорука успіху", "ключ до успіху",
        "низка переваг", "чимало переваг", "широкий вибір",
        # продуктова й інтерфейсна копія
        "справлятися з будь-яким", "будь-яке завдання",
        "зосередитися на важливому", "зосередитись на головному",
        "щоб ви могли зосередитися", "плавніший досвід",
        "інтуїтивніший досвід", "бездоганний досвід",
        "єдиний робочий простір", "усе необхідне", "жодних складнощів",
        "без зайвих зусиль", "лише кілька кроків", "у два кліки",
        "за лічені хвилини", "заощаджуйте час", "економте час",
        "підвищте продуктивність", "зробіть більше за менший час",
        "створено для того, щоб", "розроблено, щоб", "просто працює",
        "довіряють тисячі", "тисячі команд", "надійна безпека",
        "змінює те, як", "змінити те, як",
        # окремі слова-маркери
        "розмаїття", "оптимальний", "функціональність",
        "невід'ємно", "інноваційність", "ландшафт", "аспект",
        "усвідомленість", "побоювання", "дискомфорт", "новітність",
        "адаптований", "захоплюючий", "сучасність",
        "інноваційний", "трансформаційний", "безшовний", "масштабований",
        "проривний", "передовий", "неперевершений", "багатогранний",
        "всеосяжний", "революціонізувати", "максимізувати", "нівелювати",
        "уможливлює", "покликаний", "вирізняється", "гармонійно",
    ],
    "it": [
        # frasi cliché
        "nel mondo di oggi", "non fa eccezione", "è importante sottolineare",
        "vale la pena notare", "in conclusione", "riassumendo", "inoltre,",
        "per di più,", "senza dubbio",
        "soluzione ideale", "ampia gamma", "esperienza senza precedenti",
        "all'avanguardia", "immergiamoci",
        "che si tratti di", "in un mondo sempre più",
        "nonostante ciò,", "probabilmente,",
        # copy di prodotto e di interfaccia
        "soluzione completa", "tutto in uno", "per tutte le tue",
        "si integra perfettamente", "interfaccia intuitiva",
        "in pochi clic", "in pochi minuti", "inizia in pochi minuti",
        "alla base di tutto", "unisciti a migliaia", "utenti soddisfatti",
        "dimenticati di", "progettato pensando a", "crediamo che",
        "la nostra missione", "e molto altro", "potente ma semplice",
        "panorama digitale", "sblocca il pieno potenziale",
        "ottimizza il tuo flusso di lavoro", "non si tratta solo di",
        # Aggiunte per la parità con la lista inglese (2026-08-20), scritte
        # come specchio delle voci inglesi e non ricavate dal corpus. Come
        # per l'ucraino, niente congiunzioni generiche ("quindi,", "dunque,"):
        # senza un pool umano italiano la precisione non è misurabile.
        # aperture e attenuazioni
        "va notato che", "occorre considerare", "in linea di massima",
        "in una certa misura",
        # aperture temporali
        "nell'era digitale", "in un mondo in continua evoluzione",
        "ai giorni nostri",
        # chiusure
        "per riassumere", "in sintesi", "in definitiva,",
        # ganci di attenzione
        "scopriamo insieme", "immagina di", "e se ti dicessi",
        "resta con noi", "vediamo insieme",
        # espressioni di marketing
        "non cercare oltre", "libera il potenziale",
        "una vera rivoluzione", "soluzione all'avanguardia",
        "porta a un nuovo livello", "la chiave del successo",
        "una serie di vantaggi", "ampia scelta",
        # copy di prodotto e di interfaccia
        "qualunque sia il tuo", "concentrarti su ciò che conta",
        "così puoi concentrarti", "esperienza più fluida",
        "esperienza impeccabile", "un unico spazio di lavoro",
        "tutto ciò di cui hai bisogno", "senza alcuno sforzo",
        "in pochi passaggi", "in due clic", "in pochissimo tempo",
        "risparmia tempo", "aumenta la produttività",
        "fai di più in meno tempo", "progettato per", "funziona e basta",
        "scelto da migliaia", "migliaia di team", "sicurezza affidabile",
        "cambia il modo in cui",
        # singole parole/aggettivi ricorrenti
        "dinamico", "innovativo", "stimolante",
        "agevolare", "massimizzare", "ottimizzazione",
        "indagare", "rivoluzionario", "imprescindibile",
        "trasformativo", "scalabile", "senza soluzione di continuità",
        "ineguagliabile", "poliedrico", "onnicomprensivo", "all'avanguardia",
        "consentendo di", "permettendoti di", "si distingue per",
        # Ricavate dalla metà di taratura del corpus (2026-08-27), mai da
        # quella trattenuta: il numero onesto è quello che segue. Sono lo
        # specchio delle voci inglesi aggiunte lo stesso giorno. Il motivo per
        # cui servivano: i positivi italiani facevano scattare 0.67 frasi a
        # voce contro 1.34 dell'inglese e 1.43 dell'ucraino, cioè esattamente
        # la metà, e sotto le 25 parole l'italiano non superava mai la soglia.
        "informazioni actionable", "informazioni azionabili",
        "di livello aziendale", "trasformazione digitale",
        "soluzione end-to-end", "di tutte le dimensioni",
        "cresce con il tuo business", "si adatta alle tue esigenze",
        "ogni aspetto del tuo", "democratizzare l'accesso",
        "infrastruttura robusta", "sfruttando il potere",
        "sfrutta il potere", "decisioni informate",
    ],
}

# "Not just X, but Y"-style structural patterns, one regex list per language.
# These catch a construction, not a fixed phrase, so they're kept separate
# from CLICHE_PHRASES.
STRUCTURAL_PATTERNS: dict[str, list[re.Pattern]] = {
    "en": [
        re.compile(r"\bnot just\b.{0,40}\bbut\b", re.IGNORECASE),
        re.compile(r"\bit'?s not (about|just)\b.{0,40}\bit'?s (about|also)\b", re.IGNORECASE),
        re.compile(r"\bno\s+\w+\.\s*no\s+\w+\.\s*just\b", re.IGNORECASE),
        re.compile(r"\bwhether you'?re\b.{0,30}\bor\b", re.IGNORECASE),
        # "take your X to the next level" - a construction, not a phrase, so it
        # belongs here. It spent a moment in the phrase list, where every entry
        # is matched literally, and could therefore never match anything.
        re.compile(r"\btake your\b.{0,25}\bto the next level\b", re.IGNORECASE),
    ],
    "uk": [
        re.compile(r"\bне просто\b.{0,40}\bа\b", re.IGNORECASE),
        re.compile(r"\bсправа не в\b.{0,40}\bсправа в\b", re.IGNORECASE),
        re.compile(r"\bчи ви\b.{0,30}\bчи\b", re.IGNORECASE),
        # "це не просто про X; це про Y" - та сама конструкція, що й англійська
        # "it's not about X, it's about Y", але з "про" замість "а", тому
        # перший патерн її не ловив.
        re.compile(r"\bце не просто про\b.{0,40}\bце про\b", re.IGNORECASE),
        re.compile(r"\bжодних\s+\w+\.\s*жодних\s+\w+\.\s*(лише|тільки)\b",
                   re.IGNORECASE),
        re.compile(r"\b(виведіть|виведе|вивести)\b.{0,25}\bна новий рівень\b",
                   re.IGNORECASE),
    ],
    "it": [
        # `non solo X ma anche Y` was here as the Italian twin of "not just X
        # but Y", and it is not one. The English construction is a rhetorical
        # tic; the Italian is a correlative conjunction - ordinary grammar,
        # taught as such. Counted 2026-08-31: **0** model entries in the whole
        # corpus, against two human paragraphs (one travel guide, one
        # encyclopedic). A pattern that only ever fires on people is not a
        # detector, so it was removed rather than weighted down.
        re.compile(r"\bnon si tratta di\b.{0,40}\bsi tratta di\b", re.IGNORECASE),
        re.compile(r"\bche tu sia\b.{0,30}\bo\b", re.IGNORECASE),
        re.compile(r"\bniente\s+\w+\.\s*niente\s+\w+\.\s*solo\b", re.IGNORECASE),
        re.compile(r"\bport(a|are|ando)\b.{0,25}\ba un nuovo livello\b",
                   re.IGNORECASE),
    ],
}

# Re-exported so existing imports of detectors.heuristic.guess_language
# keep working; the implementation is shared with the extractors.
from lang_detect import guess_language  # noqa: E402


def combine_score(uniformity, repetition, dashes, structural: bool,
                  cliches: list) -> float:
    """One score from the evidence, in one place.

    Exported because the suppression pass has to answer "what would this have
    scored if that signal had never fired", and answering it with a second copy
    of the formula is how the two drifted apart: the copy was still treating an
    unmeasured signal as a zero, and a phrase as worth the same as a word.

    A `None` signal was not measurable on this passage, so it is left out of the
    average and the remaining weights are renormalised - not counted as zero,
    which would be a claim, and not as 0.3, which was a constant masquerading as
    a measurement.
    """
    measured = [(0.40, uniformity), (0.35, repetition), (0.25, dashes)]
    available = [(w, v) for w, v in measured if v is not None]
    if available:
        total = sum(w for w, _ in available)
        base = sum(w * v for w, v in available) / total
    else:
        base = 0.0

    # Evidence combines with diminishing returns rather than by addition with a
    # ceiling. Two reasons, and the second is the one that matters:
    #
    # A sum needs a cap or it leaves the scale, and a cap makes the score stop
    # responding. Above it, adding evidence changed nothing - and, worse,
    # *removing* evidence changed nothing either, so a user who suppressed a
    # phrase watched the score sit exactly where it was and reasonably concluded
    # the setting did nothing.
    #
    # This form is monotone everywhere: every piece of evidence raises the score
    # by a share of what is left to certainty, so the tenth is worth less than
    # the first, and taking any one away always lowers the result.
    strong = [c for c in cliches if " " in c]
    weak = [c for c in cliches if " " not in c]
    weights = [0.30] * len(strong) + [0.10] * len(weak)
    if structural:
        weights.append(0.25)

    remaining = 1.0 - max(0.0, min(1.0, base))
    for weight in weights:
        remaining *= (1.0 - weight)
    return max(0.0, min(1.0, 1.0 - remaining))


def _sentences(text: str, language: str | None = None) -> list[str]:
    """Split text into sentences, respecting abbreviations.

    The naive regex splits on every period followed by whitespace, which
    breaks on abbreviations like "es." or "Dr.". This version checks
    whether the word before each period is a known abbreviation and, if
    so, does not split there.

    Abbreviations are checked against **every** language's list, not against
    the detected language's. The language is a guess, and on exactly the
    strings this matters for - short ones - it is often wrong: the Italian
    placeholder `Inserisci un colore (es. #ffffff) o un gradiente (es.
    linear-gradient(...))` was detected as English, so the Italian list
    holding `es.` was never consulted, the string split into three
    fragments, and three fragments of near-equal length scored 0.82 for
    rhythm uniformity. A CSS placeholder with no clich√© and no structure
    became the highest-scoring finding of a whole run.

    The two errors are not symmetrical. Splitting on an abbreviation
    *invents* sentences, and the uniformity signal is computed from their
    lengths, so it invents evidence. Failing to split a real boundary only
    lowers the sentence count, and below three sentences uniformity is not
    measured at all - the signal goes quiet instead of lying. Given a guess
    at the language, the quiet failure is the one to choose.
    """
    if not text or not text.strip():
        return []

    # Find all potential split points (periods, !, ?, …)
    split_points = []
    for i, ch in enumerate(text):
        if ch in '.!?…':
            # Check if next char is whitespace (potential split point)
            if i + 1 < len(text) and text[i + 1] in ' \t\n':
                # Check if this is an abbreviation
                word = find_word_before_period(text, i)
                # `language=None` on purpose: every list, not the detected
                # one. See the docstring.
                if word and is_abbreviation(word):
                    continue  # Skip this split point
                split_points.append(i + 1)  # Split after the punctuation

    if not split_points:
        result = [text.strip()] if text.strip() else []
        return result

    # Split at the identified points
    result = []
    start = 0
    for pos in split_points:
        chunk = text[start:pos].strip()
        if chunk:
            result.append(chunk)
        start = pos

    # Add remaining text
    remaining = text[start:].strip()
    if remaining:
        result.append(remaining)

    return result


def _words(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def _burstiness_score(sentences: list[str]):
    """Human writing tends to vary sentence length a lot (bursty); a lot of
    generated prose is comparatively uniform. Returns 0..1, higher = more
    uniform = more AI-like, or None when there is not enough text to say.

    None rather than a neutral 0.3, which is what this returned before. The
    difference is not cosmetic: a constant with a weight of 0.4 in the average
    became a floor under every score, and on the short passages this tool
    mostly sees - a button label, one line of a locale file - it was the entire
    score. Model-written and human-written text both came out at 0.12 to 0.22,
    which is not a weak signal, it is no signal wearing one's clothes.
    """
    lengths = [len(_words(s)) for s in sentences if _words(s)]
    if len(lengths) < 3:
        return None
    mean = statistics.mean(lengths)
    if mean == 0:
        return None
    stdev = statistics.pstdev(lengths)
    cv = stdev / mean  # coefficient of variation
    # cv ~0 -> very uniform -> AI-like (score near 1); cv >= 0.6 -> bursty -> human-like
    score = max(0.0, min(1.0, 1.0 - (cv / 0.6)))
    return score


def _lexical_diversity_score(words: list[str]):
    """Low type-token ratio over a long-ish passage can indicate repetitive,
    formulaic phrasing. Returns 0..1, higher = less diverse = more AI-like, or
    None below the length where a ratio means anything.

    Twenty words is already generous for this: on a short passage nearly every
    word is its own type, so the ratio measures the length and not the writing.
    """
    if len(words) < 20:
        return None
    ttr = len(set(words)) / len(words)
    # Typical human TTR for this length ~0.55-0.75; below ~0.45 flagged.
    score = max(0.0, min(1.0, (0.6 - ttr) / 0.35))
    return score


def _em_dash_score(text: str, word_count: int):
    """Em/en-dash used as a stand-in for commas/parentheses, at a density
    well above typical human usage, is a commonly cited AI tell. Returns
    0..1, higher = more dash-heavy = more AI-like, or None when the passage is
    too short for a density to mean anything."""
    if word_count < 15:
        return None
    hits = len(_EM_DASH_RE.findall(text))
    per_100_words = hits / word_count * 100
    # ~0.3 dashes/100 words is normal human usage; >2/100 words is heavy.
    return max(0.0, min(1.0, (per_100_words - 0.3) / 1.7))


def _structural_matches(text: str, language: str | None) -> list[tuple[int, str]]:
    """Every structural-pattern match as (start_offset, matched_text).

    Offsets are kept because the boost this drives belongs to the sentence
    the construction is actually in — attributing it to the whole block
    scored, and explained, unrelated sentences as if they contained a
    pattern they don't.

    The English patterns are checked for every language (English marketing
    constructions get carried into Ukrainian and Italian copy untranslated),
    but only added once for English itself — otherwise every English hit was
    found twice and shown to the user twice.

    When language is None (too short to detect), check ALL patterns.
    """
    patterns = list(STRUCTURAL_PATTERNS["en"])
    if language is None:
        # Check all language-specific patterns
        for lang_patterns in STRUCTURAL_PATTERNS.values():
            patterns.extend(lang_patterns)
    elif language != "en":
        patterns = list(STRUCTURAL_PATTERNS.get(language, [])) + patterns
    hits: list[tuple[int, str]] = []
    for pattern in patterns:
        for match in pattern.finditer(text):
            hits.append((match.start(), match.group(0)))
    hits.sort()
    return hits


def _compile_word_boundary(phrase: str) -> re.Pattern:
    # Phrases may contain punctuation (e.g. "furthermore,") — only anchor a
    # word boundary on the sides that are actual word characters.
    left = r"\b" if re.match(r"\w", phrase[0], re.UNICODE) else ""
    right = r"\b" if re.match(r"\w", phrase[-1], re.UNICODE) else ""
    return re.compile(left + re.escape(phrase) + right, re.IGNORECASE)


_COMPILED_CLICHES: dict[str, list[tuple[str, re.Pattern]]] = {
    lang: [(phrase, _compile_word_boundary(phrase)) for phrase in phrases]
    for lang, phrases in CLICHE_PHRASES.items()
}


def _cliche_hits(text: str, language: str | None) -> list[str]:
    # The English list is always checked as well, since English marketing
    # phrases turn up untranslated in Ukrainian and Italian copy. For
    # English itself that would otherwise scan — and report — every phrase
    # twice, so the language list is only added when it isn't already 'en'.
    #
    # When language is None (too short to detect), check ALL lists to avoid
    # silently missing hits in the correct language.
    if language is None:
        candidates = []
        for lang_set in _COMPILED_CLICHES.values():
            candidates.extend(lang_set)
        # Deduplicate by phrase text to avoid reporting the same hit twice
        seen = set()
        unique = []
        for phrase, pattern in candidates:
            if phrase not in seen:
                seen.add(phrase)
                unique.append((phrase, pattern))
        candidates = unique
    else:
        candidates = list(_COMPILED_CLICHES["en"])
        if language != "en":
            candidates = list(_COMPILED_CLICHES.get(language, [])) + candidates
    spans = []
    for phrase, pattern in candidates:
        match = pattern.search(text)
        if match:
            spans.append((phrase, match.start(), match.end()))
    return _longest_only(spans)


def _longest_only(spans: list) -> list[str]:
    """Drop a hit that is contained in another hit on the same text.

    The lists hold both `seamless` and `seamless experience`, both
    `a testament to` and `testament`, both `delve` and `delves` - fourteen
    such pairs in English alone. One phrase in the copy then matched two
    entries, and `combine_score` charged for both: a strong hit at 0.30 and
    a weak one at 0.10 for the same three words, which is evidence counted
    twice. It also read as two clichés in the report where the reader can
    see one.

    Measured 2026-09-01 on a live tourism site: five passages matched
    `a testament to` **and** `testament`, scoring 0.57 where the one phrase
    they contain is worth 0.46.

    Compared by *span*, not by text: `ландшафт` inside
    `інформаційний ландшафт` at the same place is one construction counted
    twice, while the same word elsewhere in the passage is a second
    occurrence and is kept.

    **What this costs, measured rather than assumed.** Held-out recall goes
    62.5% -> 60.0% (Ukrainian 60.0% -> 53.3%, English and Italian
    unchanged), with false alarms still 0/359. Four Ukrainian positives were
    crossing the reporting line on one phrase charged twice - 0.30 for
    `розкрийте повний потенціал` plus 0.10 for the `повний потенціал`
    inside it - and that is not detection, it is an accounting error that
    happened to help. Recovering them by lowering the threshold is not
    available either: the sweep goes from 0 false alarms at 0.35 to 6 at
    0.30, and a wrong label is worse than a missing one here.

    Longest wins rather than "first in the list": the longer entry is the
    one that was written about this construction, and the shorter is the
    fragment it happens to contain.
    """
    kept = []
    for phrase, start, end in spans:
        covered = any(
            other != phrase and other_start <= start and end <= other_end
            for other, other_start, other_end in spans)
        if covered:
            continue
        kept.append(phrase)
    return kept


class HeuristicDetector(Detector):
    name = "heuristic"
    display_name = "Offline heuristic (style + structure + cliché phrases)"
    #: This detector *is* its lists. `CLICHE_PHRASES` and the structural
    #: patterns exist in exactly these three languages, and the score is
    #: nothing but what they match, so a fourth language gets English lists
    #: applied to text they were never swept against.
    supported_languages = ("uk", "it", "en")

    def analyze_block(self, block: TextBlock) -> list[TextSpan]:
        text = block.text
        language = block.language_hint or guess_language_safe(text)

        # A language this detector has no lists for gets silence, and gets it
        # by decision rather than by luck. Measured 2026-08-31 on 257 foreign
        # Wikipedia paragraphs: without this, all 257 came back with a span
        # each, no cliché matched, and every score sat at 0.32 - held there
        # by the statistical-only clamp three thousandths under the reporting
        # threshold. So the old answer was right and would have stopped being
        # right the day someone added an English phrase that also occurs in
        # French, with nothing in the code to notice.
        if not self.supports_language(language):
            return []

        sentences = _sentences(text, language)
        if not sentences:
            return []

        block_words = _words(text)
        burst = _burstiness_score(sentences)
        diversity = _lexical_diversity_score(block_words)
        em_dash = _em_dash_score(text, len(block_words))
        structural_matches = _structural_matches(text, language)

        # Sentence rhythm and word variety are properties of the whole
        # block, so they set a floor for every sentence in it. A structural
        # construction is not — it sits at one place in the text, and is
        # charged to the sentence it starts in.
        spans: list[TextSpan] = []
        cursor = 0
        for sentence in sentences:
            idx = text.find(sentence, cursor)
            if idx == -1:
                idx = cursor
            start, end = idx, idx + len(sentence)
            cursor = end

            structural = [m for offset, m in structural_matches if start <= offset < end]
            hits = _cliche_hits(sentence, language)
            score = combine_score(uniformity=burst, repetition=diversity,
                                  dashes=em_dash, structural=bool(structural),
                                  cliches=hits)

            # Statistical signals alone (uniformity, diversity, dashes) are
            # weak indicators. Without at least one concrete marker (a cliché
            # phrase or a structural pattern), the score must stay below the
            # reporting threshold. This prevents false positives on technical
            # descriptions, locale strings, and other non-marketing text that
            # happens to have uniform sentence lengths.
            if not hits and not structural and score >= 0.33:
                score = 0.32

            explanation_bits = [
                f"{name}={value:.2f}" if value is not None else f"{name}=not measured"
                for name, value in (("style-uniformity", burst),
                                    ("low-diversity", diversity),
                                    ("dash-density", em_dash))
            ]
            if structural:
                explanation_bits.append("structural: " + ", ".join(structural))
            if hits:
                explanation_bits.append("cliché: " + ", ".join(hits))

            # The same information as `explanation`, but as data. The UI
            # renders it into a sentence in the user's language (see
            # `explanations.render`); `explanation` stays a compact,
            # language-independent line for --json output and logs.
            details = {
                "source": "style",
                # None where the passage was too short to measure. Kept as a
                # key with no value rather than dropped, so a reader of the
                # JSON can tell "measured and low" from "not measured".
                "signals": {
                    "uniformity": None if burst is None else round(burst, 2),
                    "repetition": None if diversity is None else round(diversity, 2),
                    "dashes": None if em_dash is None else round(em_dash, 2),
                },
                "structural": list(structural),
                "cliches": list(hits),
                "language": language,
            }

            spans.append(
                TextSpan(
                    block_id=block.block_id,
                    start=start,
                    end=end,
                    score=score,
                    confidence=score_to_confidence(score),
                    detector_name=self.name,
                    explanation="; ".join(explanation_bits),
                    details=details,
                )
            )
        return spans


# Not registered as a detector of its own any more: on its own it is half of
# the free analysis, and offering it next to `offline` would ask the user to
# choose between "wording only" and "wording + characters" — a choice with no
# upside, since the character pass is exact and free. `detectors/offline.py`
# composes this class, and the old name still resolves through the alias
# below so existing CLI flags and settings files keep working.
DetectorFactory.register_alias(HeuristicDetector.name, "offline")
