"""Industries view: every analytical result of the industries evolution report, with no presentation.

Honesty rules kept from the report:
- producedYear/shippedYear/consumedYear are rolling annual figures per sample; they are compared
  sample to sample, never summed across samples.
- Service ratio = shipped / produced; ratios above one are kept (they can reflect stock draw-down).
- An industry with a missing or non-numeric input/output measurement has unknown flows: it is excluded
  from every flow total and ratio, never counted as zero.
- Station-to-industry links are inferred from an exact, unambiguous name match.
- A section whose stored evidence cannot be interpreted becomes an `Unavailable` record; it is never
  reported as a healthy empty result.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Any, Sequence

from ..game_time import calendar_ordinal
from ..snapshot import Snapshot
from .industries_evidence import IndustriesEvidence, SampleRows
from .models import EvaluationContext, SampleRef, Unavailable, ViewCoverage

MAX_EVOLUTION_ROWS = 14
BUCKET_DAYS = (7, 14, 30, 91, 182, 365, 730, 1826, 3652)
MOVER_MIN_DELTA = 15.0
MOVER_MIN_SHARE = 0.15
RATING_CHANGE_MIN = 0.05
RATING_HINT_MIN = 0.1
STOCK_MOVER_MIN = 0.2
INPUT_LIMITED_RATIO = 0.5
OUTLIER_MIN_PRODUCING = 3
SECTION_ERRORS = (KeyError, TypeError, ValueError, ZeroDivisionError, IndexError, AttributeError)

STATUS_IDLE = "idle"
STATUS_OUTPUT_FULL = "output-stock-full"
STATUS_INPUT_LIMITED = "input-limited"
STATUS_RUNNING = "running"


# ---------------------------------------------------------------------------
# Public typed records
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ViewCriterion:
    name: str
    value: float
    unit: str
    note: str
    source: str  # "policy" (methodology), "threshold" (shared engine threshold) or "engine" (fixed screen)


@dataclass(frozen=True)
class OutputFlow:
    cargo: int
    produced: float
    max_production: float
    shipped: float


@dataclass(frozen=True)
class InputFlow:
    cargo: int
    consumed: float
    max_consumption: float


@dataclass(frozen=True)
class IndustryFacts:
    """One industry at one sample; flows are empty (and `unknown_flows` set) when any measurement is missing."""

    id: int
    name: str
    type: str
    label: str
    level: int | None
    max_level: int | None
    rating: float | None
    closure_tick: int
    flagged: bool
    unknown_flows: bool
    outputs: tuple[OutputFlow, ...]
    inputs: tuple[InputFlow, ...]
    produced: float
    shipped: float
    capacity: float
    consumed: float
    consumption_capacity: float
    producing: bool
    served: bool
    idle: bool
    has_levels: bool


@dataclass(frozen=True)
class StockFacts:
    owner: Any
    stock_id: Any
    role: str  # output | input | warehouse
    fill: float
    count: float
    capacity: float
    cargos: tuple[int, ...]


@dataclass(frozen=True)
class GroupStats:
    n: int
    producing: int
    idle: int
    served: int
    produced: float
    shipped: float
    ratio: float | None
    level: int
    max_level: int
    flagged: int


@dataclass(frozen=True)
class Span:
    first: SampleRef
    last: SampleRef
    game_years: float | None
    calendar_days: float | None
    reason: str | None


@dataclass(frozen=True)
class ClosureRemaining:
    status: str  # none | due | estimate | unavailable
    target_tick: int
    game_days: float | None = None
    reason: str | None = None


@dataclass(frozen=True)
class LifecycleEvent:
    code: str  # closure-at-first-sample | new-industry | closure-scheduled | closure-cancelled |
    #            closed-as-scheduled | closed-flagged | disappeared
    sample: SampleRef
    day: float | None
    industry: IndustryFacts  # the later sample's row, except for closures/disappearances (last row seen)
    remaining: ClosureRemaining | None
    last_seen: str | None


@dataclass(frozen=True)
class EvolutionPoint:
    sample: SampleRef
    stats: GroupStats
    full_outputs: int | None


@dataclass(frozen=True)
class Comparison:
    first: SampleRef
    last: SampleRef
    common_count: int
    all_first: GroupStats
    all_last: GroupStats
    common_first: GroupStats
    common_last: GroupStats
    new_count: int
    vanished_count: int
    level_ups: int
    level_downs: int
    full_outputs_first: int | None
    full_outputs_last: int | None
    closures_scheduled: int
    closures_cancelled: int


@dataclass(frozen=True)
class LevelChange:
    industry: int
    name: str
    label: str
    level_first: int | None
    level_last: int | None
    max_level_first: int | None
    max_level_last: int | None
    produced_first: float
    produced_last: float
    shipped_first: float
    shipped_last: float
    served_first: bool


@dataclass(frozen=True)
class RatingChange:
    industry: int
    name: str
    label: str
    rating_first: float
    rating_last: float
    produced_first: float
    produced_last: float


@dataclass(frozen=True)
class UpgradeGroup:
    code: str  # shipping-at-first | not-shipping-at-first
    industries: int
    gained_level: int


@dataclass(frozen=True)
class ProductionMover:
    direction: str  # up | down
    industry: int
    name: str
    cargo: int
    cargo_name: str
    produced_first: float
    produced_last: float
    delta: float
    shipped_first: float
    shipped_last: float
    level_first: int | None
    level_last: int | None
    level_changed: bool
    rating_first: float | None
    rating_last: float | None
    rating_changed: bool


@dataclass(frozen=True)
class LevelsAnalysis:
    level_changes: tuple[LevelChange, ...]
    rating_changes: tuple[RatingChange, ...]
    upgrade_groups: tuple[UpgradeGroup, ...]  # empty when no common industry has levels
    movers: tuple[ProductionMover, ...]       # ups (largest first) then downs (largest first)


@dataclass(frozen=True)
class CargoService:
    cargo: int
    cargo_name: str
    produced_first: float
    produced_last: float
    shipped_first: float
    shipped_last: float
    ratio_first: float | None
    ratio_last: float | None
    producers_last: int
    served_last: int


@dataclass(frozen=True)
class TypeService:
    label: str
    industries: int
    producing_last: int
    served_last: int
    produced_first: float
    produced_last: float
    ratio_first: float | None
    ratio_last: float | None
    mean_rating: float | None
    no_output: bool  # no production at either end


@dataclass(frozen=True)
class Outlier:
    industry: int
    name: str
    label: str
    produced: float
    peers_served: int
    peers_producing: int
    type_median_ratio: float
    served_first: bool


@dataclass(frozen=True)
class ServiceByType:
    types: tuple[TypeService, ...]
    outliers: tuple[Outlier, ...]


@dataclass(frozen=True)
class CargoBalance:
    cargo: int
    cargo_name: str
    producers: int
    producing_producers: int
    produced: float
    shipped: float
    consumers: int
    consuming_consumers: int
    demand: float
    consumed_first: float
    consumed_last: float
    unused: float


@dataclass(frozen=True)
class FlowEntry:
    cargo: int
    cargo_name: str
    value: float
    capacity: float


@dataclass(frozen=True)
class ConsumerStatus:
    industry: int
    name: str
    label: str
    status: str  # idle | output-stock-full | input-limited | running
    inputs: tuple[FlowEntry, ...]
    outputs: tuple[FlowEntry, ...]
    consumed_first: float | None
    consumed_last: float
    consumption_capacity: float
    limiting_cargo: int | None
    limiting_cargo_name: str | None
    flagged: bool


@dataclass(frozen=True)
class ChainAnalysis:
    consumers: int
    balances: tuple[CargoBalance, ...]
    consumer_statuses: tuple[ConsumerStatus, ...]  # largest consumption capacity first
    status_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class StockGroup:
    code: str  # output-shipped | output-not-shipped | input | warehouse
    stocks_last: int
    mean_fill_first: float | None
    mean_fill_last: float | None
    full_first: int
    full_last: int


@dataclass(frozen=True)
class StockMover:
    owner: Any
    owner_name: str
    role: str
    cargos: tuple[str, ...]
    fill_first: float
    fill_last: float
    delta: float


@dataclass(frozen=True)
class StockProgression:
    samples_with_stocks: int
    first: SampleRef | None
    last: SampleRef | None
    latest_has_stocks: bool
    groups: tuple[StockGroup, ...]
    movers: tuple[StockMover, ...]  # |fill change| >= 20 points, largest first (non-warehouse)


@dataclass(frozen=True)
class ClosureRow:
    industry: IndustryFacts
    remaining: ClosureRemaining
    flagged_since: SampleRef | None
    station_link: bool | None  # None when the name-match screen itself was unavailable
    cancel_ways: tuple[str, ...]  # load-output | deliver-inputs
    input_cargo_names: tuple[str, ...]


@dataclass(frozen=True)
class RiskTier:
    code: str  # idle-every-sample | producing-never-shipped | shipped-at-least-once
    industries: int


@dataclass(frozen=True)
class IdleRisk:
    industry: int
    name: str
    label: str
    capacity: float
    consumption_capacity: float
    inputs: tuple[FlowEntry, ...]


@dataclass(frozen=True)
class ClosureAnalysis:
    flagged_now: tuple[ClosureRow, ...]
    outcomes: tuple[LifecycleEvent, ...]  # closed / disappeared / cancelled events, oldest first
    risk_tiers: tuple[RiskTier, ...]
    idle_pool: tuple[IdleRisk, ...]       # idle tier, largest consumption capacity first
    samples: int
    span: Span


@dataclass(frozen=True)
class LineCargoMatch:
    line_name: str
    ship_cargos: tuple[int, ...]
    deliver_cargos: tuple[int, ...]


@dataclass(frozen=True)
class StationEntry:
    station: str
    lines: tuple[LineCargoMatch, ...]


@dataclass(frozen=True)
class CargoRef:
    id: int
    name: str


@dataclass(frozen=True)
class IndustryLink:
    """A name-matched station on at least one of our lines: an inference, never a verified catchment link."""

    industry: IndustryFacts
    role: str  # producer | consumer | producer-consumer
    stations: tuple[StationEntry, ...]
    serving_lines: tuple[str, ...]  # lines whose capacity matches the industry's cargo
    other_lines: tuple[str, ...]    # lines stopping there without its cargo
    matched_cargos: tuple[CargoRef, ...]
    cargo_matches: bool
    produced_first: float | None
    shipped_first: float | None


@dataclass(frozen=True)
class UnlinkedShipper:
    industry: int
    name: str
    shipped: float


@dataclass(frozen=True)
class LinkAnalysis:
    links: tuple[IndustryLink, ...]  # closing first, then cargo-matched, largest producers first
    shipping_industries: int
    shipping_with_link: int
    shipping_without_link: int
    cargo_matched_industries: int
    unlinked_shippers: tuple[UnlinkedShipper, ...]  # largest shipments first


@dataclass(frozen=True)
class ManualReview:
    priority: int
    code: str  # closure-flagged | production-decline | unshipped-coproduct-full
    industry: int
    name: str
    remaining: ClosureRemaining | None = None
    produced_first: float | None = None
    produced_last: float | None = None
    decline: float | None = None


@dataclass(frozen=True)
class IndustriesView:
    coverage: ViewCoverage
    status: str  # ok | no-industries | incomplete-flows
    first: SampleRef
    latest: SampleRef
    sample_count: int
    span: Span
    stock_samples: int
    first_stock_sample: SampleRef | None
    error_families: tuple[str, ...]
    industry_count: int
    unknown_flow_count: int
    industries: tuple[IndustryFacts, ...]
    criteria: tuple[ViewCriterion, ...]
    comparison: Comparison | None
    evolution: tuple[EvolutionPoint, ...] | None
    events: tuple[LifecycleEvent, ...]
    levels: LevelsAnalysis | None
    service_by_cargo: tuple[CargoService, ...] | None
    service_by_type: ServiceByType | None
    chains: ChainAnalysis | None
    stocks: StockProgression | None
    closures: ClosureAnalysis | None
    links: LinkAnalysis | None
    manual_review: tuple[ManualReview, ...] | None


# ---------------------------------------------------------------------------
# Flattening
# ---------------------------------------------------------------------------

@dataclass
class _Sample:
    tick: int
    label: str
    day: float | None
    inds: dict[int, IndustryFacts]
    stocks: dict[tuple[Any, Any], StockFacts] | None

    @property
    def ref(self) -> SampleRef:
        return SampleRef(self.tick, self.label)


def _list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, dict):
        return list(value.values())
    return value if isinstance(value, list) else []


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _num(value: Any) -> float:
    return float(value) if _is_number(value) else 0.0


def _label(type_path: Any) -> str:
    if not type_path or not isinstance(type_path, str):
        return "unknown"
    tail = type_path.rstrip("/").split("/")[-1]
    if tail.endswith(".con"):
        tail = tail[:-4]
    return tail.replace("_", " ") or "unknown"


def _ratio(shipped: float, produced: float) -> float | None:
    return shipped / produced if produced > 0 else None


def _int_id(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _facts(raw: dict[str, Any], closing: set[Any]) -> IndustryFacts:
    iid = raw["id"]
    closure = int(_num(raw.get("closureTimeStamp")))
    unknown = "outputs" not in raw or "inputs" not in raw
    outs: dict[int, OutputFlow] = {}
    ins: dict[int, InputFlow] = {}
    for flow in _list(raw.get("outputs")):
        if not isinstance(flow, dict) or flow.get("cargo") is None:
            if not isinstance(flow, dict):
                unknown = True
            continue
        values = [flow.get(k) for k in ("producedYear", "maxProductionYear", "shippedYear")]
        if not _int_id(flow["cargo"]) or not all(_is_number(v) for v in values):
            unknown = True
            continue
        outs[flow["cargo"]] = OutputFlow(flow["cargo"], *(float(v) for v in values))
    for flow in _list(raw.get("inputs")):
        if not isinstance(flow, dict) or flow.get("cargo") is None:
            if not isinstance(flow, dict):
                unknown = True
            continue
        values = [flow.get(k) for k in ("consumedYear", "maxConsumptionYear")]
        if not _int_id(flow["cargo"]) or not all(_is_number(v) for v in values):
            unknown = True
            continue
        ins[flow["cargo"]] = InputFlow(flow["cargo"], *(float(v) for v in values))
    if unknown:
        outs, ins = {}, {}
    produced = sum(o.produced for o in outs.values())
    capacity = sum(o.max_production for o in outs.values())
    level, max_level = raw.get("level"), raw.get("maxLevel")
    rating = raw.get("productionRating")
    return IndustryFacts(
        id=iid,
        name=raw.get("name") or f"Industry #{iid}",
        type=raw.get("type") or "",
        label=_label(raw.get("type")),
        level=level if _int_id(level) else None,
        max_level=max_level if _int_id(max_level) else None,
        rating=float(rating) if _is_number(rating) else None,
        closure_tick=closure,
        flagged=bool(closure) or iid in closing,
        unknown_flows=unknown,
        outputs=tuple(outs.values()),
        inputs=tuple(ins.values()),
        produced=produced,
        shipped=sum(o.shipped for o in outs.values()),
        capacity=capacity,
        consumed=sum(i.consumed for i in ins.values()),
        consumption_capacity=sum(i.max_consumption for i in ins.values()),
        producing=produced > 0,
        served=sum(o.shipped for o in outs.values()) > 0,
        idle=bool(outs) and capacity > 0 and produced == 0,
        has_levels=bool(max_level) and _int_id(max_level),
    )


def _stocks(rows: Any, inds: dict[int, IndustryFacts], malformed: list[str]) -> dict[tuple[Any, Any], StockFacts] | None:
    stocks = _list(rows)
    if not stocks:
        return None
    out: dict[tuple[Any, Any], StockFacts] = {}
    for st in stocks:
        if not isinstance(st, dict):
            malformed.append("stock")
            continue
        cap, cnt = st.get("capacity"), st.get("count")
        if not _is_number(cap) or not _is_number(cnt) or cap <= 0:
            continue
        cargos = tuple(c for c in _list(st.get("cargos")) if isinstance(c, int))
        owner = st.get("owner")
        try:
            if st.get("kind") == "warehouse":
                role = "warehouse"
            elif st.get("kind") == "industry" and owner in inds:
                ind = inds[owner]
                outs = {o.cargo for o in ind.outputs}
                ins = {i.cargo for i in ind.inputs}
                if set(cargos) & outs:
                    role = "output"
                elif set(cargos) & ins:
                    role = "input"
                else:
                    continue
            else:
                continue
            out[(owner, st.get("stockId"))] = StockFacts(owner, st.get("stockId"), role, cnt / cap, cnt, cap, cargos)
        except TypeError:  # unhashable owner / stock id
            malformed.append("stock")
    return out


def _sample(rows: SampleRows, malformed: list[str]) -> _Sample:
    problems = rows.problems if isinstance(rows.problems, dict) else {}
    closing = set(x for x in _list(problems.get("closingIndustries")) if isinstance(x, (int, str)))
    inds: dict[int, IndustryFacts] = {}
    for raw in _list(rows.industries):
        if not isinstance(raw, dict) or not _int_id(raw.get("id")):
            malformed.append("industry")
            continue
        inds[raw["id"]] = _facts(raw, closing)
    ordinal = calendar_ordinal(rows.date)
    return _Sample(rows.tick, rows.label, float(ordinal) if ordinal is not None else None, inds,
                   _stocks(rows.stocks, inds, malformed))


# ---------------------------------------------------------------------------
# Calculations
# ---------------------------------------------------------------------------

def _stats(inds: Sequence[IndustryFacts]) -> GroupStats:
    total = len(inds)
    known = [i for i in inds if not i.unknown_flows]
    produced = sum(i.produced for i in known)
    shipped = sum(i.shipped for i in known)
    return GroupStats(
        n=total,
        producing=sum(1 for i in known if i.producing),
        idle=sum(1 for i in known if i.idle),
        served=sum(1 for i in known if i.served),
        produced=produced,
        shipped=shipped,
        ratio=_ratio(shipped, produced),
        level=sum(i.level or 0 for i in known if i.has_levels),
        max_level=sum(i.max_level or 0 for i in known if i.has_levels),
        flagged=sum(1 for i in known if i.flagged),
    )


def _full_outputs(sample: _Sample, full: float) -> int | None:
    if sample.stocks is None:
        return None
    return sum(1 for s in sample.stocks.values() if s.role == "output" and s.fill >= full)


def _pick_evenly(samples: Sequence[_Sample]) -> list[_Sample]:
    if len(samples) <= MAX_EVOLUTION_ROWS:
        return list(samples)
    if any(s.day is None for s in samples):
        return [samples[round(i * (len(samples) - 1) / (MAX_EVOLUTION_ROWS - 1))] for i in range(MAX_EVOLUTION_ROWS)]
    first_day, last_day = samples[0].day, samples[-1].day
    chosen: list[_Sample] = []
    for bucket in BUCKET_DAYS:
        buckets: dict[int, _Sample] = {}
        for s in samples:
            buckets[int((s.day - first_day) // bucket)] = s  # last sample of each bucket
        chosen = list(buckets.values())
        if len(chosen) + 1 <= MAX_EVOLUTION_ROWS or bucket == BUCKET_DAYS[-1]:
            break
    picks = {id(samples[0]): samples[0], id(samples[-1]): samples[-1], **{id(s): s for s in chosen}}
    ordered = sorted(picks.values(), key=lambda s: s.day)
    if len(ordered) > MAX_EVOLUTION_ROWS:  # pathological spacing: thin evenly, keep both ends
        step = (len(ordered) - 1) / (MAX_EVOLUTION_ROWS - 1)
        ordered = [ordered[round(i * step)] for i in range(MAX_EVOLUTION_ROWS)]
    return ordered if last_day >= first_day else list(samples)


def _span(first: _Sample, last: _Sample, clock) -> Span:
    elapsed = clock.elapsed_between_ticks(first.tick, last.tick) if clock else None
    if elapsed is None or elapsed.value is None:
        return Span(first.ref, last.ref, None, None, elapsed.reason if elapsed else "missing-calendar-context")
    return Span(first.ref, last.ref, elapsed.value, elapsed.value * 365.25, None)


def _remaining(ts: int, now_tick: int, clock) -> ClosureRemaining:
    if not ts:
        return ClosureRemaining("none", ts)
    if ts <= now_tick:
        return ClosureRemaining("due", ts)
    result = clock.elapsed_between_ticks(now_tick, ts) if clock is not None else None
    if result is None or result.value is None:
        return ClosureRemaining("unavailable", ts, None, result.reason if result else "missing-calendar-context")
    return ClosureRemaining("estimate", ts, result.value * 365.25)


def _events(samples: Sequence[_Sample], clock) -> tuple[LifecycleEvent, ...]:
    events: list[tuple[tuple, LifecycleEvent]] = []

    def add(order: int, code: str, sample: _Sample, ind: IndustryFacts, remaining=None, last_seen=None) -> None:
        events.append(((sample.day is None, sample.day or 0, order, ind.name, ind.id),
                       LifecycleEvent(code, sample.ref, sample.day, ind, remaining, last_seen)))

    first = samples[0]
    for ind in first.inds.values():
        if ind.flagged:
            add(4, "closure-at-first-sample", first, ind, _remaining(ind.closure_tick, first.tick, clock))
    for prev, cur in zip(samples, samples[1:]):
        for iid, ind in cur.inds.items():
            if iid not in prev.inds:
                add(1, "new-industry", cur, ind)
                continue
            old = prev.inds[iid]
            if ind.flagged and not old.flagged:
                add(3, "closure-scheduled", cur, ind, _remaining(ind.closure_tick, cur.tick, clock))
            elif old.flagged and not ind.flagged:
                add(3, "closure-cancelled", cur, ind)
        for iid, old in prev.inds.items():
            if iid in cur.inds:
                continue
            if old.closure_tick and old.closure_tick <= cur.tick:
                code = "closed-as-scheduled"
            elif old.flagged:
                code = "closed-flagged"
            else:
                code = "disappeared"
            add(2, code, cur, old, None, prev.label)
    events.sort(key=lambda item: item[0])
    return tuple(event for _key, event in events)


def _level(ind: IndustryFacts) -> int:
    return ind.level or 0


def _comparison(first: _Sample, last: _Sample, common: list[int], events: Sequence[LifecycleEvent], full: float) -> Comparison:
    return Comparison(
        first=first.ref, last=last.ref, common_count=len(common),
        all_first=_stats(list(first.inds.values())), all_last=_stats(list(last.inds.values())),
        common_first=_stats([first.inds[i] for i in common]), common_last=_stats([last.inds[i] for i in common]),
        new_count=sum(1 for i in last.inds if i not in first.inds),
        vanished_count=sum(1 for i in first.inds if i not in last.inds),
        level_ups=sum(1 for i in common if _level(last.inds[i]) > _level(first.inds[i])),
        level_downs=sum(1 for i in common if _level(last.inds[i]) < _level(first.inds[i])),
        full_outputs_first=_full_outputs(first, full), full_outputs_last=_full_outputs(last, full),
        closures_scheduled=sum(1 for e in events if e.code == "closure-scheduled"),
        closures_cancelled=sum(1 for e in events if e.code == "closure-cancelled"),
    )


def _levels(first: _Sample, last: _Sample, common: list[int], cargo_name) -> LevelsAnalysis:
    f, lt = first.inds, last.inds
    changed = [i for i in common if _level(lt[i]) != _level(f[i]) or (lt[i].max_level or 0) != (f[i].max_level or 0)]
    changed.sort(key=lambda i: (-abs(_level(lt[i]) - _level(f[i])), lt[i].name, i))
    level_changes = tuple(LevelChange(i, lt[i].name, lt[i].label, f[i].level, lt[i].level, f[i].max_level, lt[i].max_level,
                                      f[i].produced, lt[i].produced, f[i].shipped, lt[i].shipped, f[i].served)
                          for i in changed)
    rated = [i for i in common if f[i].rating is not None and lt[i].rating is not None
             and abs(lt[i].rating - f[i].rating) >= RATING_CHANGE_MIN]
    rated.sort(key=lambda i: (-abs(lt[i].rating - f[i].rating), lt[i].name, i))
    rating_changes = tuple(RatingChange(i, lt[i].name, lt[i].label, f[i].rating, lt[i].rating, f[i].produced, lt[i].produced)
                           for i in rated)
    leveled = [i for i in common if f[i].has_levels]
    groups: tuple[UpgradeGroup, ...] = ()
    if leveled:
        shipping = [i for i in leveled if f[i].served]
        idle = [i for i in leveled if not f[i].served]
        groups = tuple(UpgradeGroup(code, len(ids), sum(1 for i in ids if _level(lt[i]) > _level(f[i])))
                       for code, ids in (("shipping-at-first", shipping), ("not-shipping-at-first", idle)))
    movers: list[ProductionMover] = []
    for i in common:
        a, b = f[i], lt[i]
        before = {o.cargo: o for o in a.outputs}
        for out in b.outputs:
            old = before.get(out.cargo)
            if old is None:
                continue
            delta = out.produced - old.produced
            if abs(delta) >= max(MOVER_MIN_DELTA, MOVER_MIN_SHARE * old.produced):
                movers.append(ProductionMover(
                    "up" if delta > 0 else "down", i, b.name, out.cargo, cargo_name(out.cargo), old.produced,
                    out.produced, delta, old.shipped, out.shipped, a.level, b.level, _level(b) != _level(a), a.rating,
                    b.rating, a.rating is not None and b.rating is not None and abs(b.rating - a.rating) >= RATING_HINT_MIN))
    ups = sorted((m for m in movers if m.delta > 0), key=lambda m: (-m.delta, m.name, m.industry, m.cargo))
    downs = sorted((m for m in movers if m.delta < 0), key=lambda m: (m.delta, m.name, m.industry, m.cargo))
    return LevelsAnalysis(level_changes, rating_changes, groups, tuple(ups + downs))


def _service_by_cargo(first: _Sample, last: _Sample, common: list[int], cargo_name) -> tuple[CargoService, ...]:
    agg: dict[int, dict[str, float]] = {}
    for i in common:
        for sample, key in ((first, "f"), (last, "l")):
            for out in sample.inds[i].outputs:
                d = agg.setdefault(out.cargo, {"fp": 0, "fs": 0, "lp": 0, "ls": 0, "producers": 0, "served": 0})
                d[key + "p"] += out.produced
                d[key + "s"] += out.shipped
                if key == "l":
                    d["producers"] += 1 if out.produced > 0 else 0
                    d["served"] += 1 if out.shipped > 0 else 0
    rows = []
    for cargo, d in sorted(agg.items(), key=lambda kv: (-kv[1]["lp"], kv[0])):
        if d["lp"] <= 0 and d["fp"] <= 0:
            continue
        rows.append(CargoService(cargo, cargo_name(cargo), d["fp"], d["lp"], d["fs"], d["ls"],
                                 _ratio(d["fs"], d["fp"]), _ratio(d["ls"], d["lp"]), int(d["producers"]), int(d["served"])))
    return tuple(rows)


def _service_by_type(first: _Sample, last: _Sample, common: list[int]) -> ServiceByType:
    by_type: dict[str, list[int]] = {}
    for i in common:
        by_type.setdefault(last.inds[i].label, []).append(i)
    types: list[TypeService] = []
    for label, ids in sorted(by_type.items(), key=lambda kv: (-_stats([last.inds[i] for i in kv[1]]).produced, kv[0])):
        f, lt = _stats([first.inds[i] for i in ids]), _stats([last.inds[i] for i in ids])
        ratings = [last.inds[i].rating for i in ids if last.inds[i].producing and last.inds[i].rating is not None]
        types.append(TypeService(label, len(ids), lt.producing, lt.served, f.produced, lt.produced, f.ratio, lt.ratio,
                                 statistics.fmean(ratings) if ratings else None, f.produced <= 0 and lt.produced <= 0))
    outliers: list[Outlier] = []
    for label, ids in by_type.items():
        producing = [last.inds[i] for i in ids if last.inds[i].producing]
        served = [x for x in producing if x.served]
        unserved = [x for x in producing if not x.served]
        if len(producing) < OUTLIER_MIN_PRODUCING or not served or not unserved:
            continue
        median = statistics.median(_ratio(x.shipped, x.produced) or 0.0 for x in producing)
        for x in unserved:
            outliers.append(Outlier(x.id, x.name, label, x.produced, len(served), len(producing), median,
                                    first.inds[x.id].served))
    outliers.sort(key=lambda o: (-o.produced, o.name, o.industry))
    return ServiceByType(tuple(types), tuple(outliers))


def _chains(first: _Sample, last: _Sample, full: float, policy, cargo_name) -> ChainAnalysis | None:
    consumers = [i for i in last.inds.values() if i.inputs]
    if not consumers:
        return ChainAnalysis(0, (), (), ())
    balances: list[CargoBalance] = []
    for c in sorted({f.cargo for i in consumers for f in i.inputs}):
        producers = [i for i in last.inds.values() if any(o.cargo == c for o in i.outputs)]
        cons = [i for i in consumers if any(f.cargo == c for f in i.inputs)]
        def out_of(i, c=c):
            return next(o for o in i.outputs if o.cargo == c)
        def in_of(i, c=c):
            return next(f for f in i.inputs if f.cargo == c)
        consumed = sum(in_of(i).consumed for i in cons)
        demand = sum(in_of(i).max_consumption for i in cons)
        consumed_first = sum(in_of(first.inds[i.id]).consumed for i in cons
                             if i.id in first.inds and any(f.cargo == c for f in first.inds[i.id].inputs))
        balances.append(CargoBalance(
            c, cargo_name(c), len(producers), sum(1 for i in producers if i.producing),
            sum(out_of(i).produced for i in producers), sum(out_of(i).shipped for i in producers), len(cons),
            sum(1 for i in cons if in_of(i).consumed > 0), demand, consumed_first, consumed, demand - consumed))
    balances.sort(key=lambda b: (-b.unused, b.cargo_name, b.cargo))

    statuses: list[ConsumerStatus] = []
    counts: dict[str, int] = {}
    for ind in consumers:
        ratios = {f.cargo: (f.consumed / f.max_consumption if f.max_consumption > 0 else None) for f in ind.inputs}
        known = [r for r in ratios.values() if r is not None]
        out_full = last.stocks is not None and any(
            s.owner == ind.id and s.role == "output" and s.fill >= full for s in last.stocks.values())
        below_capacity = ind.capacity > 0 and ind.produced < policy.below_capacity_ratio * ind.capacity
        if ind.consumed == 0:
            status = STATUS_IDLE
        elif out_full and below_capacity:
            status = STATUS_OUTPUT_FULL
        elif known and min(known) < INPUT_LIMITED_RATIO:
            status = STATUS_INPUT_LIMITED
        else:
            status = STATUS_RUNNING
        counts[status] = counts.get(status, 0) + 1
        before = first.inds.get(ind.id)
        limiting = None
        if status != STATUS_RUNNING:
            limiting = min((c for c, r in ratios.items() if r is not None), key=lambda c: ratios[c], default=None)
        statuses.append(ConsumerStatus(
            ind.id, ind.name, ind.label, status,
            tuple(FlowEntry(f.cargo, cargo_name(f.cargo), f.consumed, f.max_consumption) for f in ind.inputs),
            tuple(FlowEntry(o.cargo, cargo_name(o.cargo), o.produced, o.max_production) for o in ind.outputs),
            before.consumed if before else None, ind.consumed, ind.consumption_capacity, limiting,
            cargo_name(limiting) if limiting is not None else None, ind.flagged))
    statuses.sort(key=lambda s: (-s.consumption_capacity, s.name, s.industry))
    return ChainAnalysis(len(consumers), tuple(balances), tuple(statuses), tuple(sorted(counts.items())))


def _stock_progression(samples: Sequence[_Sample], last: _Sample, full: float, cargo_name) -> StockProgression:
    with_stocks = [s for s in samples if s.stocks is not None]
    if not with_stocks:
        return StockProgression(0, None, None, False, (), ())
    f, lt = with_stocks[0], with_stocks[-1]

    def groups_of(sample: _Sample) -> dict[str, list[float]]:
        groups: dict[str, list[float]] = {"output-shipped": [], "output-not-shipped": [], "input": [], "warehouse": []}
        for st in sample.stocks.values():
            ind = sample.inds.get(st.owner) if st.role == "output" else None
            if st.role == "output" and ind:
                shipped = any(o.shipped > 0 for o in ind.outputs if o.cargo in st.cargos)
                groups["output-shipped" if shipped else "output-not-shipped"].append(st.fill)
            elif st.role == "input":
                groups["input"].append(st.fill)
            elif st.role == "warehouse":
                groups["warehouse"].append(st.fill)
        return groups

    gf, gl = groups_of(f), groups_of(lt)
    groups = tuple(StockGroup(code, len(gl[code]), statistics.fmean(gf[code]) if gf[code] else None,
                              statistics.fmean(gl[code]) if gl[code] else None,
                              sum(1 for x in gf[code] if x >= full), sum(1 for x in gl[code] if x >= full))
                   for code in gl)
    movers: list[StockMover] = []
    if f is not lt:
        for key, st in lt.stocks.items():
            old = f.stocks.get(key)
            if old is None or st.role == "warehouse":
                continue
            delta = st.fill - old.fill
            if abs(delta) >= STOCK_MOVER_MIN:
                ind = lt.inds.get(st.owner)
                movers.append(StockMover(st.owner, ind.name if ind else f"Industry #{st.owner}", st.role,
                                         tuple(cargo_name(c) for c in st.cargos), old.fill, st.fill, delta))
        movers.sort(key=lambda m: (-abs(m.delta), m.owner_name, str(m.owner)))
    return StockProgression(len(with_stocks), f.ref, lt.ref, lt is last, groups, tuple(movers))


def _line_cargo_offset(snap: Snapshot) -> int:
    """lines[].capacity[].cargo is cargoTypeId + 1 in current mod output (Lua 1-based key); id 0 means real ids."""
    for line in snap.lines:
        for c in line.get("capacity") or []:
            if c.get("cargo") == 0 and _num(c.get("capacity")) > 0:
                return 0
    return 1


def _line_cargos(line: dict[str, Any], offset: int) -> set[int]:
    return {int(c["cargo"]) - offset for c in line.get("capacity") or []
            if isinstance(c.get("cargo"), int) and _num(c.get("capacity")) > 0}


def _links(first: _Sample, last: _Sample, snap: Snapshot, cargo_name) -> LinkAnalysis:
    offset = _line_cargo_offset(snap)
    by_name: dict[str, list[IndustryFacts]] = {}
    for ind in last.inds.values():
        by_name.setdefault(ind.name.strip(), []).append(ind)
    lines = snap.lines_by_id
    found: dict[int, list[StationEntry]] = {}
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
        wanted_out = {o.cargo for o in ind.outputs}
        wanted_in = {i.cargo for i in ind.inputs}
        entry_lines = []
        for ln in linked:
            carried = _line_cargos(ln, offset)
            entry_lines.append(LineCargoMatch(ln.get("name") or f"Line #{ln['id']}", tuple(sorted(carried & wanted_out)),
                                              tuple(sorted(carried & wanted_in))))
        found.setdefault(ind.id, []).append(StationEntry(name, tuple(entry_lines)))

    links: list[tuple[tuple, IndustryLink]] = []
    for iid, entries in found.items():
        ind = last.inds[iid]
        before = first.inds.get(iid)
        serving: list[str] = []
        others: list[str] = []
        cargos: set[int] = set()
        for entry in entries:
            for ln in entry.lines:
                (serving if ln.ship_cargos or ln.deliver_cargos else others).append(ln.line_name)
                cargos.update(ln.ship_cargos)
                cargos.update(ln.deliver_cargos)
        role = "producer" if ind.outputs and not ind.inputs else (
            "consumer" if ind.inputs and not ind.outputs else "producer-consumer")
        refs = tuple(sorted((CargoRef(c, cargo_name(c)) for c in cargos), key=lambda r: (r.name, r.id)))
        links.append(((0 if ind.flagged else 1, 1 if cargos else 0, -ind.produced, ind.name, ind.id), IndustryLink(
            ind, role, tuple(entries), tuple(dict.fromkeys(serving)), tuple(dict.fromkeys(others)), refs, bool(cargos),
            before.produced if before else None, before.shipped if before else None)))
    links.sort(key=lambda item: item[0])

    shipping = [i for i in last.inds.values() if i.served]
    unmatched = [i for i in shipping if i.id not in found]
    return LinkAnalysis(
        tuple(link for _key, link in links), len(shipping), len(shipping) - len(unmatched), len(unmatched),
        sum(1 for link in (lk for _k, lk in links) if link.cargo_matches),
        tuple(UnlinkedShipper(i.id, i.name, i.shipped) for i in sorted(unmatched, key=lambda i: (-i.shipped, i.name, i.id))))


def _closures(first: _Sample, last: _Sample, samples: Sequence[_Sample], events: Sequence[LifecycleEvent],
              links: LinkAnalysis | None, clock, cargo_name) -> ClosureAnalysis:
    flagged_since: dict[int, SampleRef] = {}
    for s in samples:
        for iid, ind in s.inds.items():
            if ind.flagged and iid not in flagged_since:
                flagged_since[iid] = s.ref
    linked = {link.industry.id for link in links.links} if links is not None else None
    now = sorted((i for i in last.inds.values() if i.flagged), key=lambda i: (i.closure_tick or 2**62, i.name, i.id))
    rows = []
    for ind in now:
        cancel = []
        if ind.producing or ind.capacity > 0:
            cancel.append("load-output")
        if ind.inputs:
            cancel.append("deliver-inputs")
        rows.append(ClosureRow(ind, _remaining(ind.closure_tick, last.tick, clock), flagged_since.get(ind.id),
                               None if linked is None else ind.id in linked, tuple(cancel),
                               tuple(cargo_name(f.cargo) for f in ind.inputs)))
    outcomes = tuple(e for e in events if e.code.startswith("closed") or e.code == "closure-cancelled"
                     or e.code == "disappeared")

    served_ever = {i for s in samples for i, ind in s.inds.items() if ind.served}
    active_ever = {i for s in samples for i, ind in s.inds.items() if ind.producing}
    pool = [i for i in last.inds.values() if not i.flagged and i.outputs]
    idle = [i for i in pool if i.id not in active_ever]
    tiers = (RiskTier("idle-every-sample", len(idle)),
             RiskTier("producing-never-shipped", sum(1 for i in pool if i.id in active_ever and i.id not in served_ever)),
             RiskTier("shipped-at-least-once", sum(1 for i in pool if i.id in served_ever)))
    idle_rows = tuple(IdleRisk(i.id, i.name, i.label, i.capacity, i.consumption_capacity,
                               tuple(FlowEntry(f.cargo, cargo_name(f.cargo), f.consumed, f.max_consumption) for f in i.inputs))
                      for i in sorted(idle, key=lambda i: (-i.consumption_capacity, i.name, i.id)))
    return ClosureAnalysis(tuple(rows), outcomes, tiers, idle_rows, len(samples), _span(samples[0], samples[-1], clock))


def _manual_review(first: _Sample, last: _Sample, clock, full: float, policy) -> tuple[ManualReview, ...]:
    rows: list[ManualReview] = []
    closing = sorted((i for i in last.inds.values() if i.flagged), key=lambda i: (i.closure_tick or 2**62, i.name, i.id))
    if closing:
        ind = closing[0]
        rows.append(ManualReview(1, "closure-flagged", ind.id, ind.name, _remaining(ind.closure_tick, last.tick, clock)))
    declines = [(before.produced - last.inds[iid].produced, last.inds[iid], before)
                for iid, before in first.inds.items() if iid in last.inds
                and not before.unknown_flows and not last.inds[iid].unknown_flows]
    if declines:
        delta, ind, before = max(declines, key=lambda row: (row[0], row[1].name, -row[1].id))
        if delta >= policy.production_decline_min:
            rows.append(ManualReview(2, "production-decline", ind.id, ind.name, None, before.produced, ind.produced, delta))
    if last.stocks:
        blocked = [ind for ind in last.inds.values() if ind.served and any(
            st.owner == ind.id and st.role == "output" and st.fill >= full
            and any(o.cargo in st.cargos and o.shipped == 0 for o in ind.outputs)
            for st in last.stocks.values())]
        if blocked:
            ind = max(blocked, key=lambda ind: (ind.produced, ind.name, -ind.id))
            rows.append(ManualReview(3, "unshipped-coproduct-full", ind.id, ind.name))
    return tuple(rows)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _criteria(policy, full: float) -> tuple[ViewCriterion, ...]:
    return (
        ViewCriterion("below_capacity_ratio", policy.below_capacity_ratio, "ratio",
                      "consumer output below ratio * positive capacity while an output stock is full", "policy"),
        ViewCriterion("production_decline_min", policy.production_decline_min, "recorded production counter",
                      "first minus last produced >= minimum selects the manual-review decline", "policy"),
        ViewCriterion("full_stock_ratio", full, "ratio", "stock fill >= ratio counts as full", "threshold"),
        ViewCriterion("evolution_max_samples", MAX_EVOLUTION_ROWS, "samples", "evenly picked evolution samples, first and latest kept", "engine"),
        ViewCriterion("mover_min_delta", MOVER_MIN_DELTA, "items/yr", "production mover: absolute change at least this and the share below", "engine"),
        ViewCriterion("mover_min_share", MOVER_MIN_SHARE, "ratio of first value", "production mover share of the first value", "engine"),
        ViewCriterion("rating_change_min", RATING_CHANGE_MIN, "rating", "listed production-rating change", "engine"),
        ViewCriterion("rating_hint_min", RATING_HINT_MIN, "rating", "rating change noted beside a production mover", "engine"),
        ViewCriterion("stock_mover_min", STOCK_MOVER_MIN, "fill fraction", "listed stock fill change between first and latest stock samples", "engine"),
        ViewCriterion("input_limited_ratio", INPUT_LIMITED_RATIO, "consumed / capacity", "consumer input-limited when any input is consumed below this share", "engine"),
        ViewCriterion("outlier_min_producing", OUTLIER_MIN_PRODUCING, "industries", "same-type producing industries needed for an unserved-outlier screen", "engine"),
    )


def evaluate(evidence: IndustriesEvidence, *, context: EvaluationContext) -> IndustriesView:
    full = context.thresholds.full_stock_ratio
    policy = context.policies["industries"]
    clock = context.clock
    snap = evidence.endpoint
    malformed: list[str] = []
    samples = [_sample(rows, malformed) for rows in evidence.samples]
    first, last = samples[0], samples[-1]
    failures: list[Unavailable] = []
    unavailable: list[Unavailable] = []

    def cargo_name(cargo_id: int) -> str:
        return snap.cargo(cargo_id) or f"Cargo #{cargo_id}"

    def section(name: str, compute):
        try:
            return compute()
        except SECTION_ERRORS as exc:
            failures.append(Unavailable("section-uninterpretable", type(exc).__name__, name))
            return None

    if malformed:
        unavailable.append(Unavailable("malformed-rows-skipped", f"{len(malformed)} industry/stock rows were not interpretable"))
    stock_samples = [s for s in samples if s.stocks is not None]
    families = tuple(dict.fromkeys(str(e).split(":")[0] for rows in evidence.samples for e in _list(rows.errors)))
    unknown_flow_count = sum(1 for i in last.inds.values() if i.unknown_flows)
    span = _span(first, last, clock)

    status = "ok"
    if not last.inds:
        status = "no-industries"
        unavailable.append(Unavailable("latest-sample-has-no-industries", subject="industries"))
    elif all(i.unknown_flows for i in last.inds.values()):
        status = "incomplete-flows"
        unavailable.append(Unavailable("no-industry-with-complete-flows", subject="industries"))

    comparison = evolution = levels = service_cargo = service_type = chains = stocks = closures = links = review = None
    events: tuple[LifecycleEvent, ...] = ()
    picks: list[_Sample] = []
    if status == "ok":
        common = [i for i in first.inds if i in last.inds and not first.inds[i].unknown_flows
                  and not last.inds[i].unknown_flows]
        if len(samples) > 1:
            events = section("events", lambda: _events(samples, clock)) or ()
        comparable = len(samples) > 1 and bool(common)
        if not comparable:
            unavailable.append(Unavailable("insufficient-comparison",
                                           "fewer than two samples" if len(samples) < 2 else "no industry with complete flows at both ends",
                                           "comparison"))
        else:
            comparison = section("summary", lambda: _comparison(first, last, common, events, full))
            levels = section("levels", lambda: _levels(first, last, common, cargo_name))
            service_cargo = section("service-by-cargo", lambda: _service_by_cargo(first, last, common, cargo_name))
            service_type = section("service-by-type", lambda: _service_by_type(first, last, common))

        def evolve():
            chosen = _pick_evenly(samples)
            picks.extend(chosen)
            return tuple(EvolutionPoint(s.ref, _stats(list(s.inds.values())), _full_outputs(s, full)) for s in chosen)

        evolution = section("evolution", evolve)
        chains = section("chains", lambda: _chains(first, last, full, policy, cargo_name))
        stocks = section("stocks", lambda: _stock_progression(samples, last, full, cargo_name))
        links = section("lines", lambda: _links(first, last, snap, cargo_name))
        closures = section("closures", lambda: _closures(first, last, samples, events, links, clock, cargo_name))
        review = section("manual-review", lambda: _manual_review(first, last, clock, full, policy))
        if stocks is not None and stocks.samples_with_stocks == 0:
            unavailable.append(Unavailable("no-stock-data", "no sample contains stock data", "stocks"))

    coverage = ViewCoverage(
        endpoint=SampleRef(context.endpoint, snap.date_label),
        eligible=evidence.eligible, read=len(samples), used=len(samples), hydrated=evidence.hydrated,
        hydration_limit=0, sampled=tuple(s.ref for s in picks),
        limits={"evolutionSamples": MAX_EVOLUTION_ROWS},
        omitted=max(0, len(samples) - len(picks)) if picks else 0,
        warnings=tuple(f"{u.code}: {u.subject}" for u in failures),
        collection_errors=families, unavailable=tuple(unavailable) + tuple(failures))
    return IndustriesView(
        coverage=coverage, status=status, first=first.ref, latest=last.ref, sample_count=len(samples), span=span,
        stock_samples=len(stock_samples), first_stock_sample=stock_samples[0].ref if stock_samples else None,
        error_families=families, industry_count=len(last.inds), unknown_flow_count=unknown_flow_count,
        industries=tuple(last.inds.values()), criteria=_criteria(policy, full), comparison=comparison,
        evolution=evolution, events=events, levels=levels, service_by_cargo=service_cargo,
        service_by_type=service_type, chains=chains, stocks=stocks, closures=closures, links=links,
        manual_review=review)
