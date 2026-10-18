"""Vehicle ROI report: which vehicle types make (or lose) money, and what to test instead.

Honesty rules enforced here:
- ``profitYear`` is a rolling game-year figure. Per-vehicle values are only ever summed *within one
  snapshot* (distinct vehicles at one instant), never across snapshots; trends compare point samples.
- Vehicles younger than one game year have a partial window; group statistics are ranked on mature
  vehicles and young vehicles are reported separately as a lower bound.
- Catalog speed / running-cost / price units are unverified unless the catalog snapshot carries
  ``meta.verifiedUnits``. The swap section therefore only shows raw values and unit-free ratios.
- Line ``capacity[].cargo`` is indexed one higher than ``vehicles[].loadConfig[].cargo`` in the
  stored data (verified for every vehicle in the sample database). This module identifies a
  vehicle's cargo from ``loadConfig`` only and never names line-level cargo indices.
"""

from __future__ import annotations

import statistics
from datetime import date
from collections import Counter, defaultdict
from typing import Any

from . import analysis
from .reports import (
    Chart,
    Heading,
    Note,
    Paragraph,
    ReportDocument,
    Table,
    _base_header,
    _fmt_pct,
)
from .snapshot import Snapshot
from .store import Store

MIN_SAMPLE = 3
MODEL_ROWS = 30
CARGO_ROWS = 25
TREND_GROUPS = 8
TREND_COLUMNS = 8
LOAD_HISTORY = 24
SWAP_GROUPS = 6
SWAP_CANDIDATES = 3
MIN_LOAD_SAMPLES = 3

AGE_BUCKETS: list[tuple[float, float, str]] = [
    (0.0, 1.0, "<1y (partial window)"),
    (1.0, 3.0, "1-3y"),
    (3.0, 6.0, "3-6y"),
    (6.0, 10.0, "6-10y"),
    (10.0, 20.0, "10-20y"),
    (20.0, float("inf"), "20y+"),
]

ISSUE_TYPES = ("VehicleUseless", "NoVehicleToLoadCargo", "LineCargoConfig")


# ---------------------------------------------------------------------------
# Vehicle records
# ---------------------------------------------------------------------------

def _model_name(snap: Snapshot, model_id: Any) -> str:
    model = snap.models.get(model_id) or {}
    name = model.get("name")
    if name:
        return str(name)
    res = model.get("res")
    if res:
        return str(res).rsplit("/", 1)[-1].removesuffix(".mdl")
    return f"Model #{model_id}"


def _signature(snap: Snapshot, vehicle: dict[str, Any]) -> str:
    counts = Counter(_model_name(snap, m) for m in vehicle.get("models") or [])
    if not counts:
        return "Unknown model"
    return " + ".join(f"{name} x{n}" if n > 1 else name for name, n in sorted(counts.items()))


def _cargo_ids(vehicle: dict[str, Any]) -> tuple[int, ...]:
    return tuple(sorted({c["cargo"] for c in vehicle.get("loadConfig") or []
                         if isinstance(c.get("cargo"), int) and (c.get("capacity") or 0) > 0}))


def _cargo_label(snap: Snapshot, ids: tuple[int, ...]) -> str:
    if not ids:
        return "Unknown cargo"
    names = [snap.cargo(i) or str(i) for i in ids]
    return " + ".join(names) if len(names) <= 3 else " + ".join(names[:2]) + f" + {len(names) - 2} more"


def _list_price(snap: Snapshot, vehicle: dict[str, Any]) -> float | None:
    prices = [(snap.models.get(m) or {}).get("price") for m in vehicle.get("models") or []]
    if not prices or any(not isinstance(p, (int, float)) or p <= 0 for p in prices):
        return None
    return float(sum(prices))


def _ticks_per_year(snaps: list[Snapshot]) -> tuple[float | None, str]:
    """Game ticks per calendar year, calibrated from snapshot dates.

    meta.yearDuration is about 4x shorter than the calendar year in the sample data (ticks per
    calendar day ~16,000 vs yearDuration/365.25 = 4,000), so (gameTime - purchaseTime) / yearDuration
    overstates vehicle age. We calibrate from the widest date span among stored snapshots and fall
    back to yearDuration only when no two snapshots have different dates.
    """
    dated = []
    for s in snaps:
        try:
            d = s.date or {}
            dated.append((s.game_time, date(d["year"], d["month"], d["day"])))
        except (KeyError, ValueError, TypeError):
            continue
    if dated:
        first, last = min(dated, key=lambda p: p[0]), max(dated, key=lambda p: p[0])
        days = (last[1] - first[1]).days
        if days >= 7 and last[0] > first[0]:
            return (last[0] - first[0]) / days * 365.25, f"calibrated from snapshot dates ({days} calendar days spanned)"
    year = next((s.year_duration for s in reversed(snaps) if s.year_duration), 0)
    if year:
        return float(year), "meta.yearDuration (could not be calibrated; may overstate age ~4x)"
    return None, "unavailable"


def _records(snap: Snapshot, ticks_per_year: float | None, mature_years: float) -> list[dict[str, Any]]:
    out = []
    for v in snap.vehicles:
        pt = v.get("purchaseTime")
        age = (snap.game_time - pt) / ticks_per_year if pt is not None and ticks_per_year else None
        line = snap.lines_by_id.get(v.get("line"))
        ids = _cargo_ids(v)
        out.append({
            "id": v["id"],
            "name": v.get("name") or f"Vehicle #{v['id']}",
            "carrier": v.get("carrier") or "UNKNOWN",
            "model": _signature(snap, v),
            "parts": len(v.get("models") or []),
            "cargo_ids": ids,
            "cargo": _cargo_label(snap, ids),
            "age": age,
            "profit": v.get("profitYear") if isinstance(v.get("profitYear"), (int, float)) else None,
            "value": v.get("value") if isinstance(v.get("value"), (int, float)) else None,
            "running": v.get("runningCost") if isinstance(v.get("runningCost"), (int, float)) else None,
            "price": _list_price(snap, v),
            "condition": v.get("maintenanceState") if isinstance(v.get("maintenanceState"), (int, float)) else None,
            "capacity": v.get("capacity") if isinstance(v.get("capacity"), (int, float)) else None,
            "line_id": v.get("line") if line else None,
            "line": (line.get("name") or f"Line #{line['id']}") if line else None,
            "models": list(v.get("models") or []),
            "can_carry": v.get("canCarry"),
            "raw": v,
            "mature_years": mature_years,
        })
    return out


def _is_mature(r: dict[str, Any]) -> bool:
    return r["profit"] is not None and r["age"] is not None and r["age"] >= r["mature_years"]


def _is_young(r: dict[str, Any]) -> bool:
    return r["profit"] is not None and r["age"] is not None and r["age"] < r["mature_years"]


# ---------------------------------------------------------------------------
# Group statistics
# ---------------------------------------------------------------------------

def _ratio(num: float, den: float) -> float | None:
    return num / den if den else None


def _stats(recs: list[dict[str, Any]]) -> dict[str, Any]:
    mature = [r for r in recs if _is_mature(r)]
    young = [r for r in recs if _is_young(r)]
    profits = [r["profit"] for r in mature]
    with_value = [r for r in mature if r["value"]]
    with_price = [r for r in mature if r["price"]]
    with_run = [r for r in mature if r["running"]]
    return {
        "n": len(recs),
        "mature": len(mature),
        "young": len(young),
        "mean": statistics.fmean(profits) if profits else None,
        "median": statistics.median(profits) if profits else None,
        "total": sum(profits) if profits else None,
        "loss_share": sum(1 for p in profits if p < 0) / len(profits) if profits else None,
        "ret_value": _ratio(sum(r["profit"] for r in with_value), sum(r["value"] for r in with_value)) if with_value else None,
        "ret_price": _ratio(sum(r["profit"] for r in with_price), sum(r["price"] for r in with_price)) if with_price else None,
        "ret_run": _ratio(sum(r["profit"] for r in with_run), sum(r["running"] for r in with_run)) if with_run else None,
        "young_mean": statistics.fmean([r["profit"] for r in young]) if young else None,
        "mean_condition": (statistics.fmean([r["condition"] for r in recs if r["condition"] is not None])
                           if any(r["condition"] is not None for r in recs) else None),
    }


def _money(value: float | None) -> int | None:
    return None if value is None else int(round(value))


def _flag(stats: dict[str, Any]) -> str:
    if stats["mature"] == 0:
        return "No mature vehicles"
    if stats["mature"] < MIN_SAMPLE:
        return f"Small sample (n={stats['mature']})"
    return "OK"


_GROUP_COLUMNS = ["Vehicles", "Mature (>=1y)", "Young (<1y)", "Mean profit/vehicle", "Median", "Total (mature)",
                  "Loss-making (mature)", "Profit / value", "Young mean (partial)", "Sample"]
_GROUP_ALIGN = ["right"] * 9 + ["left"]


def _group_cells(stats: dict[str, Any]) -> list[Any]:
    return [stats["n"], stats["mature"], stats["young"], _money(stats["mean"]), _money(stats["median"]),
            _money(stats["total"]), _fmt_pct(stats["loss_share"]), _fmt_pct(stats["ret_value"]),
            _money(stats["young_mean"]), _flag(stats)]


def _group_by(recs: list[dict[str, Any]], key) -> dict[Any, list[dict[str, Any]]]:
    groups: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for r in recs:
        groups[key(r)].append(r)
    return groups


def _rank_key(item: tuple[Any, dict[str, Any]]) -> tuple:
    label, st = item
    if st["mean"] is not None:
        return (0, -st["mean"], str(label))
    if st["young_mean"] is not None:
        return (1, -st["young_mean"], str(label))
    return (2, 0, str(label))


def _model_label(carrier: str, model: str) -> str:
    return f"{model} [{carrier}]"


# ---------------------------------------------------------------------------
# Sampling for point-in-time comparisons
# ---------------------------------------------------------------------------

def _date_of(snap: Snapshot) -> tuple[int, int, int]:
    d = snap.date or {}
    return (d.get("year", snap.meta.get("year") or 0), d.get("month", 0), d.get("day", 0))


def _sample(snaps: list[Snapshot]) -> list[Snapshot]:
    """Last snapshot per month; coarsened to quarters then years while more than TREND_COLUMNS remain."""
    ordered = sorted(snaps, key=lambda s: s.game_time)

    def pick(bucket) -> list[Snapshot]:
        last: dict[Any, Snapshot] = {}
        for s in ordered:
            last[bucket(s)] = s
        return sorted(last.values(), key=lambda s: s.game_time)

    for bucket in (lambda s: _date_of(s)[:2],
                   lambda s: (_date_of(s)[0], (_date_of(s)[1] - 1) // 3),
                   lambda s: _date_of(s)[0]):
        chosen = pick(bucket)
        if len(chosen) <= TREND_COLUMNS:
            return chosen
    return chosen[-TREND_COLUMNS:]


# ---------------------------------------------------------------------------
# Catalog helpers
# ---------------------------------------------------------------------------

def _game_year(snap: Snapshot) -> int | None:
    return (snap.date or {}).get("year", snap.meta.get("year"))


def _in_production(model: dict[str, Any], year: int | None) -> bool:
    if model.get("available") is False and year is None:
        return False
    start, end = model.get("yearFrom"), model.get("yearTo")
    if year is None:
        return model.get("available") is not False
    return (start is None or start <= 0 or start <= year) and (end is None or end <= 0 or year < end)


def _catalog_capacity(model: dict[str, Any], cargo_id: int) -> float:
    return sum(c.get("capacity") or 0 for c in model.get("capacity") or [] if c.get("cargo") == cargo_id)


def _ratio_cell(candidate: Any, current: Any) -> str | None:
    if not isinstance(candidate, (int, float)) or not isinstance(current, (int, float)) or current <= 0 or candidate <= 0:
        return None
    return f"x{candidate / current:.2f}"


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

def _insufficient(title: str, why: str) -> list[Any]:
    return [Heading(2, title), Note("Insufficient Data", why)]


def _summary(recs: list[dict[str, Any]], model_groups: dict[Any, dict[str, Any]], latest: Snapshot) -> list[Any]:
    overall = _stats(recs)
    blocks: list[Any] = [Heading(2, "Summary (Observations)")]
    if not recs:
        return blocks + [Note("Insufficient Data", "The latest snapshot has no vehicles.")]
    lines = [
        f"{overall['n']} vehicles in the latest snapshot ({latest.date_label}): {overall['mature']} mature (>=1 game year old, "
        f"full rolling-profit window) and {overall['young']} young (partial window).",
    ]
    if overall["mature"]:
        lines.append(
            f"Mature vehicles: mean {_money(overall['mean']):,} and median {_money(overall['median']):,} rolling annual profit per "
            f"vehicle; {_fmt_pct(overall['loss_share'])} are loss-making. Sum of those distinct vehicles' rolling profits at this one "
            f"snapshot: {_money(overall['total']):,} (not calendar income)."
        )
    ranked = [(k, s) for k, s in model_groups.items() if s["mature"] >= MIN_SAMPLE]
    ranked.sort(key=lambda kv: (-kv[1]["mean"], kv[0]))
    if ranked:
        best, worst = ranked[0], ranked[-1]
        lines.append(f"Best model group with n>={MIN_SAMPLE} mature vehicles: {best[0]} - mean {_money(best[1]['mean']):,} "
                     f"(n={best[1]['mature']}).")
        if worst[0] != best[0]:
            lines.append(f"Worst: {worst[0]} - mean {_money(worst[1]['mean']):,}, {_fmt_pct(worst[1]['loss_share'])} loss-making "
                         f"(n={worst[1]['mature']}).")
    small = sum(1 for s in model_groups.values() if s["mature"] < MIN_SAMPLE)
    if small:
        lines.append(f"{small} of {len(model_groups)} model groups have fewer than {MIN_SAMPLE} mature vehicles and are flagged, not ranked.")
    blocks.extend(Paragraph(t) for t in lines)
    return blocks


def _carrier_section(recs: list[dict[str, Any]]) -> list[Any]:
    if not recs:
        return _insufficient("By Carrier", "No vehicles.")
    groups = {k: _stats(v) for k, v in _group_by(recs, lambda r: r["carrier"]).items()}
    ordered = sorted(groups.items(), key=_rank_key)
    blocks: list[Any] = [
        Heading(2, "By Carrier"),
        Table(["Carrier"] + _GROUP_COLUMNS, [[k] + _group_cells(s) for k, s in ordered], ["left"] + _GROUP_ALIGN),
    ]
    charted = [(k, s) for k, s in ordered if s["mature"] > 0]
    if len(charted) >= 2:
        blocks.append(Chart("bar", "Mean rolling profit per mature vehicle, by carrier",
                            [k for k, _ in charted], [("Mean profit", [float(_money(s["mean"])) for _, s in charted])]))
    blocks.append(Note("Reading This", "Carriers differ in cargo, distance and vehicle price, so this compares business lines, "
                                       "not how good a vehicle is. 'Profit / value' is aggregate rolling profit over aggregate "
                                       "recorded vehicle value (value depreciates, so old vehicles look better on this ratio)."))
    return blocks


def _model_section(recs: list[dict[str, Any]], groups: dict[Any, dict[str, Any]],
                   model_recs: dict[Any, list[dict[str, Any]]]) -> list[Any]:
    if not recs:
        return _insufficient("By Model", "No vehicles.")
    ordered = sorted(groups.items(), key=_rank_key)
    shown = ordered[:MODEL_ROWS]
    blocks: list[Any] = [
        Heading(2, "By Model"),
        Table(["Model [Carrier]"] + _GROUP_COLUMNS, [[k] + _group_cells(s) for k, s in shown], ["left"] + _GROUP_ALIGN),
    ]
    if len(ordered) > len(shown):
        blocks.append(Paragraph(f"{len(ordered) - len(shown)} further model groups omitted (lowest ranked / youngest)."))
    blocks.append(Paragraph("Multi-part vehicles (trains) are grouped by their full consist: locomotive and wagon models with part "
                            "counts, so differently sized consists are separate groups."))

    reliable = sorted(((k, s) for k, s in groups.items() if s["mature"] >= MIN_SAMPLE), key=lambda kv: (-kv[1]["mean"], kv[0]))
    blocks.append(Heading(3, f"Ranking (groups with at least {MIN_SAMPLE} mature vehicles)"))
    if not reliable:
        blocks.append(Note("Insufficient Data", f"No model group has {MIN_SAMPLE} or more mature vehicles yet."))
    else:
        top = reliable[:6]
        bottom = reliable[6:][-6:]
        picks = top + bottom
        rank_of = {k: i + 1 for i, (k, _) in enumerate(reliable)}
        blocks.append(Table(["Rank", "Model [Carrier]", "Mature n", "Mean profit/vehicle", "Median", "Loss-making"],
                            [[rank_of[k], k, s["mature"], _money(s["mean"]), _money(s["median"]), _fmt_pct(s["loss_share"])]
                             for k, s in picks],
                            ["right", "left", "right", "right", "right", "right"]))
        blocks.append(Chart("bar", "Mean rolling profit per mature vehicle (best and worst groups)",
                            [k for k, _ in picks], [("Mean profit", [float(_money(s["mean"])) for _, s in picks])]))
        blocks.append(Paragraph(f"Ranked {len(reliable)} groups; top {len(top)} and bottom {len(bottom)} shown."))

    blocks.append(Heading(3, "Cost Basis (Raw Catalog-Style Values)"))
    rows = []
    for k, s in shown:
        sample = model_recs[k]
        price = [r["price"] for r in sample if r["price"]]
        run = [r["running"] for r in sample if r["running"]]
        rows.append([k, s["mature"], _money(statistics.median(price)) if price else None,
                     _money(statistics.median(run)) if run else None,
                     _fmt_pct(s["ret_price"]), None if s["ret_run"] is None else f"{s['ret_run']:.2f}"])
    blocks.append(Table(["Model [Carrier]", "Mature n", "List price (raw, median)", "Running cost (raw, median)",
                         "Profit / list price", "Profit / running cost (raw ratio)"], rows,
                        ["left", "right", "right", "right", "right", "right"]))
    blocks.append(Note("Unit Limit", "List price and running cost are the stored model values (running cost also appears per "
                                     "vehicle) in unverified units; no per-year or currency conversion is applied. 'Profit / list "
                                     "price' ignores the per-vehicle price factor and any resale; whether rolling profit already "
                                     "nets out running costs is unverified, so 'profit / running cost' is a raw ratio for "
                                     "ordering only."))
    return blocks


def _cargo_section(recs: list[dict[str, Any]]) -> list[Any]:
    if not recs:
        return _insufficient("By Cargo", "No vehicles.")
    groups = {k: _stats(v) for k, v in _group_by(recs, lambda r: r["cargo"]).items()}
    ordered = sorted(groups.items(), key=_rank_key)
    blocks: list[Any] = [
        Heading(2, "By Cargo"),
        Table(["Cargo (vehicle's configured load)"] + _GROUP_COLUMNS, [[k] + _group_cells(s) for k, s in ordered[:CARGO_ROWS]],
              ["left"] + _GROUP_ALIGN),
    ]
    if len(ordered) > CARGO_ROWS:
        blocks.append(Paragraph(f"{len(ordered) - CARGO_ROWS} further cargo groups omitted."))
    blocks.append(Note("Reading This", "Cargo is taken from each vehicle's current load configuration. In this game every freight "
                                       "cargo pays the same per item and distance (see knowledge: cargo_economy), so cargo rows "
                                       "mostly reflect route length, vehicle capacity and return loads, not goods type."))
    return blocks


def _age_section(recs: list[dict[str, Any]], mature: float) -> list[Any]:
    aged = [r for r in recs if r["age"] is not None]
    if not aged:
        return _insufficient("By Age", "No vehicle has a usable purchase time.")
    rows = []
    for carrier in sorted({r["carrier"] for r in aged}):
        for lo, hi, label in AGE_BUCKETS:
            part = [r for r in aged if r["carrier"] == carrier and lo <= r["age"] < hi]
            if not part:
                continue
            s = _stats(part)
            # Young bucket has no mature vehicles by construction; use the partial-window mean there.
            rows.append([carrier, label, s["n"], _money(s["mean"] if s["mature"] else s["young_mean"]),
                         _money(s["median"]), _fmt_pct(s["loss_share"]),
                         None if s["mean_condition"] is None else round(s["mean_condition"], 2),
                         "Partial window (lower bound)" if hi <= mature else _flag(s)])
    return [
        Heading(2, "By Age (Within Carrier)"),
        Table(["Carrier", "Age", "Vehicles", "Mean profit/vehicle", "Median", "Loss-making", "Mean condition (0-1)", "Sample"],
              rows, ["left", "left", "right", "right", "right", "right", "right", "left"]),
        Note("Reading This", "Age is (snapshot time - purchase time) / ticks per calendar year (calibrated from snapshot dates; see header). Condition is maintenanceState (1 = excellent). "
                             "The <1y bucket shows the partial-window mean, which understates a full year. Older vehicles may "
                             "also sit on different lines, so age and profit are associated here, not shown to be causal."),
    ]


def _head_to_head(recs: list[dict[str, Any]]) -> list[Any]:
    by_line: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for r in recs:
        if r["line_id"] is not None and _is_mature(r):
            by_line[r["line_id"]].append(r)
    rows = []
    for line_recs in by_line.values():
        groups = _group_by(line_recs, lambda r: _model_label(r["carrier"], r["model"]))
        if len(groups) < 2:
            continue
        summarized = sorted(((k, v, statistics.fmean(r["profit"] for r in v)) for k, v in groups.items()), key=lambda t: (-t[2], t[0]))
        (bk, bv, bm), (wk, wv, wm) = summarized[0], summarized[-1]

        def side(v: list[dict[str, Any]], mean: float) -> str:
            return f"n={len(v)}, mean {_money(mean):,}, avg age {statistics.fmean(r['age'] for r in v):.1f}y"

        small = min(len(bv), len(wv)) < MIN_SAMPLE
        rows.append((bm - wm, [line_recs[0]["line"], bk, side(bv, bm), wk, side(wv, wm), _money(bm - wm),
                               f"Small sample (smaller side n={min(len(bv), len(wv))})" if small else "OK"]))
    rows.sort(key=lambda t: (-t[0], str(t[1][0])))
    if not rows:
        return _insufficient("Same-Line Head-to-Head", "No line currently runs two or more model groups with a mature vehicle each.")
    return [
        Heading(2, "Same-Line Head-to-Head"),
        Paragraph("Models operating on the same line share the route, so this removes route effects. Best vs worst mean per-vehicle "
                  "rolling profit among mature vehicles; lines with more than two model groups show only the extremes."),
        Table(["Line", "Better model", "Better: sample", "Weaker model", "Weaker: sample", "Mean gap", "Evidence"],
              [r for _, r in rows[:15]], ["left", "left", "left", "left", "left", "right", "left"]),
        Paragraph(f"{len(rows)} lines compared; top {min(15, len(rows))} by gap shown." if len(rows) > 15 else f"{len(rows)} lines compared."),
        Note("Caution", "Vehicles on one line may differ in age, purchase date, depot or timetable position; this is an observation "
                        "of association only, mostly with n<3 per side."),
    ]


def _trend_section(snaps: list[Snapshot], latest_groups: dict[Any, dict[str, Any]], tpy: float | None, mature: float) -> list[Any]:
    samples = _sample(snaps)
    if len(samples) < 2:
        return _insufficient("Group Profit At Sampled Dates", "Fewer than two sampled snapshots; no point-in-time comparison possible.")
    per_sample: list[dict[Any, dict[str, Any]]] = []
    overall_cells: list[dict[str, Any]] = []
    for s in samples:
        recs = _records(s, tpy, mature)
        per_sample.append({k: _stats(v) for k, v in _group_by(recs, lambda r: _model_label(r["carrier"], r["model"])).items()})
        overall_cells.append(_stats(recs))
    picks = sorted(((k, s) for k, s in latest_groups.items() if s["mature"] > 0),
                   key=lambda kv: (-kv[1]["mature"], kv[0]))[:TREND_GROUPS]
    cats = [s.date_label for s in samples]

    def cell(st: dict[str, Any] | None) -> str:
        if not st or st["mature"] == 0:
            return "-"
        return f"{_money(st['mean']):,} (n={st['mature']}){'*' if st['mature'] < MIN_SAMPLE else ''}"

    rows = [["All vehicles"] + [cell(o) for o in overall_cells]]
    rows += [[k] + [cell(p.get(k)) for p in per_sample] for k, _ in picks]
    blocks: list[Any] = [
        Heading(2, "Group Profit At Sampled Dates"),
        Paragraph(f"Mean rolling profit per mature vehicle at {len(samples)} sampled snapshot dates ({cats[0]} to {cats[-1]}); each "
                  "column is an independent point-in-time reading of a rolling window and the vehicle set changes between dates "
                  "(purchases, sales). Values are never summed or averaged across dates."),
        Table(["Model [Carrier]"] + cats, rows, ["left"] + ["right"] * len(cats)),
        Paragraph("* n<3 mature vehicles at that date. '-' = no mature vehicle of that group at that date (unknown, not zero)."),
    ]
    complete = [(k, [p[k]["mean"] for p in per_sample]) for k, _ in picks
                if all(k in p and p[k]["mature"] > 0 for p in per_sample)]
    if complete:
        blocks.append(Chart("line", "Mean rolling profit per mature vehicle at sampled dates (groups present at every date)",
                            cats, [(k, [float(_money(v)) for v in vals]) for k, vals in complete]))
    movers = []
    for k in sorted(per_sample[-1]):
        a, b = per_sample[0].get(k), per_sample[-1][k]
        if a and a["mature"] >= MIN_SAMPLE and b["mature"] >= MIN_SAMPLE:
            movers.append((b["mean"] - a["mean"], k, a, b))
    movers.sort(key=lambda t: (t[0], t[1]))
    if movers:
        picks_m = [m for m in movers if m[0] < 0][:4] + [m for m in reversed(movers) if m[0] > 0][:4]
        if picks_m:
            blocks.append(Heading(3, f"Largest Changes Between {cats[0]} and {cats[-1]} (groups with n>={MIN_SAMPLE} at both dates)"))
            blocks.append(Table(["Model [Carrier]", f"Mean at {cats[0]}", f"n", f"Mean at {cats[-1]}", "n ", "Change"],
                                [[k, _money(a["mean"]), a["mature"], _money(b["mean"]), b["mature"], _money(d)] for d, k, a, b in picks_m],
                                ["left", "right", "right", "right", "right", "right"]))
            blocks.append(Paragraph("Two point readings of a rolling one-year window: a drop can mean fewer or weaker recent months replacing "
                                    "strong old ones, a changed route, or a different vehicle mix; it is not a measured per-period income."))
    return blocks


def _line_loads(snaps: list[Snapshot]) -> dict[int, list[float]]:
    loads: dict[int, list[float]] = defaultdict(list)
    for s in snaps[-LOAD_HISTORY:]:
        for line in s.lines:
            load = analysis.line_load(line)
            if load is not None:
                loads[line["id"]].append(load)
    return loads


def _fit_section(latest: Snapshot, recs: list[dict[str, Any]], snaps: list[Snapshot], catalog: Snapshot | None) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Fit Checks: Cargo Match and Size vs Line Load")]
    thresholds = analysis.Thresholds()
    year = _game_year(latest)
    cat_by_res = {m.get("res"): m for m in (catalog.catalog if catalog else []) if m.get("res")}

    # -- cargo / model mismatch (stored evidence only)
    flagged: list[list[Any]] = []
    checked = 0
    for r in recs:
        raw, cargo_ids = r["raw"], r["cargo_ids"]
        if not cargo_ids:
            continue
        checked += 1
        reasons = []
        can = raw.get("canCarry")
        if isinstance(can, list) and can and any(c not in can for c in cargo_ids):
            reasons.append("configured cargo not in the vehicle's own canCarry list")
        for mid in r["models"]:
            cat = cat_by_res.get((latest.models.get(mid) or {}).get("res"))
            if cat and (cat.get("capacity") or []) and all(_catalog_capacity(cat, c) <= 0 for c in cargo_ids):
                reasons.append(f"catalog lists no capacity for {_cargo_label(latest, cargo_ids)} on {_model_name(latest, mid)}")
        if reasons:
            flagged.append([r["name"], r["line"] or "Unassigned", r["model"], r["cargo"], "; ".join(sorted(set(reasons)))])
    blocks.append(Heading(3, "Cargo / Model Mismatch"))
    if flagged:
        blocks.append(Table(["Vehicle", "Line", "Model", "Configured Cargo", "Evidence"], flagged[:25]))
        if len(flagged) > 25:
            blocks.append(Paragraph(f"{len(flagged) - 25} further flagged vehicles omitted."))
    else:
        blocks.append(Paragraph(f"No mismatch found among {checked} vehicles with a stored load configuration (checked against each "
                                "vehicle's canCarry list and, where the model matches the stored catalog, the catalog capacity entries)."))
    issue_rows = []
    for line in latest.lines:
        for issue in line.get("issues") or []:
            if issue.get("type") in ISSUE_TYPES:
                issue_rows.append([line.get("name") or f"Line #{line['id']}", issue.get("type"), issue.get("stopIndex"),
                                   issue.get("cargo")])
    if issue_rows:
        blocks.append(Table(["Line", "Game-reported issue", "Stop index", "Cargo index (base unverified)"], issue_rows[:25]))
    else:
        blocks.append(Paragraph("No game-reported VehicleUseless / NoVehicleToLoadCargo / LineCargoConfig issues in the latest snapshot."))

    # -- size vs sustained load
    loads = _line_loads(snaps)
    used_snaps = snaps[-LOAD_HISTORY:]
    by_line: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for r in recs:
        if r["line_id"] is not None:
            by_line[r["line_id"]].append(r)
    high, low = [], []
    for line in latest.lines:
        series = loads.get(line["id"], [])
        vehicles = by_line.get(line["id"], [])
        if len(series) < MIN_LOAD_SAMPLES or not vehicles:
            continue
        med = statistics.median(series)
        caps = [r["capacity"] for r in vehicles if r["capacity"]]
        models = sorted({_model_label(r["carrier"], r["model"]) for r in vehicles})
        row = [line.get("name") or f"Line #{line['id']}", len(vehicles), "; ".join(models), round(statistics.median(caps)) if caps else None,
               f"{med * 100:.0f}% ({min(series) * 100:.0f}-{max(series) * 100:.0f}%, n={len(series)})", _money(line.get("profitYear"))]
        if med >= thresholds.overloaded_load and len(vehicles) >= thresholds.underused_min_vehicles:
            high.append((med, row))
        elif med <= thresholds.underused_load and len(vehicles) >= thresholds.underused_min_vehicles:
            low.append((med, row))
    cols = ["Line", "Vehicles", "Models", "Per-vehicle capacity (median)", "Load across samples: median (range)", "Line rolling profit"]
    align = ["left", "right", "left", "right", "right", "right"]
    blocks.append(Heading(3, "Sustained High Load (Possible Undersizing)"))
    if high:
        high.sort(key=lambda t: (-t[0], str(t[1][0])))
        blocks.append(Table(cols, [r for _, r in high[:12]], align))
        blocks.append(Paragraph(f"{len(high)} lines (2+ vehicles) at or above {thresholds.overloaded_load:.0%} median sampled load; top {min(12, len(high))} shown."))
    else:
        blocks.append(Paragraph(f"No multi-vehicle line has median sampled load >= {thresholds.overloaded_load:.0%} across at least {MIN_LOAD_SAMPLES} samples."))
    blocks.append(Heading(3, "Sustained Low Load (Possible Oversizing)"))
    if low:
        low.sort(key=lambda t: (t[0], str(t[1][0])))
        blocks.append(Table(cols, [r for _, r in low[:12]], align))
        blocks.append(Paragraph(f"{len(low)} lines (2+ vehicles) at or below {thresholds.underused_load:.0%} median sampled load; top {min(12, len(low))} shown."))
    else:
        blocks.append(Paragraph(f"No multi-vehicle line has median sampled load <= {thresholds.underused_load:.0%} across at least {MIN_LOAD_SAMPLES} samples."))
    first, last = (used_snaps[0].date_label, used_snaps[-1].date_label) if used_snaps else ("-", "-")
    blocks.append(Note("Evidence Limit", f"Load is instantaneous occupancy over a line's full capacity; here the median of up to "
                                         f"{LOAD_HISTORY} snapshots ({first} to {last}) is used, and those snapshots cluster in time. "
                                         "One-way freight lines carry cargo in only one direction, so low load can be structural "
                                         "[INFERENCE]; a high load does not by itself prove demand exceeds capacity. Hypotheses to "
                                         "test, not conclusions: add vehicles or test a larger model on high-load lines; test fewer "
                                         "vehicles or a smaller model on low-load lines."))
    _ = year  # year is used by the swap section; kept here to document shared inputs
    return blocks


def _swap_section(latest: Snapshot, model_recs: dict[Any, list[dict[str, Any]]], groups: dict[Any, dict[str, Any]],
                  catalog: Snapshot | None, snaps: list[Snapshot]) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Suggested Swaps (Hypotheses to Test)")]
    weak = [(k, s) for k, s in groups.items()
            if s["mature"] >= MIN_SAMPLE and (s["median"] < 0 or (s["loss_share"] or 0) >= 0.4)]
    weak.sort(key=lambda kv: (kv[1]["mean"], kv[0]))
    weak = weak[:SWAP_GROUPS]
    if not weak:
        return blocks + [Paragraph(f"No model group with at least {MIN_SAMPLE} mature vehicles is loss-making (median < 0) or has a "
                                   "loss share of 40% or more, so no swap hypothesis is generated.")]
    if catalog is None or not catalog.catalog:
        return blocks + [Note("Insufficient Data", "No stored catalog snapshot: replacement candidates cannot be listed. The catalog is "
                                                    "collected only in start/request snapshots.")]
    units = catalog.meta.get("verifiedUnits") or {}
    speed_verified = units.get("topSpeed") == "m/s"
    cost_verified = units.get("runningCosts") == "currency/year"
    year = _game_year(latest)
    loads = _line_loads(snaps)
    blocks.append(Paragraph(
        f"Weak groups: at least {MIN_SAMPLE} mature vehicles and either median profit below 0 or a loss share of 40% or more. "
        f"Catalog sampled {catalog.date_label} (production status judged against game year {year if year is not None else 'unknown'}). "
        "Candidates are catalog models of the same carrier, in production, that list capacity for the vehicle's configured cargo, "
        "ordered by capacity per raw running cost. Ratios compare each candidate with the current model in the same raw units; no "
        "unit conversion, payback or profit forecast is made."
    ))
    cat_by_res = {m.get("res"): m for m in catalog.catalog if m.get("res")}
    evidence_rows: list[list[Any]] = []
    rows: list[list[Any]] = []
    notes: list[str] = []
    for label, st in weak:
        recs = model_recs[label]
        mature = [r for r in recs if _is_mature(r)]
        line_loads = [statistics.median(loads[r["line_id"]]) for r in mature
                      if r["line_id"] in loads and len(loads[r["line_id"]]) >= MIN_LOAD_SAMPLES]
        load_cell = f"{statistics.median(line_loads) * 100:.0f}%" if line_loads else None
        if any(r["parts"] > 1 for r in recs):
            notes.append(f"{label}: multi-part consist - locomotive/wagon replacement depends on the whole consist and is not assessed.")
            continue
        cargo_sets = Counter(r["cargo_ids"] for r in mature if r["cargo_ids"])
        if not cargo_sets:
            notes.append(f"{label}: no stored load configuration, so the cargo to match is unknown.")
            continue
        cargo_ids = cargo_sets.most_common(1)[0][0]
        if len(cargo_ids) != 1:
            notes.append(f"{label}: vehicles are configured for several cargos at once; single-cargo candidates are not proposed.")
            continue
        cargo_id = cargo_ids[0]
        carrier = recs[0]["carrier"]
        current_model_id = recs[0]["models"][0] if recs[0]["models"] else None
        current_model = latest.models.get(current_model_id) or {}
        current_cat = cat_by_res.get(current_model.get("res"))
        caps = [r["capacity"] for r in mature if r["capacity"]]
        current_cap = statistics.median(caps) if caps else None
        if current_cap is not None and float(current_cap).is_integer():
            current_cap = int(current_cap)
        cur_price, cur_run = current_model.get("price"), current_model.get("runningCosts")
        cur_speed = current_cat.get("topSpeed") if current_cat else None
        cur_life = current_model.get("lifespan")
        cargo_name = latest.cargo(cargo_id)
        evidence_rows.append([label, cargo_name, st["mature"], _money(st["mean"]), _money(st["median"]), _fmt_pct(st["loss_share"]),
                              load_cell, current_cap, cur_life if isinstance(cur_life, (int, float)) else None,
                              "In stored catalog" if current_cat else "Not in stored catalog (retired or absent)"])
        candidates = []
        for m in catalog.catalog:
            if m.get("carrier") != carrier or m.get("res") == current_model.get("res") or not _in_production(m, year):
                continue
            cap = _catalog_capacity(m, cargo_id)
            run = m.get("runningCosts")
            if cap <= 0 or not isinstance(run, (int, float)) or run <= 0:
                continue
            candidates.append((cap / run, m, cap))
        candidates.sort(key=lambda t: (-t[0], str(t[1].get("name") or "")))
        if not candidates:
            rows.append([label, "No in-production catalog model lists capacity for this cargo", None, None, None, None, None, None, None])
            continue
        for _, m, cap in candidates[:SWAP_CANDIDATES]:
            life = m.get("lifespan")
            cname = m.get("name") or m.get("res") or f"Model #{m.get('id')}"
            own = groups.get(_model_label(carrier, cname))
            if own is None:
                own_cell = "Not in fleet"
            elif own["mature"]:
                own_cell = f"n={own['mature']}, mean {_money(own['mean']):,}" + (" (small sample)" if own["mature"] < MIN_SAMPLE else "")
            else:
                own_cell = f"{own['young']} young only"
            rows.append([
                label, cname, f"{cap:g}", _ratio_cell(cap, current_cap), _ratio_cell(m.get("topSpeed"), cur_speed),
                _ratio_cell(m.get("price"), cur_price), _ratio_cell(m.get("runningCosts"), cur_run),
                life if isinstance(life, (int, float)) else None, own_cell,
            ])
    if evidence_rows:
        blocks.append(Heading(3, "Evidence: Weak Groups (Observations)"))
        blocks.append(Table(["Weak group", "Configured cargo", "Mature n", "Mean profit/vehicle", "Median", "Loss-making",
                             "Median load of its lines (sampled)", "Current capacity (median)", "Current lifespan (raw)", "Catalog match"],
                            evidence_rows, ["left", "left", "right", "right", "right", "right", "right", "right", "right", "left"]))
    if rows:
        blocks.append(Heading(3, "Candidates (Hypotheses)"))
        blocks.append(Table(["Weak group", "Candidate model", "Candidate capacity", "Capacity ratio", "Top speed ratio", "Price ratio",
                             "Running cost ratio", "Candidate lifespan (raw)", "Candidate in own fleet (mature, observed)"],
                            rows, ["left", "left", "right", "right", "right", "right", "right", "right", "left"]))
        blocks.append(Paragraph("Ratios are candidate / current (x1.00 = equal). Compare 'Candidate lifespan (raw)' with 'Current lifespan "
                                "(raw)' in the evidence table; lifespan units are unverified, so no age/expiry claim is made."))
    for n in notes:
        blocks.append(Paragraph(n))
    unit_note = ("Top speed is labelled m/s by verifiedUnits." if speed_verified else "Top speed unit unverified.") + " " + (
        "Running costs are labelled currency/year by verifiedUnits." if cost_verified else "Running-cost unit unverified.")
    blocks.append(Note("What Is Missing", "These are hypotheses, not recommendations. Not known from the data: route length and terrain "
                                          "per line, whether a candidate suits the road/track/airport/dock in use, loading time, "
                                          "the candidate's real earnings, the vehicle price factor, resale value, and whether rolling "
                                          "profit already nets out running costs. Ratios of 'x1.00' mean equal raw values; '-' means "
                                          "a value (current model not in the stored catalog, or field absent) is unknown. " + unit_note +
                                          " Manual test in game: trial one candidate on one weak line and compare after the rolling "
                                          "window has advanced."))
    return blocks


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def build(store: Store, thresholds: analysis.Thresholds | None = None) -> ReportDocument:
    mature = (thresholds or analysis.Thresholds()).mature_years
    latest = store.latest()
    if latest is None:
        raise ValueError("No snapshot found. Load a save with the bridge enabled and run tf3c refresh.")
    snaps = [s for s in store.snapshots() if s.game_time <= latest.game_time] or [latest]
    catalog = store.latest_with_catalog(game_time=latest.game_time)

    tpy, tpy_note = _ticks_per_year(snaps)
    recs = _records(latest, tpy, mature)
    model_recs = _group_by(recs, lambda r: _model_label(r["carrier"], r["model"]))
    groups = {k: _stats(v) for k, v in model_recs.items()}

    header = _base_header(latest, len(snaps))
    header.insert(3, ("Sample Coverage", f"{snaps[0].date_label} to {snaps[-1].date_label}; point-in-time snapshots, not continuous telemetry"))
    header.insert(4, ("Catalog Sample", catalog.date_label if catalog else "None stored"))
    header.append(("Age Scale", f"Vehicle age in calendar years; {tpy_note}"))
    header.append(("Vehicle Scope", f"{len(recs)} vehicles analysed from the latest snapshot; mature = age >= {mature:g} game year"))

    blocks: list[Any] = []
    blocks += _summary(recs, groups, latest)
    blocks += _carrier_section(recs)
    blocks += _model_section(recs, groups, model_recs)
    blocks += _cargo_section(recs)
    blocks += _age_section(recs, mature)
    blocks += _head_to_head(recs)
    blocks += _trend_section(snaps, groups, tpy, mature)
    blocks += _fit_section(latest, recs, snaps, catalog)
    blocks += _swap_section(latest, model_recs, groups, catalog, snaps)
    blocks.append(Note("Method And Limits",
                       "profitYear is a rolling game-year figure per vehicle; per-vehicle values are only combined across distinct "
                       f"vehicles within one snapshot. Vehicles younger than {mature:g} game year have partial windows and are kept out of "
                       "rankings. Vehicle profit mixes the vehicle's quality with the route it runs; use the same-line comparison "
                       "to separate them. transportedYear is not used (accounting unverified). Names come from the game and are "
                       "shown as stored."))
    return ReportDocument("vehicle-roi", "Vehicle ROI Report", header, blocks)
