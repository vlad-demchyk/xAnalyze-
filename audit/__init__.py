"""Site and repository auditing: accessibility, performance, SEO and best
practices, from one pass over one parsed document.

Importing this package registers every built-in rule with `RuleRegistry`,
the same way `detectors/` registers its backends.
"""
from . import rules  # noqa: F401 - registers the built-in rules

from .base import (  # noqa: F401
    ACCESSIBILITY, BEST_PRACTICES, CATEGORIES, CRITICAL, EXACT, MINOR,
    MODERATE, NEEDS_BROWSER, PERFORMANCE, SEO, SERIOUS, SEVERITY_ORDER,
    Issue, Rule, RuleRegistry,
)
from .engine import (  # noqa: F401
    AccessibilityResult, DocumentReport, analyze_document, analyze_files,
    analyze_page_file, analyze_pages,
)
