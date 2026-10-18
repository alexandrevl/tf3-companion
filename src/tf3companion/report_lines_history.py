"""Per-line history report: profit trajectories, fleet changes, occupancy samples and trend classes.

Presentation over `LinesHistoryView`. Every number is a point observation from one snapshot. Rolling
``profitYear`` values are compared (medians of early vs recent samples) but never summed or presented
as calendar income.
"""

from __future__ import annotations

from typing import Any

from .analysis_views.lines_history import CLASSES, LinesHistoryView, LineTrajectory, spread
from .analysis_views.models import EvaluationContext
from .reports import Chart, Heading, Note, Paragraph, ReportDocument, Table, _base_header, _fmt_pct

MAX_SAMPLES = 12          # sparkline / chart sample points
TABLE_CAP = 15
SPARK_CAP = 60
EVENT_CAP = 25
FOLLOWUP_CAP = 15

_BLOCKS = "▁▂▃▄▅▆▇█"

_VERDICTS = {
    "profit-fell": "profit fell",
    "profit-rose": "profit rose",
    "within-noise": "within noise",
    "line-start": "line start (no vehicles before)",
    "too-soon-after": "too soon (<2 samples after)",
    "too-soon-before": "too soon (<2 samples since previous change)",
}


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _num(v: float | None) -> str:
    return "-" if v is None else f"{round(v):,}"


def _signed(v: float | None) -> str:
    if v is None:
        return "-"
    r = round(v)
    return f"{'+' if r > 0 else ''}{r:,}"


def _spark(values: list[int | float]) -> str:
    vals = spread(values, MAX_SAMPLES)
    if not vals:
        return "-"
    lo, hi = min(vals), max(vals)
    if hi == lo:
        return _BLOCKS[3] * len(vals)
    return "".join(_BLOCKS[min(7, int((v - lo) / (hi - lo) * 8))] for v in vals)


def _arrow(a: float | None, b: float | None) -> str:
    return f"{_num(a)} → {_num(b)}"


def _veh(first: int | None, last: int | None) -> str:
    return "-" if first is None else f"{first} → {last}"


def _occ_text(ln: LineTrajectory) -> tuple[str, str, int]:
    if not ln.occupancy:
        return "-", "-", 0
    return _fmt_pct(ln.occupancy_mean), _fmt_pct(ln.occupancy_latest), len(ln.occupancy)


def _profits(ln: LineTrajectory) -> list[int]:
    return [p.profit for p in ln.points if p.profit is not None]


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

_TREND_COLS = ["Line", "Carrier", "Vehicles (window)", "Profit: early → recent median", "Change", "Noise threshold",
               "Transported (unverified): early → recent", "Rate: early → recent", "Occupancy sample mean / latest"]
_TREND_ALIGN = ["left", "left", "right", "right", "right", "right", "right", "right", "right"]


def _trend_rows(lines: list[LineTrajectory]) -> list[list[Any]]:
    rows = []
    for ln in lines:
        mean, latest_occ, n = _occ_text(ln)
        rows.append([
            ln.name, ln.carrier or "-", _veh(ln.window_vehicles_first, ln.window_vehicles_last),
            _arrow(ln.early, ln.recent), _signed(ln.delta), _num(ln.threshold),
            _arrow(ln.transported_early, ln.transported_recent),
            _arrow(ln.rate_early, ln.rate_recent),
            f"{mean} / {latest_occ} (n={n})",
        ])
    return rows


def _rule_blocks(view: LinesHistoryView, context: EvaluationContext) -> list[Any]:
    crit = {c.name: c.value for c in view.criteria}
    policy = context.policies["lines-history"]
    mature = context.thresholds.mature_years
    window_label = (f"last year (since {view.window_start.date or '-'})" if view.window_kind == "last-year"
                    else "entire stored history")
    min_points, max_k, long_years = int(crit["minProfitSamples"]), int(crit["maxGroupSize"]), crit["longHistoryYears"]
    return [
        Heading(2, "Classification Rule"),
        Paragraph(
            "Applies to lines present in the latest snapshot. Samples are collapsed to one per game date. "
            f"Evaluation window: {window_label} (the last year is used once history reaches "
            f"{long_years:g} years; before that all stored samples are used)."),
        Table(["Step", "Rule", "Result"], [
            [1, "No vehicles on the line in the latest snapshot", "insufficient data"],
            [2, f"Oldest currently assigned vehicle age < {mature:g} GAME-YEAR. This is not line creation or first-observed age; "
                "unknown calendar maturity is insufficient data, never a mature or young fact.", "too new / insufficient data"],
            [3, f"Fewer than {min_points} non-missing profit samples in the window", "insufficient data"],
            [4, f"Otherwise K = min({max_k}, max(2, n // 3)); early = median of the first K window samples, "
                "recent = median of the last K; change = recent - early.", "-"],
            [5, f"Threshold = max({policy.relative_change_ratio:.0%} of the larger of |early|, |recent|; {policy.noise_factor:g} x noise (median absolute deviation of the window samples around the straight line "
                f"joining the early and recent medians, so a steady trend is not noise); {policy.floor_share:.0%} of the median |profit| across current lines = {_num(view.floor)}).", "-"],
            [6, "change > threshold / change < -threshold / otherwise", "improving / deteriorating / stable"],
        ], ["right", "left", "left"]),
        Note("Why a noise term", "Rolling profit is lumpy: one large delivery entering or leaving the one-year window can move a "
                                 "line's value a lot between consecutive samples. The MAD term keeps such saw-tooth lines from being "
                                 "labelled as trends. Medians, never sums, are used; values are point observations."),
    ]


def _summary(view: LinesHistoryView) -> list[Any]:
    rows = [[s.trend_class, s.lines, _num(s.median_latest_profit)] for s in view.class_summary]
    return [
        Heading(2, "Trend Class Summary"),
        Table(["Class", "Lines", "Median of latest profit point per line"], rows, ["left", "right", "right"]),
        Chart("bar", "Lines per Trend Class", list(CLASSES), [("Lines", [float(s.lines) for s in view.class_summary])]),
    ]


def _trend_section(view: LinesHistoryView, by_id: dict[int, LineTrajectory], cls: str) -> list[Any]:
    sel = [by_id[i] for i in next(o.line_ids for o in view.class_order if o.trend_class == cls)]
    blocks: list[Any] = [Heading(2, f"{cls.capitalize()} Lines ({len(sel)})")]
    if not sel:
        return blocks + [Paragraph(f"No lines are classified as {cls} under the rule above.")]
    blocks.append(Table(_TREND_COLS, _trend_rows(sel[:TABLE_CAP]), _TREND_ALIGN))
    if len(sel) > TABLE_CAP:
        blocks.append(Paragraph(f"{len(sel) - TABLE_CAP} further {cls} lines omitted (ranked by size of change)."))
    return blocks


def _best_worst(view: LinesHistoryView, by_id: dict[int, LineTrajectory]) -> list[Any]:
    if not view.profit_ranking:
        return [Heading(2, "Best and Worst Lines Now"), Paragraph("Insufficient data: no line has a profit sample.")]
    ranked = [by_id[i] for i in view.profit_ranking]
    top = ranked[:TABLE_CAP]
    top_ids = {ln.line_id for ln in top}
    bottom = [ln for ln in ranked[::-1] if ln.line_id not in top_ids][:TABLE_CAP]

    def rows(sel: list[LineTrajectory]) -> list[list[Any]]:
        out = []
        for ln in sel:
            hi, lo = ln.highest, ln.lowest
            mean, latest_occ, n = _occ_text(ln)
            out.append([ln.name, ln.carrier or "-", ln.trend_class, _veh(ln.vehicles_first, ln.vehicles_last), ln.points[0].profit,
                        f"{_num(hi.profit)} ({hi.date})", f"{_num(lo.profit)} ({lo.date})", ln.points[-1].profit,
                        f"{mean} / {latest_occ} (n={n})", _spark(_profits(ln))])
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


def _charts(view: LinesHistoryView) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Trajectories of Top and Bottom Lines")]
    picks = [int(t) for t in spread([s.tick for s in view.samples], MAX_SAMPLES)]
    if len(picks) < 2:
        return blocks + [Paragraph("Insufficient data: at least two sample dates are needed for trajectory charts.")]
    date_of = {s.tick: s.date for s in view.samples}
    dates = [date_of[g] for g in picks]
    full = []
    for ln in view.trajectories:
        if not ln.current or ln.points[-1].profit is None:
            continue
        by_gt = {p.tick: p.profit for p in ln.points}
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
    omitted = sum(1 for ln in view.trajectories if ln.current) - len(full)
    blocks.append(Paragraph(f"Only lines with a sample at every charted date are eligible ({omitted} current lines excluded, e.g. newer lines). "
                            "Series order in the chart follows the table columns; Markdown charts do not label series."))
    return blocks


def _vehicles_section(view: LinesHistoryView) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Vehicle Count Changes vs Profit")]
    events = view.vehicle_changes
    if not events:
        return blocks + [Paragraph("No vehicle-count change was observed on any line between stored samples.")]
    shown = events[:EVENT_CAP]
    blocks += [
        Paragraph(f"{len(events)} vehicle-count changes across {view.changed_lines} lines ({view.additions} additions, "
                  f"{view.reductions} reductions). Before/after profit = median of up to 3 samples before the change and the last up to 3 "
                  "samples of the stretch before the next change; verdict uses the same noise rule as the classification."),
        Table(["Line", "Date seen", "Vehicles", "Profit before", "Profit after", "Change", "Samples after", "Profit per vehicle before → after", "Verdict"],
              [[e.name, e.date, f"{e.vehicles_before} → {e.vehicles_after}", _num(e.profit_before), _num(e.profit_after), _signed(e.delta),
                e.samples_after, _arrow(e.profit_per_vehicle_before, e.profit_per_vehicle_after), _VERDICTS[e.verdict]]
               for e in shown], ["left", "left", "right", "right", "right", "right", "right", "right", "left"]),
    ]
    if len(events) > len(shown):
        blocks.append(Paragraph(f"{len(events) - len(shown)} further changes omitted (ranked: profit fell, profit rose, within noise, too soon)."))
    blocks.append(Note("Limit", "The date is the first sample showing the new count, not the purchase date. Rolling profit blends a new vehicle in "
                                "gradually and purchase cost is not part of it, so early 'after' values understate the long-run effect."))
    return blocks


def _created_removed(view: LinesHistoryView) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Lines Created and Removed")]
    if not view.changes_comparable:
        return blocks + [Paragraph("Insufficient data: two or more samples are needed to detect created or removed lines.")]
    blocks.append(Paragraph(f"Compared with the first sample ({view.samples[0].date}): {len(view.created)} lines appeared and {len(view.removed)} disappeared "
                            f"by the latest sample ({view.samples[-1].date}). A line is 'removed' if it is absent from the latest snapshot; "
                            "exact dates are bounded by the sample gap."))
    for title, sel in (("Created", view.created), ("Removed", view.removed)):
        if not sel:
            blocks.append(Paragraph(f"No {title.lower()} lines."))
            continue
        rows = []
        for ch in sel[:TABLE_CAP * 2]:
            rows.append([ch.name, f"{ch.window_start.date} .. {ch.window_end.date}", ch.vehicles_first, ch.vehicles_last,
                         ch.profit_first, ch.profit_last, ch.trend_class or ("-" if title == "Created" else "removed")])
        blocks += [Heading(3, f"{title} lines ({len(sel)})"),
                   Table(["Line", "Window of change (last absent/present .. first present/absent)", "Vehicles at first sight", "Vehicles at last sight",
                          "Profit at first sight", "Profit at last sight", "Class now"], rows, ["left", "left", "right", "right", "right", "right", "left"])]
        if len(sel) > TABLE_CAP * 2:
            blocks.append(Paragraph(f"{len(sel) - TABLE_CAP * 2} further {title.lower()} lines omitted."))
    blocks.append(Note("Limit", "Last-sight profit of a removed line is a rolling value at that sample, not what the line earned in total. "
                                "A line deleted and rebuilt gets a new id and appears as one removal plus one creation."))
    return blocks


def _compact(view: LinesHistoryView, by_id: dict[int, LineTrajectory]) -> list[Any]:
    cur = [by_id[i] for i in view.compact_order]
    blocks: list[Any] = [Heading(2, "Compact Trajectory Table")]
    if not cur:
        return blocks + [Paragraph("Insufficient data: no current lines.")]
    shown = cur[:SPARK_CAP]
    rows = [[ln.name, ln.trend_class, _veh(ln.vehicles_first, ln.vehicles_last), ln.points[0].profit, ln.points[-1].profit, _signed(ln.delta),
             _spark(_profits(ln)), _spark([o.load for o in ln.occupancy])] for ln in shown]
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


def _followups(view: LinesHistoryView) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Suggested Manual Follow-ups")]
    rows: list[list[Any]] = []
    for f in view.follow_ups:
        mean = _fmt_pct(f.occupancy_mean)
        occ = f"occupancy samples mean {mean}, latest {_fmt_pct(f.occupancy_latest)} (n={f.occupancy_samples}; instantaneous readings)"
        win = _veh(f.window_vehicles_first, f.window_vehicles_last)
        if f.code == "declining-with-added-vehicles":
            rows.append([f.name, f"Profit median {_arrow(f.early, f.recent)} while vehicles went {win}; {occ}.",
                         "Extra vehicles may be sharing a fixed demand instead of adding income; the rolling window also lags the purchase. Not proven.",
                         "Look at this line's vehicles and occupancy in the game; consider whether the newest vehicle is needed, then recheck after the profit window has advanced."])
        elif f.code == "declining-without-added-vehicles":
            issues = ", ".join(f.issues) if f.issues else "none reported"
            rows.append([f.name, f"Profit median {_arrow(f.early, f.recent)} with vehicles {win} (no addition); {occ}; "
                                 f"line issues now: {issues}.",
                         "Decline is not explained by fleet size; cargo supply, a competing line or vehicle ageing are candidates (unverified).",
                         "Inspect the served stops/industries (stock levels, production) and the line's issue list in the game."])
        elif f.code == "rising-and-full":
            rows.append([f.name, f"Profit median {_arrow(f.early, f.recent)}, vehicles {win}, occupancy sample mean {mean}.",
                         "Rising profit with consistently full vehicles suggests capacity may be limiting; waiting cargo is not collected, so this is unconfirmed.",
                         "Candidate for testing one more vehicle or a larger model; compare against the vehicle catalog, then recheck this report."])
        else:
            rows.append([f.name, f"Every window sample is negative (latest {_num(f.latest_profit)}, class {f.trend_class}, "
                                 f"vehicles {_veh(f.vehicles_first, f.vehicles_last)}); {occ}.",
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

def build(view: LinesHistoryView, *, context: EvaluationContext) -> ReportDocument:
    by_id = {t.line_id: t for t in view.trajectories}
    crit = {c.name: c.value for c in view.criteria}
    min_points = int(crit["minProfitSamples"])
    window_label = (f"last year (since {view.window_start.date or '-'})" if view.window_kind == "last-year"
                    else "entire stored history")
    samples = view.samples
    header = _base_header(context.snapshot, len(samples))
    header += [
        ("Sample Period", f"{samples[0].date} .. {samples[-1].date} ({_num(view.span.value)} GAME-YEAR, {len(samples)} distinct sample dates)"),
        ("Lines Tracked", f"{len(view.trajectories)} ever seen, {sum(1 for t in view.trajectories if t.current)} in the latest snapshot"),
        ("Evaluation Window", window_label),
        ("Time Basis", f"game-calendar-v1; 365.25 calendar days per GAME-YEAR; anchor hash {context.clock.time_basis['anchorHash']}"),
        ("Occupancy Samples", f"{len(view.coverage.sampled)} snapshots (up to {MAX_SAMPLES}, spread across the history)"),
    ]
    blocks: list[Any] = []
    if view.short_span:
        blocks.append(Note("Coverage", f"Only {view.span.value:.2f} years of samples are stored. Each rolling-year profit value overlaps heavily with the "
                                       "others, so trends here are short-term movements, not year-over-year results. The report becomes more informative as "
                                       "snapshots accumulate across years."))
    if view.too_few_samples:
        blocks.append(Note("Insufficient data", f"Only {len(samples)} sample dates are stored; lines cannot be classified until at least {min_points} exist."))
    blocks += _summary(view)
    blocks += _rule_blocks(view, context)
    blocks += _followups(view)
    blocks += _trend_section(view, by_id, "deteriorating")
    blocks += _trend_section(view, by_id, "improving")
    blocks += _best_worst(view, by_id)
    blocks += _charts(view)
    blocks += _vehicles_section(view)
    blocks += _created_removed(view)
    blocks += _compact(view, by_id)
    blocks.append(Note("Measurement Limits", "Values are rolling-year point observations at sample dates, never summed. 'Transported' accounting is unverified; "
                                             "'rate' is the game's throughput estimate; occupancy is instantaneous at snapshot time. Missing values are "
                                             "unknown, not zero. Each stored save is assumed to be the same company."))
    return ReportDocument("lines-history", "Line History and Trend Report", header, blocks)
