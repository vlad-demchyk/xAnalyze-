"""What an SPFx repository says about the web parts it ships.

A SharePoint solution is not one deliverable. The repositories this was
measured against hold **35** and **19** web parts, each its own project with
its own manifest, and each rendered into somebody else's page as one subtree
among many. Three questions follow, and they need three different answers:

* *one web part, as code* - the folder is the scope, and repo mode already
  reads it that way;
* *one web part, on the site* - `--within` confines the audit to its subtree
  (`audit/within.py`);
* *this repository's web parts, across the whole site* - which is this
  module: read what the repository ships, then recognise those parts
  wherever they appear, and leave the tenant's own page out of the answer.

With no parameters at all and a repository given, the answer stays the whole
site: the repository is then used to name the file behind a finding, not to
narrow what is looked at.

**How a part is recognised in a page.** Its manifest carries a GUID that
SharePoint puts in the DOM (`data-sp-web-part-id`, `data-sp-feature-instance-id`
and friends), and its own stylesheet compiles to CSS-module class names -
`c106Notifiche_1a2b3c` - whose stem is the name the developer wrote. The
GUID is exact and is tried first; the class stem is the fallback for a part
whose container the page does not tag.

**Manifests are JSONC.** `//` comments and trailing commas are what the SPFx
generator writes, and `json.loads` refuses both - so a reader that assumes
JSON finds no web parts in any real solution and reports it as "none".
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

#: How many manifests one repository is read for. The measured repositories
#: hold 35 and 19; a ceiling exists so a `node_modules` that slipped past the
#: exclusions cannot turn discovery into a walk of the disk.
MAX_MANIFESTS = 200

_TRAILING_COMMA = re.compile(r",(\s*[}\]])")


def read_jsonc(text: str):
    """Parse JSON with comments and trailing commas, or raise `ValueError`.

    Walked character by character rather than matched with a regex, because
    a comment can contain a quote and a string can contain `//`. Both are in
    every SPFx manifest the generator writes: line 2 is a `$schema` URL, and
    line 7 is

        // The "*" signifies that the version should be taken from package.json

    A regex that finds string literals first reads `"*"` inside that comment
    as a string and leaves the rest of the comment in the document. Measured
    on a real solution: 30 of its 33 manifests failed to parse that way, and
    the repository looked like it shipped two web parts instead of 32.
    """
    out: list = []
    index = 0
    length = len(text or "")
    in_string = False
    while index < length:
        char = text[index]
        if in_string:
            out.append(char)
            if char == "\\" and index + 1 < length:
                out.append(text[index + 1])
                index += 2
                continue
            if char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            out.append(char)
            index += 1
            continue
        if char == "/" and index + 1 < length:
            following = text[index + 1]
            if following == "/":
                while index < length and text[index] not in "\r\n":
                    index += 1
                continue
            if following == "*":
                end = text.find("*/", index + 2)
                index = length if end == -1 else end + 2
                out.append(" ")
                continue
        out.append(char)
        index += 1
    cleaned = _TRAILING_COMMA.sub(r"\1", "".join(out))
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(str(exc)) from exc


@dataclass
class WebPart:
    """One shipped web part, and how to find it in a rendered page."""
    alias: str
    id: str
    #: The manifest, relative to the repository root - the evidence.
    manifest: str
    title: str = ""
    #: Class-name stems from the part's own SCSS modules, lower-cased.
    class_stems: tuple = field(default_factory=tuple)

    def selectors(self) -> list:
        """CSS selectors that find this part in a page, strongest first.

        The GUID is exact: SharePoint writes it into the container it
        creates for the part. The class stem is a prefix match, because the
        compiler appends a hash that changes with every build.
        """
        found = []
        if self.id:
            for attribute in ("data-sp-web-part-id", "data-sp-feature-instance-id",
                              "data-webpart-id", "data-instance-id"):
                found.append(f'[{attribute}="{self.id}"]')
        for stem in self.class_stems:
            found.append(f'[class*="{stem}"]')
        return found


def _class_stems(folder: Path) -> tuple:
    """Class names the part's own SCSS declares, without their hash.

    Read from the source rather than from the build: `lib/` and `dist/` are
    excluded from a scan by `project_profile`, and a repository checked out
    fresh has neither.
    """
    stems: set = set()
    for sheet in list(folder.glob("*.module.scss"))[:10]:
        try:
            text = sheet.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for name in re.findall(r"^\s*\.([A-Za-z][\w-]*)", text, re.M):
            stems.add(name.lower())
    return tuple(sorted(stems))


def web_parts(root: str | Path, max_manifests: int = MAX_MANIFESTS) -> list:
    """Every web part this repository ships, in path order.

    Never raises: an unreadable manifest is one this cannot use, and a
    repository that yields none simply has none as far as this can tell -
    which the caller must report as "none found", never as "none exist".
    """
    base = Path(root)
    found: list = []
    seen: set = set()
    pattern = "**/src/**/*.manifest.json"
    for manifest in sorted(base.glob(pattern))[:max_manifests]:
        parts = manifest.parts
        if "node_modules" in parts or "lib" in parts or "dist" in parts:
            continue
        try:
            data = read_jsonc(manifest.read_text(encoding="utf-8",
                                                 errors="replace"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        if str(data.get("componentType", "")).lower() != "webpart":
            continue
        identifier = str(data.get("id") or "")
        if identifier and identifier in seen:
            continue
        seen.add(identifier)
        entries = data.get("preconfiguredEntries") or [{}]
        title = ""
        if isinstance(entries, list) and entries and isinstance(entries[0], dict):
            raw_title = (entries[0].get("title") or {})
            title = (raw_title.get("default", "") if isinstance(raw_title, dict)
                     else str(raw_title))
        try:
            where = str(manifest.relative_to(base))
        except ValueError:  # pragma: no cover - manifest is always under base
            where = str(manifest)
        found.append(WebPart(
            alias=str(data.get("alias") or manifest.stem),
            id=identifier,
            manifest=where,
            title=title,
            class_stems=_class_stems(manifest.parent),
        ))
    return found
