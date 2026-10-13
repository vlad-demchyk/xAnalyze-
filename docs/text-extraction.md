# Text extraction evidence

Website text blocks retain decoded source characters in `text` and `raw_text`.
NBSP, zero-width characters and Unicode composition are not removed before
character checks. `normalized_text` is a separate whitespace-normalized view;
`normalization_map` contains compact `[normal_start, normal_end, raw_start,
raw_end]` segments in Unicode code points. `normalized_range_to_raw` reverses a
valid analysis range. Normalization does not perform Unicode NFKC conversion.

Short text remains available for character checks. `analysis_eligible: false`
keeps the existing 20-character website wording floor explicit. Offline style
checks and LLM batches skip those blocks; character checks still read them.
Raw variations are distinct for text detection and judgment caching so an NBSP
finding is not copied to a different occurrence containing an ordinary space.

Static extraction excludes known `hidden`, inline display/content-visibility,
opacity and visibility exclusions, including ancestors. `aria-hidden` alone
does not hide pixels. Stylesheet-dependent visibility is `unknown`; raw HTML
is not presented as a measured rendered reading. Nested declared language is
recorded per text segment separately from the detector's guessed language.

The browser captures raw nodes, native `innerText`, CSS/layout visibility and
the matching HTML in one synchronous probe in Qt's isolated application world.
It reads open shadow roots and accessible same-origin frames, records their
context paths, and reports inaccessible frames and exceeded budgets as unknown.
Closed shadow roots remain unknown. Visibility describes CSS and rendered
layout, including offscreen copy; occlusion and pixel contrast are not measured.

Authored `aria-label`, alt, title, placeholder and referenced-label text are
explicit channels. They are declared label sources, not a claim that this
collector implements the full accessible-name algorithm. Password/input values
are not read. Referenced label text may intentionally be visually hidden.

Each finding keeps its block-text code-point range and exact native DOM ranges
where known. DOM text-node/attribute offsets use UTF-16 units; `context_path`
identifies frame/shadow boundaries. No HTML source line is invented for a dynamic
text node. Fullscan JSON includes the text blocks, normalization maps and
extraction coverage beside findings; JSON briefings carry the same finding facts.

Browser-mode fullscan now renders every crawled page for text, including
server-rendered pages whose styles hide copy. This costs a render per page;
`--no-browser` retains static extraction with unknown CSS visibility. The
explicit GUI browser reader uses the same snapshot. `--within` limits the text
probe to the requested subtree. Snapshot script-preparation failures finish
with diagnostic errors instead of leaving the Qt event loop waiting.
