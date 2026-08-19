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

_HIGHLIGHT_CSS = (
    ".__ai_scanner_highlight { outline: 3px solid #ff4444 !important; "
    "background: rgba(255,68,68,0.25) !important; }"
)


def build_highlight_js(dom_path: str, opening_tag: str = "") -> str:
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
    css_json = json.dumps(_HIGHLIGHT_CSS)
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
        if (opening) {{
            var name = (opening.match(/^<([a-zA-Z][\w:-]*)/) || [])[1];
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
