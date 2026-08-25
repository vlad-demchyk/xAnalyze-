"""What a media file says about how it was made.

Every other check in this tool reads text, or the markup around it. This one
reads the fields inside an image, and it is deliberately **not** an
AI-image detector.

The difference matters more here than anywhere else in the product. There is
no honest way to look at pixels and say a model drew them: the classifiers
that claim to are scoring, and a score presented as a fact is exactly what
`detectors/claude_watermark_stub.py` refuses to ship for text. What there
*is* is a set of fields that generators write into the file themselves - and
reading a statement a file makes about itself is a fact in the same sense a
zero-width character is a fact.

So this reads declarations, and only declarations:

* **IPTC `DigitalSourceType`**, in XMP. `trainedAlgorithmicMedia` is the
  standard's own term for "a model made this", and it is what Google Images
  reads. The strongest thing short of a signature.
* **PNG text chunks.** Stable Diffusion and the interfaces around it write
  the prompt, the model and the seed into `parameters`, `prompt` or
  `workflow` as plain text. A local generation gives itself away completely.
* **EXIF/XMP tool names.** `Software: Midjourney`, `CreatorTool: Adobe
  Firefly`.
* **The presence of a C2PA manifest**, by its container marker only. This
  build cannot verify the signature, and says so rather than either ignoring
  the manifest or pretending to have read it.

**The absence of all of it means nothing at all.** A screenshot, a re-save,
or an upload through most social platforms strips every field above. This is
the single most important sentence about this module, and it is why the
finding is worded as "the file says" and never as "this is AI". A run that
finds nothing has found nothing - not a human photographer.

Not a `Detector`: that interface is `TextBlock -> TextSpan`, offsets into
text, and an image has no offsets. An `Issue` - a thing found at a place in
a document - is the shape this already is, so it joins the audit beside
`audit/rules/provenance.py`, which is the same idea one layer up.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

#: Files worth opening. Formats that carry metadata at all: a `.svg` is
#: markup and goes through the ordinary audit instead.
MEDIA_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".gif")

#: What the file turned out to say. Ordered by how much it says, because
#: that is also the order they are looked for.
DECLARED_AI = "declared_ai"          # the file names itself as model-made
GENERATOR_TOOL = "generator_tool"    # a generator's name, without the claim
SIGNED_UNVERIFIED = "signed"         # a C2PA manifest this build cannot read
NOTHING = "nothing"                  # no provenance fields at all
UNREADABLE = "unreadable"            # not an image, or truncated

#: The IPTC value that means a model made it. Matched as a substring of the
#: field, because the full value is a URL into the IPTC vocabulary and
#: producers write it with and without the scheme.
_TRAINED_ALGORITHMIC = "trainedalgorithmicmedia"

#: Generators whose name appears in a tool field. Substring of the field, so
#: "Adobe Firefly 2" and "Midjourney v6" both match; each entry is
#: distinctive enough on its own that a photograph will not carry it.
_GENERATORS = (
    "midjourney", "dall-e", "dall·e", "stable diffusion", "stablediffusion",
    "automatic1111", "comfyui", "adobe firefly", "firefly", "imagen",
    "flux", "leonardo.ai", "ideogram", "recraft", "nightcafe",
)

#: PNG text keys the local-generation stack writes. `parameters` is
#: Automatic1111's, `prompt` and `workflow` are ComfyUI's; `Software` and
#: `Comment` are generic and only count when they name a generator.
_PROMPT_KEYS = ("parameters", "prompt", "workflow", "sd-metadata",
                "invokeai_metadata")
_TOOL_KEYS = ("software", "creatortool", "comment", "description",
              "xmp:creatortool", "generator")

#: How a C2PA store announces itself inside the container: a `caBX` chunk in
#: PNG, a JUMBF box labelled `c2pa` in JPEG and the ISO-BMFF formats. Found
#: by byte search rather than parsed - the point here is only to know that
#: one is present.
_C2PA_MARKERS = (b"caBX", b"c2pa", b"jumb")

#: How much of a file is searched for those markers. The store sits near the
#: front in every format that carries one, and reading whole images to find
#: a four-byte tag would turn a scan of an assets folder into a scan of a
#: disk.
_MARKER_BYTES = 512 * 1024

#: Longest evidence string kept. Enough to recognise a prompt, short enough
#: that a report stays a report - some generators write kilobytes of JSON.
_EVIDENCE_CHARS = 300


@dataclass
class Provenance:
    """What one file says about itself."""
    kind: str = NOTHING
    #: The generator named, lowercase, or "" when nothing named one.
    tool: str = ""
    #: Which field carried it: `png:parameters`, `exif:Software`,
    #: `xmp:DigitalSourceType`, `container:c2pa`. Named so a reader can go
    #: and look at the same field rather than take this on trust.
    marker: str = ""
    #: The value itself, trimmed. The evidence line.
    detail: str = ""
    #: Set when the file could not be read at all.
    error: str = ""

    @property
    def says_something(self) -> bool:
        return self.kind not in (NOTHING, UNREADABLE)


def _clip(value: str) -> str:
    text = " ".join(str(value).split())
    return text[:_EVIDENCE_CHARS - 1] + "…" if len(text) > _EVIDENCE_CHARS else text


def _generator_in(value: str) -> str:
    low = str(value).lower()
    for name in _GENERATORS:
        if name in low:
            return name
    return ""


def _fields_of(image) -> dict:
    """Every text field this build can reach, as `label -> value`.

    One flat dictionary rather than three passes, because the rules below
    care about what was said and not about which container said it - except
    for the label, which is kept so the finding can name the field.
    """
    fields: dict = {}
    for key, value in (getattr(image, "text", None) or {}).items():
        fields[f"png:{key}"] = value
    for key, value in (image.info or {}).items():
        if isinstance(value, str) and f"png:{key}" not in fields:
            fields[f"info:{key}"] = value
    try:
        exif = image.getexif()
    except Exception:  # noqa: BLE001 - a broken EXIF block is not a crash
        exif = {}
    #: 0x0131 Software, 0x013B Artist, 0x8298 Copyright, 0x010E ImageDescription
    for tag, label in ((0x0131, "Software"), (0x013B, "Artist"),
                       (0x8298, "Copyright"), (0x010E, "ImageDescription")):
        value = exif.get(tag) if hasattr(exif, "get") else None
        if value:
            fields[f"exif:{label}"] = value
    return fields


#: The XMP packet, wherever a format chose to put it. Read out of the raw
#: bytes rather than through `Image.getxmp()`, for two reasons that both
#: matter here.
#:
#: `getxmp()` needs `defusedxml`, which is not installed - so it returned
#: nothing at all and warned once per file, which meant the strongest field
#: this module reads was silently unavailable in every build. That is
#: exactly the kind of quiet hole this module exists to close.
#:
#: And parsing is not wanted anyway. One field is needed, out of a packet
#: that arrives inside an untrusted file; a targeted search has no XML
#: parser to attack, which is the whole reason `defusedxml` exists.
_XMP_PACKET = re.compile(rb"<x:xmpmeta.*?</x:xmpmeta>", re.S)

#: `<Iptc4xmpExt:DigitalSourceType>value</…>` and the attribute spelling
#: `Iptc4xmpExt:DigitalSourceType="value"`, which producers use about
#: equally often.
_XMP_FIELDS = ("DigitalSourceType", "CreatorTool", "Software", "Credit",
               "DigitalSourceFileType")


def _xmp_fields(path: Path) -> dict:
    """`label -> value` for the XMP fields this module knows how to use."""
    try:
        with open(path, "rb") as handle:
            head = handle.read(_MARKER_BYTES)
    except OSError:
        return {}
    packet = _XMP_PACKET.search(head)
    if packet is None:
        return {}
    try:
        text = packet.group(0).decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return {}
    found = {}
    for name in _XMP_FIELDS:
        element = re.search(rf"<[\w-]*:?{name}[^>]*>([^<]+)<", text)
        attribute = re.search(rf'[\w-]*:?{name}\s*=\s*"([^"]+)"', text)
        match = element or attribute
        if match and match.group(1).strip():
            found[f"xmp:{name}"] = match.group(1).strip()
    return found


def _has_c2pa(path: Path) -> bool:
    try:
        with open(path, "rb") as handle:
            head = handle.read(_MARKER_BYTES)
    except OSError:
        return False
    return any(marker in head for marker in _C2PA_MARKERS)


def read_provenance(path) -> Provenance:
    """Read one file. Never raises: an unreadable file is an answer."""
    path = Path(path)
    try:
        from PIL import Image
    except ImportError:  # pragma: no cover - Pillow ships with the app
        return Provenance(kind=UNREADABLE, error="Pillow is not installed")

    try:
        with Image.open(path) as image:
            image.load()
            fields = _fields_of(image)
    except Exception as exc:  # noqa: BLE001 - a bad file is data, not a crash
        return Provenance(kind=UNREADABLE, error=str(exc))
    fields.update(_xmp_fields(path))

    # 1. The standard's own claim, which is the strongest thing short of a
    #    signature: the file states that a model made it.
    for label, value in fields.items():
        if _TRAINED_ALGORITHMIC in str(value).lower().replace(" ", ""):
            return Provenance(kind=DECLARED_AI, marker=label,
                              tool=_generator_in(value), detail=_clip(value))

    # 2. A prompt block. Only the local-generation stack writes these, and
    #    it writes the model and the seed with them.
    for label, value in fields.items():
        key = label.split(":", 1)[1].lower()
        if key in _PROMPT_KEYS and str(value).strip():
            return Provenance(kind=DECLARED_AI, marker=label,
                              tool=_generator_in(value) or "stable diffusion",
                              detail=_clip(value))

    # 3. A generator's name in a tool field. Weaker: it says which program
    #    touched the file, not that the pixels came from a model - an image
    #    edited in a generator's app carries the same string.
    for label, value in fields.items():
        key = label.split(":", 1)[1].lower()
        name = _generator_in(value)
        if name and (key in _TOOL_KEYS or key.endswith("software")):
            return Provenance(kind=GENERATOR_TOOL, marker=label, tool=name,
                              detail=_clip(value))

    # 4. Signed, and not by us. Reported rather than skipped: a manifest is
    #    the strongest provenance there is, and silently ignoring one would
    #    make a file that documents itself look like a file that does not.
    if _has_c2pa(path):
        return Provenance(kind=SIGNED_UNVERIFIED, marker="container:c2pa",
                          detail="Content Credentials present, not verified "
                                 "by this build")
    return Provenance(kind=NOTHING)


@dataclass
class MediaScan:
    """What the media pass looked at, and what it found.

    Counted for the same reason `ScanDiagnostics` is: nothing found and
    nothing looked at produce the same empty list, and they are opposite
    answers.
    """
    files_read: int = 0
    skipped_ignored: int = 0
    unreadable: int = 0
    findings: list = field(default_factory=list)


def scan_media(root, config=None, progress_cb=None) -> MediaScan:
    """Walk `root` for media files and read what each one says.

    Uses the repository scanner's own ignore decision, so the two walks
    cannot disagree about `node_modules/`.
    """
    from repo_scanner import ScanConfig, build_matcher, is_ignored

    config = config or ScanConfig()
    root = Path(root)
    matcher = build_matcher(config.ignore_patterns)
    scan = MediaScan()
    if not root.is_dir():
        return scan

    for path in sorted(root.rglob("*")):
        if scan.files_read >= config.max_files:
            break
        if path.is_dir() or path.suffix.lower() not in MEDIA_SUFFIXES:
            continue
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            continue
        if is_ignored(rel, matcher):
            scan.skipped_ignored += 1
            continue
        if progress_cb:
            progress_cb(rel)
        scan.files_read += 1
        found = read_provenance(path)
        if found.kind == UNREADABLE:
            scan.unreadable += 1
            continue
        if found.says_something:
            scan.findings.append((str(path), found))
    return scan


# --------------------------------------------------------------- as findings

#: One rule id per kind, because they are three different statements and a
#: reader has to be able to tell them apart in a report, a filter and a
#: suppression file.
RULE_OF = {
    DECLARED_AI: "bp-ai-media-declared",
    GENERATOR_TOOL: "bp-ai-media-tool",
    SIGNED_UNVERIFIED: "bp-ai-media-signed",
}


def as_issue(path: str, found: "Provenance"):
    """One `Provenance` as an audit `Issue`.

    MINOR, and that is not timidity. The audit's severities measure harm to
    a reader, and a generated image does no harm - it is information, and
    what to do about it is a decision this tool has no standing to make.
    """
    from audit.base import BEST_PRACTICES, EXACT, MINOR, Issue

    return Issue(
        rule_id=RULE_OF[found.kind], severity=MINOR, category=BEST_PRACTICES,
        confidence=EXACT, source=path, selector="", line=None,
        snippet=found.detail,
        details={"marker": found.marker, "tool": found.tool or "",
                 "value": found.detail},
        engine="media",
    )


def as_documents(scan: "MediaScan") -> list:
    """A `DocumentReport` per file that said something.

    One per file rather than one per finding, because that is the unit the
    rest of the audit reports in and the unit a reader opens.
    """
    from audit.engine import DocumentReport

    return [DocumentReport(source=path, issues=[as_issue(path, found)],
                           elements_checked=1)
            for path, found in scan.findings]
