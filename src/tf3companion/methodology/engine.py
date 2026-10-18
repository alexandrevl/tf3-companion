"""Evaluate a methodology over one snapshot: roles, rules, aggregates, recommendations, ladders, tables, charts."""

from __future__ import annotations

import statistics
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

from .. import analysis
from ..snapshot import Snapshot
from . import fields as fieldmod
from .conditions import evaluate as eval_condition
from .conditions import first_true
from .model import ROLE_ENTITIES, UNCLASSIFIED, Methodology
from .support import OK, SKIPPED, UNSUPPORTED, Classification, classify, items_of, snapshot_probe, template_fields
from .templates import clean_text, render

MAX_HISTORY_POINTS = 24
TABLE_LIMIT = 50
SEVERITY_CATEGORY = {"line": "lines", "stop": "lines", "town": "lines", "vehicle": "vehicles",
                     "industry": "industries", "stock": "industries"}
DEFAULT_SUGGESTION = ("Review the evidence in the methodology verdicts report and decide in the game; "
                      "the rule's rationale is shown there as untrusted methodology text.")


# ---------------------------------------------------------------------------
# result objects

@dataclass
class Hit:
    rule: str
    marker: str
    message: str
    entity: dict[str, Any] | None
    role: str | None
    evidence: dict[str, Any]
    group: dict[str, Any] | None = None
    record: Any = field(default=None, repr=False, compare=False)

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if k != "record"}


@dataclass
class RuleResult:
    id: str
    label: str | None
    description: str | None
    rationale: str | None
    entity: str
    role: str | None
    kind: str                      # rule | aggregate
    status: str                    # ok | skipped | unsupported
    reason: str | None
    needs: list[str]
    evaluated: int = 0
    not_evaluable: int = 0
    excluded_members: int = 0
    hits: list[Hit] = field(default_factory=list)
    marker_counts: dict[str, int] = field(default_factory=dict)
    groups: list[dict[str, Any]] = field(default_factory=list)   # aggregate rows (all evaluated groups)

    def to_dict(self) -> dict[str, Any]:
        out = {k: v for k, v in asdict(self).items() if k != "hits"}
        out["hits"] = [h.to_dict() for h in self.hits]
        return out


@dataclass
class RoleSummary:
    entity: str
    status: str
    reason: str | None
    roles: list[dict[str, Any]]
    classified: int = 0
    unclassified: int = 0
    unclassified_unknown: int = 0


@dataclass
class AdviceResult:
    id: str
    kind: str                      # recommendation | ladder
    status: str
    reason: str | None
    priority: int | None = None
    items: list[dict[str, Any]] = field(default_factory=list)
    evaluated: int = 0
    not_evaluable: int = 0


@dataclass
class TableResult:
    id: str
    label: str | None
    entity: str
    status: str
    reason: str | None
    columns: list[str] = field(default_factory=list)
    rows: list[list[Any]] = field(default_factory=list)
    total: int = 0


@dataclass
class ChartResult:
    id: str
    label: str | None
    type: str
    status: str
    reason: str | None
    categories: list[str] = field(default_factory=list)
    series: list[tuple[str, list[float | None]]] = field(default_factory=list)


@dataclass
class Verdicts:
    methodology: dict[str, Any]
    origin: str
    parameters: dict[str, Any]
    overrides: dict[str, Any]
    snapshot: dict[str, Any]
    roles: dict[str, RoleSummary]
    rules: list[RuleResult]
    recommendations: list[AdviceResult]
    ladders: list[AdviceResult]
    tables: list[TableResult]
    charts: list[ChartResult]
    disabled_findings: list[dict[str, Any]] = field(default_factory=list)
    classification: Classification | None = field(default=None, repr=False, compare=False)
    role_index: dict[str, dict[Any, str]] = field(default_factory=dict, repr=False, compare=False)
    selection: dict[str, Any] = field(default_factory=dict)
    time_basis: dict[str, Any] = field(default_factory=dict)

    @property
    def skipped(self) -> list[dict[str, Any]]:
        return self._by_status(SKIPPED)

    @property
    def unsupported(self) -> list[dict[str, Any]]:
        return self._by_status(UNSUPPORTED)

    def _by_status(self, status: str) -> list[dict[str, Any]]:
        out = []
        for kind, items in (("rule", self.rules), ("ladder", self.ladders), ("recommendation", self.recommendations),
                            ("table", self.tables), ("chart", self.charts)):
            out += [{"kind": kind, "id": i.id, "reason": i.reason} for i in items if i.status == status]
        for summary in self.roles.values():
            if summary.status == status:
                out.append({"kind": "roles", "id": summary.entity, "reason": summary.reason})
        return out

    @property
    def not_evaluable(self) -> list[dict[str, Any]]:
        out = [{"kind": "rule", "id": r.id, "entities": r.not_evaluable, "excludedMembers": r.excluded_members}
               for r in self.rules if r.not_evaluable or r.excluded_members]
        out += [{"kind": "ladder", "id": a.id, "entities": a.not_evaluable} for a in self.ladders if a.not_evaluable]
        out += [{"kind": "roles", "id": s.entity, "entities": s.unclassified_unknown}
                for s in self.roles.values() if s.unclassified_unknown]
        return out

    def counts(self) -> dict[str, int]:
        return {"skipped": len(self.skipped), "unsupported": len(self.unsupported),
                "notEvaluable": sum(i.get("entities", 0) for i in self.not_evaluable)}

    def to_dict(self) -> dict[str, Any]:
        return {
            "methodology": self.methodology, "origin": self.origin, "parameters": self.parameters,
            "parameterOverrides": self.overrides, "snapshot": self.snapshot,
            "selection": self.selection, "timeBasis": self.time_basis,
            "roles": {k: asdict(v) for k, v in self.roles.items()},
            "rules": [r.to_dict() for r in self.rules],
            "recommendations": [asdict(a) for a in self.recommendations],
            "ladders": [asdict(a) for a in self.ladders],
            "tables": [asdict(t) for t in self.tables], "charts": [asdict(c) for c in self.charts],
            "skipped": self.skipped, "unsupported": self.unsupported, "notEvaluable": self.not_evaluable,
            "disabledFindings": self.disabled_findings,
        }


# ---------------------------------------------------------------------------
# scopes

class EntityScope:
    def __init__(self, record: fieldmod.Record, params: dict[str, Any], definitions: dict[str, Any]) -> None:
        self.record, self.params, self.definitions = record, params, definitions

    def field(self, name: str) -> Any:
        return self.record.get(name)

    def measure(self, name: str) -> Any:  # pragma: no cover - rejected by the validator
        raise KeyError(name)

    def members(self) -> Iterable[Any]:  # pragma: no cover - rejected by the validator
        return ()


class GroupScope:
    def __init__(self, measures: dict[str, Any], members: list[fieldmod.Record], params: dict[str, Any],
                 definitions: dict[str, Any]) -> None:
        self._measures, self._members, self.params, self.definitions = measures, members, params, definitions

    def field(self, name: str) -> Any:  # pragma: no cover - rejected by the validator
        raise KeyError(name)

    def measure(self, name: str) -> Any:
        return self._measures.get(name)

    def members(self) -> Iterable[EntityScope]:
        return (EntityScope(r, self.params, self.definitions) for r in self._members)


# ---------------------------------------------------------------------------
# parameters

def thresholds_for(m: Methodology | None) -> analysis.Thresholds:
    """Engine thresholds: defaults plus the methodology's `engine.thresholds`."""
    if m is None:
        return analysis.Thresholds()
    return analysis.Thresholds(**((m.data.get("engine") or {}).get("thresholds") or {}))


# ---------------------------------------------------------------------------
# the run

class _Run:
    def __init__(self, m: Methodology, snap: Snapshot, params: dict[str, Any], classification: Classification,
                 facts: fieldmod.Facts) -> None:
        self.m, self.snap, self.params, self.cls, self.facts = m, snap, params, classification, facts
        self.defs = m.data.get("definitions") or {}
        self.markers = m.data.get("markers") or {}
        self.items = {(i.kind, i.id): i for i in items_of(m)}
        self._records: dict[str, list[fieldmod.Record]] = {}
        self.roles: dict[str, RoleSummary] = {}

    def records(self, entity: str) -> list[fieldmod.Record]:
        if entity not in self._records:
            self._records[entity] = self.facts.records(entity)
        return self._records[entity]

    # ---- roles -------------------------------------------------------------------
    def assign_roles(self) -> None:
        declared = self.m.data.get("roles") or {}
        for entity in ROLE_ENTITIES:
            if entity not in declared:
                continue
            roles = declared[entity]
            support = self.cls.roles[entity]
            summary = RoleSummary(entity, support.status, support.reason,
                                  [{"id": r["id"], "label": r.get("label"), "count": 0} for r in roles])
            self.roles[entity] = summary
            records = self.records(entity)
            if support.status != OK:
                summary.unclassified = len(records)
                continue
            counts = _assign(roles, records, self.params, self.defs, summary)
            for row in summary.roles:
                row["count"] = counts.get(row["id"], 0)
            if entity == "line":
                self.facts.line_roles = {r.raw["id"]: r.role or UNCLASSIFIED for r in records}

    # ---- templates -----------------------------------------------------------------
    def lookup_for(self, record: fieldmod.Record | None, group: dict[str, Any] | None = None,
                   measures: dict[str, Any] | None = None, band: dict[str, Any] | None = None):
        def lookup(name: str) -> Any:
            if name == "group":
                return group["label"] if group else None
            if name.startswith("param."):
                return self.params.get(name[6:])
            if name == "band.mode":
                return None if band is None else band.get("mode")
            if name == "band.max_km":
                return None if band is None else band.get("max_km")
            if "." not in name:
                return (measures or {}).get(name)
            return None if record is None else record.get(name)
        return lookup

    def marker_label(self, marker: str) -> str:
        return clean_text((self.markers.get(marker) or {}).get("label") or marker, 200)

    # ---- entity rules -------------------------------------------------------------------
    def run_rule(self, rule: dict[str, Any]) -> RuleResult:
        support = self.cls.of("rule", rule["id"])
        aggregate = "aggregate" in rule
        result = RuleResult(
            rule["id"], rule.get("label"), rule.get("description"), rule.get("rationale"), rule["entity"],
            rule.get("role"), "aggregate" if aggregate else "rule", support.status, support.reason, sorted(support.needs))
        if support.status != OK:
            return result
        members = [r for r in self.records(rule["entity"]) if "role" not in rule or r.role == rule["role"]]
        if aggregate:
            self._run_aggregate(rule, members, result)
        else:
            self._run_entity_rule(rule, members, result)
        result.marker_counts = dict(Counter(h.marker for h in result.hits))
        return result

    def _evidence(self, rule_id: str, record: fieldmod.Record) -> dict[str, Any]:
        names = sorted(self.items[("rule", rule_id)].fields)[:12]
        return {name: record.get(name) for name in names}

    def _run_entity_rule(self, rule: dict[str, Any], members: list[fieldmod.Record], result: RuleResult) -> None:
        outcomes, default = rule["outcomes"], rule.get("default")
        for record in members:
            result.evaluated += 1
            scope = EntityScope(record, self.params, self.defs)
            index, unknown = first_true(outcomes, scope)
            if unknown:
                result.not_evaluable += 1
                continue
            outcome = outcomes[index] if index is not None else default
            if outcome is None:
                continue
            marker = outcome["marker"]
            message = outcome.get("message")
            text = render(message, self.lookup_for(record)) if message else \
                f"{clean_text(record.raw.get('name') or record.entity, 200)}: {self.marker_label(marker)}"
            result.hits.append(Hit(rule["id"], marker, text, record.ident, record.role,
                                   self._evidence(rule["id"], record), None, record))

    # ---- aggregate rules -------------------------------------------------------------------
    def _run_aggregate(self, rule: dict[str, Any], members: list[fieldmod.Record], result: RuleResult) -> None:
        agg = rule["aggregate"]
        group_by, measures = agg["group_by"], agg["measures"]
        if group_by == "town":
            label_kind = "town"
        else:
            spec = fieldmod.lookup(group_by)
            label_kind = spec.label_kind if spec else None
        order = list(measures)
        groups: dict[Any, dict[str, Any]] = {}
        excluded: set[int] = set()

        def group(key: Any) -> dict[str, Any]:
            if key not in groups:
                groups[key] = {"members": [], "acc": {name: {"n": 0, "total": 0, "missing": 0, "values": set(),
                                                                "seen": set()} for name in order}}
            return groups[key]

        for index, record in enumerate(members):
            scope = EntityScope(record, self.params, self.defs)
            keys_of_member: set[Any] = set()
            for name in order:
                m = measures[name]
                if m["agg"] == "ratio":
                    continue
                keys = _as_list(record.get(m.get("via", group_by)))
                if not keys:
                    excluded.add(index)
                    continue
                keys_of_member.update(keys)
                if "where" in m:
                    passed = eval_condition(m["where"], scope)
                    if passed is None:
                        excluded.add(index)
                        continue
                    if not passed:
                        continue
                for key in keys:
                    if not self._contribute(group(key)["acc"][name], m, record):
                        excluded.add(index)
            for key in keys_of_member:
                group(key)["members"].append(record)
        result.excluded_members = len(excluded)

        having = agg.get("having")
        outcomes, default = agg["outcomes"], agg.get("default")
        for key in sorted(groups, key=lambda k: (self.facts.label(label_kind, k).casefold(), str(k))):
            info = groups[key]
            values = _measure_values(measures, order, info["acc"])
            gscope = GroupScope(values, info["members"], self.params, self.defs)
            if having is not None and eval_condition(having, gscope) is not True:
                continue
            label = clean_text(self.facts.label(label_kind, key), 200)
            result.evaluated += 1
            index, unknown = first_true(outcomes, gscope)
            row: dict[str, Any] = {"key": key, "group": label, "measures": values, "marker": None, "message": None}
            if unknown:
                result.not_evaluable += 1
                result.groups.append(row)
                continue
            outcome = outcomes[index] if index is not None else default
            if outcome is not None:
                marker = outcome["marker"]
                group_info = {"key": key, "label": label}
                message = outcome.get("message")
                text = render(message, self.lookup_for(None, group_info, values)) if message else \
                    f"{label}: {self.marker_label(marker)}"
                row.update(marker=marker, message=text)
                result.hits.append(Hit(rule["id"], marker, text, None, None, dict(values), group_info, None))
            result.groups.append(row)

    @staticmethod
    def _contribute(acc: dict[str, Any], measure: dict[str, Any], record: fieldmod.Record) -> bool:
        """Add one member to an accumulator; False when a needed value was missing."""
        kind = measure["agg"]
        if "distinct_by" in measure:
            marker = record.get(measure["distinct_by"])
            if marker is None:
                acc["missing"] += 1
                return False
            if marker in acc["seen"]:
                return True
            acc["seen"].add(marker)
        if kind == "count":
            acc["n"] += 1
            return True
        value = record.get(measure["value"])
        if value is None:
            acc["missing"] += 1
            return False
        acc["n"] += 1
        if kind == "sum":
            acc["total"] += value
        elif kind == "distinct_count":
            acc["values"].update(value if isinstance(value, list) else [value])
        else:  # min / max
            acc["values"].add(value)
        return True

    # ---- recommendations and ladders ----------------------------------------------------------
    def run_recommendation(self, rec: dict[str, Any], rules: dict[str, RuleResult]) -> AdviceResult:
        support = self.cls.of("recommendation", rec["id"])
        result = AdviceResult(rec["id"], "recommendation", support.status, support.reason, rec["priority"])
        if support.status != OK:
            return result
        trigger = rules[rec["when"]["rule"]]
        for hit in trigger.hits:
            if hit.marker != rec["when"]["marker"] or ("role" in rec["when"] and hit.role != rec["when"]["role"]):
                continue
            measures = hit.evidence if hit.group is not None else None
            lookup = self.lookup_for(hit.record, hit.group, measures)
            values = dict(hit.evidence)
            if hit.record is not None:
                values.update({name: hit.record.get(name) for name in sorted(template_fields(rec["text"]))})
            result.items.append({
                "text": render(rec["text"], lookup),
                "evidence": {"rule": hit.rule, "marker": hit.marker, "entity": hit.entity or hit.group,
                             "values": values},
            })
        result.evaluated = len(result.items)
        return result

    def run_ladder(self, ladder: dict[str, Any]) -> AdviceResult:
        support = self.cls.of("ladder", ladder["id"])
        result = AdviceResult(ladder["id"], "ladder", support.status, support.reason, 3)
        if support.status != OK:
            return result
        bands = ladder["bands"]
        for record in self.records("line"):
            if "role" in ladder and record.role != ladder["role"]:
                continue
            result.evaluated += 1
            distance, carrier = record.get(ladder["metric"]), record.get("line.carrier")
            if distance is None or carrier is None:
                result.not_evaluable += 1
                continue
            lower = 0.0
            band = bands[-1]
            for candidate in bands:
                if "max_km" not in candidate or distance < candidate["max_km"]:
                    band = candidate
                    break
                lower = candidate["max_km"]
            if band["mode"] == carrier:
                continue
            info = {"mode": band["mode"], "max_km": band.get("max_km")}
            result.items.append({
                "text": render(ladder["text"], self.lookup_for(record, band=info)),
                "evidence": {"ladder": ladder["id"], "entity": record.ident, "distanceKm": round(distance, 3),
                             "band": {"fromKm": lower, "toKm": band.get("max_km"), "mode": band["mode"]},
                             "carrier": carrier},
            })
        return result

    # ---- tables and charts ----------------------------------------------------------------
    def run_table(self, table: dict[str, Any]) -> TableResult:
        support = self.cls.of("table", table["id"])
        result = TableResult(table["id"], table.get("label"), table["entity"], support.status, support.reason,
                             list(table["columns"]))
        if support.status != OK:
            return result
        rows = [r for r in self.records(table["entity"]) if "role" not in table or r.role == table["role"]]
        if "sort" in table:
            present = [r for r in rows if r.get(table["sort"]) is not None]
            missing = [r for r in rows if r.get(table["sort"]) is None]
            rows = sorted(present, key=lambda r: r.get(table["sort"]), reverse=bool(table.get("descending"))) + missing
        result.total = len(rows)
        result.rows = [[r.get(c) for c in table["columns"]] for r in rows[: table.get("limit", TABLE_LIMIT)]]
        return result

    def run_chart(self, chart: dict[str, Any], history: list[Snapshot]) -> ChartResult:
        support = self.cls.of("chart", chart["id"])
        result = ChartResult(chart["id"], chart.get("label"), chart["type"], support.status, support.reason)
        if support.status != OK:
            return result
        if chart["type"] == "history_line":
            return self._history_chart(chart, history, result)
        groups = _chart_groups(chart, self.records(chart["entity"]))
        categories = sorted(groups, key=lambda k: str(k))
        result.categories = [str(c) for c in categories]
        result.series = [(chart.get("label") or chart["id"], [_aggregate_values(chart, groups[c]) for c in categories])]
        return result

    def _history_chart(self, chart: dict[str, Any], history: list[Snapshot], result: ChartResult) -> ChartResult:
        snaps = history[-MAX_HISTORY_POINTS:] or [self.snap]
        per_snapshot: list[dict[Any, float | None]] = []
        for snap in snaps:
            clock = self.facts.clock.bounded(snap.game_time) if self.facts.clock else None
            facts = fieldmod.Facts(snap, self.facts.name_patterns, clock=clock)
            run = _Run(self.m, snap, self.params, self.cls, facts)
            if chart.get("group_by") == "role" or "role" in chart:
                run.assign_roles()
            records = [r for r in run.records(chart["entity"]) if "role" not in chart or r.role == chart["role"]]
            groups = _chart_groups(chart, records) if chart.get("group_by") else {"all": records}
            per_snapshot.append({k: _aggregate_values(chart, v) for k, v in groups.items()})
        names = sorted({k for point in per_snapshot for k in point}, key=str)
        result.categories = [s.date_label for s in snaps]
        result.series = [(str(n), [point.get(n) for point in per_snapshot]) for n in names]
        return result


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return list(value) if isinstance(value, list) else [value]


def _measure_values(measures: dict[str, Any], order: list[str], acc: dict[str, dict[str, Any]]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for name in order:
        m = measures[name]
        kind, a = m["agg"], acc[name]
        if kind == "ratio":
            num = values.get(m["numerator"]["measure"])
            den = values.get(m["denominator"]["measure"])
            if num is not None and m["numerator"].get("negate"):
                num = -num
            if den is not None and m["denominator"].get("negate"):
                den = -den
            values[name] = None if num is None or den is None or den <= 0 else num / den
        elif kind == "count":
            values[name] = None if a["n"] == 0 and a["missing"] else a["n"]
        elif kind == "sum":
            values[name] = None if a["n"] == 0 and a["missing"] else a["total"]
        elif kind == "distinct_count":
            values[name] = len(a["values"]) if a["values"] else None
        elif kind == "min":
            values[name] = min(a["values"]) if a["values"] else None
        else:
            values[name] = max(a["values"]) if a["values"] else None
    return values


def _assign(roles: list[dict[str, Any]], records: list[fieldmod.Record], params: dict[str, Any],
            defs: dict[str, Any], summary: RoleSummary | None) -> Counter:
    """First true selector wins; an unknown selector before it makes the entity unclassified."""
    counts: Counter = Counter()
    for record in records:
        record.role = None
        scope = EntityScope(record, params, defs)
        blocked = False
        for role in roles:
            value = eval_condition(role["select"], scope)
            if value is True:
                if not blocked:
                    record.role = role["id"]
                    counts[role["id"]] += 1
                break
            if value is None:
                blocked = True
        if record.role is None and summary is not None:
            summary.unclassified += 1
            if blocked:
                summary.unclassified_unknown += 1
        elif summary is not None:
            summary.classified += 1
    return counts


def _chart_groups(chart: dict[str, Any], records: list[fieldmod.Record]) -> dict[Any, list[fieldmod.Record]]:
    group_by = chart.get("group_by")
    groups: dict[Any, list[fieldmod.Record]] = {}
    for record in records:
        if "role" in chart and record.role != chart["role"]:
            continue
        key = (record.role or UNCLASSIFIED) if group_by == "role" else record.get(group_by) if group_by else "all"
        if key is not None:
            groups.setdefault(key, []).append(record)
    return groups


def _aggregate_values(chart: dict[str, Any], records: list[fieldmod.Record]) -> float | None:
    agg = chart["agg"]
    if agg == "count":
        return float(len(records))
    values = [v for r in records if (v := r.get(chart["metric"])) is not None]
    if not values:
        return None
    return float({"sum": sum, "mean": statistics.fmean, "min": min, "max": max}[agg](values))


# ---------------------------------------------------------------------------
# entry point

def _role_index(run: _Run) -> dict[str, dict[Any, str]]:
    return {entity: {r.raw.get("id"): r.role or UNCLASSIFIED for r in run.records(entity)} for entity in run.roles}


def evaluate(m: Methodology, snap: Snapshot, *, overrides: dict[str, Any] | None = None,
             probe_snapshots: list[Snapshot] | None = None, history: list[Snapshot] | None = None,
             origin: str = "packaged-default", clock: Any = None) -> Verdicts:
    from .prepare import prepare
    m = prepare(m, overrides)
    return _evaluate_prepared(m, snap, overrides=overrides, probe_snapshots=probe_snapshots,
                              history=history, origin=origin, clock=clock)


def _evaluate_prepared(m: Methodology, snap: Snapshot, *, overrides=None, probe_snapshots=None,
                       history=None, origin="packaged-default", clock=None) -> Verdicts:
    """Private handoff from the operation's gate; never reads a mutable source file."""
    params = m.parameters
    patterns = tuple((p["id"], p["pattern"]) for p in ((m.data.get("name_patterns") or {}).get("line") or []))
    classification = classify(m, snapshot_probe(probe_snapshots or [snap]))
    run = _Run(m, snap, params, classification, fieldmod.Facts(snap, patterns, clock=clock))
    run.assign_roles()
    rules = [run.run_rule(rule) for rule in m.data.get("rules") or []]
    by_id = {r.id: r for r in rules}
    reports = m.data.get("reports") or {}
    return Verdicts(
        methodology=m.provenance(), origin=origin, parameters=params, overrides=dict(m.effective_overrides),
        selection=dict(m.selection), time_basis=clock.time_basis if clock else {},
        snapshot={"date": snap.date_label, "gameTime": snap.game_time},
        roles=run.roles, rules=rules,
        recommendations=[run.run_recommendation(r, by_id) for r in m.data.get("recommendations") or []],
        ladders=[run.run_ladder(l) for l in m.data.get("ladders") or []],
        tables=[run.run_table(t) for t in reports.get("tables") or []],
        charts=[run.run_chart(c, history or [snap]) for c in reports.get("charts") or []],
        classification=classification, role_index=_role_index(run),
    )


# ---------------------------------------------------------------------------
# findings

def rule_findings(m: Methodology, verdicts: Verdicts) -> list[analysis.Finding]:
    """Findings produced by methodology rule outcomes whose marker maps to a severity."""
    markers = m.data.get("markers") or {}
    advice: dict[tuple[str, str], str] = {}
    for rec, result in zip(m.data.get("recommendations") or [], verdicts.recommendations):
        if result.status == OK and result.items:
            advice.setdefault((rec["when"]["rule"], rec["when"]["marker"]), result.items[0]["text"])
    out = []
    for rule, result in zip(m.data.get("rules") or [], verdicts.rules):
        for hit in result.hits:
            severity = (markers.get(hit.marker) or {}).get("finding")
            if severity is None:
                continue
            name = clean_text((hit.entity or {}).get("name") or (hit.group or {}).get("label") or rule["entity"], 200)
            label = clean_text(rule.get("label") or rule["id"], 200)
            entity = hit.entity or {"type": rule["entity"], "id": None, "name": name}
            out.append(analysis.Finding(
                f"rule:{rule['id']}", severity, SEVERITY_CATEGORY[rule["entity"]],
                f"{name}: {label} ({clean_text((markers.get(hit.marker) or {}).get('label') or hit.marker, 200)})",
                hit.message, DEFAULT_SUGGESTION, entity,
                {"rule": rule["id"], "marker": hit.marker, "role": hit.role, "values": hit.evidence},
                m.identity, m.short_hash, "methodology"))
    return out


def apply_finding_overrides(m: Methodology, verdicts: Verdicts, items: list[analysis.Finding]) -> list[analysis.Finding]:
    """Switch off or re-grade engine findings by code, optionally only for one role (first match wins)."""
    overrides = (m.data.get("engine") or {}).get("findings") or []
    if not overrides:
        return items
    out: list[analysis.Finding] = []
    disabled: dict[tuple[str, str | None], int] = {}
    for finding in items:
        chosen = None
        for override in overrides:
            if override["code"] != finding.code:
                continue
            if "role" in override:
                entity = analysis.FINDING_CODES[finding.code]
                role = verdicts.role_index.get(entity, {}).get((finding.entity or {}).get("id"), UNCLASSIFIED)
                if role != override["role"]:
                    continue
            chosen = override
            break
        if chosen is None:
            out.append(finding)
        elif chosen["action"] == "off":
            key = (finding.code, chosen.get("role"))
            disabled[key] = disabled.get(key, 0) + 1
        else:
            finding.severity = chosen["severity"]
            out.append(finding)
    verdicts.disabled_findings = [{"code": code, "role": role, "suppressed": count}
                                  for (code, role), count in sorted(disabled.items(), key=lambda kv: (kv[0][0], kv[0][1] or ""))]
    return out
