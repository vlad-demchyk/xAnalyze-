# Calibration corpus

Thresholds moved without data are just a different arbitrary number. This is the
data: text with a known author, so a score can be checked against an answer.

## Labels

`model` — written by a language model. Every entry here was generated as part of
building this corpus, so the label is true by construction, not by judgement.

`human` — written by a person before language models were writing product copy.
Provenance is recorded per entry. Where it is documentation rather than
marketing, the entry says so: register matters to this detector, and a corpus
that only holds one register will calibrate for one register.

`unlabelled` — real strings from a real product, kept separate on purpose. Their
author is not known to whoever assembled this file, and guessing would put a
guess into the ground truth, which is the one place a guess must not go.

## Sources

Every entry records where it came from. Three kinds of source are in here, and
they are not interchangeable:

`locale` — interface strings from the xFormat product (`en.json`, `it.json`,
`uk.json`). These are button labels and field names: the Italian median is 7
words. They are the right negatives for the question "does the detector flag a
menu", and the wrong ones for "does it flag a person's prose".

`documentation` / `product copy` — longer human writing, kept because register
matters to this detector and a corpus holding one register calibrates for one
register.

`encyclopedic` — paragraphs taken verbatim from Italian Wikipedia at a named
revision from 2018, years before language models were writing this kind of copy.
The source field carries the article, the revision id and the revision date, so
the claim "a person wrote this, and it is dated" is checkable rather than
asserted. This text is CC BY-SA; it is quoted here with attribution, and it is
measurement material, not product content.

## What is missing, and why it is not filled in

**Human prose in English and Ukrainian.** At 25+ words the human half now holds
31 Italian entries and only 4 English and 15 Ukrainian. A false-alarm rate for
those two languages at paragraph length is still a statement about a handful of
entries. The Italian gap was closed the way this one has to be: a dated source
with a named author, not text that reads human.

**Positives that were not written for this file.** Every `model` entry was
generated while building this corpus. The label is true by construction, but so
is the distribution: it is how a model writes when asked to write for a corpus,
not how generated copy looks in a shipped product.

**The unlabelled pool.** `unlabelled.jsonl` holds real strings whose author is
not known to whoever assembled this file. Guessing would put a guess into the
ground truth, which is the one place a guess must not go, so they stay out of
every number until someone who knows confirms them.

## Running it

    python scripts/calibrate.py                 # metrics at the current bands
    python scripts/calibrate.py --sweep         # every threshold, side by side
    python scripts/calibrate.py --review        # the unlabelled pool, ranked
