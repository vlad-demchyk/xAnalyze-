"""Helpers for the graphical site-preview column (QWebEngineView).

Renders the page's real HTML (captured during the crawl) and highlights
whichever element the user selected in the flagged-passages list, by
injecting a small stylesheet + querySelector call. `dom_path` values
produced by crawler.py (`tag:nth-of-type(n) > tag:nth-of-type(n) > ...`)
are valid CSS selectors, so no extra bookkeeping is needed to map a
TextBlock back onto the rendered page.
"""
from __future__ import annotations

import json

#: The default when a caller doesn't pass the design system's own colour
#: (see `build_highlight_js`'s `color` argument) - close in spirit to
#: `Palette.error`'s default, so the outline still reads as the same red the
#: findings list and the code preview use for "found here".
_DEFAULT_HIGHLIGHT_COLOR = "#e5484d"


def _highlight_css(color: str) -> str:
    # rgba(), not color-mix(): the outline colour is whatever hex the caller
    # hands in, and computing the translucent fill in Python rather than
    # asking the embedded Chromium to do it keeps this working on whatever
    # QtWebEngine version happens to be installed.
    text = color.lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    try:
        r, g, b = (int(text[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        r, g, b = (229, 72, 77)  # the same fallback as _DEFAULT_HIGHLIGHT_COLOR
    return (
        f".__ai_scanner_highlight {{ outline: 3px solid {color} !important; "
        f"background: rgba({r},{g},{b},0.25) !important; }}"
    )


def build_highlight_js(dom_path: str, opening_tag: str = "",
                       color: str = _DEFAULT_HIGHLIGHT_COLOR) -> str:
    """Highlight and scroll to one element.

    `opening_tag` is a fallback for the case the selector misses. It does miss:
    a selector is a path of `nth-of-type` positions through the document the
    *parser* saw, and by the time the browser has run the page's JavaScript the
    positions can have moved. Matching the element's own opening tag finds it
    again wherever it ended up, which is better than silently highlighting
    nothing - or, worse, the wrong element at the same position.
    """
    selector_json = json.dumps(dom_path)
    opening_json = json.dumps(opening_tag or "")
    css_json = json.dumps(_highlight_css(color))
    return f"""
(function() {{
    // Runs against whatever is currently loaded in the preview, which may
    // be a blank/partial document (the view is cleared between scans), so
    // every DOM assumption is checked before use.
    if (!document || !document.documentElement) {{ return; }}
    document.querySelectorAll('.__ai_scanner_highlight').forEach(function(el) {{
        el.classList.remove('__ai_scanner_highlight');
    }});
    var head = document.head || document.documentElement;
    var style = document.getElementById('__ai_scanner_style');
    if (!style && head) {{
        style = document.createElement('style');
        style.id = '__ai_scanner_style';
        style.textContent = {css_json};
        head.appendChild(style);
    }}
    var el = null;
    try {{
        el = document.querySelector({selector_json});
    }} catch (e) {{ /* not a selector this document understands */ }}
    if (!el) {{
        var opening = {opening_json};
        // Only the opening tag is compared, not the whole snippet: snippets
        // are truncated for the list ("<div class=\"a\">…</div>"), so a
        // whole-snippet prefix test failed for exactly the long elements
        // that needed the fallback most.
        var cut = opening.indexOf('>');
        if (cut !== -1) {{ opening = opening.slice(0, cut + 1); }}
        if (opening) {{
            var name = (opening.match(/^<([a-zA-Z][\\w:-]*)/) || [])[1];
            if (name) {{
                var candidates = document.getElementsByTagName(name);
                for (var i = 0; i < candidates.length; i++) {{
                    var html = candidates[i].outerHTML || '';
                    if (html.indexOf(opening) === 0) {{ el = candidates[i]; break; }}
                }}
            }}
        }}
    }}
    if (el) {{
        el.classList.add('__ai_scanner_highlight');
        el.scrollIntoView({{block: 'center', behavior: 'instant'}});
    }}
}})();
"""
