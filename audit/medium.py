"""What a document is *for*, which is not the same as what it is written in.

`_document_kind` answers "page or fragment". This answers a different
question that a scan has to get right before it opens its mouth: a complete
HTML document with a doctype, a `<head>` and a `<body>` may be a page a
browser serves, or it may be an email a mail client renders. They are the
same file format and almost nothing else.

Measured on `~/repositories/VSC`, a workspace of Ghost, Beehiiv, Carrd and
ClickFunnels deliverables: 1074 findings over 144 documents, and the top of
the list was `seo-canonical` 93, `seo-structured-data` 93, `seo-open-graph`
91, `seo-meta-description` 83, `landmark-regions` 80, `skip-link` 67. Every
one of those is a browser concept. An email has no canonical URL, is never
crawled, is not shared to Open Graph, and lands in clients that do not
implement landmarks or skip links. Asking for them is not a strict audit, it
is a category error repeated eighty times.

What does **not** change on an email is the part that matters most:
`image-alt`, `control-name`, `table-headers`, contrast and language are as
real in a mail client as in a browser, and none of them is touched here.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

WEB = "web"
EMAIL = "email"

#: Outlook's VML and Office namespaces on `<html>`. Nothing but an HTML email
#: has ever carried these - they exist so Word's rendering engine can draw
#: rounded buttons - which makes them the strongest single signal available.
_OUTLOOK_NAMESPACE = re.compile(
    r"xmlns:[vo]\s*=\s*[\"']urn:schemas-microsoft-com:(?:vml|office:office)", re.I)

#: An email service provider's merge tags. Each one is that provider's own
#: syntax and appears nowhere else: Beehiiv and Ghost write `{{...}}`,
#: Mailchimp writes `*|UNSUB|*`, and the `%%...%%` family belongs to
#: Salesforce and Braze.
_MERGE_TAG = re.compile(
    r"\{\{\s*(?:unsubscribe_url|email|subscriber\.|first_name|list_address)"
    r"|\*\|[A-Z_]+\|\*"
    r"|%%\s*(?:unsubscribe|emailaddr|profile_center)\s*%%", re.I)

#: Corroborating, never decisive on its own. `supported-color-schemes` is an
#: email-client meta; a marketing page could carry `color-scheme` alone.
_EMAIL_META = re.compile(
    r"<meta[^>]+name\s*=\s*[\"']supported-color-schemes", re.I)

#: The other corroborator: a document laid out entirely in presentation
#: tables. Correct in email, where it is the only layout that works
#: everywhere, and a 2005 web page otherwise.
_PRESENTATION_TABLE = re.compile(r"<table[^>]+role\s*=\s*[\"']presentation", re.I)
_ANY_TABLE = re.compile(r"<table[\s>]", re.I)
#: How many presentation tables before "laid out in tables" is fair to say.
_TABLE_LAYOUT_MIN = 3

#: What a table layout is corroborated *by*, when there is no merge tag and
#: no Outlook namespace to settle it. Each is an attribute a browser has not
#: needed since HTML 4 and a mail client still does: a table pinned to the
#: 500-720 px an email is designed for, a `bgcolor` on a row or cell, an
#: `align` on a cell.
#:
#: Measured 2026-09-01 over 324 HTML files in seven repositories: **17** of
#: them lay out in three or more presentation tables, all seventeen are
#: email deliverables (Beehiiv and Ghost templates), and every one carries
#: at least one of these three attributes. On the other side, eight pages of
#: a live WordPress site carry **zero** presentation tables. Before this,
#: five of the seventeen were recognised and twelve were audited as web
#: pages - `seo-canonical`, `seo-open-graph`, `skip-link` and
#: `landmark-regions` on a file that lands in a mail client.
_EMAIL_TABLE_ATTRS = (
    re.compile(r"<table[^>]+width\s*=\s*[\"']?(?:5\d\d|6\d\d|7[0-2]\d)\b", re.I),
    re.compile(r"<t[dr][^>]+bgcolor\s*=", re.I),
    re.compile(r"<td[^>]+align\s*=", re.I),
)


@dataclass(frozen=True)
class Medium:
    """What the document is for, and what said so."""
    name: str = WEB
    evidence: str = ""

    @property
    def is_email(self) -> bool:
        return self.name == EMAIL


def detect(markup: str) -> Medium:
    """`web` unless the document says otherwise, with the reason it said so.

    Deliberately asymmetric. `web` is the default and needs no evidence
    because it is what almost everything is; `email` has to prove itself,
    because being wrong here *hides* findings - the failure that cannot be
    seen in a report. One decisive signal, or two corroborating ones.
    """
    text = markup or ""
    if _OUTLOOK_NAMESPACE.search(text):
        return Medium(EMAIL, "Outlook VML/Office namespace on <html>")
    match = _MERGE_TAG.search(text)
    if match:
        return Medium(EMAIL, f"email merge tag {match.group(0).strip()!r}")

    corroborating = []
    if _EMAIL_META.search(text):
        corroborating.append("supported-color-schemes meta")
    tables = len(_PRESENTATION_TABLE.findall(text))
    if tables >= _TABLE_LAYOUT_MIN:
        corroborating.append(f"{tables} presentation tables")
        # A table layout plus one attribute no browser has needed since
        # HTML 4 is not a second opinion, it is the same fact twice - and
        # asking for the meta as well left twelve of seventeen email
        # templates being audited as web pages. See `_EMAIL_TABLE_ATTRS`.
        for pattern in _EMAIL_TABLE_ATTRS:
            match = pattern.search(text)
            if match:
                return Medium(EMAIL, f"{tables} presentation tables + "
                                     f"{match.group(0).strip()[:40]!r}")
    if len(corroborating) >= 2:
        return Medium(EMAIL, " + ".join(corroborating))
    return Medium(WEB, "")
