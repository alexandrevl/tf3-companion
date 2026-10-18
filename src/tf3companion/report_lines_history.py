"""Per-line history report: profit trajectories, fleet changes, occupancy samples and trend classes.

Every number is a point observation from one snapshot. Rolling ``profitYear`` values are compared
(medians of early vs recent samples) but never summed or presented as calendar income.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from statistics import median
from typing import Any

from . import analysis
from .reports import Chart, Heading, Note, Paragraph, ReportDocument, Table, _base_header, _fmt_pct
from .snapshot import Snapshot
from .store import Store

# ---------------------------------------------------------------------------
# Classification parameters (printed verbatim in the report)
# ---------------------------------------------------------------------------

MIN_POINTS = 5            # profit samples needed inside the evaluation window
MAX_K = 6                 # samples per early/recent group (K = min(MAX_K, max(2, n // 3)))
REL_THRESHOLD = 0.15      # change must exceed 15% of the larger of the two medians
NOISE_FACTOR = 2.0        # ...and 2 x the median absolute deviation of the window samples
FLOOR_SHARE = 0.02        # ...and 2% of the median |profit| across all current lines
LONG_HISTORY_YEARS = 1.5  # with at least this much history, evaluate only the last year
MAX_SAMPLES = 12          # sparkline / chart / occupancy sample points
TABLE_CAP = 15
SPARK_CAP = 60
EVENT_CAP = 25
FOLLOWUP_CAP = 15

CLASSES = ("deteriorating", "improving", "stable", "too new", "insufficient data")
_BLOCKS = "▁▂▃▄▅▆▇█"


@dataclass
class _Pt:
    gt: int
    date: str
    profit: int | None
    transported: int | None
    rate: int | None
    vehicles: int | None


@dataclass
class _Line:
    id: int
    name: str
    pts: list[_Pt]
    in_latest: bool = False
    carrier: str | None = None
    cls: str = "insufficient data"
    reason: str = ""
    early: float | None = None
    recent: float | None = None
    delta: float | None = None
    threshold: float | None = None
    mad: float | None = None
    k: int = 0
    n_window: int = 0
    maturity: float | None = None
    window_pts: list[_Pt] = field(default_factory=list)
    occ: list[tuple[str, float]] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    @property
    def first(self) -> _Pt:
        return self.pts[0]

    @property
    def last(self) -> _Pt:
        return self.pts[-1]

    @property
    def profits(self) -> list[_Pt]:
        return [p for p in self.pts if p.profit is not None]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _num(v: float | None) -> str:
    return "-" if v is None else f"{round(v):,}"


def _signed(v: float | None) -> str:
    if v is None:
        return "-"
    r = round(v)
    return f"{'+' if r > 0 else ''}{r:,}"


def _spread(values: list[int | float], limit: int = MAX_SAMPLES) -> list[int | float]:
    """Evenly pick at most ``limit`` values by index, always keeping first and last."""
    if len(values) <= limit:
        return list(values)
    idx = sorted({round(i * (len(values) - 1) / (limit - 1)) for i in range(limit)})
    return [values[i] for i in idx]


def _spark(values: list[int | float]) -> str:
    vals = _spread(values)
    if not vals:
        return "-"
    lo, hi = min(vals), max(vals)
    if hi == lo:
        return _BLOCKS[3] * len(vals)
    return "".join(_BLOCKS[min(7, int((v - lo) / (hi - lo) * 8))] for v in vals)


def _med(values: list[int | float]) -> float | None:
    return float(median(values)) if values else None


def _detrended_mad(pts: list[_Pt], k: int) -> float:
    """Median absolute residual around the straight line joining the early and recent medians.

    A steady trend therefore adds no noise, while saw-tooth (lumpy income) series do.
    """
    xs = [float(p.gt) for p in pts]
    ys = [float(p.profit) for p in pts]
    x0, x1 = sum(xs[:k]) / k, sum(xs[-k:]) / k
    y0, y1 = median(ys[:k]), median(ys[-k:])
    slope = (y1 - y0) / (x1 - x0) if x1 > x0 else 0.0
    resid = [y - (y0 + slope * (x - x0)) for x, y in zip(xs, ys)]
    m = median(resid)
    return float(median(abs(r - m) for r in resid))


def _arrow(a: float | None, b: float | None) -> str:
    return f"{_num(a)} → {_num(b)}"


def _veh_arrow(line: _Line, since: int | None = None) -> str:
    pts = [p for p in line.pts if p.vehicles is not None and (since is None or p.gt >= since)]
    if not pts:
        return "-"
    return f"{pts[0].vehicles} → {pts[-1].vehicles}"


def _veh_net(line: _Line, since: int | None = None) -> int | None:
    pts = [p for p in line.pts if p.vehicles is not None and (since is None or p.gt >= since)]
    return pts[-1].vehicles - pts[0].vehicles if pts else None


def _evenly_pick_times(times: list[int], limit: int = MAX_SAMPLES) -> list[int]:
    return [int(t) for t in _spread(times, limit)]


# ---------------------------------------------------------------------------
# Data collection
# ---------------------------------------------------------------------------

def _collect(store: Store, latest: Snapshot) -> tuple[list[_Line], list[tuple[int, str]]]:
    """Return per-line series (one point per distinct sample date) and the sample (gt, date) list."""
    by_date: dict[str, int] = {}
    for row in store.company_history(limit=2**31 - 1):
        if row["game_time"] > latest.game_time:
            continue
        by_date[row["date_label"]] = max(by_date.get(row["date_label"], -1), row["game_time"])
    kept = {gt: date for date, gt in by_date.items()}
    samples = sorted(kept.items())
    ids = [r[0] for r in store.conn.execute(
        "SELECT DISTINCT line_id FROM line_history WHERE game_time <= ? ORDER BY line_id",
        (latest.game_time,),
    )]
    lines: list[_Line] = []
    for lid in ids:
        rows = [r for r in store.line_history(lid, limit=2**31 - 1)
                if r["game_time"] in kept and r["game_time"] <= latest.game_time]
        if not rows:
            continue
        pts = [_Pt(r["game_time"], kept[r["game_time"]], r["profit_year"], r["transported_year"], r["rate"], r["vehicles"]) for r in rows]
        name = next((r["name"] for r in reversed(rows) if r["name"]), None)
        lines.append(_Line(lid, name or f"Line #{lid}", pts))
    counts: dict[str, int] = {}
    for ln in lines:
        counts[ln.name] = counts.get(ln.name, 0) + 1
    for ln in lines:
        if counts[ln.name] > 1:
            ln.name = f"{ln.name} (#{ln.id})"
    return lines, samples


def _attach_latest(lines: list[_Line], latest: Snapshot, last_gt: int) -> None:
    for ln in lines:
        raw = latest.lines_by_id.get(ln.id)
        ln.in_latest = raw is not None and ln.last.gt == last_gt
        if ln.in_latest and raw is not None:
            ln.carrier = analysis.line_carrier(latest, raw)
            ln.issues = sorted({str(i.get("type")) for i in raw.get("issues") or [] if i.get("type")})


def _attach_occupancy(store: Store, lines: list[_Line], samples: list[tuple[int, str]]) -> int:
    picks = _evenly_pick_times([gt for gt, _ in samples])
    by_id = {ln.id: ln for ln in lines}
    used = 0
    for gt in picks:
        snap = store.snapshot_at_or_before(gt)
        if snap is None or snap.game_time != gt:
            continue
        used += 1
        for raw in snap.lines:
            load = analysis.line_load(raw)
            ln = by_id.get(raw["id"])
            if ln is not None and load is not None:
                ln.occ.append((snap.date_label, load))
    return used


def _year_ticks(first: Snapshot | None, latest: Snapshot) -> tuple[float, str]:
    """Game ticks per calendar year, calibrated from sample dates; meta.yearDuration is a fallback.

    On the real data meta.yearDuration is ~4x smaller than the tick span of a calendar year, so
    dividing tick differences by it overstates ages and elapsed time.
    """
    try:
        if first is not None and first.date and latest.date:
            d0 = _dt.date(first.date["year"], first.date["month"], min(first.date["day"], 28))
            d1 = _dt.date(latest.date["year"], latest.date["month"], min(latest.date["day"], 28))
            days = (d1 - d0).days
            ticks = latest.game_time - first.game_time
            if days >= 14 and ticks > 0:
                return ticks / days * 365.0, "calibrated from sample dates"
    except (ValueError, KeyError, TypeError):
        pass
    return float(latest.year_duration or 0), "meta.yearDuration (uncalibrated)"


def _classify(lines: list[_Line], latest: Snapshot, first_gt: int, last_gt: int, yd: float, mature: float) -> tuple[float, float, str]:
    span_years = (last_gt - first_gt) / yd if yd else 0.0
    long_hist = span_years >= LONG_HISTORY_YEARS
    window_start = last_gt - yd if long_hist else first_gt
    present = [abs(ln.last.profit) for ln in lines if ln.in_latest and ln.last.profit is not None]
    floor = FLOOR_SHARE * (median(present) if present else 0)
    for ln in lines:
        if not ln.in_latest:
            ln.cls, ln.reason = "insufficient data", "not in the latest snapshot (removed)"
            continue
        raw = latest.lines_by_id[ln.id]
        ages = []
        bought = [v["purchaseTime"] for v in latest.line_vehicles(raw) if v.get("purchaseTime") is not None]
        if bought and yd:
            ages.append((latest.game_time - min(bought)) / yd)
        if ln.first.gt > first_gt and yd:
            ages.append((last_gt - ln.first.gt) / yd)
        ln.maturity = max(ages) if ages else None
        ln.window_pts = [p for p in ln.pts if p.gt >= window_start and p.profit is not None]
        ln.n_window = len(ln.window_pts)
        if not raw.get("vehicles"):
            ln.cls, ln.reason = "insufficient data", "no vehicles on the line now"
        elif ln.maturity is not None and ln.maturity < mature:
            ln.cls = "too new"
            ln.reason = f"maturity proxy {ln.maturity:.2f} years (< {mature:g}); line creation date is unknown"
        elif ln.n_window < MIN_POINTS:
            ln.cls, ln.reason = "insufficient data", f"{ln.n_window} profit samples in window (need {MIN_POINTS})"
        else:
            values = [p.profit for p in ln.window_pts]
            ln.k = min(MAX_K, max(2, ln.n_window // 3))
            ln.early, ln.recent = _med(values[:ln.k]), _med(values[-ln.k:])
            ln.mad = _detrended_mad(ln.window_pts, ln.k)
            ln.delta = ln.recent - ln.early
            ln.threshold = max(REL_THRESHOLD * max(abs(ln.early), abs(ln.recent)), NOISE_FACTOR * ln.mad, floor)
            ln.cls = "improving" if ln.delta > ln.threshold else "deteriorating" if ln.delta < -ln.threshold else "stable"
            ln.reason = f"change {_signed(ln.delta)} vs threshold ±{_num(ln.threshold)}"
    window_label = (f"last year (since {_date_of(lines, window_start)})" if long_hist
                    else "entire stored history")
    return span_years, floor, window_label


def _date_of(lines: list[_Line], gt: int) -> str:
    dates = sorted({(p.gt, p.date) for ln in lines for p in ln.pts})
    for g, d in dates:
        if g >= gt:
            return d
    return dates[-1][1] if dates else "-"


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

def _occ_text(ln: _Line) -> tuple[str, str, int]:
    if not ln.occ:
        return "-", "-", 0
    vals = [v for _, v in ln.occ]
    return _fmt_pct(sum(vals) / len(vals)), _fmt_pct(vals[-1]), len(vals)


def _trend_rows(lines: list[_Line]) -> list[list[Any]]:
    rows = []
    for ln in lines:
        mean, latest_occ, n = _occ_text(ln)
        rows.append([
            ln.name, ln.carrier or "-", _veh_arrow(ln, ln.window_pts[0].gt if ln.window_pts else None),
            _arrow(ln.early, ln.recent), _signed(ln.delta), _num(ln.threshold),
            f"{_arrow(_med([p.transported for p in ln.window_pts[:ln.k] if p.transported is not None]), _med([p.transported for p in ln.window_pts[-ln.k:] if p.transported is not None]))}",
            f"{_arrow(_med([p.rate for p in ln.window_pts[:ln.k] if p.rate is not None]), _med([p.rate for p in ln.window_pts[-ln.k:] if p.rate is not None]))}",
            f"{mean} / {latest_occ} (n={n})",
        ])
    return rows


_TREND_COLS = ["Line", "Carrier", "Vehicles (window)", "Profit: early → recent median", "Change", "Noise threshold",
               "Transported (unverified): early → recent", "Rate: early → recent", "Occupancy sample mean / latest"]
_TREND_ALIGN = ["left", "left", "right", "right", "right", "right", "right", "right", "right"]


def _rule_blocks(window_label: str, floor: float, mature: float) -> list[Any]:
    return [
        Heading(2, "Classification Rule"),
        Paragraph(
            "Applies to lines present in the latest snapshot. Samples are collapsed to one per game date. "
            f"Evaluation window: {window_label} (the last year is used once history reaches "
            f"{LONG_HISTORY_YEARS:g} years; before that all stored samples are used)."),
        Table(["Step", "Rule", "Result"], [
            [1, "No vehicles on the line in the latest snapshot", "insufficient data"],
            [2, f"Maturity proxy < {mature:g} year. Proxy = max(age of its oldest current vehicle, time since the line first "
                "appeared in stored history if absent from the first snapshot). This does not establish line age or a partial profit window.", "too new"],
            [3, f"Fewer than {MIN_POINTS} non-missing profit samples in the window", "insufficient data"],
            [4, f"Otherwise K = min({MAX_K}, max(2, n // 3)); early = median of the first K window samples, "
                "recent = median of the last K; change = recent - early.", "-"],
            [5, f"Threshold = max({REL_THRESHOLD:.0%} of the larger of |early|, |recent|; {NOISE_FACTOR:g} x noise (median absolute deviation of the window samples around the straight line "
                f"joining the early and recent medians, so a steady trend is not noise); {FLOOR_SHARE:.0%} of the median |profit| across current lines = {_num(floor)}).", "-"],
            [6, "change > threshold / change < -threshold / otherwise", "improving / deteriorating / stable"],
        ], ["right", "left", "left"]),
        Note("Why a noise term", "Rolling profit is lumpy: one large delivery entering or leaving the one-year window can move a "
                                 "line's value a lot between consecutive samples. The MAD term keeps such saw-tooth lines from being "
                                 "labelled as trends. Medians, never sums, are used; values are point observations."),
    ]


def _summary(lines: list[_Line]) -> list[Any]:
    cur = [ln for ln in lines if ln.in_latest]
    counts = {c: sum(1 for ln in cur if ln.cls == c) for c in CLASSES}
    rows = []
    for c in CLASSES:
        members = [ln.last.profit for ln in cur if ln.cls == c and ln.last.profit is not None]
        rows.append([c, counts[c], _num(median(members)) if members else "-"])
    return [
        Heading(2, "Trend Class Summary"),
        Table(["Class", "Lines", "Median of latest profit point per line"], rows, ["left", "right", "right"]),
        Chart("bar", "Lines per Trend Class", list(CLASSES), [("Lines", [float(counts[c]) for c in CLASSES])]),
    ]


def _trend_section(lines: list[_Line], cls: str) -> list[Any]:
    sel = [ln for ln in lines if ln.in_latest and ln.cls == cls]
    sel.sort(key=lambda ln: ln.delta or 0, reverse=(cls == "improving"))
    blocks: list[Any] = [Heading(2, f"{cls.capitalize()} Lines ({len(sel)})")]
    if not sel:
        return blocks + [Paragraph(f"No lines are classified as {cls} under the rule above.")]
    blocks.append(Table(_TREND_COLS, _trend_rows(sel[:TABLE_CAP]), _TREND_ALIGN))
    if len(sel) > TABLE_CAP:
        blocks.append(Paragraph(f"{len(sel) - TABLE_CAP} further {cls} lines omitted (ranked by size of change)."))
    return blocks


def _best_worst(lines: list[_Line]) -> list[Any]:
    cur = [ln for ln in lines if ln.in_latest and ln.last.profit is not None]
    if not cur:
        return [Heading(2, "Best and Worst Lines Now"), Paragraph("Insufficient data: no line has a profit sample.")]
    ranked = sorted(cur, key=lambda ln: (-ln.last.profit, ln.name))
    top = ranked[:TABLE_CAP]
    bottom = [ln for ln in ranked[::-1] if ln not in top][:TABLE_CAP]

    def rows(sel: list[_Line]) -> list[list[Any]]:
        out = []
        for ln in sel:
            prof = ln.profits
            hi = max(prof, key=lambda p: (p.profit, -p.gt))
            lo = min(prof, key=lambda p: (p.profit, p.gt))
            mean, latest_occ, n = _occ_text(ln)
            out.append([ln.name, ln.carrier or "-", ln.cls, _veh_arrow(ln), ln.first.profit, f"{_num(hi.profit)} ({hi.date})",
                        f"{_num(lo.profit)} ({lo.date})", ln.last.profit, f"{mean} / {latest_occ} (n={n})", _spark([p.profit for p in prof])])

        return out

    cols = ["Line", "Carrier", "Class", "Vehicles (first → now)", "First sample", "Highest sample", "Lowest sample", "Now",
            "Occupancy sample mean / latest", "Path"]
    al = ["left", "left", "left", "right", "right", "right", "right", "right", "right", "left"]
    blocks: list[Any] = [
        Heading(2, "Best and Worst Lines Now"),
        Paragraph("Ranked by the latest rolling-year profit point. 'Path' is a text sparkline of that line's samples "
                  f"(at most {MAX_SAMPLES}, scaled per line between its own minimum and maximum)."),
        Heading(3, f"Top {len(top)}"), Table(cols, rows(top), al),
    ]
    if bottom:
        blocks += [Heading(3, f"Bottom {len(bottom)}"), Table(cols, rows(bottom), al)]
    return blocks


def _charts(lines: list[_Line], samples: list[tuple[int, str]]) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Trajectories of Top and Bottom Lines")]
    picks = _evenly_pick_times([gt for gt, _ in samples])
    if len(picks) < 2:
        return blocks + [Paragraph("Insufficient data: at least two sample dates are needed for trajectory charts.")]
    dates = [dict(samples)[g] for g in picks]
    full = []
    for ln in lines:
        if not ln.in_latest or ln.last.profit is None:
            continue
        by_gt = {p.gt: p.profit for p in ln.pts}
        if all(by_gt.get(g) is not None for g in picks):
            full.append((ln, [float(by_gt[g]) for g in picks]))
    if not full:
        return blocks + [Paragraph("Insufficient data: no current line has a profit sample at every charted date.")]
    full.sort(key=lambda t: (-t[1][-1], t[0].name))
    n = min(5, len(full) // 2) or len(full)
    groups = [("Top lines by latest profit", full[:n])]
    if len(full) > n:
        groups.append(("Bottom lines by latest profit", full[-n:] if len(full) - n >= n else full[n:]))
    for title, group in groups:
        names = [ln.name for ln, _ in group]
        blocks += [
            Heading(3, title),
            Chart("line", title.replace(" by latest profit", ""), dates, [(ln.name, vals) for ln, vals in group]),
            Table(["Sample date"] + names, [[d] + [_num(vals[i]) for _, vals in group] for i, d in enumerate(dates)],
                  ["left"] + ["right"] * len(group)),
        ]
    omitted = sum(1 for ln in lines if ln.in_latest) - len(full)
    blocks.append(Paragraph(f"Only lines with a sample at every charted date are eligible ({omitted} current lines excluded, e.g. newer lines). "
                            "Series order in the chart follows the table columns; Markdown charts do not label series."))
    return blocks


def _vehicle_events(lines: list[_Line], floor: float) -> list[dict[str, Any]]:
    events = []
    for ln in lines:
        idx = [i for i in range(1, len(ln.pts)) if ln.pts[i].vehicles is not None and ln.pts[i - 1].vehicles is not None
               and ln.pts[i].vehicles != ln.pts[i - 1].vehicles]
        ppts = [p for p in ln.pts if p.profit is not None]
        mad = _detrended_mad(ppts, min(MAX_K, max(2, len(ppts) // 3))) if len(ppts) >= 5 else 0.0
        for n, i in enumerate(idx):
            end = idx[n + 1] if n + 1 < len(idx) else len(ln.pts)
            before = [p.profit for p in ln.pts[max(0, (idx[n - 1] if n else 0)):i] if p.profit is not None][-3:]
            after = [p.profit for p in ln.pts[i:end] if p.profit is not None][-3:]
            seg = end - i
            b, a = _med(before), _med(after)
            v0, v1 = ln.pts[i - 1].vehicles, ln.pts[i].vehicles
            verdict, delta, thr = "too soon (<2 samples after)", None, None
            if v0 == 0:
                verdict = "line start (no vehicles before)"
            elif b is not None and a is not None and len(before) >= 2 and seg >= 2:
                delta = a - b
                thr = max(REL_THRESHOLD * max(abs(a), abs(b)), NOISE_FACTOR * mad, floor)
                verdict = "profit rose" if delta > thr else "profit fell" if delta < -thr else "within noise"
            elif b is None or len(before) < 2:
                verdict = "too soon (<2 samples since previous change)"
            events.append({"line": ln, "date": ln.pts[i].date, "v0": v0, "v1": v1, "before": b, "after": a, "delta": delta,
                           "threshold": thr, "seg": seg, "verdict": verdict,
                           "ppv": f"{_num(b / v0 if b is not None and v0 else None)} → {_num(a / v1 if a is not None and v1 else None)}"})
    return events


def _vehicles_section(events: list[dict[str, Any]]) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Vehicle Count Changes vs Profit")]
    if not events:
        return blocks + [Paragraph("No vehicle-count change was observed on any line between stored samples.")]
    order = {"profit fell": 0, "profit rose": 1, "within noise": 2, "line start (no vehicles before)": 4}
    ranked = sorted(events, key=lambda e: (order.get(e["verdict"], 3), -abs(e["delta"] or 0), e["line"].name, e["date"]))
    shown = ranked[:EVENT_CAP]
    adds = sum(1 for e in events if e["v1"] > e["v0"])
    blocks += [
        Paragraph(f"{len(events)} vehicle-count changes across {len({e['line'].id for e in events})} lines ({adds} additions, "
                  f"{len(events) - adds} reductions). Before/after profit = median of up to 3 samples before the change and the last up to 3 "
                  "samples of the stretch before the next change; verdict uses the same noise rule as the classification."),
        Table(["Line", "Date seen", "Vehicles", "Profit before", "Profit after", "Change", "Samples after", "Profit per vehicle before → after", "Verdict"],
              [[e["line"].name, e["date"], f"{e['v0']} → {e['v1']}", _num(e["before"]), _num(e["after"]), _signed(e["delta"]), e["seg"], e["ppv"], e["verdict"]]
               for e in shown], ["left", "left", "right", "right", "right", "right", "right", "right", "left"]),
    ]
    if len(ranked) > len(shown):
        blocks.append(Paragraph(f"{len(ranked) - len(shown)} further changes omitted (ranked: profit fell, profit rose, within noise, too soon)."))
    blocks.append(Note("Limit", "The date is the first sample showing the new count, not the purchase date. Rolling profit blends a new vehicle in "
                                "gradually and purchase cost is not part of it, so early 'after' values understate the long-run effect."))
    return blocks


def _created_removed(lines: list[_Line], samples: list[tuple[int, str]]) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Lines Created and Removed")]
    if len(samples) < 2:
        return blocks + [Paragraph("Insufficient data: two or more samples are needed to detect created or removed lines.")]
    first_gt, last_gt = samples[0][0], samples[-1][0]
    dates = [d for _, d in samples]
    gts = [g for g, _ in samples]
    created = [ln for ln in lines if ln.first.gt > first_gt]
    removed = [ln for ln in lines if ln.last.gt < last_gt]

    def before(gt: int) -> str:
        return dates[gts.index(gt) - 1]

    def after(gt: int) -> str:
        return dates[gts.index(gt) + 1]

    blocks.append(Paragraph(f"Compared with the first sample ({dates[0]}): {len(created)} lines appeared and {len(removed)} disappeared "
                            f"by the latest sample ({dates[-1]}). A line is 'removed' if it is absent from the latest snapshot; "
                            "exact dates are bounded by the sample gap."))
    for title, sel, kind in (("Created", created, "c"), ("Removed", removed, "r")):
        if not sel:
            blocks.append(Paragraph(f"No {title.lower()} lines."))
            continue
        rows = []
        for ln in sorted(sel, key=lambda x: (x.first.gt if kind == "c" else x.last.gt, x.name))[:TABLE_CAP * 2]:
            if kind == "c":
                rows.append([ln.name, f"{before(ln.first.gt)} .. {ln.first.date}", ln.first.vehicles, ln.last.vehicles, ln.first.profit, ln.last.profit,
                             ln.cls if ln.in_latest else "-"])
            else:
                rows.append([ln.name, f"{ln.last.date} .. {after(ln.last.gt)}", ln.first.vehicles, ln.last.vehicles, ln.first.profit, ln.last.profit, "removed"])
        blocks += [Heading(3, f"{title} lines ({len(sel)})"),
                   Table(["Line", "Window of change (last absent/present .. first present/absent)", "Vehicles at first sight", "Vehicles at last sight",
                          "Profit at first sight", "Profit at last sight", "Class now"], rows, ["left", "left", "right", "right", "right", "right", "left"])]
        if len(sel) > TABLE_CAP * 2:
            blocks.append(Paragraph(f"{len(sel) - TABLE_CAP * 2} further {title.lower()} lines omitted."))
    blocks.append(Note("Limit", "Last-sight profit of a removed line is a rolling value at that sample, not what the line earned in total. "
                                "A line deleted and rebuilt gets a new id and appears as one removal plus one creation."))
    return blocks


def _compact(lines: list[_Line]) -> list[Any]:
    cur = [ln for ln in lines if ln.in_latest]
    blocks: list[Any] = [Heading(2, "Compact Trajectory Table")]
    if not cur:
        return blocks + [Paragraph("Insufficient data: no current lines.")]
    pri = {c: i for i, c in enumerate(CLASSES)}
    cur.sort(key=lambda ln: (pri[ln.cls], ln.delta if ln.cls == "deteriorating" and ln.delta is not None else
                             -(ln.delta or 0) if ln.cls == "improving" else -(ln.last.profit or 0), ln.name))
    shown = cur[:SPARK_CAP]
    rows = [[ln.name, ln.cls, _veh_arrow(ln), ln.first.profit, ln.last.profit, _signed(ln.delta), _spark([p.profit for p in ln.profits]),
             _spark([v for _, v in ln.occ])] for ln in shown]
    blocks += [
        Paragraph(f"One row per current line, grouped by class (deteriorating and improving first, largest change first). "
                  f"Sparklines use up to {MAX_SAMPLES} evenly spread samples, each line scaled between its own min and max, so heights "
                  "are comparable only within a row. Change is the window median change (blank when not classified)."),
        Table(["Line", "Class", "Vehicles (first → now)", "First profit", "Now", "Change", "Profit path", "Occupancy path"], rows,
              ["left", "left", "right", "right", "right", "right", "left", "left"]),
    ]
    if len(cur) > len(shown):
        blocks.append(Paragraph(f"{len(cur) - len(shown)} further lines omitted (lowest priority: stable, too new and insufficient data)."))
    return blocks


def _followups(lines: list[_Line], first_gt: int, events: list[dict[str, Any]]) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Suggested Manual Follow-ups")]
    rows: list[list[Any]] = []
    cur = [ln for ln in lines if ln.in_latest]

    def occ_phrase(ln: _Line) -> str:
        mean, last, n = _occ_text(ln)
        return f"occupancy samples mean {mean}, latest {last} (n={n}; instantaneous readings)"

    def win_veh(ln: _Line) -> int | None:
        return _veh_net(ln, ln.window_pts[0].gt if ln.window_pts else None)

    det = sorted((ln for ln in cur if ln.cls == "deteriorating"), key=lambda ln: ln.delta)
    for ln in [x for x in det if (win_veh(x) or 0) > 0][:5]:
        rows.append([ln.name, f"Profit median {_arrow(ln.early, ln.recent)} while vehicles went {_veh_arrow(ln, ln.window_pts[0].gt)}; {occ_phrase(ln)}.",
                     "Extra vehicles may be sharing a fixed demand instead of adding income; the rolling window also lags the purchase. Not proven.",
                     "Look at this line's vehicles and occupancy in the game; consider whether the newest vehicle is needed, then recheck after the profit window has advanced."])
    for ln in [x for x in det if (win_veh(x) or 0) <= 0][:5]:
        issues = ", ".join(ln.issues) if ln.issues else "none reported"
        rows.append([ln.name, f"Profit median {_arrow(ln.early, ln.recent)} with vehicles {_veh_arrow(ln, ln.window_pts[0].gt)} (no addition); {occ_phrase(ln)}; "
                              f"line issues now: {issues}.",
                     "Decline is not explained by fleet size; cargo supply, a competing line or vehicle ageing are candidates (unverified).",
                     "Inspect the served stops/industries (stock levels, production) and the line's issue list in the game."])
    imp = sorted((ln for ln in cur if ln.cls == "improving"), key=lambda ln: -ln.delta)
    for ln in imp:
        mean = sum(v for _, v in ln.occ) / len(ln.occ) if ln.occ else None
        if mean is not None and mean >= 0.8 and len(rows) < 40:
            rows.append([ln.name, f"Profit median {_arrow(ln.early, ln.recent)}, vehicles {_veh_arrow(ln, ln.window_pts[0].gt)}, occupancy sample mean {_fmt_pct(mean)}.",
                         "Rising profit with consistently full vehicles suggests capacity may be limiting; waiting cargo is not collected, so this is unconfirmed.",
                         "Candidate for testing one more vehicle or a larger model; compare against the vehicle catalog, then recheck this report."])
            if sum(1 for r in rows if r[2].startswith("Rising profit")) >= 4:
                break
    neg = sorted((ln for ln in cur if ln.cls in ("deteriorating", "stable", "improving") and ln.window_pts
                  and all(p.profit < 0 for p in ln.window_pts)), key=lambda ln: ln.last.profit)
    for ln in neg[:5]:
        rows.append([ln.name, f"Every window sample is negative (latest {_num(ln.last.profit)}, class {ln.cls}, vehicles {_veh_arrow(ln)}); {occ_phrase(ln)}.",
                     "Persistent loss in the sampled window; the maturity proxy does not rule out a start-up effect.",
                     "Decide whether to rework (route, vehicle model, vehicle count) or close it; check the lines report for finding codes first."])
    shown = rows[:FOLLOWUP_CAP]
    if not shown:
        return blocks + [Paragraph("No evidence-backed follow-up under the current rules (no sustained decline, no sustained loss, "
                                   "no full-and-rising lines). This is also the result when history is too short to classify lines.")]
    blocks.append(Table(["Line", "Observation", "Inference (hedged)", "Suggested manual check"], shown, ["left", "left", "left", "left"]))
    if len(rows) > len(shown):
        blocks.append(Paragraph(f"{len(rows) - len(shown)} further follow-ups omitted."))
    blocks.append(Paragraph("All changes are made by the player in the game; nothing here is applied automatically."))
    return blocks


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def build(store: Store, thresholds: analysis.Thresholds | None = None) -> ReportDocument:
    mature = (thresholds or analysis.Thresholds()).mature_years
    latest = store.latest()
    if latest is None:
        raise ValueError("No snapshot found. Load a save with the bridge enabled and run tf3c refresh.")
    lines, samples = _collect(store, latest)
    # The report is anchored on the newest stored game time, as other kinds do.
    latest = store.snapshot_at_or_before(samples[-1][0]) or latest
    first_gt, last_gt = samples[0][0], samples[-1][0]
    _attach_latest(lines, latest, last_gt)
    occ_snaps = _attach_occupancy(store, lines, samples)
    first_snap = store.snapshot_at_or_before(first_gt)
    year_ticks, clock_note = _year_ticks(first_snap, latest)
    span_years, floor, window_label = _classify(lines, latest, first_gt, last_gt, year_ticks, mature)
    events = _vehicle_events(lines, floor)

    header = _base_header(latest, len(samples))
    header += [
        ("Sample Period", f"{samples[0][1]} .. {samples[-1][1]} ({span_years:.2f} calendar years, {len(samples)} distinct sample dates)"),
        ("Lines Tracked", f"{len(lines)} ever seen, {sum(1 for ln in lines if ln.in_latest)} in the latest snapshot"),
        ("Evaluation Window", window_label),
        ("Time Basis", f"Years are calendar years; ticks per year {year_ticks:,.0f} {clock_note}. Snapshot meta.yearDuration is {latest.year_duration:,}."),
        ("Occupancy Samples", f"{occ_snaps} snapshots (up to {MAX_SAMPLES}, spread across the history)"),
    ]
    blocks: list[Any] = []
    if span_years < mature:
        blocks.append(Note("Coverage", f"Only {span_years:.2f} years of samples are stored. Each rolling-year profit value overlaps heavily with the "
                                       "others, so trends here are short-term movements, not year-over-year results. The report becomes more informative as "
                                       "snapshots accumulate across years."))
    if len(samples) < MIN_POINTS:
        blocks.append(Note("Insufficient data", f"Only {len(samples)} sample dates are stored; lines cannot be classified until at least {MIN_POINTS} exist."))
    blocks += _summary(lines)
    blocks += _rule_blocks(window_label, floor, mature)
    blocks += _followups(lines, first_gt, events)
    blocks += _trend_section(lines, "deteriorating")
    blocks += _trend_section(lines, "improving")
    blocks += _best_worst(lines)
    blocks += _charts(lines, samples)
    blocks += _vehicles_section(events)
    blocks += _created_removed(lines, samples)
    blocks += _compact(lines)
    blocks.append(Note("Measurement Limits", "Values are rolling-year point observations at sample dates, never summed. 'Transported' accounting is unverified; "
                                             "'rate' is the game's throughput estimate; occupancy is instantaneous at snapshot time. Missing values are "
                                             "unknown, not zero. Each stored save is assumed to be the same company."))
    return ReportDocument("lines-history", "Line History and Trend Report", header, blocks)
