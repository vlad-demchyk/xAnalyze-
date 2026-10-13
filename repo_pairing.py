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
import hashlib
from copy import deepcopy


def content_index(files) -> dict:
    """`{identity: [candidate, ...]}`; repeated copy keeps every source."""
    index: dict = {}
    seen: dict = {}
    for file in files or ():
        raw = getattr(file, "raw_text", None)
        file_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest() if raw is not None else None
        for block in getattr(file, "blocks", ()) or ():
            candidate = {"file": block.file_path, "line": block.line_number,
                         "offset": block.start, "end_offset": block.end,
                         "text": block.text, "file_hash": file_hash,
                         "text_hash": hashlib.sha256(block.text.encode("utf-8")).hexdigest(),
                         "source_range_verified": raw is not None and raw[block.start:block.end] == block.text,
                         "context": deepcopy(getattr(block, "source_context", {}) or {})}
            identity = duplicates.block_identity(block)
            location = (candidate["file"], candidate["offset"], candidate["end_offset"])
            known = seen.setdefault(identity, set())
            if location not in known:
                known.add(location)
                index.setdefault(identity, []).append(candidate)
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
    """Keep every textual candidate; choose only an exact unique occurrence.

    Returns how many passages have candidates, including ambiguous matches.
    Language hints can differ between rendered and source readings, so all
    candidates for the text are considered. DOM/locale/component context
    ranks the candidates without treating a hint as proof of origin.
    """
    by_text: dict = {}
    for (text, _language), sources in (index or {}).items():
        candidates = by_text.setdefault(text, {})
        for source in sources:
            candidates.setdefault((source["file"], source["offset"], source["end_offset"]), source)
    matched = 0
    for block in blocks or ():
        identity = duplicates.block_identity(block)
        sources = by_text.get(identity[0], {}).values()
        block.source_file, block.source_line = "", None
        block.source_mapping, block.source_candidates = "unmapped", []
        context = getattr(block, "source_context", {}) or {}
        candidates = []
        for source in sources:
            candidate = deepcopy({k: v for k, v in source.items() if k != "text"})
            candidate["match"] = "exact" if source["text"] == block.text else "normalized"
            candidate["context_matches"] = [key for key in ("locale_key", "element", "component_file")
                if context.get(key) and context[key] == candidate["context"].get(key)]
            candidates.append(candidate)
        candidates.sort(key=lambda c: (-len(c["context_matches"]), c["file"], c["offset"]))
        block.source_candidates = candidates
        if not candidates:
            continue
        block.source_mapping = "ambiguous" if len(candidates) > 1 else (
            "exact-unique" if candidates[0]["match"] == "exact" else "inferred")
        if block.source_mapping == "exact-unique":
            block.source_file = candidates[0]["file"]
            block.source_line = candidates[0]["line"]
        matched += 1
    return matched


def mapping_for(block) -> dict:
    """Detached mapping evidence, including context hints that do not prove origin."""
    status = getattr(block, "source_mapping", "")
    if not status:
        return {}
    candidates = deepcopy(getattr(block, "source_candidates", []) or [])
    eligible = status == "exact-unique" and len(candidates) == 1 and candidates[0]["source_range_verified"]
    return {"status": status, "candidates": candidates,
            "context": {"selector": getattr(block, "dom_path", ""),
                        **deepcopy(getattr(block, "source_context", {}) or {})},
            "auto_fix_eligible": eligible, "requires_hash_revalidation": True,
            "source_map_status": "unknown"}


def mapping_lines(mapping, lang="en") -> list[str]:
    """The same candidate list in GUI and human report exports."""
    if not mapping or mapping.get("status") == "unmapped":
        return []
    from i18n.translations import t
    lines = [t("source_mapping_" + mapping["status"].replace("-", "_"), lang)]
    for candidate in mapping.get("candidates", []):
        lines.append(t("finding_file_line", lang, path=candidate["file"], line=candidate["line"]))
    return lines
