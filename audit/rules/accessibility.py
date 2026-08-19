"""The offline accessibility rules.

Every rule here answers a question the markup alone can answer. Where a
check can only be partly done without a browser, it says so
(`confidence = NEEDS_BROWSER`) instead of pretending otherwise.

Two habits run through the file:

* **Report the element, not the page.** A finding names one element and
  shows its opening tag, so the fix has an address.
* **Derive the fix when the markup allows it.** `fix_snippet` is filled in
  when the correction follows from what is already there — adding
  `alt=""` to a spacer image, adding `type="button"`, removing a positive
  `tabindex`. It is left empty when the fix needs a human decision, because
  a generated `alt="image"` is worse than no alt text at all: it silences
  the error and tells the reader nothing.
"""
from __future__ import annotations

import re

from ..base import (
    ACCESSIBILITY, CRITICAL, EXACT, MINOR, MODERATE, NEEDS_BROWSER, SERIOUS,
    Issue, Rule, RuleRegistry, is_binding, snippet_of,
)

# Elements that are focusable and actionable, i.e. need an accessible name.
_INTERACTIVE = ("a", "button", "input", "select", "textarea", "summary")
# Input types that are not text fields and label differently.
_UNLABELLED_INPUT_TYPES = {"hidden", "submit", "reset", "button", "image"}
# Link text that describes the mechanism instead of the destination.
_VAGUE_LINK_TEXT = {
    "en": {"click here", "here", "read more", "more", "link", "this", "learn more",
           "details", "download", "see more", "continue"},
    "uk": {"тут", "детальніше", "докладніше", "читати далі", "далі", "посилання",
           "більше", "дивитись", "перейти", "завантажити"},
    "it": {"clicca qui", "qui", "leggi di più", "altro", "link", "questo",
           "scopri di più", "dettagli", "continua", "vedi"},
}
_WHITESPACE_RE = re.compile(r"\s+")


def _text_of(tag) -> str:
    return _WHITESPACE_RE.sub(" ", " ".join(tag.stripped_strings)).strip()


def _accessible_name(tag) -> str:
    """A rough accessible name, in roughly the order the spec computes it.

    Rough on purpose: the full algorithm walks `aria-labelledby` across the
    document, applies CSS-generated content and consults native host
    semantics. What is implemented here is what static markup supports —
    and it is enough to answer the only question these rules ask, which is
    whether there is *any* name at all.
    """
    for attribute in ("aria-label", "title"):
        value = (tag.get(attribute) or "").strip()
        if value:
            return value
    labelled_by = (tag.get("aria-labelledby") or "").strip()
    if labelled_by:
        root = tag.find_parent() or tag
        for token in labelled_by.split():
            target = root.find(id=token) if hasattr(root, "find") else None
            if target is not None and _text_of(target):
                return _text_of(target)
    if tag.name == "img":
        return (tag.get("alt") or "").strip()
    if tag.name == "input":
        value = (tag.get("value") or "").strip()
        if tag.get("type", "").lower() in ("submit", "button", "reset") and value:
            return value
    text = _text_of(tag)
    if text:
        return text
    # An icon-only control: a nested image's alt is the name.
    nested = tag.find("img") if hasattr(tag, "find") else None
    if nested is not None:
        return (nested.get("alt") or "").strip()
    return ""


class AccessibilityRule(Rule):
    """Base for this module, so the category is declared once rather than
    repeated on seventeen classes and eventually mistyped on one."""
    category = ACCESSIBILITY


class ImageAlt(AccessibilityRule):
    id = "image-alt"
    severity = CRITICAL
    wcag = ("1.1.1",)

    def check(self, document, context) -> list:
        issues = []
        for tag in document.find_all("img"):
            if tag.has_attr("alt"):
                continue
            # A presentational image is announced as "image" with no name,
            # which is noise; an informative one loses its content entirely.
            # Static markup can't tell which this is, so the finding says
            # both and the fix offers the decorative form explicitly.
            selector, line = context.locate(tag)
            issues.append(Issue(
                rule_id=self.id, severity=self.severity, selector=selector, line=line,
                snippet=snippet_of(tag), source=context.source,
                details={"src": (tag.get("src") or "")[:120]},
                fix_snippet=_with_attribute(tag, "alt", ""),
            ))
        return issues


class ImageAltIsFilename(AccessibilityRule):
    id = "image-alt-filename"
    severity = SERIOUS
    wcag = ("1.1.1",)

    _FILENAME_RE = re.compile(r"^[\w\-. ]+\.(png|jpe?g|gif|svg|webp|avif)$", re.IGNORECASE)

    def check(self, document, context) -> list:
        issues = []
        for tag in document.find_all("img"):
            alt = (tag.get("alt") or "").strip()
            if not alt or not self._FILENAME_RE.match(alt):
                continue
            # alt="hero-banner-2.png" passes every "has alt" checker and
            # tells the listener nothing, which is why it gets its own rule.
            selector, line = context.locate(tag)
            issues.append(Issue(
                rule_id=self.id, severity=self.severity, selector=selector, line=line,
                snippet=snippet_of(tag), source=context.source, details={"alt": alt},
            ))
        return issues


class ControlName(AccessibilityRule):
    id = "control-name"
    severity = CRITICAL
    wcag = ("4.1.2", "2.4.4")

    def check(self, document, context) -> list:
        issues = []
        for tag in document.find_all(_INTERACTIVE):
            if tag.name == "input" and tag.get("type", "text").lower() in _UNLABELLED_INPUT_TYPES:
                continue
            if tag.name == "a" and not tag.has_attr("href"):
                continue  # an anchor without href is not a control
            if tag.name in ("input", "select", "textarea") and _has_label(tag, document):
                continue
            if _accessible_name(tag):
                continue
            if tag.get("aria-hidden") == "true":
                continue
            selector, line = context.locate(tag)
            issues.append(Issue(
                rule_id=self.id, severity=self.severity, selector=selector, line=line,
                snippet=snippet_of(tag), source=context.source,
                details={"element": tag.name},
            ))
        return issues


def _has_label(tag, document) -> bool:
    """A form control is named by a <label> as well as by its own attributes."""
    if tag.find_parent("label") is not None:
        return True
    control_id = tag.get("id")
    if not control_id:
        return False
    for label in document.find_all("label"):
        # `htmlFor` is React's spelling of the same attribute, and an HTML
        # parser lowercases it. Reading only `for` made every labelled JSX
        # field look unlabelled.
        target = label.get("for") or label.get("htmlfor")
        if target == control_id and _text_of(label):
            return True
    return False


class VagueLinkText(AccessibilityRule):
    id = "link-text-vague"
    severity = MODERATE
    wcag = ("2.4.4",)

    def check(self, document, context) -> list:
        issues = []
        vague = set()
        for words in _VAGUE_LINK_TEXT.values():
            vague |= words
        for tag in document.find_all("a", href=True):
            text = _text_of(tag).lower().strip(" .!?:»«\"'")
            if not text or text not in vague:
                continue
            # Screen reader users navigate by pulling up a list of every link
            # on the page, out of context. Fifteen entries reading "read
            # more" is a list of fifteen identical, useless choices.
            selector, line = context.locate(tag)
            issues.append(Issue(
                rule_id=self.id, severity=self.severity, selector=selector, line=line,
                snippet=snippet_of(tag), source=context.source,
                details={"text": _text_of(tag), "href": (tag.get("href") or "")[:120]},
            ))
        return issues


class DocumentLanguage(AccessibilityRule):
    id = "html-lang"
    page_level = True
    severity = SERIOUS
    wcag = ("3.1.1",)

    def check(self, document, context) -> list:
        html = document.find("html")
        if html is None:
            return []  # a fragment, not a document — nothing to declare on
        lang = (html.get("lang") or "").strip()
        if lang:
            return []
        selector, line = context.locate(html)
        return [Issue(
            rule_id=self.id, severity=self.severity, selector=selector, line=line,
            snippet=snippet_of(html), source=context.source, details={},
            fix_snippet='<html lang="uk">',
        )]


class DocumentTitle(AccessibilityRule):
    id = "document-title"
    page_level = True
    severity = SERIOUS
    wcag = ("2.4.2",)

    def check(self, document, context) -> list:
        if document.find("html") is None:
            return []
        title = document.find("title")
        if title is not None and _text_of(title):
            return []
        return [Issue(
            rule_id=self.id, severity=self.severity, source=context.source,
            snippet="<head>…</head>", details={"present": title is not None},
        )]


class HeadingOrder(AccessibilityRule):
    id = "heading-order"
    severity = MODERATE
    wcag = ("1.3.1", "2.4.6")

    def check(self, document, context) -> list:
        issues = []
        headings = [h for h in document.find_all(re.compile(r"^h[1-6]$"))
                    if _text_of(h)]
        previous = 0
        for heading in headings:
            level = int(heading.name[1])
            if previous and level > previous + 1:
                # Headings are how a screen reader user skims. A jump from h2
                # to h4 reads as a missing section, not as a design choice.
                selector, line = context.locate(heading)
                issues.append(Issue(
                    rule_id=self.id, severity=self.severity, selector=selector,
                    line=line, snippet=snippet_of(heading), source=context.source,
                    details={"from": previous, "to": level, "text": _text_of(heading)[:80]},
                    fix_snippet=f"<h{previous + 1}>{_text_of(heading)[:60]}</h{previous + 1}>",
                ))
            previous = level
        return issues


class MissingH1(AccessibilityRule):
    id = "page-has-h1"
    page_level = True
    severity = MODERATE
    wcag = ("1.3.1",)

    def check(self, document, context) -> list:
        if document.find("html") is None:
            return []
        h1s = [h for h in document.find_all("h1") if _text_of(h)]
        if len(h1s) == 1:
            return []
        return [Issue(
            rule_id=self.id, severity=self.severity, source=context.source,
            snippet="<body>…</body>", details={"count": len(h1s)},
        )]


class PositiveTabindex(AccessibilityRule):
    id = "tabindex-positive"
    severity = SERIOUS
    wcag = ("2.4.3",)

    def check(self, document, context) -> list:
        issues = []
        for tag in document.find_all(attrs={"tabindex": True}):
            try:
                value = int((tag.get("tabindex") or "0").strip())
            except ValueError:
                continue
            if value <= 0:
                continue
            # A positive tabindex pulls the element out of document order and
            # in front of everything with tabindex 0 — including the skip
            # link. One such element re-orders the whole page's keyboard path.
            selector, line = context.locate(tag)
            issues.append(Issue(
                rule_id=self.id, severity=self.severity, selector=selector, line=line,
                snippet=snippet_of(tag), source=context.source,
                details={"value": value, "element": tag.name},
                fix_snippet=_with_attribute(tag, "tabindex", "0"),
            ))
        return issues


class DuplicateIds(AccessibilityRule):
    id = "duplicate-id"
    severity = MODERATE
    wcag = ("4.1.1",)

    def check(self, document, context) -> list:
        seen: dict = {}
        issues = []
        for tag in document.find_all(id=True):
            identifier = (tag.get("id") or "").strip()
            if not identifier:
                continue
            if identifier in seen:
                # `for`, `aria-labelledby` and `aria-describedby` all resolve
                # to the *first* match, so a duplicate silently points every
                # reference at one element and leaves the other unnamed.
                selector, line = context.locate(tag)
                issues.append(Issue(
                    rule_id=self.id, severity=self.severity, selector=selector,
                    line=line, snippet=snippet_of(tag), source=context.source,
                    details={"id": identifier},
                ))
            seen[identifier] = tag
        return issues


class BrokenAriaReference(AccessibilityRule):
    id = "aria-reference-broken"
    severity = SERIOUS
    wcag = ("1.3.1", "4.1.2")

    _REFERENCING = ("aria-labelledby", "aria-describedby", "aria-controls", "aria-owns")

    def check(self, document, context) -> list:
        issues = []
        ids = {tag.get("id") for tag in document.find_all(id=True)}
        for attribute in self._REFERENCING:
            for tag in document.find_all(attrs={attribute: True}):
                missing = [token for token in (tag.get(attribute) or "").split()
                           if token not in ids]
                if not missing:
                    continue
                # A dangling aria-labelledby is worse than none: the element
                # ends up with no name at all, and the markup looks correct.
                selector, line = context.locate(tag)
                issues.append(Issue(
                    rule_id=self.id, severity=self.severity, selector=selector,
                    line=line, snippet=snippet_of(tag), source=context.source,
                    details={"attribute": attribute, "missing": missing},
                ))
        return issues


class ButtonWithoutType(AccessibilityRule):
    id = "button-type"
    severity = MINOR
    wcag = ()

    def check(self, document, context) -> list:
        issues = []
        for tag in document.find_all("button"):
            if tag.get("type"):
                continue
            if tag.find_parent("form") is None:
                continue
            # Inside a form a button defaults to type="submit", so an
            # icon-only "clear" button submits the form on Enter.
            selector, line = context.locate(tag)
            issues.append(Issue(
                rule_id=self.id, severity=self.severity, selector=selector, line=line,
                snippet=snippet_of(tag), source=context.source, details={},
                fix_snippet=_with_attribute(tag, "type", "button"),
            ))
        return issues


class MediaWithoutCaptions(AccessibilityRule):
    id = "media-captions"
    severity = SERIOUS
    confidence = NEEDS_BROWSER
    wcag = ("1.2.2",)

    def check(self, document, context) -> list:
        issues = []
        for tag in document.find_all(("video", "audio")):
            tracks = tag.find_all("track")
            if any((t.get("kind") or "").lower() in ("captions", "subtitles") for t in tracks):
                continue
            # Tracks added by a player's JavaScript are invisible here, hence
            # needs-browser: this finds the markup-only case honestly and
            # says the rest needs checking in a browser.
            selector, line = context.locate(tag)
            issues.append(Issue(
                rule_id=self.id, severity=self.severity, selector=selector, line=line,
                snippet=snippet_of(tag), source=context.source, confidence=self.confidence,
                details={"element": tag.name, "tracks": len(tracks)},
            ))
        return issues


class AutoplayingMedia(AccessibilityRule):
    id = "media-autoplay"
    severity = SERIOUS
    wcag = ("1.4.2",)

    def check(self, document, context) -> list:
        issues = []
        for tag in document.find_all(("video", "audio")):
            if not tag.has_attr("autoplay"):
                continue
            if tag.has_attr("muted") and tag.name == "video":
                continue
            if tag.has_attr("controls"):
                continue
            # Sound the visitor did not ask for, with no way to stop it,
            # covers a screen reader's own speech.
            selector, line = context.locate(tag)
            issues.append(Issue(
                rule_id=self.id, severity=self.severity, selector=selector, line=line,
                snippet=snippet_of(tag), source=context.source,
                details={"element": tag.name},
                fix_snippet=_with_attribute(tag, "controls", ""),
            ))
        return issues


class TableStructure(AccessibilityRule):
    id = "table-headers"
    severity = SERIOUS
    wcag = ("1.3.1",)

    def check(self, document, context) -> list:
        issues = []
        for table in document.find_all("table"):
            if table.get("role") == "presentation":
                continue
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue  # a one-row table is layout, not data
            if table.find("th") is not None:
                continue
            # Without <th>, every cell is announced as a bare value with no
            # indication of which column it belongs to.
            selector, line = context.locate(table)
            issues.append(Issue(
                rule_id=self.id, severity=self.severity, selector=selector, line=line,
                snippet=snippet_of(table), source=context.source,
                details={"rows": len(rows)},
            ))
        return issues


class ViewportZoomBlocked(AccessibilityRule):
    id = "viewport-zoom"
    page_level = True
    severity = SERIOUS
    wcag = ("1.4.4",)

    def check(self, document, context) -> list:
        issues = []
        for tag in document.find_all("meta"):
            if (tag.get("name") or "").lower() != "viewport":
                continue
            content = (tag.get("content") or "").lower()
            blocked = "user-scalable=no" in content.replace(" ", "")
            capped = re.search(r"maximum-scale\s*=\s*(1(\.0+)?|0?\.\d+)\b", content)
            if not blocked and not capped:
                continue
            # Blocking zoom is a one-line meta tag that makes the site
            # unusable for anyone who needs larger text.
            selector, line = context.locate(tag)
            issues.append(Issue(
                rule_id=self.id, severity=self.severity, selector=selector, line=line,
                snippet=snippet_of(tag), source=context.source,
                details={"content": content[:120]},
                fix_snippet='<meta name="viewport" content="width=device-width, initial-scale=1">',
            ))
        return issues


class InlineContrast(AccessibilityRule):
    id = "contrast-inline"
    severity = SERIOUS
    confidence = NEEDS_BROWSER
    wcag = ("1.4.3",)

    _COLOR_RE = re.compile(r"(^|;)\s*color\s*:\s*([^;]+)", re.IGNORECASE)
    _BG_RE = re.compile(r"(^|;)\s*background(?:-color)?\s*:\s*([^;]+)", re.IGNORECASE)

    def check(self, document, context) -> list:
        issues = []
        for tag in document.find_all(style=True):
            style = tag.get("style") or ""
            foreground = self._COLOR_RE.search(style)
            background = self._BG_RE.search(style)
            if not foreground or not background:
                continue  # only judgeable when both are on the same element
            fg = _parse_color(foreground.group(2))
            bg = _parse_color(background.group(2))
            if fg is None or bg is None:
                continue
            ratio = contrast_ratio(fg, bg)
            if ratio >= 4.5:
                continue
            # Only inline pairs are checkable without a browser; the real
            # contrast of the page comes from the cascade, which this pass
            # cannot see. Hence needs-browser, and hence "found in the
            # markup" rather than "the page fails contrast".
            selector, line = context.locate(tag)
            issues.append(Issue(
                rule_id=self.id, severity=self.severity, selector=selector, line=line,
                snippet=snippet_of(tag), source=context.source, confidence=self.confidence,
                details={"ratio": round(ratio, 2), "foreground": foreground.group(2).strip(),
                         "background": background.group(2).strip(), "required": 4.5},
            ))
        return issues


# ------------------------------------------------------------------ helpers

#: Attributes whose presence is the whole meaning; writing `autoplay=""` in
#: a suggested fix is valid HTML but reads as a mistake to anyone copying it.
_BOOLEAN_ATTRIBUTES = frozenset((
    "controls", "muted", "autoplay", "loop", "playsinline", "disabled",
    "checked", "selected", "readonly", "required", "open", "hidden",
    "multiple", "novalidate", "default", "reversed", "async", "defer",
))


def _with_attribute(tag, name: str, value: str) -> str:
    """The element's opening tag with one attribute set — the fix, written
    out, so it can be copied straight into the source."""
    attributes = dict(tag.attrs)
    attributes[name] = value
    parts = []
    for key, val in attributes.items():
        if isinstance(val, list):
            val = " ".join(val)
        if key in _BOOLEAN_ATTRIBUTES and val in ("", key, True):
            parts.append(key)
        else:
            parts.append(f'{key}="{val}"')
    return f"<{tag.name} " + " ".join(parts) + ">"


_NAMED_COLORS = {
    "white": (255, 255, 255), "black": (0, 0, 0), "red": (255, 0, 0),
    "green": (0, 128, 0), "blue": (0, 0, 255), "gray": (128, 128, 128),
    "grey": (128, 128, 128), "silver": (192, 192, 192), "yellow": (255, 255, 0),
}


def _parse_color(value: str) -> tuple | None:
    value = value.strip().lower()
    if value in _NAMED_COLORS:
        return _NAMED_COLORS[value]
    if value.startswith("#"):
        digits = value[1:]
        if len(digits) == 3:
            digits = "".join(c * 2 for c in digits)
        if len(digits) >= 6:
            try:
                return tuple(int(digits[i:i + 2], 16) for i in (0, 2, 4))
            except ValueError:
                return None
    match = re.match(r"rgba?\(([^)]+)\)", value)
    if match:
        parts = [p.strip() for p in match.group(1).replace("/", ",").split(",")]
        try:
            return tuple(int(float(p)) for p in parts[:3])
        except ValueError:
            return None
    return None


def _channel(value: int) -> float:
    c = value / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb: tuple) -> float:
    r, g, b = (_channel(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(foreground: tuple, background: tuple) -> float:
    """WCAG 2.x contrast ratio, 1.0 (identical) to 21.0 (black on white)."""
    light, dark = sorted(
        (relative_luminance(foreground), relative_luminance(background)), reverse=True
    )
    return (light + 0.05) / (dark + 0.05)


for _rule in (
    ImageAlt, ImageAltIsFilename, ControlName, VagueLinkText, DocumentLanguage,
    DocumentTitle, HeadingOrder, MissingH1, PositiveTabindex, DuplicateIds,
    BrokenAriaReference, ButtonWithoutType, MediaWithoutCaptions, AutoplayingMedia,
    TableStructure, ViewportZoomBlocked, InlineContrast,
):
    RuleRegistry.register(_rule)
