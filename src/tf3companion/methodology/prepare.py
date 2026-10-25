"""Operation-scoped compatibility checks; no store, filesystem writes or game discovery."""
from __future__ import annotations

import copy
import json
import math
from dataclasses import replace
from typing import Any

from . import fields
from .loader import parse
from .model import MAX_BYTES, Issue, Methodology, MethodologyError, content_hash
from .support import classify, static_probe


def pointer(value: Any) -> str:
    return str(value).replace("~", "~0").replace("/", "~1")


def _field_issues(data: Any, path: str = "", rule: str | None = None) -> list[Issue]:
    issues = []
    if isinstance(data, dict):
        rule = data.get("id", rule) if path.startswith("/rules/") and path.count("/") == 2 else rule
        for key, value in data.items():
            p = path + "/" + pointer(key)
            if key == "field" and isinstance(value, str):
                spec = fields.lookup(value)
                if spec is None:
                    issues.append(Issue(p, f"Unknown field '{value}'.", category="unsupported-field",
                                        code="unsupported-field", itemKind="rule" if rule else None,
                                        itemId=rule, ruleId=rule))
                elif not spec.collected:
                    issues.append(Issue(p, f"Field '{value}' requires unavailable collector data: {', '.join(spec.requires)}.",
                                        category="unsupported-capability", code="unsupported-capability",
                                        itemKind="rule" if rule else None, itemId=rule, ruleId=rule))
            issues.extend(_field_issues(value, p, rule))
    elif isinstance(data, list):
        for index, value in enumerate(data):
            issues.extend(_field_issues(value, path + f"/{index}", rule))
    return issues


def inspect(raw: bytes, *, source: str = "file", path: str | None = None,
            overrides: dict[str, Any] | None = None) -> tuple[Methodology | None, dict[str, Any]]:
    issues: list[Issue] = []
    m = None
    structurally_valid = False
    rows = []
    params = None
    try:
        m = parse(raw, source=source, path=path)
        structurally_valid = True
    except MethodologyError as exc:
        issues.extend(exc.issues)
        if len(raw) <= MAX_BYTES and not any(i.category in ("syntax", "unsupported-schema") for i in issues):
            try:
                issues.extend(_field_issues(json.loads(raw)))
            except (ValueError, UnicodeError, RecursionError):
                pass
    if m is not None:
        issues.extend(_field_issues(m.data))
        from .resolve import support_rows
        rows = support_rows(m, classify(m, static_probe))
        for row in rows:
            if row["status"] != "ok":
                category = "unsupported-capability" if row["status"] == "skipped" else "unsupported-field"
                kind, ident = row["kind"], row["id"]
                collection = {"rule": "rules", "ladder": "ladders", "recommendation": "recommendations"}.get(kind)
                location = "/roles/" + pointer(ident) if kind == "roles" else ""
                if collection:
                    location = next((f"/{collection}/{n}" for n, item in enumerate(m.data.get(collection, []))
                                     if item["id"] == ident), "")
                elif kind in ("table", "chart"):
                    collection = kind + "s"
                    location = next((f"/reports/{collection}/{n}" for n, item in enumerate(m.data.get("reports", {}).get(collection, []))
                                     if item["id"] == ident), "")
                issues.append(Issue(location, row["reason"] or "Unsupported capability", category=category,
                                    code=category, itemKind=kind, itemId=ident,
                                    ruleId=ident if kind == "rule" else None))
        params = copy.deepcopy(m.parameters)
        effective = copy.deepcopy(m.data)
        for name, value in (overrides or {}).items():
            p = "/overrides/" + pointer(name)
            current = params.get(name)
            numeric = isinstance(current, (int, float)) and not isinstance(current, bool)
            valid_type = (isinstance(value, (int, float)) and not isinstance(value, bool)) if numeric else type(value) is type(current)
            if name not in params or not valid_type or (isinstance(value, float) and not math.isfinite(value)):
                issues.append(Issue(p, f"Invalid override '{name}': expected declared parameter type and finite value.",
                                    category="override", code="invalid-override"))
                continue
            params[name] = copy.deepcopy(value)
            effective["parameters"][name]["value"] = copy.deepcopy(value)
        from .validate import validate
        for issue in validate(effective):
            names = [name for name in (overrides or {}) if name in params and
                     (repr(name) in issue.message or issue.path.startswith("/parameters/" + pointer(name) + "/"))]
            for name in names:
                issues.append(replace(issue, path="/overrides/" + pointer(name), category="override",
                                      code="invalid-effective-policy", relatedPaths=(issue.path,)))
            if not names:
                issues.append(issue)
        if not issues:
            m = replace(m, data=effective, effective_overrides=copy.deepcopy(overrides or {}))
    report = {"structurallyValid": structurally_valid, "activationEligible": structurally_valid and not issues,
              "diagnostics": [i.to_dict() for i in issues], "errors": [str(i) for i in issues],
              "sha256": content_hash(raw), "hash": "sha256:" + content_hash(raw)[:12],
              "rules": rows, "unsupported": [r for r in rows if r["status"] != "ok"],
              "parameters": params, "parameterOverrides": copy.deepcopy(overrides or {})}
    if m:
        report["identity"] = m.identity
    return m, report


def prepare(m: Methodology, overrides: dict[str, Any] | None = None) -> Methodology:
    """Revalidate original bytes and effective inputs, never a mutable validation stamp."""
    raw = m.raw or json.dumps(m.data, allow_nan=False).encode()
    inherited = copy.deepcopy(dict(m.effective_overrides))
    if m.raw:
        captured = parse(m.raw, source=m.source, path=m.path)
        expected = copy.deepcopy(captured.data)
        for name, value in inherited.items():
            if name in (expected.get("parameters") or {}):
                expected["parameters"][name]["value"] = value
        if expected != m.data:
            raise MethodologyError([Issue(
                "", "In-memory methodology content changed after loading; load the current source bytes again.",
                code="modified-policy-content")], m.path or m.identity)
    effective_overrides = {**inherited, **copy.deepcopy(overrides or {})}
    result, report = inspect(raw, source=m.source, path=m.path, overrides=effective_overrides)
    if not report["activationEligible"]:
        raise MethodologyError([Issue(**{**i, "relatedPaths": tuple(i["relatedPaths"])})
                                for i in report["diagnostics"]], m.path or m.identity)
    assert result is not None
    return replace(result, selection=copy.deepcopy(dict(m.selection)),
                   effective_overrides=effective_overrides)
