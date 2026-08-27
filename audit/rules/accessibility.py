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
    ACCESSIBILITY, CRITICAL, EXACT, MINOR, MODERATE, NEEDS_BROWSER, PERFORMANCE,
    SERIOUS, Issue, Rule, RuleRegistry, is_binding, snippet_of,
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


class DocumentLanguageMismatch(AccessibilityRule):
    """The page declares one language and is written in another.

    `html-lang` asks whether the attribute is there. This asks whether it is
    *true*, which is what 3.1.1 is actually about: a screen reader trusts the
    attribute completely, so `lang="en"` over Ukrainian copy is read out with
    English phonetics and is worse than no attribute at all - with none, the
    reader falls back to the user's own setting.

    Both halves already existed and had never been introduced: the audit
    knew the declared language and `lang_detect.guess_language_safe` was
    reading the real one for the text detectors two modules away.

    Deliberately silent in two cases, and the second is the important one:

    * Not enough text to tell. `guess_language_safe` answers `None` there
      rather than guessing, and this passes it straight through.
    * **Whenever the detector's answer is English.** It has no "some fourth
      language" verdict - anything non-Cyrillic with no Italian markers comes
      back `en` - so `lang="de"` on a German page would be reported as a lie.
      Ukrainian is decided by the share of Cyrillic letters and Italian by
      its own markers, and those two are evidence; English is a default
      wearing the same coat. See the language step in the hunting plan.
    """
    id = "html-lang-mismatch"
    page_level = True
    severity = SERIOUS
    wcag = ("3.1.1",)

    #: Below this the page is a shell or a menu, and no detector should be
    #: asked. The threshold is in words because that is what the detector
    #: measures.
    MIN_WORDS = 40

    def check(self, document, context) -> list:
        from lang_detect import guess_language_safe

        html = document.find("html")
        if html is None:
            return []
        declared = (html.get("lang") or "").strip().lower()
        if not declared:
            return []  # `html-lang` already reports the absence
        body = document.find("body")
        text = _text_of(body) if body is not None else ""
        if len(text.split()) < self.MIN_WORDS:
            return []
        # Read twice, on the two halves of the page, and report only when
        # both readings agree. A single stray word is what makes a long
        # English page look Italian - "per user", "che" in a quoted name -
        # and a stray word lands in one half, not in both. The same
        # corroboration the audit already asks of two engines, asked of one
        # detector on two samples.
        words = text.split()
        middle = len(words) // 2
        readings = (guess_language_safe(" ".join(words[:middle])),
                    guess_language_safe(" ".join(words[middle:])),
                    guess_language_safe(text))
        detected = readings[-1]
        if detected in (None, "en") or any(r != detected for r in readings):
            return []
        if declared.split("-")[0] == detected:
            return []
        selector, line = context.locate(html)
        return [Issue(
            rule_id=self.id, severity=self.severity, selector=selector, line=line,
            snippet=snippet_of(html), source=context.source,
            details={"declared": declared, "detected": detected,
                     "sample": text[:120]},
            fix_snippet=f'<html lang="{detected}">',
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
            if is_binding(identifier):
                # `id={m.id}` is one expression that yields a different id per
                # render, and a list renders it many times. Comparing the
                # source text makes every row after the first a duplicate of
                # itself, which is a statement about the file rather than
                # about the page. Same reasoning as `bp-inline-handlers` and
                # `onClick={close}`; found on `ChatMessageRenderer.tsx` and
                # `SettingsCollapsible.tsx` once repo mode could read `.tsx`.
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


def _style_sources(document) -> list:
    """Every (element, css_text) pair holding style declarations: inline
    `style` attributes plus the contents of <style> blocks. Stylesheet
    files need the browser pass; these two cover what the markup ships."""
    pairs = [(tag, tag.get("style") or "") for tag in document.find_all(style=True)]
    for block in document.find_all("style"):
        pairs.append((block, block.get_text() or ""))
    return pairs


def _strip_small_screen_media(css: str) -> str:
    """Drop @media blocks scoped to narrow screens (`max-width` up to
    900px): those declarations exist to FIX phone layouts, and reporting
    them as hazards would punish exactly the right fix."""
    out = []
    pos = 0
    while True:
        start = css.find("@media", pos)
        if start == -1:
            out.append(css[pos:])
            break
        out.append(css[pos:start])
        brace = css.find("{", start)
        if brace == -1:
            break
        depth = 1
        end = brace + 1
        while end < len(css) and depth:
            if css[end] == "{":
                depth += 1
            elif css[end] == "}":
                depth -= 1
            end += 1
        block = css[start:end]
        limit = re.search(r"max-width\s*:\s*(\d+)px", block)
        if limit and int(limit.group(1)) <= 900:
            pass  # mobile-scoped: ignore its declarations
        else:
            out.append(block)
        pos = end
    return "".join(out)


class FixedPixelWidth(AccessibilityRule):
    id = "viewport-fixed-width"
    severity = MODERATE
    confidence = NEEDS_BROWSER
    wcag = ("1.4.10",)

    #: Anchored so `max-width` / `min-width` never match: those are the fix,
    #: not the bug.
    _WIDTH_RE = re.compile(r"(?:^|;|\{)\s*width\s*:\s*(\d+(?:\.\d+)?)px",
                           re.IGNORECASE)

    def check(self, document, context) -> list:
        issues = []
        for tag, css in _style_sources(document):
            css = _strip_small_screen_media(css)
            for found in self._WIDTH_RE.finditer(css):
                px = float(found.group(1))
                if px < 600:
                    continue  # fits a 390px phone with margin for chrome
                selector, line = context.locate(tag)
                issues.append(Issue(
                    rule_id=self.id, severity=self.severity, selector=selector,
                    line=line, snippet=snippet_of(tag)[:160], source=context.source,
                    confidence=self.confidence,
                    details={"width_px": int(px),
                             "mobile_viewport": 390},
                    fix_snippet=_with_attribute(
                        tag, "style",
                        self._WIDTH_RE.sub(f"max-width: {int(px)}px",
                                           css, count=1)) if tag.has_attr("style") else None,
                ))
        return issues


class TinyFont(AccessibilityRule):
    id = "viewport-tiny-font"
    severity = SERIOUS
    confidence = NEEDS_BROWSER
    wcag = ("1.4.4",)

    _FONT_RE = re.compile(
        r"(?:^|;|\{)\s*font-size\s*:\s*(\d+(?:\.\d+)?)(px|pt|rem|em)",
        re.IGNORECASE)
    _PX_PER_UNIT = {"px": 1.0, "pt": 4.0 / 3.0, "rem": 16.0, "em": 16.0}

    def check(self, document, context) -> list:
        issues = []
        for tag, css in _style_sources(document):
            css = _strip_small_screen_media(css)
            for found in self._FONT_RE.finditer(css):
                value = float(found.group(1)) * self._PX_PER_UNIT[
                    found.group(2).lower()]
                if value >= 10:
                    continue
                selector, line = context.locate(tag)
                issues.append(Issue(
                    rule_id=self.id, severity=self.severity, selector=selector,
                    line=line, snippet=snippet_of(tag)[:160], source=context.source,
                    confidence=self.confidence,
                    details={"font_px": round(value, 1),
                             "minimum_recommended": 10},
                ))
        return issues


class SmallTouchTarget(AccessibilityRule):
    id = "viewport-touch-target"
    severity = MINOR
    confidence = NEEDS_BROWSER
    wcag = ("2.5.8",)

    _SIZE_RE = re.compile(
        r"(?:^|;)\s*(width|height)\s*:\s*(\d+(?:\.\d+)?)px", re.IGNORECASE)
    _MINIMUM_PX = 24

    def check(self, document, context) -> list:
        issues = []
        for name in _INTERACTIVE:
            for tag in document.find_all(name, style=True):
                sizes = {m.group(1).lower(): float(m.group(2))
                         for m in self._SIZE_RE.finditer(tag.get("style") or "")}
                too_small = {axis: px for axis, px in sizes.items()
                             if px < self._MINIMUM_PX}
                if not too_small:
                    continue
                selector, line = context.locate(tag)
                issues.append(Issue(
                    rule_id=self.id, severity=self.severity, selector=selector,
                    line=line, snippet=snippet_of(tag), source=context.source,
                    confidence=self.confidence,
                    details={"declared": ", ".join(f"{axis}={int(px)}px"
                                                   for axis, px in sorted(too_small.items())),
                             "wcag_minimum": self._MINIMUM_PX,
                             "recommended": 44},
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
    """The opaque sRGB triple this declaration paints, or None when the
    markup alone cannot say.

    None is the honest answer far more often than it looks: `var(--fg)`,
    `currentColor`, `transparent`, `hsl()`, `color-mix()` and percentage
    channels all resolve somewhere this pass cannot see. Translucent
    colours belong in the same group — a ratio computed against a colour
    that is half the layer underneath is a number nobody measured.
    """
    value = value.strip().lower()
    if value in _NAMED_COLORS:
        return _NAMED_COLORS[value]
    if value.startswith("#"):
        digits = value[1:]
        if len(digits) in (3, 4):
            digits = "".join(c * 2 for c in digits)
        if len(digits) == 8 and _hex_pair(digits[6:8]) not in (255, None):
            return None  # translucent: the colour behind it is unknown
        if len(digits) >= 6:
            channels = tuple(_hex_pair(digits[i:i + 2]) for i in (0, 2, 4))
            return None if None in channels else channels
    match = re.match(r"rgba?\(([^)]+)\)", value)
    if match:
        parts = [p.strip() for p in match.group(1).replace("/", ",").split(",")]
        parts = [p for p in parts if p]
        if len(parts) < 3 and parts and len(parts[0].split()) == 3:
            parts = parts[0].split() + parts[1:]  # rgb(0 0 0 / 50%) space syntax
        try:
            channels = tuple(_clamp_channel(float(p)) for p in parts[:3])
            alpha = float(parts[3]) if len(parts) > 3 else 1.0
        except ValueError:
            return None
        if len(channels) < 3 or alpha < 1.0:
            return None
        return channels
    return None


def _hex_pair(digits: str) -> int | None:
    try:
        return int(digits, 16)
    except ValueError:
        return None


def _clamp_channel(value: float) -> int:
    """CSS channels outside 0-255 are clamped by browsers, not honoured;
    letting them through produces luminances no screen ever shows."""
    return max(0, min(255, int(value)))


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


class LandmarkRegions(AccessibilityRule):
    """Page should have landmark regions for screen reader navigation.

    Landmarks (<main>, <nav>, <header>, <footer>, or ARIA equivalents) let
    screen reader users jump directly to the section they need instead of
    tabbing through the entire page. A page with no landmarks at all forces
    linear navigation.
    """
    id = "landmark-regions"
    web_only = True
    page_level = True
    severity = MODERATE
    wcag = ("1.3.1", "2.4.1")

    _LANDMARK_TAGS = {"main", "nav", "header", "footer", "aside", "form"}
    _LANDMARK_ROLES = {
        "banner", "complementary", "contentinfo", "form", "main",
        "navigation", "region", "search",
    }

    def check(self, document, context) -> list:
        if document.find("html") is None:
            return []
        found = set()
        for tag in document.find_all(True):
            if tag.name in self._LANDMARK_TAGS:
                found.add(tag.name)
            role = (tag.get("role") or "").lower().strip()
            if role in self._LANDMARK_ROLES:
                found.add(role)
        if "main" in found or "main" in {t.name for t in document.find_all("main")}:
            return []
        return [Issue(
            rule_id=self.id, severity=self.severity, source=context.source,
            snippet="<body>…</body>",
            details={"found": sorted(found)},
            fix_snippet='<main>…</main>',
        )]


class SkipLink(AccessibilityRule):
    """First focusable element should be a skip-to-content link.

    Keyboard users (including screen reader users) need a way to bypass
    repeated navigation. The convention is a link at the top of the page
    that jumps to the main content area. Without it, every page visit
    requires tabbing through the entire nav.
    """
    id = "skip-link"
    web_only = True
    page_level = True
    severity = MODERATE
    wcag = ("2.4.1",)

    def check(self, document, context) -> list:
        if document.find("html") is None:
            return []
        body = document.find("body")
        if body is None:
            return []
        # Look for a link near the top that points to an anchor
        for tag in body.find_all("a", href=True, limit=10):
            href = (tag.get("href") or "").strip()
            if href.startswith("#") and len(href) > 1:
                target_id = href[1:]
                if body.find(id=target_id) is not None:
                    return []
        return [Issue(
            rule_id=self.id, severity=self.severity, source=context.source,
            snippet="<body>…</body>",
            details={},
            fix_snippet='<a href="#main-content" class="skip-link">Skip to main content</a>',
        )]


class FormErrorMessage(AccessibilityRule):
    """Form inputs with errors should be described by the error message.

    When a form field has an error (indicated by aria-invalid="true"), the
    error message must be programmatically linked to the field via
    aria-describedby or aria-errormessage. Without this, screen reader users
    know the field is invalid but not why.
    """
    id = "form-error-message"
    severity = SERIOUS
    wcag = ("3.3.1",)

    def check(self, document, context) -> list:
        issues = []
        for tag in document.find_all(("input", "select", "textarea")):
            if (tag.get("aria-invalid") or "").lower() != "true":
                continue
            described_by = (tag.get("aria-describedby") or "").strip()
            errormessage = (tag.get("aria-errormessage") or "").strip()
            if described_by or errormessage:
                continue
            selector, line = context.locate(tag)
            issues.append(Issue(
                rule_id=self.id, severity=self.severity, selector=selector,
                line=line, snippet=snippet_of(tag), source=context.source,
                details={"element": tag.name, "type": tag.get("type", "")},
            ))
        return issues


class TableScope(AccessibilityRule):
    """Data table headers should use scope attribute.

    The scope attribute on <th> tells screen readers whether the header
    applies to a row or a column. Without it, complex tables become
    ambiguous — the user hears a cell value but not which header it belongs to.
    """
    id = "table-scope"
    severity = MODERATE
    wcag = ("1.3.1",)

    def check(self, document, context) -> list:
        issues = []
        for table in document.find_all("table"):
            if table.get("role") == "presentation":
                continue
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue
            ths = table.find_all("th")
            if not ths:
                continue
            # Only flag if there are th elements but none use scope
            has_scope = any(th.get("scope") for th in ths)
            if has_scope:
                continue
            # Multi-row or multi-column tables benefit most from scope
            if len(ths) <= 1:
                continue
            selector, line = context.locate(table)
            issues.append(Issue(
                rule_id=self.id, severity=self.severity, selector=selector,
                line=line, snippet=snippet_of(table), source=context.source,
                details={"th_count": len(ths), "rows": len(rows)},
                fix_snippet='<th scope="col">…</th>',
            ))
        return issues


class HreflangLinks(AccessibilityRule):
    """Multilingual pages should declare language alternatives.

    hreflang links tell search engines and browsers which language/version
    of a page exists. Without them, users may land on the wrong language
    version, and search engines cannot properly index multilingual content.
    """
    id = "hreflang-links"
    web_only = True
    page_level = True
    severity = MINOR
    wcag = ("3.1.2",)

    def check(self, document, context) -> list:
        if document.find("html") is None:
            return []
        html_tag = document.find("html")
        lang = (html_tag.get("lang") or "").strip()
        if not lang:
            return []  # Already reported by html-lang rule
        # Check if there are links to other language versions
        links = document.find_all("a", hreflang=True)
        alternate_links = [l for l in document.find_all("link")
                          if "alternate" in (l.get("rel") or []) and l.get("hreflang")]
        if links or alternate_links:
            return []
        # Only suggest if the page content suggests multilingual site
        # (e.g., has language switcher patterns)
        for tag in document.find_all("a", href=True):
            href = (tag.get("href") or "").lower()
            text = _text_of(tag).lower()
            if any(f"/{lc}/" in href or f"/{lc}" in href
                   for lc in ("en", "uk", "it", "de", "fr", "es", "pl")):
                return [Issue(
                    rule_id=self.id, severity=self.severity, source=context.source,
                    snippet="<head>…</head>",
                    details={"lang": lang},
                    fix_snippet=f'<link rel="alternate" hreflang="en" href="https://example.com/en/" />',
                )]
        return []


class BreadcrumbMarkup(AccessibilityRule):
    """Breadcrumb navigation should use proper markup.

    Breadcrumbs help users understand their location in the site hierarchy.
    When present, they should use <nav aria-label="breadcrumb"> and an
    ordered list (<ol>) for proper screen reader announcement.
    """
    id = "breadcrumb-markup"
    severity = MINOR
    wcag = ("1.3.1", "2.4.8")

    _BREADCRUMB_SELECTORS = [
        {"class": "breadcrumb"}, {"class": "breadcrumbs"},
        {"aria-label": "breadcrumb"}, {"aria-label": "Breadcrumbs"},
        {"aria-label": "Breadcrumb"},
    ]

    def check(self, document, context) -> list:
        issues = []
        for selector in self._BREADCRUMB_SELECTORS:
            for tag in document.find_all(attrs=selector):
                # Check if it's properly wrapped in nav
                if tag.name == "nav":
                    continue
                parent_nav = tag.find_parent("nav")
                if parent_nav:
                    continue
                # Has breadcrumb-like content but not in nav
                if tag.find("a") or tag.find("li"):
                    selector_path, line = context.locate(tag)
                    issues.append(Issue(
                        rule_id=self.id, severity=self.severity,
                        selector=selector_path, line=line,
                        snippet=snippet_of(tag), source=context.source,
                        details={"element": tag.name},
                        fix_snippet='<nav aria-label="breadcrumb"><ol>…</ol></nav>',
                    ))
                    break  # One finding per page
        return issues


class ImageModernFormat(AccessibilityRule):
    """Images should use modern formats when possible.

    WebP and AVIF offer better compression than PNG/JPG, reducing page
    weight and improving load times. The srcset attribute allows serving
    different sizes to different viewports.
    """
    id = "image-modern-format"
    severity = MINOR
    category = PERFORMANCE
    # WebP and AVIF are a browser's formats. Mail clients are years behind on
    # both, and asking an email to ship them is asking it to break.
    web_only = True
    wcag = ()

    _LEGACY_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".bmp")
    _MODERN_EXTENSIONS = (".webp", ".avif", ".svg")

    def check(self, document, context) -> list:
        issues = []
        for tag in document.find_all("img"):
            src = (tag.get("src") or "").lower()
            if not src:
                continue
            # Skip data URIs and SVGs
            if src.startswith("data:") or src.endswith(".svg"):
                continue
            # Check if using legacy format without srcset
            has_legacy = any(src.endswith(ext) for ext in self._LEGACY_EXTENSIONS)
            has_srcset = bool(tag.get("srcset"))
            if has_legacy and not has_srcset:
                selector, line = context.locate(tag)
                issues.append(Issue(
                    rule_id=self.id, severity=self.severity,
                    category=self.category, selector=selector, line=line,
                    snippet=snippet_of(tag), source=context.source,
                    details={"src": src[:120]},
                ))
        return issues


class LanguageChange(AccessibilityRule):
    """Inline foreign text should declare its language.

    When a passage in a different language appears within a page, screen
    readers need a `lang` attribute on the surrounding element to switch
    pronunciation. Without it, Ukrainian text inside an English page is
    read with English phonetics, which is unintelligible.
    """
    id = "language-change"
    severity = MINOR
    wcag = ("3.1.2",)

    # Common inline elements that might wrap foreign text
    _INLINE_TAGS = {"span", "em", "strong", "a", "b", "i", "u", "mark", "small", "cite", "q"}

    def check(self, document, context) -> list:
        if document.find("html") is None:
            return []
        page_lang = ""
        html_tag = document.find("html")
        if html_tag:
            page_lang = (html_tag.get("lang") or "").strip().lower()[:2]
        if not page_lang:
            return []  # Already reported by html-lang rule

        issues = []
        # Look for elements with lang attribute different from page lang
        for tag in document.find_all(attrs={"lang": True}):
            if tag.name == "html":
                continue
            element_lang = (tag.get("lang") or "").strip().lower()[:2]
            if element_lang and element_lang != page_lang:
                # This is correct usage - no issue
                continue

        # Look for text that might be in a different language but has no lang
        # This is a heuristic: check for common non-Latin/Cyrillic patterns
        # when page is Latin, or vice versa
        import unicodedata

        def _script_of(text):
            """Dominant script of a text string."""
            scripts = {}
            for ch in text:
                if ch.isalpha():
                    try:
                        name = unicodedata.name(ch, "")
                        if "CYRILLIC" in name:
                            scripts["cyrillic"] = scripts.get("cyrillic", 0) + 1
                        elif "LATIN" in name:
                            scripts["latin"] = scripts.get("latin", 0) + 1
                        elif "GREEK" in name:
                            scripts["greek"] = scripts.get("greek", 0) + 1
                        elif "ARABIC" in name:
                            scripts["arabic"] = scripts.get("arabic", 0) + 1
                        elif "CJK" in name or "HIRAGANA" in name or "KATAKANA" in name:
                            scripts["cjk"] = scripts.get("cjk", 0) + 1
                    except ValueError:
                        pass
            if not scripts:
                return ""
            return max(scripts, key=scripts.get)

        _SCRIPT_TO_LANG = {
            "cyrillic": ("uk", "ru", "bg", "sr"),
            "greek": ("el",),
            "arabic": ("ar", "fa", "ur"),
            "cjk": ("zh", "ja", "ko"),
        }

        page_script = "latin" if page_lang in ("en", "it", "de", "fr", "es", "pl", "pt") else "cyrillic" if page_lang in ("uk", "ru") else ""

        if not page_script:
            return []

        for tag in document.find_all(self._INLINE_TAGS):
            # Skip if already has lang
            if tag.get("lang"):
                continue
            # Skip if parent has lang
            parent_with_lang = tag.find_parent(attrs={"lang": True})
            if parent_with_lang:
                continue
            text = _text_of(tag)
            if len(text) < 10:  # Too short to judge
                continue
            script = _script_of(text)
            if script and script != page_script and script in _SCRIPT_TO_LANG:
                selector, line = context.locate(tag)
                issues.append(Issue(
                    rule_id=self.id, severity=self.severity,
                    selector=selector, line=line,
                    snippet=snippet_of(tag), source=context.source,
                    details={"page_lang": page_lang, "detected_script": script,
                             "suggested_lang": _SCRIPT_TO_LANG[script][0]},
                    fix_snippet=f'<span lang="{_SCRIPT_TO_LANG[script][0]}">{text[:60]}</span>',
                ))
        return issues


class AbbreviationExpansion(AccessibilityRule):
    """Abbreviations should use <abbr> with title.

    Screen readers cannot pronounce abbreviations correctly without
    expansion. The <abbr> element with a title attribute provides the
    full form, which screen readers can announce on first encounter.
    """
    id = "abbreviation-expansion"
    severity = MINOR
    wcag = ("3.1.4",)

    # Common abbreviations that should be expanded
    _COMMON_ABBREVS = {
        "WCAG", "HTML", "CSS", "JS", "API", "URL", "SEO", "UX", "UI",
        "FAQ", "CEO", "CTO", "CFO", "HR", "PR", "R&D", "B2B", "B2C",
        "SaaS", "PaaS", "IaaS", "CRM", "ERP", "CMS", "CDN", "DNS",
        "SSL", "TLS", "HTTP", "HTTPS", "FTP", "SSH", "SQL", "REST",
        "GraphQL", "JSON", "XML", "YAML", "CSV", "PDF", "PNG", "JPG",
        "SVG", "GIF", "WebP", "AVIF", "WOFF", "TTF", "EOT",
    }

    #: Whole words, and case as written. Substring matching is what this
    #: rule shipped with, and it is why one run produced 446 findings: `UI`
    #: matched "building" and "guide", `PR` matched "PRODUCT", `HR` matched
    #: "THROUGH". Compiled once, because it is consulted on every text node
    #: of every document.
    _PATTERN = None

    @classmethod
    def _matcher(cls):
        if cls._PATTERN is None:
            import re as _re

            alternatives = "|".join(sorted((_re.escape(a) for a in cls._COMMON_ABBREVS),
                                           key=len, reverse=True))
            cls._PATTERN = _re.compile(rf"(?<![A-Za-z0-9])({alternatives})(?![A-Za-z0-9])")
        return cls._PATTERN

    def check(self, document, context) -> list:
        """One finding per abbreviation per document, not per text node.

        The rule already carried the comment "only report once per page per
        abbreviation" and had never done it: the loop appended a finding for
        every text node it saw, so a page that says "API" in the nav, the
        body and the footer reported it three times. 3.1.4 is about the
        first occurrence - the reader needs the expansion once.
        """
        issues = []
        reported = set()
        for tag in document.find_all(string=True):
            if tag.parent.name in ("script", "style", "code", "pre", "abbr"):
                continue
            parent = tag.parent
            if parent is not None and parent.find_parent("abbr") is not None:
                continue
            for match in self._matcher().finditer(str(tag)):
                abbrev = match.group(1)
                if abbrev in reported:
                    continue
                if parent and parent.find("abbr", string=lambda s: s and abbrev in s):
                    continue
                reported.add(abbrev)
                selector, line = context.locate(parent) if parent else ("", None)
                issues.append(Issue(
                    rule_id=self.id, severity=self.severity,
                    selector=selector, line=line,
                    snippet=f"...{abbrev}...",
                    source=context.source,
                    details={"abbreviation": abbrev},
                    fix_snippet=f'<abbr title="Full form">{abbrev}</abbr>',
                ))
        return issues


for _rule in (
    ImageAlt, ImageAltIsFilename, ControlName, VagueLinkText, DocumentLanguage,
    DocumentLanguageMismatch,
    DocumentTitle, HeadingOrder, MissingH1, PositiveTabindex, DuplicateIds,
    BrokenAriaReference, ButtonWithoutType, MediaWithoutCaptions, AutoplayingMedia,
    TableStructure, ViewportZoomBlocked, InlineContrast,
    FixedPixelWidth, TinyFont, SmallTouchTarget,
    LandmarkRegions, SkipLink, FormErrorMessage, TableScope,
    HreflangLinks, BreadcrumbMarkup, ImageModernFormat,
    LanguageChange, AbbreviationExpansion,
):
    RuleRegistry.register(_rule)
