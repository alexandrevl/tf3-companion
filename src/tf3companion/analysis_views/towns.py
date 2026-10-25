"""Towns view: capacity, usage and demand rows with ranks and history, growth/stall, coverage, headroom,
cargo demand, relative hot spots, passenger pairs and the selected key observations.

Town size is the sum of the three building capacities, a proxy and not a head count. The screens below
(large-town quantile, usage headroom, stall window, pair pool) are fixed engine heuristics disclosed in
`criteria`; they are judgments, not methodology policy and not proven game failures. Town geometry is
only what the snapshot stores: when a town has no stored position its distances stay unknown.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Any

from ..game_time import DAYS_PER_YEAR
from ..snapshot import LINE_CAPACITY_CARGO_OFFSET
from .models import EvaluationContext, SampleRef, Unavailable, ViewCoverage
from .towns_evidence import TownPoint, TownSample, TownsEvidence

# Passenger rating = min(1, 2 x line usage) (knowledge/mechanics.md M2): usage above this adds nothing to it.
USAGE_CAP = 0.5
# Growth statistics need a window long enough to mean something (game years) and a few samples.
MIN_WINDOW_YEARS = 0.25
MIN_WINDOW_SAMPLES = 3
LARGE_QUANTILE = 0.6  # 'large' = upper 40% of towns by capacity proxy
MIN_TOWNS_FOR_QUANTILE = 4
HEADROOM_MARGIN = 0.02  # a usage gap smaller than this is not reported; usage within it counts as at the cap
MAX_EVOLUTION_POINTS = 40
PAIR_POOL = 10
MIN_TOWNS_FOR_HOTSPOT_SUMMARY = 4
# `lines[].capacity[].cargo` is cargoTypeId + 1 (`snapshot.LINE_CAPACITY_CARGO_OFFSET`); town
# `cargoSupply[].cargo` and `industries[].outputs[].cargo` are plain cargo ids.


@dataclass(frozen=True)
class Criterion:
    name: str
    value: float
    unit: str
    note: str


@dataclass(frozen=True)
class CargoSupply:
    cargo: int
    cargo_name: str
    supply: float
    limit: float


@dataclass(frozen=True)
class TownLine:
    id: int
    name: str
    passenger: bool


@dataclass(frozen=True)
class TownRow:
    id: int
    name: str
    capacity: float | None
    capacities: tuple[float, ...]
    first_capacity: float | None
    delta: float | None
    growth: float | None
    annual_growth: float | None
    last_change: str | None            # label of the newest sample whose capacity differed from the previous one
    last_change_tick: int | None
    usage: float | None
    usage_first: float | None
    usage_change: float | None
    headroom: float | None             # gap between usage and the passenger-rating cap; None when usage is unknown
    noise: float | None
    noise_first: float | None
    pollution: float | None
    pollution_first: float | None
    development: bool | None
    stations: int
    lines_all: int
    lines_passenger: int
    lines: tuple[TownLine, ...]        # passenger lines first, then by name
    supply: tuple[CargoSupply, ...]
    demands_met: int
    demands_total: int
    rank: int | None
    share: float | None
    large: bool
    served: bool
    reading: str                       # stall-reading code: no-station, freight-only, usage-at-cap, usage-unknown, below-cap
    position: tuple[float, float] | None


@dataclass(frozen=True)
class TownsSummary:
    towns: int
    sized: int
    total_capacity: float | None
    first_total_capacity: float | None
    capacity_change: float | None       # None with a single sample
    growing: int | None                 # None with a single sample
    served: int
    served_share: float | None
    passenger_served: int
    passenger_share: float | None
    weighted_usage: float | None
    development_active: int
    large_threshold: float | None
    window_samples: int
    window_first: SampleRef | None
    window_last: SampleRef | None
    span_years: float | None
    span_days: float | None
    span_reason: str | None


@dataclass(frozen=True)
class EvolutionPoint:
    tick: int
    label: str
    total_capacity: float
    change_vs_first: float
    residential: float
    commercial: float
    industrial: float
    weighted_usage: float | None
    development_active: int


@dataclass(frozen=True)
class GrowthScreen:
    window_sufficient: bool
    comparable: int
    risers: tuple[int, ...]            # town ids, fastest relative growth first
    median_growth: float | None
    stalled: tuple[int, ...]           # town ids without a net gain, largest first
    stalled_served: int
    stalled_unserved: int
    large_served_stalled: tuple[int, ...]


@dataclass(frozen=True)
class CoverageScreen:
    stations_known: bool
    passenger_gaps: tuple[int, ...]    # sized towns with no passenger line, largest first
    gaps_unserved: int
    gaps_unserved_share: float | None
    zero_usage: tuple[int, ...]        # sized towns with a passenger line and a known line usage of exactly 0
    served_ranked: tuple[int, ...]     # sized served towns in rank order


@dataclass(frozen=True)
class UsageGap:
    code: str | None                   # None when evaluable; otherwise the stable insufficiency code
    towns: tuple[int, ...]             # large towns more than the margin below the cap, by capacity x headroom
    scores: tuple[float, ...]          # capacity x headroom, parallel to `towns`


@dataclass(frozen=True)
class CargoDemand:
    cargo: int
    cargo_name: str
    towns: int
    zero_supply_towns: int
    supply: float
    limit: float
    ratio: float | None
    producers: int
    produced_year: float
    unshipped_year: float
    produced_unknown: int              # outputs of this cargo without a stored producedYear
    unshipped_unknown: int             # outputs without both producedYear and shippedYear


@dataclass(frozen=True)
class TownDemand:
    town_id: int
    supply: float
    limit: float
    ratio: float | None
    demands_met: int
    demands_total: int
    unmet_total: float
    largest_cargo: int
    largest_cargo_name: str
    largest_gap: float


@dataclass(frozen=True)
class CargoDemandScreen:
    towns_with_demand: int
    towns_receiving_none: int
    by_cargo: tuple[CargoDemand, ...]  # largest limit-minus-supply gap first
    served_towns: tuple[TownDemand, ...]
    idle_cargos: tuple[int, ...]       # demanded, none delivered, and no output producing it with known flows
    idle_names: tuple[str, ...]


@dataclass(frozen=True)
class HotspotRank:
    town_id: int
    value: float
    change: float | None
    per_100_capacity: float | None


@dataclass(frozen=True)
class PollutionSummary:
    town_id: int
    value: float
    ratio_to_next: float | None
    ratio_to_median: float | None
    relative_worst_id: int | None      # worst pollution per capacity when it is not the highest town


@dataclass(frozen=True)
class Hotspots:
    pollution: tuple[HotspotRank, ...]
    noise: tuple[HotspotRank, ...]
    pollution_summary: PollutionSummary | None


@dataclass(frozen=True)
class TownPair:
    town_a: int
    town_b: int
    capacity_a: float
    capacity_b: float
    status: str                        # no-passenger-link | indirect-shared-network
    distance_km: float | None          # straight line between stored positions; None when a position is unknown


@dataclass(frozen=True)
class PairScreen:
    pool: tuple[int, ...]              # the largest towns considered (PAIR_POOL)
    linked_pairs: int
    separate_networks: int
    transfer_pairs: int
    pairs: tuple[TownPair, ...]
    any_distance: bool


@dataclass(frozen=True)
class KeyObservation:
    code: str                          # unserved-towns | usage-gap | stalled-large-served | fastest-growth | starved-served
    town_id: int
    count: int | None = None
    total: int | None = None
    span_years: float | None = None
    growth: float | None = None
    delta: float | None = None
    cargo_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class TownsView:
    summary: TownsSummary
    rows: tuple[TownRow, ...]          # ranked towns first (largest capacity first), then towns without a capacity
    evolution: tuple[EvolutionPoint, ...]
    growth: GrowthScreen
    coverage_screen: CoverageScreen
    usage_gap: UsageGap
    cargo_demand: CargoDemandScreen
    hotspots: Hotspots
    pairs: PairScreen
    key_observations: tuple[KeyObservation, ...]
    criteria: tuple[Criterion, ...]
    coverage: ViewCoverage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cap(point: TownPoint) -> float | None:
    return float(sum(point.capacities)) if point.capacities else None


def _quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def _weighted_usage(pairs: list[tuple[float, float]]) -> float | None:
    total = sum(c for c, _ in pairs)
    return sum(c * u for c, u in pairs) / total if total else None


def _bucket(sample: TownSample, span_years: float | None) -> tuple[int, ...]:
    if sample.ymd and span_years is not None:
        year, month, _ = sample.ymd
        if span_years <= 2:
            return (year, month)
        return (year, (month - 1) // 3) if span_years <= 10 else (year,)
    # Undated or ambiguous samples retain observation identity, never an invented calendar bucket.
    return (-1, sample.tick)


def _pick(samples: tuple[TownSample, ...], span: float | None) -> list[TownSample]:
    """Last sample per month/quarter/year (by span), plus the first, at most MAX_EVOLUTION_POINTS."""
    if len(samples) <= 2:
        return list(samples)
    buckets: dict[tuple[int, ...], TownSample] = {}
    for s in samples:
        buckets[_bucket(s, span)] = s
    picked = {samples[0].tick: samples[0], **{s.tick: s for s in buckets.values()}}
    out = sorted(picked.values(), key=lambda s: s.tick)
    if len(out) > MAX_EVOLUTION_POINTS:
        step = (len(out) - 1) / (MAX_EVOLUTION_POINTS - 1)
        out = [out[round(i * step)] for i in range(MAX_EVOLUTION_POINTS)]
    return out


class _Network:
    def __init__(self, evidence: TownsEvidence) -> None:
        self.station_town = {s.id: s.town for s in evidence.stations}
        self.stations_by_town: dict[int, set[int]] = {}
        for sid, tid in self.station_town.items():
            self.stations_by_town.setdefault(tid, set()).add(sid)
        self.lines_by_town: dict[int, dict[int, tuple[str, bool]]] = {}
        self.edges: set[frozenset[int]] = set()
        parent: dict[int, int] = {}

        def find(x: int) -> int:
            parent.setdefault(x, x)
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        index = evidence.passenger_cargo + LINE_CAPACITY_CARGO_OFFSET
        for line in evidence.lines:
            towns: list[int] = []
            for group in line.stop_groups:
                tid = self.station_town.get(group)
                if tid is not None and tid not in towns:
                    towns.append(tid)
            passenger = any(cargo == index and (cap or 0) > 0 for cargo, cap in line.capacity)
            for tid in towns:
                known = self.lines_by_town.setdefault(tid, {})
                known[line.id] = (line.name, known.get(line.id, (line.name, False))[1] or passenger)
            if passenger:
                for i, a in enumerate(towns):
                    find(a)
                    for b in towns[i + 1:]:
                        self.edges.add(frozenset((a, b)))
                        parent[find(a)] = find(b)
        self.component = {tid: find(tid) for tid in parent}


def _reading(served: bool, passengers: int, usage: float | None) -> str:
    if not served:
        return "no-station"
    if not passengers:
        return "freight-only"
    if usage is None:
        return "usage-unknown"
    if usage >= USAGE_CAP - HEADROOM_MARGIN:
        return "usage-at-cap"
    return "below-cap"


def _rows(evidence: TownsEvidence, samples: tuple[TownSample, ...], net: _Network, span: float | None) -> tuple[TownRow, ...]:
    last = samples[-1]
    enough = span is not None and span >= MIN_WINDOW_YEARS and len(samples) >= MIN_WINDOW_SAMPLES
    names = dict(evidence.cargo_names)
    positions = dict(evidence.positions)
    presence: dict[int, list[tuple[int, TownPoint]]] = {}
    for i, sample in enumerate(samples):
        for point in sample.towns:
            presence.setdefault(point.id, []).append((i, point))
    drafts: list[dict[str, Any]] = []
    for now in last.towns:
        window = presence[now.id]
        first_index, first = window[0]
        now_cap, first_cap = _cap(now), _cap(first)
        delta = growth = annual = None
        if now_cap is not None and first_cap is not None and first_index != len(samples) - 1:
            delta = now_cap - first_cap
            growth = delta / first_cap if first_cap else None
            if growth is not None and enough and first_index == 0:
                annual = growth / span
        change_tick = change_label = None
        for (_, prev), (cur_index, cur) in zip(window, window[1:]):
            if _cap(prev) != _cap(cur):
                change_tick, change_label = samples[cur_index].tick, samples[cur_index].label
        lines = net.lines_by_town.get(now.id, {})
        ordered = sorted(((lid, n, p) for lid, (n, p) in lines.items()), key=lambda e: (not e[2], e[1]))
        supply = {c: (s, lim) for c, s, lim in now.supply}
        stations = len(net.stations_by_town.get(now.id, ()))
        passengers = sum(1 for p in lines.values() if p[1])
        drafts.append(dict(
            id=now.id, name=now.name, capacity=now_cap, capacities=now.capacities, first_capacity=first_cap,
            delta=delta, growth=growth, annual_growth=annual, last_change=change_label, last_change_tick=change_tick,
            usage=now.usage, usage_first=first.usage,
            usage_change=None if now.usage is None or first.usage is None else now.usage - first.usage,
            headroom=None if now.usage is None else max(0.0, USAGE_CAP - now.usage),
            noise=now.noise, noise_first=first.noise, pollution=now.pollution, pollution_first=first.pollution,
            development=now.development, stations=stations, lines_all=len(lines), lines_passenger=passengers,
            lines=tuple(TownLine(lid, n, p) for lid, n, p in ordered),
            supply=tuple(CargoSupply(c, names.get(c, str(c)), s, lim) for c, (s, lim) in supply.items()),
            demands_met=sum(1 for s, _ in supply.values() if s > 0), demands_total=len(supply),
            served=stations > 0, reading=_reading(stations > 0, passengers, now.usage), position=positions.get(now.id),
        ))
    sized = sorted((d for d in drafts if d["capacity"] is not None), key=lambda d: (-d["capacity"], d["name"]))
    total = sum(d["capacity"] for d in sized)
    threshold = _quantile([d["capacity"] for d in sized], LARGE_QUANTILE) if len(sized) >= MIN_TOWNS_FOR_QUANTILE else None
    for i, d in enumerate(sized, 1):
        d["rank"] = i
        d["share"] = d["capacity"] / total if total else None
        d["large"] = threshold is not None and d["capacity"] >= threshold
    for d in drafts:
        d.setdefault("rank", None)
        d.setdefault("share", None)
        d.setdefault("large", False)
    drafts.sort(key=lambda d: (d["rank"] is None, d["rank"] or 0, d["name"]))
    return tuple(TownRow(**d) for d in drafts)


def _evolution(samples: tuple[TownSample, ...], span: float | None) -> tuple[EvolutionPoint, ...]:
    if len(samples) < 2:
        return ()
    out: list[EvolutionPoint] = []
    base = None
    for s in _pick(samples, span):
        caps = [c for c in (_cap(p) for p in s.towns) if c is not None]
        total = float(sum(caps))
        base = total if base is None else base
        full = [p for p in s.towns if len(p.capacities) >= 3]
        weighted = _weighted_usage([(c, p.usage) for p in s.towns if (c := _cap(p)) is not None and p.usage is not None])
        out.append(EvolutionPoint(
            s.tick, s.label, total, total - base, float(sum(p.capacities[0] for p in full)),
            float(sum(p.capacities[1] for p in full)), float(sum(p.capacities[2] for p in full)), weighted,
            sum(1 for p in s.towns if p.development),
        ))
    return tuple(out)


def _growth(rows: tuple[TownRow, ...], samples: tuple[TownSample, ...], span: float | None) -> GrowthScreen:
    if len(samples) < MIN_WINDOW_SAMPLES or span is None or span < MIN_WINDOW_YEARS:
        return GrowthScreen(False, 0, (), None, (), 0, 0, ())
    comparable = [r for r in rows if r.delta is not None and r.growth is not None]
    risers = sorted((r for r in comparable if r.delta > 0), key=lambda r: (-r.growth, r.name))
    stalled = sorted((r for r in comparable if r.delta <= 0 and r.capacity is not None), key=lambda r: (-r.capacity, r.name))
    return GrowthScreen(
        True, len(comparable), tuple(r.id for r in risers),
        statistics.median(r.growth for r in comparable) if risers else None,
        tuple(r.id for r in stalled), sum(1 for r in stalled if r.served), sum(1 for r in stalled if not r.served),
        tuple(r.id for r in stalled if r.served and r.large),
    )


def _coverage_screen(rows: tuple[TownRow, ...], net: _Network) -> CoverageScreen:
    sized = [r for r in rows if r.capacity is not None]
    gaps = sorted((r for r in sized if not r.lines_passenger), key=lambda r: (-r.capacity, r.name))
    unserved = [r for r in gaps if not r.served]
    total = sum(r.capacity for r in sized)
    share = (sum(r.capacity for r in unserved) / total if total else None) if unserved else 0.0
    return CoverageScreen(
        bool(net.station_town), tuple(r.id for r in gaps), len(unserved), share,
        tuple(r.id for r in sorted((r for r in sized if r.lines_passenger and r.usage == 0), key=lambda r: -r.capacity)),
        tuple(r.id for r in sized if r.served),
    )


def _usage_gap(rows: tuple[TownRow, ...]) -> UsageGap:
    measured = [r for r in rows if r.capacity is not None and r.usage is not None]
    if len(measured) < MIN_TOWNS_FOR_QUANTILE:
        return UsageGap("too-few-towns-with-usage", (), ())
    low = [r for r in measured if r.large and (r.headroom or 0) > HEADROOM_MARGIN]
    low.sort(key=lambda r: (-(r.capacity * (r.headroom or 0)), r.name))
    return UsageGap(None, tuple(r.id for r in low), tuple(r.capacity * (r.headroom or 0) for r in low))


def _cargo_demand(rows: tuple[TownRow, ...], evidence: TownsEvidence) -> CargoDemandScreen:
    names = dict(evidence.cargo_names)
    with_supply = [r for r in rows if r.supply]
    producers: dict[int, dict[str, float]] = {}
    for out in evidence.outputs:
        p = producers.setdefault(out.cargo, {"count": 0, "produced": 0.0, "unshipped": 0.0, "pu": 0, "uu": 0})
        p["count"] += 1
        if out.produced_year is None:
            p["pu"] += 1
        else:
            p["produced"] += out.produced_year
        if out.produced_year is None or out.shipped_year is None:
            p["uu"] += 1
        else:
            p["unshipped"] += max(0.0, out.produced_year - out.shipped_year)
    per_cargo: dict[int, dict[str, float]] = {}
    for r in with_supply:
        for entry in r.supply:
            c = per_cargo.setdefault(entry.cargo, {"towns": 0, "zero": 0, "supply": 0.0, "limit": 0.0})
            c["towns"] += 1
            c["zero"] += 1 if entry.supply <= 0 else 0
            c["supply"] += entry.supply
            c["limit"] += entry.limit
    ranked = sorted(per_cargo.items(), key=lambda kv: (-(kv[1]["limit"] - kv[1]["supply"]), names.get(kv[0], str(kv[0]))))
    by_cargo = tuple(
        CargoDemand(
            cargo, names.get(cargo, str(cargo)), int(c["towns"]), int(c["zero"]), c["supply"], c["limit"],
            c["supply"] / c["limit"] if c["limit"] else None,
            int(producers.get(cargo, {}).get("count", 0)), producers.get(cargo, {}).get("produced", 0.0),
            producers.get(cargo, {}).get("unshipped", 0.0), int(producers.get(cargo, {}).get("pu", 0)),
            int(producers.get(cargo, {}).get("uu", 0)),
        )
        for cargo, c in ranked
    )
    served = sorted((r for r in with_supply if r.served),
                    key=lambda r: (-sum(max(0.0, e.limit - e.supply) for e in r.supply), r.name))
    towns: list[TownDemand] = []
    for r in served:
        sup = sum(e.supply for e in r.supply)
        lim = sum(e.limit for e in r.supply)
        big = max(r.supply, key=lambda e: e.limit - e.supply)
        towns.append(TownDemand(
            r.id, sup, lim, sup / lim if lim else None, r.demands_met, r.demands_total,
            sum(max(0.0, e.limit - e.supply) for e in r.supply), big.cargo, big.cargo_name,
            max(0.0, big.limit - big.supply),
        ))
    idle = tuple(d.cargo for d in by_cargo if d.supply <= 0 and d.produced_year <= 0 and d.produced_unknown == 0)
    return CargoDemandScreen(
        len(with_supply), sum(1 for r in with_supply if all(e.supply <= 0 for e in r.supply)), by_cargo, tuple(towns),
        idle, tuple(names.get(c, str(c)) for c in idle),
    )


def _hotspots(rows: tuple[TownRow, ...]) -> Hotspots:
    pol = [r for r in rows if r.pollution is not None]
    noi = [r for r in rows if r.noise is not None]

    def rank(items: list[TownRow], value: str) -> tuple[HotspotRank, ...]:
        ordered = sorted(items, key=lambda r: (-getattr(r, value), r.name))
        out = []
        for r in ordered:
            now, first = getattr(r, value), getattr(r, f"{value}_first")
            out.append(HotspotRank(r.id, now, None if first is None else now - first,
                                   now / r.capacity * 100 if r.capacity else None))
        return tuple(out)

    summary = None
    if len(pol) >= MIN_TOWNS_FOR_HOTSPOT_SUMMARY:
        ordered = sorted(pol, key=lambda r: (-r.pollution, r.name))
        median = statistics.median(r.pollution for r in pol)
        worst = max((r for r in pol if r.capacity), key=lambda r: (r.pollution / r.capacity, r.name), default=None)
        top = ordered[0]
        summary = PollutionSummary(
            top.id, top.pollution,
            top.pollution / ordered[1].pollution if median > 0 and ordered[1].pollution > 0 else None,
            top.pollution / median if median > 0 and ordered[1].pollution > 0 else None,
            worst.id if worst is not None and worst is not top else None,
        )
    return Hotspots(rank(pol, "pollution"), rank(noi, "noise"), summary)


def _distance_km(a: TownRow, b: TownRow) -> float | None:
    if a.position is None or b.position is None:
        return None
    return math.hypot(a.position[0] - b.position[0], a.position[1] - b.position[1]) / 1000.0


def _pairs(rows: tuple[TownRow, ...], net: _Network) -> PairScreen:
    pool = [r for r in rows if r.capacity is not None][:PAIR_POOL]
    if len(pool) < 2:
        return PairScreen(tuple(r.id for r in pool), 0, 0, 0, (), False)
    candidates = []
    for i, a in enumerate(pool):
        for b in pool[i + 1:]:
            if frozenset((a.id, b.id)) in net.edges:
                continue
            comp_a, comp_b = net.component.get(a.id), net.component.get(b.id)
            indirect = comp_a is not None and comp_a == comp_b
            candidates.append((1 if indirect else 0, -(a.capacity * b.capacity), a, b,
                               "indirect-shared-network" if indirect else "no-passenger-link"))
    candidates.sort(key=lambda c: (c[0], c[1], c[2].name, c[3].name))
    pairs = tuple(TownPair(a.id, b.id, a.capacity, b.capacity, status, _distance_km(a, b)) for _, _, a, b, status in candidates)
    isolated = sum(1 for c in candidates if c[0] == 0)
    return PairScreen(
        tuple(r.id for r in pool), (len(pool) * (len(pool) - 1)) // 2 - len(candidates), isolated,
        len(candidates) - isolated, pairs, any(p.distance_km is not None for p in pairs),
    )


def _key_observations(rows: tuple[TownRow, ...], span: float | None, samples_count: int) -> tuple[KeyObservation, ...]:
    sized = [r for r in rows if r.capacity is not None]
    if not sized:
        return ()
    out: list[KeyObservation] = []
    unserved = [r for r in sized if not r.served]
    if unserved:
        out.append(KeyObservation("unserved-towns", unserved[0].id, len(unserved), len(sized)))
    low = sorted((r for r in sized if r.large and r.usage is not None and (r.headroom or 0) > HEADROOM_MARGIN),
                 key=lambda r: -(r.capacity * (r.headroom or 0)))
    if low:
        out.append(KeyObservation("usage-gap", low[0].id))
    if span is not None and span >= MIN_WINDOW_YEARS and samples_count >= MIN_WINDOW_SAMPLES:
        stalled = [r for r in sized if r.large and r.served and r.delta is not None and r.delta <= 0]
        if stalled:
            out.append(KeyObservation("stalled-large-served", stalled[0].id, sum(1 for x in sized if (x.delta or 0) > 0),
                                      len(sized), span_years=span))
        growing = [r for r in sized if r.growth is not None and r.growth > 0]
        if growing:
            r = max(growing, key=lambda r: (r.growth, r.name))
            out.append(KeyObservation("fastest-growth", r.id, growth=r.growth, delta=r.delta))
    starved = [r for r in sized if r.served and r.supply and all(e.supply <= 0 for e in r.supply)]
    if starved:
        r = starved[0]
        top = sorted(r.supply, key=lambda e: -e.limit)[:3]
        out.append(KeyObservation("starved-served", r.id, len(starved), len(r.supply),
                                  cargo_names=tuple(e.cargo_name for e in top)))
    return tuple(out)


def _criteria() -> tuple[Criterion, ...]:
    return (
        Criterion("usageCap", USAGE_CAP, "ratio", "Passenger rating is min(1, 2 x usage), so usage above this adds nothing; headroom is the gap to it."),
        Criterion("minWindowYears", MIN_WINDOW_YEARS, "game-year", "Growth and stall screens need at least this supported span."),
        Criterion("minWindowSamples", MIN_WINDOW_SAMPLES, "samples", "Growth and stall screens need at least this many samples."),
        Criterion("largeQuantile", LARGE_QUANTILE, "quantile", "A town is large when its capacity is at or above this quantile of capacity (needs four sized towns)."),
        Criterion("headroomMargin", HEADROOM_MARGIN, "ratio", "Usage gaps at or below this margin are not reported and usage within it counts as at the cap."),
        Criterion("pairPool", PAIR_POOL, "towns", "Passenger pairs are screened among this many largest towns."),
        Criterion("maxEvolutionPoints", MAX_EVOLUTION_POINTS, "samples", "Evolution keeps at most this many representative samples, always the first and latest."),
        Criterion("minTownsForHotspotSummary", MIN_TOWNS_FOR_HOTSPOT_SUMMARY, "towns", "The pollution comparison needs this many towns with a value."),
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def evaluate(evidence: TownsEvidence, *, context: EvaluationContext) -> TownsView:
    clock = context.clock
    samples = evidence.samples
    unavailable: list[Unavailable] = []
    if clock.ambiguous:
        samples = samples[-1:]
        unavailable.append(Unavailable("ambiguous-timeline", "growth and history windows need an unambiguous calendar; only the latest sample is used"))
    measure = clock.elapsed_between_ticks(samples[0].tick, samples[-1].tick)
    span = measure.value
    net = _Network(evidence)
    rows = _rows(evidence, samples, net, span)
    sized = [r for r in rows if r.capacity is not None]
    total = sum(r.capacity for r in sized)
    first_total = sum(r.first_capacity for r in sized if r.first_capacity is not None)
    served = [r for r in sized if r.served]
    pax = [r for r in sized if r.lines_passenger]
    multi = len(samples) > 1
    threshold = _quantile([r.capacity for r in sized], LARGE_QUANTILE) if len(sized) >= MIN_TOWNS_FOR_QUANTILE else None
    summary = TownsSummary(
        towns=len(rows), sized=len(sized), total_capacity=total if sized else None,
        first_total_capacity=first_total if sized else None,
        capacity_change=total - first_total if multi and sized else None,
        growing=sum(1 for r in sized if (r.delta or 0) > 0) if multi and sized else None,
        served=len(served), served_share=sum(r.capacity for r in served) / total if total else None,
        passenger_served=len(pax), passenger_share=sum(r.capacity for r in pax) / total if total else None,
        weighted_usage=_weighted_usage([(r.capacity, r.usage) for r in sized if r.usage is not None]),
        development_active=sum(1 for r in sized if r.development),
        large_threshold=threshold,
        window_samples=len(samples),
        window_first=SampleRef(samples[0].tick, samples[0].label), window_last=SampleRef(samples[-1].tick, samples[-1].label),
        span_years=span, span_days=span * DAYS_PER_YEAR if span is not None else None, span_reason=measure.reason,
    )
    evolution = _evolution(samples, span)
    growth = _growth(rows, samples, span)
    coverage_screen = _coverage_screen(rows, net)
    usage_gap = _usage_gap(rows)
    cargo_demand = _cargo_demand(rows, evidence)
    hotspots = _hotspots(rows)
    pairs = _pairs(rows, net)
    if not rows:
        unavailable.append(Unavailable("no-towns", "the endpoint lists no towns"))
    if rows and not growth.window_sufficient:
        unavailable.append(Unavailable("growth-window-insufficient", f"needs {MIN_WINDOW_SAMPLES} samples spanning {MIN_WINDOW_YEARS} game-year"))
    if rows and not coverage_screen.stations_known:
        unavailable.append(Unavailable("stations-unassigned", "no station is assigned to a town, so coverage cannot be verified"))
    if rows and usage_gap.code:
        unavailable.append(Unavailable(usage_gap.code, "too few towns with capacity and line usage"))
    if rows and not cargo_demand.towns_with_demand:
        unavailable.append(Unavailable("cargo-supply-missing", "towns report no cargoSupply entries"))
    if rows and not hotspots.pollution and not hotspots.noise:
        unavailable.append(Unavailable("pollution-noise-missing", "no pollution or noise values"))
    if rows and len(pairs.pool) < 2:
        unavailable.append(Unavailable("pair-pool-too-small", "fewer than two towns with capacities"))
    coverage = ViewCoverage(
        endpoint=evidence.endpoint, eligible=evidence.eligible, read=evidence.read, used=len(samples),
        hydrated=evidence.hydrated, hydration_limit=0,
        sampled=tuple(SampleRef(p.tick, p.label) for p in evolution),
        limits={"evolutionPoints": MAX_EVOLUTION_POINTS, "pairPool": PAIR_POOL},
        omitted=max(0, evidence.eligible - len(samples)),
        warnings=tuple(str(w) for w in clock.time_basis["warnings"]),
        collection_errors=evidence.collection_errors, unavailable=tuple(unavailable),
    )
    return TownsView(
        summary=summary, rows=rows, evolution=evolution, growth=growth, coverage_screen=coverage_screen,
        usage_gap=usage_gap, cargo_demand=cargo_demand, hotspots=hotspots, pairs=pairs,
        key_observations=_key_observations(rows, span, len(samples)),
        criteria=_criteria(), coverage=coverage,
    )
