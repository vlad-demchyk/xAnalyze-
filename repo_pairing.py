"""Matching a passage on a served page to the file that wrote it.

A finding on a website names the page. That is the address a reader visits
and the wrong address to fix anything at: the sentence lives in a template,
a component or a content file, and nothing on the page says which. `--repo`
answers that in the CLI, and this module is the answer itself, so the window
and the command line pair the same way rather than twice.

The join is `duplicates.block_identity` - the same normalise-and-mask
identity a crawl's own blocks are grouped by - so a passage matches from
either side: the rendered page, or the source that produced it.

**A passage that does not match is not a failure.** WordPress puts
`<html lang>`, canonical links and most of `<head>` in `wp_head()` rather
than in any theme file; a Next.js page's copy may arrive from a CMS. The
checkout can be entirely genuine and still explain none of a given finding,
so the pairing reports how many matched and never treats a miss as an error.
"""
from __future__ import annotations

import duplicates


def content_index(files) -> dict:
    """`{identity: block}` for every distinct passage in the scanned files.

    First occurrence wins: a passage repeated inside the repository itself -
    a shared partial, an include - still resolves to one place, matching how
    `duplicates.distinct_blocks` treats the crawled side.
    """
    index: dict = {}
    for file in files or ():
        for block in getattr(file, "blocks", ()) or ():
            index.setdefault(duplicates.block_identity(block), block)
    return index


def index_for_path(path: str, ignore_patterns=None, max_files: int = 5000,
                   scope: str = "content") -> dict:
    """Walk a checkout and build the index for it.

    `scope` is deliberately `content` by default and not the run's own scope:
    what a page shows is user-facing copy, so pairing it against a scan that
    also read comments and docstrings would offer a docstring as the source
    of a headline.
    """
    from repo_scanner import ScanConfig, scan_repo

    files = scan_repo(str(path), ScanConfig(
        ignore_patterns=list(ignore_patterns or []),
        max_files=max_files, scope=scope))
    return content_index(files)


def pair_blocks(blocks, index) -> int:
    """Fill in `source_file`/`source_line` on every block that matches.

    Returns how many did. The number is the honest half of this feature: a
    run that paired 3 of 40 passages has pointed at the wrong checkout, and
    a surface that shows only the three matches would never say so.

    **Two passes, and the second one exists because of the language.**
    `block_identity` is `(text, language_hint)`, which is right for grouping
    passages *within* one reading - the same string read as Italian and as
    English is two questions for a detector. Across two readings it is too
    strict: a crawled page takes its hint from `<html lang="uk">` while the
    same sentence in a `.tsx` file is guessed from the sentence itself, so an
    English heading on a Ukrainian site is `uk` on one side and `en` on the
    other and never matches. The text is the same text; when the strict key
    misses, the normalised text alone is asked, which cannot produce a wrong
    pairing - identical copy is the same passage whichever language either
    side thought it was in.
    """
    if not index:
        return 0
    by_text: dict = {}
    for (text, _language), source in index.items():
        by_text.setdefault(text, source)
    matched = 0
    for block in blocks or ():
        identity = duplicates.block_identity(block)
        source = index.get(identity) or by_text.get(identity[0])
        if source is None:
            continue
        block.source_file = getattr(source, "file_path", "") or ""
        block.source_line = getattr(source, "line_number", None)
        matched += 1
    return matched
