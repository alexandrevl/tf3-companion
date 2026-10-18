"""Three-valued (Kleene) condition evaluation.

`True` and `False` are definite answers; `None` means *unknown* (a value was missing).
A rule fires only on `True`; an unknown is counted as not evaluable and never as satisfied.
"""

from __future__ import annotations

from typing import Any, Iterable, Protocol

from .safe_regex import bounded_search


class Scope(Protocol):
    params: dict[str, Any]
    definitions: dict[str, Any]

    def field(self, name: str) -> Any: ...
    def measure(self, name: str) -> Any: ...
    def members(self) -> Iterable["Scope"]: ...


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _comparable(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool)
    if _is_number(left) and _is_number(right):
        return True
    return isinstance(left, str) and isinstance(right, str)


def compare(op: str, left: Any, right: Any) -> bool | None:
    """Apply one operator; `left` is the entity's value (None = missing)."""
    if op == "exists":
        return left is not None
    if op == "missing":
        return left is None
    if left is None:
        return None
    if op == "contains_any":
        items = left if isinstance(left, list) else [left]
        return any(item in right for item in items)
    if op == "matches":
        items = left if isinstance(left, list) else [left]
        return any(isinstance(item, str) and bounded_search(right, item) is not None for item in items)
    if op in ("in", "not_in"):
        if not all(_comparable(left, r) for r in right):
            return None
        found = any(left == r for r in right)
        return found if op == "in" else not found
    if not _comparable(left, right):
        return None
    if op == "eq":
        return left == right
    if op == "ne":
        return left != right
    if op == "lt":
        return left < right
    if op == "le":
        return left <= right
    if op == "gt":
        return left > right
    if op == "ge":
        return left >= right
    raise ValueError(f"unknown operator {op}")


def evaluate(node: dict[str, Any], scope: Scope) -> bool | None:
    if "all" in node:
        result: bool | None = True
        for part in node["all"]:
            value = evaluate(part, scope)
            if value is False:
                return False
            if value is None:
                result = None
        return result
    if "any" in node:
        result = False
        for part in node["any"]:
            value = evaluate(part, scope)
            if value is True:
                return True
            if value is None:
                result = None
        return result
    if "not" in node:
        value = evaluate(node["not"], scope)
        return None if value is None else not value
    if "ref" in node:
        return evaluate(scope.definitions[node["ref"]], scope)
    if "any_member" in node:
        result = False
        for member in scope.members():
            value = evaluate(node["any_member"], member)
            if value is True:
                return True
            if value is None:
                result = None
        return result
    left = scope.measure(node["measure"]) if "measure" in node else scope.field(node["field"])
    op = node["op"]
    if op in ("exists", "missing"):
        return compare(op, left, None)
    right = node["value"]
    if isinstance(right, dict):
        right = scope.params[right["param"]]
    return compare(op, left, right)


def first_true(outcomes: list[dict[str, Any]], scope: Scope) -> tuple[int | None, bool]:
    """Index of the first outcome whose condition is true, and whether the entity is not evaluable.

    An unknown outcome before a true one makes the result undecidable: the earlier outcome might
    have applied, so the entity is reported as not evaluable instead of getting a later marker.
    """
    unknown = False
    for index, outcome in enumerate(outcomes):
        value = evaluate(outcome["when"], scope)
        if value is True:
            return (None, True) if unknown else (index, False)
        if value is None:
            unknown = True
    return None, unknown
