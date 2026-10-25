"""Company history report: how the company evolved across every stored snapshot.

Presentation over the typed `HistoryView`: all period, coverage, growth, comparison, turnover, milestone,
earnings-offset and cohort numbers are computed by the analysis view; this module only chooses headings,
prose, formatting, display caps and chart series.

Design notes
- Elapsed time uses the shared evidence-bound calendar clock; nominal query duration never substitutes for it.
- Aggregation level adapts to the covered span (month / quarter / year); the closing sample of each period
  represents it. Rolling annual line profit is only ever shown as a level at a sample, never summed.
- Transport counters are displayed as raw sampled levels and differences; undocumented accounting
  windows prohibit interpreting those differences as period transport volumes or throughput rates.
"""

from __future__ import annotations

from typing import Any, Callable, Sequence

from .analysis_views.history import HistoryEvent, HistoryView
from .analysis_views.models import EvaluationContext
from .game_time import DAYS_PER_YEAR
from .reports import (
    Chart,
    Heading,
    Note,
    Paragraph,
    ReportDocument,
    Table,
    _fmt,
    _fmt_pct,
)

MAX_CHART_POINTS = 60
MAX_EVENT_ROWS = 10
MAX_NAMES = 3
INSUFFICIENT = "Insufficient data"

GROWTH_NAMES = {
    "balance": "Cash balance",
    "loan": "Loan",
    "net": "Net position (balance - loan)",
    "vehicles": "Vehicles",
    "lines": "Lines",
    "stations": "Stations served",
    "track": "Track length (raw)",
    "score": "Company value score (raw)",
    "rolling-profit": "Rolling line profit (level)",
    "passengers-counter": "Passengers transported counter (raw)",
    "cargo-counter": "Cargo transported counter (raw)",
}
EXTREME_NAMES = {
    "highest-balance": "Highest sampled balance",
    "lowest-balance": "Lowest sampled balance",
    "largest-fleet": "Largest sampled fleet",
    "smallest-fleet": "Smallest sampled fleet",
    "highest-rolling-profit": "Highest rolling line profit level",
    "lowest-rolling-profit": "Lowest rolling line profit level",
}


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _signed(value: int | float | None) -> str:
    if value is None:
        return "-"
    return f"{'+' if value > 0 else ''}{_fmt(value)}"


def _pct_text(percent: float | None) -> str:
    return "-" if percent is None else f"{percent:+.1f}%"


def _days_text(days: float | None) -> str | None:
    return None if days is None else f"{days:g}" if days == int(days) else f"{days:.1f}"


def _names(items: Sequence[str], limit: int = MAX_NAMES) -> str:
    if not items:
        return "-"
    shown = "; ".join(items[:limit])
    return shown + (f" and {len(items) - limit} more" if len(items) > limit else "")


def _criterion(view: HistoryView, name: str) -> float:
    return next(c.value for c in view.criteria if c.name == name)


def _chart_rows(
    periods: Sequence[Any], series: dict[str, Callable[[Any], float | int | None]], kind: str, title: str
) -> list[Chart]:
    """Chart only periods where every series has a value, so chart and table agree."""
    rows = [p for p in periods if all(fn(p) is not None for fn in series.values())]
    rows = rows[-MAX_CHART_POINTS:]
    if len(rows) < 2:
        return []
    return [
        Chart(
            kind, title, [p.label for p in rows], [(name, [float(fn(p)) for p in rows]) for name, fn in series.items()]
        )
    ]


def _insufficient(title: str, text: str) -> list[Any]:
    return [Heading(2, title), Note(INSUFFICIENT, text)]


def _rounded(days: float | None) -> int | None:
    return None if days is None else round(days)


def _range(first: str, last: str) -> str:
    return f"{first} -> {last}"


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------


def _coverage_section(view: HistoryView) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Coverage and Sampling Cadence")]
    cadence = view.cadence
    first, last = view.points[0], view.points[-1]
    expected = cadence.periods_expected
    rows = [
        ["First sample", first.label],
        ["Latest sample", last.label],
        ["Calendar span (days)", _rounded(view.span_days)],
        ["Stored samples", view.stored_samples],
        ["Samples after merging near-duplicates (<1 day apart)", view.usable_samples],
        ["Near-duplicate samples merged", view.unused_samples],
        ["Samples without a calendar date (excluded)", view.undated_samples],
        ["Sample reasons", ", ".join(f"{k}: {v}" for k, v in cadence.reasons.items())],
        [
            "Median gap between samples (days)",
            "-" if cadence.median_gap_days is None else round(cadence.median_gap_days, 1),
        ],
        ["Largest gap (days)", "-" if cadence.largest_gap_days is None else round(cadence.largest_gap_days, 1)],
        ["Periods with data / periods in span", f"{cadence.periods_with_data} / {expected} ({view.level} level)"],
        ["Periods with no sample", _names(cadence.missing_periods, 8)],
        [
            "Game ticks per calendar day (whole-span diagnostic)",
            "-" if cadence.ticks_per_day is None else round(cadence.ticks_per_day),
        ],
    ]
    blocks.append(Table(["Coverage fact", "Value"], rows, ["left", "right"]))

    if cadence.median_gap_days is not None:
        big = cadence.gaps_longer_than_usual
        if big:
            blocks.append(Heading(3, f"Gaps Longer Than Usual ({min(len(big), MAX_EVENT_ROWS)} of {len(big)})"))
            blocks.append(
                Table(
                    ["From", "To", "Days"],
                    [[g.start_label, g.end_label, _days_text(g.days)] for g in big[:MAX_EVENT_ROWS]],
                    ["left", "left", "right"],
                )
            )
        else:
            blocks.append(Paragraph("No gap between merged samples is longer than 2.5x the median cadence."))

    if cadence.tick_rate_diverges:
        tpd, ratio, nominal = cadence.ticks_per_day, cadence.tick_rate_ratio, cadence.nominal_ticks_per_day
        blocks.append(
            Note(
                "Observation",
                f"The whole-span observation is about {tpd:,.0f} game ticks per calendar day, {ratio:.2f}x the "
                f"{nominal:,.0f} implied by meta.yearDuration. This is a diagnostic, not a conversion rate. "
                "Elapsed time uses the shared calendar clock; nominal duration remains a financial/query-window "
                "input and is never an age fallback.",
            )
        )
    if view.later_samples:
        blocks.append(
            Note(
                "Coverage Warning",
                "The most recently ingested snapshot is not the newest by game time. A save from earlier in the "
                "timeline may have been loaded; samples from the abandoned timeline are still counted here.",
            )
        )
    errors = cadence.errors
    if errors is not None:
        listing = "; ".join(f"{c.family} ({c.samples} samples)" for c in errors.collectors[:4])
        blocks.append(
            Note(
                "Collection Errors",
                f"{errors.samples} of {view.stored_samples} samples reported collector errors (first: {errors.first_label}, "
                f"latest: {errors.last_label}). Failing collectors: {listing}. Values from failed collectors "
                "are missing, not zero, so counts that depend on them may be understated.",
            )
        )
    return blocks


def _summary_section(view: HistoryView) -> list[Any]:
    first, last = view.points[0], view.points[-1]
    blocks: list[Any] = [Heading(2, "Summary of the Recorded History")]
    changes = view.endpoint_changes
    if changes is None:
        blocks.append(
            Note(
                INSUFFICIENT,
                "Only one usable sample exists, so no change over time can be reported yet. "
                "Further snapshots will fill this section.",
            )
        )
        return blocks
    parts = [
        f"Observation: {view.usable_samples} usable samples between {first.label} and {last.label} "
        f"({_rounded(view.span_days)} calendar days)."
    ]
    if changes.balance_change is not None:
        parts.append(
            f"Cash balance moved from {_fmt(first.balance)} to {_fmt(last.balance)} "
            f"({_signed(changes.balance_change)}, {_pct_text(changes.balance_change_percent)}); "
            f"loan {_fmt(first.loan)} -> {_fmt(last.loan)}."
        )
    parts.append(f"Fleet {first.vehicles} -> {last.vehicles} vehicles; lines {first.lines} -> {last.lines}.")
    blocks.append(Paragraph(" ".join(parts)))

    if changes.passengers_change is not None:
        blocks.append(
            Paragraph(
                f"Observation: the raw passengersTransported counter changed by "
                f"{_fmt(changes.passengers_change)} and cargoTransported by "
                f"{_fmt(changes.cargo_change)} between the endpoint samples. "
                "Their accounting windows are unverified; these differences are not transport volumes earned in the span."
            )
        )

    profit = view.rolling_profit
    if profit is not None:
        blocks.append(
            Paragraph(
                f"Observation: the rolling line profit level was {_fmt(profit.first.value)} at {profit.first.label}, "
                f"peaked at {_fmt(profit.peak.value)} on {profit.peak.label} and was {_fmt(profit.latest.value)} at "
                f"{profit.latest.label} ({_pct_text(profit.latest_vs_peak_percent)} from the peak). "
                f"Lines reporting a loss: {profit.first.lines_losing} of {profit.first.lines_with_profit} at the first "
                f"sample and {profit.latest.lines_losing} of {profit.latest.lines_with_profit} at the latest."
            )
        )
    return blocks


def _finance_section(view: HistoryView, level_reason: str) -> list[Any]:
    periods = view.periods
    blocks: list[Any] = [
        Heading(2, f"Finance by {view.level.title()}"),
        Paragraph(
            f"Each row shows the closing sample of the period. {level_reason} The first row is "
            "compared with the first stored sample, and later rows with the previous closing "
            "sample; the Days column is the time actually elapsed between the compared samples."
        ),
    ]
    rows = []
    for p in periods:
        c = p.close
        rows.append(
            [
                p.label,
                p.samples,
                c.label,
                _days_text(p.days),
                c.balance,
                p.balance_change,
                _pct_text(p.balance_change_percent),
                c.loan,
                c.net,
                c.rolling_profit,
                f"{c.lines_losing} / {c.lines_with_profit}" if c.lines_with_profit else "-",
            ]
        )
    blocks.append(
        Table(
            [
                "Period",
                "Samples",
                "Closing Sample",
                "Days Compared",
                "Balance",
                "Balance Change",
                "Balance Change %",
                "Loan",
                "Net (Balance - Loan)",
                "Rolling Line Profit (level)",
                "Losing / Profit-Reporting Lines",
            ],
            rows,
            ["left", "right", "left", "right", "right", "right", "right", "right", "right", "right", "right"],
        )
    )
    blocks.append(
        Note(
            "Rolling Profit",
            "Rolling Line Profit is the sum of each line's rolling 12-month profit at the "
            "closing sample. It is a level at that date, not income earned in the period, "
            "and rows must not be added together.",
        )
    )
    blocks.extend(
        _chart_rows(
            periods,
            {"Balance": lambda p: p.close.balance, "Loan": lambda p: p.close.loan},
            "line",
            "Balance and Loan at Period Close",
        )
    )
    blocks.extend(
        _chart_rows(
            periods,
            {"Rolling line profit": lambda p: p.close.rolling_profit},
            "line",
            "Rolling Line Profit at Period Close",
        )
    )
    return blocks


def _network_section(view: HistoryView) -> list[Any]:
    periods = view.periods
    carriers = sorted({c for p in periods for c in p.close.carriers})
    blocks: list[Any] = [Heading(2, f"Network and Fleet Size by {view.level.title()}")]
    rows = []
    for p in periods:
        c = p.close
        rows.append(
            [
                p.label,
                c.lines,
                p.lines_change,
                c.vehicles,
                p.vehicles_change,
                c.stations,
                c.track,
                c.score,
                *[c.carriers.get(carrier, 0) for carrier in carriers],
            ]
        )
    blocks.append(
        Table(
            [
                "Period",
                "Lines",
                "Lines Change",
                "Vehicles",
                "Vehicles Change",
                "Stations Served",
                "Track Length (raw)",
                "Company Value Score (raw)",
                *[f"{c} Vehicles" for c in carriers],
            ],
            rows,
            ["left"] + ["right"] * (7 + len(carriers)),
        )
    )
    blocks.append(
        Note(
            "Units",
            "Track length and company value score are raw API values; units are unverified. "
            "Stations Served counts only station groups used by the company's lines.",
        )
    )
    blocks.extend(
        _chart_rows(
            periods,
            {c: (lambda p, c=c: p.close.carriers.get(c, 0)) for c in carriers},
            "line",
            "Vehicles by Carrier at Period Close",
        )
    )
    return blocks


def _turnover_section(view: HistoryView) -> list[Any]:
    periods = view.periods
    blocks: list[Any] = [Heading(2, f"Fleet and Line Turnover by {view.level.title()}")]
    if not view.interval_count:
        return blocks + [
            Note(INSUFFICIENT, "At least two samples are needed to see vehicles or lines appear or disappear.")
        ]
    blocks.append(
        Paragraph(
            "Counts compare entity ids between consecutive samples. A vehicle or line created and removed between two "
            "samples is invisible, and replacements cannot be told apart from independent buys and sales."
        )
    )
    rows = [
        [p.label, p.vehicles_added, p.vehicles_removed, p.net_vehicles, p.added_value, p.lines_created, p.lines_removed]
        for p in periods
    ]
    blocks.append(
        Table(
            [
                "Period",
                "Vehicles Added",
                "Vehicles Removed",
                "Net Vehicles",
                "Recorded Value of Added Vehicles",
                "Lines Created",
                "Lines Removed",
            ],
            rows,
            ["left"] + ["right"] * 6,
        )
    )
    blocks.append(
        Note(
            "Units",
            "Recorded value is each added vehicle's current book value in the sample where it first "
            "appeared, not necessarily its purchase price.",
        )
    )
    blocks.extend(
        _chart_rows(
            periods,
            {"Added": lambda p: p.vehicles_added, "Removed": lambda p: p.vehicles_removed},
            "bar",
            "Vehicles Added and Removed per Period",
        )
    )
    return blocks


def _traffic_section(view: HistoryView) -> list[Any]:
    periods = view.periods
    blocks: list[Any] = [Heading(2, f"Transported Passengers and Cargo by {view.level.title()}")]
    if not view.traffic.has_counters:
        return blocks + [Note(INSUFFICIENT, "No sample carries the company transport counters.")]
    rows = [[p.label, p.close.passengers, p.passengers_change, p.close.cargo, p.cargo_change] for p in periods]
    blocks.append(
        Table(
            [
                "Period",
                "Passengers Counter (raw)",
                "Passengers Counter Change",
                "Cargo Counter (raw)",
                "Cargo Counter Change",
            ],
            rows,
            ["left"] + ["right"] * 4,
        )
    )
    decreases = view.traffic.decreases
    if decreases:
        blocks.append(
            Note(
                "Data Warning",
                "A transport counter decreased between "
                + "; ".join(f"{d.start_label} and {d.end_label}" for d in decreases[:3])
                + ".",
            )
        )
    blocks.append(
        Note(
            "Accounting Limit",
            "The transport counters' accounting windows are unverified. "
            "Counter differences are observations, not transported volumes or rates for a period.",
        )
    )
    blocks.extend(
        _chart_rows(
            periods, {"Passengers counter": lambda p: p.close.passengers}, "line", "Passengers Counter at Period Close"
        )
    )
    blocks.extend(
        _chart_rows(periods, {"Cargo counter": lambda p: p.close.cargo}, "line", "Cargo Counter at Period Close")
    )
    return blocks


def _growth_section(view: HistoryView) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Growth From First to Latest Sample")]
    if not view.growth:
        return blocks + [Note(INSUFFICIENT, "Growth needs two samples on different days.")]
    first, last = view.points[0], view.points[-1]
    rows = [
        [
            GROWTH_NAMES[g.code],
            g.first,
            g.latest,
            g.change,
            _pct_text(g.change_percent),
            _pct_text(g.annualised_percent),
        ]
        for g in view.growth
    ]
    blocks.append(
        Table(
            ["Metric", f"First ({first.label})", f"Latest ({last.label})", "Change", "Change %", "Annualised Growth"],
            rows,
            ["left", "right", "right", "right", "right", "right"],
        )
    )
    blocks.append(
        Note(
            "Annualising",
            "Annualised growth is shown only when the history spans at least one calendar year."
            if view.annualised
            else f"History spans {_rounded(view.span_days)} days, under one year; annualised growth is deliberately omitted "
            "because a short window would extrapolate noise and seasonal effects.",
        )
    )
    return blocks


def _yoy_section(view: HistoryView) -> list[Any]:
    title = f"Year-over-Year Comparison ({view.level} level)"
    pairs = view.year_over_year
    if not pairs:
        remaining = ""
        nxt = view.next_comparison
        if nxt is not None:
            remaining = (
                f" The earliest same-period comparison becomes possible around "
                f"{nxt.earliest_date or '?'} (about {nxt.days_after_latest} days after the latest sample)."
            )
        return _insufficient(
            title,
            f"No period has a counterpart one year earlier; history spans {_rounded(view.span_days)} days.{remaining}",
        )
    rows = [
        [
            p.label,
            p.prior_label,
            p.balance_prior,
            p.balance_now,
            _pct_text(p.balance_percent),
            p.vehicles_prior,
            p.vehicles_now,
            p.lines_prior,
            p.lines_now,
            p.profit_prior,
            p.profit_now,
            _pct_text(p.profit_percent),
        ]
        for p in pairs[-12:]
    ]
    return [
        Heading(2, title),
        Paragraph(
            "Each row compares the closing sample of a period with the closing sample of the same period one "
            "year earlier (latest 12 comparisons shown)."
        ),
        Table(
            [
                "Period",
                "Year-Ago Period",
                "Balance Year Ago",
                "Balance Now",
                "Balance %",
                "Vehicles Year Ago",
                "Vehicles Now",
                "Lines Year Ago",
                "Lines Now",
                "Rolling Profit Year Ago",
                "Rolling Profit Now",
                "Rolling Profit %",
            ],
            rows,
            ["left", "left"] + ["right"] * 10,
        ),
    ]


def _year_end_section(view: HistoryView) -> list[Any]:
    if not view.year_ends:
        return []
    rows = [
        [str(y.year), y.label, y.balance, y.balance_change, y.vehicles, y.lines, y.rolling_profit]
        for y in view.year_ends
    ]
    return [
        Heading(2, "Last Sample of Each Calendar Year"),
        Paragraph(
            "Years that are still in progress, or whose last sample is well before 31 December, show figures to date."
        ),
        Table(
            [
                "Year",
                "Last Sample",
                "Balance",
                "Balance Change vs Previous Year's Last Sample",
                "Vehicles",
                "Lines",
                "Rolling Line Profit (level)",
            ],
            rows,
            ["right", "left", "right", "right", "right", "right", "right"],
        ),
    ]


def _event_context(e: HistoryEvent) -> str:
    bits = []
    if e.vehicles_added or e.vehicles_removed:
        bits.append(f"vehicles +{len(e.vehicles_added)}/-{len(e.vehicles_removed)}")
    if e.lines_created or e.lines_removed:
        bits.append(f"lines +{len(e.lines_created)}/-{len(e.lines_removed)}")
    if e.track_change:
        bits.append(f"track {_signed(e.track_change)}")
    return ", ".join(bits) or "no fleet, line or track change"


def _milestones_section(view: HistoryView) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Milestones and Turning Points")]
    if not view.interval_count:
        return blocks + [Note(INSUFFICIENT, "Turning points need at least two samples.")]

    drops, jumps = view.cash_drops, view.cash_jumps
    if drops or jumps:
        rows = [
            ["Drop", _range(e.start_label, e.end_label), _days_text(e.days), e.balance_change, _event_context(e)]
            for e in drops
        ]
        rows += [
            ["Jump", _range(e.start_label, e.end_label), _days_text(e.days), e.balance_change, _event_context(e)]
            for e in jumps
        ]
        blocks += [
            Heading(3, "Largest Cash Movements Between Consecutive Samples"),
            Table(
                ["Type", "Samples", "Days", "Balance Change", "What Else Changed"],
                rows,
                ["left", "left", "right", "right", "left"],
            ),
            Note(
                "Reading",
                "A balance change is net cash flow: income minus every cost, including infrastructure "
                "and purchases. The snapshot does not itemise it; the last column only lists what "
                "visibly changed in the same interval.",
            ),
        ]

    changed = view.changed_intervals
    if changed:
        shown = changed[:MAX_EVENT_ROWS]
        blocks.append(
            Heading(3, f"Biggest Fleet and Network Changes ({len(shown)} of {len(changed)} changing intervals)")
        )
        blocks.append(
            Table(
                [
                    "Samples",
                    "Vehicles Added",
                    "Added (names)",
                    "Vehicles Removed",
                    "Removed (names)",
                    "Lines Created",
                    "Lines Removed",
                    "Removed Lines (names)",
                ],
                [
                    [
                        _range(e.start_label, e.end_label),
                        len(e.vehicles_added),
                        _names([v.name for v in e.vehicles_added]),
                        len(e.vehicles_removed),
                        _names([v.name for v in e.vehicles_removed]),
                        len(e.lines_created),
                        len(e.lines_removed),
                        _names([line.name for line in e.lines_removed]),
                    ]
                    for e in shown
                ],
                ["left", "right", "left", "right", "left", "right", "right", "left"],
            )
        )
        created = [(e, line.name) for e in changed for line in e.lines_created]
        if created:
            blocks.append(
                Paragraph(
                    "Lines created: "
                    + "; ".join(f"{n} (seen {e.end_label})" for e, n in created[:8])
                    + (f"; and {len(created) - 8} more" if len(created) > 8 else "")
                    + "."
                )
            )
    else:
        blocks.append(Paragraph("No vehicle or line was created or removed between any consecutive samples."))

    loan = view.loan_changes
    if loan:
        blocks += [
            Heading(3, "Loan Changes"),
            Table(
                ["Samples", "Loan Before", "Loan After", "Change"],
                [
                    [_range(e.start_label, e.end_label), e.loan_start, e.loan_end, e.loan_change]
                    for e in loan[:MAX_EVENT_ROWS]
                ],
                ["left", "right", "right", "right"],
            ),
        ]
    elif view.constant_loan is not None:
        blocks.append(Paragraph(f"The loan never changed across the samples (always {_fmt(view.constant_loan)})."))

    extremes = [[EXTREME_NAMES[x.code], x.label, x.value] for x in view.extremes]
    blocks += [
        Heading(3, "Sampled Extremes"),
        Table(["Extreme", "Sample", "Value"], extremes, ["left", "left", "right"]),
        Note(
            "Sampling Limit",
            "Extremes are among stored samples only; true peaks and troughs between samples are not visible.",
        ),
    ]
    return blocks


def _earnings_section(view: HistoryView) -> list[Any]:
    title = "Company Earnings Counter Behaviour"
    earnings = view.earnings
    if earnings.status == "insufficient-samples":
        return _insufficient(title, "Fewer than three samples carry both balance and the raw earnings counter.")
    blocks: list[Any] = [Heading(2, title)]
    if earnings.status == "unstable-offset":
        return blocks + [
            Paragraph(
                "Observation: the raw earnings counter does not move one-for-one with the balance across samples, so no "
                "stable relationship could be derived; it is not interpreted here."
            )
        ]
    rows = [
        [str(s.index), s.start_label, s.end_label, s.samples, s.earnings_start, s.earnings_end, s.offset]
        for s in earnings.segments
    ]
    blocks.append(
        Table(
            ["Segment", "From", "To", "Samples", "Earnings at Start", "Earnings at End", "Balance - Earnings Offset"],
            rows[:MAX_EVENT_ROWS],
            ["right", "left", "left", "right", "right", "right", "right"],
        )
    )
    if earnings.segment_count == 1:
        blocks.append(
            Paragraph(
                "Observation: across all samples the raw earnings counter differs from the balance by one constant, so it "
                "has moved exactly with the balance and was never reset in this history."
            )
        )
    else:
        blocks.append(
            Paragraph(
                f"Observation: within each segment the raw earnings counter moves exactly with the balance; the offset changed "
                f"{earnings.offset_changes} time(s). Inference (unverified): earnings looks like net cash change since the "
                "last reset of some accounting window, so the value just before a reset would be that window's net "
                "result. Its semantics are undocumented, so treat it as a hint, not an income statement."
            )
        )
    return blocks


def _cohort_section(view: HistoryView) -> list[Any]:
    title = "Surviving Fleet by Purchase Year"
    cohorts = view.cohorts
    if not cohorts.cohorts:
        return _insufficient(title, "No vehicle in the latest sample carries a usable purchase time.")
    carriers = cohorts.carriers
    rows = [
        [str(c.year), c.vehicles, _fmt_pct(c.share), *[c.carriers.get(name, 0) for name in carriers]]
        for c in cohorts.cohorts
    ]
    blocks: list[Any] = [
        Heading(2, title),
        Paragraph(
            f"Vehicles in the latest sample ({cohorts.sample.date}) grouped by supported purchase year. Only purchases inside "
            "the observed calendar range can be mapped; bracketed interpolation is an estimate, not an exact date. "
            "Only surviving vehicles are counted, so anything sold or scrapped earlier is absent."
        ),
        Table(
            ["Purchase Year", "Surviving Vehicles", "Share of Fleet", *[f"{c} Vehicles" for c in carriers]],
            rows,
            ["right"] * (3 + len(carriers)),
        ),
    ]
    if cohorts.unknown_vehicles:
        blocks.append(
            Paragraph(
                f"{cohorts.unknown_vehicles} vehicle(s) have unavailable purchase dates and are excluded; "
                "no extrapolation is used."
            )
        )
    shown = cohorts.cohorts[-MAX_CHART_POINTS:]
    if len(shown) >= 2:
        blocks.append(
            Chart(
                "bar",
                "Surviving Vehicles by Purchase Year",
                [str(c.year) for c in shown],
                [("Vehicles", [float(c.vehicles) for c in shown])],
            )
        )
    return blocks


def _limits_section(view: HistoryView) -> list[Any]:
    span = _rounded(view.span_days) if view.usable_samples > 1 else 0
    years = (span or 0) / DAYS_PER_YEAR
    if view.usable_samples <= 1:
        cadence = "a single sample"
    elif view.cadence.median_gap_days is None:
        cadence = "an unmeasured cadence"
    else:
        cadence = f"about one sample every {view.cadence.median_gap_days:.0f} days"
    items = [
        f"Sampling: this history is {view.stored_samples} snapshots covering {span} calendar days ({years:.2f} GAME-YEAR) at {cadence}. "
        f"It is observation at those instants, not continuous telemetry; anything that happened and was undone between "
        f"two samples (a vehicle bought and sold, a loan taken and repaid, a temporary cash dip) is invisible.",
        "Rolling profit: line and vehicle profitYear are rolling 12-month figures. Summing them across samples or "
        "periods double-counts the same months, so this report only shows them as levels at a date. Lines younger than "
        "a year report a partial figure, which makes early values look lower than they will be.",
        "Cash: balance changes are net of everything (income, running costs, purchases, construction). They cannot be "
        "split into those parts from snapshots; the earnings counter is undocumented.",
        "Transport counters: passengersTransported and cargoTransported have unverified accounting windows. Changes "
        "in their sampled values are not treated as period transport volumes, lifetime totals or throughput rates; "
        "transportedYear accounting is also unverified.",
        "Load is instantaneous and is not used here. Company value score, track length, and money units are raw API "
        "values with unverified units.",
        "Turnover: vehicles and lines are tracked by id between consecutive samples. Replacements, renames, and "
        "entities created and removed between samples cannot be identified.",
        "Time: elapsed time and rates use calendar dates. Within a calendar day, samples are merged when closer than one "
        "day. Periods at the edges of the history are partial; the first row is compared against the first sample, not "
        "the period start.",
        "Scope: legacy history is not proven isolated per save or branch; never interpret a monotone sequence as proof of lineage.",
    ]
    if span < 365:
        items.append(
            f"What is missing today: {span} days is less than one calendar year, so year-over-year comparison, "
            "annualised growth, and seasonal patterns are unavailable. They appear automatically as snapshots accumulate."
        )
    elif view.level != "month":
        items.append(
            f"Aggregation is at {view.level} level because the span is long; monthly detail stays in the stored "
            "snapshots but is not tabulated."
        )
    return [Heading(2, "What This History Can and Cannot Tell You"), *[Paragraph(i) for i in items]]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def build(view: HistoryView, *, context: EvaluationContext) -> ReportDocument:
    basis = context.clock.time_basis
    company_name = view.endpoint.company_name or "Primary Company"
    base_header = [
        ("Company / Save", company_name),
        ("Calendar Time Basis", f"{basis['version']}; {DAYS_PER_YEAR} days/GAME-YEAR; {basis['anchorHash']}"),
        ("Calendar Scope", basis["isolation"]),
    ]
    limits = (
        "Rolling profit is a level, never summed; load is instantaneous; transportedYear accounting is "
        "unverified; samples are observations, not continuous telemetry."
    )
    errors_total = view.error_samples

    if view.status == "ambiguous-timeline":
        return ReportDocument(
            "history",
            "Company History Report",
            base_header,
            [
                Note(INSUFFICIENT, "Ambiguous timeline: historical durations and comparisons are unavailable."),
                Table(
                    ["Latest observed fact", "Value"],
                    [
                        ["Snapshot", view.endpoint.sample.date],
                        ["Balance", view.endpoint.balance],
                        ["Loan", view.endpoint.loan],
                    ],
                    ["left", "right"],
                ),
                *[Note("Calendar Warning", warning) for warning in basis["warnings"]],
            ],
        )
    if view.status == "no-dated-samples":
        header = base_header + [
            ("History Span", "No snapshot carries a calendar date"),
            ("Snapshots Used", f"0 of {view.stored_samples}"),
            ("Collection Errors", f"{errors_total} sample(s) with errors" if errors_total else "None reported"),
            ("Measurement Limits", limits),
        ]
        return ReportDocument(
            "history",
            "Company History Report",
            header,
            [
                Heading(2, "Summary of the Recorded History"),
                Note(
                    INSUFFICIENT,
                    "No stored snapshot carries a calendar date, so the history cannot be placed on a timeline.",
                ),
            ],
        )

    first, last = view.points[0], view.points[-1]
    level, span_months = view.level, view.span_months
    month_max, quarter_max = (
        round(_criterion(view, "month-level-max-months")),
        round(_criterion(view, "quarter-level-max-months")),
    )
    level_reason = {
        "month": f"Monthly aggregation is used because the history spans {span_months} calendar month(s) (limit {month_max}).",
        "quarter": f"Quarterly aggregation is used because the history spans {span_months} calendar months ({month_max + 1}-{quarter_max}).",
        "year": f"Yearly aggregation is used because the history spans {span_months} calendar months (over {quarter_max}).",
    }[level]

    header = base_header + [
        ("History Span", f"{first.label} to {last.label} ({_rounded(view.span_days)} calendar days)"),
        ("Latest Sample Date", last.label),
        (
            "Snapshots Used",
            f"{view.usable_samples} of {view.stored_samples} stored (near-duplicates within one day merged)",
        ),
        ("Aggregation", f"{level} ({len(view.periods)} period(s)); closing sample represents each period"),
        (
            "Collection Errors",
            f"{errors_total} of {view.stored_samples} samples reported errors" if errors_total else "None reported",
        ),
        ("Measurement Limits", limits),
    ]

    blocks: list[Any] = [Note("Calendar Warning", warning) for warning in basis["warnings"]]
    blocks += _summary_section(view)
    blocks += _coverage_section(view)
    blocks += _growth_section(view)
    blocks += _finance_section(view, level_reason)
    blocks += _network_section(view)
    blocks += _turnover_section(view)
    blocks += _traffic_section(view)
    blocks += _yoy_section(view)
    blocks += _year_end_section(view)
    blocks += _milestones_section(view)
    blocks += _earnings_section(view)
    blocks += _cohort_section(view)
    blocks += _limits_section(view)
    return ReportDocument("history", "Company History Report", header, blocks)
