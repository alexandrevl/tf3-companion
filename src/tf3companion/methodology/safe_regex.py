"""Bounded regular expressions for methodology name patterns and `matches` conditions.

A pattern is accepted only when it cannot backtrack catastrophically on a short subject:
length cap, no backreferences or lookarounds, no quantified group that contains another
quantifier or an alternation, and a small budget of unbounded quantifiers. Matching always
truncates the subject.
"""

from __future__ import annotations

import re
from functools import lru_cache
from re import _constants as _c  # type: ignore[attr-defined]
from re import _parser as _p  # type: ignore[attr-defined]

from .model import MAX_REGEX, MAX_SUBJECT, MAX_UNBOUNDED_QUANTIFIERS

_REPEATS = {_c.MAX_REPEAT, _c.MIN_REPEAT, getattr(_c, "POSSESSIVE_REPEAT", _c.MAX_REPEAT)}


def check_pattern(pattern: str) -> str | None:
    """Return a problem description, or None when the pattern is acceptable."""
    if not isinstance(pattern, str):
        return "pattern must be a string"
    if len(pattern) > MAX_REGEX:
        return f"pattern is {len(pattern)} characters; the limit is {MAX_REGEX}"
    try:
        parsed = _p.parse(pattern)
        re.compile(pattern)
    except (re.error, RecursionError, OverflowError) as exc:
        return f"invalid regular expression: {exc}"
    state = {"unbounded": 0}
    problem = _walk(parsed, False, state)
    if problem:
        return problem
    if state["unbounded"] > MAX_UNBOUNDED_QUANTIFIERS:
        return (
            f"pattern has {state['unbounded']} unbounded quantifiers; at most {MAX_UNBOUNDED_QUANTIFIERS} are allowed"
        )
    return None


def _walk(items, in_repeat: bool, state: dict[str, int]) -> str | None:
    for op, av in items:
        if op in (_c.GROUPREF, _c.GROUPREF_EXISTS):
            return "backreferences are not allowed"
        if op in (_c.ASSERT, _c.ASSERT_NOT):
            return "lookahead and lookbehind are not allowed"
        if op in _REPEATS:
            low, high, sub = av
            if in_repeat:
                return "a quantified group may not contain another quantifier"
            if high == _c.MAXREPEAT:
                state["unbounded"] += 1
            problem = _walk(sub, True, state)
            if problem:
                return problem
        elif op == _c.BRANCH:
            if in_repeat:
                return "a quantified group may not contain an alternation"
            for branch in av[1]:
                problem = _walk(branch, in_repeat, state)
                if problem:
                    return problem
        elif op == _c.SUBPATTERN:
            problem = _walk(av[3], in_repeat, state)
            if problem:
                return problem
        elif op == getattr(_c, "ATOMIC_GROUP", None):
            problem = _walk(av, in_repeat, state)
            if problem:
                return problem
    return None


def capture_names(pattern: str) -> list[str]:
    return list(re.compile(pattern).groupindex)


@lru_cache(maxsize=256)
def _compiled(pattern: str) -> re.Pattern[str]:
    if check_pattern(pattern) is not None:
        raise ValueError("unsafe pattern")
    return re.compile(pattern)


def bounded_search(pattern: str, subject: str) -> re.Match[str] | None:
    """Search a pattern in the subject truncated to MAX_SUBJECT characters."""
    return _compiled(pattern).search(subject[:MAX_SUBJECT])
