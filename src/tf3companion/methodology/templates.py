"""Message templates: `{path}` / `{path|fmt}` placeholders over measured values, and text hygiene."""

from __future__ import annotations

import re
from typing import Any, Callable

PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_.]*)(?:\|([a-z]+))?\}")
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
NOT_AVAILABLE = "n/a"


def clean_text(value: Any, limit: int = 2000) -> str:
    """Strip control characters (newlines become spaces) and bound the length."""
    return _CONTROL_RE.sub(" ", str(value))[:limit]


def _trim(number: float, decimals: int) -> str:
    text = f"{number:.{decimals}f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def format_value(value: Any, fmt: str | None) -> str:
    if value is None:
        return NOT_AVAILABLE
    if isinstance(value, list):
        return ", ".join(format_value(v, fmt) for v in value)
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        if fmt == "money" or fmt == "int":
            return f"{round(value):,}"
        if fmt == "pct":
            return f"{value * 100:.0f}%"
        if fmt == "km":
            return f"{value:.1f} km"
        if fmt == "years":
            return f"{_trim(value, 1)} years"
        return _trim(value, 2)
    return clean_text(value, 200)


_TOKEN_RE = re.compile(r"(\{\{|\}\}|\{[A-Za-z_][A-Za-z0-9_.]*(?:\|[a-z]+)?\})")


def render(template: str, lookup: Callable[[str], Any]) -> str:
    """Fill placeholders; `{{` and `}}` are literal braces. Missing values print as n/a."""
    out: list[str] = []
    for token in _TOKEN_RE.split(template):
        match = PLACEHOLDER_RE.fullmatch(token)
        if token == "{{":
            out.append("{")
        elif token == "}}":
            out.append("}")
        elif match:
            out.append(format_value(lookup(match.group(1)), match.group(2)))
        else:
            out.append(token)
    return clean_text("".join(out))
