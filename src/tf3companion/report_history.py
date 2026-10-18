"""Company history report: how the company evolved across every stored snapshot.

Design notes
- Snapshots are compacted into small ``_Point`` records while streaming, so years of history stay cheap.
- Elapsed time uses calendar dates (``meta.date``), never ``gameTime / yearDuration``: on real data the
  default year duration is ~4x shorter than the calendar year the game actually runs.
- Aggregation level adapts to the covered span (month / quarter / year); the closing sample of each period
  represents it. Rolling annual line profit is only ever shown as a level at a sample, never summed.
- Transport counters are displayed as raw sampled levels and differences; undocumented accounting
  windows prohibit interpreting those differences as period transport volumes or throughput rates.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import statistics
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

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
from .snapshot import Snapshot
from .store import Store

MAX_CHART_POINTS = 60
MAX_EVENT_ROWS = 10
MAX_NAMES = 3
CASH_TOLERANCE = 1000  # balance - earnings offset drift treated as "same offset"
INSUFFICIENT = "Insufficient data"


# ---------------------------------------------------------------------------
# Compact per-snapshot record
# ---------------------------------------------------------------------------

@dataclass
class _Point:
    game_time: int
    year_duration: int
    ymd: tuple[int, int, int] | None
    day: float | None
    label: str
    reason: str | None
    balance: int | None
    loan: int | None
    earnings: int | None
    score: int | None
    track: int | None
    passengers: int | None
    cargo: int | None
    lines: dict[int, str]
    vehicles: dict[int, dict[str, Any]]
    n_stations: int
    rolling_profit: int | None
    lines_losing: int
    lines_with_profit: int
    errors: list[str] = field(default_factory=list)

    @property
    def carriers(self) -> Counter:
        return Counter(v["carrier"] for v in self.vehicles.values())

    @property
    def net(self) -> int | None:
        if self.balance is None:
            return None
        return self.balance - (self.loan or 0)


def _ordinal(y: int, m: int, d: int) -> float:
    try:
        return float(dt.date(y, m, d).toordinal())
    except ValueError:
        return y * 365.2425 + (m - 1) * 30.44 + d


def _year_of(day: float) -> int | None:
    try:
        return dt.date.fromordinal(int(day)).year
    except ValueError:
        return None


def _int(value: Any) -> int | None:
    return value if type(value) is int else None


def _point(snap: Snapshot) -> _Point:
    date = snap.date
    ymd = (date["year"], date["month"], date["day"]) if date else None
    company = snap.company
    value = company.get("value") if isinstance(company.get("value"), dict) else {}
    profits = [line.get("profitYear") for line in snap.lines if type(line.get("profitYear")) is int]
    vehicles: dict[int, dict[str, Any]] = {}
    for vehicle in snap.vehicles:
        vehicles[vehicle["id"]] = {
            "name": vehicle.get("name") or f"Vehicle #{vehicle['id']}",
            "carrier": vehicle.get("carrier") or "UNKNOWN",
            "value": _int(vehicle.get("value")),
            "purchase": _int(vehicle.get("purchaseTime")),
        }
    return _Point(
        game_time=snap.game_time,
        year_duration=snap.year_duration,
        ymd=ymd,
        day=_ordinal(*ymd) if ymd else None,
        label=snap.date_label,
        reason=snap.meta.get("reason"),
        balance=_int(company.get("balance")),
        loan=_int(company.get("loan")),
        earnings=_int(company.get("earnings")),
        score=_int(value.get("totalScore")),
        track=_int(value.get("trackTotalLength")),
        passengers=_int(company.get("passengersTransported")),
        cargo=_int(company.get("cargoTransported")),
        lines={line["id"]: line.get("name") or f"Line #{line['id']}" for line in snap.lines},
        vehicles=vehicles,
        n_stations=len(snap.stations),
        rolling_profit=sum(profits) if profits else None,
        lines_losing=sum(1 for p in profits if p < 0),
        lines_with_profit=len(profits),
        errors=list(snap.errors),
    )


def _load_points(store: Store) -> list[_Point]:
    rows = store.conn.execute("SELECT data, source_file FROM snapshots ORDER BY game_time")
    return [_point(Snapshot(raw=json.loads(row["data"]), source=row["source_file"])) for row in rows]


# ---------------------------------------------------------------------------
# Time handling
# ---------------------------------------------------------------------------

def _ticks_per_day(points: Sequence[_Point]) -> float | None:
    """Calibrate game ticks per calendar day from first/last dated samples (needs >= 28 days)."""
    dated = [p for p in points if p.day is not None]
    if len(dated) < 2:
        return None
    days = dated[-1].day - dated[0].day
    ticks = dated[-1].game_time - dated[0].game_time
    return ticks / days if days >= 28 and ticks > 0 else None


def _merge_near_duplicates(points: Sequence[_Point], tpd: float | None) -> list[_Point]:
    """Samples closer than one calendar day (e.g. refresh requests) collapse onto the later one."""
    out: list[_Point] = []
    for p in points:
        if p.day is None:
            continue
        threshold = tpd if tpd else (p.year_duration / 365.25 if p.year_duration else 0)
        if out and threshold and p.game_time - out[-1].game_time < threshold:
            out[-1] = p
        else:
            out.append(p)
    return out


def _days_between(a: _Point, b: _Point) -> float:
    return b.day - a.day


# ---------------------------------------------------------------------------
# Periods
# ---------------------------------------------------------------------------

Key = tuple[int, int]


def _level_for(span_months: int) -> str:
    if span_months <= 18:
        return "month"
    if span_months <= 72:
        return "quarter"
    return "year"


def _key(p: _Point, level: str) -> Key:
    y, m, _ = p.ymd
    if level == "month":
        return (y, m)
    if level == "quarter":
        return (y, (m - 1) // 3 + 1)
    return (y, 0)


def _label(key: Key, level: str) -> str:
    y, s = key
    if level == "month":
        return f"{y:04d}-{s:02d}"
    if level == "quarter":
        return f"{y:04d}-Q{s}"
    return f"{y:04d}"


def _all_keys(first: Key, last: Key, level: str) -> list[Key]:
    keys: list[Key] = []
    y, s = first
    while (y, s) <= last:
        keys.append((y, s))
        if level == "month":
            y, s = (y + 1, 1) if s == 12 else (y, s + 1)
        elif level == "quarter":
            y, s = (y + 1, 1) if s == 4 else (y, s + 1)
        else:
            y, s = y + 1, 0
    return keys


@dataclass
class _Period:
    key: Key
    label: str
    samples: int
    closing: _Point
    previous: _Point
    first_period: bool
    added: int = 0
    removed: int = 0
    added_value: int | None = None
    lines_created: int = 0
    lines_removed: int = 0

    @property
    def days(self) -> float | None:
        d = _days_between(self.previous, self.closing)
        return d if d > 0 else None


@dataclass
class _Event:
    start: _Point
    end: _Point
    days: float
    d_balance: int | None
    d_loan: int | None
    added: list[dict[str, Any]]
    removed: list[dict[str, Any]]
    lines_created: list[str]
    lines_removed: list[str]
    d_track: int | None


def _events(points: Sequence[_Point]) -> list[_Event]:
    out = []
    for a, b in zip(points, points[1:]):
        added = [v for i, v in b.vehicles.items() if i not in a.vehicles]
        removed = [v for i, v in a.vehicles.items() if i not in b.vehicles]
        out.append(_Event(
            start=a, end=b, days=_days_between(a, b),
            d_balance=None if a.balance is None or b.balance is None else b.balance - a.balance,
            d_loan=None if a.loan is None or b.loan is None else b.loan - a.loan,
            added=added, removed=removed,
            lines_created=[n for i, n in b.lines.items() if i not in a.lines],
            lines_removed=[n for i, n in a.lines.items() if i not in b.lines],
            d_track=None if a.track is None or b.track is None else b.track - a.track,
        ))
    return out


def _build_periods(points: Sequence[_Point], level: str, events: Sequence[_Event]) -> list[_Period]:
    groups: dict[Key, list[_Point]] = {}
    for p in points:
        groups.setdefault(_key(p, level), []).append(p)
    periods: list[_Period] = []
    prev = points[0]
    for index, key in enumerate(sorted(groups)):
        closing = groups[key][-1]
        periods.append(_Period(key, _label(key, level), len(groups[key]), closing, prev, index == 0))
        prev = closing
    by_key = {p.key: p for p in periods}
    for e in events:
        period = by_key[_key(e.end, level)]
        period.added += len(e.added)
        period.removed += len(e.removed)
        period.lines_created += len(e.lines_created)
        period.lines_removed += len(e.lines_removed)
        values = [v["value"] for v in e.added if v["value"] is not None]
        if values:
            period.added_value = (period.added_value or 0) + sum(values)
    return periods


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _delta(curr: int | None, prev: int | None) -> int | None:
    return None if curr is None or prev is None else curr - prev


def _signed(value: int | float | None) -> str:
    if value is None:
        return "-"
    return f"{'+' if value > 0 else ''}{_fmt(value)}"


def _pct(curr: int | None, prev: int | None) -> str:
    if curr is None or prev in (None, 0):
        return "-"
    return f"{(curr - prev) / abs(prev) * 100:+.1f}%"


def _days_text(days: float | None) -> str | None:
    return None if days is None else f"{days:g}" if days == int(days) else f"{days:.1f}"


def _date_text(day: float) -> str:
    try:
        return dt.date.fromordinal(int(day)).isoformat()
    except ValueError:
        return "?"




def _names(items: Sequence[str], limit: int = MAX_NAMES) -> str:
    if not items:
        return "-"
    shown = "; ".join(items[:limit])
    return shown + (f" and {len(items) - limit} more" if len(items) > limit else "")


def _chart_rows(periods: Sequence[Any], series: dict[str, Callable[[Any], float | int | None]],
                kind: str, title: str) -> list[Chart]:
    """Chart only periods where every series has a value, so chart and table agree."""
    rows = [p for p in periods if all(fn(p) is not None for fn in series.values())]
    rows = rows[-MAX_CHART_POINTS:]
    if len(rows) < 2:
        return []
    return [Chart(kind, title, [p.label for p in rows],
                  [(name, [float(fn(p)) for p in rows]) for name, fn in series.items()])]


def _insufficient(title: str, text: str) -> list[Any]:
    return [Heading(2, title), Note(INSUFFICIENT, text)]


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

def _coverage_section(raw: Sequence[_Point], pts: Sequence[_Point], periods: Sequence[_Period], level: str,
                      tpd: float | None, latest_mismatch: bool) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Coverage and Sampling Cadence")]
    first, last = pts[0], pts[-1]
    span = _days_between(first, last)
    gaps = [(_days_between(a, b), a, b) for a, b in zip(pts, pts[1:])]
    median_gap = statistics.median(g for g, _, _ in gaps) if gaps else None
    reasons = Counter(p.reason or "unknown" for p in raw)
    merged = len(raw) - len(pts)
    undated = sum(1 for p in raw if p.day is None)
    present = {p.key for p in periods}
    expected = _all_keys(min(present), max(present), level)
    missing = [_label(k, level) for k in expected if k not in present]

    rows = [
        ["First sample", first.label],
        ["Latest sample", last.label],
        ["Calendar span (days)", round(span)],
        ["Stored samples", len(raw)],
        ["Samples after merging near-duplicates (<1 day apart)", len(pts)],
        ["Near-duplicate samples merged", merged],
        ["Samples without a calendar date (excluded)", undated],
        ["Sample reasons", ", ".join(f"{k}: {v}" for k, v in sorted(reasons.items()))],
        ["Median gap between samples (days)", "-" if median_gap is None else round(median_gap, 1)],
        ["Largest gap (days)", "-" if not gaps else round(max(g for g, _, _ in gaps), 1)],
        ["Periods with data / periods in span", f"{len(present)} / {len(expected)} ({level} level)"],
        ["Periods with no sample", _names(missing, 8)],
        ["Game ticks per calendar day (calibrated)", "-" if tpd is None else round(tpd)],
    ]
    blocks.append(Table(["Coverage fact", "Value"], rows, ["left", "right"]))

    if median_gap is not None:
        big = sorted([g for g in gaps if g[0] >= 15 and g[0] > 2.5 * median_gap], key=lambda g: -g[0])
        if big:
            blocks.append(Heading(3, f"Gaps Longer Than Usual ({min(len(big), MAX_EVENT_ROWS)} of {len(big)})"))
            blocks.append(Table(["From", "To", "Days"],
                                [[a.label, b.label, _days_text(g)] for g, a, b in big[:MAX_EVENT_ROWS]],
                                ["left", "left", "right"]))
        else:
            blocks.append(Paragraph("No gap between merged samples is longer than 2.5x the median cadence."))

    if tpd and last.year_duration:
        nominal = last.year_duration / 365.25
        ratio = tpd / nominal
        if abs(ratio - 1) > 0.05:
            blocks.append(Note(
                "Observation",
                f"Calibration shows about {tpd:,.0f} game ticks per calendar day, {ratio:.2f}x the "
                f"{nominal:,.0f} implied by meta.yearDuration. Elapsed time in this report therefore uses calendar "
                "dates, not gameTime / yearDuration; time units derived from yearDuration (such as vehicle age in "
                "years) would be off by that factor."))
    if latest_mismatch:
        blocks.append(Note(
            "Coverage Warning",
            "The most recently ingested snapshot is not the newest by game time. A save from earlier in the "
            "timeline may have been loaded; samples from the abandoned timeline are still counted here."))
    errored = [p for p in raw if p.errors]
    if errored:
        collectors: Counter = Counter()
        for p in errored:
            for name in {re.sub(r"\[\d+\]", "[]", e.split(":", 1)[0])[:80] for e in p.errors}:
                collectors[name] += 1
        listing = "; ".join(f"{name} ({n} samples)" for name, n in collectors.most_common(4))
        blocks.append(Note(
            "Collection Errors",
            f"{len(errored)} of {len(raw)} samples reported collector errors (first: {errored[0].label}, "
            f"latest: {errored[-1].label}). Failing collectors: {listing}. Values from failed collectors "
            "are missing, not zero, so counts that depend on them may be understated."))
    return blocks


def _summary_section(pts: Sequence[_Point], periods: Sequence[_Period], events: Sequence[_Event]) -> list[Any]:
    first, last = pts[0], pts[-1]
    span = _days_between(first, last)
    blocks: list[Any] = [Heading(2, "Summary of the Recorded History")]
    if len(pts) < 2 or span <= 0:
        blocks.append(Note(INSUFFICIENT, "Only one usable sample exists, so no change over time can be reported yet. "
                                          "Further snapshots will fill this section."))
        return blocks
    parts = [f"Observation: {len(pts)} usable samples between {first.label} and {last.label} ({round(span)} calendar days)."]
    if first.balance is not None and last.balance is not None:
        parts.append(
            f"Cash balance moved from {_fmt(first.balance)} to {_fmt(last.balance)} "
            f"({_signed(last.balance - first.balance)}, {_pct(last.balance, first.balance)}); "
            f"loan {_fmt(first.loan)} -> {_fmt(last.loan)}.")
    parts.append(f"Fleet {len(first.vehicles)} -> {len(last.vehicles)} vehicles; lines {len(first.lines)} -> {len(last.lines)}.")
    blocks.append(Paragraph(" ".join(parts)))

    if first.passengers is not None and last.passengers is not None:
        blocks.append(Paragraph(
            f"Observation: the raw passengersTransported counter changed by "
            f"{_fmt(last.passengers - first.passengers)} and cargoTransported by "
            f"{_fmt(_delta(last.cargo, first.cargo))} between the endpoint samples. "
            "Their accounting windows are unverified; these differences are not transport volumes earned in the span."))

    profit_pts = [p for p in pts if p.rolling_profit is not None]
    if len(profit_pts) >= 2:
        peak = max(profit_pts, key=lambda p: p.rolling_profit)
        blocks.append(Paragraph(
            f"Observation: the rolling line profit level was {_fmt(profit_pts[0].rolling_profit)} at {profit_pts[0].label}, "
            f"peaked at {_fmt(peak.rolling_profit)} on {peak.label} and was {_fmt(profit_pts[-1].rolling_profit)} at "
            f"{profit_pts[-1].label} ({_pct(profit_pts[-1].rolling_profit, peak.rolling_profit)} from the peak). "
            f"Lines reporting a loss: {profit_pts[0].lines_losing} of {profit_pts[0].lines_with_profit} at the first "
            f"sample and {profit_pts[-1].lines_losing} of {profit_pts[-1].lines_with_profit} at the latest."))
    return blocks


def _finance_section(periods: Sequence[_Period], level: str, level_reason: str) -> list[Any]:
    blocks: list[Any] = [Heading(2, f"Finance by {level.title()}"),
                         Paragraph(f"Each row shows the closing sample of the period. {level_reason} The first row is "
                                   "compared with the first stored sample, and later rows with the previous closing "
                                   "sample; the Days column is the time actually elapsed between the compared samples.")]
    rows = []
    for p in periods:
        c, b = p.closing, p.previous
        rows.append([
            p.label, p.samples, c.label, _days_text(p.days),
            c.balance, _delta(c.balance, b.balance) if c is not b else None,
            _pct(c.balance, b.balance) if c is not b else "-",
            c.loan, c.net, c.rolling_profit,
            f"{c.lines_losing} / {c.lines_with_profit}" if c.lines_with_profit else "-",
        ])
    blocks.append(Table(
        ["Period", "Samples", "Closing Sample", "Days Compared", "Balance", "Balance Change", "Balance Change %",
         "Loan", "Net (Balance - Loan)", "Rolling Line Profit (level)", "Losing / Profit-Reporting Lines"],
        rows, ["left", "right", "left", "right", "right", "right", "right", "right", "right", "right", "right"]))
    blocks.append(Note("Rolling Profit", "Rolling Line Profit is the sum of each line's rolling 12-month profit at the "
                                          "closing sample. It is a level at that date, not income earned in the period, "
                                          "and rows must not be added together."))
    blocks.extend(_chart_rows(periods, {"Balance": lambda p: p.closing.balance, "Loan": lambda p: p.closing.loan},
                              "line", "Balance and Loan at Period Close"))
    blocks.extend(_chart_rows(periods, {"Rolling line profit": lambda p: p.closing.rolling_profit},
                              "line", "Rolling Line Profit at Period Close"))
    return blocks


def _network_section(periods: Sequence[_Period], level: str) -> list[Any]:
    carriers = sorted({c for p in periods for c in p.closing.carriers})
    blocks: list[Any] = [Heading(2, f"Network and Fleet Size by {level.title()}")]
    rows = []
    for p in periods:
        c, b = p.closing, p.previous
        rows.append([
            p.label, len(c.lines), None if c is b else len(c.lines) - len(b.lines),
            len(c.vehicles), None if c is b else len(c.vehicles) - len(b.vehicles), c.n_stations,
            c.track, c.score,
            *[c.carriers.get(carrier, 0) for carrier in carriers],
        ])
    blocks.append(Table(
        ["Period", "Lines", "Lines Change", "Vehicles", "Vehicles Change", "Stations Served",
         "Track Length (raw)", "Company Value Score (raw)", *[f"{c} Vehicles" for c in carriers]],
        rows, ["left"] + ["right"] * (7 + len(carriers))))
    blocks.append(Note("Units", "Track length and company value score are raw API values; units are unverified. "
                                "Stations Served counts only station groups used by the company's lines."))
    blocks.extend(_chart_rows(periods, {c: (lambda p, c=c: p.closing.carriers.get(c, 0)) for c in carriers},
                              "line", "Vehicles by Carrier at Period Close"))
    return blocks


def _turnover_section(periods: Sequence[_Period], events: Sequence[_Event], level: str) -> list[Any]:
    blocks: list[Any] = [Heading(2, f"Fleet and Line Turnover by {level.title()}")]
    if not events:
        return blocks + [Note(INSUFFICIENT, "At least two samples are needed to see vehicles or lines appear or disappear.")]
    blocks.append(Paragraph(
        "Counts compare entity ids between consecutive samples. A vehicle or line created and removed between two "
        "samples is invisible, and replacements cannot be told apart from independent buys and sales."))
    rows = [[p.label, p.added, p.removed, p.added - p.removed, p.added_value, p.lines_created, p.lines_removed]
            for p in periods]
    blocks.append(Table(
        ["Period", "Vehicles Added", "Vehicles Removed", "Net Vehicles", "Recorded Value of Added Vehicles",
         "Lines Created", "Lines Removed"],
        rows, ["left"] + ["right"] * 6))
    blocks.append(Note("Units", "Recorded value is each added vehicle's current book value in the sample where it first "
                                "appeared, not necessarily its purchase price."))
    blocks.extend(_chart_rows(periods, {"Added": lambda p: p.added, "Removed": lambda p: p.removed},
                              "bar", "Vehicles Added and Removed per Period"))
    return blocks


def _traffic_section(periods: Sequence[_Period], pts: Sequence[_Point], level: str) -> list[Any]:
    blocks: list[Any] = [Heading(2, f"Transported Passengers and Cargo by {level.title()}")]
    if all(p.passengers is None and p.cargo is None for p in pts):
        return blocks + [Note(INSUFFICIENT, "No sample carries the company transport counters.")]
    decreases = [(a.label, b.label) for a, b in zip(pts, pts[1:])
                 if (_delta(b.passengers, a.passengers) or 0) < 0 or (_delta(b.cargo, a.cargo) or 0) < 0]
    rows = []
    for p in periods:
        c, b = p.closing, p.previous
        same = c is b
        dp, dc = (None, None) if same else (_delta(c.passengers, b.passengers), _delta(c.cargo, b.cargo))
        rows.append([p.label, c.passengers, dp, c.cargo, dc])
    blocks.append(Table(
        ["Period", "Passengers Counter (raw)", "Passengers Counter Change",
         "Cargo Counter (raw)", "Cargo Counter Change"],
        rows, ["left"] + ["right"] * 4))
    if decreases:
        blocks.append(Note("Data Warning", "A transport counter decreased between "
                           + "; ".join(f"{a} and {b}" for a, b in decreases[:3]) + "."))
    blocks.append(Note("Accounting Limit", "The transport counters' accounting windows are unverified. "
                       "Counter differences are observations, not transported volumes or rates for a period."))
    blocks.extend(_chart_rows(periods, {"Passengers counter": lambda p: p.closing.passengers},
                             "line", "Passengers Counter at Period Close"))
    blocks.extend(_chart_rows(periods, {"Cargo counter": lambda p: p.closing.cargo},
                             "line", "Cargo Counter at Period Close"))
    return blocks


def _growth_section(pts: Sequence[_Point]) -> list[Any]:
    first, last = pts[0], pts[-1]
    span = _days_between(first, last)
    blocks: list[Any] = [Heading(2, "Growth From First to Latest Sample")]
    if len(pts) < 2 or span <= 0:
        return blocks + [Note(INSUFFICIENT, "Growth needs two samples on different days.")]
    metrics: list[tuple[str, int | None, int | None, bool]] = [
        ("Cash balance", first.balance, last.balance, True),
        ("Loan", first.loan, last.loan, False),
        ("Net position (balance - loan)", first.net, last.net, True),
        ("Vehicles", len(first.vehicles), len(last.vehicles), True),
        ("Lines", len(first.lines), len(last.lines), True),
        ("Stations served", first.n_stations, last.n_stations, True),
        ("Track length (raw)", first.track, last.track, True),
        ("Company value score (raw)", first.score, last.score, True),
        ("Rolling line profit (level)", first.rolling_profit, last.rolling_profit, True),
        ("Passengers transported counter (raw)", first.passengers, last.passengers, False),
        ("Cargo transported counter (raw)", first.cargo, last.cargo, False),
    ]
    rows = []
    annualise = span >= 365
    for name, a, b, annual_ok in metrics:
        annual = "-"
        if annualise and annual_ok and a and b and a > 0 and b > 0:
            annual = f"{((b / a) ** (365.25 / span) - 1) * 100:+.1f}%"
        rows.append([name, a, b, _delta(b, a), _pct(b, a), annual])
    blocks.append(Table(
        ["Metric", f"First ({first.label})", f"Latest ({last.label})", "Change", "Change %", "Annualised Growth"],
        rows, ["left", "right", "right", "right", "right", "right"]))
    blocks.append(Note(
        "Annualising",
        "Annualised growth is shown only when the history spans at least one calendar year."
        if annualise else
        f"History spans {round(span)} days, under one year; annualised growth is deliberately omitted because a "
        "short window would extrapolate noise and seasonal effects."))
    return blocks


def _yoy_section(periods: Sequence[_Period], pts: Sequence[_Point], level: str) -> list[Any]:
    title = f"Year-over-Year Comparison ({level} level)"
    first, last = pts[0], pts[-1]
    by_key = {p.key: p for p in periods}
    pairs = []
    for p in periods:
        prior = by_key.get((p.key[0] - 1, p.key[1]))
        if prior is not None:
            pairs.append((prior, p))
    if not pairs:
        remaining = ""
        if last.day is not None:
            earliest = first.day + 365.25
            remaining = (f" The earliest same-period comparison becomes possible around "
                         f"{_date_text(earliest)} (about {max(0, round(earliest - last.day))} days after the latest sample).")
        return _insufficient(title, f"No period has a counterpart one year earlier; history spans "
                                    f"{round(_days_between(first, last))} days.{remaining}")
    pairs = pairs[-12:]
    rows = []
    for prior, now in pairs:
        a, b = prior.closing, now.closing
        rows.append([now.label, prior.label, a.balance, b.balance, _pct(b.balance, a.balance),
                     len(a.vehicles), len(b.vehicles), len(a.lines), len(b.lines),
                     a.rolling_profit, b.rolling_profit, _pct(b.rolling_profit, a.rolling_profit)])
    return [Heading(2, title),
            Paragraph("Each row compares the closing sample of a period with the closing sample of the same period one "
                      "year earlier (latest 12 comparisons shown)."),
            Table(["Period", "Year-Ago Period", "Balance Year Ago", "Balance Now", "Balance %",
                   "Vehicles Year Ago", "Vehicles Now", "Lines Year Ago", "Lines Now",
                   "Rolling Profit Year Ago", "Rolling Profit Now", "Rolling Profit %"],
                  rows, ["left", "left"] + ["right"] * 10)]


def _year_end_section(pts: Sequence[_Point]) -> list[Any]:
    by_year: dict[int, _Point] = {}
    for p in pts:
        by_year[p.ymd[0]] = p
    if len(by_year) < 2:
        return []
    rows = []
    prev: _Point | None = None
    for year, p in sorted(by_year.items()):
        rows.append([str(year), p.label, p.balance, _delta(p.balance, prev.balance if prev else None),
                     len(p.vehicles), len(p.lines), p.rolling_profit])
        prev = p
    return [Heading(2, "Last Sample of Each Calendar Year"),
            Paragraph("Years that are still in progress, or whose last sample is well before 31 December, show "
                      "figures to date."),
            Table(["Year", "Last Sample", "Balance", "Balance Change vs Previous Year's Last Sample",
                   "Vehicles", "Lines", "Rolling Line Profit (level)"], rows,
                  ["right", "left", "right", "right", "right", "right", "right"])]


def _milestones_section(pts: Sequence[_Point], events: Sequence[_Event]) -> list[Any]:
    blocks: list[Any] = [Heading(2, "Milestones and Turning Points")]
    if not events:
        return blocks + [Note(INSUFFICIENT, "Turning points need at least two samples.")]

    def context(e: _Event) -> str:
        bits = []
        if e.added or e.removed:
            bits.append(f"vehicles +{len(e.added)}/-{len(e.removed)}")
        if e.lines_created or e.lines_removed:
            bits.append(f"lines +{len(e.lines_created)}/-{len(e.lines_removed)}")
        if e.d_track:
            bits.append(f"track {_signed(e.d_track)}")
        return ", ".join(bits) or "no fleet, line or track change"

    money = [e for e in events if e.d_balance is not None]
    drops = sorted([e for e in money if e.d_balance < 0], key=lambda e: e.d_balance)[:3]
    jumps = sorted([e for e in money if e.d_balance > 0], key=lambda e: -e.d_balance)[:3]
    if drops or jumps:
        rows = [["Drop", f"{e.start.label} -> {e.end.label}", _days_text(e.days), e.d_balance, context(e)] for e in drops]
        rows += [["Jump", f"{e.start.label} -> {e.end.label}", _days_text(e.days), e.d_balance, context(e)] for e in jumps]
        blocks += [Heading(3, "Largest Cash Movements Between Consecutive Samples"),
                   Table(["Type", "Samples", "Days", "Balance Change", "What Else Changed"],
                         rows, ["left", "left", "right", "right", "left"]),
                   Note("Reading", "A balance change is net cash flow: income minus every cost, including infrastructure "
                                   "and purchases. The snapshot does not itemise it; the last column only lists what "
                                   "visibly changed in the same interval.")]

    changed = [e for e in events if e.added or e.removed or e.lines_created or e.lines_removed]
    changed.sort(key=lambda e: (-(len(e.added) + len(e.removed) + len(e.lines_created) + len(e.lines_removed)),
                                e.end.game_time))
    if changed:
        shown = changed[:MAX_EVENT_ROWS]
        blocks.append(Heading(3, f"Biggest Fleet and Network Changes ({len(shown)} of {len(changed)} changing intervals)"))
        blocks.append(Table(
            ["Samples", "Vehicles Added", "Added (names)", "Vehicles Removed", "Removed (names)",
             "Lines Created", "Lines Removed", "Removed Lines (names)"],
            [[f"{e.start.label} -> {e.end.label}", len(e.added), _names([v["name"] for v in e.added]),
              len(e.removed), _names([v["name"] for v in e.removed]),
              len(e.lines_created), len(e.lines_removed), _names(e.lines_removed)] for e in shown],
            ["left", "right", "left", "right", "left", "right", "right", "left"]))
        created = [(e, n) for e in changed for n in e.lines_created]
        if created:
            blocks.append(Paragraph("Lines created: " + "; ".join(f"{n} (seen {e.end.label})" for e, n in created[:8])
                                    + (f"; and {len(created) - 8} more" if len(created) > 8 else "") + "."))
    else:
        blocks.append(Paragraph("No vehicle or line was created or removed between any consecutive samples."))

    loan = [e for e in events if e.d_loan]
    if loan:
        blocks += [Heading(3, "Loan Changes"),
                   Table(["Samples", "Loan Before", "Loan After", "Change"],
                         [[f"{e.start.label} -> {e.end.label}", e.start.loan, e.end.loan, e.d_loan]
                          for e in loan[:MAX_EVENT_ROWS]], ["left", "right", "right", "right"])]
    elif all(p.loan is not None for p in pts):
        blocks.append(Paragraph(f"The loan never changed across the samples (always {_fmt(pts[0].loan)})."))

    extremes = []
    bal = [p for p in pts if p.balance is not None]
    if bal:
        hi, lo = max(bal, key=lambda p: p.balance), min(bal, key=lambda p: p.balance)
        extremes += [["Highest sampled balance", hi.label, hi.balance], ["Lowest sampled balance", lo.label, lo.balance]]
    fleet_hi = max(pts, key=lambda p: len(p.vehicles))
    fleet_lo = min(pts, key=lambda p: len(p.vehicles))
    extremes += [["Largest sampled fleet", fleet_hi.label, len(fleet_hi.vehicles)],
                 ["Smallest sampled fleet", fleet_lo.label, len(fleet_lo.vehicles)]]
    prof = [p for p in pts if p.rolling_profit is not None]
    if prof:
        ph, pl = max(prof, key=lambda p: p.rolling_profit), min(prof, key=lambda p: p.rolling_profit)
        extremes += [["Highest rolling line profit level", ph.label, ph.rolling_profit],
                     ["Lowest rolling line profit level", pl.label, pl.rolling_profit]]
    blocks += [Heading(3, "Sampled Extremes"),
               Table(["Extreme", "Sample", "Value"], extremes, ["left", "left", "right"]),
               Note("Sampling Limit", "Extremes are among stored samples only; true peaks and troughs between samples "
                                      "are not visible.")]
    return blocks


def _earnings_section(pts: Sequence[_Point]) -> list[Any]:
    title = "Company Earnings Counter Behaviour"
    usable = [p for p in pts if p.balance is not None and p.earnings is not None]
    if len(usable) < 3:
        return _insufficient(title, "Fewer than three samples carry both balance and the raw earnings counter.")
    segments: list[list[_Point]] = [[usable[0]]]
    for p in usable[1:]:
        last = segments[-1][-1]
        if abs((p.balance - p.earnings) - (last.balance - last.earnings)) <= CASH_TOLERANCE:
            segments[-1].append(p)
        else:
            segments.append([p])
    blocks: list[Any] = [Heading(2, title)]
    if len(segments) > max(3, len(usable) // 4):
        return blocks + [Paragraph(
            "Observation: the raw earnings counter does not move one-for-one with the balance across samples, so no "
            "stable relationship could be derived; it is not interpreted here.")]
    rows = [[str(i + 1), s[0].label, s[-1].label, len(s), s[0].earnings, s[-1].earnings,
             s[0].balance - s[0].earnings] for i, s in enumerate(segments)]
    blocks.append(Table(
        ["Segment", "From", "To", "Samples", "Earnings at Start", "Earnings at End", "Balance - Earnings Offset"],
        rows[:MAX_EVENT_ROWS], ["right", "left", "left", "right", "right", "right", "right"]))
    if len(segments) == 1:
        blocks.append(Paragraph(
            "Observation: across all samples the raw earnings counter differs from the balance by one constant, so it "
            "has moved exactly with the balance and was never reset in this history."))
    else:
        blocks.append(Paragraph(
            f"Observation: within each segment the raw earnings counter moves exactly with the balance; the offset changed "
            f"{len(segments) - 1} time(s). Inference (unverified): earnings looks like net cash change since the "
            "last reset of some accounting window, so the value just before a reset would be that window's net "
            "result. Its semantics are undocumented, so treat it as a hint, not an income statement."))
    return blocks


def _cohort_section(pts: Sequence[_Point], tpd: float | None) -> list[Any]:
    title = "Surviving Fleet by Purchase Year"
    last = pts[-1]
    if tpd is None or last.day is None:
        return _insufficient(title, "Converting purchase times to calendar years needs a calibration span of at "
                                    "least 28 calendar days between samples.")
    cohorts: dict[int, Counter] = {}
    unknown = 0
    for v in last.vehicles.values():
        if v["purchase"] is None or v["purchase"] > last.game_time:
            unknown += 1
            continue
        year = _year_of(last.day - (last.game_time - v["purchase"]) / tpd)
        if year is None:
            unknown += 1
            continue
        cohorts.setdefault(year, Counter())[v["carrier"]] += 1
    if not cohorts:
        return _insufficient(title, "No vehicle in the latest sample carries a usable purchase time.")
    carriers = sorted({c for ctr in cohorts.values() for c in ctr})
    total = sum(sum(ctr.values()) for ctr in cohorts.values())
    years = list(range(min(cohorts), max(cohorts) + 1))
    rows = [[str(y), sum(cohorts.get(y, Counter()).values()), _fmt_pct(sum(cohorts.get(y, Counter()).values()) / total),
             *[cohorts.get(y, Counter()).get(c, 0) for c in carriers]] for y in years]
    blocks: list[Any] = [
        Heading(2, title),
        Paragraph(
            f"Vehicles in the latest sample ({last.label}) grouped by estimated purchase year. This reaches back before "
            "the first stored snapshot, but it only counts vehicles that still exist: anything sold or scrapped earlier "
            "is absent, so older years are undercounted. Purchase dates are converted with the calibrated ticks per day "
            "and may be off by a few weeks near year boundaries."),
        Table(["Purchase Year", "Surviving Vehicles", "Share of Fleet", *[f"{c} Vehicles" for c in carriers]],
              rows, ["right"] * (3 + len(carriers)))]
    if unknown:
        blocks.append(Paragraph(f"{unknown} vehicle(s) without a usable purchase time are excluded."))
    cats = [str(y) for y in years][-MAX_CHART_POINTS:]
    if len(cats) >= 2:
        blocks.append(Chart("bar", "Surviving Vehicles by Purchase Year", cats,
                            [("Vehicles", [float(sum(cohorts.get(y, Counter()).values())) for y in years][-MAX_CHART_POINTS:])]))
    return blocks


def _limits_section(pts: Sequence[_Point], raw: Sequence[_Point], tpd: float | None, level: str) -> list[Any]:
    first, last = pts[0], pts[-1]
    span = round(_days_between(first, last)) if len(pts) > 1 else 0
    years = span / 365.25
    cadence = (f"about one sample every {statistics.median(_days_between(a, b) for a, b in zip(pts, pts[1:])):.0f} "
               "days") if len(pts) > 1 else "a single sample"
    items = [
        f"Sampling: this history is {len(raw)} snapshots covering {span} calendar days ({years:.2f} years) at {cadence}. "
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
        "Scope: one companion store holds one save; do not read mixed saves into one history.",
    ]
    if span < 365:
        items.append(f"What is missing today: {span} days is less than one calendar year, so year-over-year comparison, "
                     "annualised growth, and seasonal patterns are unavailable. They appear automatically as snapshots accumulate.")
    elif level != "month":
        items.append(f"Aggregation is at {level} level because the span is long; monthly detail stays in the stored "
                     "snapshots but is not tabulated.")
    return [Heading(2, "What This History Can and Cannot Tell You"), *[Paragraph(i) for i in items]]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def build(store: Store) -> ReportDocument:
    latest = store.latest()
    if latest is None:
        raise ValueError("no snapshot found")
    raw = [point for point in _load_points(store) if point.game_time <= latest.game_time]
    if not raw:
        raise ValueError("no snapshot found")
    mismatch = store.conn.execute(
        "SELECT 1 FROM snapshots WHERE game_time > ? LIMIT 1", (latest.game_time,)
    ).fetchone() is not None
    tpd = _ticks_per_day(raw)
    pts = _merge_near_duplicates(raw, tpd)

    company_name = "Primary Company"
    if latest is not None:
        company_name = latest.company.get("name") or company_name

    errors_total = sum(1 for p in raw if p.errors)
    base_header = [("Company / Save", company_name)]
    limits = ("Rolling profit is a level, never summed; load is instantaneous; transportedYear accounting is "
              "unverified; samples are observations, not continuous telemetry.")

    if not pts:
        header = base_header + [
            ("History Span", "No snapshot carries a calendar date"),
            ("Snapshots Used", f"0 of {len(raw)}"),
            ("Collection Errors", f"{errors_total} sample(s) with errors" if errors_total else "None reported"),
            ("Measurement Limits", limits),
        ]
        return ReportDocument("history", "Company History Report", header, [
            Heading(2, "Summary of the Recorded History"),
            Note(INSUFFICIENT, "No stored snapshot carries a calendar date, so the history cannot be placed on a timeline.")])

    first, last = pts[0], pts[-1]
    span_months = (last.ymd[0] * 12 + last.ymd[1]) - (first.ymd[0] * 12 + first.ymd[1]) + 1
    level = _level_for(span_months)
    level_reason = {
        "month": f"Monthly aggregation is used because the history spans {span_months} calendar month(s) (limit 18).",
        "quarter": f"Quarterly aggregation is used because the history spans {span_months} calendar months (19-72).",
        "year": f"Yearly aggregation is used because the history spans {span_months} calendar months (over 72).",
    }[level]
    events = _events(pts)
    periods = _build_periods(pts, level, events)

    span_days = round(_days_between(first, last))
    header = base_header + [
        ("History Span", f"{first.label} to {last.label} ({span_days} calendar days)"),
        ("Latest Sample Date", last.label),
        ("Snapshots Used", f"{len(pts)} of {len(raw)} stored (near-duplicates within one day merged)"),
        ("Aggregation", f"{level} ({len(periods)} period(s)); closing sample represents each period"),
        ("Collection Errors", f"{errors_total} of {len(raw)} samples reported errors" if errors_total else "None reported"),
        ("Measurement Limits", limits),
    ]

    blocks: list[Any] = []
    blocks += _summary_section(pts, periods, events)
    blocks += _coverage_section(raw, pts, periods, level, tpd, mismatch)
    blocks += _growth_section(pts)
    blocks += _finance_section(periods, level, level_reason)
    blocks += _network_section(periods, level)
    blocks += _turnover_section(periods, events, level)
    blocks += _traffic_section(periods, pts, level)
    blocks += _yoy_section(periods, pts, level)
    blocks += _year_end_section(pts)
    blocks += _milestones_section(pts, events)
    blocks += _earnings_section(pts)
    blocks += _cohort_section(pts, tpd)
    blocks += _limits_section(pts, raw, tpd, level)
    return ReportDocument("history", "Company History Report", header, blocks)
