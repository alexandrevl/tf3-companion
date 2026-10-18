"""Network health / bottleneck report with a cross-snapshot persistence layer.

Per-sample detectors reuse `analysis` (findings, full_stocks, line_load, Thresholds). Every flagged
condition is tracked across the recent snapshots so that persistent problems (seen in most recent
samples) are separated from one-offs and from problems that have since cleared.

Honesty rules: samples are instants, not continuous telemetry; `load` is instantaneous; missing
values are unknown (a source absent from early samples is never counted as "no problem");
`profitYear` is a rolling window and is only shown, never summed; `daysAtTerminal` has unverified
semantics; entity names come from the game and are escaped by the renderers.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field, replace
from typing import Any

from . import analysis
from .reports import (
    Chart, Heading, Note, Paragraph, ReportDocument, Table,
    _base_header, _fmt_pct,
)
from .snapshot import Snapshot
from .store import Store

THRESH = analysis.Thresholds()
WINDOW = 36            # most recent (de-duplicated) samples used for persistence
LOAD_LIMIT = 240       # snapshots read from the store
CHART_POINTS = 24
PERSIST_STREAK = 3     # consecutive latest samples required to call a problem persistent
NOISY_MIN_SHARE = 0.4  # instant-reading families must recur in this share of eligible samples
PILEUP_MIN = 3         # vehicles simultaneously AT_TERMINAL at one station group
LONG_WAIT_DAYS = 10    # daysAtTerminal; semantics/units unverified
TABLE_CAP = 20
CODE_CAP = 8           # non-HIGH rows per finding family in a priority table, so one family cannot crowd out the rest

SEV_RANK = {"high": 0, "medium": 1, "low": 2}
STATUS_ORDER = ("persistent", "intermittent", "new", "resolved")
STATUS_TITLES = {
    "persistent": "Persistent (present in the latest sample and in the last {streak}+ consecutive samples)",
    "intermittent": "Intermittent (present in the latest sample, but not for {streak}+ consecutive samples)",
    "new": "New or not yet classifiable (first seen recently, or too little history)",
    "resolved": "Seen earlier, not present in the latest sample",
}

# families whose single instant reading is normal noise; only shown when they recur
NOISY = {"line_load_high", "line_load_low", "station_pileup", "long_terminal_wait"}

AREA = {
    "vehicle_no_path": "Vehicles", "vehicle_user_stopped": "Vehicles", "vehicle_idle_depot": "Fleet / depots",
    "long_terminal_wait": "Vehicles", "line_config_issue": "Lines", "line_orphan": "Lines",
    "line_no_vehicles": "Lines", "line_no_stops": "Lines", "line_load_high": "Lines", "line_load_low": "Lines",
    "stock_output_full": "Stocks", "warehouse_full": "Stocks", "station_stock_full": "Stocks",
    "industry_closing": "Industries", "station_pileup": "Stations",
}


# ---------------------------------------------------------------------------
# sampling and per-sample observation
# ---------------------------------------------------------------------------

@dataclass
class Obs:
    code: str
    scope: tuple
    key: tuple
    name: str
    ev: dict[str, Any] = field(default_factory=dict)


@dataclass
class Sample:
    snap: Snapshot
    exists: set = field(default_factory=set)
    obs: dict[tuple, Obs] = field(default_factory=dict)
    stock_rows: list[dict[str, Any]] = field(default_factory=list)

    def flag(self, ob: Obs) -> None:
        self.obs[ob.key] = ob


def _dedupe(snaps: list[Snapshot]) -> list[Snapshot]:
    """Collapse near-simultaneous samples (e.g. a refresh request just after an interval sample)."""
    out: list[Snapshot] = []
    for s in sorted(snaps, key=lambda x: x.game_time):
        if out and s.year_duration and (s.game_time - out[-1].game_time) < s.year_duration / 48:
            out[-1] = s
        else:
            out.append(s)
    return out


def _quarter_buckets(snaps: list[Snapshot]) -> list[Snapshot]:
    buckets: dict[Any, Snapshot] = {}
    for s in snaps:
        d = s.date
        buckets[(d["year"], (d["month"] - 1) // 3) if d else ("t", s.game_time)] = s
    return sorted(buckets.values(), key=lambda x: x.game_time)


def _vehicle_name(v: dict[str, Any]) -> str:
    return v.get("name") or f"Vehicle #{v.get('id')}"


def _line_name(line: dict[str, Any] | None, line_id: Any = None) -> str:
    if line and line.get("name"):
        return line["name"]
    return f"Line #{line_id if line_id is not None else (line or {}).get('id')}"


def _has_line(snap: Snapshot, v: dict[str, Any]) -> bool:
    return v.get("line") in snap.lines_by_id


def _known_sum(rows: list[dict[str, Any]], field: str) -> int | float | None:
    values = [r.get(field) for r in rows]
    return sum(values) if values and all(v is not None for v in values) else None


def _load(line: dict[str, Any]) -> float | None:
    capacities = line.get("capacity") or []
    if any(c.get("used") is None or c.get("capacity") is None for c in capacities):
        return None
    return analysis.line_load(line)


def _observe(snap: Snapshot, known_depots: dict[Any, str] | None = None) -> Sample:
    sm = Sample(snap)
    ex = sm.exists
    for line in snap.lines:
        ex.add(("line", line["id"]))
    for v in snap.vehicles:
        ex.add(("vehicle", v["id"]))
    for ind in snap.industries:
        ex.add(("industry", ind["id"]))

    # ---- reuse analysis findings (no_path, config issues, incomplete lines, closing industries)
    for f in analysis.findings(snap):
        ent = f.entity or {}
        if f.code == "vehicle_no_path":
            sm.flag(Obs(f.code, ("vehicle", ent["id"]), (f.code, ent["id"]), ent.get("name") or f"Vehicle #{ent['id']}",
                        {"line": f.evidence.get("lineName"), "state": f.evidence.get("state")}))
        elif f.code == "line_config_issue":
            issue = f.evidence.get("issue") or {}
            key = (f.code, ent["id"], issue.get("type"), issue.get("stopIndex"), issue.get("cargo"))
            sm.flag(Obs(f.code, ("line", ent["id"]), key, _line_name(snap.lines_by_id.get(ent["id"]), ent["id"]),
                        {"type": issue.get("type"), "stopIndex": issue.get("stopIndex"),
                         "cargo": snap.cargo(issue.get("cargo")),
                         "stopName": _stop_name(snap.lines_by_id.get(ent["id"]), issue.get("stopIndex"))}))
        elif f.code in ("line_orphan", "line_no_vehicles", "line_no_stops"):
            sm.flag(Obs(f.code, ("line", ent["id"]), (f.code, ent["id"]), _line_name(snap.lines_by_id.get(ent["id"]), ent["id"]),
                        {"stops": f.evidence.get("stops"), "vehicles": f.evidence.get("vehicles")}))
        elif f.code == "industry_closing":
            ind = snap.industries_by_id.get(ent["id"]) or {}
            served = any((o.get("shippedYear") or 0) > 0 for o in ind.get("outputs") or []) or \
                any((i.get("deliveredYear") or 0) > 0 for i in ind.get("inputs") or [])
            sm.flag(Obs(f.code, ("industry", ent["id"]), (f.code, ent["id"]), ent.get("name") or f"Industry #{ent['id']}",
                        {"served": served}))
    for vid in snap.problems.get("noPathVehicles") or []:
        v = snap.vehicles_by_id.get(vid)
        if v and ("vehicle_no_path", vid) not in sm.obs:
            sm.flag(Obs("vehicle_no_path", ("vehicle", vid), ("vehicle_no_path", vid), _vehicle_name(v),
                        {"line": (snap.lines_by_id.get(v.get("line")) or {}).get("name"), "state": v.get("state")}))

    # ---- vehicles: user stopped; idle in depot (grouped per depot)
    depot_names = {**(known_depots or {}), **{d["id"]: d.get("name") for d in snap.depots if d.get("name")}}
    for depot_id in set(depot_names) | {v.get("depot") for v in snap.vehicles if v.get("depot") is not None}:
        ex.add(("idledepot", depot_id))
    idle: dict[Any, list[dict[str, Any]]] = {}
    for v in snap.vehicles:
        if v.get("userStopped"):
            row = analysis.vehicle_row(snap, v)
            sm.flag(Obs("vehicle_user_stopped", ("vehicle", v["id"]), ("vehicle_user_stopped", v["id"]),
                        _vehicle_name(v), {"line": row["lineName"], "state": v.get("state"), "value": v.get("value")}))
        if v.get("state") == "IN_DEPOT" and not _has_line(snap, v):
            idle.setdefault(v.get("depot"), []).append(v)
    for depot_id, vs in idle.items():
        label = depot_names.get(depot_id) or (f"Depot #{depot_id} (name not available)" if depot_id is not None else "Unknown depot")
        sm.flag(Obs("vehicle_idle_depot", ("idledepot", depot_id), ("vehicle_idle_depot", depot_id), label,
                    {"count": len(vs), "days": max((v["daysInDepot"] for v in vs), default=None)
                     if all(v.get("daysInDepot") is not None for v in vs) else None,
                     "value": _known_sum(vs, "value"),
                     "examples": sorted(_vehicle_name(v) for v in vs)[:3],
                     "carriers": sorted({v.get("carrier") for v in vs if v.get("carrier")})}))

    # ---- long waits at terminals, per line (daysAtTerminal semantics unverified)
    for line in snap.lines:
        vehicles = snap.line_vehicles(line)
        waits = [v.get("daysAtTerminal") or 0 for v in vehicles]
        long = [w for w in waits if w >= LONG_WAIT_DAYS]
        if long:
            sm.flag(Obs("long_terminal_wait", ("line", line["id"]), ("long_terminal_wait", line["id"]), _line_name(line),
                        {"count": len(long), "max": max(long), "vehicles": len(vehicles)}))

    # ---- line occupancy (instant readings)
    for line in snap.lines:
        load = _load(line)
        if load is None:
            continue
        ex.add(("lineload", line["id"]))
        n_veh = len(line.get("vehicles") or [])
        ev = {"load": load, "vehicles": n_veh, "profitYear": line.get("profitYear")}
        if load >= THRESH.overloaded_load:
            sm.flag(Obs("line_load_high", ("lineload", line["id"]), ("line_load_high", line["id"]), _line_name(line), ev))
        elif load <= THRESH.underused_load and n_veh >= THRESH.underused_min_vehicles:
            sm.flag(Obs("line_load_low", ("lineload", line["id"]), ("line_load_low", line["id"]), _line_name(line), ev))

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
        if n >= PILEUP_MIN:
            names = sorted(_line_name(snap.lines_by_id.get(i), i) for i in group_lines.get(gid, ()))
            sm.flag(Obs("station_pileup", ("station", gid), ("station_pileup", gid), group_name.get(gid) or f"Station #{gid}",
                        {"waiting": n, "lines": len(names), "lineNames": names[:3]}))

    # ---- stocks (only present in newer snapshots)
    if snap.stocks:
        rows = analysis.full_stocks(snap, replace(THRESH, full_stock_ratio=0.0))
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
            full = r["fill"] >= THRESH.full_stock_ratio
            kind = r.get("kind")
            if kind == "industry" and r["served"] is True and full:
                ind = snap.industries_by_id.get(r["owner"]) or {}
                cargos = set(r.get("cargos") or [])
                outs = [o for o in ind.get("outputs") or [] if o.get("cargo") in cargos]
                sm.flag(Obs("stock_output_full", skey, ("stock_output_full", r.get("owner"), r.get("stockId")), r["name"],
                            {"cargo": ", ".join(r["cargoNames"]), "count": r["count"], "capacity": r["capacity"],
                             "fill": r["fill"], "produced": _known_sum(outs, "producedYear"),
                             "shipped": _known_sum(outs, "shippedYear")}))
            elif kind == "station" and full:
                sm.flag(Obs("station_stock_full", skey, ("station_stock_full", r.get("owner"), r.get("stockId")), r["name"],
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
                sm.flag(Obs("warehouse_full", ("warehouse", owner), ("warehouse_full", owner), w["name"],
                            {"full": w["full"], "total": w["total"], "cargos": sorted(w["cargos"])}))
    return sm


def _stop_name(line: dict[str, Any] | None, index: Any) -> str | None:
    stops = (line or {}).get("stops") or []
    return stops[index].get("name") if isinstance(index, int) and 0 <= index < len(stops) else None


# ---------------------------------------------------------------------------
# persistence layer
# ---------------------------------------------------------------------------

@dataclass
class Item:
    code: str
    key: tuple
    name: str
    flagged: list[int]
    eligible: int
    streak: int
    in_latest: bool
    latest_ev: dict[str, Any]
    first_label: str
    last_label: str
    status: str = ""
    severity: str = "low"

    @property
    def n(self) -> int:
        return len(self.flagged)

    @property
    def seen(self) -> str:
        return f"{self.n} of {self.eligible}" + (f" (streak {self.streak})" if self.in_latest else "")


def _track(samples: list[Sample]) -> list[Item]:
    last = len(samples) - 1
    keys: dict[tuple, list[int]] = {}
    for i, sm in enumerate(samples):
        for key in sm.obs:
            keys.setdefault(key, []).append(i)
    items: list[Item] = []
    for key, idxs in keys.items():
        final = samples[idxs[-1]].obs[key]
        eligible = sum(1 for sm in samples if final.scope in sm.exists)
        streak = 0
        for i in range(last, -1, -1):
            if key in samples[i].obs:
                streak += 1
            else:
                break
        items.append(Item(final.code, key, final.name, idxs, max(eligible, len(idxs)), streak, idxs[-1] == last,
                          final.ev, samples[idxs[0]].snap.date_label, samples[idxs[-1]].snap.date_label))
    keep: list[Item] = []
    for it in items:
        it.status = _status(it)
        if it.code in NOISY and not (it.n >= PERSIST_STREAK and it.n / it.eligible >= NOISY_MIN_SHARE):
            continue
        it.severity = _severity(it)
        keep.append(it)
    return keep


def _status(it: Item) -> str:
    if not it.in_latest:
        return "resolved"
    if it.eligible < PERSIST_STREAK:
        return "new"
    if it.streak >= PERSIST_STREAK:
        return "persistent"
    return "new" if it.n == 1 else "intermittent"


def _severity(it: Item) -> str:
    ev, code = it.latest_ev, it.code
    if code in ("vehicle_no_path", "line_config_issue"):
        return "high"
    if code == "stock_output_full":
        return "high" if it.status == "persistent" else "medium"
    if code == "industry_closing":
        return "high" if ev.get("served") else "low"
    if code == "vehicle_idle_depot":
        return "medium" if (ev.get("days") or 0) >= THRESH.idle_depot_days else "low"
    if code in ("vehicle_user_stopped", "line_orphan", "line_no_vehicles", "line_no_stops",
                "warehouse_full", "station_stock_full", "station_pileup"):
        return "medium"
    if code == "line_load_high":
        return "medium" if ev.get("vehicles", 0) >= 2 else "low"
    if code == "line_load_low":
        return "medium" if (ev.get("profitYear") or 0) < 0 else "low"
    return "low"


def _cargo_text(cargos: list[str]) -> str:
    if len(cargos) > 5:
        return f"{len(cargos)} cargo types (general-purpose stock)"
    return ", ".join(cargos) or "-"


def _money(v: Any) -> str:
    return "-" if v is None else f"{v:,}"


def _describe(it: Item) -> tuple[str, str, str]:
    """(evidence, what it may mean, what to check manually) for the latest flagged reading."""
    ev, c = it.latest_ev, it.code
    if c == "vehicle_no_path":
        return (f"Vehicle cannot find a path (line: {ev.get('line') or 'none'}, state {ev.get('state')}).",
                "Route is broken or the vehicle is stranded; it earns nothing and may block others.",
                "Open the vehicle's line and look for disconnected track/road, removed stops, one-way or signalling gaps.")
    if c == "vehicle_user_stopped":
        return (f"Vehicle manually stopped (line: {ev.get('line') or 'none'}); recorded value {_money(ev.get('value'))}.",
                "Possibly deliberate; otherwise a forgotten stopped vehicle that still incurs costs.",
                "Confirm in the game whether the stop is intentional; restart or sell if not.")
    if c == "vehicle_idle_depot":
        return (f"{ev['count']} vehicle(s) with no line inside this depot (longest {ev['days']} days; "
                f"{', '.join(ev['carriers']) or '-'}); recorded value {_money(ev['value'])}; e.g. {'; '.join(ev['examples'])}.",
                "Capital tied up (recent purchase awaiting assignment, or abandoned reserve vehicles).",
                "Assign them to a line or sell them if the reserve is not intended.")
    if c == "long_terminal_wait":
        return (f"{ev['count']} of {ev['vehicles']} vehicles with daysAtTerminal >= {LONG_WAIT_DAYS} (max {ev['max']}).",
                "Queue or slow loading at a stop; may also be a normal full-load wait. Counter semantics are unverified.",
                "Inspect the line's stops: loading mode, waiting times, terminal count, whether cargo is available.")
    if c == "line_config_issue":
        where = f" at stop {ev.get('stopIndex')}" + (f" ({ev['stopName']})" if ev.get("stopName") else "") \
            if isinstance(ev.get("stopIndex"), int) and ev.get("stopIndex", -1) >= 0 else " (no specific stop)"
        return (f"Game-reported issue {ev.get('type')}{where}, cargo {ev.get('cargo') or '-'}.",
                "The game says this line cannot load/unload or configure that cargo as set.",
                "Open the line, review stop cargo filters and compatible vehicles for that cargo.")
    if c in ("line_orphan", "line_no_vehicles", "line_no_stops"):
        return (f"{ev.get('vehicles')} vehicles and {ev.get('stops')} stops.",
                "Incomplete or abandoned line.", "Complete it (vehicles and at least two stops) or remove it.")
    if c == "line_load_high":
        return (f"Occupancy {_fmt_pct(ev['load'])} with {ev['vehicles']} vehicles.",
                "Vehicles often full at sampling time; may indicate unmet demand (not proven).",
                "Check station queues/waiting cargo before adding vehicles or capacity.")
    if c == "line_load_low":
        return (f"Occupancy {_fmt_pct(ev['load'])} with {ev['vehicles']} vehicles; rolling profit {_money(ev.get('profitYear'))}.",
                "Often nearly empty at sampling time; possibly too many vehicles or weak demand.",
                "Check demand at the stops; consider fewer vehicles or merging lines.")
    if c == "stock_output_full":
        ratio = f"; shipped/produced {_money(ev['shipped'])}/{_money(ev['produced'])}" if ev.get("produced") is not None else ""
        return (f"{ev['cargo']}: {ev['count']:,}/{ev['capacity']:,} ({_fmt_pct(ev['fill'])}){ratio}.",
                "Output stock near/full on an industry with recorded shipping: collection may be insufficient. At capacity, excess production is destroyed (documented mechanic); actual destruction is not measured.",
                "Inspect the serving line(s): vehicle count, capacity, frequency, loading time, queues at the pick-up stop.")
    if c == "warehouse_full":
        cargos = _cargo_text(ev.get("cargos") or [])
        return (f"{ev['full']} of {ev['total']} stocks full ({cargos}).",
                "Full warehouse stocks may stop unloading deliveries [INFERENCE]; also tied-up cargo.",
                "Check which lines deliver to or collect from this warehouse and whether collection exists.")
    if c == "station_stock_full":
        return (f"{ev['cargo']}: {ev['count']:,}/{ev['capacity']:,}.",
                "Station stock full.", "Check lines collecting that cargo at this station.")
    if c == "industry_closing":
        return ("Marked for closure" + ("; your network ships from/delivers to it." if ev.get("served") else "; no recorded shipments or deliveries."),
                "Dependent lines will lose their cargo source or sink.",
                "If lines depend on it, plan a replacement source or accept closure.")
    if c == "station_pileup":
        return (f"{ev['waiting']} vehicles at the stop at once; {ev['lines']} line(s) call here ({'; '.join(ev['lineNames'])}).",
                "Possible congestion/queue at the station (vehicles at a terminal may also just be loading).",
                "Watch the station: add terminals/platforms or spread lines over alternative stops if a queue shows.")
    return ("", "", "")


# ---------------------------------------------------------------------------
# sections
# ---------------------------------------------------------------------------

def _sort_key(it: Item) -> tuple:
    return (SEV_RANK[it.severity], -it.n, -(it.latest_ev.get("fill") or 0), it.name, str(it.key))


def _priority_blocks(items: list[Item]) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Prioritized Findings")]
    sev = Counter(i.severity for i in items if i.status != "resolved")
    status = Counter(i.status for i in items)
    blocks.append(Paragraph(
        f"Active now: {sev['high']} high, {sev['medium']} medium, {sev['low']} low severity "
        f"({status['persistent']} persistent, {status['intermittent']} intermittent, {status['new']} new/unclassified). "
        f"{status['resolved']} further finding(s) were seen earlier in the window but are absent from the latest sample."))
    blocks.append(Note(
        "How to read persistence",
        f"'Seen N of M' counts samples in the persistence window in which the entity existed and the condition held "
        f"(M excludes samples where the entity or data source did not yet exist); streak is the number of consecutive "
        f"latest samples. Persistent needs a streak of {PERSIST_STREAK}+. Samples are irregularly spaced points "
        f"in time, not continuous telemetry; use the listed calendar dates rather than treating sample counts as elapsed months. Severity is a heuristic ranking, not a measured loss: game-reported issues and no-path vehicles are HIGH; "
        f"a full output stock on a served industry is HIGH once persistent (full output stock destroys excess production, "
        f"per mechanics) and MEDIUM otherwise; occupancy extremes are MEDIUM only for crowded or loss-making lines."))
    for st in STATUS_ORDER:
        group = sorted((i for i in items if i.status == st), key=_sort_key)
        title = STATUS_TITLES[st].format(streak=PERSIST_STREAK)
        blocks.append(Heading(3, f"{title} - {len(group)} finding(s)"))
        if not group:
            blocks.append(Paragraph("None."))
            continue
        shown: list[Item] = []
        omitted: Counter = Counter()
        taken: Counter = Counter()
        for it in group:
            if it.severity == "high" or taken[it.code] < CODE_CAP:
                taken[it.code] += 1
                shown.append(it)
            else:
                omitted[it.code] += 1
        rows = []
        for it in shown:
            evidence, meaning, check = _describe(it)
            rows.append([it.severity.upper(), AREA.get(it.code, it.code), it.name, evidence, it.seen,
                         f"{it.first_label}" if st != "resolved" else f"{it.first_label} - {it.last_label}",
                         meaning, check])
        cols = ["Severity", "Area", "Entity", "Evidence (latest flagged sample)", "Seen (N of M samples)",
                "First seen" if st != "resolved" else "Seen between", "What it may mean", "Check in game (manual)"]
        blocks.append(Table(cols, rows))
        if omitted:
            blocks.append(Paragraph("Not shown (lower-ranked within their family; see the detail sections): "
                                    + "; ".join(f"{n} x {AREA.get(c, c)} / {c}" for c, n in sorted(omitted.items())) + "."))
    return blocks


def _stock_series(samples: list[Sample]) -> dict[tuple, list[tuple[int, int, int, float]]]:
    out: dict[tuple, list[tuple[int, int, int, float]]] = {}
    for i, sm in enumerate(samples):
        for r in sm.stock_rows:
            out.setdefault((r.get("kind"), r.get("owner"), r.get("stockId")), []).append(
                (i, r["count"], r["capacity"], r["fill"]))
    return out


def _slope(values: list[float]) -> float:
    n = len(values)
    mean = sum(values) / n
    centre = (n - 1) / 2
    den = sum((i - centre) ** 2 for i in range(n))
    return sum((i - centre) * (v - mean) for i, v in enumerate(values)) / den if den else 0.0


def _stock_blocks(samples: list[Sample], items: list[Item]) -> list[Any]:
    latest = samples[-1]
    with_stocks = [i for i, s in enumerate(samples) if s.stock_rows]
    blocks: list[Any] = [Heading(2, "Stocks: Cargo Destruction Risk")]
    if not latest.stock_rows:
        blocks.append(Note("Insufficient data", "The latest sample has no stock data (mod/snapshot predates stock collection); "
                           "no stock conclusion is possible."))
        return blocks
    first = samples[with_stocks[0]].snap.date_label
    blocks.append(Paragraph(
        f"Stock data exists in {len(with_stocks)} of {len(samples)} samples (first: {first}). "
        "Earlier samples are unknown, not 'no problem'. Industry rows count only output stocks whose cargo matches a "
        "recorded industry output; 'served' means that output has annual shipments > 0."))
    full_items = sorted((i for i in items if i.code == "stock_output_full"), key=_sort_key)
    blocks.append(Heading(3, "Served industries with a full output stock"))
    if full_items:
        rows = []
        for it in full_items[:TABLE_CAP]:
            ev = it.latest_ev
            ratio = ev["shipped"] / ev["produced"] if ev.get("produced") and ev.get("shipped") is not None else None
            rows.append([it.name, ev["cargo"], f"{ev['count']:,}/{ev['capacity']:,}", it.seen, it.first_label,
                         ev.get("produced"), ev.get("shipped"), _fmt_pct(ratio), it.status])
        blocks.append(Table(["Industry", "Cargo", "Stock (latest flagged)", "Full in N of M samples", "First seen full",
                             "Produced (annual counter)", "Shipped (annual counter)", "Shipped/Produced", "Status"], rows,
                            ["left", "left", "right", "left", "left", "right", "right", "right", "left"]))
        if len(full_items) > TABLE_CAP:
            blocks.append(Paragraph(f"{len(full_items) - TABLE_CAP} more omitted."))
        blocks.append(Note("Reading the counters",
                           "Annual counters are rolling-year figures with unverified accounting; the ratio only indicates "
                           "whether collection keeps up relative to production, it is not a destruction measurement."))
    else:
        blocks.append(Paragraph("No served industry output stock is at or above "
                                f"{THRESH.full_stock_ratio:.0%} in the window."))

    wh = sorted((i for i in items if i.code == "warehouse_full"), key=_sort_key)
    blocks.append(Heading(3, "Warehouses with full stocks"))
    if wh:
        blocks.append(Table(
            ["Warehouse", "Full stocks (latest flagged)", "Cargos", "Seen with a full stock (N of M)", "First seen", "Status"],
            [[i.name, f"{i.latest_ev['full']} of {i.latest_ev['total']}", _cargo_text(i.latest_ev["cargos"]),
              i.seen, i.first_label, i.status] for i in wh[:TABLE_CAP]]))
    else:
        blocks.append(Paragraph("No warehouse stock at or above the full threshold."))

    # approaching full: rising, not yet full
    series = _stock_series(samples)
    approaching = []
    names = {(r.get("kind"), r.get("owner"), r.get("stockId")): r for r in latest.stock_rows}
    for key, pts in series.items():
        if key not in names or pts[-1][0] != len(samples) - 1:
            continue
        recent = pts[-6:]
        if len(recent) < 3:
            continue
        r = names[key]
        if r["kind"] == "industry" and r["served"] is not True:
            continue
        fill = recent[-1][3]
        if not 0.5 <= fill < THRESH.full_stock_ratio:
            continue
        slope = _slope([p[1] for p in recent])
        cap = recent[-1][2]
        if slope / cap < 0.02:
            continue
        approaching.append([r["name"], r["kind"].title(), ", ".join(c for c in r["cargoNames"] if c), _fmt_pct(fill),
                            recent[0][1], recent[-1][1], f"+{slope:.1f}", round((cap - recent[-1][1]) / slope, 1)])
    approaching.sort(key=lambda row: row[-1])
    blocks.append(Heading(3, "Rising stocks that are not yet full"))
    if approaching:
        blocks.append(Table(["Stock owner", "Kind", "Cargo", "Fill (latest)", "Count (window start)", "Count (latest)",
                             "Units per sample (linear)", "Samples to full at this rate"],
                            approaching[:TABLE_CAP], ["left", "left", "left", "right", "right", "right", "right", "right"]))
        blocks.append(Note("Inference", "Samples-to-full is a linear extrapolation over the last up to 6 samples; "
                           "stocks do not necessarily rise linearly."))
    else:
        blocks.append(Paragraph("No stock between 50% and the full threshold is rising by 2% of capacity per sample or more."))

    unserved = [r for r in latest.stock_rows if r["kind"] == "industry" and r["served"] is False
                and r["fill"] >= THRESH.full_stock_ratio]
    blocks.append(Heading(3, "Near/full output stocks with zero recorded shipments"))
    blocks.append(Paragraph(
        f"{len(unserved)} industry output stock(s) are near/full with recorded annual shipments equal to zero in the latest sample. "
        "These are possible production opportunities, not proven network bottlenecks. A new or interrupted service may "
        "also have zero annual shipments; check connections before concluding they are unserved."))
    return blocks


def _load_blocks(samples: list[Sample], items: list[Item]) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Line Occupancy Persistence")]
    shown = sorted((i for i in items if i.code in ("line_load_high", "line_load_low")), key=_sort_key)
    if len(samples) < PERSIST_STREAK:
        blocks.append(Note("Insufficient data", f"Persistence needs at least {PERSIST_STREAK} samples; only {len(samples)} available."))
        return blocks
    blocks.append(Paragraph(
        f"Lines whose instantaneous occupancy was >= {THRESH.overloaded_load:.0%} (or <= {THRESH.underused_load:.0%} with "
        f"{THRESH.underused_min_vehicles}+ vehicles) in at least {PERSIST_STREAK} samples and {NOISY_MIN_SHARE:.0%} of the "
        "samples where occupancy was measurable. Single readings that did not recur are deliberately not listed."))
    rows = []
    for it in shown[:TABLE_CAP * 2]:
        loads = []
        for sm in samples:
            line = sm.snap.lines_by_id.get(it.key[1])
            val = _load(line) if line else None
            if val is not None:
                loads.append(val)
        current = samples[-1].snap.lines_by_id.get(it.key[1])
        rows.append([it.name, "Often full" if it.code == "line_load_high" else "Often nearly empty", it.seen,
                     _fmt_pct(sum(loads) / len(loads)) if loads else "-", _fmt_pct(min(loads)) if loads else "-",
                     _fmt_pct(max(loads)) if loads else "-", _fmt_pct(_load(current)) if current else "-",
                     len(current.get("vehicles") or []) if current else None,
                     current.get("profitYear") if current else None, it.status])
    if rows:
        blocks.append(Table(["Line", "Pattern", "Flagged (N of M)", "Sample mean", "Min", "Max", "Latest",
                             "Vehicles", "Rolling annual profit (latest)", "Status"], rows,
                            ["left", "left", "left", "right", "right", "right", "right", "right", "right", "left"]))
        blocks.append(Note("Limits", "Sample mean is an unweighted average of instants, not a time average. High occupancy "
                           "alone does not prove unmet demand; low occupancy alone does not prove no demand."))
        if len(shown) > TABLE_CAP * 2:
            blocks.append(Paragraph(f"{len(shown) - TABLE_CAP * 2} lower-ranked occupancy patterns omitted."))
    else:
        blocks.append(Paragraph("No line shows a recurring extreme occupancy in the window."))
    return blocks


def _station_depot_blocks(samples: list[Sample], items: list[Item]) -> list[Any]:
    latest = samples[-1].snap
    blocks: list[Any] = [Heading(2, "Station Pile-ups and Depots")]
    piles = sorted((i for i in items if i.code == "station_pileup"), key=_sort_key)
    if piles:
        blocks.append(Table(["Station", "Recurring (N of M)", "Vehicles waiting (latest flagged)", "Lines calling", "Example lines", "Status"],
                            [[i.name, i.seen, i.latest_ev["waiting"], i.latest_ev["lines"], "; ".join(i.latest_ev["lineNames"]), i.status]
                             for i in piles[:TABLE_CAP]]))
        blocks.append(Note("Limits", f"{PILEUP_MIN}+ vehicles AT_TERMINAL at one stop in the same sample. The mod records no "
                           "waiting-cargo or passenger counts per station, so starved or overcrowded stations cannot be "
                           "measured directly; this is only a vehicle-side proxy."))
    else:
        blocks.append(Paragraph(f"No station had {PILEUP_MIN}+ vehicles waiting simultaneously in a recurring way."))
    by_depot = Counter(v.get("depot") for v in latest.vehicles if v.get("state") == "IN_DEPOT")
    blocks.append(Heading(3, "Vehicles inside depots (latest sample)"))
    if by_depot:
        names = {d["id"]: d.get("name") for d in latest.depots}
        rows = []
        for depot_id, n in by_depot.most_common():
            vs = [v for v in latest.vehicles if v.get("state") == "IN_DEPOT" and v.get("depot") == depot_id]
            unassigned = [v for v in vs if not _has_line(latest, v)]
            rows.append([names.get(depot_id) or f"Depot #{depot_id} (name not available)", n,
                         len(unassigned), _known_sum(unassigned, "value") if unassigned else 0])
        blocks.append(Table(["Depot", "Vehicles inside", "Of which without a line", "Recorded value of those"], rows,
                            ["left", "right", "right", "right"]))
    else:
        blocks.append(Paragraph("No vehicle was inside a depot in the latest sample."))
    return blocks


def _counts(samples: list[Sample], codes: set[str]) -> list[int]:
    return [sum(1 for ob in sm.obs.values() if ob.code in codes) for sm in samples]


def _trend_blocks(chart_samples: list[Sample], bucketed: bool) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Network Health Over Time")]
    if len(chart_samples) < 2:
        blocks.append(Note("Insufficient data", "At least two samples are needed for a trend."))
        return blocks
    cats = [s.snap.date_label for s in chart_samples]
    if bucketed:
        blocks.append(Note("Sampling", "History is long; the last sample of each game quarter is shown (most recent "
                           f"{len(chart_samples)} quarters)."))
    groups = [
        ("Hard problems per sample", [
            ("Vehicles without path", {"vehicle_no_path"}), ("Vehicles stopped by player", {"vehicle_user_stopped"}),
            ("Lines with issues or incomplete", {"line_config_issue", "line_orphan", "line_no_vehicles", "line_no_stops"}),
            ("Vehicles idle in depots", {"vehicle_idle_depot"})], False),
        ("Instant pressure readings", [
            ("Lines at 90%+ occupancy", {"line_load_high"}), ("Lines at 30% or less occupancy", {"line_load_low"}),
            ("Stops with 3+ vehicles waiting", {"station_pileup"}), ("Lines with long terminal waits", {"long_terminal_wait"})], False),
        ("Full stocks per sample", [
            ("Served industry outputs full", {"stock_output_full"}), ("Warehouses with a full stock", {"warehouse_full"})], True),
    ]
    for title, series_def, needs_stocks in groups:
        pts = [s for s in chart_samples if s.stock_rows] if needs_stocks else chart_samples
        if len(pts) < 2:
            if needs_stocks:
                blocks.append(Paragraph("Stock trend unavailable: fewer than two samples contain stock data."))
            continue
        series = [(label, _counts(pts, codes)) for label, codes in series_def]
        series = [(label, vals) for label, vals in series if any(vals)]
        if not series:
            blocks.append(Paragraph(f"{title}: all counts are zero across {len(pts)} samples."))
            continue
        blocks.append(Heading(3, title))
        cat = [s.snap.date_label for s in pts]
        blocks.append(Chart("line", title, cat, [(label, [float(v) for v in vals]) for label, vals in series]))
        blocks.append(Table(["Sample date"] + [label for label, _ in series],
                            [[cat[i]] + [vals[i] for _, vals in series] for i in range(len(pts))],
                            ["left"] + ["right"] * len(series)))
    return blocks


_AFFECTS = (
    ("depot", "depot names/positions (idle-capital attribution may show 'name not available'); depots that failed to read may be missing from depot listings; vehicle depot ids are unaffected"),
    ("stock", "stock fill and cargo-destruction findings"),
    ("line", "line occupancy, issues and profit"),
    ("vehicle", "vehicle state and no-path/idle findings"),
    ("industr", "industry flows and closing/served classification"),
    ("station", "station data"),
    ("town", "town data"),
)


def _error_family(text: str) -> tuple[str, str]:
    first = text.splitlines()[0] if text else ""
    family = re.sub(r"\[\d+\]", "[*]", first.split(": ", 1)[0])
    family = family[:80]
    match = re.search(r"\]:\d+: (.*)", text)
    tail = match.group(1).strip() if match else (first.split(": ", 1)[1] if ": " in first else first)
    return family, tail[:100]


def _data_blocks(samples: list[Sample]) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Data Coverage and Collection Errors")]
    n = len(samples)

    def coverage(label: str, pred) -> list[Any]:
        idx = [i for i, s in enumerate(samples) if pred(s.snap)]
        return [label, f"{len(idx)} of {n}", samples[idx[0]].snap.date_label if idx else "never"]

    blocks.append(Table(["Data source", "Samples with data", "First sample with data"], [
        coverage("Lines and vehicles", lambda s: bool(s.lines)),
        coverage("Stocks (stations/industries/warehouses)", lambda s: bool(s.stocks)),
        coverage("Depots", lambda s: bool(s.depots)),
        coverage("Vehicle depot id", lambda s: any(v.get("depot") is not None for v in s.vehicles)),
    ]))
    fam: dict[tuple, dict[str, Any]] = {}
    for i, sm in enumerate(samples):
        for e in sm.snap.errors:
            f = fam.setdefault(_error_family(e), {"samples": set(), "latest": set()})
            f["samples"].add(i)
            if i == n - 1:
                f["latest"].add(e)
    if fam:
        rows = []
        for (family, tail), f in sorted(fam.items(), key=lambda kv: -len(kv[1]["samples"])):
            lowered = family.lower()
            affects = next((a for k, a in _AFFECTS if k in lowered), "unknown")
            rows.append([family, tail, f"{len(f['samples'])} of {n}", len(f["latest"]), affects])
        blocks.append(Table(["Collector", "Message", "Samples with error", "Occurrences in latest sample", "Conclusions affected"], rows))
        blocks.append(Note("Effect on this report", "Collector errors mean the affected entities are absent or partial in the data; their "
                           "absence from a finding list is not evidence that they are healthy."))
    else:
        blocks.append(Paragraph("No collection errors reported in any sample of the window."))

    # daysAtTerminal reset detection
    counts = [sum(1 for v in s.snap.vehicles if (v.get("daysAtTerminal") or 0) >= 5) for s in samples]
    resets = [(samples[i - 1].snap.date_label, samples[i].snap.date_label) for i in range(1, n)
              if max(counts[i - 1], counts[i]) >= 10 and min(counts[i - 1], counts[i]) == 0]
    if resets:
        blocks.append(Note(
            "daysAtTerminal discontinuity",
            "Vehicles with daysAtTerminal >= 5 jump between zero and many across consecutive samples ("
            + "; ".join(f"{a} to {b}" for a, b in resets[:3]) + "). The counter's semantics are unverified and may reset "
            "(for example on save reload), so long-wait findings that 'resolve' at such a boundary may be artifacts rather than real fixes."))
    return blocks


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

def build(store: Store) -> ReportDocument:
    latest = store.latest()
    if latest is None:
        raise ValueError("No snapshot found. Load a save with the bridge enabled and run tf3c refresh.")
    history = _dedupe(store.recent_snapshots(limit=LOAD_LIMIT, game_time=latest.game_time) or [latest])
    window = history[-WINDOW:]
    depots = {d["id"]: d["name"] for s in history for d in s.depots if d.get("name")}
    samples = [_observe(s, depots) for s in window]
    items = _track(samples)
    cur = samples[-1].snap

    chart_snaps = window
    bucketed = len(history) > WINDOW
    if bucketed:
        chart_snaps = _quarter_buckets(history)[-CHART_POINTS:]
        by_time = {s.snap.game_time: s for s in samples}
        chart_samples = [by_time.get(s.game_time) or _observe(s, depots) for s in chart_snaps]
    else:
        chart_samples = samples

    header = _base_header(cur, len(window))
    header[1] = ("Latest Sample Date", cur.date_label)
    header[3] = ("Collection Errors", f"{len(cur.errors)} in the latest sample (details under Data Coverage)" if cur.errors else "None reported")
    header.insert(2, ("Persistence Window", f"{window[0].date_label} to {cur.date_label} ({len(window)} samples after merging "
                                           f"near-simultaneous ones; {len(history)} available, up to {WINDOW} used)"))
    header.insert(3, ("Thresholds", f"stock full >= {THRESH.full_stock_ratio:.0%}; persistent = streak {PERSIST_STREAK}+; "
                                     f"pile-up {PILEUP_MIN}+ vehicles; long wait daysAtTerminal >= {LONG_WAIT_DAYS} (unverified unit); "
                                     f"occupancy >= {THRESH.overloaded_load:.0%} / <= {THRESH.underused_load:.0%}"))
    header.append(("History Read Limit", f"Up to {LOAD_LIMIT} stored snapshots at or before the latest timeline point; "
                                        "older history beyond that is not evaluated."))

    blocks: list[Any] = []
    if len(window) < PERSIST_STREAK:
        blocks.append(Note("Limited history", f"Only {len(window)} sample(s) available: persistence cannot be judged, "
                           "so findings are listed as new/unclassified and recurring-reading checks are suppressed."))
    blocks += _priority_blocks(items)
    blocks += _stock_blocks(samples, items)
    blocks += _load_blocks(samples, items)
    blocks += _station_depot_blocks(samples, items)
    blocks += _trend_blocks(chart_samples, bucketed)
    blocks += _data_blocks(samples)
    blocks.append(Note("What this report cannot show",
                       "Per-station waiting cargo/passengers, actual destroyed-item counts and vehicle queue order are not collected. "
                       "Findings are observations at sampled instants plus inferences; every in-game change is yours to make and "
                       "the 'check in game' column describes what to inspect, not a prescribed fix."))
    return ReportDocument("bottlenecks", "Network Health and Bottleneck Report", header, blocks)
