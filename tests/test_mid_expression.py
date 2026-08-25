"""JSX puts markup and code in the same braces, so the walk that reads the
text between tags also reads the code between them.

`) : doc.indexed_at ? (` is not copy. Neither is
`= useTranslation();  const [open, setOpen] = useState`. Both were being
handed to the detectors as passages to judge, and a detector that scores
them is answering a question about the wrong string.

The rule is asymmetric on purpose, and the asymmetry came out of a
measurement rather than a preference. Prose never *starts* with a closing
bracket or an assignment. It does routinely *end* with an opening one,
because a sentence broken across JSX lines does exactly that -
`Languages the provider declares (` is real copy, and a rule that read the
ending too threw it away.

Measured against `~/repositories/XFormat` (1200 files, 1471 blocks from
`.ts`/`.tsx`): the opening rule removes 67 of them, every one syntax, and
nothing that reads as prose. Adding the ending rule caught three more and
cost one real sentence.

The fragments below are verbatim from that corpus. That is the point of
them: a heuristic tuned on invented examples is tuned on the person who
invented them.
"""
from __future__ import annotations

import unittest

from repo_scanner import _MID_EXPRESSION_RE

#: Real fragments the extractor used to hand over as copy.
SYNTAX = (
    ") : doc.indexed_at ? (",
    ") : defaultSection ? (",
    ") : analyzing ? (",
    ") : !detail ? (",
    ");\n\n  const actions = (",
    ");\n    expect(container.querySelectorAll('.ai-pi__line')).toHaveLength(3",
    "= useTranslation();\n  const [open, setOpen] = useState(true);",
    "= useParams",
    "= settings;\n\n  const patchApp = useCallback(",
    "]/i.test(html)\n    ? html\n    : `",
    "),\n    mime: 'application/vnd.openxmlformats-officedocument'",
    ", cause);\n  }\n\n  const result = await runAiChatFeature(",
)

#: Real copy from the same corpus, including the two the wider rules ate.
COPY = (
    "Languages the provider declares (",
    "Save. Once the offer has a slug,",
    "Drafts &amp; revisions (",
    "How do I…?",
    "Book language code (e.g. 'en', 'uk'). Optional.",
    "Remove all EXIF metadata (location, camera info, timestamps)",
    "Read the findings",
    "Потрібен доказ",
    "Contesto: {{tokens}} token",
    "OCR plus translation in one place",
)


class TheOpeningIsWhatGivesItAway(unittest.TestCase):
    def test_every_syntax_fragment_is_recognised(self):
        for fragment in SYNTAX:
            with self.subTest(fragment=fragment[:40]):
                self.assertTrue(_MID_EXPRESSION_RE.search(fragment))

    def test_no_real_copy_is_recognised(self):
        """The half that matters. A rule that removes a real sentence has
        made the scan quieter and worse."""
        for text in COPY:
            with self.subTest(text=text[:40]):
                self.assertIsNone(_MID_EXPRESSION_RE.search(text))

    def test_a_sentence_may_end_mid_expression(self):
        """`Languages the provider declares (` is a sentence broken across
        JSX lines, and this is exactly why the rule reads only the start."""
        self.assertIsNone(_MID_EXPRESSION_RE.search("Something declares ("))
        self.assertIsNone(_MID_EXPRESSION_RE.search("A list, and then"))

    def test_an_equality_test_is_not_an_assignment(self):
        """`== ` at the start is not `= `, and a rule that confused them
        would eat any sentence beginning with a comparison quoted in prose."""
        self.assertIsNone(_MID_EXPRESSION_RE.search("== means equality here"))


class ThroughTheExtractor(unittest.TestCase):
    """The rule where it actually runs, rather than in isolation."""

    def blocks(self, markup: str) -> list:
        from repo_scanner import SCOPE_CONTENT, _extract_blocks

        return [b.text for b in _extract_blocks(markup, "Comp.tsx", SCOPE_CONTENT)]

    def test_a_ternary_between_tags_is_not_copy(self):
        markup = ("export const C = () => (<div>{cond ? (<p>Real copy here "
                  "for a reader</p>) : other ? (<span>More</span>) : null}"
                  "</div>);")
        for text in self.blocks(markup):
            with self.subTest(text=text[:40]):
                self.assertFalse(text.strip().startswith(")"))

    def test_the_copy_around_it_survives(self):
        markup = ("export const C = () => (<div>{cond ? (<p>Real copy here "
                  "for a reader</p>) : null}</div>);")
        self.assertTrue(any("Real copy here for a reader" in text
                            for text in self.blocks(markup)))


if __name__ == "__main__":
    unittest.main()
