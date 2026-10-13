# Independent detector validation

The old `corpus/*.jsonl` files are historical regression material. Their
holdout has already been used to change rules and thresholds. It cannot
establish independent release quality. `scripts/calibrate.py` now says so;
its historical sweeps remain useful for diagnostics. Existing production
scores, thresholds and embedding reference selection are unchanged.

`scripts/benchmark.py` separates preparation, calibration and one locked test:

```sh
python scripts/benchmark.py inspect dataset.json
python scripts/benchmark.py partition unassigned.json --seed study-v1 --output dataset.json
python scripts/benchmark.py unicode dataset.json --output dataset-with-unicode.json
python scripts/benchmark.py freeze dataset.json --detector offline --output protocol.json
python scripts/benchmark.py run dataset.json --protocol protocol.json --output results.json
python scripts/gate.py --quality-report results.json
```

Outputs are new files, never overwrites. `run` exits 2 when measured quality
does not meet the declared requirements; malformed inputs exit 1. Without
an independent report, the release gate reports historical diagnostics and
fails readiness. The current Italian historical holdout recall is 4/11,
36.4%, below its existing 50% release floor. Missing groups also fail; the
English/Ukrainian aggregate cannot hide Italian. `--skip-quality` explicitly
skips this requirement and reports that only selected checks passed.

## Dataset contract

The manifest is one JSON object with `schema_version: 1`, a `dataset_id`,
`purpose: validation` (or `fixture` for synthetic plumbing checks) and `samples`.
Each sample has:

* `id`, original `text`, `label` (`human`, `model`, `mixed`), `language`,
  `register`, `condition`, `split` (`reference`, `calibration`, `test`).
* `groups` with explicit `author_id`, `site_id`, `source_id`, `template_id`.
* `provenance` with `source`, `date`, `license`, `verified_by`, `evidence`, and
  an explicit boolean `public_benchmark`. Model/mixed samples also require
  `generator` with `name`, `model_version`, `prompt`, `date`.
* Optional `parents` sample IDs for edited/transformed/mixed lineage.
* `gold_spans`: original Unicode code-point `[start, end]` pairs, or null
  when unannotated. Human gold spans must be empty. Missing span annotation
  is unknown, never an invented whole-text ground truth.

Unknown authorship is not a human negative. Supplied provenance is a recorded
assertion requiring review, not automatic proof that a person wrote a text.
No existing unlabelled pool is relabelled. New labels require confirmed authorship.
Model generator/prompt/date fields are never guessed for historical examples.

Samples sharing any source-group field, parent or canonical duplicate belong
to one connected component and cannot cross partitions. Canonical identity
uses NFKC, case folding, whitespace and removal of format characters only for
leakage checks; input text and span offsets remain original. Partitioning is
deterministic under reordering. Adding/merging groups creates a new manifest
requiring review; existing split assignments are never silently rewritten.
The test must not overlap any historical corpus file. Semantic near-duplicate
and unknown pretrained-model contamination are not certified absent.

The `unicode` command derives fullwidth Latin, zero-width and NBSP formatting
variants from original samples. It retains supplied labels and group IDs,
records parent/transformation provenance and maps annotated spans to changed
code-point offsets. It does not create human ground truth or paraphrase/mixed
labels. Variants stay with their source partition and independent group count.

## Freeze and test access

Freeze scores only calibration. It chooses maximum recall under the declared
worst-case calibration FPR (including abstentions), or checks an explicitly
fixed threshold with `--fixed-threshold`. The measured test FPR is reported
as observed; no test sweep forces it to the target.

The frozen protocol hashes the complete dataset, individual test samples,
reference, model settings, source/prompt code, benchmark methodology and
dependency versions. Any change invalidates it. Test scores are not read
while fitting. The source-group guard and each original sample are rechecked
when consuming a saved report; its `passed` flag is not trusted.

Test text access is claimed atomically before inference in
`~/.xanalyze/validation/test-access`. A failed run still consumes the test;
refitting or a second run is refused. `XANALYZE_VALIDATION_LEDGER` points to
an isolated ledger for synthetic tests. Copying/renaming a protocol does not
reset exposure because keys identify canonical text, not filenames. This is
process protection on the current machine, not cryptographic attestation or
a cross-machine dataset registry.

## What is measured

Reports include confusion counts, FPR, conservative recall, conditional recall,
sample precision and precision projected to an explicitly stated prevalence,
macro-language recall, language/length/register/edit strata, coverage,
abstention/error counts, measured latency and known API cost. Missing cost
stays null. Mixed labels are excluded from binary authorship rates and use
annotated span localization. Character precision/recall and IoU merge overlapping
ranges before counting; unannotated or failed samples do not become zeros.

Nominal Wilson intervals assume independent Bernoulli observations. Reports
also count independent source groups, with separate group-event intervals:
any human false flag/abstention and all model passages detected. These group
events are not labelled document-level population FPR/recall. Repeating one
website's paragraphs cannot inflate independent group count. Sampling and
distribution assumptions still require review.

Default requirements are deliberately conservative readiness checks, not a
claim that the current tool meets them: all uk/it/en, all three length bands,
specified registers and editing conditions; recall >=50%, projected precision
>=90% at prevalence 10%, worst-case FPR <=1%, coverage >=95%, at least 30
samples per applicable class and 30 source groups. Group error upper bound
must also be <=1% and group detection lower bound >=50%. Zero errors on 20
samples does not establish a 1% FPR. Human marketing uses negative-only checks;
mixed content requires at least 30 annotated samples, IoU >=0.5 and coverage.
A policy JSON can declare a research scope, but cannot loosen release defaults.

## Adapters and remaining work

The implemented adapters use the existing offline/heuristic, embedding, direct
Claude judge and hybrid detectors. Production language guessing is used,
not the benchmark's gold language. Character findings are not AI-authorship
evidence. Unsupported lengths/languages abstain; detector failures are errors.
Embedding reads only the reference file and retains its production text-hash
selection within that file. It does not read calibration/test neighbours.

Remote inference requires both `--allow-remote` and exclusively declared public
benchmark text, with an explicit model identifier. It is off by default. Model
weights and remote response identity are not yet fully pinned for these
adapters, so their reports cannot pass release readiness. Provider-bound
session models and experimental multilingual encoder, Fast-DetectGPT,
Binoculars, Copyleaks/Pangram/GPTZero, AdaDetectGPT/ProSSD comparisons still
need their own adapters and measurements. No unavailable method is counted as
a successful negative. Anthropic watermark availability is separate from
stylistic authorship scoring and remains to be verified.

The command expects a supplied manifest with confirmed provenance. Synthetic
fixtures prove the pipeline contract, not detector accuracy. New calibration does not silently
replace a production configuration; release consumption also checks the
current offline configuration and reporting threshold.

Statistical reference: [NIST confidence intervals](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm).
Research implementations to evaluate: [Fast-DetectGPT](https://github.com/baoguangsheng/fast-detect-gpt),
[Binoculars](https://github.com/ahans30/Binoculars).
