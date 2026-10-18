"""What each methodology item needs, and whether this companion and save can supply it.

Two distinct outcomes (see design D4):
* *unsupported*: the item names a field this companion does not define (typo or newer release);
* *skipped*: the field is defined but the snapshot data it needs is absent.
Per-entity missing values are handled later, by the evaluator, as *not evaluable*.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from . import fields as fieldmod
from .model import Methodology
from .templates import PLACEHOLDER_RE

OK, SKIPPED, UNSUPPORTED = "ok", "skipped", "unsupported"
HUMAN_PATHS = {"stations[].position": "station positions"}

Probe = Callable[[fieldmod.FieldSpec], str | None]


@dataclass
class Support:
    status: str = OK
    reasons: list[str] = field(default_factory=list)
    needs: set[str] = field(default_factory=set)

    @property
    def reason(self) -> str | None:
        return "; ".join(self.reasons) if self.reasons else None

    def merge(self, status: str, reason: str) -> None:
        if status == UNSUPPORTED:
            self.status = UNSUPPORTED
        elif status == SKIPPED and self.status == OK:
            self.status = SKIPPED
        if reason not in self.reasons:
            self.reasons.append(reason)


@dataclass
class ItemInfo:
    kind: str                      # rule | ladder | recommendation | table | chart
    id: str
    entity: str | None
    fields: set[str] = field(default_factory=set)
    role_entities: set[str] = field(default_factory=set)
    rule: str | None = None        # trigger rule (recommendations)


# ---------------------------------------------------------------------------
# field collection

def condition_fields(node: Any, definitions: dict[str, Any], out: set[str] | None = None,
                     _stack: tuple[str, ...] = ()) -> set[str]:
    out = set() if out is None else out
    if not isinstance(node, dict):
        return out
    for key in ("all", "any"):
        if key in node:
            for part in node[key]:
                condition_fields(part, definitions, out, _stack)
    if "not" in node:
        condition_fields(node["not"], definitions, out, _stack)
    if "any_member" in node:
        condition_fields(node["any_member"], definitions, out, _stack)
    if "ref" in node and node["ref"] not in _stack and node["ref"] in definitions:
        condition_fields(definitions[node["ref"]], definitions, out, _stack + (node["ref"],))
    if "field" in node:
        out.add(node["field"])
    return out


def template_fields(text: Any) -> set[str]:
    if not isinstance(text, str):
        return set()
    names = {m.group(1) for m in PLACEHOLDER_RE.finditer(text.replace("{{", "").replace("}}", ""))}
    return {n for n in names if "." in n and not n.startswith(("param.", "band."))}


def role_entities(names: Iterable[str]) -> set[str]:
    """Entity kinds whose role assignment a set of field names depends on."""
    out = set()
    for name in names:
        parts = name.split(".")
        if parts[-1] == "role":
            out.add("line" if len(parts) == 3 and parts[1] == "line" else parts[0])
    return out


def items_of(m: Methodology) -> list[ItemInfo]:
    data = m.data
    defs = data.get("definitions") or {}
    items: list[ItemInfo] = []
    for rule in data.get("rules") or []:
        info = ItemInfo("rule", rule["id"], rule["entity"])
        agg = rule.get("aggregate")
        if agg is None:
            for outcome in rule["outcomes"]:
                info.fields |= condition_fields(outcome["when"], defs)
                info.fields |= template_fields(outcome.get("message"))
            info.fields |= template_fields((rule.get("default") or {}).get("message"))
        else:
            if agg["group_by"] != "town":
                info.fields.add(agg["group_by"])
            for measure in agg["measures"].values():
                for key in ("value", "via", "distinct_by"):
                    if key in measure:
                        info.fields.add(measure[key])
                if "where" in measure:
                    info.fields |= condition_fields(measure["where"], defs)
            if "having" in agg:
                info.fields |= condition_fields(agg["having"], defs)
            for outcome in agg["outcomes"]:
                info.fields |= condition_fields(outcome["when"], defs)
        if "role" in rule:
            info.role_entities.add(rule["entity"])
        info.role_entities |= role_entities(info.fields)
        items.append(info)
    for ladder in data.get("ladders") or []:
        info = ItemInfo("ladder", ladder["id"], "line", {ladder["metric"]} | template_fields(ladder["text"]))
        if "role" in ladder:
            info.role_entities.add("line")
        info.role_entities |= role_entities(info.fields)
        items.append(info)
    rule_entities = {r["id"]: r["entity"] for r in data.get("rules") or []}
    for rec in data.get("recommendations") or []:
        info = ItemInfo("recommendation", rec["id"], rule_entities.get(rec["when"]["rule"]),
                        template_fields(rec["text"]), rule=rec["when"]["rule"])
        if "role" in rec["when"]:
            info.role_entities.add(info.entity or "line")
        items.append(info)
    reports = data.get("reports") or {}
    for table in reports.get("tables") or []:
        info = ItemInfo("table", table["id"], table["entity"], set(table["columns"]) | ({table["sort"]} if "sort" in table else set()))
        if "role" in table:
            info.role_entities.add(table["entity"])
        info.role_entities |= role_entities(info.fields)
        items.append(info)
    for chart in reports.get("charts") or []:
        fields = {chart["metric"]} if "metric" in chart else set()
        if chart.get("group_by") not in (None, "role"):
            fields.add(chart["group_by"])
        info = ItemInfo("chart", chart["id"], chart["entity"], fields)
        if "role" in chart or chart.get("group_by") == "role":
            info.role_entities.add(chart["entity"])
        info.role_entities |= role_entities(fields)
        items.append(info)
    return items


def role_fields(m: Methodology, entity: str) -> set[str]:
    defs = m.data.get("definitions") or {}
    out: set[str] = set()
    for role in (m.data.get("roles") or {}).get(entity) or []:
        out |= condition_fields(role["select"], defs)
    return out


# ---------------------------------------------------------------------------
# classification

def _field_support(names: Iterable[str], probe: Probe) -> Support:
    support = Support()
    for name in sorted(names):
        spec = fieldmod.lookup(name)
        if spec is None:
            hint = fieldmod.suggest(name)
            support.merge(UNSUPPORTED, f"unknown field '{name}'" + (f" (did you mean '{hint}'?)" if hint else ""))
            continue
        support.needs.update(p for p in (*spec.sources, *spec.requires) if not p.startswith("("))
        missing = probe(spec)
        if missing:
            support.merge(SKIPPED, f"missing data: {missing}")
    return support


@dataclass
class Classification:
    items: dict[tuple[str, str], Support]
    roles: dict[str, Support]

    def of(self, kind: str, ident: str) -> Support:
        return self.items[(kind, ident)]


def classify(m: Methodology, probe: Probe) -> Classification:
    roles = {entity: _field_support(role_fields(m, entity), probe) for entity in (m.data.get("roles") or {})}
    classification = Classification({}, roles)
    for info in items_of(m):
        support = _field_support(info.fields, probe)
        for entity in info.role_entities:
            role_support = roles.get(entity)
            if role_support is not None and role_support.status != OK:
                support.merge(role_support.status, f"role classification for {entity} is unavailable: {role_support.reason}")
            if role_support is not None:
                support.needs |= role_support.needs
        if info.kind == "recommendation":
            trigger = classification.items.get(("rule", info.rule or ""))
            if trigger is not None and trigger.status != OK:
                support.merge(SKIPPED if trigger.status == SKIPPED else UNSUPPORTED,
                              f"trigger rule '{info.rule}': {trigger.reason}")
        classification.items[(info.kind, info.id)] = support
    return classification


def static_probe(spec: fieldmod.FieldSpec) -> str | None:
    """Availability without a snapshot: only what this release's collector never emits."""
    if not spec.collected:
        return _missing_text(spec.requires[0])
    return None


def _missing_text(path: str) -> str:
    human = HUMAN_PATHS.get(path)
    return f"{human} ({path})" if human else path


def snapshot_probe(snapshots: list[Any]) -> Probe:
    """Skip fields whose source path is absent from every probed snapshot (empty sections are inconclusive)."""
    cache: dict[str, bool] = {}

    def absent(path: str) -> bool:
        if path not in cache:
            results = [fieldmod.probe_path(s, path) for s in snapshots]
            cache[path] = bool(results) and not any(r is True for r in results) and any(r is False for r in results)
        return cache[path]

    def probe(spec: fieldmod.FieldSpec) -> str | None:
        for path in (*spec.requires, *spec.sources):
            if not path.startswith("(") and absent(path):
                return _missing_text(path)
        return None

    return probe
