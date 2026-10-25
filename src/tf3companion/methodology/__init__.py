"""Analysis methodologies: declarative, shareable player policy applied to snapshot evidence.

The engine computes facts; a methodology (one JSON file) says how those facts are classified,
judged and presented. See docs/methodologies.md.
"""

from .engine import Verdicts, evaluate, thresholds_for
from .loader import load_default, load_file, load_packaged, parse
from .model import FILE_SUFFIX, SCHEMA_ID, Issue, Methodology, MethodologyError

__all__ = [
    "FILE_SUFFIX",
    "SCHEMA_ID",
    "Issue",
    "Methodology",
    "MethodologyError",
    "Verdicts",
    "evaluate",
    "load_default",
    "load_file",
    "load_packaged",
    "parse",
    "thresholds_for",
]
