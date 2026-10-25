"""Vehicle-return analysis: group statistics, ranks, trends, fit screens and swap hypotheses.

Pure over `VehicleRoiEvidence`; nothing here formats, renders or reads a store. `profitYear` is a
rolling game-year figure: per-vehicle values are only combined across distinct vehicles within one
sample, never across samples. Vehicles younger than the maturity policy have a partial window and are
kept out of ranks. Catalog units are unverified unless the catalog carries `meta.verifiedUnits`, so
swap candidates expose raw values and unit-free ratios only; no causal or payback claim is made.
Line `capacity[].cargo` is indexed one higher than `vehicles[].loadConfig[].cargo`, so a vehicle's cargo
is identified from `loadConfig` only.
"""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

from .. import analysis
from ..game_time import GameCalendarClock
from ..snapshot import Snapshot
from .models import EvaluationContext, SampleRef, Unavailable, ViewCoverage
from .vehicle_roi_evidence import LOAD_HISTORY, TREND_COLUMNS, VehicleRoiEvidence

# Engine-owned statistical safeguards and algorithm bounds (not methodology policy).
MIN_SAMPLE = 3
MIN_LOAD_SAMPLES = 3
TREND_GROUPS = 8
SWAP_GROUPS = 6
SWAP_CANDIDATES = 3
WEAK_LOSS_SHARE = 0.4
HYDRATION_LIMIT = TREND_COLUMNS + LOAD_HISTORY + 1  # trend samples, load snapshots and the catalog

# (lower, upper) in game years; the last bucket is open-ended. Labels are presentation.
AGE_BUCKETS: tuple[tuple[float, float | None], ...] = (
    (0.0, 1.0),
    (1.0, 3.0),
    (3.0, 6.0),
    (6.0, 10.0),
    (10.0, 20.0),
    (20.0, None),
)

ISSUE_TYPES = ("VehicleUseless", "NoVehicleToLoadCargo", "LineCargoConfig")


@dataclass(frozen=True)
class Criterion:
    """A fixed engine-owned heuristic, disclosed rather than configurable."""

    name: str
    value: float | str
    unit: str
    note: str


@dataclass(frozen=True)
class VehicleObservation:
    id: int
    name: str
    carrier: str
    model: str  # consist signature
    parts: int
    model_ids: tuple[Any, ...]
    cargo_ids: tuple[int, ...]  # configured load, capacity > 0, sorted
    cargo: str  # cargo group identity (display name of the configured load)
    age: float | None  # elapsed game-years on the bounded calendar; None when unknown
    age_reason: str | None
    maturity: str  # "mature" | "young" | "unknown" (unknown age or profit)
    profit: float | None
    value: float | None
    running_cost: float | None
    list_price: float | None
    condition: float | None
    capacity: float | None
    line_id: int | None
    line: str | None
    can_carry: tuple[Any, ...] | None


@dataclass(frozen=True)
class GroupStats:
    n: int
    mature: int
    young: int
    mean: float | None
    median: float | None
    total: float | None
    loss_share: float | None
    return_on_value: float | None
    return_on_price: float | None
    return_on_running_cost: float | None
    young_mean: float | None
    mean_condition: float | None
    sample: str  # "no-mature" | "small-sample" | "ok"


@dataclass(frozen=True)
class GroupRow:
    key: str
    stats: GroupStats


@dataclass(frozen=True)
class ModelGroup:
    key: str  # "Model [Carrier]"
    carrier: str
    model: str
    stats: GroupStats
    rank: int | None  # 1-based among groups with MIN_SAMPLE mature vehicles, by mean profit
    median_list_price: float | None
    median_running_cost: float | None


@dataclass(frozen=True)
class AgeGroup:
    carrier: str
    lower_years: float
    upper_years: float | None
    stats: GroupStats
    reported_mean: float | None  # mean of mature vehicles, else the partial-window mean
    partial_window: bool  # bucket lies entirely below the maturity policy


@dataclass(frozen=True)
class LineComparison:
    line_id: int
    line: str
    better: str
    better_n: int
    better_mean: float
    better_avg_age: float
    weaker: str
    weaker_n: int
    weaker_mean: float
    weaker_avg_age: float
    gap: float
    small_sample: bool


@dataclass(frozen=True)
class TrendSample:
    sample: SampleRef
    overall: GroupStats
    groups: tuple[GroupRow, ...]


@dataclass(frozen=True)
class TrendMover:
    key: str
    first_mean: float
    first_n: int
    last_mean: float
    last_n: int
    change: float


@dataclass(frozen=True)
class MismatchReason:
    code: str  # "cargo-not-in-can-carry" | "catalog-lists-no-capacity"
    model: str | None = None
    cargo: str | None = None


@dataclass(frozen=True)
class VehicleMismatch:
    vehicle_id: int
    vehicle: str
    line: str | None
    model: str
    cargo: str
    reasons: tuple[MismatchReason, ...]


@dataclass(frozen=True)
class GameIssue:
    line_id: int
    line: str
    type: str
    stop_index: Any
    cargo_index: Any


@dataclass(frozen=True)
class LineFit:
    line_id: int
    line: str
    vehicles: int
    models: tuple[str, ...]
    capacity_median: float | None
    load_median: float
    load_min: float
    load_max: float
    load_samples: int
    line_profit: float | None


@dataclass(frozen=True)
class CatalogRef:
    sample: SampleRef
    models: int
    top_speed_verified: bool  # meta.verifiedUnits.topSpeed == "m/s"
    running_cost_verified: bool  # meta.verifiedUnits.runningCosts == "currency/year"


@dataclass(frozen=True)
class SwapCandidate:
    name: str
    capacity: float
    capacity_ratio: float | None  # candidate / current, same raw units; None when either side unknown
    top_speed_ratio: float | None
    price_ratio: float | None
    running_cost_ratio: float | None
    lifespan: float | None
    in_fleet: bool
    own_mature: int
    own_mean: float | None
    own_young: int


@dataclass(frozen=True)
class WeakGroup:
    key: str
    carrier: str
    stats: GroupStats
    status: str  # "assessed" | "no-catalog" | "multi-part-consist" | "no-load-configuration" | "multiple-cargos"
    cargo_id: int | None
    cargo: str | None
    lines_median_load: float | None
    current_capacity: float | None
    current_lifespan: float | None
    in_stored_catalog: bool | None
    current_price: float | None
    current_running_cost: float | None
    current_top_speed: float | None
    candidates: tuple[SwapCandidate, ...]


@dataclass(frozen=True)
class VehicleRoiView:
    coverage: ViewCoverage
    first_sample: SampleRef
    last_sample: SampleRef
    catalog: CatalogRef | None
    game_year: int | None
    mature_years: float
    time_basis_anchor_hash: str | None
    observations: tuple[VehicleObservation, ...]
    overall: GroupStats
    carriers: tuple[GroupRow, ...]  # ordered by mature mean, then partial-window mean
    models: tuple[ModelGroup, ...]  # same order
    model_groups_below_minimum: int
    cargos: tuple[GroupRow, ...]
    ages: tuple[AgeGroup, ...]
    same_line: tuple[LineComparison, ...]  # largest gap first
    trend_samples: tuple[TrendSample, ...]
    trend_groups: tuple[str, ...]  # endpoint groups with most mature vehicles
    trend_movers: tuple[TrendMover, ...]  # ascending change; groups with MIN_SAMPLE mature at both ends
    mismatch_checked: int
    mismatches: tuple[VehicleMismatch, ...]
    game_issues: tuple[GameIssue, ...]
    load_samples: tuple[SampleRef, ...]
    high_load: tuple[LineFit, ...]  # highest median load first
    low_load: tuple[LineFit, ...]  # lowest median load first
    swap_status: str  # "no-weak-groups" | "no-catalog" | "assessed"
    weak_groups: tuple[WeakGroup, ...]
    criteria: tuple[Criterion, ...]


# ---------------------------------------------------------------------------
# Vehicle observations
# ---------------------------------------------------------------------------


def _num(value: Any) -> float | None:
    return value if isinstance(value, (int, float)) else None


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
    return tuple(
        sorted(
            {
                c["cargo"]
                for c in vehicle.get("loadConfig") or []
                if isinstance(c.get("cargo"), int) and (c.get("capacity") or 0) > 0
            }
        )
    )


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


def _observations(snap: Snapshot, clock: GameCalendarClock, mature_years: float) -> tuple[VehicleObservation, ...]:
    out = []
    for v in snap.vehicles:
        measure = clock.elapsed_between_ticks(v.get("purchaseTime"), snap.game_time)
        age = measure.value
        profit = _num(v.get("profitYear"))
        line = snap.lines_by_id.get(v.get("line"))
        ids = _cargo_ids(v)
        can = v.get("canCarry")
        out.append(
            VehicleObservation(
                id=v["id"],
                name=v.get("name") or f"Vehicle #{v['id']}",
                carrier=v.get("carrier") or "UNKNOWN",
                model=_signature(snap, v),
                parts=len(v.get("models") or []),
                model_ids=tuple(v.get("models") or ()),
                cargo_ids=ids,
                cargo=_cargo_label(snap, ids),
                age=age,
                age_reason=None if age is not None else measure.reason,
                maturity="unknown" if profit is None or age is None else ("mature" if age >= mature_years else "young"),
                profit=profit,
                value=_num(v.get("value")),
                running_cost=_num(v.get("runningCost")),
                list_price=_list_price(snap, v),
                condition=_num(v.get("maintenanceState")),
                capacity=_num(v.get("capacity")),
                line_id=v.get("line") if line else None,
                line=(line.get("name") or f"Line #{line['id']}") if line else None,
                can_carry=tuple(can) if isinstance(can, list) else None,
            )
        )
    return tuple(out)


# ---------------------------------------------------------------------------
# Group statistics
# ---------------------------------------------------------------------------


def _ratio(num: float, den: float) -> float | None:
    return num / den if den else None


def _stats(recs: list[VehicleObservation]) -> GroupStats:
    mature = [r for r in recs if r.maturity == "mature"]
    young = [r for r in recs if r.maturity == "young"]
    profits = [r.profit for r in mature]
    with_value = [r for r in mature if r.value]
    with_price = [r for r in mature if r.list_price]
    with_run = [r for r in mature if r.running_cost]
    conditions = [r.condition for r in recs if r.condition is not None]
    return GroupStats(
        n=len(recs),
        mature=len(mature),
        young=len(young),
        mean=statistics.fmean(profits) if profits else None,
        median=statistics.median(profits) if profits else None,
        total=sum(profits) if profits else None,
        loss_share=sum(1 for p in profits if p < 0) / len(profits) if profits else None,
        return_on_value=_ratio(sum(r.profit for r in with_value), sum(r.value for r in with_value))
        if with_value
        else None,
        return_on_price=_ratio(sum(r.profit for r in with_price), sum(r.list_price for r in with_price))
        if with_price
        else None,
        return_on_running_cost=_ratio(sum(r.profit for r in with_run), sum(r.running_cost for r in with_run))
        if with_run
        else None,
        young_mean=statistics.fmean([r.profit for r in young]) if young else None,
        mean_condition=statistics.fmean(conditions) if conditions else None,
        sample="no-mature" if not mature else ("small-sample" if len(mature) < MIN_SAMPLE else "ok"),
    )


def _group_by(recs, key) -> dict[Any, list[VehicleObservation]]:
    groups: dict[Any, list[VehicleObservation]] = defaultdict(list)
    for r in recs:
        groups[key(r)].append(r)
    return groups


def _rank_key(item: tuple[str, GroupStats]) -> tuple:
    label, st = item
    if st.mean is not None:
        return (0, -st.mean, str(label))
    if st.young_mean is not None:
        return (1, -st.young_mean, str(label))
    return (2, 0, str(label))


def _model_label(carrier: str, model: str) -> str:
    return f"{model} [{carrier}]"


def _by_model(recs) -> dict[str, list[VehicleObservation]]:
    return _group_by(recs, lambda r: _model_label(r.carrier, r.model))


def _median_positive(values) -> float | None:
    values = [v for v in values if v]
    return statistics.median(values) if values else None


# ---------------------------------------------------------------------------
# Catalog helpers
# ---------------------------------------------------------------------------


def _in_production(model: dict[str, Any], year: int | None) -> bool:
    if model.get("available") is False and year is None:
        return False
    start, end = model.get("yearFrom"), model.get("yearTo")
    if year is None:
        return model.get("available") is not False
    return (start is None or start <= 0 or start <= year) and (end is None or end <= 0 or year < end)


def _catalog_capacity(model: dict[str, Any], cargo_id: int) -> float:
    return sum(c.get("capacity") or 0 for c in model.get("capacity") or [] if c.get("cargo") == cargo_id)


def _ratio_of(candidate: Any, current: Any) -> float | None:
    if (
        not isinstance(candidate, (int, float))
        or not isinstance(current, (int, float))
        or current <= 0
        or candidate <= 0
    ):
        return None
    return candidate / current


# ---------------------------------------------------------------------------
# Screens
# ---------------------------------------------------------------------------


def _same_line(recs: tuple[VehicleObservation, ...]) -> tuple[LineComparison, ...]:
    by_line: dict[Any, list[VehicleObservation]] = defaultdict(list)
    for r in recs:
        if r.line_id is not None and r.maturity == "mature":
            by_line[r.line_id].append(r)
    rows = []
    for line_id, line_recs in by_line.items():
        groups = _by_model(line_recs)
        if len(groups) < 2:
            continue
        summarized = sorted(
            ((k, v, statistics.fmean(r.profit for r in v)) for k, v in groups.items()), key=lambda t: (-t[2], t[0])
        )
        (bk, bv, bm), (wk, wv, wm) = summarized[0], summarized[-1]
        rows.append(
            LineComparison(
                line_id,
                line_recs[0].line,
                bk,
                len(bv),
                bm,
                statistics.fmean(r.age for r in bv),
                wk,
                len(wv),
                wm,
                statistics.fmean(r.age for r in wv),
                bm - wm,
                min(len(bv), len(wv)) < MIN_SAMPLE,
            )
        )
    rows.sort(key=lambda c: (-c.gap, str(c.line)))
    return tuple(rows)


def _trend(evidence: VehicleRoiEvidence, mature_years: float, latest_groups: dict[str, GroupStats]):
    samples = []
    for t in evidence.trend:
        recs = _observations(t.snapshot, t.clock, mature_years)
        samples.append(
            TrendSample(
                SampleRef(t.snapshot.game_time, t.snapshot.date_label),
                _stats(list(recs)),
                tuple(GroupRow(k, _stats(v)) for k, v in _by_model(recs).items()),
            )
        )
    picks = tuple(
        k
        for k, _ in sorted(
            ((k, s) for k, s in latest_groups.items() if s.mature > 0), key=lambda kv: (-kv[1].mature, kv[0])
        )[:TREND_GROUPS]
    )
    movers: list[TrendMover] = []
    if len(samples) >= 2:
        first = {g.key: g.stats for g in samples[0].groups}
        last = {g.key: g.stats for g in samples[-1].groups}
        for k in sorted(last):
            a, b = first.get(k), last[k]
            if a and a.mature >= MIN_SAMPLE and b.mature >= MIN_SAMPLE:
                movers.append(TrendMover(k, a.mean, a.mature, b.mean, b.mature, b.mean - a.mean))
        movers.sort(key=lambda m: (m.change, m.key))
    return tuple(samples), picks, tuple(movers)


def _mismatches(latest: Snapshot, recs: tuple[VehicleObservation, ...], catalog: Snapshot | None):
    cat_by_res = {m.get("res"): m for m in (catalog.catalog if catalog else []) if m.get("res")}
    flagged, checked = [], 0
    for r in recs:
        if not r.cargo_ids:
            continue
        checked += 1
        reasons: list[MismatchReason] = []
        if r.can_carry and any(c not in r.can_carry for c in r.cargo_ids):
            reasons.append(MismatchReason("cargo-not-in-can-carry"))
        for mid in r.model_ids:
            cat = cat_by_res.get((latest.models.get(mid) or {}).get("res"))
            if cat and (cat.get("capacity") or []) and all(_catalog_capacity(cat, c) <= 0 for c in r.cargo_ids):
                reasons.append(
                    MismatchReason(
                        "catalog-lists-no-capacity", _model_name(latest, mid), _cargo_label(latest, r.cargo_ids)
                    )
                )
        unique = tuple(dict.fromkeys(reasons))
        if unique:
            flagged.append(VehicleMismatch(r.id, r.name, r.line, r.model, r.cargo, unique))
    return checked, tuple(flagged)


def _line_loads(snaps: tuple[Snapshot, ...]) -> dict[int, list[float]]:
    loads: dict[int, list[float]] = defaultdict(list)
    for s in snaps[-LOAD_HISTORY:]:
        for line in s.lines:
            load = analysis.line_load(line)
            if load is not None:
                loads[line["id"]].append(load)
    return loads


def _load_fits(latest: Snapshot, recs, loads, thresholds):
    by_line: dict[int, list[VehicleObservation]] = defaultdict(list)
    for r in recs:
        if r.line_id is not None:
            by_line[r.line_id].append(r)
    high, low = [], []
    for line in latest.lines:
        series = loads.get(line["id"], [])
        vehicles = by_line.get(line["id"], [])
        if len(series) < MIN_LOAD_SAMPLES or not vehicles:
            continue
        med = statistics.median(series)
        caps = [r.capacity for r in vehicles if r.capacity]
        fit = LineFit(
            line["id"],
            line.get("name") or f"Line #{line['id']}",
            len(vehicles),
            tuple(sorted({_model_label(r.carrier, r.model) for r in vehicles})),
            statistics.median(caps) if caps else None,
            med,
            min(series),
            max(series),
            len(series),
            _num(line.get("profitYear")),
        )
        if med >= thresholds.overloaded_load and len(vehicles) >= thresholds.underused_min_vehicles:
            high.append(fit)
        elif med <= thresholds.underused_load and len(vehicles) >= thresholds.underused_min_vehicles:
            low.append(fit)
    high.sort(key=lambda f: (-f.load_median, str(f.line)))
    low.sort(key=lambda f: (f.load_median, str(f.line)))
    return tuple(high), tuple(low)


def _swaps(
    latest: Snapshot,
    model_recs: dict[str, list[VehicleObservation]],
    groups: dict[str, GroupStats],
    catalog: Snapshot | None,
    loads: dict[int, list[float]],
):
    weak = [
        (k, s)
        for k, s in groups.items()
        if s.mature >= MIN_SAMPLE and (s.median < 0 or (s.loss_share or 0) >= WEAK_LOSS_SHARE)
    ]
    weak.sort(key=lambda kv: (kv[1].mean, kv[0]))
    weak = weak[:SWAP_GROUPS]
    if not weak:
        return "no-weak-groups", ()
    if catalog is None or not catalog.catalog:
        return "no-catalog", tuple(
            WeakGroup(
                k, model_recs[k][0].carrier, s, "no-catalog", None, None, None, None, None, None, None, None, None, ()
            )
            for k, s in weak
        )
    year = (latest.date or {}).get("year", latest.meta.get("year"))
    cat_by_res = {m.get("res"): m for m in catalog.catalog if m.get("res")}
    out = []
    for label, st in weak:
        recs = model_recs[label]
        mature = [r for r in recs if r.maturity == "mature"]
        carrier = recs[0].carrier

        def unassessed(status: str, label=label, carrier=carrier, st=st) -> WeakGroup:
            return WeakGroup(label, carrier, st, status, None, None, None, None, None, None, None, None, None, ())

        line_loads = [
            statistics.median(loads[r.line_id])
            for r in mature
            if r.line_id in loads and len(loads[r.line_id]) >= MIN_LOAD_SAMPLES
        ]
        lines_median = statistics.median(line_loads) if line_loads else None
        if any(r.parts > 1 for r in recs):
            out.append(unassessed("multi-part-consist"))
            continue
        cargo_sets = Counter(r.cargo_ids for r in mature if r.cargo_ids)
        if not cargo_sets:
            out.append(unassessed("no-load-configuration"))
            continue
        cargo_ids = cargo_sets.most_common(1)[0][0]
        if len(cargo_ids) != 1:
            out.append(unassessed("multiple-cargos"))
            continue
        cargo_id = cargo_ids[0]
        current_model_id = recs[0].model_ids[0] if recs[0].model_ids else None
        current_model = latest.models.get(current_model_id) or {}
        current_cat = cat_by_res.get(current_model.get("res"))
        caps = [r.capacity for r in mature if r.capacity]
        current_cap = statistics.median(caps) if caps else None
        cur_price, cur_run = current_model.get("price"), current_model.get("runningCosts")
        cur_speed = current_cat.get("topSpeed") if current_cat else None
        cur_life = current_model.get("lifespan")
        ranked = []
        for m in catalog.catalog:
            if m.get("carrier") != carrier or m.get("res") == current_model.get("res") or not _in_production(m, year):
                continue
            cap = _catalog_capacity(m, cargo_id)
            run = m.get("runningCosts")
            if cap <= 0 or not isinstance(run, (int, float)) or run <= 0:
                continue
            ranked.append((cap / run, m, cap))
        ranked.sort(key=lambda t: (-t[0], str(t[1].get("name") or "")))
        candidates = []
        for _, m, cap in ranked[:SWAP_CANDIDATES]:
            cname = m.get("name") or m.get("res") or f"Model #{m.get('id')}"
            own = groups.get(_model_label(carrier, cname))
            candidates.append(
                SwapCandidate(
                    cname,
                    cap,
                    _ratio_of(cap, current_cap),
                    _ratio_of(m.get("topSpeed"), cur_speed),
                    _ratio_of(m.get("price"), cur_price),
                    _ratio_of(m.get("runningCosts"), cur_run),
                    _num(m.get("lifespan")),
                    own is not None,
                    own.mature if own else 0,
                    own.mean if own else None,
                    own.young if own else 0,
                )
            )
        out.append(
            WeakGroup(
                label,
                carrier,
                st,
                "assessed",
                cargo_id,
                latest.cargo(cargo_id),
                lines_median,
                current_cap,
                _num(cur_life),
                current_cat is not None,
                _num(cur_price),
                _num(cur_run),
                _num(cur_speed),
                tuple(candidates),
            )
        )
    return "assessed", tuple(out)


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def evaluate(evidence: VehicleRoiEvidence, *, context: EvaluationContext) -> VehicleRoiView:
    thresholds = context.thresholds
    mature_years = thresholds.mature_years
    latest = evidence.endpoint
    catalog = evidence.catalog
    recs = _observations(latest, evidence.clock, mature_years)
    model_recs = _by_model(recs)
    groups = {k: _stats(v) for k, v in model_recs.items()}

    carriers = sorted(((k, _stats(v)) for k, v in _group_by(recs, lambda r: r.carrier).items()), key=_rank_key)
    cargos = sorted(((k, _stats(v)) for k, v in _group_by(recs, lambda r: r.cargo).items()), key=_rank_key)
    reliable = sorted(
        ((k, s) for k, s in groups.items() if s.mature >= MIN_SAMPLE), key=lambda kv: (-kv[1].mean, kv[0])
    )
    rank_of = {k: i + 1 for i, (k, _) in enumerate(reliable)}
    models = tuple(
        ModelGroup(
            k,
            model_recs[k][0].carrier,
            model_recs[k][0].model,
            s,
            rank_of.get(k),
            _median_positive(r.list_price for r in model_recs[k]),
            _median_positive(r.running_cost for r in model_recs[k]),
        )
        for k, s in sorted(groups.items(), key=_rank_key)
    )

    ages = []
    aged = [r for r in recs if r.age is not None]
    for carrier in sorted({r.carrier for r in aged}):
        for lo, hi in AGE_BUCKETS:
            part = [r for r in aged if r.carrier == carrier and lo <= r.age < (hi if hi is not None else float("inf"))]
            if not part:
                continue
            s = _stats(part)
            ages.append(
                AgeGroup(
                    carrier, lo, hi, s, s.mean if s.mature else s.young_mean, hi is not None and hi <= mature_years
                )
            )

    trend_samples, trend_groups, movers = _trend(evidence, mature_years, groups)
    checked, mismatches = _mismatches(latest, recs, catalog)
    issues = tuple(
        GameIssue(
            line["id"],
            line.get("name") or f"Line #{line['id']}",
            issue.get("type"),
            issue.get("stopIndex"),
            issue.get("cargo"),
        )
        for line in latest.lines
        for issue in line.get("issues") or []
        if issue.get("type") in ISSUE_TYPES
    )
    loads = _line_loads(evidence.load_snapshots)
    high, low = _load_fits(latest, recs, loads, thresholds)
    swap_status, weak = _swaps(latest, model_recs, groups, catalog, loads)

    unavailable = tuple(
        Unavailable("unknown-vehicle-age", f"{n} vehicles", reason)
        for reason, n in sorted(Counter(r.age_reason for r in recs if r.age is None).items(), key=lambda kv: str(kv[0]))
    )
    used_ticks = (
        {t.snapshot.game_time for t in evidence.trend}
        | {s.game_time for s in evidence.load_snapshots}
        | {latest.game_time}
    )
    coverage = ViewCoverage(
        endpoint=SampleRef(latest.game_time, latest.date_label),
        eligible=evidence.eligible,
        read=evidence.read,
        used=len(used_ticks),
        hydrated=evidence.hydrated,
        hydration_limit=HYDRATION_LIMIT,
        sampled=tuple(SampleRef(t.snapshot.game_time, t.snapshot.date_label) for t in evidence.trend),
        limits={
            "trendSamples": TREND_COLUMNS,
            "loadSnapshots": LOAD_HISTORY,
            "swapGroups": SWAP_GROUPS,
            "swapCandidates": SWAP_CANDIDATES,
            "trendGroups": TREND_GROUPS,
        },
        omitted=max(0, evidence.eligible - len(used_ticks)),
        unavailable=unavailable,
    )
    units = (catalog.meta.get("verifiedUnits") or {}) if catalog else {}
    anchor_hash = (evidence.clock.time_basis or {}).get("anchorHash")
    criteria = (
        Criterion(
            "minimum-mature-sample", MIN_SAMPLE, "vehicles", "Groups below this are flagged, not ranked or compared."
        ),
        Criterion(
            "minimum-load-samples", MIN_LOAD_SAMPLES, "samples", "Sampled line load needs at least this many snapshots."
        ),
        Criterion(
            "weak-group-loss-share",
            WEAK_LOSS_SHARE,
            "ratio",
            "A group is weak when its mature median profit is below 0 or its loss share reaches this value.",
        ),
        Criterion(
            "candidate-order",
            "capacity-per-running-cost",
            "raw-catalog-units",
            "Swap candidates are ordered by catalog capacity per raw running cost; a hypothesis ordering, not a forecast.",
        ),
    )
    return VehicleRoiView(
        coverage=coverage,
        first_sample=evidence.first_sample,
        last_sample=evidence.last_sample,
        catalog=CatalogRef(
            SampleRef(catalog.game_time, catalog.date_label),
            len(catalog.catalog),
            units.get("topSpeed") == "m/s",
            units.get("runningCosts") == "currency/year",
        )
        if catalog
        else None,
        game_year=(latest.date or {}).get("year", latest.meta.get("year")),
        mature_years=mature_years,
        time_basis_anchor_hash=anchor_hash,
        observations=recs,
        overall=_stats(list(recs)),
        carriers=tuple(GroupRow(k, s) for k, s in carriers),
        models=models,
        model_groups_below_minimum=sum(1 for s in groups.values() if s.mature < MIN_SAMPLE),
        cargos=tuple(GroupRow(k, s) for k, s in cargos),
        ages=tuple(ages),
        same_line=_same_line(recs),
        trend_samples=trend_samples,
        trend_groups=trend_groups,
        trend_movers=movers,
        mismatch_checked=checked,
        mismatches=mismatches,
        game_issues=issues,
        load_samples=tuple(SampleRef(s.game_time, s.date_label) for s in evidence.load_snapshots[-LOAD_HISTORY:]),
        high_load=high,
        low_load=low,
        swap_status=swap_status,
        weak_groups=weak,
        criteria=criteria,
    )
