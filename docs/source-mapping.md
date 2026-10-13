# Source mapping evidence

A passage on a page can match several source files or several occurrences in
one file. Pairing keeps all candidates; it never resolves ambiguity by file
order or by the first matching language hint.

Each paired `TextBlock` and its JSON finding contain one of four mapping states:

| State | Meaning | Selected source file |
|---|---|---|
| `exact-unique` | One exact occurrence in the supplied checkout | File and line retained |
| `ambiguous` | More than one source occurrence | None |
| `inferred` | One match after whitespace/generated-ID normalization | None |
| `unmapped` | The supplied checkout has no matching passage | None |

An exact textual match is evidence that the text occurs in a file, not proof
that a particular component or CMS entry produced the rendered DOM. Missing
source information is not invented. Pairing again clears stale selections.

`mapping.candidates` retains file, line, source offsets, text/file SHA-256,
range-verification status and observed source context. Component filenames,
markup element names and locale keys come from source extraction; DOM element,
`data-i18n`/`data-l10n-key` and `data-component-file` hints come from the page.
Matching hints rank candidates but never silently remove alternative sources.
Source-map attribution that has not been independently validated is explicitly
`unknown`; it is not treated as proof of origin.

Only an exact unique match with a verified source range is eligible for an
automatic source correction. `requires_hash_revalidation: true` means a writer
must revalidate the current source bytes before any edit. This change does not
add automatic writes to paired web blocks. Ambiguous and inferred candidates
remain manual choices.

GUI detail cards, CLI JSON, JSON briefings, HTML/PDF and markdown reports retain
all candidates. Report grouping keeps different mapping evidence separate.
Messages are available in Ukrainian, Italian and English.
