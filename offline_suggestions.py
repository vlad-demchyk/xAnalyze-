"""Offline replacements for the patterns the offline detector flags.

The rest of the app can *generate* a rewrite through a model, which costs
money and needs a network. This module is the free half: for the two kinds
of finding whose fix is decided by a rule rather than by taste, it produces
the corrected text directly.

Two sources of a correction:

* **Non-keyboard characters** — `unicode_rules` already knows the exact
  replacement for every character it flags, so nothing extra is needed here.
* **Cliché words and phrases** — each entry in the detector's word lists is
  paired below with the plainer wording a person would have typed, or with
  an empty string when the phrase is pure filler and the sentence reads
  better with it deleted. Substitution preserves the original capitalisation
  of the first letter and cleans up the double spaces and stranded commas
  that deleting an opener leaves behind.

What this deliberately does **not** do: rewrite for style. Sentence
uniformity and low lexical diversity are properties of a whole passage, not
a string that can be swapped out — a suggestion for those would be a guess
dressed up as a rule. Where the only signals are statistical, `suggest()`
returns None and the UI says the rewrite needs a model.

The tables cover exactly the entries in `detectors.heuristic.CLICHE_PHRASES`;
`missing_suggestions()` is the check that keeps them in step, and there is a
test that fails when a phrase is added to one and not the other.
"""
from __future__ import annotations

import re

# phrase (as written in CLICHE_PHRASES) -> replacement.
#   ""    delete it: the sentence says the same thing without it.
#   None  no mechanical replacement exists. The phrase is a claim or a piece of
#         positioning, and replacing it needs to know what is true of this
#         product - which a substitution table does not.
PHRASE_SUGGESTIONS: dict = {
    "en": {
        # product and interface copy. Most of these have no mechanical
        # replacement: they are positioning, and what replaces them depends
        # on what is actually true of the product.
        'comprehensive solution': None,
        'all your needs': None,
        'all-in-one solution': None,
        'empowering teams': None,
        'empowering you to': "so you can",
        'empowers you to': "lets you",
        'seamlessly integrate': "work with",
        'seamlessly integrates': "works with",
        'seamless integration': None,
        'intuitive interface': None,
        'user-friendly interface': None,
        'in just a few clicks': None,
        'in a matter of minutes': None,
        'get started in minutes': None,
        'at the core of everything': None,
        'everything you need in one place': None,
        'join thousands of': None,
        'trusted by thousands': None,
        'satisfied users': "users",
        'say goodbye to': None,
        'designed with you in mind': None,
        'built from the ground up': None,
        'the way it should be': None,
        'so you can focus on what matters': None,
        'focus on what truly matters': "focus on",
        'we believe that': "",
        'our mission is simple': None,
        'never looked back': None,
        'whatever you throw at it': None,
        'it just works': None,
        'and much more': None,
        'powerful yet simple': None,
        'simple yet powerful': None,
        'fast-paced digital': None,
        'digital landscape': None,
        'ever-changing landscape': None,
        'unlock the full potential': None,
        'full potential of your': None,
        'streamline your workflow': None,
        'streamline your workflows': None,
        'bridges the gap between': None,
        'not just about': None,
        'modern professional': None,
        # padding / hedging openers — the sentence says the same thing without them
        "it's important to note": "", "it is important to note": "",
        "it is worth mentioning": "", "it should be noted that": "",
        "it is essential to understand": "", "one must consider": "",
        "generally speaking": "", "broadly speaking": "", "to some extent": "",
        "arguably": "",
        # temporal / scene-setting openers
        "in today's fast-paced world": "", "in today's digital age": "",
        "in the era of": "in", "in a world where": "when",
        "in this day and age": "now", "in the modern era": "now",
        "in the ever-evolving landscape": "in",
        # transitions overused as sentence openers
        "furthermore,": "", "moreover,": "", "additionally,": "also,",
        "nevertheless,": "still,", "consequently,": "so,",
        "subsequently,": "then,", "that being said": "still",
        "at its core": "basically",
        # summary / closing clichés
        "in conclusion": "", "to summarize": "", "in summary": "",
        "to put it simply": "", "a key takeaway is": "",
        "from a broader perspective": "",
        # engagement hooks
        "let's dive in": "", "let's explore": "", "let's unpack": "",
        "buckle up": "", "stay tuned": "", "here's the deal": "",
        "picture this": "", "imagine if": "", "what if i told you": "",
        # marketing verbs / buzz phrases
        "unlock the potential": "make the most", "unlock your potential": "do more",
        "seamless experience": "smooth experience", "look no further": "",
        "elevate your": "improve your", "unleash the power": "use the power",
        "game-changer": "big change", "at the end of the day": "",
        "boasts a": "has a", "plethora of": "many",
        "navigate the complexities": "deal with", "a testament to": "proof of",
        "whether you're": "", "dive into the world of": "look at",
        "stand the test of time": "last", "in the realm of": "in",
        "shed light on": "explain", "cutting-edge": "latest",
        # business clichés
        "synergy": "working together", "paradigm shift": "major change",
        "low-hanging fruit": "easy wins", "move the needle": "make a difference",
        "boil the ocean": "do everything at once", "circle back": "come back to",
        "deep dive": "close look", "touch base": "check in",
        "value-add": "benefit", "win-win": "good for both sides",
        "bandwidth": "time",
        # structural clichés
        "is the new": "", "in the world of": "in",
        # single overused words
        "delve": "look into", "underscore": "show", "pivotal": "key",
        "realm": "area", "harness": "use", "illuminate": "show",
        "facilitate": "help", "refine": "improve", "bolster": "strengthen",
        "differentiate": "set apart", "streamline": "simplify",
        "revolutionize": "change", "innovative": "new",
        "transformative": "far-reaching", "seamless": "smooth",
        "scalable": "able to grow", "comprehensive": "complete",
        "robust": "solid", "stellar": "excellent", "exceptional": "unusually good",
        "unparalleled": "unmatched", "dynamic": "changing", "intricate": "detailed",
        "nuanced": "subtle", "holistic": "whole", "paramount": "most important",
        "formidable": "hard to beat", "nimble": "quick", "supercharge": "speed up",
        "turbocharge": "speed up", "amplify": "increase", "embark": "start",
        "uncover": "find", "unveil": "show", "tailor": "adapt", "hone": "sharpen",
        "foster": "encourage", "myriad": "many", "countless": "many",
        "innumerable": "many", "substantial": "large", "testament": "proof",
        "tapestry": "mix", "indelible": "lasting", "invaluable": "very useful",
        "meticulous": "careful", "vibrant": "lively",
    },
    "uk": {
        # product and interface copy. Most of these have no mechanical
        # replacement: they are positioning, and what replaces them depends
        # on what is actually true of the product.
        'комплексне рішення': None,
        'для всіх ваших': None,
        'все в одному': None,
        'даючи змогу': "щоб",
        'дозволяючи вам': "щоб ви могли",
        'безшовно інтегру': None,
        'інтуїтивний інтерфейс': None,
        'зручний інтерфейс': None,
        'у кілька кліків': None,
        'за кілька хвилин': None,
        'почати роботу за': None,
        'основою всього, що ми': None,
        'все, що вам потрібно': None,
        'приєднуйтесь до тисяч': None,
        'задоволених користувачів': "користувачів",
        'забудьте про': None,
        'створено з думкою про': None,
        'ми переконані, що': "",
        'наша мета проста': None,
        'і багато іншого': None,
        'просте й водночас': None,
        'динамічному цифровому': None,
        'цифровому середовищі': None,
        'розкрийте повний потенціал': None,
        'повний потенціал': None,
        'оптимізувати робочі процеси': None,
        'оптимізували роботу': None,
        'не просто про': None,
        'сучасного професіонала': None,
        'передовому ai': None,
        'передові технології': None,
        'потужні технології': None,
        "у сучасному світі": "", "не є винятком": "", "варто зазначити": "",
        "важливо підкреслити": "", "зануримося": "",
        "розкрити потенціал": "використати сповна",
        "розкрийте потенціал": "використайте сповна",
        "на завершення": "", "підсумовуючи": "", "крім того,": "",
        "більше того,": "", "безсумнівно": "", "це свідчить про": "це показує",
        "надзвичайно важливо": "важливо", "широкий спектр": "багато",
        "справжня знахідка": "", "ідеальне рішення": "рішення",
        "у світі, де": "коли", "незалежно від того": "",
        "з кожним днем": "", "перш за все,": "", "невід'ємна частина": "частина",
        "інформаційний ландшафт": "медіа", "цифровий контент": "контент",
        "справжній феномен": "", "розумний вибір": "вибір",
        "оптимальне рішення": "рішення",
        "потреби сучасної аудиторії": "потреби аудиторії",
        "інноваційні рішення": "нові рішення",
        "максимальна ефективність": "ефективність",
        "більшість користувачів": "", "ось деякі з них": "",
        "особливо корисно": "корисно",
        "розмаїття": "різні", "оптимальний": "найкращий",
        "функціональність": "можливості", "феномен": "явище",
        "невід'ємно": "нерозривно", "інноваційність": "новизна",
        "ландшафт": "середовище", "аспект": "бік",
        "усвідомленість": "розуміння", "побоювання": "страх",
        "дискомфорт": "незручність", "новітність": "новизна",
        "адаптований": "пристосований", "захоплюючий": "цікавий",
        "сучасність": "сьогодення",
    },
    "it": {
        # product and interface copy. Most of these have no mechanical
        # replacement: they are positioning, and what replaces them depends
        # on what is actually true of the product.
        'soluzione completa': None,
        'tutto in uno': None,
        'per tutte le tue': None,
        'si integra perfettamente': "funziona con",
        'interfaccia intuitiva': None,
        'in pochi clic': None,
        'in pochi minuti': None,
        'inizia in pochi minuti': None,
        'alla base di tutto': None,
        'unisciti a migliaia': None,
        'utenti soddisfatti': "utenti",
        'dimenticati di': None,
        'progettato pensando a': None,
        'crediamo che': "",
        'la nostra missione': None,
        'e molto altro': None,
        'potente ma semplice': None,
        'panorama digitale': None,
        'sblocca il pieno potenziale': None,
        'ottimizza il tuo flusso di lavoro': None,
        'non si tratta solo di': None,
        "nel mondo di oggi": "", "non fa eccezione": "",
        "è importante sottolineare": "", "vale la pena notare": "",
        "in conclusione": "", "riassumendo": "", "inoltre,": "",
        "per di più,": "", "senza dubbio": "", "un vero e proprio": "",
        "soluzione ideale": "soluzione", "ampia gamma": "molti",
        "esperienza senza precedenti": "esperienza nuova",
        "all'avanguardia": "aggiornato", "punto di svolta": "svolta",
        "immergiamoci": "", "che si tratti di": "",
        "in un mondo sempre più": "", "tuttavia,": "ma,",
        "nonostante ciò,": "eppure,", "probabilmente,": "forse,",
        "dinamico": "vivace", "efficiente": "rapido", "innovativo": "nuovo",
        "stimolante": "interessante", "efficienza": "resa",
        "agevolare": "aiutare", "massimizzare": "aumentare",
        "ottimizzazione": "miglioramento", "integrazione": "collegamento",
        "indagare": "esaminare", "rivoluzionario": "nuovo",
        "imprescindibile": "necessario", "fondamentale": "importante",
    },
}

# Em/en dashes used as commas are the other mechanical part of the style
# signal: a dash between two spaces is standing in for punctuation a person
# would have typed. A dash with no spaces around it (a range, "2020—2024")
# is left alone, and so is Ukrainian тире, which is correct there.
_SPACED_DASH_RE = re.compile(r"\s+[—–]\s+")
_DASH_LANGUAGES_TO_FIX = ("en", "it")

_MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")
_SPACE_BEFORE_PUNCT_RE = re.compile(r"\s+([,.;:!?])")
_LEADING_PUNCT_RE = re.compile(r"^[\s,;:—–-]+")

# A replacement that ends in a preposition can collide with the one already
# in the sentence: "delve into" -> "look into" + "into" = "look into into".
# Only these function words are collapsed when doubled — a general
# duplicate-word rule would also "fix" deliberate repetition in real copy.
_FUNCTION_WORDS = (
    "into", "in", "on", "at", "to", "of", "for", "with", "the", "a", "an",
    "di", "da", "del", "della", "il", "la", "le", "un", "una", "per", "con",
    "у", "в", "на", "до", "з", "із", "за", "про",
)
_DOUBLED_RE = re.compile(
    r"\b(" + "|".join(_FUNCTION_WORDS) + r")\s+\1\b", re.IGNORECASE | re.UNICODE
)


def _compile(phrase: str) -> re.Pattern:
    """Word-boundary match, anchored only on the sides that are word
    characters — the same rule the detector uses, so the two agree on what
    counts as a hit."""
    left = r"\b" if re.match(r"\w", phrase[0], re.UNICODE) else ""
    right = r"\b" if re.match(r"\w", phrase[-1], re.UNICODE) else ""
    return re.compile(left + re.escape(phrase) + right, re.IGNORECASE)


#: Only the entries that actually have wording to substitute. `None` means the
#: phrase was considered and has no mechanical replacement: "comprehensive
#: solution" is not a word that can be swapped for a better one, it is a claim
#: that has to be rewritten into whatever the product actually does, and only a
#: person or a model knows that. Recorded as a decision rather than an omission,
#: so `missing_suggestions()` still catches a phrase nobody has thought about.
_COMPILED: dict = {
    lang: [(phrase, _compile(phrase), replacement)
           for phrase, replacement in table.items()
           if replacement is not None]
    for lang, table in PHRASE_SUGGESTIONS.items()
}


def _match_case(original: str, replacement: str) -> str:
    """Keep the original capitalisation so replacing the first words of a
    sentence doesn't lowercase it."""
    if not replacement or not original:
        return replacement
    if original[0].isupper():
        return replacement[0].upper() + replacement[1:]
    return replacement


def _tidy(text: str) -> str:
    """Repair the punctuation that deleting a phrase leaves behind."""
    text = _DOUBLED_RE.sub(r"\1", text)
    text = _MULTI_SPACE_RE.sub(" ", text)
    text = _SPACE_BEFORE_PUNCT_RE.sub(r"\1", text)
    text = _LEADING_PUNCT_RE.sub("", text)
    text = re.sub(r",\s*,", ",", text)
    text = text.strip()
    # Deleting an opener can leave a lowercase first letter mid-sentence.
    if text and text[0].islower():
        text = text[0].upper() + text[1:]
    return text


def suggest(text: str, language: str | None) -> str | None:
    """Return an offline-corrected version of `text`, or None when no rule
    applies and only a model could improve it."""
    language = language or "en"
    # English marketing phrases turn up untranslated in Ukrainian and Italian
    # copy, so the English table is always consulted as well — matching the
    # detector, which flags them for the same reason.
    tables = list(_COMPILED.get(language, []))
    if language != "en":
        tables += _COMPILED["en"]

    out = text
    for _phrase, pattern, replacement in tables:
        out = pattern.sub(lambda m: _match_case(m.group(0), replacement), out)

    if language in _DASH_LANGUAGES_TO_FIX:
        out = _SPACED_DASH_RE.sub(", ", out)

    out = _tidy(out)
    return out if out and out != text else None


def missing_suggestions() -> dict:
    """Phrases the detector can flag but this module has no wording for.

    Kept as a function rather than a comment because the two lists are edited
    independently: a phrase added to the detector without a replacement here
    would otherwise silently produce a finding the user can't act on offline.
    """
    from detectors.heuristic import CLICHE_PHRASES

    gaps = {}
    for lang, phrases in CLICHE_PHRASES.items():
        known = PHRASE_SUGGESTIONS.get(lang, {})
        absent = [p for p in phrases if p not in known]
        if absent:
            gaps[lang] = absent
    return gaps
