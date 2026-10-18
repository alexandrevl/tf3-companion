"""Structural validation of a parsed methodology document.

Everything that is wrong *structurally* is an error with a JSON-pointer-like path. Field
names that this companion does not know are not errors (see `support.py`).
"""

from __future__ import annotations

import dataclasses
import difflib
import math
import re
from typing import Any, Iterable

from . import fields as fieldmod
from .model import (
    AGGREGATES, CARRIERS, CHART_AGGS, CHART_TYPES, ENTITIES, FORMATS, ID_RE, IDENT_RE, MAX_DEPTH, MAX_ID,
    MAX_RULES, MAX_ROLES_PER_ENTITY, MAX_TEXT, OPS, ROLE_ENTITIES, SCHEMA_ID, SEVERITIES, VERSION_RE, Issue,
)
from .safe_regex import capture_names, check_pattern

TOP_KEYS = {"$schema", "schema", "id", "version", "name", "description", "author", "parameters", "markers",
            "name_patterns", "definitions", "roles", "engine", "rules", "recommendations", "ladders", "reports", "report_policies"}
REQUIRED_TOP = ("schema", "id", "version", "name", "description")
FIELD_RE = re.compile(r"^[a-z]+(\.[a-z_][a-z0-9_]*)+$")
PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_.]*)(?:\|([a-z]+))?\}")
MAX_EXPANDED_NODES = 20_000
MAX_OUTCOMES = 20
MAX_COLLECTION = {"parameters": 100, "markers": 50, "definitions": 100, "recommendations": 200,
                  "ladders": 50, "tables": 50, "charts": 50}
LEAF_KEYS = {"field", "measure", "op", "value"}
CONTROL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")

NUMERIC_OPS = {"eq", "ne", "lt", "le", "gt", "ge", "in", "not_in"}
OPS_BY_TYPE = {
    fieldmod.NUMBER: NUMERIC_OPS,
    fieldmod.STRING: {"eq", "ne", "in", "not_in", "matches"},
    fieldmod.BOOL: {"eq", "ne"},
    fieldmod.LIST_NUMBER: {"contains_any"},
    fieldmod.LIST_STRING: {"contains_any", "matches"},
}


def entity_of_field(name: str) -> str | None:
    head = name.split(".", 1)[0]
    return head if head in ENTITIES else None


@dataclasses.dataclass
class _Ctx:
    entity: str | None
    measures: tuple[str, ...] | None = None  # None: measures not allowed here
    allow_any_member: bool = False
    in_role_selector: bool = False
    allow_field: bool = True


class _State:
    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        self.issues: list[Issue] = []
        self.seen: set[tuple[str, str]] = set()
        self.expanded = 0
        self.params: dict[str, Any] = {}
        self.markers: set[str] = set()
        self.captures: set[str] = set()
        self.definitions: dict[str, Any] = {}
        self.roles: dict[str, set[str]] = {}
        self.rule_entities: dict[str, str] = {}
        self.aggregate_rules: dict[str, list[str]] = {}

    def error(self, path: str, message: str) -> None:
        key = (path, message)
        if key not in self.seen:
            self.seen.add(key)
            parts = path.split("/")
            kind = parts[1] if len(parts) > 2 else None
            item_id = None
            try:
                item = self.data[kind][int(parts[2])]
                item_id = item.get("id") if isinstance(item, dict) else None
            except (KeyError, IndexError, TypeError, ValueError):
                pass
            category = "reference" if "undefined" in message else "structure"
            code = "undefined-reference" if category == "reference" else (
                "unknown-key" if message.startswith("unknown key") else "invalid-structure")
            self.issues.append(Issue(path, message, category=category, code=code,
                                     itemKind=kind, itemId=item_id,
                                     ruleId=item_id if kind == "rules" else None))


def validate(data: Any) -> list[Issue]:
    st = _State(data if isinstance(data, dict) else {})
    if not isinstance(data, dict):
        st.error("", "a methodology must be a JSON object")
        return st.issues
    _top(st, data)
    from ..report_policy import validate_report_policies
    for path, message in validate_report_policies(data.get("report_policies", {})):
        st.error(path, message)
    return st.issues


# ---------------------------------------------------------------------------
# helpers

def _p(path: str, *parts: Any) -> str:
    return path + "".join("/" + str(p).replace("~", "~0").replace("/", "~1") for p in parts)


def _is_num(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and (not isinstance(value, float) or math.isfinite(value))


def _keys(st: _State, obj: Any, path: str, what: str, allowed: Iterable[str], required: Iterable[str] = ()) -> bool:
    if not isinstance(obj, dict):
        st.error(path, f"{what} must be an object")
        return False
    allowed = set(allowed)
    for key in obj:
        if key not in allowed:
            hint = difflib.get_close_matches(key, sorted(allowed), n=1)
            st.error(_p(path, key), f"unknown key '{key}' in {what}" + (f"; did you mean '{hint[0]}'?" if hint else
                                                                       f"; allowed keys: {', '.join(sorted(allowed))}"))
    for key in required:
        if key not in obj:
            st.error(path, f"{what} is missing required key '{key}'")
    return True


def _text(st: _State, value: Any, path: str, what: str, *, required: bool = False, limit: int = MAX_TEXT) -> None:
    if value is None:
        if required:
            st.error(path, f"{what} is required")
        return
    if not isinstance(value, str):
        st.error(path, f"{what} must be a string")
    elif len(value) > limit:
        st.error(path, f"{what} is {len(value)} characters; the limit is {limit}")
    elif required and not value.strip():
        st.error(path, f"{what} must not be empty")


def _ident(st: _State, value: Any, path: str, what: str) -> bool:
    if not isinstance(value, str) or not IDENT_RE.match(value) or len(value) > MAX_ID:
        st.error(path, f"{what} must match [a-z][a-z0-9_-]* and be at most {MAX_ID} characters")
        return False
    return True


def _collection(st: _State, value: Any, path: str, what: str, limit: int, kind: type) -> bool:
    if not isinstance(value, kind):
        st.error(path, f"{what} must be {'an object' if kind is dict else 'a list'}")
        return False
    if len(value) > limit:
        st.error(path, f"{what} has {len(value)} entries; the limit is {limit}")
        return False
    return True


# ---------------------------------------------------------------------------
# top level

def _top(st: _State, data: dict[str, Any]) -> None:
    _keys(st, data, "", "the methodology", TOP_KEYS, REQUIRED_TOP)
    if "schema" in data and data["schema"] != SCHEMA_ID:
        st.error("/schema", f"unsupported schema {data['schema']!r}; this companion supports '{SCHEMA_ID}'")
    ident = data.get("id")
    if not isinstance(ident, str) or not ID_RE.match(ident) or len(ident) > MAX_ID:
        if "id" in data:
            st.error("/id", f"id {ident!r} must be lowercase letters, digits and single hyphens (at most {MAX_ID} characters)")
    version = data.get("version")
    if "version" in data and (not isinstance(version, str) or not VERSION_RE.match(version)):
        st.error("/version", f"version {version!r} must be a three-part number such as 1.0.0")
    _text(st, data.get("name"), "/name", "name", required=True, limit=200)
    _text(st, data.get("description"), "/description", "description", required=True)
    _text(st, data.get("author"), "/author", "author")
    if "$schema" in data and not isinstance(data["$schema"], str):
        st.error("/$schema", "$schema must be a string")

    _parameters(st, data.get("parameters"))
    _markers(st, data.get("markers"))
    _name_patterns(st, data.get("name_patterns"))
    _definitions(st, data.get("definitions"))
    _roles(st, data.get("roles"))
    _engine(st, data.get("engine"))
    _rules(st, data.get("rules"))
    _recommendations(st, data.get("recommendations"))
    _ladders(st, data.get("ladders"))
    _reports(st, data.get("reports"))


def _parameters(st: _State, value: Any) -> None:
    if value is None:
        return
    if not _collection(st, value, "/parameters", "parameters", MAX_COLLECTION["parameters"], dict):
        return
    for name, param in value.items():
        path = _p("/parameters", name)
        if not _ident(st, name, path, "parameter name"):
            continue
        if _keys(st, param, path, f"parameter '{name}'", ("value", "description"), ("value",)):
            v = param.get("value")
            if not (_is_num(v) or isinstance(v, (str, bool))):
                st.error(_p(path, "value"), "parameter value must be a number, string or boolean")
            elif isinstance(v, str) and len(v) > 200:
                st.error(_p(path, "value"), "parameter string value is longer than 200 characters")
            else:
                st.params[name] = v
            _text(st, param.get("description"), _p(path, "description"), "description")


def _markers(st: _State, value: Any) -> None:
    if value is None:
        return
    if not _collection(st, value, "/markers", "markers", MAX_COLLECTION["markers"], dict):
        return
    for name, marker in value.items():
        path = _p("/markers", name)
        if not _ident(st, name, path, "marker name"):
            continue
        st.markers.add(name)
        if _keys(st, marker, path, f"marker '{name}'", ("symbol", "label", "description", "finding"), ("label",)):
            _text(st, marker.get("symbol"), _p(path, "symbol"), "symbol", limit=16)
            _text(st, marker.get("label"), _p(path, "label"), "label", required=True, limit=200)
            _text(st, marker.get("description"), _p(path, "description"), "description")
            if "finding" in marker and marker["finding"] not in SEVERITIES:
                st.error(_p(path, "finding"), f"finding must be one of {', '.join(SEVERITIES)}")


def _name_patterns(st: _State, value: Any) -> None:
    if value is None:
        return
    if not _keys(st, value, "/name_patterns", "name_patterns", ("line",)):
        return
    patterns = value.get("line")
    if patterns is None:
        return
    if not _collection(st, patterns, "/name_patterns/line", "name_patterns.line", 20, list):
        return
    seen: set[str] = set()
    for i, item in enumerate(patterns):
        path = _p("/name_patterns/line", i)
        if not _keys(st, item, path, "name pattern", ("id", "pattern", "description"), ("id", "pattern")):
            continue
        if _ident(st, item.get("id"), _p(path, "id"), "pattern id"):
            if item["id"] in seen:
                st.error(_p(path, "id"), f"duplicate name pattern id '{item['id']}'")
            seen.add(item["id"])
        problem = check_pattern(item.get("pattern"))
        if problem:
            st.error(_p(path, "pattern"), problem)
        else:
            st.captures.update(capture_names(item["pattern"]))


def _definitions(st: _State, value: Any) -> None:
    if value is None:
        return
    if not _collection(st, value, "/definitions", "definitions", MAX_COLLECTION["definitions"], dict):
        return
    for name in value:
        if _ident(st, name, _p("/definitions", name), "definition name"):
            st.definitions[name] = value[name]
    for name, cond in value.items():
        if name in st.definitions:
            _cond(st, cond, _p("/definitions", name), _Ctx(None), 1, (name,))


def _roles(st: _State, value: Any) -> None:
    if value is None:
        return
    if not _keys(st, value, "/roles", "roles", ROLE_ENTITIES):
        return
    for entity, roles in value.items():
        if entity not in ROLE_ENTITIES:
            continue
        path = _p("/roles", entity)
        if not _collection(st, roles, path, f"roles.{entity}", MAX_ROLES_PER_ENTITY, list):
            continue
        ids: set[str] = set()
        for i, role in enumerate(roles):
            rpath = _p(path, i)
            if not _keys(st, role, rpath, "role", ("id", "label", "description", "rationale", "select"), ("id", "select")):
                continue
            if _ident(st, role.get("id"), _p(rpath, "id"), "role id"):
                if role["id"] in ids:
                    st.error(_p(rpath, "id"), f"duplicate role id '{role['id']}' for {entity}")
                if role["id"] == "unclassified":
                    st.error(_p(rpath, "id"), "'unclassified' is reserved for entities that match no role")
                ids.add(role["id"])
            _text(st, role.get("label"), _p(rpath, "label"), "label", limit=200)
            _text(st, role.get("description"), _p(rpath, "description"), "description")
            _text(st, role.get("rationale"), _p(rpath, "rationale"), "rationale")
            if "select" in role:
                _cond(st, role["select"], _p(rpath, "select"), _Ctx(entity, in_role_selector=True), 1, ())
        st.roles[entity] = ids


def _engine(st: _State, value: Any) -> None:
    if value is None:
        return
    if not _keys(st, value, "/engine", "engine", ("thresholds", "findings")):
        return
    from ..analysis import FINDING_CODES, Thresholds

    fields = {f.name: f for f in dataclasses.fields(Thresholds)}
    thresholds = value.get("thresholds")
    if thresholds is not None and _collection(st, thresholds, "/engine/thresholds", "thresholds", 50, dict):
        for name, v in thresholds.items():
            path = _p("/engine/thresholds", name)
            if name not in fields:
                hint = difflib.get_close_matches(name, sorted(fields), n=1)
                st.error(path, f"unknown threshold '{name}'" + (f"; did you mean '{hint[0]}'?" if hint else
                                                               f"; known thresholds: {', '.join(sorted(fields))}"))
            elif not _is_num(v) or v < 0:
                st.error(path, "threshold must be a non-negative number")
            elif fields[name].type in (int, "int") and (isinstance(v, float) and not v.is_integer()):
                st.error(path, f"threshold '{name}' must be an integer")
    findings = value.get("findings")
    if findings is not None and _collection(st, findings, "/engine/findings", "engine.findings", 200, list):
        for i, item in enumerate(findings):
            path = _p("/engine/findings", i)
            if not _keys(st, item, path, "finding override", ("code", "role", "action", "severity"), ("code", "action")):
                continue
            code = item.get("code")
            if code not in FINDING_CODES:
                hint = difflib.get_close_matches(str(code), sorted(FINDING_CODES), n=1)
                st.error(_p(path, "code"), f"unknown finding code {code!r}" + (f"; did you mean '{hint[0]}'?" if hint else
                                                                              f"; known codes: {', '.join(sorted(FINDING_CODES))}"))
            action = item.get("action")
            if action not in ("off", "set_severity"):
                st.error(_p(path, "action"), "action must be 'off' or 'set_severity'")
            if action == "set_severity" and item.get("severity") not in SEVERITIES:
                st.error(_p(path, "severity"), f"set_severity requires severity {', '.join(SEVERITIES)}")
            if action == "off" and "severity" in item:
                st.error(_p(path, "severity"), "severity applies only to action 'set_severity'")
            if "role" in item:
                entity = FINDING_CODES.get(code)
                if code in FINDING_CODES and entity is None:
                    st.error(_p(path, "role"), f"finding '{code}' has no role-bearing entity")
                elif code in FINDING_CODES and item["role"] not in st.roles.get(entity, set()):
                    st.error(_p(path, "role"), f"role {item['role']!r} is not defined for {entity} roles")


# ---------------------------------------------------------------------------
# conditions

def _literal_ok(type_: str, op: str, value: Any) -> str | None:
    if op in ("in", "not_in", "contains_any"):
        if not isinstance(value, list) or not value:
            return "value must be a non-empty list"
        if len(value) > 200:
            return "list value has more than 200 entries"
        items = value
    else:
        items = [value]
    base = {fieldmod.LIST_NUMBER: fieldmod.NUMBER, fieldmod.LIST_STRING: fieldmod.STRING}.get(type_, type_)
    for item in items:
        if base == fieldmod.NUMBER and not _is_num(item):
            return "value must be a number" if op not in ("in", "not_in", "contains_any") else "list entries must be numbers"
        if base == fieldmod.STRING and not isinstance(item, str):
            return "value must be a string" if op not in ("in", "not_in", "contains_any") else "list entries must be strings"
        if base == fieldmod.BOOL and not isinstance(item, bool):
            return "value must be true or false"
    if op == "matches":
        return check_pattern(value)
    return None


def _field_ref(st: _State, name: Any, path: str, ctx: _Ctx, what: str = "field") -> fieldmod.FieldSpec | None | bool:
    """Validate a field name. Returns the spec, None for an unknown (unsupported) name, False on error."""
    if not isinstance(name, str) or not FIELD_RE.match(name):
        st.error(path, f"{what} must be a name such as 'line.profit_year'")
        return False
    entity = entity_of_field(name)
    if entity is None:
        st.error(path, f"unknown entity prefix in '{name}'; fields start with one of {', '.join(ENTITIES)}")
        return False
    if ctx.entity is not None and entity != ctx.entity:
        st.error(path, f"field '{name}' belongs to {entity} but this context is {ctx.entity}")
        return False
    capture = fieldmod.capture_name(name)
    if capture is not None and capture[1] not in st.captures:
        st.error(path, f"name capture '{capture[1]}' is not declared by any name pattern")
        return False
    spec = fieldmod.lookup(name)
    if spec is not None and ctx.in_role_selector and name.endswith(".role") and name.split(".")[0] == ctx.entity \
            and name.count(".") == 1:
        st.error(path, "a role selector cannot read its own entity's role")
        return False
    return spec


def _cond(st: _State, node: Any, path: str, ctx: _Ctx, depth: int, stack: tuple[str, ...]) -> None:
    st.expanded += 1
    if st.expanded > MAX_EXPANDED_NODES:
        if st.expanded == MAX_EXPANDED_NODES + 1:
            st.error(path, f"conditions expand to more than {MAX_EXPANDED_NODES} nodes (references included)")
        return
    if depth > MAX_DEPTH:
        st.error(path, f"condition nesting exceeds {MAX_DEPTH} levels")
        return
    if not isinstance(node, dict) or not node:
        st.error(path, "a condition must be a non-empty object")
        return
    if "all" in node or "any" in node:
        key = "all" if "all" in node else "any"
        _keys(st, node, path, f"'{key}' condition", (key,))
        parts = node.get(key)
        if not isinstance(parts, list) or not parts:
            st.error(_p(path, key), f"'{key}' needs a non-empty list of conditions")
            return
        if len(parts) > 50:
            st.error(_p(path, key), f"'{key}' has more than 50 conditions")
            return
        for i, part in enumerate(parts):
            _cond(st, part, _p(path, key, i), ctx, depth + 1, stack)
    elif "not" in node:
        _keys(st, node, path, "'not' condition", ("not",))
        _cond(st, node["not"], _p(path, "not"), ctx, depth + 1, stack)
    elif "ref" in node:
        _keys(st, node, path, "'ref' condition", ("ref",))
        name = node["ref"]
        if not isinstance(name, str) or name not in st.definitions:
            st.error(_p(path, "ref"), f"reference to undefined definition {name!r}")
        elif name in stack:
            st.error(_p(path, "ref"), f"cyclic reference: {' -> '.join(stack + (name,))}")
        else:
            _cond(st, st.definitions[name], _p("/definitions", name), ctx, depth + 1, stack + (name,))
    elif "any_member" in node:
        _keys(st, node, path, "'any_member' condition", ("any_member",))
        if not ctx.allow_any_member:
            st.error(path, "'any_member' is allowed only in an aggregate rule's 'having'")
            return
        _cond(st, node["any_member"], _p(path, "any_member"),
              dataclasses.replace(ctx, measures=None, allow_any_member=False, allow_field=True), depth + 1, stack)
    else:
        _leaf(st, node, path, ctx)


def _leaf(st: _State, node: dict[str, Any], path: str, ctx: _Ctx) -> None:
    if not _keys(st, node, path, "condition", LEAF_KEYS, ("op",)):
        return
    has_field, has_measure = "field" in node, "measure" in node
    if has_field == has_measure:
        st.error(path, "a condition needs exactly one of 'field' or 'measure' (or a combinator: all, any, not, ref)")
        return
    op = node.get("op")
    if op not in OPS:
        st.error(_p(path, "op"), f"unknown operator {op!r}; operators: {', '.join(OPS)}")
        return
    spec: Any = None
    type_: str | None = None
    if has_measure:
        if ctx.measures is None:
            st.error(_p(path, "measure"), "'measure' is allowed only in an aggregate rule's outcomes and 'having'")
            return
        if node["measure"] not in ctx.measures:
            st.error(_p(path, "measure"), f"undefined measure {node['measure']!r}")
            return
        type_ = fieldmod.NUMBER
        if op not in NUMERIC_OPS - {"in", "not_in"} | {"exists", "missing"}:
            st.error(_p(path, "op"), f"operator '{op}' does not apply to a measure")
            return
    else:
        if not ctx.allow_field:
            st.error(_p(path, "field"), "aggregate outcomes and 'having' read measures; use a measure 'where' or "
                                         "'any_member' to test member fields")
            return
        spec = _field_ref(st, node["field"], _p(path, "field"), ctx)
        if spec is False:
            return
        if spec is not None:
            type_ = spec.type
            if op not in ("exists", "missing") and op not in OPS_BY_TYPE[type_]:
                st.error(_p(path, "op"), f"operator '{op}' does not apply to {type_} field '{spec.name}'")
                return
    if op in ("exists", "missing"):
        if "value" in node:
            st.error(_p(path, "value"), f"operator '{op}' takes no value")
        return
    if "value" not in node:
        st.error(path, f"operator '{op}' needs a 'value'")
        return
    value = node["value"]
    if isinstance(value, dict):
        if set(value) != {"param"}:
            st.error(_p(path, "value"), "an object value must be {\"param\": <name>}")
            return
        pname = value["param"]
        if pname not in st.params:
            st.error(_p(path, "value", "param"), f"undefined parameter {pname!r}")
            return
        if op in ("in", "not_in", "contains_any"):
            st.error(_p(path, "value"), f"operator '{op}' needs a list literal, not a parameter")
            return
        if type_ is not None:
            problem = _literal_ok(type_, op, st.params[pname])
            if problem:
                st.error(_p(path, "value", "param"), f"parameter {pname!r}: {problem}")
        return
    if type_ is not None:
        problem = _literal_ok(type_, op, value)
        if problem:
            st.error(_p(path, "value"), problem)
    elif op == "matches":
        problem = check_pattern(value)
        if problem:
            st.error(_p(path, "value"), problem)
    elif op in ("in", "not_in", "contains_any") and not isinstance(value, list):
        st.error(_p(path, "value"), "value must be a list")


# ---------------------------------------------------------------------------
# templates

def template_placeholders(text: str) -> list[tuple[str, str | None]]:
    return [(m.group(1), m.group(2)) for m in PLACEHOLDER_RE.finditer(text.replace("{{", "").replace("}}", ""))]


def _template(st: _State, text: Any, path: str, entity: str | None, *, group: bool = False,
              measures: Iterable[str] = (), band: bool = False, what: str = "template") -> None:
    if not isinstance(text, str):
        st.error(path, f"{what} must be a string")
        return
    if len(text) > MAX_TEXT:
        st.error(path, f"{what} is {len(text)} characters; the limit is {MAX_TEXT}")
        return
    cleaned = text.replace("{{", "").replace("}}", "")
    leftover = PLACEHOLDER_RE.sub("", cleaned)
    if "{" in leftover or "}" in leftover:
        st.error(path, f"{what} has a malformed placeholder; use {{field}} or {{field|fmt}} ({{{{ and }}}} for literal braces)")
    measures = tuple(measures)
    for name, fmt in template_placeholders(text):
        if fmt is not None and fmt not in FORMATS:
            st.error(path, f"unknown format '{fmt}' in placeholder {{{name}|{fmt}}}; formats: {', '.join(FORMATS)}")
        if name == "group":
            if not group:
                st.error(path, "{group} is available only in aggregate rules")
        elif name.startswith("param."):
            if name[6:] not in st.params:
                st.error(path, f"placeholder references undefined parameter '{name[6:]}'")
        elif name in ("band.mode", "band.max_km"):
            if not band:
                st.error(path, f"{{{name}}} is available only in ladder text")
        elif "." not in name:
            if name not in measures:
                st.error(path, f"placeholder '{{{name}}}' is not a measure of this rule")
        else:
            if group:
                st.error(path, f"aggregate rules cannot reference entity field '{name}'; use {{group}} or a measure")
                continue
            _field_ref(st, name, path, _Ctx(entity), "placeholder")


# ---------------------------------------------------------------------------
# rules

def _outcomes(st: _State, items: Any, path: str, ctx: _Ctx, entity: str | None, *, group: bool = False,
              measures: Iterable[str] = ()) -> None:
    if not isinstance(items, list) or not items:
        st.error(path, "outcomes must be a non-empty list")
        return
    if len(items) > MAX_OUTCOMES:
        st.error(path, f"outcomes has {len(items)} entries; the limit is {MAX_OUTCOMES}")
        return
    for i, outcome in enumerate(items):
        opath = _p(path, i)
        if not _keys(st, outcome, opath, "outcome", ("when", "marker", "message"), ("when", "marker")):
            continue
        _cond(st, outcome.get("when"), _p(opath, "when"), ctx, 1, ())
        _marker_ref(st, outcome.get("marker"), _p(opath, "marker"))
        if "message" in outcome:
            _template(st, outcome["message"], _p(opath, "message"), entity, group=group, measures=measures, what="message")


def _marker_ref(st: _State, name: Any, path: str) -> None:
    if name not in st.markers:
        st.error(path, f"undefined marker {name!r}; define it under 'markers'")


def _default(st: _State, default: Any, path: str, entity: str | None, *, group: bool = False,
             measures: Iterable[str] = ()) -> None:
    if default is None:
        return
    if _keys(st, default, path, "default outcome", ("marker", "message"), ("marker",)):
        _marker_ref(st, default.get("marker"), _p(path, "marker"))
        if "message" in default:
            _template(st, default["message"], _p(path, "message"), entity, group=group, measures=measures, what="message")


def _rules(st: _State, value: Any) -> None:
    if value is None:
        return
    if not _collection(st, value, "/rules", "rules", MAX_RULES, list):
        return
    ids: set[str] = set()
    for i, rule in enumerate(value):
        path = _p("/rules", i)
        rid = rule.get("id") if isinstance(rule, dict) else None
        label = f"rule '{rid}'" if isinstance(rid, str) else f"rule #{i}"
        aggregate = isinstance(rule, dict) and "aggregate" in rule
        allowed = {"id", "label", "description", "rationale", "entity", "role"} | ({"aggregate"} if aggregate else {"outcomes", "default"})
        if not _keys(st, rule, path, label, allowed, ("id", "entity") + (("aggregate",) if aggregate else ("outcomes",))):
            continue
        if _ident(st, rid, _p(path, "id"), "rule id"):
            if rid in ids:
                st.error(_p(path, "id"), f"duplicate rule id '{rid}'")
            ids.add(rid)
        _text(st, rule.get("label"), _p(path, "label"), "label", limit=200)
        _text(st, rule.get("description"), _p(path, "description"), "description")
        _text(st, rule.get("rationale"), _p(path, "rationale"), "rationale")
        entity = rule.get("entity")
        if entity not in ENTITIES or (entity == "stop" and not aggregate):
            st.error(_p(path, "entity"), f"{label}: entity must be one of "
                                       f"{', '.join(e for e in ENTITIES if aggregate or e != 'stop')}")
            continue
        if isinstance(rid, str):
            st.rule_entities[rid] = entity
        if "role" in rule:
            if entity not in ROLE_ENTITIES:
                st.error(_p(path, "role"), f"{label}: {entity} entities have no roles")
            elif rule["role"] not in st.roles.get(entity, set()):
                st.error(_p(path, "role"), f"{label}: role {rule['role']!r} is not defined for {entity} roles")
        if aggregate:
            _aggregate(st, rule["aggregate"], _p(path, "aggregate"), entity, rid if isinstance(rid, str) else "")
        else:
            _outcomes(st, rule.get("outcomes"), _p(path, "outcomes"), _Ctx(entity), entity)
            _default(st, rule.get("default"), _p(path, "default"), entity)


def _aggregate(st: _State, agg: Any, path: str, entity: str, rid: str) -> None:
    if not _keys(st, agg, path, "aggregate", ("group_by", "measures", "having", "outcomes", "default"),
                 ("group_by", "measures", "outcomes")):
        return
    group_by = agg.get("group_by")
    if group_by != "town":
        _field_ref(st, group_by, _p(path, "group_by"), _Ctx(entity), "group_by")
    measures = agg.get("measures")
    names: list[str] = []
    if _collection(st, measures, _p(path, "measures"), "measures", 20, dict) and measures:
        for name, m in measures.items():
            mpath = _p(path, "measures", name)
            if not _ident(st, name, mpath, "measure name"):
                continue
            _measure(st, m, mpath, entity, group_by, tuple(names))
            names.append(name)
    elif isinstance(measures, dict) and not measures:
        st.error(_p(path, "measures"), "an aggregate needs at least one measure")
    if rid:
        st.aggregate_rules[rid] = list(names)
    ctx = _Ctx(entity, measures=tuple(names), allow_field=False)
    if "having" in agg:
        _cond(st, agg["having"], _p(path, "having"), dataclasses.replace(ctx, allow_any_member=True), 1, ())
    _outcomes(st, agg.get("outcomes"), _p(path, "outcomes"), ctx, entity, group=True, measures=names)
    _default(st, agg.get("default"), _p(path, "default"), entity, group=True, measures=names)


def _measure(st: _State, m: Any, path: str, entity: str, group_by: Any, earlier: tuple[str, ...]) -> None:
    if not isinstance(m, dict):
        st.error(path, "a measure must be an object")
        return
    kind = m.get("agg")
    if kind not in AGGREGATES:
        st.error(_p(path, "agg"), f"agg must be one of {', '.join(AGGREGATES)}")
        return
    if kind == "ratio":
        _keys(st, m, path, "ratio measure", ("agg", "numerator", "denominator"), ("numerator", "denominator"))
        for side in ("numerator", "denominator"):
            ref = m.get(side)
            spath = _p(path, side)
            if _keys(st, ref, spath, side, ("measure", "negate"), ("measure",)):
                if ref.get("measure") not in earlier:
                    st.error(_p(spath, "measure"), f"{side} must name a measure defined earlier in this aggregate")
                if "negate" in ref and not isinstance(ref["negate"], bool):
                    st.error(_p(spath, "negate"), "negate must be true or false")
        return
    _keys(st, m, path, f"{kind} measure", ("agg", "value", "where", "via", "distinct_by"))
    if kind != "count" and "value" not in m:
        st.error(path, f"a {kind} measure needs a 'value' field")
    if "value" in m:
        spec = _field_ref(st, m["value"], _p(path, "value"), _Ctx(entity))
        if spec and kind in ("sum", "min", "max") and spec.type != fieldmod.NUMBER:
            st.error(_p(path, "value"), f"a {kind} measure needs a number field; '{spec.name}' is {spec.type}")
    if "where" in m:
        _cond(st, m["where"], _p(path, "where"), _Ctx(entity), 1, ())
    if "via" in m:
        _field_ref(st, m["via"], _p(path, "via"), _Ctx(entity), "via")
    elif group_by == "town":
        st.error(path, "when grouping by 'town' every measure needs a 'via' field naming the town key")
    if "distinct_by" in m:
        _field_ref(st, m["distinct_by"], _p(path, "distinct_by"), _Ctx(entity), "distinct_by")


# ---------------------------------------------------------------------------
# recommendations, ladders, reports

def _recommendations(st: _State, value: Any) -> None:
    if value is None:
        return
    if not _collection(st, value, "/recommendations", "recommendations", MAX_COLLECTION["recommendations"], list):
        return
    ids: set[str] = set()
    for i, rec in enumerate(value):
        path = _p("/recommendations", i)
        if not _keys(st, rec, path, "recommendation", ("id", "when", "priority", "text", "rationale"),
                     ("id", "when", "priority", "text")):
            continue
        if _ident(st, rec.get("id"), _p(path, "id"), "recommendation id"):
            if rec["id"] in ids:
                st.error(_p(path, "id"), f"duplicate recommendation id '{rec['id']}'")
            ids.add(rec["id"])
        priority = rec.get("priority")
        if not isinstance(priority, int) or isinstance(priority, bool) or not 1 <= priority <= 5:
            st.error(_p(path, "priority"), "priority must be an integer from 1 to 5")
        _text(st, rec.get("rationale"), _p(path, "rationale"), "rationale")
        when = rec.get("when")
        entity: str | None = None
        rule_id = None
        if _keys(st, when, _p(path, "when"), "recommendation trigger", ("rule", "marker", "role"), ("rule", "marker")):
            rule_id = when.get("rule")
            if rule_id not in st.rule_entities:
                st.error(_p(path, "when", "rule"), f"recommendation trigger names undefined rule {rule_id!r}")
            else:
                entity = st.rule_entities[rule_id]
            _marker_ref(st, when.get("marker"), _p(path, "when", "marker"))
            if "role" in when and entity is not None and when["role"] not in st.roles.get(entity, set()):
                st.error(_p(path, "when", "role"), f"role {when['role']!r} is not defined for {entity} roles")
        if "text" in rec and entity is not None:
            aggregate = rule_id in st.aggregate_rules
            _template(st, rec["text"], _p(path, "text"), entity, group=aggregate,
                      measures=st.aggregate_rules.get(rule_id, ()), what="text")
        elif "text" in rec:
            _template(st, rec["text"], _p(path, "text"), None, what="text")


def _ladders(st: _State, value: Any) -> None:
    if value is None:
        return
    if not _collection(st, value, "/ladders", "ladders", MAX_COLLECTION["ladders"], list):
        return
    ids: set[str] = set()
    for i, ladder in enumerate(value):
        path = _p("/ladders", i)
        if not _keys(st, ladder, path, "ladder", ("id", "label", "description", "rationale", "entity", "role", "metric",
                                                 "bands", "text"), ("id", "entity", "metric", "bands", "text")):
            continue
        if _ident(st, ladder.get("id"), _p(path, "id"), "ladder id"):
            if ladder["id"] in ids:
                st.error(_p(path, "id"), f"duplicate ladder id '{ladder['id']}'")
            ids.add(ladder["id"])
        _text(st, ladder.get("label"), _p(path, "label"), "label", limit=200)
        _text(st, ladder.get("description"), _p(path, "description"), "description")
        _text(st, ladder.get("rationale"), _p(path, "rationale"), "rationale")
        if ladder.get("entity") != "line":
            st.error(_p(path, "entity"), "ladders apply to line entities")
        if "role" in ladder and ladder["role"] not in st.roles.get("line", set()):
            st.error(_p(path, "role"), f"role {ladder['role']!r} is not defined for line roles")
        spec = _field_ref(st, ladder.get("metric"), _p(path, "metric"), _Ctx("line"), "metric")
        if spec and spec.type != fieldmod.NUMBER:
            st.error(_p(path, "metric"), f"metric must be a number field; '{spec.name}' is {spec.type}")
        bands = ladder.get("bands")
        if not isinstance(bands, list) or not bands or len(bands) > 10:
            st.error(_p(path, "bands"), "bands must be a list of 1 to 10 bands")
        else:
            last = -1.0
            for j, band in enumerate(bands):
                bpath = _p(path, "bands", j)
                if not _keys(st, band, bpath, "band", ("max_km", "mode"), ("mode",)):
                    continue
                if band.get("mode") not in CARRIERS:
                    st.error(_p(bpath, "mode"), f"mode must be one of {', '.join(CARRIERS)}")
                final = j == len(bands) - 1
                if final and "max_km" in band:
                    st.error(_p(bpath, "max_km"), "the last band is open-ended and takes no max_km")
                elif not final:
                    limit = band.get("max_km")
                    if not _is_num(limit) or limit <= last:
                        st.error(_p(bpath, "max_km"), "max_km must be a number greater than the previous band's limit")
                    else:
                        last = limit
        _template(st, ladder.get("text"), _p(path, "text"), "line", band=True, what="text")


def _reports(st: _State, value: Any) -> None:
    if value is None:
        return
    if not _keys(st, value, "/reports", "reports", ("kinds", "tables", "charts")):
        return
    from ..reports import VALID_KINDS

    kinds = value.get("kinds")
    if kinds is not None and _collection(st, kinds, "/reports/kinds", "kinds", 40, list):
        for i, kind in enumerate(kinds):
            if kind not in VALID_KINDS:
                st.error(_p("/reports/kinds", i), f"unknown report kind {kind!r}; valid kinds: {', '.join(VALID_KINDS)}")
        if len(set(map(str, kinds))) != len(kinds):
            st.error("/reports/kinds", "report kinds must not repeat")
    tables = value.get("tables")
    if tables is not None and _collection(st, tables, "/reports/tables", "tables", MAX_COLLECTION["tables"], list):
        ids: set[str] = set()
        for i, table in enumerate(tables):
            path = _p("/reports/tables", i)
            if not _keys(st, table, path, "table", ("id", "label", "entity", "role", "sort", "descending", "columns", "limit"),
                         ("id", "entity", "columns")):
                continue
            if _ident(st, table.get("id"), _p(path, "id"), "table id"):
                if table["id"] in ids:
                    st.error(_p(path, "id"), f"duplicate table id '{table['id']}'")
                ids.add(table["id"])
            _text(st, table.get("label"), _p(path, "label"), "label", limit=200)
            entity = table.get("entity")
            if entity not in ENTITIES:
                st.error(_p(path, "entity"), f"entity must be one of {', '.join(ENTITIES)}")
                continue
            _report_role(st, table, path, entity)
            ctx = _Ctx(entity)
            if "sort" in table:
                _field_ref(st, table["sort"], _p(path, "sort"), ctx, "sort")
            if "descending" in table and not isinstance(table["descending"], bool):
                st.error(_p(path, "descending"), "descending must be true or false")
            columns = table.get("columns")
            if not isinstance(columns, list) or not 1 <= len(columns) <= 12:
                st.error(_p(path, "columns"), "columns must be a list of 1 to 12 fields")
            else:
                for j, column in enumerate(columns):
                    _field_ref(st, column, _p(path, "columns", j), ctx, "column")
            limit = table.get("limit")
            if "limit" in table and (not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 500):
                st.error(_p(path, "limit"), "limit must be an integer from 1 to 500")
    charts = value.get("charts")
    if charts is not None and _collection(st, charts, "/reports/charts", "charts", MAX_COLLECTION["charts"], list):
        ids = set()
        for i, chart in enumerate(charts):
            path = _p("/reports/charts", i)
            if not _keys(st, chart, path, "chart", ("id", "label", "type", "entity", "role", "metric", "agg", "group_by"),
                         ("id", "type", "entity", "agg")):
                continue
            if _ident(st, chart.get("id"), _p(path, "id"), "chart id"):
                if chart["id"] in ids:
                    st.error(_p(path, "id"), f"duplicate chart id '{chart['id']}'")
                ids.add(chart["id"])
            _text(st, chart.get("label"), _p(path, "label"), "label", limit=200)
            if chart.get("type") not in CHART_TYPES:
                st.error(_p(path, "type"), f"type must be one of {', '.join(CHART_TYPES)}")
            if chart.get("agg") not in CHART_AGGS:
                st.error(_p(path, "agg"), f"agg must be one of {', '.join(CHART_AGGS)}")
            entity = chart.get("entity")
            if entity not in ENTITIES:
                st.error(_p(path, "entity"), f"entity must be one of {', '.join(ENTITIES)}")
                continue
            _report_role(st, chart, path, entity)
            ctx = _Ctx(entity)
            if chart.get("agg") != "count" and "metric" not in chart:
                st.error(path, f"agg '{chart.get('agg')}' needs a metric field")
            if "metric" in chart:
                spec = _field_ref(st, chart["metric"], _p(path, "metric"), ctx, "metric")
                if spec and spec.type != fieldmod.NUMBER:
                    st.error(_p(path, "metric"), f"metric must be a number field; '{spec.name}' is {spec.type}")
            group_by = chart.get("group_by")
            if group_by is not None and group_by != "role":
                spec = _field_ref(st, group_by, _p(path, "group_by"), ctx, "group_by")
                if spec and spec.type not in (fieldmod.STRING, fieldmod.BOOL):
                    st.error(_p(path, "group_by"), "group_by must be 'role' or a string/boolean field")
            if group_by == "role" and entity not in ROLE_ENTITIES:
                st.error(_p(path, "group_by"), f"{entity} entities have no roles")
            if chart.get("type") in ("bar", "pie") and group_by is None:
                st.error(path, "bar and pie charts need a group_by")


def _report_role(st: _State, obj: dict[str, Any], path: str, entity: str) -> None:
    if "role" in obj:
        if entity not in ROLE_ENTITIES:
            st.error(_p(path, "role"), f"{entity} entities have no roles")
        elif obj["role"] not in st.roles.get(entity, set()):
            st.error(_p(path, "role"), f"role {obj['role']!r} is not defined for {entity} roles")
