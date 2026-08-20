"""Importing this package registers every built-in rule.

Split by category rather than by mechanism, because that is how the rules
are read, edited and argued about — someone tuning SEO checks should not
have to scroll past keyboard-focus logic to find them.
"""
from . import accessibility  # noqa: F401
from . import best_practices  # noqa: F401
from . import performance  # noqa: F401
from . import provenance  # noqa: F401
from . import seo  # noqa: F401
