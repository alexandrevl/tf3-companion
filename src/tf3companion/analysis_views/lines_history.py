"""Lines-history view: per-line profit trajectories, robust trend classes, fleet-change comparisons.

Every number is a point observation from one stored sample. Rolling ``profitYear`` values are compared
(medians of early vs recent samples) but never summed or treated as calendar income. The statistical
safeguards below are engine-owned constants; the methodology policy only changes the decision terms
(relative change, noise multiplier, median-current floor), never the medians or the MAD.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import TYPE_CHECKING

from ..game_time import TimeMeasure
from .models import EvaluationContext, SampleRef, Unavailable, ViewCoverage

if TYPE_CHECKING:
    from .lines_history_evidence import LinesHistoryEvidence

MIN_POINTS = 5            # profit samples needed inside the evaluation window
MAX_K = 6                 # samples per early/recent group (K = min(MAX_K, max(2, n // 3)))
LONG_HISTORY_YEARS = 1.5  # with at least this much history, evaluate only the last year
EVENT_MIN_POINTS = 5      # profit samples needed before a line's own MAD is used for fleet-change verdicts
EVENT_SIDE_SAMPLES = 3    # newest samples used on each side of a vehicle-count change
OCCUPANCY_SAMPLES = 12    # full snapshots sampled for instantaneous occupancy
FULL_OCCUPANCY = 0.8      # mean occupancy at which a rising line counts as full

CLASSES = ("deteriorating", "improving", "stable", "too new", "insufficient data")

# Follow-up selection limits (analytical scope, not display caps).
FOLLOWUP_PER_DECLINE_GROUP = 5
FOLLOWUP_RISING_FULL = 4
FOLLOWUP_PERSISTENT_LOSS = 5


@dataclass(frozen=True)
class Criterion:
    name: str
    value: float
    unit: str
    note: str


@dataclass(frozen=True)
class LinePoint:
    tick: int
    date: str
    profit: int | None
    transported: int | None
    rate: int | None
    vehicles: int | None


@dataclass(frozen=True)
class OccupancyPoint:
    tick: int
    date: str
    load: float


@dataclass(frozen=True)
class LineTrajectory:
    line_id: int
    name: str
    points: tuple[LinePoint, ...]
    current: bool                       # present in the endpoint snapshot and sampled at the endpoint
    carrier: str | None
    issues: tuple[str, ...]
    trend_class: str
    reason: str                         # stable code: classified | removed | no-vehicles | maturity-unavailable | too-new | insufficient-samples
    maturity: TimeMeasure | None        # age of the oldest currently assigned vehicle (a proxy, not line age)
    window_samples: int                 # non-missing profit samples inside the evaluation window
    window_points: tuple[LinePoint, ...]  # those samples (empty for removed lines)
    k: int
    early: float | None
    recent: float | None
    delta: float | None
    mad: float | None
    relative_term: float | None
    noise_term: float | None
    floor_term: float | None
    threshold: float | None
    transported_early: float | None
    transported_recent: float | None
    rate_early: float | None
    rate_recent: float | None
    vehicles_first: int | None          # first/last known vehicle count over all samples
    vehicles_last: int | None
    window_vehicles_first: int | None   # same, restricted to samples since the window start
    window_vehicles_last: int | None
    highest: LinePoint | None           # highest known profit sample (earliest on ties)
    lowest: LinePoint | None            # lowest known profit sample (earliest on ties)
    occupancy: tuple[OccupancyPoint, ...]
    occupancy_mean: float | None
    occupancy_latest: float | None


@dataclass(frozen=True)
class VehicleChangeEvent:
    line_id: int
    name: str
    tick: int
    date: str                           # first sample showing the new count, not the purchase date
    vehicles_before: int
    vehicles_after: int
    profit_before: float | None
    profit_after: float | None
    delta: float | None
    threshold: float | None
    samples_after: int
    verdict: str                        # profit-fell | profit-rose | within-noise | line-start | too-soon-after | too-soon-before
    profit_per_vehicle_before: float | None
    profit_per_vehicle_after: float | None


@dataclass(frozen=True)
class LineChange:
    """A line first seen after (created) or last seen before (removed) the sampled period's ends."""

    line_id: int
    name: str
    window_start: SampleRef
    window_end: SampleRef
    vehicles_first: int | None
    vehicles_last: int | None
    profit_first: int | None
    profit_last: int | None
    trend_class: str | None             # None for removed lines


@dataclass(frozen=True)
class ManualFollowUp:
    line_id: int
    name: str
    code: str                           # declining-with-added-vehicles | declining-without-added-vehicles | rising-and-full | persistent-loss
    action: str                         # review-added-vehicle | inspect-supply-and-issues | test-more-capacity | rework-or-close
    trend_class: str
    early: float | None
    recent: float | None
    vehicles_first: int | None
    vehicles_last: int | None
    window_vehicles_first: int | None
    window_vehicles_last: int | None
    latest_profit: int | None
    occupancy_mean: float | None
    occupancy_latest: float | None
    occupancy_samples: int
    issues: tuple[str, ...]


@dataclass(frozen=True)
class ClassSummary:
    trend_class: str
    lines: int
    median_latest_profit: float | None


@dataclass(frozen=True)
class ClassOrder:
    trend_class: str
    line_ids: tuple[int, ...]           # current lines of the class: deteriorating by change, improving by -change, else by id


@dataclass(frozen=True)
class LinesHistoryView:
    samples: tuple[SampleRef, ...]      # one retained sample per distinct date, oldest first
    span: TimeMeasure                   # elapsed game time between first and last retained sample
    short_span: bool                    # span known and below the maturity threshold
    too_few_samples: bool               # fewer distinct dates than MIN_POINTS
    window_kind: str                    # last-year | entire-history
    window_start: SampleRef | None
    median_current_profit: float | None # median |latest profit| across current lines
    floor: float                        # median-current floor term of the threshold
    criteria: tuple[Criterion, ...]
    trajectories: tuple[LineTrajectory, ...]
    class_summary: tuple[ClassSummary, ...]
    class_order: tuple[ClassOrder, ...]
    profit_ranking: tuple[int, ...]     # current lines with a latest profit, best first
    compact_order: tuple[int, ...]      # current lines by class priority then size of change
    vehicle_changes: tuple[VehicleChangeEvent, ...]   # ranked: fell, rose, within noise, too soon, line start
    additions: int
    reductions: int
    changed_lines: int
    changes_comparable: bool            # at least two retained samples
    created: tuple[LineChange, ...]
    removed: tuple[LineChange, ...]
    follow_ups: tuple[ManualFollowUp, ...]
    coverage: ViewCoverage


def spread(values: list, limit: int) -> list:
    """Evenly pick at most ``limit`` values by index, always keeping first and last."""
    if len(values) <= limit:
        return list(values)
    idx = sorted({round(i * (len(values) - 1) / (limit - 1)) for i in range(limit)})
    return [values[i] for i in idx]


def _med(values) -> float | None:
    return float(median(values)) if values else None


def _detrended_mad(pts: list[LinePoint], k: int) -> float:
    """Median absolute residual around the straight line joining the early and recent medians.

    A steady trend therefore adds no noise, while saw-tooth (lumpy income) series do.
    """
    xs = [float(p.tick) for p in pts]
    ys = [float(p.profit) for p in pts]
    x0, x1 = sum(xs[:k]) / k, sum(xs[-k:]) / k
    y0, y1 = median(ys[:k]), median(ys[-k:])
    slope = (y1 - y0) / (x1 - x0) if x1 > x0 else 0.0
    resid = [y - (y0 + slope * (x - x0)) for x, y in zip(xs, ys)]
    m = median(resid)
    return float(median(abs(r - m) for r in resid))


def _vehicle_range(points: tuple[LinePoint, ...], since: int | None = None) -> tuple[int | None, int | None]:
    pts = [p for p in points if p.vehicles is not None and (since is None or p.tick >= since)]
    return (pts[0].vehicles, pts[-1].vehicles) if pts else (None, None)


def _net(rng: tuple[int | None, int | None]) -> int | None:
    return None if rng[0] is None else rng[1] - rng[0]


def _date_of(dates: list[tuple[int, str]], tick: int) -> str | None:
    for t, d in dates:
        if t >= tick:
            return d
    return dates[-1][1] if dates else None


def evaluate(evidence: "LinesHistoryEvidence", *, context: EvaluationContext) -> LinesHistoryView:
    policy = context.policies["lines-history"]
    mature = context.thresholds.mature_years
    clock = context.clock
    samples = evidence.samples
    last_gt = samples[-1].tick if samples else evidence.endpoint.tick
    first_gt = samples[0].tick if samples else last_gt
    current = {c.id: c for c in evidence.current}

    span = clock.elapsed_between_ticks(first_gt, last_gt)
    long_hist = span.value is not None and span.value >= LONG_HISTORY_YEARS
    candidates = [p.tick for s in evidence.series for p in s.points
                  if (elapsed := clock.elapsed_between_ticks(p.tick, last_gt).value) is not None and elapsed <= 1]
    window_tick = min(candidates) if long_hist and candidates else first_gt
    dates = sorted({(p.tick, p.date) for s in evidence.series for p in s.points})
    window_date = _date_of(dates, window_tick)

    counts: dict[str, int] = {}
    names: dict[int, str] = {}
    for s in evidence.series:
        names[s.line_id] = s.name or f"Line #{s.line_id}"
        counts[names[s.line_id]] = counts.get(names[s.line_id], 0) + 1
    for lid, name in list(names.items()):
        if counts[name] > 1:
            names[lid] = f"{name} (#{lid})"

    occupancy: dict[int, list[OccupancyPoint]] = {}
    for sample in evidence.occupancy:
        for lid, load in sample.loads:
            occupancy.setdefault(lid, []).append(OccupancyPoint(sample.tick, sample.date, load))

    in_current = {s.line_id: s.line_id in current and s.points[-1].tick == last_gt for s in evidence.series}
    present = [abs(s.points[-1].profit) for s in evidence.series if in_current[s.line_id] and s.points[-1].profit is not None]
    median_present = float(median(present)) if present else None
    floor = policy.floor_share * (median(present) if present else 0)

    trajectories: list[LineTrajectory] = []
    for s in evidence.series:
        lid, pts = s.line_id, s.points
        cur = current.get(lid)
        is_current = in_current[lid]
        maturity = None
        window: list[LinePoint] = []
        k = 0
        early = recent = delta = mad = rel = noise = threshold = None
        if not is_current:
            cls, reason = "insufficient data", "removed"
        else:
            if cur.oldest_purchase is not None:
                maturity = clock.elapsed_between_ticks(cur.oldest_purchase, evidence.endpoint.tick)
            window = [p for p in pts if p.tick >= window_tick and p.profit is not None]
            if not cur.has_vehicles:
                cls, reason = "insufficient data", "no-vehicles"
            elif maturity is None or maturity.value is None:
                cls, reason = "insufficient data", "maturity-unavailable"
            elif maturity.value < mature:
                cls, reason = "too new", "too-new"
            elif len(window) < MIN_POINTS:
                cls, reason = "insufficient data", "insufficient-samples"
            else:
                values = [p.profit for p in window]
                k = min(MAX_K, max(2, len(window) // 3))
                early, recent = _med(values[:k]), _med(values[-k:])
                mad = _detrended_mad(window, k)
                delta = recent - early
                rel = policy.relative_change_ratio * max(abs(early), abs(recent))
                noise = policy.noise_factor * mad
                threshold = max(rel, noise, floor)
                cls = "improving" if delta > threshold else "deteriorating" if delta < -threshold else "stable"
                reason = "classified"
        classified = k > 0
        first_k, last_k = window[:k], window[-k:] if k else []
        known = [p for p in pts if p.profit is not None]
        occ = tuple(occupancy.get(lid, ()))
        loads = [o.load for o in occ]
        win_since = window[0].tick if window else None
        vfirst, vlast = _vehicle_range(pts)
        wfirst, wlast = _vehicle_range(pts, win_since)
        trajectories.append(LineTrajectory(
            line_id=lid, name=names[lid], points=pts, current=is_current,
            carrier=cur.carrier if is_current else None, issues=cur.issues if is_current else (),
            trend_class=cls, reason=reason, maturity=maturity, window_samples=len(window), window_points=tuple(window), k=k,
            early=early, recent=recent, delta=delta, mad=mad, relative_term=rel, noise_term=noise,
            floor_term=floor if classified else None, threshold=threshold,
            transported_early=_med([p.transported for p in first_k if p.transported is not None]) if classified else None,
            transported_recent=_med([p.transported for p in last_k if p.transported is not None]) if classified else None,
            rate_early=_med([p.rate for p in first_k if p.rate is not None]) if classified else None,
            rate_recent=_med([p.rate for p in last_k if p.rate is not None]) if classified else None,
            vehicles_first=vfirst, vehicles_last=vlast, window_vehicles_first=wfirst, window_vehicles_last=wlast,
            highest=max(known, key=lambda p: (p.profit, -p.tick)) if known else None,
            lowest=min(known, key=lambda p: (p.profit, p.tick)) if known else None,
            occupancy=occ, occupancy_mean=sum(loads) / len(loads) if loads else None,
            occupancy_latest=loads[-1] if loads else None))

    cur_lines = [t for t in trajectories if t.current]
    summary = []
    for c in CLASSES:
        members = [t.points[-1].profit for t in cur_lines if t.trend_class == c and t.points[-1].profit is not None]
        summary.append(ClassSummary(c, sum(1 for t in cur_lines if t.trend_class == c), _med(members)))
    class_order = []
    for c in CLASSES:
        sel = [t for t in cur_lines if t.trend_class == c]
        sel.sort(key=lambda t: t.delta or 0, reverse=(c == "improving"))
        class_order.append(ClassOrder(c, tuple(t.line_id for t in sel)))
    ranked = sorted((t for t in cur_lines if t.points[-1].profit is not None), key=lambda t: (-t.points[-1].profit, t.name, t.line_id))
    pri = {c: i for i, c in enumerate(CLASSES)}

    def compact_key(t: LineTrajectory):
        if t.trend_class == "deteriorating" and t.delta is not None:
            second = t.delta
        elif t.trend_class == "improving":
            second = -(t.delta or 0)
        else:
            second = -(t.points[-1].profit or 0)
        return pri[t.trend_class], second, t.name, t.line_id
    compact = sorted(cur_lines, key=compact_key)

    events = _vehicle_events(trajectories, floor, policy)
    changed = len({e.line_id for e in events})
    additions = sum(1 for e in events if e.vehicles_after > e.vehicles_before)

    created: list[LineChange] = []
    removed: list[LineChange] = []
    comparable = len(samples) >= 2
    if comparable:
        ticks = [s.tick for s in samples]
        for t in sorted((t for t in trajectories if t.points[0].tick > first_gt), key=lambda t: (t.points[0].tick, t.name, t.line_id)):
            i = ticks.index(t.points[0].tick)
            created.append(LineChange(t.line_id, t.name, samples[i - 1], samples[i], t.points[0].vehicles, t.points[-1].vehicles,
                                      t.points[0].profit, t.points[-1].profit, t.trend_class if t.current else None))
        for t in sorted((t for t in trajectories if t.points[-1].tick < last_gt), key=lambda t: (t.points[-1].tick, t.name, t.line_id)):
            i = ticks.index(t.points[-1].tick)
            removed.append(LineChange(t.line_id, t.name, samples[i], samples[i + 1], t.points[0].vehicles, t.points[-1].vehicles,
                                      t.points[0].profit, t.points[-1].profit, None))

    follow = _follow_ups(cur_lines)

    unavailable = (Unavailable("calendar-span-unavailable", "elapsed game time between the first and last sample is unknown"),) if span.value is None else ()
    coverage = ViewCoverage(
        endpoint=evidence.endpoint, eligible=evidence.eligible, read=evidence.read, used=len(samples),
        hydrated=evidence.hydrated, hydration_limit=OCCUPANCY_SAMPLES,
        sampled=tuple(SampleRef(o.tick, o.date) for o in evidence.occupancy),
        limits={"occupancySnapshots": OCCUPANCY_SAMPLES, "retainedSamplesPerDate": 1},
        unavailable=unavailable)
    criteria = (
        Criterion("minProfitSamples", MIN_POINTS, "samples", "profit samples needed inside the evaluation window"),
        Criterion("maxGroupSize", MAX_K, "samples", "samples per early/recent group = min(max, max(2, n // 3))"),
        Criterion("longHistoryYears", LONG_HISTORY_YEARS, "game-years", "with at least this history only the last game-year is evaluated"),
        Criterion("eventSideSamples", EVENT_SIDE_SAMPLES, "samples", "newest samples used on each side of a vehicle-count change"),
        Criterion("occupancySnapshots", OCCUPANCY_SAMPLES, "snapshots", "full snapshots sampled for instantaneous occupancy"),
        Criterion("fullOccupancy", FULL_OCCUPANCY, "ratio", "mean occupancy at which a rising line is treated as full"),
    )
    return LinesHistoryView(
        samples=samples, span=span,
        short_span=span.value is not None and span.value < mature,
        too_few_samples=len(samples) < MIN_POINTS,
        window_kind="last-year" if long_hist else "entire-history",
        window_start=SampleRef(window_tick, window_date) if samples else None,
        median_current_profit=median_present, floor=float(floor), criteria=criteria,
        trajectories=tuple(trajectories), class_summary=tuple(summary), class_order=tuple(class_order),
        profit_ranking=tuple(t.line_id for t in ranked), compact_order=tuple(t.line_id for t in compact),
        vehicle_changes=events, additions=additions, reductions=len(events) - additions, changed_lines=changed,
        changes_comparable=comparable, created=tuple(created), removed=tuple(removed),
        follow_ups=follow, coverage=coverage)


_VERDICT_ORDER = {"profit-fell": 0, "profit-rose": 1, "within-noise": 2, "line-start": 4}


def _vehicle_events(lines: list[LineTrajectory], floor: float, policy) -> tuple[VehicleChangeEvent, ...]:
    events: list[VehicleChangeEvent] = []
    for ln in lines:
        pts = ln.points
        idx = [i for i in range(1, len(pts)) if pts[i].vehicles is not None and pts[i - 1].vehicles is not None
               and pts[i].vehicles != pts[i - 1].vehicles]
        ppts = [p for p in pts if p.profit is not None]
        mad = _detrended_mad(ppts, min(MAX_K, max(2, len(ppts) // 3))) if len(ppts) >= EVENT_MIN_POINTS else 0.0
        for n, i in enumerate(idx):
            end = idx[n + 1] if n + 1 < len(idx) else len(pts)
            before = [p.profit for p in pts[max(0, (idx[n - 1] if n else 0)):i] if p.profit is not None][-EVENT_SIDE_SAMPLES:]
            after = [p.profit for p in pts[i:end] if p.profit is not None][-EVENT_SIDE_SAMPLES:]
            seg = end - i
            b, a = _med(before), _med(after)
            v0, v1 = pts[i - 1].vehicles, pts[i].vehicles
            verdict, delta, thr = "too-soon-after", None, None
            if v0 == 0:
                verdict = "line-start"
            elif b is not None and a is not None and len(before) >= 2 and seg >= 2:
                delta = a - b
                thr = max(policy.relative_change_ratio * max(abs(a), abs(b)), policy.noise_factor * mad, floor)
                verdict = "profit-rose" if delta > thr else "profit-fell" if delta < -thr else "within-noise"
            elif b is None or len(before) < 2:
                verdict = "too-soon-before"
            events.append(VehicleChangeEvent(
                ln.line_id, ln.name, pts[i].tick, pts[i].date, v0, v1, b, a, delta, thr, seg, verdict,
                b / v0 if b is not None and v0 else None, a / v1 if a is not None and v1 else None))
    events.sort(key=lambda e: (_VERDICT_ORDER.get(e.verdict, 3), -abs(e.delta or 0), e.name, e.date, e.line_id, e.tick))
    return tuple(events)


def _follow_ups(cur: list[LineTrajectory]) -> tuple[ManualFollowUp, ...]:
    rows: list[ManualFollowUp] = []

    def make(t: LineTrajectory, code: str, action: str) -> ManualFollowUp:
        return ManualFollowUp(
            t.line_id, t.name, code, action, t.trend_class, t.early, t.recent, t.vehicles_first, t.vehicles_last,
            t.window_vehicles_first, t.window_vehicles_last, t.points[-1].profit, t.occupancy_mean, t.occupancy_latest,
            len(t.occupancy), t.issues)

    def window_net(t: LineTrajectory) -> int | None:
        return _net((t.window_vehicles_first, t.window_vehicles_last))

    det = sorted((t for t in cur if t.trend_class == "deteriorating"), key=lambda t: t.delta)
    for t in [x for x in det if (window_net(x) or 0) > 0][:FOLLOWUP_PER_DECLINE_GROUP]:
        rows.append(make(t, "declining-with-added-vehicles", "review-added-vehicle"))
    for t in [x for x in det if (window_net(x) or 0) <= 0][:FOLLOWUP_PER_DECLINE_GROUP]:
        rows.append(make(t, "declining-without-added-vehicles", "inspect-supply-and-issues"))
    rising = 0
    for t in sorted((t for t in cur if t.trend_class == "improving"), key=lambda t: -t.delta):
        if t.occupancy_mean is not None and t.occupancy_mean >= FULL_OCCUPANCY:
            rows.append(make(t, "rising-and-full", "test-more-capacity"))
            rising += 1
            if rising >= FOLLOWUP_RISING_FULL:
                break
    neg = [t for t in cur if t.trend_class in ("deteriorating", "stable", "improving") and t.window_points
           and all(p.profit < 0 for p in t.window_points)]
    neg.sort(key=lambda t: t.points[-1].profit if t.points[-1].profit is not None else t.window_points[-1].profit)
    for t in neg[:FOLLOWUP_PERSISTENT_LOSS]:
        rows.append(make(t, "persistent-loss", "rework-or-close"))
    return tuple(rows)
