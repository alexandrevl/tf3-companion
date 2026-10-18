"""Industries evolution report: how production, service, levels, closures and chains changed.

Complements the `cargo` report (unshipped production + nearest consumers) by focusing on
change over snapshots and comparison between industries, cargos and types.

Honesty rules applied here:
- producedYear/shippedYear/consumedYear are rolling annual figures per snapshot. They are
  compared snapshot to snapshot, never summed across snapshots.
- Service ratio = shipped / produced; ratios above 100% can reflect stock draw-down.
- Calendar time comes from meta.date, not from meta.yearDuration (which is not a calendar year).
- Station-to-industry links are inferred from an exact name match; the snapshot has no
  station position or catchment data.
"""

from __future__ import annotations

import datetime
import statistics
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from . import analysis
from .reports import Chart, Heading, Note, Paragraph, ReportDocument, Table, _fmt_pct
from .snapshot import Snapshot
from .store import Store


MAX_EVOLUTION_ROWS = 14
EVENT_CAP = 30
BUCKET_DAYS = (7, 14, 30, 91, 182, 365, 730, 1826, 3652)


# ---------------------------------------------------------------------------
# Per-snapshot flattening
# ---------------------------------------------------------------------------

@dataclass
class Ind:
    id: int
    name: str
    type: str
    label: str
    level: int | None
    max_level: int | None
    rating: float | None
    closure: int
    flagged: bool
    unknown_flows: bool = False
    outs: dict[int, tuple[float, float, float]] = field(default_factory=dict)  # cargo -> (produced, max, shipped)
    ins: dict[int, tuple[float, float]] = field(default_factory=dict)  # cargo -> (consumed, max)

    @property
    def primary(self) -> bool:
        return not self.ins

    @property
    def produced(self) -> float:
        return sum(o[0] for o in self.outs.values())

    @property
    def shipped(self) -> float:
        return sum(o[2] for o in self.outs.values())

    @property
    def shipped_eff(self) -> float:
        return self.shipped

    @property
    def capacity(self) -> float:
        return sum(o[1] for o in self.outs.values())

    @property
    def producing(self) -> bool:
        return self.produced > 0

    @property
    def served(self) -> bool:
        return self.shipped > 0

    @property
    def idle(self) -> bool:
        return bool(self.outs) and self.capacity > 0 and self.produced == 0

    @property
    def has_levels(self) -> bool:
        return bool(self.max_level)

    @property
    def consumption_capacity(self) -> float:
        return sum(i[1] for i in self.ins.values())

    @property
    def consumed(self) -> float:
        return sum(i[0] for i in self.ins.values())


def _num(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0


def _label(type_path: str | None) -> str:
    if not type_path:
        return "unknown"
    tail = str(type_path).rstrip("/").split("/")[-1]
    if tail.endswith(".con"):
        tail = tail[:-4]
    return tail.replace("_", " ") or "unknown"


def _ratio(shipped_eff: float, produced: float) -> float | None:
    return shipped_eff / produced if produced > 0 else None


def _flatten(snap: Snapshot) -> dict[int, Ind]:
    closing = set(snap.problems.get("closingIndustries") or [])
    out: dict[int, Ind] = {}
    for raw in snap.industries:
        iid = raw["id"]
        closure = int(_num(raw.get("closureTimeStamp")))
        ind = Ind(
            id=iid,
            name=raw.get("name") or f"Industry #{iid}",
            type=raw.get("type") or "",
            label=_label(raw.get("type")),
            level=raw.get("level") if isinstance(raw.get("level"), int) else None,
            max_level=raw.get("maxLevel") if isinstance(raw.get("maxLevel"), int) else None,
            rating=raw.get("productionRating") if isinstance(raw.get("productionRating"), (int, float)) else None,
            closure=closure,
            flagged=bool(closure) or iid in closing,
        )
        for flow in raw.get("outputs") or []:
            if flow.get("cargo") is None:
                continue
            values = [flow.get(k) for k in ("producedYear", "maxProductionYear", "shippedYear")]
            if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
                ind.unknown_flows = True
                continue
            ind.outs[flow["cargo"]] = tuple(float(v) for v in values)
        for flow in raw.get("inputs") or []:
            if flow.get("cargo") is None:
                continue
            values = [flow.get(k) for k in ("consumedYear", "maxConsumptionYear")]
            if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
                ind.unknown_flows = True
                continue
            ind.ins[flow["cargo"]] = tuple(float(v) for v in values)
        if "outputs" not in raw or "inputs" not in raw:
            ind.unknown_flows = True
        if ind.unknown_flows:
            ind.outs.clear()
            ind.ins.clear()
        out[iid] = ind
    return out


@dataclass
class StockRow:
    owner: int
    stock_id: Any
    role: str  # output | input | warehouse
    fill: float
    count: float
    capacity: float
    cargos: list[int]


def _stocks(snap: Snapshot, inds: dict[int, Ind]) -> dict[tuple[int, Any], StockRow] | None:
    """Stock fill keyed by (owner, stockId); None when the snapshot carries no stock data."""
    stocks = snap.stocks
    if not stocks:
        return None
    out: dict[tuple[int, Any], StockRow] = {}
    for st in stocks:
        cap, cnt = st.get("capacity"), st.get("count")
        if not isinstance(cap, (int, float)) or not isinstance(cnt, (int, float)) or cap <= 0:
            continue
        cargos = [c for c in st.get("cargos") or [] if isinstance(c, int)]
        owner = st.get("owner")
        if st.get("kind") == "warehouse":
            role = "warehouse"
        elif st.get("kind") == "industry" and owner in inds:
            ind = inds[owner]
            if set(cargos) & set(ind.outs):
                role = "output"
            elif set(cargos) & set(ind.ins):
                role = "input"
            else:
                continue
        else:
            continue
        out[(owner, st.get("stockId"))] = StockRow(owner, st.get("stockId"), role, cnt / cap, cnt, cap, cargos)
    return out


@dataclass
class Sample:
    snap: Snapshot
    inds: dict[int, Ind]
    stocks: dict[tuple[int, Any], StockRow] | None
    day: float

    @property
    def label(self) -> str:
        return self.snap.date_label


def _day(snap: Snapshot) -> float:
    d = snap.date
    if d:
        try:
            return float(datetime.date(d["year"], d["month"], d["day"]).toordinal())
        except (KeyError, TypeError, ValueError):
            pass
    yd = snap.year_duration
    return snap.game_time / yd * 365.25 if yd else float(snap.game_time)


def _sample_of(snap: Snapshot) -> Sample:
    inds = _flatten(snap)
    return Sample(snap, inds, _stocks(snap, inds), _day(snap))


def _ticks_per_day(first: Sample, last: Sample) -> float | None:
    """Game ticks per calendar day, calibrated from meta.date (meta.yearDuration is not a calendar year)."""
    if not first.snap.date or not last.snap.date:
        return None
    days = last.day - first.day
    ticks = last.snap.game_time - first.snap.game_time
    return ticks / days if days >= 14 and ticks > 0 else None


def _pick_evenly(samples: Sequence[Sample]) -> list[Sample]:
    if len(samples) <= MAX_EVOLUTION_ROWS:
        return list(samples)
    first_day, last_day = samples[0].day, samples[-1].day
    chosen: list[Sample] = []
    for bucket in BUCKET_DAYS:
        buckets: dict[int, Sample] = {}
        for s in samples:
            buckets[int((s.day - first_day) // bucket)] = s  # last snapshot of each bucket
        chosen = list(buckets.values())
        if len(chosen) + 1 <= MAX_EVOLUTION_ROWS or bucket == BUCKET_DAYS[-1]:
            break
    picks = {id(samples[0]): samples[0], id(samples[-1]): samples[-1], **{id(s): s for s in chosen}}
    ordered = sorted(picks.values(), key=lambda s: s.day)
    if len(ordered) > MAX_EVOLUTION_ROWS:  # pathological spacing: thin evenly, keep both ends
        step = (len(ordered) - 1) / (MAX_EVOLUTION_ROWS - 1)
        ordered = [ordered[round(i * step)] for i in range(MAX_EVOLUTION_ROWS)]
    return ordered if last_day >= first_day else list(samples)


def _span_text(first: Sample, last: Sample) -> str:
    days = int(round(last.day - first.day))
    return f"{days} calendar days" if days < 365 else f"{days} calendar days (~{days / 365.25:.1f} years)"


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _cargo(snap: Snapshot, cargo_id: int) -> str:
    return snap.cargo(cargo_id) or f"Cargo #{cargo_id}"


def _int(value: float | None) -> int | None:
    return None if value is None else int(round(value))


def _pp(a: float | None, b: float | None) -> str:
    """Percentage-point change b - a."""
    if a is None or b is None:
        return "-"
    diff = (b - a) * 100
    return f"{'+' if diff > 0 else ''}{diff:.1f} pp"


def _arrow(a: Any, b: Any, fmt: Callable[[Any], str] = lambda v: "-" if v is None else f"{v:,}") -> str:
    return f"{fmt(a)} → {fmt(b)}"


def _signed(v: float | int | None) -> str:
    if v is None:
        return "-"
    n = int(round(v))
    return f"{'+' if n > 0 else ''}{n:,}"


def _cap(rows: list[list[Any]], limit: int) -> tuple[list[list[Any]], int]:
    return rows[:limit], max(0, len(rows) - limit)


def _omitted(n: int, noun: str = "rows") -> list[Any]:
    return [Note("Omitted", f"{n} more {noun} not shown.")] if n > 0 else []


def _stats(inds: Sequence[Ind]) -> dict[str, Any]:
    total = len(inds)
    inds = [i for i in inds if not i.unknown_flows]
    produced = sum(i.produced for i in inds)
    shipped_eff = sum(i.shipped_eff for i in inds)
    producing = [i for i in inds if i.producing]
    return {
        "n": total,
        "producing": len(producing),
        "idle": sum(1 for i in inds if i.idle),
        "served": sum(1 for i in inds if i.served),
        "produced": produced,
        "shipped": sum(i.shipped for i in inds),
        "shipped_eff": shipped_eff,
        "ratio": _ratio(shipped_eff, produced),
        "level": sum(i.level or 0 for i in inds if i.has_levels),
        "max_level": sum(i.max_level or 0 for i in inds if i.has_levels),
        "flagged": sum(1 for i in inds if i.flagged),
    }


def _pct_text(ratio: float) -> str:
    return f"{ratio * 100:g}%"


def _full_outputs(sample: Sample, full: float) -> int | None:
    if sample.stocks is None:
        return None
    return sum(1 for s in sample.stocks.values() if s.role == "output" and s.fill >= full)


# ---------------------------------------------------------------------------
# Events across consecutive snapshots
# ---------------------------------------------------------------------------

def _events(samples: Sequence[Sample], tpd: float | None) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    first = samples[0]
    for ind in first.inds.values():
        if ind.flagged:
            events.append({"day": first.day, "date": first.label, "event": "Closure already scheduled at first sample",
                           "ind": ind, "detail": _closure_text(ind, first, tpd), "order": 4})
    for prev, cur in zip(samples, samples[1:]):
        for iid, ind in cur.inds.items():
            if iid not in prev.inds:
                events.append({"day": cur.day, "date": cur.label, "event": "New industry", "ind": ind, "order": 1,
                               "detail": f"{ind.label}; level {ind.level}/{ind.max_level}; produces "
                                         f"{_fmt_amount(ind.produced)}/yr at first sight"})
                continue
            old = prev.inds[iid]
            if ind.flagged and not old.flagged:
                events.append({"day": cur.day, "date": cur.label, "event": "Closure scheduled", "ind": ind, "order": 3,
                               "detail": _closure_text(ind, cur, tpd)})
            elif old.flagged and not ind.flagged:
                events.append({"day": cur.day, "date": cur.label, "event": "Closure cancelled", "ind": ind, "order": 3,
                               "detail": f"produced {_fmt_amount(ind.produced)}/yr, shipped {_fmt_amount(ind.shipped)}/yr now"})
        for iid, old in prev.inds.items():
            if iid in cur.inds:
                continue
            if old.closure and old.closure <= cur.snap.game_time:
                kind, detail = "Closed (as scheduled)", f"flagged for closure; last seen {prev.label}"
            elif old.flagged:
                kind, detail = "Closed (flagged)", f"flagged for closure; last seen {prev.label}"
            else:
                kind, detail = "Disappeared (never seen flagged)", f"last seen {prev.label}"
            events.append({"day": cur.day, "date": cur.label, "event": kind, "ind": old, "order": 2, "detail": detail})
    events.sort(key=lambda e: (e["day"], e["order"], e["ind"].name))
    return events


def _fmt_amount(v: float) -> str:
    return f"{int(round(v)):,}"


def _remaining(ts: int, now_ticks: int, tpd: float | None) -> str:
    if not ts:
        return "-"
    if ts <= now_ticks:
        return "due now / overdue"
    if not tpd:
        return "n/a (no calendar calibration)"
    days = (ts - now_ticks) / tpd
    return f"~{days:.0f} days"


def _closure_text(ind: Ind, sample: Sample, tpd: float | None) -> str:
    if ind.closure:
        return f"closes in {_remaining(ind.closure, sample.snap.game_time, tpd)}"
    return "flagged in problems.closingIndustries without a timestamp"


# ---------------------------------------------------------------------------
# Station <-> industry links (name match, inference)
# ---------------------------------------------------------------------------

def _line_cargo_offset(snap: Snapshot) -> int:
    """lines[].capacity[].cargo is cargoTypeId + 1 in current mod output (Lua 1-based key).

    If the passenger id 0 ever appears with capacity, the bridge is emitting real ids.
    """
    for line in snap.lines:
        for c in line.get("capacity") or []:
            if c.get("cargo") == 0 and _num(c.get("capacity")) > 0:
                return 0
    return 1


def _line_cargos(line: dict[str, Any], offset: int) -> set[int]:
    return {int(c["cargo"]) - offset for c in line.get("capacity") or []
            if isinstance(c.get("cargo"), int) and _num(c.get("capacity")) > 0}


def _links(sample: Sample) -> dict[int, list[dict[str, Any]]]:
    snap = sample.snap
    offset = _line_cargo_offset(snap)
    by_name: dict[str, list[Ind]] = {}
    for ind in sample.inds.values():
        by_name.setdefault(ind.name.strip(), []).append(ind)
    lines = snap.lines_by_id
    result: dict[int, list[dict[str, Any]]] = {}
    for station in snap.stations:
        name = (station.get("name") or "").strip()
        matches = by_name.get(name)
        if not matches or len(matches) != 1:  # ambiguous names are never linked
            continue
        ind = matches[0]
        line_ids = set(station.get("lines") or [])
        line_ids |= {ln["id"] for ln in snap.lines
                     if any(stop.get("stationGroup") == station.get("id") for stop in ln.get("stops") or [])}
        linked = [lines[lid] for lid in sorted(line_ids) if lid in lines]
        if not linked:
            continue
        wanted_out, wanted_in = set(ind.outs), set(ind.ins)
        entry = {"station": name, "lines": [], "ind": ind}
        for ln in linked:
            carried = _line_cargos(ln, offset)
            entry["lines"].append({
                "name": ln.get("name") or f"Line #{ln['id']}",
                "ship": sorted(carried & wanted_out),
                "deliver": sorted(carried & wanted_in),
            })
        result.setdefault(ind.id, []).append(entry)
    return result


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

def _section_summary(first: Sample, last: Sample, common: list[int], events: list[dict[str, Any]], full: float) -> list[Any]:
    f_all, l_all = list(first.inds.values()), list(last.inds.values())
    f_c, l_c = [first.inds[i] for i in common], [last.inds[i] for i in common]
    fa, la, fc, lc = _stats(f_all), _stats(l_all), _stats(f_c), _stats(l_c)
    new_ids = [i for i in last.inds if i not in first.inds]
    gone_ids = [i for i in first.inds if i not in last.inds]
    level_ups = sum(1 for i in common if (last.inds[i].level or 0) > (first.inds[i].level or 0))
    level_downs = sum(1 for i in common if (last.inds[i].level or 0) < (first.inds[i].level or 0))
    ff, lf = _full_outputs(first, full), _full_outputs(last, full)

    def row(metric: str, a: Any, b: Any, change: str | None = None) -> list[Any]:
        return [metric, "-" if a is None else a, "-" if b is None else b,
                change if change is not None else (_signed(b - a) if isinstance(a, (int, float)) and isinstance(b, (int, float)) else "-")]

    rows = [
        row("Industries in snapshot (all)", fa["n"], la["n"]),
        row(f"Industries present at both ends (comparison set)", len(common), len(common), "0"),
        row("Industries producing (comparison set)", fc["producing"], lc["producing"]),
        row("Idle industries: capacity but zero output (comparison set)", fc["idle"], lc["idle"]),
        row("Production, items/yr (comparison set)", _int(fc["produced"]), _int(lc["produced"])),
        row("Shipped, items/yr (comparison set)", _int(fc["shipped"]), _int(lc["shipped"])),
        [("Service ratio (comparison set)"), _fmt_pct(fc["ratio"]), _fmt_pct(lc["ratio"]), _pp(fc["ratio"], lc["ratio"])],
        row("Industries with any shipments (comparison set)", fc["served"], lc["served"]),
        row("Primary-industry levels, sum of level (comparison set)", fc["level"], lc["level"]),
        row("Closures flagged (all)", fa["flagged"], la["flagged"]),
        row(f"Full output stocks ≥{_pct_text(full)} (all)", ff, lf),
    ]
    blocks: list[Any] = [
        Heading(2, "Change Since First Sample"),
        Paragraph(f"Comparing {first.label} with {last.label} ({_span_text(first, last)}). The comparison set contains the "
                  f"{len(common)} industries present at both ends so that new or closed industries do not distort the "
                  "totals; they are listed separately below."),
        Table(["Metric", f"First ({first.label})", f"Latest ({last.label})", "Change"], rows,
              ["left", "right", "right", "right"]),
    ]
    bullets: list[str] = []
    if fc["produced"] or lc["produced"]:
        bullets.append(f"Observation: production in the comparison set went {_fmt_amount(fc['produced'])} → "
                       f"{_fmt_amount(lc['produced'])} items/yr and shipments {_fmt_amount(fc['shipped'])} → "
                       f"{_fmt_amount(lc['shipped'])} items/yr (service ratio {_fmt_pct(fc['ratio'])} → {_fmt_pct(lc['ratio'])}).")
    if new_ids or gone_ids:
        bullets.append(f"Observation: {len(new_ids)} new and {len(gone_ids)} vanished industries between the two samples.")
    if level_ups or level_downs:
        bullets.append(f"Observation: {level_ups} industries gained a level and {level_downs} lost one.")
    sched = [e for e in events if e["event"] in ("Closure scheduled", "Closure cancelled")]
    if sched:
        bullets.append(f"Observation: closure schedule changes after the first sample: "
                       f"{sum(1 for e in sched if e['event'] == 'Closure scheduled')} newly scheduled, "
                       f"{sum(1 for e in sched if e['event'] == 'Closure cancelled')} cancelled.")
    blocks.extend(Paragraph(b) for b in bullets)
    return blocks


def _section_evolution(samples: Sequence[Sample], full: float) -> list[Any]:
    picks = _pick_evenly(samples)
    rows, produced, shipped, ratios, cats = [], [], [], [], []
    for s in picks:
        st = _stats(list(s.inds.values()))
        full_count = _full_outputs(s, full)
        rows.append([s.label, st["n"], st["producing"], st["idle"], _int(st["produced"]), _int(st["shipped"]),
                     _fmt_pct(st["ratio"]), st["served"], f"{st['level']}/{st['max_level']}", st["flagged"],
                     "-" if full_count is None else full_count])
        cats.append(s.label)
        produced.append(float(st["produced"]))
        shipped.append(float(st["shipped"]))
        ratios.append(round((st["ratio"] or 0.0) * 100, 1))
    blocks: list[Any] = [
        Heading(2, "Evolution Over Time"),
        Paragraph(f"Showing {len(picks)} of {len(samples)} snapshots ({picks[0].label} to {picks[-1].label}). Every row is "
                  "one snapshot's rolling annual figures; rows are not additive. Level is Σ level/Σ maxLevel over "
                  "industries that have levels (primary industries)."),
        Table(["Sample", "Industries", "Producing", "Idle", "Produced/yr", "Shipped/yr", "Service ratio", "Industries shipping",
               "Level (Σ/Σ max)", "Closures flagged", "Full output stocks"],
              rows, ["left"] + ["right"] * 10),
    ]
    if len(picks) >= 2:
        blocks.extend([
            Chart("line", "Produced vs shipped, items per year (all industries)", cats,
                  [("Produced", produced), ("Shipped", shipped)]),
            Table(["Sample", "Service ratio (%)"], [[cat, value] for cat, value in zip(cats, ratios)],
                  ["left", "right"]),
            Chart("line", "Service ratio (%), shipped / produced", cats, [("Service ratio %", ratios)]),
        ])
    else:
        blocks.append(Note("Insufficient data", "Only one snapshot is available; trend charts need at least two."))
    return blocks


def _section_events(events: list[dict[str, Any]], tpd_known: bool) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Industry Lifecycle: New, Closed, Scheduled and Cancelled Closures")]
    if not events:
        return blocks + [Paragraph("No industry appeared, disappeared or changed closure status between the available snapshots.")]
    shown = events[-EVENT_CAP:]
    rows = [[e["date"], e["event"], e["ind"].name, e["ind"].label, e["detail"]] for e in shown]
    blocks.append(Table(["Sample", "Event", "Industry", "Type", "Detail"], rows, ["left"] * 5))
    if len(events) > len(shown):
        blocks.append(Note("Omitted", f"{len(events) - len(shown)} older events not shown (most recent {EVENT_CAP} displayed)."))
    if not tpd_known:
        blocks.append(Note("Calendar calibration", "Closing countdowns could not be converted to days (history spans less "
                           "than 14 calendar days or lacks dates)."))
    return blocks


def _section_levels(first: Sample, last: Sample, common: list[int]) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Level Upgrades and Production Movers")]
    changed = [i for i in common if (last.inds[i].level or 0) != (first.inds[i].level or 0)
               or (last.inds[i].max_level or 0) != (first.inds[i].max_level or 0)]
    changed.sort(key=lambda i: (-abs((last.inds[i].level or 0) - (first.inds[i].level or 0)), last.inds[i].name))
    if changed:
        rows = []
        for i in changed:
            a, b = first.inds[i], last.inds[i]
            rows.append([b.name, b.label, _arrow(a.level, b.level), _arrow(a.max_level, b.max_level),
                         _arrow(_int(a.produced), _int(b.produced)), _arrow(_int(a.shipped), _int(b.shipped)),
                         "Yes" if a.served else "No"])
        shown, omitted = _cap(rows, 20)
        blocks.extend([
            Paragraph(f"{len(changed)} industries changed level or maximum level between the first and latest sample."),
            Table(["Industry", "Type", "Level", "Max level", "Produced/yr", "Shipped/yr", "Shipping at first sample"],
                  shown, ["left", "left", "right", "right", "right", "right", "center"]),
            *_omitted(omitted, "industries"),
        ])
    else:
        blocks.append(Paragraph("No industry changed level or maximum level between the first and latest sample."))

    ratings = [i for i in common if first.inds[i].rating is not None and last.inds[i].rating is not None
               and abs(last.inds[i].rating - first.inds[i].rating) >= 0.05]
    ratings.sort(key=lambda i: (-abs(last.inds[i].rating - first.inds[i].rating), last.inds[i].name))
    if ratings:
        blocks.extend([
            Heading(3, "Production-rating changes (absolute change ≥0.05)"),
            Paragraph("productionRating is the raw engine measure, not instantaneous vehicle load. "
                      "Changes do not establish a cause or guarantee an upgrade."),
            Table(["Industry", "Type", "Rating first", "Rating latest", "Produced/yr"],
                  [[last.inds[i].name, last.inds[i].label, round(first.inds[i].rating, 3),
                    round(last.inds[i].rating, 3),
                    _arrow(_int(first.inds[i].produced), _int(last.inds[i].produced))] for i in ratings[:12]],
                  ["left", "left", "right", "right", "right"]),
            *_omitted(max(0, len(ratings) - 12), "rating changes"),
        ])

    # served vs unserved upgrade rates
    leveled = [i for i in common if first.inds[i].has_levels]
    groups = {"Shipping at first sample": [i for i in leveled if first.inds[i].served],
              "Not shipping at first sample": [i for i in leveled if not first.inds[i].served]}
    rows = []
    for name, ids in groups.items():
        ups = sum(1 for i in ids if (last.inds[i].level or 0) > (first.inds[i].level or 0))
        rows.append([name, len(ids), ups, _fmt_pct(ups / len(ids)) if ids else None])
    if leveled:
        blocks.extend([
            Table(["Primary industries (with levels)", "Industries", "Gained a level", "Share"], rows,
                  ["left", "right", "right", "right"]),
            Note("Reading", "Observation only: the game's expansion check is documented to favour well-served industries "
                 "(see knowledge M3), but a few months of history and the small group sizes here cannot confirm a causal "
                 "effect. The table becomes more meaningful as snapshots span years."),
        ])

    # production movers
    movers = []
    for i in common:
        a, b = first.inds[i], last.inds[i]
        for cargo, (p1, m1, s1) in b.outs.items():
            if cargo not in a.outs:
                continue
            p0, _, s0 = a.outs[cargo]
            delta = p1 - p0
            if abs(delta) >= max(15.0, 0.15 * p0):
                hint = []
                if (b.level or 0) != (a.level or 0):
                    hint.append(f"level {a.level}→{b.level}")
                if a.rating is not None and b.rating is not None and abs(b.rating - a.rating) >= 0.1:
                    hint.append(f"rating {a.rating:.2f}→{b.rating:.2f}")
                movers.append((delta, [b.name, _cargo(last.snap, cargo), _arrow(_int(p0), _int(p1)), _signed(delta),
                                       _arrow(_int(s0), _int(s1)), "; ".join(hint) or "-"]))
    if movers:
        ups = sorted((m for m in movers if m[0] > 0), key=lambda m: -m[0])[:8]
        downs = sorted((m for m in movers if m[0] < 0), key=lambda m: m[0])[:8]
        rows = [["Up"] + m[1] for m in ups] + [["Down"] + m[1] for m in downs]
        blocks.extend([
            Paragraph(f"Largest production changes per industry and cargo (threshold: at least 15 items/yr and 15% of the "
                      f"first value; {len(movers)} outputs qualified, top 8 per direction shown)."),
            Table(["Direction", "Industry", "Cargo", "Produced/yr", "Change", "Shipped/yr", "Level / rating change"], rows,
                  ["left", "left", "left", "right", "right", "right", "left"]),
        ])
    else:
        blocks.append(Paragraph("No output changed enough to pass the movers threshold."))
    return blocks


def _section_service_by_cargo(first: Sample, last: Sample, common: list[int]) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Service Ratio by Cargo (comparison set)")]
    agg: dict[int, dict[str, float]] = {}
    for i in common:
        for sample, key in ((first, "f"), (last, "l")):
            for cargo, (p, _m, s) in sample.inds[i].outs.items():
                d = agg.setdefault(cargo, {"fp": 0, "fs": 0, "lp": 0, "ls": 0, "producers": 0, "served": 0})
                d[key + "p"] += p
                d[key + "s"] += s
                if key == "l":
                    d["producers"] += 1 if p > 0 else 0
                    d["served"] += 1 if s > 0 else 0
    rows = []
    for cargo, d in sorted(agg.items(), key=lambda kv: (-kv[1]["lp"], kv[0])):
        if d["lp"] <= 0 and d["fp"] <= 0:
            continue
        r0, r1 = _ratio(d["fs"], d["fp"]), _ratio(d["ls"], d["lp"])
        rows.append([_cargo(last.snap, cargo), f"{int(d['served'])}/{int(d['producers'])}",
                     _arrow(_int(d["fp"]), _int(d["lp"])), _fmt_pct(r0), _fmt_pct(r1), _pp(r0, r1)])
    if not rows:
        return blocks + [Paragraph("Insufficient data: no industry output was recorded in the comparison set.")]
    shown, omitted = _cap(rows, 20)
    blocks.extend([
        Paragraph("Per cargo: how much of what is produced is shipped, at the first and the latest sample. "
                  "'Shipping/producing' counts industries with shipments against industries producing that cargo at the latest sample."),
        Table(["Cargo", "Shipping/producing (latest)", "Produced/yr", "Service ratio first", "Service ratio latest", "Change"],
              shown, ["left", "right", "right", "right", "right", "right"]),
        *_omitted(omitted, "cargos"),
    ])
    return blocks


def _section_service_by_type(first: Sample, last: Sample, common: list[int]) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Service by Industry Type and Outliers")]
    by_type: dict[str, list[int]] = {}
    for i in common:
        by_type.setdefault(last.inds[i].label, []).append(i)
    rows, chart_cats, chart_vals, no_output = [], [], [], []
    for label, ids in sorted(by_type.items(), key=lambda kv: (-_stats([last.inds[i] for i in kv[1]])["produced"], kv[0])):
        f, l = _stats([first.inds[i] for i in ids]), _stats([last.inds[i] for i in ids])
        if f["produced"] <= 0 and l["produced"] <= 0:
            no_output.append(f"{label} ({len(ids)})")
            continue
        ratings = [last.inds[i].rating for i in ids if last.inds[i].producing and last.inds[i].rating is not None]
        rows.append([label, len(ids), f"{l['served']}/{l['producing']}", _arrow(_int(f["produced"]), _int(l["produced"])),
                     _fmt_pct(f["ratio"]), _fmt_pct(l["ratio"]), f"{statistics.fmean(ratings):.2f}" if ratings else "-"])
        chart_cats.append(label)
        chart_vals.append(round((l["ratio"] or 0.0) * 100, 1))
    blocks.extend([
        Paragraph("Types are the industry's building type. 'Shipping/producing' = industries with shipments over industries "
                  "producing at the latest sample; the last column is the mean productionRating of producing industries."),
        Table(["Type", "Industries", "Shipping/producing", "Produced/yr", "Service first", "Service latest", "Mean rating"],
              rows, ["left", "right", "right", "right", "right", "right", "right"]),
    ])
    if no_output:
        blocks.append(Paragraph("Types with no production at either end (idle or input-starved): " + ", ".join(no_output) + "."))
    if chart_cats:
        blocks.append(Table(["Type", "Service ratio (%)"], list(map(list, zip(chart_cats[:20], chart_vals[:20]))),
                            ["left", "right"]))
        blocks.append(Chart("bar", "Service ratio by industry type, latest sample (%)", chart_cats[:20], [("Service ratio %", chart_vals[:20])]))

    # outliers: unserved producers whose peers of the same type are served
    out_rows = []
    for label, ids in by_type.items():
        producing = [last.inds[i] for i in ids if last.inds[i].producing]
        served = [x for x in producing if x.served]
        unserved = [x for x in producing if not x.served]
        if len(producing) < 3 or not served or not unserved:
            continue
        median = statistics.median(_ratio(x.shipped_eff, x.produced) or 0.0 for x in producing)
        for x in unserved:
            out_rows.append((x.produced, [x.name, label, _int(x.produced), f"{len(served)}/{len(producing)}", _fmt_pct(median),
                                         "Yes" if first.inds[x.id].served else "No"]))
    out_rows.sort(key=lambda r: (-r[0], r[1][0]))
    if out_rows:
        shown, omitted = _cap([r[1] for r in out_rows], 12)
        blocks.extend([
            Heading(3, "Unserved while same-type peers are served"),
            Paragraph("Producing industries with zero shipments in a type where other industries do ship (≥3 producing in the type). "
                      "These are candidates worth comparing with their served peers (cargo and consumers: see the cargo report)."),
            Table(["Industry", "Type", "Produced/yr", "Peers shipping", "Type median service", "Shipping at first sample"],
                  shown, ["left", "left", "right", "right", "right", "center"]),
            *_omitted(omitted, "industries"),
        ])
    else:
        blocks.append(Paragraph("No type has a mix of served and unserved producing industries (≥3 producing) at the latest sample."))
    return blocks


def _section_chains(first: Sample, last: Sample, full: float) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Consumer Chains: Inputs, Outputs and Throughput")]
    consumers = [i for i in last.inds.values() if i.ins]
    if not consumers:
        return blocks + [Paragraph("No industry with inputs (consumer) is recorded at the latest sample.")]

    # cargo balance
    cargo_ids = sorted({c for i in consumers for c in i.ins})
    rows = []
    for c in cargo_ids:
        producers = [i for i in last.inds.values() if c in i.outs]
        cons = [i for i in consumers if c in i.ins]
        produced = sum(i.outs[c][0] for i in producers)
        shipped = sum(i.outs[c][2] for i in producers)
        demand = sum(i.ins[c][1] for i in cons)
        consumed = sum(i.ins[c][0] for i in cons)
        consumed_first = sum(first.inds[i.id].ins[c][0] for i in cons if i.id in first.inds and c in first.inds[i.id].ins)
        rows.append((demand - consumed, [
            _cargo(last.snap, c), f"{sum(1 for i in producers if i.producing)}/{len(producers)}", _int(produced), _int(shipped),
            f"{sum(1 for i in cons if i.ins[c][0] > 0)}/{len(cons)}", _int(demand),
            _arrow(_int(consumed_first), _int(consumed)), _int(demand - consumed)]))
    rows.sort(key=lambda r: (-r[0], r[1][0]))
    shown, omitted = _cap([r[1] for r in rows], 15)
    blocks.extend([
        Heading(3, "Cargo balance: supply vs consumption capacity"),
        Paragraph("Per input cargo at the latest sample: how much is produced and shipped against how much consumer industries "
                  "could consume ('capacity' = maxConsumptionYear) and actually consume (consumedYear, first → latest). Ranked by "
                  "unused consumption capacity. Consumption is measured by consumedYear; deliveredYear is not used because "
                  "its meaning is unverified and it can be zero despite positive consumption."),
        Table(["Cargo", "Producing/producers", "Produced/yr", "Shipped/yr", "Consuming/consumers", "Consumption capacity/yr",
               "Consumed/yr (first → latest)", "Unused capacity/yr"],
              shown, ["left", "right", "right", "right", "right", "right", "right", "right"]),
        *_omitted(omitted, "cargos"),
    ])

    # consumer status
    status_rows = []
    counts: dict[str, int] = {}
    for ind in consumers:
        ratios = {c: (v[0] / v[1] if v[1] > 0 else None) for c, v in ind.ins.items()}
        known = [r for r in ratios.values() if r is not None]
        out_full = last.stocks is not None and any(
            s.owner == ind.id and s.role == "output" and s.fill >= full for s in last.stocks.values())
        below_capacity = ind.capacity > 0 and ind.produced < 0.9 * ind.capacity
        if ind.consumed == 0:
            status = "Idle (no input consumed)"
        elif out_full and below_capacity:
            status = "Output stock full, output below capacity"
        elif known and min(known) < 0.5:
            status = "Input-limited"
        else:
            status = "Running"
        counts[status] = counts.get(status, 0) + 1
        if status == "Running":
            continue
        before = first.inds.get(ind.id)
        limiting = min((c for c, r in ratios.items() if r is not None), key=lambda c: ratios[c], default=None)
        inputs_txt = "; ".join(f"{_cargo(last.snap, c)} {_int(v[0])}/{_int(v[1])}" for c, v in ind.ins.items())
        outputs_txt = "; ".join(f"{_cargo(last.snap, c)} {_int(v[0])}/{_int(v[1])}" for c, v in ind.outs.items())
        status_rows.append((ind.consumption_capacity, [
            ind.name, ind.label, status, inputs_txt, outputs_txt,
            _arrow(_int(before.consumed) if before else None, _int(ind.consumed)),
            _cargo(last.snap, limiting) if limiting is not None and status != "Running" else "-",
            "Yes" if ind.flagged else "No"]))
    status_rows.sort(key=lambda r: (-r[0], r[1][0]))
    summary = ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
    blocks.append(Heading(3, "Consumer industries that are not running at capacity"))
    blocks.append(Paragraph(f"{len(consumers)} consumers at the latest sample ({summary}). Status is inferred from consumedYear "
                            "vs maxConsumptionYear and, where stock data exists, full output stocks while output is below 90% of capacity; 'Input-limited' means at "
                            "least one input is consumed below 50% of its capacity. Inputs/outputs read 'consumed/capacity' and "
                            "'produced/capacity' items per year."))
    if status_rows:
        shown, omitted = _cap([r[1] for r in status_rows], 14)
        blocks.extend([
            Table(["Consumer", "Type", "Status", "Inputs", "Outputs", "Consumed/yr (first → latest)", "Weakest input", "Closing"],
                  shown, ["left", "left", "left", "left", "left", "right", "left", "center"]),
            *_omitted(omitted, "consumers"),
            Note("Inference", "An idle consumer is missing at least one required input; recipes need fixed ratios of all inputs "
                 "(knowledge M3). Which supplier to connect is a manual decision; the cargo report shows nearest producers/consumers."),
        ])
    else:
        blocks.append(Paragraph("All consumers are running."))
    return blocks


def _section_stocks(first: Sample, last: Sample, samples: Sequence[Sample], full: float) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Stock Fullness: Change in Time")]
    with_stocks = [s for s in samples if s.stocks is not None]
    if not with_stocks:
        return blocks + [Paragraph("Insufficient data: no snapshot contains stock data.")]
    f, l = with_stocks[0], with_stocks[-1]
    if l is not last:
        blocks.append(Note("Coverage", f"The latest snapshot has no stock data; using {l.label} as the latest stock sample."))
    only_one = f is l
    blocks.append(Paragraph(
        f"Stock data exists in {len(with_stocks)} of {len(samples)} snapshots (first with stocks: {f.label}). Fill = count / capacity "
        "at that instant. Output stock is the stock of an output cargo; input stock is the buffer of an input cargo. Full output "
        "stocks cause production to be wasted (knowledge M3); the cargo report lists those currently at 90% or more."))

    def group_rows(sample: Sample, other: Sample | None) -> dict[str, list[float]]:
        groups: dict[str, list[float]] = {"Output stocks, cargo shipped": [], "Output stocks, cargo not shipped": [],
                                         "Input stocks (consumers)": [], "Warehouses": []}
        for key, st in sample.stocks.items():
            ind = sample.inds.get(st.owner)
            if st.role == "output" and ind:
                shipped = any(ind.outs[c][2] > 0 for c in st.cargos if c in ind.outs)
                groups["Output stocks, cargo shipped" if shipped else "Output stocks, cargo not shipped"].append(st.fill)
            elif st.role == "input":
                groups["Input stocks (consumers)"].append(st.fill)
            elif st.role == "warehouse":
                groups["Warehouses"].append(st.fill)
        return groups

    gf, gl = group_rows(f, None), group_rows(l, None)
    rows = []
    for name in gl:
        a, b = gf.get(name, []), gl[name]
        rows.append([name, len(b), _fmt_pct(statistics.fmean(a)) if a else None, _fmt_pct(statistics.fmean(b)) if b else None,
                     sum(1 for x in a if x >= full), sum(1 for x in b if x >= full)])
    blocks.append(Table(["Stock group", "Stocks (latest)", f"Mean fill ({f.label})", f"Mean fill ({l.label})",
                         f"≥{_pct_text(full)} first", f"≥{_pct_text(full)} latest"], rows, ["left", "right", "right", "right", "right", "right"]))
    if only_one:
        return blocks + [Note("Insufficient data", "Only one snapshot has stock data, so fill changes cannot be computed yet.")]

    movers = []
    for key, st in l.stocks.items():
        old = f.stocks.get(key)
        ind = l.inds.get(st.owner)
        if old is None or st.role == "warehouse":
            continue
        delta = st.fill - old.fill
        if abs(delta) >= 0.2:
            name = ind.name if ind else f"Industry #{st.owner}"
            cargos = ", ".join(_cargo(l.snap, c) for c in st.cargos)
            movers.append((abs(delta), [name, st.role, cargos, f"{_fmt_pct(old.fill)} → {_fmt_pct(st.fill)}", _pp(old.fill, st.fill)]))
    movers.sort(key=lambda m: (-m[0], m[1][0]))
    if movers:
        shown, omitted = _cap([m[1] for m in movers], 15)
        blocks.extend([
            Heading(3, "Largest changes in stock fill (≥20 percentage points)"),
            Table(["Industry", "Stock", "Cargo", "Fill (first → latest)", "Change"], shown,
                  ["left", "left", "left", "right", "right"]),
            *_omitted(omitted, "stocks"),
        ])
    else:
        blocks.append(Paragraph("No industry stock changed fill by 20 percentage points or more between the first and latest stock samples."))
    return blocks


def _section_closures(first: Sample, last: Sample, samples: Sequence[Sample], events: list[dict[str, Any]],
                      tpd: float | None, links: dict[int, list[dict[str, Any]]]) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Closures and Risk")]
    flagged_since: dict[int, str] = {}
    for s in samples:
        for iid, ind in s.inds.items():
            if ind.flagged and iid not in flagged_since:
                flagged_since[iid] = s.label
    now = [i for i in last.inds.values() if i.flagged]
    now.sort(key=lambda i: (i.closure or 2**62, i.name))
    if now:
        rows = []
        for ind in now:
            ours = links.get(ind.id)
            cancel = []
            if ind.producing or ind.capacity > 0:
                cancel.append("load its output")
            if ind.ins:
                cancel.append("deliver inputs: " + ", ".join(_cargo(last.snap, c) for c in ind.ins))
            rows.append([ind.name, ind.label, _remaining(ind.closure, last.snap.game_time, tpd), flagged_since.get(ind.id, "-"),
                         _int(ind.produced), _int(ind.shipped), _int(ind.consumed) if ind.ins else None,
                         "Yes (name match)" if ours else "No station found", "; ".join(cancel) or "-"])
        blocks.extend([
            Heading(3, "Scheduled to close now"),
            Table(["Industry", "Type", "Closes in", "Flagged since", "Produced/yr", "Shipped/yr", "Consumed/yr", "Our station",
                   "Documented ways to cancel"], rows, ["left", "left", "left", "left", "right", "right", "right", "left", "left"]),
            Note("Documented mechanic", "A closure countdown is cancelled if production, consumption or loading resumes before it "
                 "ends (knowledge M4, from game code/wiki; not verified on this save). Whether to act is the player's call; "
                 "if one of our lines depends on its cargo, closure puts that supply or demand at risk."),
        ])
        if tpd is None:
            blocks.append(Note("Calendar calibration", "Days remaining need at least 14 calendar days of history; unavailable here."))
    else:
        blocks.append(Paragraph("No industry is flagged for closure at the latest sample."))

    resolved = [e for e in events if e["event"].startswith("Closed") or e["event"] == "Closure cancelled"
                or e["event"].startswith("Disappeared")]
    if resolved:
        rows = [[e["date"], e["event"], e["ind"].name, e["ind"].label, _int(e["ind"].produced), _int(e["ind"].shipped)]
                for e in resolved[-12:]]
        blocks.extend([
            Heading(3, "Closure outcomes observed"),
            Paragraph("Produced/shipped are the last values seen before the event row (for closed industries) or at the event (cancellations)."),
            Table(["Sample", "Outcome", "Industry", "Type", "Produced/yr", "Shipped/yr"], rows,
                  ["left", "left", "left", "left", "right", "right"]),
        ])

    # risk pool among non-flagged industries
    served_ever = {i for s in samples for i, ind in s.inds.items() if ind.served}
    active_ever = {i for s in samples for i, ind in s.inds.items() if ind.producing}
    pool = [i for i in last.inds.values() if not i.flagged and i.outs]
    tiers = {
        "Idle at every sample (capacity, zero output, never shipped)": [i for i in pool if i.id not in active_ever],
        "Producing but never shipped in any sample": [i for i in pool if i.id in active_ever and i.id not in served_ever],
        "Shipped in at least one sample": [i for i in pool if i.id in served_ever],
    }
    blocks.extend([
        Heading(3, "Closure-risk pool (not yet flagged)"),
        Paragraph(f"Covers {len(samples)} snapshots over {_span_text(samples[0], samples[-1])}. The documented draw is about "
                  "1.1% per industry per year times the closing-frequency option, and only industries without recent use are "
                  "eligible; the 'unused years' threshold (5 or 10) is unverified (knowledge M4). Our history cannot show how many "
                  "years an industry has been unused, so the tiers below rank evidence, not probability."),
        Table(["Tier (among industries with outputs)", "Industries"], [[k, len(v)] for k, v in tiers.items()], ["left", "right"]),
    ])
    idle_rows = sorted(tiers["Idle at every sample (capacity, zero output, never shipped)"],
                       key=lambda i: (-i.consumption_capacity, i.name))
    if idle_rows:
        shown, omitted = _cap([[i.name, i.label, _int(i.capacity), "; ".join(
            f"{_cargo(last.snap, c)} {_int(v[0])}/{_int(v[1])}" for c, v in i.ins.items()) or "-"] for i in idle_rows], 10)
        blocks.extend([
            Table(["Idle industry (largest demand first)", "Type", "Output capacity/yr", "Inputs (consumed/capacity per yr)"],
                  shown, ["left", "left", "right", "left"]),
            *_omitted(omitted, "industries"),
        ])
    return blocks


def _section_lines(first: Sample, last: Sample, links: dict[int, list[dict[str, Any]]]) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Which of Our Lines Serve Which Industry")]
    snap = last.snap
    blocks.append(Note(
        "Evidence level",
        "The snapshot has no station position, catchment or stock-at-station data, so a station-industry link is NOT verified. "
        "Links below are inferred when a station group has exactly the same name as exactly one industry (stations built at an "
        "industry are named after it). The cargo check compares the cargos the line has vehicle capacity for with the industry's "
        "output (shipping) or input (delivering) cargos; capacity is read instantaneously and the cargo index is corrected from "
        "the bridge's 1-based numbering."))
    if not links:
        return blocks + [Paragraph("No station name matches an industry name, so no line can be linked to an industry at this sample.")]

    rows = []
    for iid, entries in links.items():
        ind = last.inds[iid]
        before = first.inds.get(iid)
        serving, others, ship, deliver = [], [], set(), set()
        for e in entries:
            for ln in e["lines"]:
                if ln["ship"] or ln["deliver"]:
                    serving.append(ln["name"])
                else:
                    others.append(ln["name"])
                ship.update(ln["ship"])
                deliver.update(ln["deliver"])
        uniq = list(dict.fromkeys(serving))
        shown_lines = ", ".join(uniq[:2]) + (f" (+{len(uniq) - 2} more)" if len(uniq) > 2 else "")
        if others:
            n_other = len(set(others))
            shown_lines = (shown_lines + "; " if shown_lines else "") + f"{n_other} other line(s) stop there without its cargo"
        role = "producer" if ind.outs and not ind.ins else ("consumer" if ind.ins and not ind.outs else "producer + consumer")
        cargo_match = ", ".join(sorted(_cargo(snap, c) for c in ship | deliver)) or "none"
        verdict = ("cargo matches" if (ship | deliver) else "no line carries its cargo")
        rows.append((
            (0 if ind.flagged else 1, 1 if (ship | deliver) else 0, -ind.produced, ind.name),
            [ind.name, ind.label, role, shown_lines, cargo_match, verdict,
             _arrow(_int(before.produced) if before else None, _int(ind.produced)),
             _arrow(_int(before.shipped) if before else None, _int(ind.shipped)),
             "Yes" if ind.flagged else "No"]))
    rows.sort(key=lambda r: r[0])
    shown, omitted = _cap([r[1] for r in rows], 25)
    blocks.extend([
        Paragraph(f"{len(links)} industries have a name-matched station that is on at least one of our lines."),
        Table(["Industry", "Type", "Role", "Lines at the station carrying its cargo (name match)", "Cargo carried that matches", "Verdict",
               "Produced/yr (first → latest)", "Shipped/yr (first → latest)", "Closing"],
              shown, ["left", "left", "left", "left", "left", "left", "right", "right", "center"]),
        *_omitted(omitted, "industries"),
    ])
    shipping = [i for i in last.inds.values() if i.served]
    unmatched = [i for i in shipping if i.id not in links]
    matched_cargo = [i for i in links if any(ln["ship"] or ln["deliver"] for e in links[i] for ln in e["lines"])]
    blocks.append(Table(["Link coverage", "Industries"], [
        ["Industries with shipments at the latest sample", len(shipping)],
        ["... of which with a name-matched station on our lines", len(shipping) - len(unmatched)],
        ["... of which link NOT verifiable (no station carries the industry's name)", len(unmatched)],
        ["Name-matched industries whose station lines carry a matching cargo", len(matched_cargo)],
    ], ["left", "right"]))
    if unmatched:
        names = ", ".join(i.name for i in sorted(unmatched, key=lambda i: -i.shipped)[:6])
        blocks.append(Paragraph(f"Observation: shipping industries without a verifiable station link include: {names}"
                                f"{' …' if len(unmatched) > 6 else ''}. The shipments exist (shippedYear > 0) but the snapshot does "
                                "not say which of our stations or lines moves them (renamed stations, shared stations or distant "
                                "stations cannot be matched)."))
    return blocks


def _section_manual_review(first: Sample, last: Sample, tpd: float | None, full: float) -> list[Any]:
    rows = []
    closing = sorted((ind for ind in last.inds.values() if ind.flagged),
                     key=lambda ind: (ind.closure or 2**62, ind.name))
    if closing:
        ind = closing[0]
        rows.append(["1", ind.name,
                     f"Closure flagged; remaining {_remaining(ind.closure, last.snap.game_time, tpd)}",
                     "Decide manually whether this industry is worth retaining. Inspect its input/output links in-game "
                     "before the countdown ends; otherwise allow closure and avoid depending on it."])
    declines = [(before.produced - last.inds[iid].produced, last.inds[iid], before)
                for iid, before in first.inds.items() if iid in last.inds
                and not before.unknown_flows and not last.inds[iid].unknown_flows]
    if declines:
        delta, ind, before = max(declines, key=lambda row: (row[0], row[1].name))
        if delta >= 30:
            rows.append(["2", ind.name,
                         f"Produced/yr {_fmt_amount(before.produced)} → {_fmt_amount(ind.produced)} "
                         f"({_signed(-delta)})",
                         "Inspect its input buffer and the lines supplying it, then its downstream output buffers. "
                         "Determine whether supply fell or stock accumulated before changing vehicles."])
    if last.stocks:
        blocked = [ind for ind in last.inds.values() if ind.served and any(
            st.owner == ind.id and st.role == "output" and st.fill >= full
            and any(c in ind.outs and ind.outs[c][2] == 0 for c in st.cargos)
            for st in last.stocks.values())]
        if blocked:
            ind = max(blocked, key=lambda ind: (ind.produced, ind.name))
            rows.append(["3", ind.name,
                         f"Some output ships, but another output cargo has zero shipments and a ≥{_pct_text(full)} full stock",
                         "Inspect the unshipped coproduct and its consumer chain. A line carrying one output does not "
                         "necessarily serve all of this industry's outputs. Compare against the cargo report."])
    return [Heading(2, "Suggested Manual Review Priorities"),
            Table(["Priority", "Industry", "Observation", "Suggestion (player action only)"], rows)] if rows else [
                Heading(2, "Suggested Manual Review Priorities"),
                Paragraph("No closing industry, substantial production decline or full unshipped coproduct qualifies "
                          "for these review priorities in the available samples.")]



# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _safe(title: str, fn: Callable[[], list[Any]]) -> list[Any]:
    try:
        return fn()
    except (KeyError, TypeError, ValueError, ZeroDivisionError, IndexError) as exc:  # malformed snapshot data
        return [Heading(2, title), Paragraph(f"Section unavailable: snapshot data could not be interpreted ({type(exc).__name__}).")]


def build(store: Store, thresholds: analysis.Thresholds | None = None) -> ReportDocument:
    full = (thresholds or analysis.Thresholds()).full_stock_ratio
    latest_snapshot = store.latest()
    if latest_snapshot is None:
        raise ValueError("No snapshot found. Load a save with the bridge enabled and run tf3c refresh.")
    snaps = [snap for snap in store.snapshots() if snap.game_time <= latest_snapshot.game_time]
    samples = [_sample_of(s) for s in snaps]
    first, last = samples[0], samples[-1]
    latest = last.snap

    with_stock = [s for s in samples if s.stocks is not None]
    header = [
        ("Company / Save", latest.company.get("name") or "Primary Company"),
        ("First Sample Date", first.label),
        ("Latest Sample Date", latest.date_label),
        ("Snapshots Used", str(len(samples))),
        ("Coverage", _span_text(first, last) if len(samples) > 1 else "single snapshot (no change can be shown)"),
        ("Stock Coverage", (f"{len(with_stock)} of {len(samples)} snapshots (from {with_stock[0].label})" if with_stock
                            else "no stock data in any snapshot")),
        ("Collection Errors", "; ".join(dict.fromkeys(
            error.split(":")[0] for s in samples for error in s.snap.errors
        )) or "None reported"),
        ("Unknown Flows", f"{sum(i.unknown_flows for i in last.inds.values())} latest industries excluded from flow totals "
                          "(missing input/output fields or measurements)"),
        ("Measurement Limits", "Production, shipments and consumption are rolling annual figures per snapshot (never summed "
                               "across snapshots); service ratio is shipped / produced and can exceed 100% due to stock draw-down; "
                               "incomplete input/output flows are omitted as unknown, never counted as zero; distances are not used; "
                               "station-industry links are name-match inferences; calendar days come from meta.date."),
        ("Save Boundary", "One companion store; history is not guaranteed to belong to a single save. "
                          "Comparisons assume these samples are from the same save."),
    ]
    if not last.inds:
        return ReportDocument("industries", "Industries Evolution and Comparison Report", header, [
            Heading(2, "Industries"),
            Paragraph("Insufficient data: the latest snapshot lists no industries."),
        ])

    if all(ind.unknown_flows for ind in last.inds.values()):
        return ReportDocument("industries", "Industries Evolution and Comparison Report", header, [
            Heading(2, "Industries"),
            Paragraph("Insufficient data: no industry has complete input/output measurements; production, service and chain "
                      "comparisons are unknown, not zero."),
        ])
    tpd = _ticks_per_day(first, last)
    common = [i for i in first.inds if i in last.inds and not first.inds[i].unknown_flows
              and not last.inds[i].unknown_flows]
    events = _events(samples, tpd) if len(samples) > 1 else []
    links = _links(last)

    blocks: list[Any] = []
    if len(samples) < 2 or not common:
        blocks.append(Heading(2, "Change Since First Sample"))
        blocks.append(Paragraph("Insufficient data: at least two snapshots sharing industries are required to show change. "
                                "The sections below describe the latest sample only where they can."))
    else:
        blocks += _safe("Change Since First Sample", lambda: _section_summary(first, last, common, events, full))
    blocks += _safe("Evolution Over Time", lambda: _section_evolution(samples, full))
    if len(samples) > 1:
        blocks += _safe("Industry Lifecycle", lambda: _section_events(events, tpd is not None))
    if common and len(samples) > 1:
        blocks += _safe("Level Upgrades and Production Movers", lambda: _section_levels(first, last, common))
        blocks += _safe("Service Ratio by Cargo", lambda: _section_service_by_cargo(first, last, common))
        blocks += _safe("Service by Industry Type", lambda: _section_service_by_type(first, last, common))
    blocks += _safe("Consumer Chains", lambda: _section_chains(first, last, full))
    blocks += _safe("Stock Fullness", lambda: _section_stocks(first, last, samples, full))
    blocks += _safe("Closures and Risk", lambda: _section_closures(first, last, samples, events, tpd, links))
    blocks += _safe("Lines and Industries", lambda: _section_lines(first, last, links))
    blocks += _section_manual_review(first, last, tpd, full)
    return ReportDocument("industries", "Industries Evolution and Comparison Report", header, blocks)
