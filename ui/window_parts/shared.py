"""Names shared between the window's parts and its facade.

Moved out of `ui.main_window` so the part modules can use them without
importing the facade back (which would be circular). The facade re-imports
everything defined here, so existing references keep working.
"""
from __future__ import annotations

from models import Confidence
from ui import theme

#: Auditing is a third source of findings, not a third detector: it reports
#: defects in the document (missing alt text, a broken heading order, a page
#: that ships 4 MB of JavaScript) rather than passages a person wrote. It
#: shares the toolbar's URL and depth fields because it asks about the same
#: site, and nothing else.
MODE_AUDIT = "audit"

MODE_WEB = "web"
MODE_REPO = "repo"

#: One HTML file the user picked, rather than a folder or a site. The same
#: three words `audit.engine.AccessibilityResult.mode` uses, because they end
#: up being the same fact read from two places.
#:
#: This was referenced by `MainWindow.mode` and by the browser pass's
#: `allow_local_files` before it existed anywhere - so choosing "single file"
#: as the source raised `NameError` on a property that half the window reads.
#: It did not show up as a failing test because no test selected that source
#: and then asked for the mode.
MODE_FILE = "file"

#: Shown beside a lowered score so it does not read as the detector being
#: unsure rather than as a decision the user already made.
SUPPRESSED_NOTE = (
    "Score lowered: part of this finding was suppressed (a phrase, rule or "
    "signal you've already dismissed)."
)


#: Severity mapped to the badge class the style sheet already paints for
#: confidence. One vocabulary of colour for the window, not two.
SEVERITY_BADGE = {
    "critical": theme.CLASS_BADGE_HIGH,
    "serious": theme.CLASS_BADGE_HIGH,
    "moderate": theme.CLASS_BADGE_MEDIUM,
    "minor": theme.CLASS_BADGE_LOW,
}

#: Severity is the audit's name for the axis the finding delegate paints as
#: confidence. Mapped here rather than teaching the delegate a second
#: vocabulary, which would mean two ways to colour one row.
SEVERITY_CONFIDENCE = {
    "critical": Confidence.HIGH,
    "serious": Confidence.HIGH,
    "moderate": Confidence.MEDIUM,
    "minor": Confidence.LOW,
}


def browser_url(source: str) -> str:
    """The address to open for a document.

    A crawled page already is a URL; a file has to become an absolute one,
    because `file://page.html` is not something a browser can resolve.
    """
    if source.startswith(("http://", "https://", "file://")):
        return source
    from pathlib import Path
    return Path(source).resolve().as_uri()


# Private aliases: the names these lived under inside main_window.py before
# the split, kept so older call sites and tests read unchanged.
_SEVERITY_BADGE = SEVERITY_BADGE
_SEVERITY_CONFIDENCE = SEVERITY_CONFIDENCE
_browser_url = browser_url
_SUPPRESSED_NOTE = SUPPRESSED_NOTE
