"""Importing this package registers every built-in detector with
DetectorFactory. Add new backends by creating a module here that calls
DetectorFactory.register(...) at import time, then import it below.
"""
from . import heuristic  # noqa: F401
from . import unicode_anomalies  # noqa: F401
from . import offline  # noqa: F401
from . import claude_llm_judge  # noqa: F401
from . import xformat_llm_judge  # noqa: F401
from . import claude_code_llm_judge  # noqa: F401
from . import claude_watermark_stub  # noqa: F401
from . import hybrid  # noqa: F401

from .base import Detector, DetectorUnavailable  # noqa: F401
from .factory import DetectorFactory  # noqa: F401
