# Finding JSON contract

The CLI, report adapters and audit checkpoints share `finding_contract.py`.
The top-level JSON and each new finding carry `schema_version: 1`. This is an
additive format: the old `rule`, `file`, `line`, `source`, `confidence`, `text`,
`snippet` and `fix_snippet` keys retain their meaning. Readers should ignore
unknown additive keys. The deserializer accepts legacy records without a version
and rejects unsupported versions instead of interpreting them as version 1.

`finding_type` is `issue`, `text-span` or `report-finding`. All model fields,
including nested rule details, survive serialization. Snippets and replacement
text are complete; display renderers choose their own presentation limits.
Report findings retain their original detached machine record in `evidence`.

## Locations and evidence

`location.source` identifies the file or page. `location.line` is a one-based
source line when known; null means unavailable. `location.selector` identifies a
DOM element when known. For backward compatibility, a text finding's top-level
`source` still names its signal family, such as `style` or `characters`.

A text `range` has start-inclusive and end-exclusive Python character offsets.
`coordinate_system: source-text` means offsets into the decoded source file.
`coordinate_system: block-text` means offsets into the extracted block named by
`block_id`. Neither is a UTF-8 byte offset. An audit issue has `range: null` when
the engine did not provide exact character offsets; a line or selector is not
converted into an invented range.

`evidence_status` is `observed`, `scored`, `advisory`, `unknown` or `error`.
Text detector scores remain detector-specific. `observed` says the engine
recorded a fact; it does not validate authorship or source mapping. Errors and
checks requiring a browser keep their uncertainty rather than becoming findings
at exact certainty. Unknown source mapping confidence remains explicit until
independent mapping validation is implemented.

## Coverage

`audit` and `fullscan` JSON and JSON briefings include `coverage`. It records
per-document static rule executions and skipped rules, browser engine execution
states, unresolved findings, errors, selected rules, effective options, engine
versions and artifact hashes, scan walk diagnostics, and content hashes.
Human HTML/PDF and markdown reports show a translated coverage summary.

Coverage is captured before certainty/category views hide unresolved findings.
Clean source documents remain in coverage even when the finding list omits them.
`checked` means the recorded scope was checked, not that the target is defect-free.
`unknown` means evidence of coverage is missing. `incomplete` records known errors,
unresolved findings or walk limits. A skipped optional browser pass remains skipped.
Auxiliary passes without per-rule instrumentation have unknown coverage.

`content_hashes` use SHA-256 of decoded text encoded as UTF-8, identified by
`hash_coordinate_system: decoded-text-utf8`. They describe text already read by
the pass, not original transport bytes or every transient DOM state. Engine
versions unavailable at runtime are null; source-rule and vendor-script hashes
identify artifacts when they are available. Options never include credentials.

JSON briefings keep complete `findings` and `content_findings` alongside grouped
human summaries. Resume checkpoints retain document kinds, checks, hashes,
browser failures and scan diagnostics. Old checkpoints remain readable with
unknown coverage where their original format recorded no execution facts.
