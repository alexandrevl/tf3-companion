"""Company history analysis: periods, coverage, growth, year comparisons, turnover, milestones, earnings offsets, cohorts.

Pure over compact per-sample records and the endpoint-bounded calendar clock of the evaluation context.
Elapsed time always comes from that clock (never nominal tick arithmetic). Transport counters stay raw
sampled levels and differences; rolling profit is a level at a sample and is never summed; nothing here
infers earned income.
"""

from __future__ import annotations

import datetime as dt
import re
import statistics
from collections import Counter
from dataclasses import dataclass
from typing import Any, Sequence

from ..game_time import DAYS_PER_YEAR, GameCalendarClock
from .history_evidence import HistoryEvidence, HistorySample
from .models import EvaluationContext, SampleRef, Unavailable, ViewCoverage

# Engine-owned diagnostics and aggregation safeguards (not methodology policy).
CASH_TOLERANCE = 1000  # balance - earnings offset drift treated as "same offset"
MONTH_LEVEL_MAX_MONTHS = 18  # up to this many calendar months: month periods
QUARTER_LEVEL_MAX_MONTHS = 72  # up to this many: quarter periods, beyond: year periods
LONG_GAP_DAYS = 15
LONG_GAP_MEDIAN_FACTOR = 2.5
TICK_RATE_TOLERANCE = 0.05
MILESTONE_COUNT = 3  # largest cash drops and jumps kept
EARNINGS_MIN_SAMPLES = 3
ANNUALISE_MIN_DAYS = 365
MIN_DIAGNOSTIC_SPAN_DAYS = 28

Key = tuple[int, int]


@dataclass(frozen=True)
class Criterion:
    """A fixed engine-owned heuristic or safeguard, disclosed rather than configurable."""

    name: str
    value: float
    unit: str
    note: str


@dataclass(frozen=True)
class HistoryEndpoint:
    """The selected endpoint's own facts, kept even when the timeline cannot be used."""

    sample: SampleRef
    company_name: str | None
    balance: Any
    loan: Any


@dataclass(frozen=True)
class HistoryPoint:
    """One merged sample of the history. Unknown counters are None, never zero."""

    tick: int
    label: str
    year: int
    month: int
    day: int
    ordinal: int
    reason: str | None
    balance: int | None
    loan: int | None
    net: int | None
    earnings: int | None
    score: int | None
    track: int | None
    passengers: int | None
    cargo: int | None
    vehicles: int
    lines: int
    stations: int
    rolling_profit: int | None
    lines_losing: int
    lines_with_profit: int
    carriers: dict[str, int]


@dataclass(frozen=True)
class HistoryPeriod:
    """The closing sample of a calendar period compared with the previous closing (or first) sample."""

    year: int
    slot: int  # month 1-12, quarter 1-4, or 0 for a year
    label: str
    samples: int
    close: HistoryPoint
    baseline: HistoryPoint
    compared: bool  # False when the closing sample is itself the baseline
    days: float | None  # calendar days between baseline and close; None when not positive/unknown
    balance_change: int | None
    balance_change_percent: float | None
    vehicles_change: int | None
    lines_change: int | None
    passengers_change: int | None
    cargo_change: int | None
    vehicles_added: int
    vehicles_removed: int
    net_vehicles: int
    added_value: int | None  # known recorded value of added vehicles; None when none carries a value
    lines_created: int
    lines_removed: int


@dataclass(frozen=True)
class VehicleRef:
    id: int
    name: str
    carrier: str
    value: int | None


@dataclass(frozen=True)
class LineRef:
    id: int
    name: str


@dataclass(frozen=True)
class HistoryEvent:
    """What changed between two consecutive merged samples."""

    start_tick: int
    start_label: str
    end_tick: int
    end_label: str
    days: float | None
    balance_change: int | None
    loan_start: int | None
    loan_end: int | None
    loan_change: int | None
    track_change: int | None
    vehicles_added: tuple[VehicleRef, ...]
    vehicles_removed: tuple[VehicleRef, ...]
    lines_created: tuple[LineRef, ...]
    lines_removed: tuple[LineRef, ...]


@dataclass(frozen=True)
class Gap:
    start_tick: int
    start_label: str
    end_tick: int
    end_label: str
    days: float


@dataclass(frozen=True)
class CollectorFailure:
    family: str
    samples: int


@dataclass(frozen=True)
class ErrorSummary:
    samples: int  # stored samples that reported collector errors
    first_label: str
    last_label: str
    collectors: tuple[CollectorFailure, ...]  # failing collector families, most frequent first


@dataclass(frozen=True)
class HistoryCadence:
    span_days: float | None
    median_gap_days: float | None
    largest_gap_days: float | None
    gaps_longer_than_usual: tuple[Gap, ...]  # longest first
    periods_with_data: int
    periods_expected: int
    missing_periods: tuple[str, ...]
    reasons: dict[str, int]  # stored-sample reasons, "unknown" when absent
    ticks_per_day: float | None  # whole-span diagnostic, never a conversion rate
    nominal_ticks_per_day: float | None  # implied by meta.yearDuration, disclosure only
    tick_rate_ratio: float | None
    tick_rate_diverges: bool
    errors: ErrorSummary | None


@dataclass(frozen=True)
class EndpointChanges:
    """Raw differences between the first and latest usable sample; counters are not period volumes."""

    balance_change: int | None
    balance_change_percent: float | None
    passengers_change: int | None
    cargo_change: int | None


@dataclass(frozen=True)
class ProfitLevel:
    label: str
    tick: int
    value: int
    lines_losing: int
    lines_with_profit: int


@dataclass(frozen=True)
class RollingProfitSummary:
    first: ProfitLevel
    peak: ProfitLevel
    latest: ProfitLevel
    latest_vs_peak_percent: float | None


@dataclass(frozen=True)
class GrowthRow:
    code: str
    first: int | None
    latest: int | None
    change: int | None
    change_percent: float | None
    annualised_percent: float | None  # only for level metrics over at least one calendar year with positive ends


@dataclass(frozen=True)
class YearOverYearPair:
    label: str
    prior_label: str
    balance_prior: int | None
    balance_now: int | None
    balance_percent: float | None
    vehicles_prior: int
    vehicles_now: int
    lines_prior: int
    lines_now: int
    profit_prior: int | None
    profit_now: int | None
    profit_percent: float | None


@dataclass(frozen=True)
class NextComparison:
    """When the first same-period comparison becomes possible, from calendar ordinals."""

    earliest_date: str | None
    days_after_latest: int | None


@dataclass(frozen=True)
class YearEnd:
    year: int
    label: str
    tick: int
    balance: int | None
    balance_change: int | None
    vehicles: int
    lines: int
    rolling_profit: int | None


@dataclass(frozen=True)
class Extreme:
    code: str  # highest-balance | lowest-balance | largest-fleet | smallest-fleet | highest-rolling-profit | lowest-rolling-profit
    label: str
    tick: int
    value: int


@dataclass(frozen=True)
class CounterDecrease:
    start_tick: int
    start_label: str
    end_tick: int
    end_label: str


@dataclass(frozen=True)
class TrafficCounters:
    has_counters: bool
    decreases: tuple[CounterDecrease, ...]  # consecutive merged samples between which a raw counter decreased


@dataclass(frozen=True)
class EarningsSegment:
    index: int
    start_label: str
    end_label: str
    start_tick: int
    end_tick: int
    samples: int
    earnings_start: int
    earnings_end: int
    offset: int  # balance - earnings at the segment start


@dataclass(frozen=True)
class EarningsBehaviour:
    """Whether the raw earnings counter tracks the balance by a constant offset. No income is inferred."""

    status: str  # insufficient-samples | unstable-offset | segments
    usable_samples: int
    segment_count: int
    offset_changes: int | None
    segments: tuple[EarningsSegment, ...]  # only when status is "segments"


@dataclass(frozen=True)
class PurchaseCohort:
    year: int
    vehicles: int
    share: float  # of the latest sample's vehicles with a supported purchase year
    carriers: dict[str, int]


@dataclass(frozen=True)
class PurchaseCohorts:
    sample: SampleRef
    fleet: int
    dated_vehicles: int
    unknown_vehicles: int
    unknown_reasons: dict[str, int]
    carriers: tuple[str, ...]
    cohorts: tuple[PurchaseCohort, ...]  # every year from the first to the last cohort year, empty years included


@dataclass(frozen=True)
class HistoryView:
    coverage: ViewCoverage
    status: str  # ok | ambiguous-timeline | no-dated-samples
    endpoint: HistoryEndpoint
    stored_samples: int
    usable_samples: int
    unused_samples: int  # stored samples that are not a usable merged sample (merged or undated)
    undated_samples: int
    later_samples: int  # stored samples after the endpoint (count only, never read)
    error_samples: int
    level: str | None
    span_months: int | None
    span_days: float | None
    points: tuple[HistoryPoint, ...]
    periods: tuple[HistoryPeriod, ...]
    interval_count: int
    cadence: HistoryCadence | None
    endpoint_changes: EndpointChanges | None
    rolling_profit: RollingProfitSummary | None
    growth: tuple[GrowthRow, ...]
    annualised: bool
    traffic: TrafficCounters | None
    year_over_year: tuple[YearOverYearPair, ...]
    next_comparison: NextComparison | None
    year_ends: tuple[YearEnd, ...]
    cash_drops: tuple[HistoryEvent, ...]  # largest balance falls, most negative first
    cash_jumps: tuple[HistoryEvent, ...]  # largest balance rises first
    changed_intervals: tuple[HistoryEvent, ...]  # intervals with fleet or line changes, biggest first
    loan_changes: tuple[HistoryEvent, ...]
    constant_loan: int | None  # the loan when it never changed and is known at every sample
    extremes: tuple[Extreme, ...]
    earnings: EarningsBehaviour | None
    cohorts: PurchaseCohorts | None
    criteria: tuple[Criterion, ...]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _delta(curr: int | None, prev: int | None) -> int | None:
    return None if curr is None or prev is None else curr - prev


def _pct(curr: int | None, prev: int | None) -> float | None:
    if curr is None or prev in (None, 0):
        return None
    return (curr - prev) / abs(prev) * 100


def _year_of(day: float) -> int | None:
    try:
        return dt.date.fromordinal(int(day)).year
    except ValueError:
        return None


def _date_text(day: float) -> str | None:
    try:
        return dt.date.fromordinal(int(day)).isoformat()
    except ValueError:
        return None


def _days(clock: GameCalendarClock, a: int, b: int) -> float | None:
    measure = clock.elapsed_between_ticks(a, b)
    return None if measure.value is None else measure.value * DAYS_PER_YEAR


def _merge_near_duplicates(samples: Sequence[HistorySample], clock: GameCalendarClock) -> list[HistorySample]:
    """Keep the latest observation on each exported calendar day, without nominal tick estimates."""
    out: list[HistorySample] = []
    for s in samples:
        if s.ordinal is None:
            continue
        if out and clock.elapsed_between_ticks(out[-1].tick, s.tick).value == 0:
            out[-1] = s
        else:
            out.append(s)
    return out


def _observed_ticks_per_day(samples: Sequence[HistorySample]) -> float | None:
    dated = [s for s in samples if s.ordinal is not None]
    if len(dated) < 2:
        return None
    days = dated[-1].ordinal - dated[0].ordinal
    ticks = dated[-1].tick - dated[0].tick
    return ticks / days if days >= MIN_DIAGNOSTIC_SPAN_DAYS and ticks > 0 else None


def _level_for(span_months: int) -> str:
    if span_months <= MONTH_LEVEL_MAX_MONTHS:
        return "month"
    if span_months <= QUARTER_LEVEL_MAX_MONTHS:
        return "quarter"
    return "year"


def _key(s: HistorySample, level: str) -> Key:
    y, m, _ = s.ymd
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


def _point(s: HistorySample) -> HistoryPoint:
    carriers = Counter(v[2] for v in s.vehicles)
    return HistoryPoint(
        tick=s.tick,
        label=s.label,
        year=s.ymd[0],
        month=s.ymd[1],
        day=s.ymd[2],
        ordinal=s.ordinal,
        reason=s.reason,
        balance=s.balance,
        loan=s.loan,
        net=None if s.balance is None or s.loan is None else s.balance - s.loan,
        earnings=s.earnings,
        score=s.score,
        track=s.track,
        passengers=s.passengers,
        cargo=s.cargo,
        vehicles=len(s.vehicles),
        lines=len(s.lines),
        stations=s.stations,
        rolling_profit=s.rolling_profit,
        lines_losing=s.lines_losing,
        lines_with_profit=s.lines_with_profit,
        carriers=dict(sorted(carriers.items())),
    )


def _event(a: HistorySample, b: HistorySample, clock: GameCalendarClock) -> HistoryEvent:
    a_vehicles = {v[0] for v in a.vehicles}
    b_vehicles = {v[0] for v in b.vehicles}
    a_lines = {line[0] for line in a.lines}
    b_lines = {line[0] for line in b.lines}
    return HistoryEvent(
        start_tick=a.tick,
        start_label=a.label,
        end_tick=b.tick,
        end_label=b.label,
        days=_days(clock, a.tick, b.tick),
        balance_change=_delta(b.balance, a.balance),
        loan_start=a.loan,
        loan_end=b.loan,
        loan_change=_delta(b.loan, a.loan),
        track_change=_delta(b.track, a.track),
        vehicles_added=tuple(VehicleRef(v[0], v[1], v[2], v[3]) for v in b.vehicles if v[0] not in a_vehicles),
        vehicles_removed=tuple(VehicleRef(v[0], v[1], v[2], v[3]) for v in a.vehicles if v[0] not in b_vehicles),
        lines_created=tuple(LineRef(*line) for line in b.lines if line[0] not in a_lines),
        lines_removed=tuple(LineRef(*line) for line in a.lines if line[0] not in b_lines),
    )


def _changes(e: HistoryEvent) -> int:
    return len(e.vehicles_added) + len(e.vehicles_removed) + len(e.lines_created) + len(e.lines_removed)


def _periods(
    pts: Sequence[HistorySample],
    points: dict[int, HistoryPoint],
    level: str,
    events: Sequence[HistoryEvent],
    clock: GameCalendarClock,
) -> tuple[HistoryPeriod, ...]:
    groups: dict[Key, list[HistorySample]] = {}
    for s in pts:
        groups.setdefault(_key(s, level), []).append(s)
    counts: dict[Key, list[Any]] = {
        k: [0, 0, None, 0, 0] for k in groups
    }  # added, removed, value, created, removed lines
    end_keys = {s.tick: _key(s, level) for s in pts}
    for e in events:
        c = counts[end_keys[e.end_tick]]
        c[0] += len(e.vehicles_added)
        c[1] += len(e.vehicles_removed)
        c[3] += len(e.lines_created)
        c[4] += len(e.lines_removed)
        values = [v.value for v in e.vehicles_added if v.value is not None]
        if values:
            c[2] = (c[2] or 0) + sum(values)
    out: list[HistoryPeriod] = []
    prev = pts[0]
    for key in sorted(groups):
        closing = groups[key][-1]
        close, base = points[closing.tick], points[prev.tick]
        compared = closing is not prev
        days = _days(clock, prev.tick, closing.tick)
        added, removed, value, created, lines_removed = counts[key]
        out.append(
            HistoryPeriod(
                year=key[0],
                slot=key[1],
                label=_label(key, level),
                samples=len(groups[key]),
                close=close,
                baseline=base,
                compared=compared,
                days=days if days is not None and days > 0 else None,
                balance_change=_delta(close.balance, base.balance) if compared else None,
                balance_change_percent=_pct(close.balance, base.balance) if compared else None,
                vehicles_change=close.vehicles - base.vehicles if compared else None,
                lines_change=close.lines - base.lines if compared else None,
                passengers_change=_delta(close.passengers, base.passengers) if compared else None,
                cargo_change=_delta(close.cargo, base.cargo) if compared else None,
                vehicles_added=added,
                vehicles_removed=removed,
                net_vehicles=added - removed,
                added_value=value,
                lines_created=created,
                lines_removed=lines_removed,
            )
        )
        prev = closing
    return tuple(out)


def _cadence(
    raw: Sequence[HistorySample],
    pts: Sequence[HistorySample],
    periods: Sequence[HistoryPeriod],
    level: str,
    clock: GameCalendarClock,
    span: float | None,
) -> HistoryCadence:
    gaps = []
    for a, b in zip(pts, pts[1:]):
        days = _days(clock, a.tick, b.tick)
        if days is not None:
            gaps.append(Gap(a.tick, a.label, b.tick, b.label, days))
    median_gap = statistics.median(g.days for g in gaps) if gaps else None
    long_gaps: tuple[Gap, ...] = ()
    if median_gap is not None:
        long_gaps = tuple(
            sorted(
                (g for g in gaps if g.days >= LONG_GAP_DAYS and g.days > LONG_GAP_MEDIAN_FACTOR * median_gap),
                key=lambda g: -g.days,
            )
        )
    present = {(p.year, p.slot) for p in periods}
    expected = _all_keys(min(present), max(present), level)
    tpd = _observed_ticks_per_day(raw)
    nominal = ratio = None
    if tpd and pts[-1].year_duration:
        nominal = pts[-1].year_duration / DAYS_PER_YEAR
        ratio = tpd / nominal
    errored = [s for s in raw if s.errors]
    errors = None
    if errored:
        collectors: Counter = Counter()
        for s in errored:
            for name in sorted({re.sub(r"\[\d+\]", "[]", e.split(":", 1)[0])[:80] for e in s.errors}):
                collectors[name] += 1
        errors = ErrorSummary(
            len(errored),
            errored[0].label,
            errored[-1].label,
            tuple(CollectorFailure(n, c) for n, c in sorted(collectors.items(), key=lambda kv: (-kv[1], kv[0]))),
        )
    return HistoryCadence(
        span_days=span,
        median_gap_days=median_gap,
        largest_gap_days=max((g.days for g in gaps), default=None),
        gaps_longer_than_usual=long_gaps,
        periods_with_data=len(present),
        periods_expected=len(expected),
        missing_periods=tuple(_label(k, level) for k in expected if k not in present),
        reasons=dict(sorted(Counter(s.reason or "unknown" for s in raw).items())),
        ticks_per_day=tpd,
        nominal_ticks_per_day=nominal,
        tick_rate_ratio=ratio,
        tick_rate_diverges=ratio is not None and abs(ratio - 1) > TICK_RATE_TOLERANCE,
        errors=errors,
    )


def _growth(first: HistoryPoint, last: HistoryPoint, span: float) -> tuple[GrowthRow, ...]:
    metrics: list[tuple[str, int | None, int | None, bool]] = [
        ("balance", first.balance, last.balance, True),
        ("loan", first.loan, last.loan, False),
        ("net", first.net, last.net, True),
        ("vehicles", first.vehicles, last.vehicles, True),
        ("lines", first.lines, last.lines, True),
        ("stations", first.stations, last.stations, True),
        ("track", first.track, last.track, True),
        ("score", first.score, last.score, True),
        ("rolling-profit", first.rolling_profit, last.rolling_profit, True),
        ("passengers-counter", first.passengers, last.passengers, False),
        ("cargo-counter", first.cargo, last.cargo, False),
    ]
    annualise = span >= ANNUALISE_MIN_DAYS
    rows = []
    for code, a, b, annual_ok in metrics:
        annual = None
        if annualise and annual_ok and a and b and a > 0 and b > 0:
            annual = ((b / a) ** (DAYS_PER_YEAR / span) - 1) * 100
        rows.append(GrowthRow(code, a, b, _delta(b, a), _pct(b, a), annual))
    return tuple(rows)


def _earnings(pts: Sequence[HistorySample]) -> EarningsBehaviour:
    usable = [s for s in pts if s.balance is not None and s.earnings is not None]
    if len(usable) < EARNINGS_MIN_SAMPLES:
        return EarningsBehaviour("insufficient-samples", len(usable), 0, None, ())
    segments: list[list[HistorySample]] = [[usable[0]]]
    for s in usable[1:]:
        last = segments[-1][-1]
        if abs((s.balance - s.earnings) - (last.balance - last.earnings)) <= CASH_TOLERANCE:
            segments[-1].append(s)
        else:
            segments.append([s])
    if len(segments) > max(3, len(usable) // 4):
        return EarningsBehaviour("unstable-offset", len(usable), len(segments), len(segments) - 1, ())
    rows = tuple(
        EarningsSegment(
            i + 1,
            g[0].label,
            g[-1].label,
            g[0].tick,
            g[-1].tick,
            len(g),
            g[0].earnings,
            g[-1].earnings,
            g[0].balance - g[0].earnings,
        )
        for i, g in enumerate(segments)
    )
    return EarningsBehaviour("segments", len(usable), len(segments), len(segments) - 1, rows)


def _cohorts(last: HistorySample, clock: GameCalendarClock) -> PurchaseCohorts:
    cohorts: dict[int, Counter] = {}
    reasons: Counter = Counter()
    for _, _, carrier, _, purchase in last.vehicles:
        if purchase is None:
            reasons["missing-purchase-time"] += 1
            continue
        if purchase > last.tick:
            reasons["future-timestamp"] += 1
            continue
        estimate = clock.calendar_at_tick(purchase)
        year = _year_of(estimate.ordinal) if estimate.ordinal is not None else None
        if year is None:
            reasons[estimate.reason or "invalid-calendar-date"] += 1
            continue
        cohorts.setdefault(year, Counter())[carrier] += 1
    total = sum(sum(c.values()) for c in cohorts.values())
    carriers = tuple(sorted({c for ctr in cohorts.values() for c in ctr}))
    rows = []
    if cohorts:
        for y in range(min(cohorts), max(cohorts) + 1):
            ctr = cohorts.get(y, Counter())
            rows.append(PurchaseCohort(y, sum(ctr.values()), sum(ctr.values()) / total, dict(sorted(ctr.items()))))
    return PurchaseCohorts(
        SampleRef(last.tick, last.label),
        len(last.vehicles),
        total,
        sum(reasons.values()),
        dict(sorted(reasons.items())),
        carriers,
        tuple(rows),
    )


CRITERIA = (
    Criterion(
        "month-level-max-months",
        MONTH_LEVEL_MAX_MONTHS,
        "months",
        "Spans up to this many calendar months aggregate by month.",
    ),
    Criterion(
        "quarter-level-max-months",
        QUARTER_LEVEL_MAX_MONTHS,
        "months",
        "Longer spans up to this aggregate by quarter, beyond it by year.",
    ),
    Criterion(
        "long-gap-minimum",
        LONG_GAP_DAYS,
        "days",
        "A cadence gap must reach this and exceed the median factor to be listed.",
    ),
    Criterion(
        "long-gap-median-factor",
        LONG_GAP_MEDIAN_FACTOR,
        "x median gap",
        "Cadence gaps beyond this multiple of the median are listed.",
    ),
    Criterion(
        "tick-rate-tolerance",
        TICK_RATE_TOLERANCE,
        "ratio",
        "Whole-span ticks per day is flagged when it differs from the nominal by more than this; a diagnostic only.",
    ),
    Criterion(
        "earnings-offset-tolerance",
        CASH_TOLERANCE,
        "money",
        "Balance minus raw earnings drift treated as one offset segment; a heuristic, not accounting.",
    ),
    Criterion(
        "earnings-minimum-samples",
        EARNINGS_MIN_SAMPLES,
        "samples",
        "Samples with both balance and earnings needed to look at offsets.",
    ),
    Criterion(
        "annualisation-minimum-span",
        ANNUALISE_MIN_DAYS,
        "days",
        "Annualised growth only for spans of at least this many calendar days.",
    ),
    Criterion("milestone-count", MILESTONE_COUNT, "events", "Largest cash drops and jumps retained."),
)


def evaluate(evidence: HistoryEvidence, *, context: EvaluationContext) -> HistoryView:
    clock = context.clock
    raw = evidence.samples
    facts = evidence.endpoint_facts
    endpoint = HistoryEndpoint(evidence.endpoint, facts.company_name, facts.balance, facts.loan)
    pts = _merge_near_duplicates(raw, clock) if not clock.ambiguous else []
    undated = sum(1 for s in raw if s.ordinal is None)
    error_samples = sum(1 for s in raw if s.errors)
    families = sorted({re.sub(r"\[\d+\]", "[]", e.split(":", 1)[0])[:80] for s in raw for e in s.errors})
    warnings = []
    unavailable = []
    if evidence.later_samples:
        warnings.append("later-samples-stored")
    if clock.ambiguous:
        status = "ambiguous-timeline"
        unavailable.append(Unavailable("ambiguous-timeline", "historical durations and comparisons are unavailable"))
    elif not pts:
        status = "no-dated-samples"
        unavailable.append(Unavailable("missing-calendar-date", "no stored sample carries a calendar date"))
    else:
        status = "ok"
    if undated:
        warnings.append("undated-samples-excluded")

    def coverage(points: Sequence[HistoryPoint] = ()) -> ViewCoverage:
        sampled = (
            (SampleRef(points[0].tick, points[0].label), SampleRef(points[-1].tick, points[-1].label)) if points else ()
        )
        return ViewCoverage(
            endpoint=evidence.endpoint,
            eligible=evidence.eligible,
            read=len(raw),
            used=len(pts),
            hydrated=evidence.hydrated,
            hydration_limit=evidence.hydration_limit,
            sampled=sampled,
            limits={
                "samples": "every eligible sample at or before the endpoint, compact projection",
                "hydratedSnapshots": evidence.hydration_limit,
            },
            omitted=len(raw) - len(pts),
            warnings=tuple(warnings),
            collection_errors=tuple(families),
            unavailable=tuple(unavailable),
        )

    def bare() -> HistoryView:
        return HistoryView(
            coverage=coverage(),
            status=status,
            endpoint=endpoint,
            stored_samples=len(raw),
            usable_samples=len(pts),
            unused_samples=len(raw) - len(pts),
            undated_samples=undated,
            later_samples=evidence.later_samples,
            error_samples=error_samples,
            level=None,
            span_months=None,
            span_days=None,
            points=(),
            periods=(),
            interval_count=0,
            cadence=None,
            endpoint_changes=None,
            rolling_profit=None,
            growth=(),
            annualised=False,
            traffic=None,
            year_over_year=(),
            next_comparison=None,
            year_ends=(),
            cash_drops=(),
            cash_jumps=(),
            changed_intervals=(),
            loan_changes=(),
            constant_loan=None,
            extremes=(),
            earnings=None,
            cohorts=None,
            criteria=CRITERIA,
        )

    if status != "ok":
        return bare()

    points = {s.tick: _point(s) for s in pts}
    series = tuple(points[s.tick] for s in pts)
    first, last = series[0], series[-1]
    span = _days(clock, pts[0].tick, pts[-1].tick)
    span_months = (last.year * 12 + last.month) - (first.year * 12 + first.month) + 1
    level = _level_for(span_months)
    events = tuple(_event(a, b, clock) for a, b in zip(pts, pts[1:]))
    periods = _periods(pts, points, level, events, clock)
    cadence = _cadence(raw, pts, periods, level, clock, span)

    comparable = len(pts) >= 2 and span is not None and span > 0
    endpoint_changes = rolling = None
    growth: tuple[GrowthRow, ...] = ()
    if comparable:
        endpoint_changes = EndpointChanges(
            balance_change=_delta(last.balance, first.balance),
            balance_change_percent=_pct(last.balance, first.balance),
            passengers_change=_delta(last.passengers, first.passengers),
            cargo_change=_delta(last.cargo, first.cargo),
        )
        growth = _growth(first, last, span)
        profit = [p for p in series if p.rolling_profit is not None]
        if len(profit) >= 2:
            peak = max(profit, key=lambda p: p.rolling_profit)

            def level_of(p: HistoryPoint) -> ProfitLevel:
                return ProfitLevel(p.label, p.tick, p.rolling_profit, p.lines_losing, p.lines_with_profit)

            rolling = RollingProfitSummary(
                level_of(profit[0]),
                level_of(peak),
                level_of(profit[-1]),
                _pct(profit[-1].rolling_profit, peak.rolling_profit),
            )

    traffic = TrafficCounters(
        any(p.passengers is not None or p.cargo is not None for p in series),
        tuple(
            CounterDecrease(a.tick, a.label, b.tick, b.label)
            for a, b in zip(series, series[1:])
            if (_delta(b.passengers, a.passengers) or 0) < 0 or (_delta(b.cargo, a.cargo) or 0) < 0
        ),
    )

    by_key = {(p.year, p.slot): p for p in periods}
    pairs = []
    for p in periods:
        prior = by_key.get((p.year - 1, p.slot))
        if prior is not None:
            a, b = prior.close, p.close
            pairs.append(
                YearOverYearPair(
                    p.label,
                    prior.label,
                    a.balance,
                    b.balance,
                    _pct(b.balance, a.balance),
                    a.vehicles,
                    b.vehicles,
                    a.lines,
                    b.lines,
                    a.rolling_profit,
                    b.rolling_profit,
                    _pct(b.rolling_profit, a.rolling_profit),
                )
            )
    next_comparison = None
    if not pairs:
        earliest = first.ordinal + DAYS_PER_YEAR
        next_comparison = NextComparison(_date_text(earliest), max(0, round(earliest - last.ordinal)))

    by_year: dict[int, HistoryPoint] = {}
    for p in series:
        by_year[p.year] = p
    year_ends: list[YearEnd] = []
    if len(by_year) >= 2:
        prev = None
        for year, p in sorted(by_year.items()):
            year_ends.append(
                YearEnd(
                    year,
                    p.label,
                    p.tick,
                    p.balance,
                    _delta(p.balance, prev.balance if prev else None),
                    p.vehicles,
                    p.lines,
                    p.rolling_profit,
                )
            )
            prev = p

    money = [e for e in events if e.balance_change is not None]
    drops = tuple(sorted((e for e in money if e.balance_change < 0), key=lambda e: e.balance_change)[:MILESTONE_COUNT])
    jumps = tuple(sorted((e for e in money if e.balance_change > 0), key=lambda e: -e.balance_change)[:MILESTONE_COUNT])
    changed = tuple(sorted((e for e in events if _changes(e)), key=lambda e: (-_changes(e), e.end_tick)))
    loan_changes = tuple(e for e in events if e.loan_change)
    constant_loan = first.loan if events and not loan_changes and all(p.loan is not None for p in series) else None

    extremes: list[Extreme] = []
    bal = [p for p in series if p.balance is not None]
    if bal:
        hi, lo = max(bal, key=lambda p: p.balance), min(bal, key=lambda p: p.balance)
        extremes += [
            Extreme("highest-balance", hi.label, hi.tick, hi.balance),
            Extreme("lowest-balance", lo.label, lo.tick, lo.balance),
        ]
    fleet_hi, fleet_lo = max(series, key=lambda p: p.vehicles), min(series, key=lambda p: p.vehicles)
    extremes += [
        Extreme("largest-fleet", fleet_hi.label, fleet_hi.tick, fleet_hi.vehicles),
        Extreme("smallest-fleet", fleet_lo.label, fleet_lo.tick, fleet_lo.vehicles),
    ]
    prof = [p for p in series if p.rolling_profit is not None]
    if prof:
        ph, pl = max(prof, key=lambda p: p.rolling_profit), min(prof, key=lambda p: p.rolling_profit)
        extremes += [
            Extreme("highest-rolling-profit", ph.label, ph.tick, ph.rolling_profit),
            Extreme("lowest-rolling-profit", pl.label, pl.tick, pl.rolling_profit),
        ]

    return HistoryView(
        coverage=coverage(series),
        status=status,
        endpoint=endpoint,
        stored_samples=len(raw),
        usable_samples=len(pts),
        unused_samples=len(raw) - len(pts),
        undated_samples=undated,
        later_samples=evidence.later_samples,
        error_samples=error_samples,
        level=level,
        span_months=span_months,
        span_days=span,
        points=series,
        periods=periods,
        interval_count=len(events),
        cadence=cadence,
        endpoint_changes=endpoint_changes,
        rolling_profit=rolling,
        growth=growth,
        annualised=comparable and span >= ANNUALISE_MIN_DAYS,
        traffic=traffic,
        year_over_year=tuple(pairs),
        next_comparison=next_comparison,
        year_ends=tuple(year_ends),
        cash_drops=drops,
        cash_jumps=jumps,
        changed_intervals=changed,
        loan_changes=loan_changes,
        constant_loan=constant_loan,
        extremes=tuple(extremes),
        earnings=_earnings(pts),
        cohorts=_cohorts(pts[-1], clock),
        criteria=CRITERIA,
    )
