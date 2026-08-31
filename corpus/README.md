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

`encyclopedic` — paragraphs taken verbatim from Wikipedia in all three
languages, each at a named revision from 2018 (a few from 2017), years before
language models were writing this kind of copy. The source field carries the
article, the revision id and the revision date, so the claim "a person wrote
this, and it is dated" is checkable rather than asserted. This text is CC BY-SA;
it is quoted here with attribution, and it is measurement material, not product
content.

## What is missing, and why it is not filled in

**Negatives that argue rather than describe.** At 25+ words the human half now
holds 40 English, 31 Italian and 45 Ukrainian entries, but the prose among them
is encyclopedic: it explains a subject. Marketing copy written by a person
persuades, which is the register the model half imitates, and the corpus has
almost none of it with certain provenance. A false alarm is likelier there than
anywhere else in this file, and it is the one place still unmeasured.

**Positives that were not written for this file.** Every `model` entry was
generated while building this corpus. The label is true by construction, but so
is the distribution: it is how a model writes when asked to write for a corpus,
not how generated copy looks in a shipped product.

**The unlabelled pool.** `unlabelled.jsonl` holds real strings whose author is
not known to whoever assembled this file. Guessing would put a guess into the
ground truth, which is the one place a guess must not go, so they stay out of
every number until someone who knows confirms them.

## Half of this file is a detector

`EmbeddingDetector` scores by nearest-neighbour margin against these entries, so
the corpus is a *component* of it as well as the yardstick it is judged by, and
the two roles pull opposite ways. Measured 2026-08-31: adding 95 correct human
paragraphs raised the human side of the margin from 0.461 to 0.541 and dropped
the score on an unchanged AI passage from 0.590 to 0.549. The corpus got better
and the detector got worse.

So the halves have jobs, decided by a hash of the text in `corpus_split.py`:

* the **tune half** is the only part that detector is allowed to read;
* the **held-out half** is the only part any number about it may be measured on.

A hash rather than a position, so an entry added today lands in one half and
stays there instead of moving an existing entry across the line and quietly
restating every number measured before it.

Two consequences worth knowing before editing this file:

* **A corpus change is a detector change.** Re-run
  `python scripts/calibrate.py --detector embedding --holdout --sweep` after
  adding entries; the threshold in `detectors/embedding.py` is a measurement,
  not a preference.
* **The whole-corpus number for such a detector does not exist.** Asked for one,
  the script refuses: read whole, the corpus separates itself almost perfectly
  (model 0.73-0.79 against human near 0.16) and every point of it is
  self-recognition.

## Running it

    python scripts/calibrate.py                 # metrics at the current bands
    python scripts/calibrate.py --sweep         # every threshold, side by side
    python scripts/calibrate.py --review        # the unlabelled pool, ranked

    # a detector built out of this file: the held-out half is the only number
    python scripts/calibrate.py --detector embedding --holdout --sweep
