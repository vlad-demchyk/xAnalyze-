# Read each distinct passage once, ever

## Problem

A crawl of ten pages of one site produced 573 text blocks. **236 of them were
distinct.** `Tel. +39 0432 924815` was read 26 times, the site's email 26
times, a menu label 23 times - because a header and a footer appear on every
page, and nothing upstream noticed.

Both detectors pay for this. The offline pass does 573 analyses instead of
236, which is cheap but pointless. The judge does 72 network round trips
instead of 30, and on the Claude Code route each round trip is a `claude -p`
process start: measured at ~7 seconds, so the waste is minutes of wall clock
and real money, spent to ask the same question of the same string.

Separately, the judge is **not deterministic**. Two runs of the same site
with the same flags returned 6 findings and then 24. A reader cannot act on a
number that moves like that, and a comparison between runs cannot mean
anything.

## Acceptance criteria

### A. One reading per distinct passage, per run

1. Two blocks whose text is the same after normalisation are analysed once.
   Normalisation collapses whitespace and masks machine-generated
   identifiers, so a menu that renders with a fresh uuid per page is still
   one passage.
2. The language hint is part of the identity: the same string detected as
   Italian on one page and English on another is two questions, and the
   detectors answer them differently.
3. **Nothing is lost.** Every occurrence still produces its own finding, with
   its own page URL, because a fix has to visit each page. Deduplication
   changes what is *asked*, never what is *reported*.
4. Both detectors benefit. The offline pass and the judge read the same
   distinct list; a second list would be a second answer to "what is distinct
   here".
5. Deduplication spans the whole run, not one page. A shared header is
   exactly the case worth collapsing and it is invisible within a page.
6. Progress is reported by batch, since the work is no longer per page:
   `# [AI patterns 12/30 batches]`.

### B. One reading per distinct passage, across runs

7. A judged verdict is cached on disk, keyed by the passage, the detector,
   the model, the effort and the prompt version. A second run of the same
   site re-reads nothing it has already judged.
8. Changing the model, the effort or the prompt invalidates the entry: a
   verdict is an answer to a specific question asked of a specific model, and
   serving it after any of those changed would be answering a question nobody
   asked.
9. The cache is what makes a repeat run deterministic. This is the honest
   fix available: no route here exposes temperature or a seed, so identical
   output cannot be requested from the model - it can only be remembered.
10. The cache can be inspected and cleared, and a run can be told to ignore
    it, because a cached wrong answer must not be un-fixable.
11. A cache miss is silent and a cache hit is reported, so "this run cost
    nothing" is visible rather than inferred from the clock.

## Non-goals

- Making a single fresh judgement deterministic. It is not, no flag here
  makes it so, and pretending otherwise by averaging two passes would double
  the cost to hide the variance rather than report it.
- Deduplicating *audit* findings at the source. Those already group at
  report time and their cost is local parsing, not a round trip.
