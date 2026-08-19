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

## What is missing, and why it is not filled in

There are no Ukrainian `human` entries yet. There is no local source of
Ukrainian product copy whose author is certain, and labelling the xFormat
strings "human" because they read that way would be exactly the mistake this
file exists to avoid. Until someone who knows confirms them, per-language
metrics for Ukrainian are reported as unavailable rather than estimated.

## Running it

    python scripts/calibrate.py                 # metrics at the current bands
    python scripts/calibrate.py --sweep         # every threshold, side by side
    python scripts/calibrate.py --review        # the unlabelled pool, ranked
