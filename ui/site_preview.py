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


def build_highlight_js(dom_path: str) -> str:
    selector_json = json.dumps(dom_path)
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
    try {{
        var el = document.querySelector({selector_json});
        if (el) {{
            el.classList.add('__ai_scanner_highlight');
            el.scrollIntoView({{block: 'center', behavior: 'instant'}});
        }}
    }} catch (e) {{ /* selector didn't match after page changed shape — ignore */ }}
}})();
"""
