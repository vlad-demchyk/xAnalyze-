"""Detection behaviour: what gets flagged, what must not, and why.

The point of these is not coverage. Every case here is either a bug that
was actually found in this code, or a property the tool would be dishonest
without — a clean Ukrainian sentence with an em dash coming back clean
matters more than any percentage.
"""
from __future__ import annotations

import unittest
import uuid

import detectors  # noqa: F401 - registers the built-in detectors
import offline_suggestions
import unicode_rules
from detectors.factory import DetectorFactory
from models import Confidence, TextBlock


def block(text: str, language: str | None = None) -> TextBlock:
    return TextBlock(block_id=str(uuid.uuid4()), page_url="http://x/",
                     dom_path="p", text=text, language_hint=language)


def spans(text: str, language: str | None = None, **config) -> list:
    return DetectorFactory.create("offline", **config).analyze_block(block(text, language))


def top_score(text: str, language: str | None = None) -> float:
    style = [s for s in spans(text, language) if s.details.get("source") == "style"]
    return max((s.score for s in style), default=0.0)


class LanguageScoping(unittest.TestCase):
    """The hard part is not finding non-ASCII — it is leaving alone the
    characters that are correct for the language."""

    def test_ukrainian_prose_is_clean(self):
        text = "Учора я купив хліб. Було холодно, тому я швидко пішов додому."
        self.assertEqual(unicode_rules.find_anomalies(text, "uk"), [])

    def test_ukrainian_guillemets_and_apostrophe_are_correct(self):
        text = "Це «стандартні» лапки, і м'який апостроф."
        self.assertEqual(unicode_rules.find_anomalies(text, "uk"), [])

    def test_italian_accents_are_correct(self):
        text = "Perché è così? Ieri sono andato al mercato però."
        self.assertEqual(unicode_rules.find_anomalies(text, "it"), [])

    def test_english_guillemets_are_flagged(self):
        found = unicode_rules.find_anomalies("He said «hello» to me.", "en")
        self.assertTrue(found, "guillemets are not English punctuation")

    def test_latin_brand_inside_ukrainian_sentence_is_clean(self):
        # A brand name in the Latin alphabet is not a mixed-alphabet word.
        text = "Купуйте iPhone 15 Pro у нашому магазині."
        homoglyphs = [a for a in unicode_rules.find_anomalies(text, "uk")
                      if a.category == unicode_rules.CAT_HOMOGLYPH]
        self.assertEqual(homoglyphs, [])


class CharacterFindings(unittest.TestCase):
    def test_homoglyph_is_found_and_corrected(self):
        found = unicode_rules.find_anomalies("Enter your pаssword", "en")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].category, unicode_rules.CAT_HOMOGLYPH)
        self.assertEqual(found[0].replacement, "a")

    def test_invisible_character_is_removed(self):
        found = unicode_rules.find_anomalies("Hello​world", "en")
        self.assertEqual(found[0].replacement, "")

    def test_clean_text_round_trips(self):
        dirty = "Hello​world and pаssword"
        # The zero-width space is deleted, not turned into a space: it was
        # never a word boundary, it was pasted in between two letters.
        self.assertEqual(unicode_rules.clean_text(dirty, "en"), "Helloworld and password")

    def test_non_breaking_space_becomes_a_plain_space(self):
        nbsp = "five\u00a0euros"
        self.assertEqual(unicode_rules.clean_text(nbsp, "en"), "five euros")

    def test_replacement_is_carried_on_the_span(self):
        # Recomputing the fix later from the isolated span would lose the
        # surrounding word, and a homoglyph fix would silently become a no-op.
        found = [s for s in spans("Enter your pаssword now", "en")
                 if s.details.get("source") == "characters"]
        self.assertEqual([s.replacement for s in found], ["a"])


class StyleFindings(unittest.TestCase):
    def test_cliche_heavy_text_scores_above_plain_prose(self):
        ai_like = ("In today's fast-paced world, it is important to note that our "
                   "comprehensive platform will unlock the potential of your team.")
        human = ("I went to the shop. It rained. My dog ate the receipt, which was "
                 "annoying because I needed it for the return.")
        self.assertGreater(top_score(ai_like), top_score(human))

    def test_structural_pattern_is_charged_to_its_own_sentence(self):
        # Regression: a structural hit anywhere in a block used to boost and
        # "explain" every sentence in it, including unrelated ones.
        text = "It is not just a tool but a partner. Enter your password here."
        style = [s for s in spans(text, "en") if s.details.get("source") == "style"]
        by_text = {text[s.start:s.end]: s.details.get("structural") for s in style}
        self.assertTrue(by_text["It is not just a tool but a partner."])
        self.assertEqual(by_text["Enter your password here."], [])

    def test_the_other_two_languages_catch_the_same_constructions(self):
        """Parity, checked as behaviour rather than as list length.

        The Ukrainian and Italian lists were brought up to the English one in
        August 2026 because a single cliché hit scores 0.30 and the reporting
        threshold is 0.33: a sentence that fires one phrase in Ukrainian and
        two in English is reported in English and silent in Ukrainian, which
        read as "the tool does not work in my language" and was in fact "the
        list is half as dense".
        """
        cases = (
            # "це не просто про X; це про Y" - the Ukrainian form of
            # "it's not about X, it's about Y". The older pattern expected
            # "а" and could not match it.
            ("uk", "Це не просто про економію часу; це про зміну того, як ви працюєте."),
            ("it", "Non si tratta di risparmiare tempo: si tratta di cambiare il modo in cui lavori."),
        )
        for lang, text in cases:
            with self.subTest(lang=lang):
                style = [s for s in spans(text, lang)
                         if s.details.get("source") == "style"]
                self.assertTrue(any(s.details.get("structural") for s in style),
                                f"no structural hit for {lang}")

    def test_a_ukrainian_sentence_with_two_hits_clears_the_threshold(self):
        text = ("Наша мета проста: прибрати тертя із завдань, що вас сповільнюють, "
                "щоб ви могли зосередитися на важливому.")
        self.assertGreaterEqual(top_score(text, "uk"), 0.33)

    def test_english_patterns_are_not_reported_twice(self):
        # Regression: the English list was concatenated onto itself for
        # English text, so every hit was found and shown twice.
        text = "It is not just a tool but a partner."
        style = [s for s in spans(text, "en") if s.details.get("source") == "style"]
        hits = style[0].details["structural"]
        self.assertEqual(len(hits), len(set(hits)))


class MergedOfflineDetector(unittest.TestCase):
    def test_both_passes_run_in_one_detector(self):
        text = ("In today's fast-paced world, it is important to note this. "
                "Enter your pаssword.")
        sources = {s.details.get("source") for s in spans(text, "en")}
        self.assertEqual(sources, {"style", "characters"})

    def test_character_categories_can_be_narrowed(self):
        text = "This costs 5 — 6 euros — roughly."
        with_typography = [s for s in spans(text, "en")
                           if s.details.get("category") == "typography"]
        without = [s for s in spans(text, "en",
                                    categories=("invisible", "homoglyph"))
                   if s.details.get("category") == "typography"]
        self.assertTrue(with_typography)
        self.assertEqual(without, [])

    def test_style_can_be_turned_off(self):
        text = "In today's fast-paced world, it is important to note this."
        found = spans(text, "en", include_style=False)
        self.assertEqual([s for s in found if s.details.get("source") == "style"], [])

    def test_retired_names_still_resolve(self):
        # An old settings.json or a CLI flag in someone's git hook must not
        # break just because the two passes were merged.
        self.assertEqual(DetectorFactory.resolve("heuristic"), "offline")
        self.assertEqual(DetectorFactory.resolve("unicode-anomalies"), "offline")

    def test_retired_names_are_not_offered_as_choices(self):
        self.assertNotIn("heuristic", DetectorFactory.available())
        self.assertNotIn("unicode-anomalies", DetectorFactory.available())


class OfflineSuggestions(unittest.TestCase):
    def test_every_cliche_has_a_replacement(self):
        # The detector's word lists and the replacement tables are edited
        # independently; a phrase in one and not the other would produce a
        # finding the user cannot act on offline.
        self.assertEqual(offline_suggestions.missing_suggestions(), {})

    def test_filler_opener_is_deleted_and_sentence_recapitalised(self):
        out = offline_suggestions.suggest(
            "It is important to note that the form was saved.", "en")
        self.assertEqual(out, "That the form was saved.")

    def test_replacement_does_not_double_a_preposition(self):
        # "delve" -> "look into" next to an existing "into".
        out = offline_suggestions.suggest("We delve into the data.", "en")
        self.assertEqual(out, "We look into the data.")

    def test_plain_prose_gets_no_suggestion(self):
        self.assertIsNone(
            offline_suggestions.suggest("I went to the shop and bought bread.", "en"))

    def test_english_phrases_are_caught_inside_ukrainian_copy(self):
        out = offline_suggestions.suggest("Наш robust сервіс працює.", "uk")
        self.assertIn("solid", out)


class Explanations(unittest.TestCase):
    def test_character_finding_explains_the_exact_codepoint(self):
        import explanations

        text = "Enter your pаssword"
        span = next(s for s in spans(text, "en")
                    if s.details.get("source") == "characters")
        rendered = explanations.render(span, text, "en")
        self.assertIn("U+0430", " ".join(rendered.reasons))
        self.assertEqual(rendered.suggestion, "a")

    def test_statistical_only_finding_offers_no_fake_suggestion(self):
        import explanations

        # Uniform rhythm and low word variety are a rewrite, not a
        # substitution; inventing a "suggestion" here would be a guess.
        text = "The cat sat there. The dog sat there. The bird sat there."
        span = next(s for s in spans(text, "en") if s.details.get("source") == "style")
        rendered = explanations.render(span, text, "en")
        self.assertIsNone(rendered.suggestion)

    def test_explanation_follows_the_ui_language(self):
        import explanations

        text = "Enter your pаssword"
        span = next(s for s in spans(text, "en")
                    if s.details.get("source") == "characters")
        self.assertNotEqual(
            explanations.render(span, text, "uk").title,
            explanations.render(span, text, "en").title,
        )


if __name__ == "__main__":
    unittest.main()
