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
from .base import Detector
from .factory import DetectorFactory

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")
_WORD_RE = re.compile(r"[\w'’-]+", re.UNICODE)
_EM_DASH_RE = re.compile(r"[—–]")

# Single words + short phrases large language models reach for far more
# often than typical human writers, grouped by language. Matched with word
# boundaries (case-insensitive), so short items don't false-positive inside
# unrelated longer words. Not exhaustive — extend freely.
CLICHE_PHRASES: dict[str, list[str]] = {
    "en": [
        # padding / hedging openers
        "it's important to note", "it is important to note",
        "it is worth mentioning", "it should be noted that",
        "it is essential to understand", "one must consider",
        "generally speaking", "broadly speaking", "to some extent", "arguably",
        # temporal / scene-setting openers
        "in today's fast-paced world", "in today's digital age",
        "in the era of", "in a world where", "in this day and age",
        "in the modern era", "in the ever-evolving landscape",
        # transitions overused as sentence openers
        "furthermore,", "moreover,", "additionally,", "nevertheless,",
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
        "value-add", "win-win", "bandwidth",
        # structural clichés ("No X. No Y. Just Z." is a regex in
        # STRUCTURAL_PATTERNS — a literal here could never match real text)
        "is the new", "in the world of",
        # single overused words
        "delve", "underscore", "pivotal", "realm", "harness", "illuminate",
        "facilitate", "refine", "bolster", "differentiate", "streamline",
        "revolutionize", "innovative", "transformative", "seamless",
        "scalable", "comprehensive", "robust", "stellar", "exceptional",
        "unparalleled", "dynamic", "intricate", "nuanced", "holistic",
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
        "крім того,", "більше того,", "безсумнівно", "це свідчить про",
        "надзвичайно важливо", "широкий спектр", "справжня знахідка",
        "ідеальне рішення", "у світі, де", "незалежно від того",
        "з кожним днем", "перш за все,", "невід'ємна частина",
        "інформаційний ландшафт", "цифровий контент", "справжній феномен",
        "розумний вибір", "оптимальне рішення", "потреби сучасної аудиторії",
        "інноваційні рішення", "максимальна ефективність",
        "більшість користувачів", "ось деякі з них", "особливо корисно",
        # окремі слова-маркери
        "розмаїття", "оптимальний", "функціональність", "феномен",
        "невід'ємно", "інноваційність", "ландшафт", "аспект",
        "усвідомленість", "побоювання", "дискомфорт", "новітність",
        "адаптований", "захоплюючий", "сучасність",
    ],
    "it": [
        # frasi cliché
        "nel mondo di oggi", "non fa eccezione", "è importante sottolineare",
        "vale la pena notare", "in conclusione", "riassumendo", "inoltre,",
        "per di più,", "senza dubbio", "un vero e proprio",
        "soluzione ideale", "ampia gamma", "esperienza senza precedenti",
        "all'avanguardia", "punto di svolta", "immergiamoci",
        "che si tratti di", "in un mondo sempre più", "tuttavia,",
        "nonostante ciò,", "probabilmente,",
        # singole parole/aggettivi ricorrenti
        "dinamico", "efficiente", "innovativo", "stimolante", "efficienza",
        "agevolare", "massimizzare", "ottimizzazione", "integrazione",
        "indagare", "rivoluzionario", "imprescindibile", "fondamentale",
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
    ],
    "uk": [
        re.compile(r"\bне просто\b.{0,40}\bа\b", re.IGNORECASE),
        re.compile(r"\bсправа не в\b.{0,40}\bсправа в\b", re.IGNORECASE),
        re.compile(r"\bчи ви\b.{0,30}\bчи\b", re.IGNORECASE),
    ],
    "it": [
        re.compile(r"\bnon solo\b.{0,40}\bma anche\b", re.IGNORECASE),
        re.compile(r"\bnon si tratta di\b.{0,40}\bsi tratta di\b", re.IGNORECASE),
        re.compile(r"\bche tu sia\b.{0,30}\bo\b", re.IGNORECASE),
    ],
}

# Re-exported so existing imports of detectors.heuristic.guess_language
# keep working; the implementation is shared with the extractors.
from lang_detect import guess_language  # noqa: E402


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]


def _words(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def _burstiness_score(sentences: list[str]) -> float:
    """Human writing tends to vary sentence length a lot (bursty); a lot of
    generated prose is comparatively uniform. Returns 0..1, higher = more
    uniform = more AI-like."""
    lengths = [len(_words(s)) for s in sentences if _words(s)]
    if len(lengths) < 3:
        return 0.3  # not enough data, stay neutral-low
    mean = statistics.mean(lengths)
    if mean == 0:
        return 0.3
    stdev = statistics.pstdev(lengths)
    cv = stdev / mean  # coefficient of variation
    # cv ~0 -> very uniform -> AI-like (score near 1); cv >= 0.6 -> bursty -> human-like
    score = max(0.0, min(1.0, 1.0 - (cv / 0.6)))
    return score


def _lexical_diversity_score(words: list[str]) -> float:
    """Low type-token ratio over a long-ish passage can indicate repetitive,
    formulaic phrasing. Returns 0..1, higher = less diverse = more AI-like."""
    if len(words) < 20:
        return 0.3
    ttr = len(set(words)) / len(words)
    # Typical human TTR for this length ~0.55-0.75; below ~0.45 flagged.
    score = max(0.0, min(1.0, (0.6 - ttr) / 0.35))
    return score


def _em_dash_score(text: str, word_count: int) -> float:
    """Em/en-dash used as a stand-in for commas/parentheses, at a density
    well above typical human usage, is a commonly cited AI tell. Returns
    0..1, higher = more dash-heavy = more AI-like."""
    if word_count < 15:
        return 0.0
    hits = len(_EM_DASH_RE.findall(text))
    per_100_words = hits / word_count * 100
    # ~0.3 dashes/100 words is normal human usage; >2/100 words is heavy.
    return max(0.0, min(1.0, (per_100_words - 0.3) / 1.7))


def _structural_matches(text: str, language: str) -> list[tuple[int, str]]:
    """Every structural-pattern match as (start_offset, matched_text).

    Offsets are kept because the boost this drives belongs to the sentence
    the construction is actually in — attributing it to the whole block
    scored, and explained, unrelated sentences as if they contained a
    pattern they don't.

    The English patterns are checked for every language (English marketing
    constructions get carried into Ukrainian and Italian copy untranslated),
    but only added once for English itself — otherwise every English hit was
    found twice and shown to the user twice.
    """
    patterns = list(STRUCTURAL_PATTERNS["en"])
    if language != "en":
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


def _cliche_hits(text: str, language: str) -> list[str]:
    # The English list is always checked as well, since English marketing
    # phrases turn up untranslated in Ukrainian and Italian copy. For
    # English itself that would otherwise scan — and report — every phrase
    # twice, so the language list is only added when it isn't already 'en'.
    candidates = list(_COMPILED_CLICHES["en"])
    if language != "en":
        candidates = list(_COMPILED_CLICHES.get(language, [])) + candidates
    return [phrase for phrase, pattern in candidates if pattern.search(text)]


class HeuristicDetector(Detector):
    name = "heuristic"
    display_name = "Offline heuristic (style + structure + cliché phrases)"
    supported_languages = ("uk", "it", "en")

    def analyze_block(self, block: TextBlock) -> list[TextSpan]:
        text = block.text
        language = block.language_hint or guess_language(text)
        sentences = _sentences(text)
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
        base_score = 0.4 * burst + 0.35 * diversity + 0.25 * em_dash
        base_score = max(0.0, min(1.0, base_score))

        spans: list[TextSpan] = []
        cursor = 0
        for sentence in sentences:
            idx = text.find(sentence, cursor)
            if idx == -1:
                idx = cursor
            start, end = idx, idx + len(sentence)
            cursor = end

            structural = [m for offset, m in structural_matches if start <= offset < end]
            structural_boost = 0.25 if structural else 0.0

            hits = _cliche_hits(sentence, language)
            cliche_boost = min(0.4, 0.15 * len(hits))
            score = max(0.0, min(1.0, base_score + structural_boost + cliche_boost))

            explanation_bits = [
                f"style-uniformity={burst:.2f}", f"low-diversity={diversity:.2f}",
                f"dash-density={em_dash:.2f}",
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
                "signals": {
                    "uniformity": round(burst, 2),
                    "repetition": round(diversity, 2),
                    "dashes": round(em_dash, 2),
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
