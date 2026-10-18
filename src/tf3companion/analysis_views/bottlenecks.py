"""Bottleneck view: per-sample observations tracked across the recent samples.

Per-sample detectors reuse `analysis` (findings, full_stocks, line_load, Thresholds). Every flagged
condition is tracked across the persistence window so persistent problems (flagged in the latest
sample and its recent streak) are separated from one-offs and from problems that have since cleared.

Honesty rules: samples are instants, not continuous telemetry; `load` is instantaneous; a source absent
from early samples is unknown (never counted as "no problem"); `profitYear` is a rolling window and is
only carried, never summed; `daysAtTerminal` has unverified semantics. Stock slopes are units per sample
and the samples-to-full figure is an explicitly conditional linear extrapolation.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field, replace
from typing import Any

from .. import analysis
from ..snapshot import Snapshot
from .bottlenecks_evidence import LOAD_LIMIT, BottlenecksEvidence
from .models import EvaluationContext, SampleRef, Unavailable, ViewCoverage

WINDOW = 36            # most recent merged samples used for persistence
CHART_POINTS = 24      # at most this many health points once history exceeds the window
RISE_MIN_POINTS = 3    # stock-rise needs at least this many recent samples ...
RISE_MAX_POINTS = 6    # ... and uses at most this many
TERMINAL_DAYS = 5      # daysAtTerminal level counted for the discontinuity screen
TERMINAL_JUMP = 10     # a jump between zero and at least this many such vehicles is a discontinuity

SEV_RANK = {"high": 0, "medium": 1, "low": 2}

# families whose single instant reading is normal noise; only kept when they recur
NOISY = {"line_load_high", "line_load_low", "station_pileup", "long_terminal_wait"}

# chart/trend series: stable key -> finding codes counted in each sample
TREND_SERIES = {
    "no_path": {"vehicle_no_path"},
    "user_stopped": {"vehicle_user_stopped"},
    "line_issues": {"line_config_issue", "line_orphan", "line_no_vehicles", "line_no_stops"},
    "idle_depot": {"vehicle_idle_depot"},
    "load_high": {"line_load_high"},
    "load_low": {"line_load_low"},
    "pileup": {"station_pileup"},
    "long_wait": {"long_terminal_wait"},
    "stock_output_full": {"stock_output_full"},
    "warehouse_full": {"warehouse_full"},
}

# collector-error family keyword -> affected-conclusion code (the report words the effect)
AFFECTS = ("depot", "stock", "line", "vehicle", "industr", "station", "town")


# ---------------------------------------------------------------------------
# typed result records
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Criterion:
    """An engine-owned heuristic or safeguard exposed with its value; not methodology policy."""

    name: str
    value: float
    unit: str
    note: str


@dataclass(frozen=True)
class BottleneckItem:
    code: str
    entity: tuple                          # scope of the flagged entity, e.g. ("line", 100)
    key: tuple                             # identity of this condition
    name: str
    observations: int                      # samples in which it was flagged
    eligible: int                          # samples in which the entity/data source existed (>= observations)
    streak: int                            # consecutive flagged samples ending at the latest
    in_latest: bool
    status: str                            # persistent | intermittent | new | resolved
    severity: str                          # high | medium | low
    first_tick: int
    last_tick: int
    first_label: str
    last_label: str
    evidence: dict[str, Any]               # latest flagged reading (numbers/strings/tuples)


@dataclass(frozen=True)
class BottleneckSummary:
    high: int                              # active (not resolved) by severity
    medium: int
    low: int
    persistent: int                        # all items by status
    intermittent: int
    new: int
    resolved: int


@dataclass(frozen=True)
class StockPoint:
    tick: int
    count: int
    capacity: int
    fill: float


@dataclass(frozen=True)
class StockRise:
    kind: str
    owner: Any
    stock_id: Any
    name: str
    cargo_names: tuple[str, ...]
    fill: float
    count_start: int                       # first of the points used
    count_latest: int
    capacity: int
    slope_per_sample: float                # units per sample, least squares over `points`
    samples_to_full: float                 # conditional linear extrapolation (the policy slope minimum is positive)
    points: tuple[StockPoint, ...]


@dataclass(frozen=True)
class UnservedStock:
    name: str
    cargo_names: tuple[str, ...]
    count: int
    capacity: int
    fill: float


@dataclass(frozen=True)
class StockSummary:
    samples_with_stocks: int               # window samples that carry measurable stocks
    first_with_stocks: SampleRef | None
    latest_has_stocks: bool
    unserved: tuple[UnservedStock, ...]    # near/full industry outputs with zero recorded annual shipments (latest)


@dataclass(frozen=True)
class OccupancyPattern:
    line: Any
    name: str
    pattern: str                           # "high" | "low"
    observations: int
    eligible: int
    status: str
    known_samples: int                     # window samples with a measurable occupancy
    mean: float | None                     # unweighted mean of instants, not a time average
    minimum: float | None
    maximum: float | None
    latest: float | None
    vehicles: int | None
    profit_year: Any


@dataclass(frozen=True)
class StationGroup:
    station_group: Any
    name: str
    observations: int
    eligible: int
    status: str
    waiting: int
    lines: int
    line_names: tuple[str, ...]


@dataclass(frozen=True)
class DepotGroup:
    depot: Any
    name: str | None                       # None when the name was not collected
    vehicles: int                          # vehicles inside in the latest sample
    without_line: int
    value_without_line: int | float | None  # None when any such vehicle has an unknown recorded value


@dataclass(frozen=True)
class HealthPoint:
    tick: int
    date_label: str
    stocks_known: bool
    counts: dict[str, int]                 # TREND_SERIES key -> flagged conditions in that sample


@dataclass(frozen=True)
class DataSourceCoverage:
    source: str                            # lines_vehicles | stocks | depots | vehicle_depot_id
    samples: int
    of: int
    first: SampleRef | None


@dataclass(frozen=True)
class ErrorFamily:
    family: str
    message: str
    samples: int                           # window samples with this error family
    of: int
    latest_occurrences: int
    affects: str | None                    # keyword from AFFECTS, None when unknown


@dataclass(frozen=True)
class TerminalReset:
    from_sample: SampleRef
    to_sample: SampleRef
    before: int                            # vehicles with daysAtTerminal >= TERMINAL_DAYS
    after: int


@dataclass(frozen=True)
class BottlenecksView:
    coverage: ViewCoverage
    samples: int                           # merged samples in the persistence window
    merged_available: int                  # merged samples read (window source)
    window_start: SampleRef
    window_end: SampleRef
    insufficient_history: bool             # fewer samples than the persistence streak
    rising_interval_empty: bool            # no fill interval is both rising-eligible and not full
    latest_errors: int
    summary: BottleneckSummary
    items: tuple[BottleneckItem, ...]      # severity, then observations, fill, name
    stocks: StockSummary
    stock_rises: tuple[StockRise, ...]
    occupancy: tuple[OccupancyPattern, ...]
    station_groups: tuple[StationGroup, ...]
    depot_groups: tuple[DepotGroup, ...]
    bucketed: bool                         # health points are quarter representatives
    health: tuple[HealthPoint, ...]
    data_sources: tuple[DataSourceCoverage, ...]
    error_families: tuple[ErrorFamily, ...]
    terminal_resets: tuple[TerminalReset, ...]
    criteria: tuple[Criterion, ...]


# ---------------------------------------------------------------------------
# per-sample observation (internal)
# ---------------------------------------------------------------------------

@dataclass
class _Obs:
    code: str
    scope: tuple
    key: tuple
    name: str
    ev: dict[str, Any] = field(default_factory=dict)


@dataclass
class _Sample:
    snap: Snapshot
    exists: set = field(default_factory=set)
    obs: dict[tuple, _Obs] = field(default_factory=dict)
    stock_rows: list[dict[str, Any]] = field(default_factory=list)

    def flag(self, ob: _Obs) -> None:
        self.obs[ob.key] = ob


def _vehicle_name(v: dict[str, Any]) -> str:
    return v.get("name") or f"Vehicle #{v.get('id')}"


def _line_name(line: dict[str, Any] | None, line_id: Any = None) -> str:
    if line and line.get("name"):
        return line["name"]
    return f"Line #{line_id if line_id is not None else (line or {}).get('id')}"


def _has_line(snap: Snapshot, v: dict[str, Any]) -> bool:
    return v.get("line") in snap.lines_by_id


def _known_sum(rows: list[dict[str, Any]], name: str) -> int | float | None:
    values = [r.get(name) for r in rows]
    return sum(values) if values and all(v is not None for v in values) else None


def _load(line: dict[str, Any]) -> float | None:
    capacities = line.get("capacity") or []
    if any(c.get("used") is None or c.get("capacity") is None for c in capacities):
        return None
    return analysis.line_load(line)


def _stop_name(line: dict[str, Any] | None, index: Any) -> str | None:
    stops = (line or {}).get("stops") or []
    return stops[index].get("name") if isinstance(index, int) and 0 <= index < len(stops) else None


def _observe(snap: Snapshot, known_depots: dict[Any, str], context: EvaluationContext) -> _Sample:
    policy = context.policies["bottlenecks"]
    sm = _Sample(snap)
    ex = sm.exists
    for line in snap.lines:
        ex.add(("line", line["id"]))
    for v in snap.vehicles:
        ex.add(("vehicle", v["id"]))
    for ind in snap.industries:
        ex.add(("industry", ind["id"]))

    # ---- reuse analysis findings (no_path, config issues, incomplete lines, closing industries)
    for f in analysis.findings(snap, t=context.thresholds):
        ent = f.entity or {}
        if f.code == "vehicle_no_path":
            sm.flag(_Obs(f.code, ("vehicle", ent["id"]), (f.code, ent["id"]), ent.get("name") or f"Vehicle #{ent['id']}",
                         {"line": f.evidence.get("lineName"), "state": f.evidence.get("state")}))
        elif f.code == "line_config_issue":
            issue = f.evidence.get("issue") or {}
            key = (f.code, ent["id"], issue.get("type"), issue.get("stopIndex"), issue.get("cargo"))
            sm.flag(_Obs(f.code, ("line", ent["id"]), key, _line_name(snap.lines_by_id.get(ent["id"]), ent["id"]),
                         {"type": issue.get("type"), "stopIndex": issue.get("stopIndex"),
                          "cargo": snap.cargo(issue.get("cargo")),
                          "stopName": _stop_name(snap.lines_by_id.get(ent["id"]), issue.get("stopIndex"))}))
        elif f.code in ("line_orphan", "line_no_vehicles", "line_no_stops"):
            sm.flag(_Obs(f.code, ("line", ent["id"]), (f.code, ent["id"]), _line_name(snap.lines_by_id.get(ent["id"]), ent["id"]),
                         {"stops": f.evidence.get("stops"), "vehicles": f.evidence.get("vehicles")}))
        elif f.code == "industry_closing":
            ind = snap.industries_by_id.get(ent["id"]) or {}
            served = any((o.get("shippedYear") or 0) > 0 for o in ind.get("outputs") or []) or \
                any((i.get("deliveredYear") or 0) > 0 for i in ind.get("inputs") or [])
            sm.flag(_Obs(f.code, ("industry", ent["id"]), (f.code, ent["id"]), ent.get("name") or f"Industry #{ent['id']}",
                         {"served": served}))
    for vid in snap.problems.get("noPathVehicles") or []:
        v = snap.vehicles_by_id.get(vid)
        if v and ("vehicle_no_path", vid) not in sm.obs:
            sm.flag(_Obs("vehicle_no_path", ("vehicle", vid), ("vehicle_no_path", vid), _vehicle_name(v),
                         {"line": (snap.lines_by_id.get(v.get("line")) or {}).get("name"), "state": v.get("state")}))

    # ---- vehicles: user stopped; idle in depot (grouped per depot)
    depot_names = {**known_depots, **{d["id"]: d.get("name") for d in snap.depots if d.get("name")}}
    for depot_id in set(depot_names) | {v.get("depot") for v in snap.vehicles if v.get("depot") is not None}:
        ex.add(("idledepot", depot_id))
    idle: dict[Any, list[dict[str, Any]]] = {}
    for v in snap.vehicles:
        if v.get("userStopped"):
            row = analysis.vehicle_row(snap, v)
            sm.flag(_Obs("vehicle_user_stopped", ("vehicle", v["id"]), ("vehicle_user_stopped", v["id"]),
                         _vehicle_name(v), {"line": row["lineName"], "state": v.get("state"), "value": v.get("value")}))
        if v.get("state") == "IN_DEPOT" and not _has_line(snap, v):
            idle.setdefault(v.get("depot"), []).append(v)
    for depot_id, vs in idle.items():
        label = depot_names.get(depot_id) or (f"Depot #{depot_id} (name not available)" if depot_id is not None else "Unknown depot")
        sm.flag(_Obs("vehicle_idle_depot", ("idledepot", depot_id), ("vehicle_idle_depot", depot_id), label,
                     {"count": len(vs), "days": max((v["daysInDepot"] for v in vs), default=None)
                      if all(v.get("daysInDepot") is not None for v in vs) else None,
                      "value": _known_sum(vs, "value"),
                      "examples": tuple(sorted(_vehicle_name(v) for v in vs)[:3]),
                      "carriers": tuple(sorted({v.get("carrier") for v in vs if v.get("carrier")}))}))

    # ---- long waits at terminals, per line (daysAtTerminal semantics unverified)
    for line in snap.lines:
        vehicles = snap.line_vehicles(line)
        waits = [v.get("daysAtTerminal") or 0 for v in vehicles]
        long = [w for w in waits if w >= policy.long_wait_days]
        if long:
            sm.flag(_Obs("long_terminal_wait", ("line", line["id"]), ("long_terminal_wait", line["id"]), _line_name(line),
                         {"count": len(long), "max": max(long), "vehicles": len(vehicles)}))

    # ---- line occupancy (instant readings)
    for line in snap.lines:
        load = _load(line)
        if load is None:
            continue
        ex.add(("lineload", line["id"]))
        n_veh = len(line.get("vehicles") or [])
        ev = {"load": load, "vehicles": n_veh, "profitYear": line.get("profitYear")}
        if load >= context.thresholds.overloaded_load:
            sm.flag(_Obs("line_load_high", ("lineload", line["id"]), ("line_load_high", line["id"]), _line_name(line), ev))
        elif load <= context.thresholds.underused_load and n_veh >= context.thresholds.underused_min_vehicles:
            sm.flag(_Obs("line_load_low", ("lineload", line["id"]), ("line_load_low", line["id"]), _line_name(line), ev))

    # ---- stations: vehicles piled up at the same stop
    group_name: dict[Any, str] = {s["id"]: s.get("name") for s in snap.stations}
    group_lines: dict[Any, set] = {}
    waiting: Counter = Counter()
    for line in snap.lines:
        for st in line.get("stops") or []:
            gid = st.get("stationGroup")
            if gid is None:
                continue
            ex.add(("station", gid))
            group_name.setdefault(gid, st.get("name"))
            group_lines.setdefault(gid, set()).add(line["id"])
    for v in snap.vehicles:
        line = snap.lines_by_id.get(v.get("line"))
        idx = v.get("stopIndex")
        if v.get("state") == "AT_TERMINAL" and line and isinstance(idx, int) and 0 <= idx < len(line.get("stops") or []):
            gid = line["stops"][idx].get("stationGroup")
            if gid is not None:
                waiting[gid] += 1
    for gid, n in waiting.items():
        if n >= policy.pileup_min:
            names = sorted(_line_name(snap.lines_by_id.get(i), i) for i in group_lines.get(gid, ()))
            sm.flag(_Obs("station_pileup", ("station", gid), ("station_pileup", gid), group_name.get(gid) or f"Station #{gid}",
                         {"waiting": n, "lines": len(names), "lineNames": tuple(names[:3])}))

    # ---- stocks (only present in newer snapshots)
    if snap.stocks:
        rows = analysis.full_stocks(snap, replace(context.thresholds, full_stock_ratio=0.0))
        for r in rows:
            if r.get("kind") == "industry":
                outputs = (snap.industries_by_id.get(r.get("owner")) or {}).get("outputs") or []
                matching = [o for o in outputs if o.get("cargo") in (r.get("cargos") or [])]
                if not any((o.get("shippedYear") or 0) > 0 for o in matching) and any(
                    o.get("shippedYear") is None for o in matching
                ):
                    r["served"] = None
        sm.stock_rows = rows
        warehouses: dict[Any, dict[str, Any]] = {}
        for r in rows:
            skey = ("stock", r.get("kind"), r.get("owner"), r.get("stockId"))
            ex.add(skey)
            full = r["fill"] >= context.thresholds.full_stock_ratio
            kind = r.get("kind")
            if kind == "industry" and r["served"] is True and full:
                ind = snap.industries_by_id.get(r["owner"]) or {}
                cargos = set(r.get("cargos") or [])
                outs = [o for o in ind.get("outputs") or [] if o.get("cargo") in cargos]
                produced, shipped = _known_sum(outs, "producedYear"), _known_sum(outs, "shippedYear")
                sm.flag(_Obs("stock_output_full", skey, ("stock_output_full", r.get("owner"), r.get("stockId")), r["name"],
                             {"cargo": ", ".join(r["cargoNames"]), "count": r["count"], "capacity": r["capacity"],
                              "fill": r["fill"], "produced": produced, "shipped": shipped,
                              "shippedRatio": shipped / produced if produced and shipped is not None else None}))
            elif kind == "station" and full:
                sm.flag(_Obs("station_stock_full", skey, ("station_stock_full", r.get("owner"), r.get("stockId")), r["name"],
                             {"cargo": ", ".join(r["cargoNames"]), "count": r["count"], "capacity": r["capacity"], "fill": r["fill"]}))
            elif kind == "warehouse":
                w = warehouses.setdefault(r.get("owner"), {"name": r["name"], "total": 0, "full": 0, "cargos": set()})
                w["total"] += 1
                if full:
                    w["full"] += 1
                    w["cargos"].update(c for c in r["cargoNames"] if c)
        counts = Counter(w["name"] for w in warehouses.values())
        for owner, w in warehouses.items():
            if counts[w["name"]] > 1:
                w["name"] = f"{w['name']} (warehouse #{owner})"
            ex.add(("warehouse", owner))
            if w["full"]:
                sm.flag(_Obs("warehouse_full", ("warehouse", owner), ("warehouse_full", owner), w["name"],
                             {"full": w["full"], "total": w["total"], "cargos": tuple(sorted(w["cargos"]))}))
    return sm


# ---------------------------------------------------------------------------
# persistence layer
# ---------------------------------------------------------------------------

def _status(in_latest: bool, n: int, eligible: int, streak: int, policy) -> str:
    if not in_latest:
        return "resolved"
    if eligible < policy.persistence_streak:
        return "new"
    if streak >= policy.persistence_streak:
        return "persistent"
    return "new" if n == 1 else "intermittent"


def _severity(code: str, status: str, ev: dict[str, Any], context: EvaluationContext) -> str:
    if code in ("vehicle_no_path", "line_config_issue"):
        return "high"
    if code == "stock_output_full":
        return "high" if status == "persistent" else "medium"
    if code == "industry_closing":
        return "high" if ev.get("served") else "low"
    if code == "vehicle_idle_depot":
        return "medium" if (ev.get("days") or 0) >= context.thresholds.idle_depot_days else "low"
    if code in ("vehicle_user_stopped", "line_orphan", "line_no_vehicles", "line_no_stops",
                "warehouse_full", "station_stock_full", "station_pileup"):
        return "medium"
    if code == "line_load_high":
        return "medium" if ev.get("vehicles", 0) >= 2 else "low"
    if code == "line_load_low":
        return "medium" if (ev.get("profitYear") or 0) < 0 else "low"
    return "low"


def _sort_key(item: BottleneckItem) -> tuple:
    return (SEV_RANK[item.severity], -item.observations, -(item.evidence.get("fill") or 0), item.name, str(item.key))


def _track(samples: list[_Sample], context: EvaluationContext) -> list[BottleneckItem]:
    policy = context.policies["bottlenecks"]
    last = len(samples) - 1
    keys: dict[tuple, list[int]] = {}
    for i, sm in enumerate(samples):
        for key in sm.obs:
            keys.setdefault(key, []).append(i)
    items: list[BottleneckItem] = []
    for key, idxs in keys.items():
        final = samples[idxs[-1]].obs[key]
        n = len(idxs)
        eligible = max(sum(1 for sm in samples if final.scope in sm.exists), n)
        streak = 0
        for i in range(last, -1, -1):
            if key in samples[i].obs:
                streak += 1
            else:
                break
        in_latest = idxs[-1] == last
        status = _status(in_latest, n, eligible, streak, policy)
        if final.code in NOISY and not (n >= policy.persistence_streak and n / eligible >= policy.noisy_min_share):
            continue
        first, latest = samples[idxs[0]].snap, samples[idxs[-1]].snap
        items.append(BottleneckItem(
            final.code, final.scope, key, final.name, n, eligible, streak, in_latest, status,
            _severity(final.code, status, final.ev, context), first.game_time, latest.game_time,
            first.date_label, latest.date_label, dict(final.ev)))
    return sorted(items, key=_sort_key)


# ---------------------------------------------------------------------------
# stocks, occupancy, groups
# ---------------------------------------------------------------------------

def _slope(values: list[float]) -> float:
    n = len(values)
    mean = sum(values) / n
    centre = (n - 1) / 2
    den = sum((i - centre) ** 2 for i in range(n))
    return sum((i - centre) * (v - mean) for i, v in enumerate(values)) / den if den else 0.0


def _stock_rises(samples: list[_Sample], context: EvaluationContext) -> list[StockRise]:
    policy = context.policies["bottlenecks"]
    latest = samples[-1]
    series: dict[tuple, list[tuple[int, int, int, int, float]]] = {}
    for i, sm in enumerate(samples):
        for r in sm.stock_rows:
            series.setdefault((r.get("kind"), r.get("owner"), r.get("stockId")), []).append(
                (i, sm.snap.game_time, r["count"], r["capacity"], r["fill"]))
    names = {(r.get("kind"), r.get("owner"), r.get("stockId")): r for r in latest.stock_rows}
    out: list[StockRise] = []
    for key, pts in series.items():
        if key not in names or pts[-1][0] != len(samples) - 1:
            continue
        recent = pts[-RISE_MAX_POINTS:]
        if len(recent) < RISE_MIN_POINTS:
            continue
        r = names[key]
        if r["kind"] == "industry" and r["served"] is not True:
            continue
        fill = recent[-1][4]
        if not policy.rising_stock_min_fill <= fill < context.thresholds.full_stock_ratio:
            continue
        slope = _slope([p[2] for p in recent])
        cap = recent[-1][3]
        if slope / cap < policy.rising_stock_min_slope:
            continue
        out.append(StockRise(
            r["kind"], r.get("owner"), r.get("stockId"), r["name"], tuple(c for c in r["cargoNames"] if c), fill,
            recent[0][2], recent[-1][2], cap, slope, (cap - recent[-1][2]) / slope,
            tuple(StockPoint(p[1], p[2], p[3], p[4]) for p in recent)))
    return sorted(out, key=lambda x: (x.samples_to_full, x.name, str(x.kind), str(x.owner), str(x.stock_id)))


def _occupancy(items: list[BottleneckItem], samples: list[_Sample]) -> list[OccupancyPattern]:
    out = []
    current_snap = samples[-1].snap
    for it in items:
        if it.code not in ("line_load_high", "line_load_low"):
            continue
        loads = []
        for sm in samples:
            line = sm.snap.lines_by_id.get(it.key[1])
            val = _load(line) if line else None
            if val is not None:
                loads.append(val)
        current = current_snap.lines_by_id.get(it.key[1])
        out.append(OccupancyPattern(
            it.key[1], it.name, "high" if it.code == "line_load_high" else "low", it.observations, it.eligible, it.status,
            len(loads), sum(loads) / len(loads) if loads else None, min(loads) if loads else None,
            max(loads) if loads else None, _load(current) if current else None,
            len(current.get("vehicles") or []) if current else None, current.get("profitYear") if current else None))
    return out


def _station_groups(items: list[BottleneckItem]) -> list[StationGroup]:
    return [StationGroup(it.key[1], it.name, it.observations, it.eligible, it.status, it.evidence["waiting"],
                         it.evidence["lines"], it.evidence["lineNames"])
            for it in items if it.code == "station_pileup"]


def _depot_groups(latest: Snapshot) -> list[DepotGroup]:
    inside = [v for v in latest.vehicles if v.get("state") == "IN_DEPOT"]
    names = {d["id"]: d.get("name") for d in latest.depots}
    out = []
    for depot_id in {v.get("depot") for v in inside}:
        vs = [v for v in inside if v.get("depot") == depot_id]
        unassigned = [v for v in vs if not _has_line(latest, v)]
        out.append(DepotGroup(depot_id, names.get(depot_id) or None, len(vs), len(unassigned),
                              _known_sum(unassigned, "value") if unassigned else 0))
    return sorted(out, key=lambda g: (-g.vehicles, g.name or "", str(g.depot)))


# ---------------------------------------------------------------------------
# trend and collector coverage
# ---------------------------------------------------------------------------

def _quarter_buckets(snaps: list[Snapshot]) -> list[Snapshot]:
    buckets: dict[Any, Snapshot] = {}
    for s in snaps:
        d = s.date
        buckets[(d["year"], (d["month"] - 1) // 3) if d else ("t", s.game_time)] = s
    return sorted(buckets.values(), key=lambda x: x.game_time)


def _health(chart: list[_Sample]) -> list[HealthPoint]:
    return [HealthPoint(sm.snap.game_time, sm.snap.date_label, bool(sm.stock_rows),
                        {key: sum(1 for ob in sm.obs.values() if ob.code in codes) for key, codes in TREND_SERIES.items()})
            for sm in chart]


def _error_family(text: str) -> tuple[str, str]:
    first = text.splitlines()[0] if text else ""
    family = re.sub(r"\[\d+\]", "[*]", first.split(": ", 1)[0])
    family = family[:80]
    match = re.search(r"\]:\d+: (.*)", text)
    tail = match.group(1).strip() if match else (first.split(": ", 1)[1] if ": " in first else first)
    return family, tail[:100]


def _data_sources(samples: list[_Sample]) -> list[DataSourceCoverage]:
    n = len(samples)

    def coverage(source: str, pred) -> DataSourceCoverage:
        idx = [i for i, s in enumerate(samples) if pred(s.snap)]
        first = samples[idx[0]].snap if idx else None
        return DataSourceCoverage(source, len(idx), n, SampleRef(first.game_time, first.date_label) if first else None)

    return [
        coverage("lines_vehicles", lambda s: bool(s.lines)),
        coverage("stocks", lambda s: bool(s.stocks)),
        coverage("depots", lambda s: bool(s.depots)),
        coverage("vehicle_depot_id", lambda s: any(v.get("depot") is not None for v in s.vehicles)),
    ]


def _error_families(samples: list[_Sample]) -> list[ErrorFamily]:
    n = len(samples)
    fam: dict[tuple, dict[str, Any]] = {}
    for i, sm in enumerate(samples):
        for e in sm.snap.errors:
            f = fam.setdefault(_error_family(e), {"samples": set(), "latest": set()})
            f["samples"].add(i)
            if i == n - 1:
                f["latest"].add(e)
    out = []
    for (family, tail), f in fam.items():
        lowered = family.lower()
        out.append(ErrorFamily(family, tail, len(f["samples"]), n, len(f["latest"]),
                               next((k for k in AFFECTS if k in lowered), None)))
    return sorted(out, key=lambda e: (-e.samples, e.family, e.message))


def _terminal_resets(samples: list[_Sample]) -> list[TerminalReset]:
    counts = [sum(1 for v in s.snap.vehicles if (v.get("daysAtTerminal") or 0) >= TERMINAL_DAYS) for s in samples]
    out = []
    for i in range(1, len(samples)):
        if max(counts[i - 1], counts[i]) >= TERMINAL_JUMP and min(counts[i - 1], counts[i]) == 0:
            a, b = samples[i - 1].snap, samples[i].snap
            out.append(TerminalReset(SampleRef(a.game_time, a.date_label), SampleRef(b.game_time, b.date_label),
                                     counts[i - 1], counts[i]))
    return out


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

def evaluate(evidence: BottlenecksEvidence, *, context: EvaluationContext) -> BottlenecksView:
    policy = context.policies["bottlenecks"]
    history = list(evidence.history)
    window = history[-WINDOW:]
    depots = dict(evidence.known_depots)
    samples = [_observe(s, depots, context) for s in window]
    items = _track(samples, context)
    latest = samples[-1]
    cur = latest.snap

    bucketed = len(history) > WINDOW
    if bucketed:
        by_time = {s.snap.game_time: s for s in samples}
        chart = [by_time.get(s.game_time) or _observe(s, depots, context)
                 for s in _quarter_buckets(history)[-CHART_POINTS:]]
    else:
        chart = samples
    health = _health(chart) if len(chart) >= 2 else []

    with_stocks = [i for i, s in enumerate(samples) if s.stock_rows]
    first_stock = samples[with_stocks[0]].snap if with_stocks else None
    unserved = tuple(
        UnservedStock(r["name"], tuple(r["cargoNames"]), r["count"], r["capacity"], r["fill"])
        for r in latest.stock_rows
        if r["kind"] == "industry" and r["served"] is False and r["fill"] >= context.thresholds.full_stock_ratio)
    stocks = StockSummary(len(with_stocks), SampleRef(first_stock.game_time, first_stock.date_label) if first_stock else None,
                          bool(latest.stock_rows), unserved)
    rises = _stock_rises(samples, context) if latest.stock_rows else []

    active = Counter(i.severity for i in items if i.status != "resolved")
    status = Counter(i.status for i in items)
    summary = BottleneckSummary(active["high"], active["medium"], active["low"], status["persistent"],
                                status["intermittent"], status["new"], status["resolved"])
    families = _error_families(samples)
    insufficient = len(samples) < policy.persistence_streak

    unavailable = []
    if insufficient:
        unavailable.append(Unavailable("insufficient-samples", f"{len(samples)} of {policy.persistence_streak}", "persistence"))
    if not latest.stock_rows:
        unavailable.append(Unavailable("latest-sample-without-stocks", None, "stocks"))
    if len(chart) < 2:
        unavailable.append(Unavailable("fewer-than-two-samples", None, "health-trend"))
    warnings = tuple(w for w, cond in (("history-beyond-read-limit", evidence.eligible > evidence.read),
                                       ("samples-merged", len(history) < evidence.read)) if cond)
    coverage = ViewCoverage(
        SampleRef(cur.game_time, cur.date_label), evidence.eligible, evidence.read, len(samples), evidence.hydrated,
        LOAD_LIMIT, tuple(SampleRef(s.game_time, s.date_label) for s in window),
        {"readLimit": LOAD_LIMIT, "persistenceWindow": WINDOW, "healthPoints": CHART_POINTS},
        max(evidence.eligible - len(samples), 0), warnings, tuple(sorted({f.family for f in families})), tuple(unavailable))

    criteria = (
        Criterion("persistence_window", WINDOW, "samples", "Most recent merged samples used for persistence."),
        Criterion("read_limit", LOAD_LIMIT, "snapshots", "Newest stored snapshots read at or before the endpoint."),
        Criterion("health_points", CHART_POINTS, "points", "Maximum quarter representatives in the health trend."),
        Criterion("merge_fraction", 1 / 48, "game years", "Samples closer than this are merged into the later one."),
        Criterion("rise_min_points", RISE_MIN_POINTS, "samples", "Fewest recent samples for a stock-rise slope."),
        Criterion("rise_max_points", RISE_MAX_POINTS, "samples", "Most recent samples used for a stock-rise slope."),
        Criterion("terminal_days", TERMINAL_DAYS, "days", "daysAtTerminal level counted by the discontinuity screen."),
        Criterion("terminal_jump", TERMINAL_JUMP, "vehicles", "Jump between zero and this many vehicles flags a discontinuity."),
    )
    return BottlenecksView(
        coverage, len(samples), len(history), SampleRef(window[0].game_time, window[0].date_label),
        SampleRef(cur.game_time, cur.date_label), insufficient,
        policy.rising_stock_min_fill >= context.thresholds.full_stock_ratio, len(cur.errors), summary, tuple(items),
        stocks, tuple(rises), tuple(_occupancy(items, samples)), tuple(_station_groups(items)),
        tuple(_depot_groups(cur)), bucketed, tuple(health), tuple(_data_sources(samples)), tuple(families),
        tuple(_terminal_resets(samples)), criteria)
