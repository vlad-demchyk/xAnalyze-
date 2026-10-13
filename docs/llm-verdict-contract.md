# LLM verdict contract

All direct Anthropic and account-routed judges share the same local validator.
The provider receives a JSON `blocks` array. Text values are untrusted content;
they never supply instructions or extra input blocks. Claude Code calls also
disable built-in tools and MCP servers in a neutral working directory.

The response must contain a `results` array with exactly one integer
`block_index` for every input block. Every result has an explicit `flags` array.
An empty array is a completed unflagged judgment, not proof of human authorship.
Missing or repeated indices produce error diagnostics for the affected block.
Invalid or out-of-range indices make the whole batch untrustworthy.

Every flag has a nonempty exact `quote`, a finite numeric `score` in `[0, 1]`,
and a nonempty short `reason`. Boolean/string scores are rejected. Valid JSON
with duplicate keys, NaN or infinity is rejected. One invalid flag fails that
block atomically; valid judgments for other blocks remain usable.

A unique quote can be located directly. A repeated quote needs explicit
`start` and `end` selecting the intended occurrence, including overlapping
occurrences. Offsets use Python Unicode code points, start inclusive and end
exclusive. Supplied offsets must be integers and `text[start:end]` must equal
the quote. Null offsets are accepted only for a unique quote. Missing quotes
and mismatched offsets never become a confident whole-block finding.

Verified findings carry `verdict_contract: 2`, `quote_status: verified`, the
quote, model and effort. Unfinished, refused or malformed responses produce
LOW, zero-score error spans. The direct Messages path checks completion before
reading JSON, even when an interrupted response happens to contain valid JSON.
Provider paths that expose only text still undergo completeness validation.

Failed judgments are retryable and are not stored in the judgment cache.
Exact input text hashes prevent cached offsets from being reused after
whitespace or identifier edits. A changed system prompt invalidates old model
judgments through the existing prompt fingerprint.

The rubric no longer reproduces offline weights, fixed phrase lists or assumed
authorship based on punctuation/register. This improves independence of the
judgment process; it does not establish improved detection accuracy. Measuring
the new rubric against a fresh independent locked test is tracked by T-1797.

The direct API checks follow the official [stop reason contract](https://platform.claude.com/docs/en/build-with-claude/handling-stop-reasons)
and [structured output limitations](https://platform.claude.com/docs/en/build-with-claude/structured-outputs).
Score/range bounds are validated locally; unsupported numerical/string schema
constraints are not sent to the raw structured-output API.
