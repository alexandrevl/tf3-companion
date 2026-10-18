"""Towns report: evolution, ranking, coverage by our lines, unmet cargo demand, hot spots.

Everything is derived from stored snapshots. Town "size" is the sum of the three building
capacities (residential + commercial + industrial). That is a capacity proxy, not a head count.
"""

from __future__ import annotations

import datetime
import json
import math
import statistics
from dataclasses import dataclass, field
from typing import Any

from .reports import Chart, Heading, Note, Paragraph, ReportDocument, Table, _base_header, _fmt, _fmt_pct
from .snapshot import Snapshot, _list
from .store import Store

# Passenger rating = min(1, 2 x line usage) (knowledge/mechanics.md M2): usage above this adds nothing to it.
USAGE_CAP = 0.5
# Growth statistics need a window long enough to mean something (calendar years) and a few samples.
MIN_WINDOW_YEARS = 0.25
MIN_WINDOW_SAMPLES = 3
LARGE_QUANTILE = 0.6  # 'large' = upper 40% of towns by capacity proxy
MAX_TABLE_ROWS = 15
MAX_CHART_POINTS = 40
PAIR_POOL = 10
# `lines[].capacity[].cargo` is cargoTypeId + 1 (knowledge/snapshot_schema.md, loadConfig note); town
# `cargoSupply[].cargo` and `industries[].outputs[].cargo` are plain cargo ids.
LINE_CAPACITY_CARGO_OFFSET = 1


# ---------------------------------------------------------------------------
# History extraction
# ---------------------------------------------------------------------------

@dataclass
class _TownPoint:
    name: str
    caps: tuple[float, ...]
    usage: float | None
    noise: float | None
    pollution: float | None
    development: bool | None
    supply: dict[int, tuple[float, float]]

    @property
    def cap(self) -> float | None:
        return float(sum(self.caps)) if self.caps else None


@dataclass
class _Sample:
    game_time: int
    year_duration: int
    label: str
    ymd: tuple[int, int, int] | None
    towns: dict[int, _TownPoint] = field(default_factory=dict)


def _num(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _town_point(town: dict[str, Any]) -> _TownPoint:
    caps = tuple(c for c in (_num(v) for v in _list(town.get("capacities"))) if c is not None)
    supply = {}
    for entry in _list(town.get("cargoSupply")):
        cargo, sup, limit = entry.get("cargo"), _num(entry.get("supply")), _num(entry.get("limit"))
        if isinstance(cargo, int) and sup is not None and limit is not None:
            supply[cargo] = (sup, limit)
    dev = town.get("developmentActive")
    return _TownPoint(
        name=town.get("name") or f"Town #{town.get('id')}", caps=caps, usage=_num(town.get("lineUsage")),
        noise=_num(town.get("noise")), pollution=_num(town.get("pollution")),
        development=dev if isinstance(dev, bool) else None, supply=supply,
    )


def _sample_from_raw(raw: dict[str, Any]) -> _Sample:
    meta = raw.get("meta") or {}
    date = meta.get("date") if isinstance(meta.get("date"), dict) else None
    ymd = (date["year"], date["month"], date["day"]) if date else None
    label = f"{ymd[0]:04d}-{ymd[1]:02d}-{ymd[2]:02d}" if ymd else str(meta.get("year") or f"t={meta['gameTime']}")
    sample = _Sample(int(meta["gameTime"]), int(meta.get("yearDuration") or 0), label, ymd)
    for town in _list(raw.get("towns")):
        sample.towns[town["id"]] = _town_point(town)
    return sample


def _load_history(store: Store, latest: Snapshot) -> list[_Sample]:
    """Compact per-snapshot town data up to the latest snapshot, oldest first (the store holds one save)."""
    samples: list[_Sample] = []
    for row in store.conn.execute(
        "SELECT data FROM snapshots WHERE game_time <= ? ORDER BY game_time", (latest.game_time,)
    ):
        samples.append(_sample_from_raw(json.loads(row["data"])))
    return samples


def _bucket(sample: _Sample, span_years: float) -> tuple[int, ...]:
    if sample.ymd:
        year, month, _ = sample.ymd
        if span_years <= 2:
            return (year, month)
        return (year, (month - 1) // 3) if span_years <= 10 else (year,)
    months = int(sample.game_time / sample.year_duration * 12) if sample.year_duration else 0
    return (months,) if span_years <= 2 else (months // 3,) if span_years <= 10 else (months // 12,)


def _pick_samples(samples: list[_Sample]) -> list[_Sample]:
    """Chart/table sample points: last snapshot per month/quarter/year (by span), plus the first."""
    if len(samples) <= 2:
        return list(samples)
    first, last = samples[0], samples[-1]
    span = _span_years(samples)
    buckets: dict[tuple[int, ...], _Sample] = {}
    for s in samples:
        buckets[_bucket(s, span)] = s
    picked = {first.game_time: first, **{s.game_time: s for s in buckets.values()}}
    out = sorted(picked.values(), key=lambda s: s.game_time)
    if len(out) > MAX_CHART_POINTS:
        step = (len(out) - 1) / (MAX_CHART_POINTS - 1)
        out = [out[round(i * step)] for i in range(MAX_CHART_POINTS)]
    return out


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _signed(value: float | None, digits: int = 0) -> str:
    if value is None:
        return "-"
    if round(value, digits) == 0:
        return "0"
    return f"{value:+.{digits}f}"


def _signed_pct(value: float | None) -> str:
    return "-" if value is None else f"{value * 100:+.1f}%"


def _pct(value: float | None) -> str:
    return _fmt_pct(value) if value is not None else "-"


def _num_str(value: float | None, digits: int = 0) -> str:
    return "-" if value is None else f"{value:,.{digits}f}"


def _omitted(total: int, shown: int) -> str:
    return f" ({total - shown} more omitted)" if total > shown else ""


def _quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


# ---------------------------------------------------------------------------
# Per-town analysis
# ---------------------------------------------------------------------------

def _passenger_cargo_id(snap: Snapshot) -> int:
    for entry in _list(snap.raw.get("cargos")):
        if "passenger" in str(entry.get("res") or "").casefold() and isinstance(entry.get("id"), int):
            return entry["id"]
    return 0


def _is_passenger_line(line: dict[str, Any], passenger_id: int) -> bool:
    index = passenger_id + LINE_CAPACITY_CARGO_OFFSET
    return any(c.get("cargo") == index and (c.get("capacity") or 0) > 0 for c in _list(line.get("capacity")))


@dataclass
class _Network:
    """Which of our lines touch which town, via the station-group -> town assignment in stations[]."""
    station_town: dict[int, int]
    stations_by_town: dict[int, set[int]]
    lines_by_town: dict[int, dict[int, bool]]  # town id -> {line id: is passenger line}
    line_names: dict[int, str]
    line_towns: dict[int, list[int]]
    passenger_edges: set[frozenset[int]]
    component: dict[int, int]  # town id -> passenger-network component id


def _build_network(snap: Snapshot) -> _Network:
    station_town = {s["id"]: s["town"] for s in snap.stations if isinstance(s.get("town"), int)}
    stations_by_town: dict[int, set[int]] = {}
    for sid, tid in station_town.items():
        stations_by_town.setdefault(tid, set()).add(sid)
    passenger_id = _passenger_cargo_id(snap)
    lines_by_town: dict[int, dict[int, bool]] = {}
    names: dict[int, str] = {}
    line_towns: dict[int, list[int]] = {}
    edges: set[frozenset[int]] = set()
    parent: dict[int, int] = {}

    def find(x: int) -> int:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for line in snap.lines:
        names[line["id"]] = line.get("name") or f"Line #{line['id']}"
        towns: list[int] = []
        for stop in _list(line.get("stops")):
            tid = station_town.get(stop.get("stationGroup"))
            if tid is not None and tid not in towns:
                towns.append(tid)
        line_towns[line["id"]] = towns
        passenger = _is_passenger_line(line, passenger_id)
        for tid in towns:
            lines_by_town.setdefault(tid, {})[line["id"]] = lines_by_town.get(tid, {}).get(line["id"], False) or passenger
        if passenger:
            for i, a in enumerate(towns):
                find(a)
                for b in towns[i + 1:]:
                    edges.add(frozenset((a, b)))
                    parent[find(a)] = find(b)
    return _Network(station_town, stations_by_town, lines_by_town, names, line_towns, edges,
                    {tid: find(tid) for tid in parent})


@dataclass
class _Row:
    id: int
    name: str
    cap: float | None
    caps: tuple[float, ...]
    first_cap: float | None
    delta: float | None
    growth: float | None
    annual: float | None
    last_change: str | None
    usage: float | None
    usage_first: float | None
    noise: float | None
    noise_first: float | None
    pollution: float | None
    pollution_first: float | None
    development: bool | None
    stations: int
    lines_all: int
    lines_passenger: int
    supply: dict[int, tuple[float, float]]
    rank: int = 0
    share: float | None = None
    large: bool = False
    position: list[float] | None = None

    @property
    def served(self) -> bool:
        return self.stations > 0

    @property
    def headroom(self) -> float | None:
        return None if self.usage is None else max(0.0, USAGE_CAP - self.usage)


def _calendar_days(samples: list[_Sample]) -> int | None:
    if len(samples) < 2 or not samples[0].ymd or not samples[-1].ymd:
        return None
    try:
        return (datetime.date(*samples[-1].ymd) - datetime.date(*samples[0].ymd)).days
    except ValueError:
        return None


def _span_years(samples: list[_Sample]) -> float:
    """Elapsed time in calendar years from meta.date. meta.yearDuration is not used when dates exist: on real
    data it is about 4x shorter than the calendar year, so it would overstate elapsed time."""
    if len(samples) < 2:
        return 0.0
    days = _calendar_days(samples)
    if days is not None:
        return days / 365.25
    last = samples[-1]
    return (last.game_time - samples[0].game_time) / last.year_duration if last.year_duration else 0.0


def _build_rows(latest: Snapshot, samples: list[_Sample], net: _Network) -> list[_Row]:
    last = samples[-1]
    span = _span_years(samples)
    enough = span >= MIN_WINDOW_YEARS and len(samples) >= MIN_WINDOW_SAMPLES
    raw_towns = {t["id"]: t for t in latest.towns}
    rows: list[_Row] = []
    for tid, now in last.towns.items():
        first_sample = next((s for s in samples if tid in s.towns), None)
        first = first_sample.towns[tid] if first_sample else now
        window = [s for s in samples if tid in s.towns]
        delta = growth = annual = None
        if now.cap is not None and first.cap is not None and first_sample is not samples[-1]:
            delta = now.cap - first.cap
            growth = delta / first.cap if first.cap else None
            if growth is not None and enough and first_sample is samples[0]:
                annual = growth / span
        last_change = None
        for prev, cur in zip(window, window[1:]):
            if prev.towns[tid].cap != cur.towns[tid].cap:
                last_change = cur.label
        position = raw_towns.get(tid, {}).get("position")
        if isinstance(position, dict):
            position = _list(position)
        position = [float(v) for v in position[:2]] if isinstance(position, list) and len(position) >= 2 \
            and all(_num(v) is not None for v in position[:2]) else None
        lines = net.lines_by_town.get(tid, {})
        rows.append(_Row(
            id=tid, name=now.name, cap=now.cap, caps=now.caps, first_cap=first.cap, delta=delta, growth=growth,
            annual=annual, last_change=last_change, usage=now.usage, usage_first=first.usage,
            noise=now.noise, noise_first=first.noise, pollution=now.pollution, pollution_first=first.pollution,
            development=now.development, stations=len(net.stations_by_town.get(tid, ())),
            lines_all=len(lines), lines_passenger=sum(1 for p in lines.values() if p), supply=now.supply,
            position=position,
        ))
    sized = sorted((r for r in rows if r.cap is not None), key=lambda r: (-r.cap, r.name))
    total = sum(r.cap for r in sized)
    threshold = _quantile([r.cap for r in sized], LARGE_QUANTILE) if len(sized) >= 4 else None
    for i, r in enumerate(sized, 1):
        r.rank = i
        r.share = r.cap / total if total else None
        r.large = threshold is not None and r.cap >= threshold
    rows.sort(key=lambda r: (r.rank == 0, r.rank, r.name))
    return rows


def _rank_label(row: _Row) -> str:
    return f"#{row.rank}" if row.rank else "-"


def _line_names(net: _Network, tid: int, limit: int = 4) -> str:
    entries = sorted(net.lines_by_town.get(tid, {}).items(), key=lambda kv: (not kv[1], net.line_names[kv[0]]))
    shown = [f"{net.line_names[lid]} [{'P' if p else 'F'}]" for lid, p in entries[:limit]]
    extra = f" +{len(entries) - limit} more" if len(entries) > limit else ""
    return "; ".join(shown) + extra if shown else "none"


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

def _proxy_section() -> list[Any]:
    return [
        Heading(2, "What the town numbers mean"),
        Note("Capacity proxy",
             "'Size' here is capacity = residential + commercial + industrial building capacity from "
             "townBuildingSystem. It is a capacity proxy, not a head count: population is only approximated "
             "by it [INFERENCE]. Town growth in this game comes only from transport XP (mechanics M2), and new "
             "capacity arrives in small steps, so short windows show few or no changes."),
        Note("Line usage", "lineUsage is the game's town line usage. The passenger rating is double the usage "
             f"clamped to 0-1 (mechanics M2), so usage above {USAGE_CAP:.0%} adds nothing to that rating. "
             "Headroom below means the gap to that cap."),
        Note("Cargo supply / limit", "cargoSupply gives, per cargo the town demands, a supply and a limit in game "
             "units that are not verified (per-year meaning unconfirmed); the 'extra' field is not interpreted. "
             "Supply as a percentage of limit is used as a relative fulfilment measure only."),
        Note("Pollution / noise", "Units and scale are unverified. Values are compared between towns and over "
             "time only; whether a town is actually penalised (authority rating) cannot be told from these numbers."),
    ]


def _overview(rows: list[_Row], samples: list[_Sample]) -> list[Any]:
    sized = [r for r in rows if r.cap is not None]
    if not sized:
        return [Heading(2, "Overview"), Paragraph("Insufficient data: no town reports building capacities.")]
    total = sum(r.cap for r in sized)
    first_total = sum(r.first_cap for r in sized if r.first_cap is not None)
    served = [r for r in sized if r.served]
    pax = [r for r in sized if r.lines_passenger]
    served_share = sum(r.cap for r in served) / total if total else None
    pax_share = sum(r.cap for r in pax) / total if total else None
    usage_w = _weighted_usage(sized)
    growing = sum(1 for r in sized if (r.delta or 0) > 0)
    rows_out = [
        ["Towns tracked", len(rows)],
        ["Total capacity (latest)", _num_str(total)],
        ["Total capacity change over window", _signed(total - first_total) if len(samples) > 1 else "-"],
        ["Towns with growth observed in window", f"{growing} of {len(sized)}" if len(samples) > 1 else "-"],
        ["Towns with a station of ours", f"{len(served)} of {len(sized)} ({_pct(served_share)} of capacity)"],
        ["Towns with a passenger line of ours", f"{len(pax)} of {len(sized)} ({_pct(pax_share)} of capacity)"],
        ["Capacity-weighted line usage", _pct(usage_w)],
        ["Towns with development active", f"{sum(1 for r in sized if r.development)} of {len(sized)}"],
    ]
    return [Heading(2, "Overview"), Table(["Measure", "Value"], rows_out, ["left", "right"])]


def _weighted_usage(rows: list[_Row]) -> float | None:
    pairs = [(r.cap, r.usage) for r in rows if r.cap is not None and r.usage is not None]
    total = sum(c for c, _ in pairs)
    return sum(c * u for c, u in pairs) / total if total else None


def _evolution(samples: list[_Sample], picked: list[_Sample]) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Evolution")]
    if len(samples) < 2:
        return blocks + [Paragraph("Insufficient data: only one snapshot, no evolution to show yet.")]
    table_rows, totals = [], []
    base = None
    for s in picked:
        pts = list(s.towns.values())
        caps = [p.cap for p in pts if p.cap is not None]
        total = sum(caps)
        base = total if base is None else base
        weighted = _weighted_usage_points(pts)
        res = sum(p.caps[0] for p in pts if len(p.caps) >= 3)
        com = sum(p.caps[1] for p in pts if len(p.caps) >= 3)
        ind = sum(p.caps[2] for p in pts if len(p.caps) >= 3)
        table_rows.append([s.label, _num_str(total), _signed(total - base), _num_str(res), _num_str(com),
                           _num_str(ind), _pct(weighted), sum(1 for p in pts if p.development)])
        totals.append(float(total))
    blocks.append(Paragraph(
        f"{len(picked)} sample points from {len(samples)} snapshots ({picked[0].label} to {picked[-1].label}); "
        "one point per month, quarter or year depending on the span, always including the first and latest."))
    blocks.append(Chart("line", "Total town capacity (all towns)", [s.label for s in picked],
                        [("Total capacity", totals)]))
    blocks.append(Table(
        ["Sample", "Total capacity", "Change vs first", "Residential", "Commercial", "Industrial",
         "Weighted line usage", "Dev. active"], table_rows,
        ["left", "right", "right", "right", "right", "right", "right", "right"]))
    return blocks


def _weighted_usage_points(points: list[_TownPoint]) -> float | None:
    pairs = [(p.cap, p.usage) for p in points if p.cap is not None and p.usage is not None]
    total = sum(c for c, _ in pairs)
    return sum(c * u for c, u in pairs) / total if total else None


def _league(rows: list[_Row], net: _Network, samples: list[_Sample]) -> list[Any]:
    sized = [r for r in rows if r.cap is not None]
    blocks: list[Any] = [Heading(2, "Town ranking")]
    if not sized:
        return blocks + [Paragraph("Insufficient data: no capacities available.")]
    top = sized[:MAX_TABLE_ROWS]
    blocks.append(Paragraph(
        f"Largest {len(top)} of {len(sized)} towns by capacity proxy. Change columns compare the first sample "
        f"({samples[0].label}) with the latest ({samples[-1].label}); 'Growth/yr' is a linear extrapolation per "
        "calendar year and only shown when the window is long enough."))
    blocks.append(Chart("bar", "Town capacity (largest towns)", [r.name for r in top[:20]],
                        [("Capacity", [r.cap for r in top[:20]])]))
    blocks.append(Table(
        ["#", "Town", "Capacity", "Share", "Res / Com / Ind", "Change", "Growth", "Growth/yr", "Line usage",
         "Usage change", "Stations", "Lines (pax/all)"],
        [[r.rank, r.name, _num_str(r.cap), _pct(r.share),
          " / ".join(_num_str(c) for c in r.caps) if len(r.caps) >= 3 else "-", _signed(r.delta),
          _signed_pct(r.growth), _signed_pct(r.annual), _pct(r.usage),
          _signed_pct(None if r.usage is None or r.usage_first is None else r.usage - r.usage_first),
          r.stations, f"{r.lines_passenger}/{r.lines_all}"] for r in top],
        ["right", "left", "right", "right", "right", "right", "right", "right", "right", "right", "right", "right"]))
    return blocks


def _growth(rows: list[_Row], samples: list[_Sample]) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Growth and stalls")]
    span = _span_years(samples)
    if len(samples) < MIN_WINDOW_SAMPLES or span < MIN_WINDOW_YEARS:
        return blocks + [Paragraph(
            f"Insufficient data: growth needs at least {MIN_WINDOW_SAMPLES} snapshots spanning "
            f"{MIN_WINDOW_YEARS} calendar years (have {len(samples)} spanning {span:.2f}).")]
    comparable = [r for r in rows if r.delta is not None and r.growth is not None]
    risers = sorted((r for r in comparable if r.delta > 0), key=lambda r: (-r.growth, r.name))
    if risers:
        shown = risers[:10]
        blocks.append(Heading(3, "Fastest-growing towns"))
        blocks.append(Table(
            ["Town", "Capacity", "Change", "Growth", "Growth/yr", "Last change seen", "Line usage", "Stations"],
            [[r.name, _num_str(r.cap), _signed(r.delta), _signed_pct(r.growth), _signed_pct(r.annual),
              r.last_change or "-", _pct(r.usage), r.stations] for r in shown],
            ["left", "right", "right", "right", "right", "left", "right", "right"]))
        if len(risers) > len(shown):
            blocks.append(Paragraph(f"{len(risers) - len(shown)} further growing towns omitted."))
        median = statistics.median(r.growth for r in comparable)
        blocks.append(Note("Observation", f"{len(risers)} of {len(comparable)} towns gained capacity in the window; "
                           f"median growth is {_signed_pct(median)}."))
    else:
        blocks.append(Paragraph("No town gained capacity in the window."))
    stalled = [r for r in comparable if r.delta <= 0 and r.cap is not None]
    stalled.sort(key=lambda r: (-r.cap, r.name))
    blocks.append(Heading(3, "Stalled towns (no net capacity gain in the window)"))
    if not stalled:
        blocks.append(Paragraph("No stalled towns in the window."))
        return blocks
    shown = stalled[:MAX_TABLE_ROWS]
    blocks.append(Table(
        ["Town", "Capacity", "Rank", "Stations", "Pax lines", "Line usage", "Cargo demands met", "Noise", "Situation"],
        [[r.name, _num_str(r.cap), _rank_label(r), r.stations, r.lines_passenger, _pct(r.usage),
          _demands_met(r), _num_str(r.noise), _stall_reading(r)] for r in shown],
        ["left", "right", "right", "right", "right", "right", "right", "right", "left"]))
    if len(stalled) > len(shown):
        blocks.append(Paragraph(f"{len(stalled) - len(shown)} smaller stalled towns omitted."))
    served_stalled = [r for r in stalled if r.served]
    unserved_stalled = [r for r in stalled if not r.served]
    blocks.append(Note(
        "Observation", f"{len(stalled)} towns did not grow ({len(unserved_stalled)} have none of our stations, "
        f"{len(served_stalled)} do). A window of {span:.2f} calendar years is short; capacity arrives in steps, "
        "so a stall here is not proof of a lasting problem."))
    big = [r for r in served_stalled if r.large]
    if big:
        names = ", ".join(r.name for r in big[:5])
        blocks.append(Note(
            "Suggestion", f"Look first at large towns we already serve that did not grow ({names}): inspect their "
            "line usage, which cargo demands are unmet (see the cargo section) and the authority ratings shown in "
            "the town window in-game; the snapshot does not collect the six ratings directly."))
    return blocks


def _demands_met(row: _Row) -> str:
    if not row.supply:
        return "-"
    met = sum(1 for sup, _ in row.supply.values() if sup > 0)
    return f"{met}/{len(row.supply)}"


def _stall_reading(row: _Row) -> str:
    if not row.served:
        return "No station of ours; growth comes only from transport [documented]"
    if not row.lines_passenger:
        return "Freight stations only"
    if row.usage is not None and row.usage >= USAGE_CAP - 0.02:
        return "Usage at passenger cap; other XP sources or ratings limit it [INFERENCE]"
    return "Served but usage below cap"


def _coverage(rows: list[_Row], net: _Network) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Coverage by our lines")]
    sized = [r for r in rows if r.cap is not None]
    if not net.station_town:
        return blocks + [Paragraph("Insufficient data: the snapshot lists no stations with a town assignment, so "
                                   "coverage by our lines cannot be verified.")]
    gaps = [r for r in sized if not r.lines_passenger]
    gaps.sort(key=lambda r: (-r.cap, r.name))
    blocks.append(Note(
        "Method", "A town counts as touched by a line when a stop's station group is assigned to that town in "
        "stations[].town (verifiable from the snapshot). stations[] only lists station groups our lines use. A "
        "station assigned to town A may physically cover part of town B, and catchment radius is not collected, so "
        "a town can be reached without being listed [unverifiable]. [P] = line has passenger capacity in its "
        "vehicles, [F] = freight only."))
    if not gaps:
        blocks.append(Paragraph("Every town has at least one passenger line touching it."))
    else:
        shown = gaps[:MAX_TABLE_ROWS]
        blocks.append(Heading(3, "Towns without a passenger line"))
        blocks.append(Table(
            ["Town", "Capacity", "Rank", "Status", "Stations", "Freight lines", "Line usage", "Dev. active"],
            [[r.name, _num_str(r.cap), _rank_label(r), "No station of ours" if not r.served else "Freight lines only",
              r.stations, r.lines_all - r.lines_passenger, _pct(r.usage),
              "-" if r.development is None else ("yes" if r.development else "no")] for r in shown],
            ["left", "right", "right", "left", "right", "right", "right", "right"]))
        if len(gaps) > len(shown):
            blocks.append(Paragraph(f"{len(gaps) - len(shown)} smaller towns omitted."))
        unserved = [r for r in gaps if not r.served]
        share = sum(r.cap for r in unserved) / sum(r.cap for r in sized) if sized and unserved else 0.0
        blocks.append(Note(
            "Observation", f"{len(unserved)} of {len(sized)} towns have no station of ours ({_pct(share)} of "
            f"capacity); {len(gaps) - len(unserved)} more are touched only by freight lines."))
    zero = [r for r in sized if r.lines_passenger and (r.usage or 0) == 0]
    if zero:
        blocks.append(Note(
            "Observation", "Passenger lines touch these towns but line usage is 0: "
            + ", ".join(f"{r.name} ({_num_str(r.cap)})" for r in sorted(zero, key=lambda r: -r.cap)[:8])
            + ". Possible reasons: the line was just built, or the station is far from the town's houses "
            "[INFERENCE; catchment is not collected]."))
    top = [r for r in sized if r.served][:12]
    if top:
        blocks.append(Heading(3, "Lines touching the largest served towns"))
        blocks.append(Table(
            ["Town", "Rank", "Stations", "Pax lines", "Freight lines", "Examples ([P] passenger, [F] freight)"],
            [[r.name, _rank_label(r), r.stations, r.lines_passenger, r.lines_all - r.lines_passenger,
              _line_names(net, r.id, 3)] for r in top],
            ["left", "right", "right", "right", "right", "left"]))
    return blocks


def _usage_gap(rows: list[_Row]) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Large towns with low line usage")]
    sized = [r for r in rows if r.cap is not None and r.usage is not None]
    if len([r for r in sized]) < 4:
        return blocks + [Paragraph("Insufficient data: too few towns with capacity and line usage.")]
    low = [r for r in sized if r.large and (r.headroom or 0) > 0.02]
    low.sort(key=lambda r: (-(r.cap * (r.headroom or 0)), r.name))
    if not low:
        return blocks + [Paragraph(f"No large town (upper {100 - int(LARGE_QUANTILE * 100)}% by capacity) is more "
                                   f"than 2 points below the {USAGE_CAP:.0%} usage cap.")]
    shown = low[:MAX_TABLE_ROWS]
    blocks.append(Paragraph(
        f"Large = upper {100 - int(LARGE_QUANTILE * 100)}% of towns by capacity. Ranked by capacity x headroom "
        f"(gap to the {USAGE_CAP:.0%} usage cap)."))
    blocks.append(Table(
        ["Town", "Capacity", "Residential", "Line usage", "Headroom", "Usage change", "Stations", "Pax lines"],
        [[r.name, _num_str(r.cap), _num_str(r.caps[0]) if r.caps else "-", _pct(r.usage), _pct(r.headroom),
          _signed_pct(None if r.usage_first is None else r.usage - r.usage_first), r.stations, r.lines_passenger]
         for r in shown],
        ["left", "right", "right", "right", "right", "right", "right", "right"]))
    if len(low) > len(shown):
        blocks.append(Paragraph(f"{len(low) - len(shown)} further towns omitted."))
    top = low[0]
    blocks.append(Note("Observation", f"{top.name} has the largest gap: capacity {_num_str(top.cap)}, usage "
                       f"{_pct(top.usage)} against the {USAGE_CAP:.0%} cap, {top.lines_passenger} passenger line(s)."))
    blocks.append(Note(
        "Suggestion", "For these towns consider (manually) more or better-placed passenger stops, higher "
        "frequency, or a connection to another sizeable town; passenger trips to farther towns earn more XP "
        "than same-town trips (5/10/20 XP tiers, mechanics M2). Check the town's existing stops first: this "
        "report cannot see station position relative to the houses."))
    return blocks


def _cargo_demand(rows: list[_Row], latest: Snapshot) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Cargo demand: supply vs limit")]
    with_supply = [r for r in rows if r.supply]
    if not with_supply:
        return blocks + [Paragraph("Insufficient data: towns report no cargoSupply entries.")]
    producers: dict[int, list[float]] = {}  # cargo -> [count, unshipped/yr, produced/yr]
    for ind in latest.industries:
        for out in _list(ind.get("outputs")):
            cargo = out.get("cargo")
            if isinstance(cargo, int):
                p = producers.setdefault(cargo, [0, 0.0, 0.0])
                produced = _num(out.get("producedYear")) or 0.0
                p[0] += 1
                p[1] += max(0.0, produced - (_num(out.get("shippedYear")) or 0.0))
                p[2] += produced
    per_cargo: dict[int, dict[str, Any]] = {}
    for r in with_supply:
        for cargo, (sup, limit) in r.supply.items():
            c = per_cargo.setdefault(cargo, {"towns": 0, "zero": 0, "supply": 0.0, "limit": 0.0})
            c["towns"] += 1
            c["zero"] += 1 if sup <= 0 else 0
            c["supply"] += sup
            c["limit"] += limit
    ranked = sorted(per_cargo.items(), key=lambda kv: (-(kv[1]["limit"] - kv[1]["supply"]), str(latest.cargo(kv[0]))))
    shown = ranked[:MAX_TABLE_ROWS]
    blocks.append(Heading(3, "By cargo"))
    blocks.append(Table(
        ["Cargo", "Towns demanding", "Towns with zero supply", "Supply", "Limit", "Supply / limit",
         "Producers on map", "Produced / yr", "Unshipped / yr"],
        [[latest.cargo(cargo) or f"Cargo #{cargo}", c["towns"], c["zero"], _num_str(c["supply"]),
          _num_str(c["limit"]), _pct(c["supply"] / c["limit"] if c["limit"] else None),
          int(producers.get(cargo, [0, 0.0, 0.0])[0]), _num_str(producers.get(cargo, [0, 0.0, 0.0])[2]),
          _num_str(producers.get(cargo, [0, 0.0, 0.0])[1])]
         for cargo, c in shown],
        ["left", "right", "right", "right", "right", "right", "right", "right", "right"]))
    if len(ranked) > len(shown):
        blocks.append(Paragraph(f"{len(ranked) - len(shown)} further cargos omitted."))

    served = [r for r in with_supply if r.served]
    served.sort(key=lambda r: (-sum(max(0.0, lim - sup) for sup, lim in r.supply.values()), r.name))
    blocks.append(Heading(3, "Unmet demand in towns where we already have a station"))
    if not served:
        blocks.append(Paragraph("No town with cargo demand has a station of ours."))
    else:
        shown_t = served[:MAX_TABLE_ROWS]
        rows_out = []
        for r in shown_t:
            sup = sum(s for s, _ in r.supply.values())
            lim = sum(limit for _, limit in r.supply.values())
            cargo, (_, cl) = max(r.supply.items(), key=lambda kv: kv[1][1] - kv[1][0])
            rows_out.append([r.name, _rank_label(r), _demands_met(r), _num_str(sup), _num_str(lim),
                             _pct(sup / lim if lim else None),
                             f"{latest.cargo(cargo) or cargo} ({_num_str(max(0.0, cl - r.supply[cargo][0]))})"])
        blocks.append(Table(
            ["Town", "Rank", "Demands met", "Supply", "Limit", "Supply / limit", "Largest unmet (cargo, gap)"],
            rows_out, ["left", "right", "right", "right", "right", "right", "left"]))
        if len(served) > len(shown_t):
            blocks.append(Paragraph(f"{len(served) - len(shown_t)} further served towns omitted."))
    zero_all = [r for r in with_supply if all(s <= 0 for s, _ in r.supply.values())]
    idle = [latest.cargo(c) or str(c) for c, _ in ranked if per_cargo[c]["supply"] <= 0
            and producers.get(c, [0, 0.0, 0.0])[2] <= 0]
    top = ranked[0]
    blocks.append(Note(
        "Observation", f"{len(zero_all)} of {len(with_supply)} towns receive none of the cargo they demand. "
        f"Largest overall gap: {latest.cargo(top[0]) or top[0]} (supply {_num_str(top[1]['supply'])} against limit "
        f"{_num_str(top[1]['limit'])}, {top[1]['zero']} of {top[1]['towns']} towns at zero)."))
    if idle:
        blocks.append(Note(
            "Observation", f"No industry currently produces {', '.join(idle[:6])}"
            f"{' and others' if len(idle) > 6 else ''} (produced per year is 0 in every output), and towns get none "
            "of it: these demands cannot be met until an upstream industry chain is producing them."))
    blocks.append(Note(
        "Inference", "Towns only add cargo demands after receiving some cargo, and delivered cargo gives growth XP "
        "(mechanics M2); an unmet demand is therefore both a possible freight market and a growth lever. Whether "
        "'limit' is a hard cap or annual demand is unverified. Producers/unshipped figures come from industries, "
        "not from where the cargo could physically be routed; towns have no coordinates in snapshots, so "
        "distances cannot be checked."))
    return blocks


def _hotspots(rows: list[_Row]) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Pollution and noise hot spots")]
    pol = [r for r in rows if r.pollution is not None]
    noi = [r for r in rows if r.noise is not None]
    if not pol and not noi:
        return blocks + [Paragraph("Insufficient data: no pollution or noise values in the snapshots.")]
    blocks.append(Paragraph("Ranked by value; units and thresholds are unverified, so only relative comparison and "
                            "change over the window are shown. 'Per 100 capacity' controls for town size."))
    for title, items, attr in (("Pollution", pol, "pollution"), ("Noise", noi, "noise")):
        if not items:
            continue
        ranked = sorted(items, key=lambda r: (-getattr(r, attr), r.name))[:8]
        blocks.append(Heading(3, f"Highest {title.lower()}"))
        first_attr = f"{attr}_first"
        blocks.append(Table(
            ["Town", title, "Change", "Per 100 capacity", "Capacity", "Line usage", "Stations"],
            [[r.name, _num_str(getattr(r, attr), 1 if attr == "noise" else 0),
              _signed(None if getattr(r, first_attr) is None else getattr(r, attr) - getattr(r, first_attr),
                      1 if attr == "noise" else 0),
              _num_str(getattr(r, attr) / r.cap * 100 if r.cap else None, 1), _num_str(r.cap),
              _pct(r.usage), r.stations] for r in ranked],
            ["left", "right", "right", "right", "right", "right", "right"]))
    if len(pol) >= 4:
        ordered = sorted(pol, key=lambda r: (-r.pollution, r.name))
        median = statistics.median(r.pollution for r in pol)
        worst = max((r for r in pol if r.cap), key=lambda r: (r.pollution / r.cap, r.name), default=None)
        text = (f"{ordered[0].name} has the highest pollution ({_num_str(ordered[0].pollution)}), "
                f"{ordered[0].pollution / ordered[1].pollution:.1f}x the next town and "
                f"{ordered[0].pollution / median:.0f}x the median town." if median > 0 and ordered[1].pollution > 0
                else f"{ordered[0].name} has the highest pollution ({_num_str(ordered[0].pollution)}).")
        if worst is not None and worst is not ordered[0]:
            text += (f" Relative to size the worst is {worst.name} "
                     f"({_num_str(worst.pollution)} for capacity {_num_str(worst.cap)}).")
        blocks.append(Note("Observation", text))
    blocks.append(Note(
        "Inference", "Noise and pollution are two of the six authority ratings whose minimum scales growth XP "
        "(mechanics M2). The report cannot tell whether a hot spot is actually the limiting rating; compare with "
        "the in-game town ratings before acting. Industry and road traffic near a town, rather than our lines, "
        "may be the source."))
    return blocks


def _distance_km(a: _Row, b: _Row) -> float | None:
    if a.position is None or b.position is None:
        return None
    return math.hypot(a.position[0] - b.position[0], a.position[1] - b.position[1]) / 1000.0


def _pairs(rows: list[_Row], net: _Network) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Large towns without a direct passenger line between them")]
    pool = [r for r in rows if r.cap is not None][:PAIR_POOL]
    if len(pool) < 2:
        return blocks + [Paragraph("Insufficient data: fewer than two towns with capacities.")]
    candidates = []
    for i, a in enumerate(pool):
        for b in pool[i + 1:]:
            if frozenset((a.id, b.id)) in net.passenger_edges:
                continue
            comp_a, comp_b = net.component.get(a.id), net.component.get(b.id)
            if comp_a is not None and comp_a == comp_b:
                status = "Indirect (shared passenger network)"
                order = 1
            else:
                status = "No passenger link"
                order = 0
            candidates.append((order, -(a.cap * b.cap), a, b, status))
    candidates.sort(key=lambda c: (c[0], c[1], c[2].name, c[3].name))
    linked = (len(pool) * (len(pool) - 1)) // 2 - len(candidates)
    have_distance = any(_distance_km(c[2], c[3]) is not None for c in candidates)
    isolated = sum(1 for c in candidates if c[0] == 0)
    blocks.append(Paragraph(
        f"Pairs among the {len(pool)} largest towns. {linked} of those pairs already share a passenger line "
        f"(any two towns on the same passenger line count as linked); {len(candidates)} do not, of which "
        f"{isolated} are in separate passenger networks (no transfer route at all) and "
        f"{len(candidates) - isolated} could be reached with a transfer."))
    if not candidates:
        return blocks + [Paragraph("Every pair of large towns already shares a passenger line.")]
    shown = candidates[:MAX_TABLE_ROWS]
    blocks.append(Table(
        ["Town A", "Town B", "Capacity A", "Capacity B", "Status", "Straight-line distance (km, estimate)"],
        [[a.name, b.name, _num_str(a.cap), _num_str(b.cap), status,
          _num_str(_distance_km(a, b), 1) if _distance_km(a, b) is not None else "unknown"]
         for _, _, a, b, status in shown],
        ["left", "left", "right", "right", "left", "right"]))
    if len(candidates) > len(shown):
        blocks.append(Paragraph(f"{len(candidates) - len(shown)} further pairs omitted."))
    if have_distance:
        blocks.append(Note("Estimate", "Distances are straight-line from town positions (metres assumed, as for "
                           "industries); real road, rail or air routes will be longer and terrain may block them."))
    else:
        blocks.append(Note(
            "Unverifiable", "Snapshots contain no town coordinates, so distances between towns cannot be computed "
            "and candidate pairs are ranked by combined capacity only. Pair viability (and passenger XP tier, "
            "which depends on distance) must be judged in-game."))
    blocks.append(Note(
        "Suggestion", "Pairs in separate networks are the cleanest candidates for a new manually-built passenger "
        "connection; transfer-only pairs are second choice (a direct line would shorten the trip). Confirm "
        "distance and terrain in-game first."))
    return blocks


def _key_findings(rows: list[_Row], samples: list[_Sample], net: _Network, latest: Snapshot) -> list[Any]:
    sized = [r for r in rows if r.cap is not None]
    if not sized:
        return []
    notes: list[Any] = []
    unserved = [r for r in sized if not r.served]
    if unserved:
        big = unserved[0]
        notes.append(Note(
            "Observation", f"{len(unserved)} of {len(sized)} towns have no station of ours; the largest is "
            f"{big.name} (capacity {_num_str(big.cap)}, rank {_rank_label(big)})."))
    low = sorted((r for r in sized if r.large and r.usage is not None and (r.headroom or 0) > 0.02),
                 key=lambda r: -(r.cap * (r.headroom or 0)))
    if low:
        r = low[0]
        notes.append(Note(
            "Observation", f"{r.name} is a large town (capacity {_num_str(r.cap)}, rank {_rank_label(r)}) with line "
            f"usage {_pct(r.usage)} against the {USAGE_CAP:.0%} cap, {r.stations} station(s) of ours and "
            f"{r.lines_passenger} passenger line(s)."))
    span = _span_years(samples)
    if span >= MIN_WINDOW_YEARS and len(samples) >= MIN_WINDOW_SAMPLES:
        stalled = [r for r in sized if r.large and r.served and r.delta is not None and r.delta <= 0]
        if stalled:
            r = stalled[0]
            notes.append(Note(
                "Observation", f"{r.name} (rank {_rank_label(r)}, {r.stations} stations, usage {_pct(r.usage)}) gained "
                f"no capacity in {span:.2f} calendar years while {len([x for x in sized if (x.delta or 0) > 0])} of "
                f"{len(sized)} towns did."))
        growing = [r for r in sized if r.growth is not None and r.growth > 0]
        if growing:
            r = max(growing, key=lambda r: (r.growth, r.name))
            notes.append(Note("Observation", f"Fastest relative growth: {r.name} {_signed_pct(r.growth)} "
                              f"({_signed(r.delta)} capacity), line usage {_pct(r.usage)}."))
    starved = [r for r in sized if r.served and r.supply and all(s <= 0 for s, _ in r.supply.values())]
    if starved:
        r = starved[0]
        gap = {c: lim for c, (_, lim) in r.supply.items()}
        top = sorted(gap, key=lambda c: -gap[c])[:3]
        notes.append(Note(
            "Observation", f"{r.name} (rank {_rank_label(r)}) has our stations but receives none of its "
            f"{len(r.supply)} demanded cargos ({', '.join(latest.cargo(c) or str(c) for c in top)}); "
            f"{len(starved)} served town(s) get no cargo at all."))
    if not notes:
        notes.append(Paragraph("No standout findings yet."))
    return [Heading(2, "Key findings")] + notes


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def build(store: Store) -> ReportDocument:
    latest = store.latest()
    if latest is None:
        raise ValueError("No snapshot found. Load a save with the bridge enabled and run tf3c refresh.")
    samples = _load_history(store, latest)
    if not samples:
        samples = [_sample_from_raw(latest.raw)]
    net = _build_network(latest)
    rows = _build_rows(latest, samples, net)
    picked = _pick_samples(samples)

    header = _base_header(latest, len(samples))
    span = _span_years(samples)
    days = _calendar_days(samples)
    window = f"{samples[0].label} to {samples[-1].label}" if len(samples) > 1 else samples[0].label
    detail = f"{span:.2f} calendar years" + (f", {days} days by meta.date" if days is not None else "")
    header.insert(2, ("Town Sample Window", f"{window} ({detail})" if len(samples) > 1 else window))
    header.append(("Town Data Notes", "Capacity sum is a population proxy; stations[] covers only station groups our "
                   "lines use; towns carry no coordinates."))

    blocks: list[Any] = []
    if not rows:
        blocks.append(Paragraph("Insufficient data: the latest snapshot lists no towns."))
    else:
        blocks += _key_findings(rows, samples, net, latest)
        blocks += _proxy_section()
        blocks += _overview(rows, samples)
        blocks += _evolution(samples, picked)
        blocks += _league(rows, net, samples)
        blocks += _growth(rows, samples)
        blocks += _coverage(rows, net)
        blocks += _usage_gap(rows)
        blocks += _cargo_demand(rows, latest)
        blocks += _hotspots(rows)
        blocks += _pairs(rows, net)
    return ReportDocument("towns", "Towns Report", header, blocks)
