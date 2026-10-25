"""Expansion analysis: ranked route candidates, exclusions, proven economics and diagnostics.

Candidates are (producer industry, cargo, consumer) triples where the consumer is an industry that takes
the cargo as an input or a town that demands it. Each is scored with a transparent additive formula,
cross-checked against routes the company already runs and then selected greedily so a shared consumer's
unmet demand is never claimed twice. Everything is derived from the stored samples; distances are
straight-line estimates, rolling annual figures are never summed across samples and unknown values are
unknown, never zero.
"""

from __future__ import annotations

import math
import re
import statistics
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from ..snapshot import Snapshot
from .expansion_evidence import HYDRATION_LIMIT, MAX_MONTHLY_SAMPLES, MAX_QUARTERLY_SAMPLES, ExpansionEvidence
from .models import EvaluationContext, SampleRef, Unavailable, ViewCoverage

TOP_N = 10
PROVEN_MIN_VEHICLES = 3
PERSISTENCE_MIN_SAMPLES = 3
STARVED_USAGE_RATIO = 0.1
SERVED_TOWN_USAGE = 0.2
ELEVATED_INPUT_STOCK = 0.5
RAIL_MIN_KM = 6
MAX_TARGETS_PER_OUTPUT, MAX_INDUSTRY_CANDIDATES_PER_OUTPUT = 5, 3
ALTERNATIVES = 2
WATER_INDUSTRIES = {"oil_platform", "sand_excavator"}
BOOSTER_CARGOS = {"fertilizer", "tools", "machines"}

_LARGEST = "largest_capacity"
_CHEAPEST = "lowest_running_cost_per_capacity"


# ---------------------------------------------------------------------------
# typed result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EntityRef:
    kind: str                 # "industry" | "town"
    id: int | None
    name: str | None          # untrusted display data; None when the sample has no name


@dataclass(frozen=True)
class CargoRef:
    id: int | None
    name: str | None
    key: str                  # resource key, e.g. "coal"; empty when unknown


@dataclass(frozen=True)
class Criterion:
    name: str
    value: float | int | str
    unit: str
    note: str


@dataclass(frozen=True)
class ScoreParts:
    volume: float
    distance: float
    urgency: float
    pull: float
    chain: float
    proven: float


@dataclass(frozen=True)
class Penalty:
    code: str                 # consumer_input_stock_full | consumer_closing | producer_closing
    amount: float
    stock_ratio: float | None = None


@dataclass(frozen=True)
class Flag:
    code: str
    subject: str | None = None     # a line or cargo name where the code names one
    value: float | None = None     # a ratio where the code carries one
    samples: int | None = None


@dataclass(frozen=True)
class CargoProof:
    vehicles: int
    profitable: int
    share: float | None             # None below the minimum vehicle count
    best_carrier: str | None


@dataclass(frozen=True)
class Alternative:
    consumer: EntityRef
    score: float
    distance_km: float | None


@dataclass(frozen=True)
class ExpansionCandidate:
    rank: int
    producer: EntityRef
    consumer: EntityRef
    consumer_kind: str
    cargo: CargoRef
    produced: float
    shipped: float
    unshipped: float
    ratio: float
    out_fill: float | None
    in_fill: float | None
    producer_lines: tuple[str, ...]
    persistence: float | None
    persistence_samples: int
    unmet_recorded: float
    unmet_available: float          # what was left of the consumer's demand when this candidate was chosen
    consumer_capacity: float
    town_supplied: float | None
    volume: float                   # allocated volume: min(unshipped, unmet_available)
    distance_km: float | None
    distance_method: str            # industry-positions | town-anchor-estimate | unknown
    anchor_industries: int | None
    anchor_spread_km: float | None
    parts: ScoreParts
    penalties: tuple[Penalty, ...]
    penalty_total: float
    score: float
    flags: tuple[Flag, ...]
    missing_inputs: tuple[str, ...]
    input_stock_elevated: bool
    water: bool
    proof: CargoProof
    alternatives: tuple[Alternative, ...]


@dataclass(frozen=True)
class ExcludedRoute:
    producer: EntityRef
    consumer: EntityRef
    consumer_kind: str
    cargo: CargoRef
    produced: float
    shipped: float
    unshipped: float
    ratio: float
    lines: tuple[str, ...]


@dataclass(frozen=True)
class DeadEnd:
    producer: EntityRef
    cargo: CargoRef
    produced: float
    shipped: float
    unshipped: float
    ratio: float
    reasons: tuple[str, ...]        # already_linked | input_at_capacity | booster_cargo_without_inputs | no_consumer


@dataclass(frozen=True)
class ProvenGroup:
    cargo: CargoRef
    carrier: str
    vehicles: int
    profitable: int
    median_profit: float
    total_profit: float
    qualifies: bool                 # freight, enough vehicles and a positive median
    candidates_in_ranking: int


@dataclass(frozen=True)
class TownAnchorEstimate:
    town: EntityRef
    x: float
    y: float
    industries_used: int
    spread_km: float
    confidence: str = "low"         # positions are never collected; derived from industry names


@dataclass(frozen=True)
class StarvedSupplier:
    cargo: CargoRef
    producer: EntityRef | None
    distance_km: float | None
    unshipped: float | None


@dataclass(frozen=True)
class StarvedConsumer:
    consumer: EntityRef
    capacity: float
    used: float
    usage_ratio: float
    outputs: tuple[CargoRef, ...]
    suppliers: tuple[StarvedSupplier, ...]


@dataclass(frozen=True)
class TownDemand:
    town: EntityRef
    capacity_sum: float | None
    line_usage: float | None
    stations: int
    unmet_cargos: tuple[CargoRef, ...]
    unknown_supply_cargos: tuple[CargoRef, ...]


@dataclass(frozen=True)
class VehicleModelRef:
    id: int | None
    res: str | None
    name: str | None


@dataclass(frozen=True)
class VehicleFitCandidate:
    candidate_rank: int
    cargo: CargoRef
    carrier: str
    model: VehicleModelRef
    why: tuple[str, ...]            # largest_capacity | lowest_running_cost_per_capacity
    capacity: float
    loads_per_year: float | None
    price: float | None             # None unless the catalog's price unit is verified
    running_costs: float | None     # None unless the catalog's running-cost unit is verified
    year_from: int | None
    year_to: int | None


@dataclass(frozen=True)
class CatalogFit:
    sample: SampleRef | None
    game_year: int | None
    price_verified: bool
    running_costs_verified: bool
    capacity_matched: int
    capacity_compared: int
    candidates: tuple[VehicleFitCandidate, ...]


@dataclass(frozen=True)
class ExpansionView:
    endpoint: SampleRef
    unshipped_ratio_limit: float
    full_stock_ratio: float
    candidates: tuple[ExpansionCandidate, ...]       # the greedy selection, rank order
    candidates_evaluated: int                        # producer-consumer pairs before selection
    outputs_evaluated: int                           # distinct under-shipping (producer, cargo) outputs
    persistence_usable: int                          # selected candidates with enough history samples
    excluded: tuple[ExcludedRoute, ...]
    dead_ends: tuple[DeadEnd, ...]                   # largest unshipped output first
    proven: tuple[ProvenGroup, ...]                  # best median first
    town_anchors: tuple[TownAnchorEstimate, ...]
    starved_consumers: tuple[StarvedConsumer, ...]   # largest input capacity first
    unassessed_consumers: tuple[EntityRef, ...]      # input usage unknown: never reported as starved
    towns: tuple[TownDemand, ...]                    # towns with no or little service, largest first
    catalog: CatalogFit
    criteria: tuple[Criterion, ...]
    coverage: ViewCoverage


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def _name(entity: dict[str, Any], kind: str) -> str:
    return entity.get("name") or f"{kind} #{entity.get('id', 'unknown')}"


def _industry_key(industry: dict[str, Any]) -> str:
    return str(industry.get("type") or "").rsplit("/", 1)[-1].removesuffix(".con")


def _cargo_key(snap: Snapshot, cargo_id: int | None) -> str:
    for cargo in snap.raw.get("cargos") or []:
        if isinstance(cargo, dict) and cargo.get("id") == cargo_id:
            return str(cargo.get("res") or "").rsplit("/", 1)[-1].removesuffix(".cargo")
    return ""


def _cargo(snap: Snapshot, cargo_id: int | None) -> CargoRef:
    return CargoRef(cargo_id, snap.cargo(cargo_id), _cargo_key(snap, cargo_id))


def _is_closing(snap: Snapshot, industry: dict[str, Any]) -> bool:
    return bool(industry.get("closureTimeStamp")) or industry.get("id") in set(snap.problems.get("closingIndustries") or [])


def _distance(a: Any, b: Any) -> float | None:
    from .. import analysis
    dist = analysis._distance(a, b)
    return None if dist is None else dist / 1000


def _num(value: Any) -> float:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def _is_num(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _industry_ref(industry: dict[str, Any]) -> EntityRef:
    return EntityRef("industry", industry.get("id"), industry.get("name"))


def _town_ref(town: dict[str, Any]) -> EntityRef:
    return EntityRef("town", town.get("id"), town.get("name"))


def _distance_points(km: float | None, policy) -> float:
    p = policy
    if km is None or km < p.distance_short_km:
        return 0.0
    if km < p.distance_sweet_from_km:
        return p.weight_distance * (km - p.distance_short_km) / (p.distance_sweet_from_km - p.distance_short_km)
    if km <= p.distance_sweet_to_km:
        return float(p.weight_distance)
    if km <= p.distance_long_km:
        return p.weight_distance * (1 - (1 - p.distance_long_floor) * (km - p.distance_sweet_to_km) / (p.distance_long_km - p.distance_sweet_to_km))
    return p.weight_distance * p.distance_long_floor


# ---------------------------------------------------------------------------
# network cross-check: what does the company already run?
# ---------------------------------------------------------------------------

class _Network:
    """Which industries and towns our lines already call at, and which cargo those lines carry."""

    def __init__(self, snap: Snapshot) -> None:
        industry_by_name = {ind.get("name"): ind["id"] for ind in snap.industries if ind.get("name")}
        group_industry: dict[int, int] = {}
        group_town: dict[int, int] = {}
        for station in snap.stations:
            if station.get("name") in industry_by_name:
                group_industry[station["id"]] = industry_by_name[station["name"]]
            if station.get("town") is not None:
                group_town[station["id"]] = station["town"]
        self.line_cargos: dict[int, set[int]] = {}
        self.line_industries: dict[int, set[int]] = {}
        self.line_towns: dict[int, set[int]] = {}
        self.line_names: dict[int, str] = {}
        self.groups: dict[int, set[int]] = {}
        self.industry_groups = {i: {g for g, v in group_industry.items() if v == i} for i in group_industry.values()}
        self.town_groups = {t: {g for g, v in group_town.items() if v == t} for t in group_town.values()}
        for line in snap.lines:
            lid = line["id"]
            self.line_names[lid] = _name(line, "Line")
            cargos: set[int] = set()
            for vehicle in snap.line_vehicles(line):
                for cfg in vehicle.get("loadConfig") or []:
                    if _num(cfg.get("capacity")) > 0:
                        cargos.add(cfg.get("cargo"))
            self.line_cargos[lid] = cargos
            stops = [s.get("stationGroup") for s in line.get("stops") or []]
            self.groups[lid] = set(stops)
            self.line_industries[lid] = {group_industry[g] for g in stops if g in group_industry}
            self.line_towns[lid] = {group_town[g] for g in stops if g in group_town}

    def _path(self, starts: set[int], ends: set[int], cargo: int) -> list[str]:
        # Shared station groups permit a transfer; this conservatively excludes a
        # possible existing route without asserting that filters permit delivery.
        queue = [(g, []) for g in sorted(starts)]
        visited = set(starts)
        for group, path in queue:
            for lid, groups in self.groups.items():
                if cargo not in self.line_cargos[lid] or group not in groups:
                    continue
                next_path = path + [self.line_names[lid]]
                if groups & ends:
                    return next_path
                for target in sorted(groups - visited):
                    visited.add(target)
                    queue.append((target, next_path))
        return []

    def lines_between(self, a: int, b: int, cargo: int) -> list[str]:
        return self._path(self.industry_groups.get(a, set()), self.industry_groups.get(b, set()), cargo)

    def lines_to_town(self, industry: int, town: int, cargo: int) -> list[str]:
        return self._path(self.industry_groups.get(industry, set()), self.town_groups.get(town, set()), cargo)

    def lines_at(self, industry: int, cargo: int) -> list[str]:
        return sorted(self.line_names[lid] for lid, inds in self.line_industries.items()
                      if industry in inds and cargo in self.line_cargos[lid])


# ---------------------------------------------------------------------------
# evidence: persistence, proven cargo economics, stocks, towns
# ---------------------------------------------------------------------------

def _persistence(samples: tuple[Snapshot, ...], producer: int, cargo: int, ratio_limit: float) -> tuple[float | None, int]:
    """Share of samples in which this output shipped below the limit (needs enough samples)."""
    flags: list[bool] = []
    for snap in samples:
        industry = snap.industries_by_id.get(producer)
        for flow in (industry or {}).get("outputs") or []:
            if flow.get("cargo") == cargo and flow.get("shippedYear") is not None and _num(flow.get("producedYear")) > 0:
                flags.append(_num(flow.get("shippedYear")) / flow["producedYear"] < ratio_limit)
    if len(flags) < PERSISTENCE_MIN_SAMPLES:
        return None, len(flags)
    return sum(flags) / len(flags), len(flags)


def _main_cargo(vehicle: dict[str, Any]) -> int | None:
    configs = [c for c in vehicle.get("loadConfig") or [] if _num(c.get("capacity")) > 0]
    return max(configs, key=lambda c: c["capacity"]).get("cargo") if configs else None


def _proven(snap: Snapshot) -> dict[tuple[int, str], dict[str, Any]]:
    """Per (cargo, carrier): vehicle count, profitable share and median rolling profit, one snapshot only."""
    groups: dict[tuple[int, str], list[float]] = defaultdict(list)
    for vehicle in snap.vehicles:
        cargo = _main_cargo(vehicle)
        profit = vehicle.get("profitYear")
        if cargo is None or not vehicle.get("line") or not isinstance(profit, (int, float)):
            continue
        groups[(cargo, vehicle.get("carrier") or "?")].append(profit)
    return {
        key: {"vehicles": len(values), "profitable": sum(1 for v in values if v > 0),
              "median": statistics.median(values), "total": sum(values)}
        for key, values in groups.items()
    }


def _cargo_proof(proven: dict[tuple[int, str], dict[str, Any]], cargo: int,
                 carriers: tuple[str, ...] | None = None) -> CargoProof:
    rows = [(carrier, row) for (c, carrier), row in proven.items()
            if c == cargo and (carriers is None or carrier in carriers)]
    vehicles = sum(r["vehicles"] for _, r in rows)
    profitable = sum(r["profitable"] for _, r in rows)
    solid = [(carrier, r) for carrier, r in rows if r["vehicles"] >= PROVEN_MIN_VEHICLES and r["median"] > 0]
    best = max(solid, key=lambda x: x[1]["median"])[0] if solid else None
    return CargoProof(vehicles, profitable, profitable / vehicles if vehicles >= PROVEN_MIN_VEHICLES else None, best)


def _stock_fill(snap: Snapshot) -> dict[tuple[int, int, str], float]:
    """Fill ratio per (industry, cargo, side) where side is 'in' or 'out', by cargo overlap with the industry's flows."""
    fills: dict[tuple[int, int, str], float] = {}
    for stock in snap.stocks:
        if stock.get("kind") != "industry":
            continue
        count, capacity = stock.get("count"), stock.get("capacity")
        industry = snap.industries_by_id.get(stock.get("owner"))
        if industry is None or not isinstance(count, (int, float)) or not isinstance(capacity, (int, float)) or capacity <= 0:
            continue
        inputs = {f.get("cargo") for f in industry.get("inputs") or []}
        outputs = {f.get("cargo") for f in industry.get("outputs") or []}
        for cargo in stock.get("cargos") or []:
            side = "in" if cargo in inputs else "out" if cargo in outputs else None
            if side:
                fills[(industry["id"], cargo, side)] = count / capacity
    return fills


def _town_anchors(snap: Snapshot) -> dict[int, tuple[list[float], int, float]]:
    """Town positions are not collected; estimate from industries whose name contains the town name."""
    anchors: dict[int, tuple[list[float], int, float]] = {}
    for town in snap.towns:
        town_name = (town.get("name") or "").strip()
        if not town_name:
            continue
        pattern = re.compile(rf"(?<!\w){re.escape(town_name)}(?!\w)", re.IGNORECASE)
        points = [i["position"][:2] for i in snap.industries
                  if pattern.search(i.get("name") or "") and isinstance(i.get("position"), list) and len(i["position"]) >= 2]
        if points:
            cx = sum(p[0] for p in points) / len(points)
            cy = sum(p[1] for p in points) / len(points)
            spread = max(math.hypot(p[0] - cx, p[1] - cy) for p in points) / 1000
            anchors[town["id"]] = ([cx, cy], len(points), spread)
    return anchors


# ---------------------------------------------------------------------------
# candidates
# ---------------------------------------------------------------------------

def _outputs_useful(snap: Snapshot, consumer: dict[str, Any], consuming: dict[int, list[dict[str, Any]]],
                    town_cargos: set[int]) -> float:
    best = 0.0
    for flow in consumer.get("outputs") or []:
        cargo = flow.get("cargo")
        if any(i["id"] != consumer["id"] and not _is_closing(snap, i) for i in consuming.get(cargo, [])):
            return 1.0
        if cargo in town_cargos:
            best = 0.6
    return best


def _other_inputs_missing(snap: Snapshot, consumer: dict[str, Any], cargo: int) -> list[str]:
    """Other mandatory inputs with no recorded delivery. Food Factory takes fish OR meat."""
    inputs = consumer.get("inputs") or []
    alternates = {f.get("cargo") for f in inputs if _industry_key(consumer) == "food_factory"
                  and _cargo_key(snap, f.get("cargo")) in {"fish", "meat"}}
    if cargo in alternates:
        return [snap.cargo(f.get("cargo")) or "?" for f in inputs
                if f.get("cargo") not in alternates and not _num(f.get("deliveredYear")) and not _num(f.get("consumedYear"))]
    out = []
    for flow in inputs:
        other = flow.get("cargo")
        if other == cargo or _num(flow.get("deliveredYear")) or _num(flow.get("consumedYear")):
            continue
        if other in alternates and any(_num(f.get("deliveredYear")) or _num(f.get("consumedYear"))
                                       for f in inputs if f.get("cargo") in alternates):
            continue
        out.append(snap.cargo(other) or "?")
    return sorted(set(out))


def _unmet_input(consumer: dict[str, Any], cargo: int) -> tuple[float, float]:
    capacity = used = 0.0
    for flow in consumer.get("inputs") or []:
        if flow.get("cargo") == cargo:
            if any(flow.get(k) is None for k in ("maxConsumptionYear", "deliveredYear", "consumedYear")):
                return 0.0, 0.0  # unknown demand cannot justify a route
            capacity += _num(flow.get("maxConsumptionYear"))
            used += max(_num(flow.get("deliveredYear")), _num(flow.get("consumedYear")))
    return max(0.0, capacity - used), capacity


class _Scoring:
    """The latest sample's derived tables shared by candidate generation and scoring."""

    def __init__(self, evidence: ExpansionEvidence, context: EvaluationContext) -> None:
        latest = evidence.endpoint
        self.snap = latest
        self.thresholds = context.thresholds
        self.policy = context.policies["expansion"]
        self.network = _Network(latest)
        self.fills = _stock_fill(latest)
        self.proven = _proven(latest)
        self.anchors = _town_anchors(latest)
        self.samples = evidence.samples
        self.consuming: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for ind in latest.industries:
            for flow in ind.get("inputs") or []:
                self.consuming[flow.get("cargo")].append(ind)
        self.town_cargos = {c["cargo"] for t in latest.towns for c in t.get("cargoSupply") or []
                            if isinstance(c, dict) and _num(c.get("limit")) > 0}


def _candidates(ctx: _Scoring) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (candidates, excluded-as-already-served, producers with unshipped output and no viable target)."""
    snap, limit = ctx.snap, ctx.thresholds.unshipped_ratio
    candidates: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    dead_ends: list[dict[str, Any]] = []
    for producer in sorted(snap.industries, key=lambda i: i["id"]):
        for flow in producer.get("outputs") or []:
            if flow.get("producedYear") is None or flow.get("shippedYear") is None:
                continue
            produced = _num(flow.get("producedYear"))
            if produced <= 0:
                continue
            shipped = _num(flow.get("shippedYear"))
            ratio = shipped / produced
            if ratio >= limit:
                continue
            cargo = flow["cargo"]
            base = {"producer": producer, "cargo": cargo, "produced": produced, "shipped": shipped,
                    "unshipped": produced - shipped, "ratio": ratio,
                    "outFill": ctx.fills.get((producer["id"], cargo, "out")),
                    "producerLines": ctx.network.lines_at(producer["id"], cargo)}
            base["persistence"], base["persistenceN"] = _persistence(ctx.samples, producer["id"], cargo, limit)
            found = 0
            reasons: set[str] = set()
            targets = []
            for consumer in ctx.consuming.get(cargo, []):
                if consumer["id"] == producer["id"]:
                    continue
                unmet, capacity = _unmet_input(consumer, cargo)
                distance = _distance(producer.get("position"), consumer.get("position"))
                targets.append((distance is None, distance or 0.0, consumer["id"], consumer, unmet, capacity))
            targets.sort(key=lambda t: t[:3])
            for _, _, _, consumer, unmet, capacity in targets[:MAX_TARGETS_PER_OUTPUT]:
                direct = ctx.network.lines_between(producer["id"], consumer["id"], cargo)
                if direct:
                    excluded.append({**base, "consumer": consumer["name"], "consumerRef": _industry_ref(consumer),
                                     "lines": direct, "kind": "industry"})
                    reasons.add("already_linked")
                    continue
                if unmet <= 0:
                    reasons.add("input_at_capacity")
                    continue
                candidates.append({**base, "type": "industry", "consumer": consumer, "unmet": unmet,
                                   "consumerCapacity": capacity,
                                   "distance": _distance(producer.get("position"), consumer.get("position")),
                                   "distanceMethod": "industry-positions", "anchor": None,
                                   "inFill": ctx.fills.get((consumer["id"], cargo, "in"))})
                found += 1
                if found >= MAX_INDUSTRY_CANDIDATES_PER_OUTPUT:
                    break
            for town in snap.towns:
                supply = next((c for c in town.get("cargoSupply") or [] if isinstance(c, dict) and c.get("cargo") == cargo), None)
                if not supply or supply.get("supply") is None or _num(supply.get("limit")) <= 0:
                    continue
                unmet = _num(supply["limit"]) - _num(supply.get("supply"))
                if unmet <= 0:
                    continue
                anchor = ctx.anchors.get(town["id"])
                distance = _distance(producer.get("position"), anchor[0]) if anchor else None
                direct = ctx.network.lines_to_town(producer["id"], town["id"], cargo)
                if direct:
                    excluded.append({**base, "consumer": _name(town, "Town"), "consumerRef": _town_ref(town),
                                     "lines": direct, "kind": "town"})
                    continue
                candidates.append({**base, "type": "town", "consumer": town, "unmet": unmet,
                                   "consumerCapacity": _num(supply["limit"]),
                                   "distance": distance,
                                   "distanceMethod": "town-anchor-estimate" if anchor else "unknown", "anchor": anchor,
                                   "inFill": None})
                found += 1
            if not found:
                booster = _cargo_key(snap, cargo) in BOOSTER_CARGOS
                dead_ends.append({**base, "why": tuple(sorted(reasons)) or (
                    ("booster_cargo_without_inputs",) if booster else ("no_consumer",))})
    return candidates, excluded, dead_ends


def _score(ctx: _Scoring, cand: dict[str, Any], remaining: dict[tuple[int, int], float]) -> dict[str, Any]:
    snap, policy = ctx.snap, ctx.policy
    producer, consumer, cargo = cand["producer"], cand["consumer"], cand["cargo"]
    unmet = remaining.get((consumer["id"], cargo), cand["unmet"])
    volume = max(0.0, min(cand["unshipped"], unmet))
    parts: dict[str, float] = {}
    parts["volume"] = policy.weight_volume * min(1.0, volume / policy.volume_reference)
    parts["distance"] = _distance_points(cand["distance"], policy)
    waiting = cand["outFill"]
    base_urgency = (0.5 * (1 - cand["ratio"]) + 0.5 * waiting) if waiting is not None else 0.5 * (1 - cand["ratio"]) * 0.5
    persistence = cand["persistence"]
    if persistence is not None:
        base_urgency *= 0.5 + 0.5 * persistence
    parts["urgency"] = policy.weight_urgency * base_urgency
    flags: list[Flag] = []
    penalties: list[Penalty] = []
    missing: list[str] = []
    if cand["type"] == "industry":
        capacity = cand["consumerCapacity"]
        parts["pull"] = policy.weight_pull * (unmet / capacity if capacity else 0.0)
        missing = _other_inputs_missing(snap, consumer, cargo)
        useful = _outputs_useful(snap, consumer, ctx.consuming, ctx.town_cargos)
        parts["chain"] = policy.weight_chain * useful * (0.5 if missing else 1.0)
        if missing:
            flags.append(Flag("consumer_lacks_inputs", subject=", ".join(missing)))
        if cand["inFill"] is not None and cand["inFill"] >= ctx.thresholds.full_stock_ratio:
            penalties.append(Penalty("consumer_input_stock_full", policy.full_input_penalty, cand["inFill"]))
        if _is_closing(snap, consumer):
            penalties.append(Penalty("consumer_closing", policy.closing_penalty))
    else:
        parts["pull"] = policy.weight_pull * (unmet / cand["consumerCapacity"] if cand["consumerCapacity"] else 0.0)
        parts["chain"] = policy.weight_chain / 2
    if _is_closing(snap, producer):
        penalties.append(Penalty("producer_closing", policy.closing_penalty))
    water = _industry_key(producer) in WATER_INDUSTRIES
    proof = _cargo_proof(ctx.proven, cargo, ("WATER",) if water else None)
    parts["proven"] = policy.weight_proven * proof.share if proof.share is not None else 0.0
    if cand["distance"] is None:
        flags.append(Flag("distance_unknown"))
    elif cand["type"] == "town":
        flags.append(Flag("town_distance_estimate"))
    if cand["producerLines"]:
        flags.append(Flag("producer_already_served", subject=cand["producerLines"][0]))
    if waiting is not None and waiting >= ctx.thresholds.full_stock_ratio:
        flags.append(Flag("output_stock_full", value=waiting))
    if water:
        flags.append(Flag("water_producer"))
    if persistence is None:
        flags.append(Flag("persistence_unavailable", samples=cand["persistenceN"]))
    else:
        flags.append(Flag("persistence_underserved", value=persistence, samples=cand["persistenceN"]))
    penalty = sum(p.amount for p in penalties)
    total = max(0.0, sum(parts.values()) - penalty)
    return {**cand, "unmetAvailable": unmet, "volume": volume, "parts": parts, "penalties": tuple(penalties),
            "penaltyTotal": penalty, "score": total, "flags": tuple(flags), "missingInputs": tuple(missing),
            "water": water, "proof": proof}


def _rank(ctx: _Scoring, candidates: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Greedy selection: best candidate first, its volume is deducted from the consumer, the rest are re-scored.

    One row per (producer, cargo): a producer is not recommended twice for the same cargo.
    """
    remaining: dict[tuple[int, int], float] = {}
    pool = list(candidates)
    picked: list[dict[str, Any]] = []
    while pool and len(picked) < limit:
        scored = [_score(ctx, c, remaining) for c in pool]
        scored.sort(key=lambda c: (-round(c["score"], 6), c["producer"]["id"], c["cargo"], c["consumer"]["id"]))
        best = scored[0]
        if best["score"] <= 0 or best["volume"] <= 0:
            break
        best["alternatives"] = tuple(
            Alternative(_consumer_ref(c), c["score"], c["distance"])
            for c in scored[1:]
            if c["producer"]["id"] == best["producer"]["id"] and c["cargo"] == best["cargo"])[:ALTERNATIVES]
        picked.append(best)
        key = (best["consumer"]["id"], best["cargo"])
        remaining[key] = max(0.0, remaining.get(key, best["unmet"]) - best["volume"])
        pool = [c for c in pool if not (c["producer"]["id"] == best["producer"]["id"] and c["cargo"] == best["cargo"])]
    return picked


def _consumer_ref(cand: dict[str, Any]) -> EntityRef:
    return _town_ref(cand["consumer"]) if cand["type"] == "town" else _industry_ref(cand["consumer"])


# ---------------------------------------------------------------------------
# vehicle fit
# ---------------------------------------------------------------------------

def _available(model: dict[str, Any], year: int | None) -> bool:
    if model.get("available") is False:
        return False
    start, end = model.get("yearFrom"), model.get("yearTo")
    if year is None:
        return True
    return (not start or start <= year) and (not end or year < end)


def _capacity_for(model: dict[str, Any], cargo: int) -> float:
    return sum(_num(c.get("capacity")) for c in model.get("capacity") or [] if c.get("cargo") == cargo)


def _capacity_check(latest: Snapshot, catalog_snap: Snapshot | None) -> tuple[int, int]:
    """Compare recorded capacity of single-model fleet vehicles with the catalog entry: (matching, compared)."""
    if catalog_snap is None:
        return 0, 0
    by_res = {m.get("res"): m for m in catalog_snap.catalog if m.get("res")}
    matched = compared = 0
    for vehicle in latest.vehicles:
        models = vehicle.get("models") or []
        cargo = _main_cargo(vehicle)
        if len(models) != 1 or cargo is None:
            continue
        model = by_res.get(latest.models.get(models[0], {}).get("res"))
        if not model:
            continue
        config = next(c for c in vehicle["loadConfig"] if c.get("cargo") == cargo)
        compared += 1
        matched += _capacity_for(model, cargo) == config.get("capacity")
    return matched, compared


def _vehicle_fit(snap: Snapshot, catalog_snap: Snapshot, year: int | None, rank: int,
                 cand: dict[str, Any]) -> list[VehicleFitCandidate]:
    cargo = cand["cargo"]
    carriers: list[str]
    if cand["water"]:
        carriers = ["WATER"]
    else:
        carriers = []
        best = cand["proof"].best_carrier
        if best:
            carriers.append(best)
        carriers.append("ROAD")
        if (cand["distance"] or 0) >= RAIL_MIN_KM:
            carriers.append("RAIL")
    units = catalog_snap.meta.get("verifiedUnits") or {}
    price_ok = units.get("price") == "currency"
    running_ok = units.get("runningCosts") == "currency/year"
    cargo_ref = _cargo(snap, cargo)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for carrier in carriers:
        if carrier in seen:
            continue
        seen.add(carrier)
        models = [m for m in catalog_snap.catalog if m.get("carrier") == carrier and _available(m, year)
                  and _capacity_for(m, cargo) > 0]
        if not models:
            continue
        biggest = max(models, key=lambda m: (_capacity_for(m, cargo), str(m.get("name"))))
        priced = [m for m in models if _num(m.get("runningCosts")) > 0] if running_ok else []
        cheapest = min(priced, key=lambda m: (_num(m["runningCosts"]) / _capacity_for(m, cargo), str(m.get("name")))) if priced else None
        for tag, model in ((_LARGEST, biggest), (_CHEAPEST, cheapest)):
            if model is None:
                continue
            if rows and rows[-1]["carrier"] == carrier and rows[-1]["model"] is model:
                rows[-1]["why"].append(tag)
                continue
            rows.append({"carrier": carrier, "model": model, "why": [tag]})
    out = []
    for row in rows:
        m = row["model"]
        capacity = _capacity_for(m, cargo)
        out.append(VehicleFitCandidate(
            rank, cargo_ref, row["carrier"], VehicleModelRef(m.get("id"), m.get("res"), m.get("name")),
            tuple(row["why"]), capacity, cand["volume"] / capacity if capacity else None,
            m.get("price") if price_ok else None, m.get("runningCosts") if running_ok else None,
            m.get("yearFrom"), m.get("yearTo")))
    return out


# ---------------------------------------------------------------------------
# diagnostics: starved consumers and towns with little service
# ---------------------------------------------------------------------------

def _usage_known(flow: dict[str, Any]) -> bool:
    return flow.get("maxConsumptionYear") is not None and not (
        flow.get("deliveredYear") is None and flow.get("consumedYear") is None)


def _starved(snap: Snapshot) -> tuple[list[StarvedConsumer], list[EntityRef]]:
    producers: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for ind in snap.industries:
        for flow in ind.get("outputs") or []:
            if _num(flow.get("producedYear")) > 0 and not _is_closing(snap, ind):
                producers[flow["cargo"]].append({"ind": ind, "flow": flow})
    rows: list[StarvedConsumer] = []
    unassessed: list[EntityRef] = []
    for consumer in snap.industries:
        inputs = consumer.get("inputs") or []
        if _is_closing(snap, consumer):
            continue
        if inputs and not all(_usage_known(f) for f in inputs):
            unassessed.append(_industry_ref(consumer))
            continue
        capacity = sum(_num(f.get("maxConsumptionYear")) for f in inputs)
        used = sum(max(_num(f.get("deliveredYear")), _num(f.get("consumedYear"))) for f in inputs)
        if capacity <= 0 or used / capacity >= STARVED_USAGE_RATIO:
            continue
        suppliers = []
        for flow in inputs:
            cargo = flow["cargo"]
            options = [(_distance(consumer.get("position"), p["ind"].get("position")), p)
                       for p in producers.get(cargo, []) if p["ind"]["id"] != consumer["id"]]
            options = [o for o in options if o[0] is not None]
            if options:
                dist, best = min(options, key=lambda o: (o[0], o[1]["ind"]["id"]))
                gone = max(0.0, _num(best["flow"].get("producedYear")) - _num(best["flow"].get("shippedYear")))
                suppliers.append(StarvedSupplier(_cargo(snap, cargo), _industry_ref(best["ind"]), dist, gone))
            else:
                suppliers.append(StarvedSupplier(_cargo(snap, cargo), None, None, None))
        outputs = tuple(_cargo(snap, f.get("cargo")) for f in consumer.get("outputs") or [])
        rows.append(StarvedConsumer(_industry_ref(consumer), capacity, used, used / capacity, outputs, tuple(suppliers)))
    rows.sort(key=lambda r: (-r.capacity, _name({"name": r.consumer.name, "id": r.consumer.id}, "Industry"), r.consumer.id or 0))
    return rows, unassessed


def _town_demand(snap: Snapshot) -> list[TownDemand]:
    station_towns: dict[int, int] = defaultdict(int)
    for station in snap.stations:
        if station.get("town") is not None:
            station_towns[station["town"]] += 1
    rows: list[TownDemand] = []
    for town in snap.towns:
        usage = town.get("lineUsage")
        stations = station_towns.get(town["id"], 0)
        if stations and isinstance(usage, (int, float)) and usage >= SERVED_TOWN_USAGE:
            continue
        unmet: list[CargoRef] = []
        unknown: list[CargoRef] = []
        for c in town.get("cargoSupply") or []:
            if not isinstance(c, dict):
                continue
            if c.get("supply") is None:
                if _num(c.get("limit")) > 0:
                    unknown.append(_cargo(snap, c.get("cargo")))
            elif _num(c.get("limit")) - _num(c.get("supply")) > 0:
                unmet.append(_cargo(snap, c.get("cargo")))
        def key(c):
            return c.name or "?"
        rows.append(TownDemand(_town_ref(town), sum(town.get("capacities") or []) or None,
                               usage if _is_num(usage) else None, stations,
                               tuple(sorted(unmet, key=key)), tuple(sorted(unknown, key=key))))
    rows.sort(key=lambda r: (-(r.capacity_sum or 0), _name({"name": r.town.name, "id": r.town.id}, "Town"), r.town.id or 0))
    return rows


# ---------------------------------------------------------------------------
# evaluation
# ---------------------------------------------------------------------------

def _candidate(rank: int, c: dict[str, Any], snap: Snapshot) -> ExpansionCandidate:
    anchor = c["anchor"]
    town = c["type"] == "town"
    parts = c["parts"]
    fill = c["inFill"]
    elevated = (c["type"] == "industry" and fill is not None and fill >= ELEVATED_INPUT_STOCK
                and not any(p.code == "consumer_input_stock_full" for p in c["penalties"]))
    return ExpansionCandidate(
        rank, _industry_ref(c["producer"]), _consumer_ref(c), c["type"], _cargo(snap, c["cargo"]),
        c["produced"], c["shipped"], c["unshipped"], c["ratio"], c["outFill"], fill, tuple(c["producerLines"]),
        c["persistence"], c["persistenceN"], c["unmet"], c["unmetAvailable"], c["consumerCapacity"],
        c["consumerCapacity"] - c["unmet"] if town else None, c["volume"], c["distance"], c["distanceMethod"],
        anchor[1] if anchor else None, anchor[2] if anchor else None,
        ScoreParts(parts["volume"], parts["distance"], parts["urgency"], parts["pull"], parts["chain"], parts["proven"]),
        c["penalties"], c["penaltyTotal"], c["score"], c["flags"], c["missingInputs"], elevated, c["water"], c["proof"],
        tuple(c["alternatives"]))


def _criteria(unshipped_limit: float, full_stock: float) -> tuple[Criterion, ...]:
    return (
        Criterion("unshippedRatio", unshipped_limit, "ratio", "outputs shipping below this share of production are considered"),
        Criterion("fullStockRatio", full_stock, "ratio", "stock fill treated as full for penalties and flags"),
        Criterion("topN", TOP_N, "candidates", "greedy selection length; selection deducts shared consumer demand"),
        Criterion("alternatives", ALTERNATIVES, "consumers", "other consumers listed per selected candidate"),
        Criterion("targetsPerOutput", MAX_TARGETS_PER_OUTPUT, "consumers", "nearest consumers examined per output"),
        Criterion("industryCandidatesPerOutput", MAX_INDUSTRY_CANDIDATES_PER_OUTPUT, "consumers", "industry candidates kept per output"),
        Criterion("provenMinVehicles", PROVEN_MIN_VEHICLES, "vehicles", "minimum vehicles before a cargo counts as proven"),
        Criterion("persistenceMinSamples", PERSISTENCE_MIN_SAMPLES, "samples", "minimum usable samples before persistence scales urgency"),
        Criterion("starvedUsageRatio", STARVED_USAGE_RATIO, "ratio", "input usage below this share marks a starved consumer"),
        Criterion("servedTownLineUsage", SERVED_TOWN_USAGE, "ratio", "towns with a station and line usage at or above this are well served"),
        Criterion("elevatedInputStockRatio", ELEVATED_INPUT_STOCK, "ratio", "consumer input stock noted as a risk below the full threshold"),
        Criterion("railMinKm", RAIL_MIN_KM, "km", "distance from which rail models are also listed"),
    )


def evaluate(evidence: ExpansionEvidence, *, context: EvaluationContext) -> ExpansionView:
    snap = evidence.endpoint
    scoring = _Scoring(evidence, context)
    candidates, excluded, dead_ends = _candidates(scoring)
    picked = _rank(scoring, candidates, TOP_N)

    year = (snap.date or {}).get("year", snap.meta.get("year"))
    catalog_snap = evidence.catalog
    fit: list[VehicleFitCandidate] = []
    if catalog_snap is not None:
        for i, c in enumerate(picked):
            fit.extend(_vehicle_fit(snap, catalog_snap, year, i + 1, c))
        units = catalog_snap.meta.get("verifiedUnits") or {}
        matched, compared = _capacity_check(snap, catalog_snap)
        catalog = CatalogFit(SampleRef(catalog_snap.game_time, catalog_snap.date_label), year,
                             units.get("price") == "currency", units.get("runningCosts") == "currency/year",
                             matched, compared, tuple(fit))
    else:
        catalog = CatalogFit(None, year, False, False, 0, 0, ())

    in_ranking: dict[int, int] = defaultdict(int)
    for c in picked:
        in_ranking[c["cargo"]] += 1
    proven_rows = sorted(scoring.proven.items(), key=lambda kv: (-kv[1]["median"], str(snap.cargo(kv[0][0])), kv[0][1]))
    proven = tuple(ProvenGroup(_cargo(snap, cargo), carrier, v["vehicles"], v["profitable"], v["median"], v["total"],
                               cargo != 0 and v["vehicles"] >= PROVEN_MIN_VEHICLES and v["median"] > 0,
                               in_ranking.get(cargo, 0))
                   for (cargo, carrier), v in proven_rows)

    seen: set[tuple[Any, Any, Any]] = set()
    excluded_out: list[ExcludedRoute] = []
    for e in excluded:
        key = (e["producer"]["id"], e["cargo"], e["consumer"])
        if key in seen:
            continue
        seen.add(key)
        excluded_out.append(ExcludedRoute(_industry_ref(e["producer"]), e["consumerRef"], e["kind"], _cargo(snap, e["cargo"]),
                                          e["produced"], e["shipped"], e["unshipped"], e["ratio"], tuple(e["lines"])))
    dead = sorted(dead_ends, key=lambda d: (-d["unshipped"], d["producer"]["id"], d["cargo"]))
    dead_out = tuple(DeadEnd(_industry_ref(d["producer"]), _cargo(snap, d["cargo"]), d["produced"], d["shipped"],
                             d["unshipped"], d["ratio"], d["why"]) for d in dead)

    anchors = tuple(TownAnchorEstimate(_town_ref(t), scoring.anchors[t["id"]][0][0], scoring.anchors[t["id"]][0][1],
                                       scoring.anchors[t["id"]][1], scoring.anchors[t["id"]][2])
                    for t in snap.towns if t["id"] in scoring.anchors)
    starved, unassessed = _starved(snap)

    unavailable: list[Unavailable] = []
    if catalog_snap is None:
        unavailable.append(Unavailable("catalog_missing", "no catalog snapshot at or before the endpoint"))
    if unassessed:
        unavailable.append(Unavailable("starved_usage_unknown", f"{len(unassessed)} industries lack recorded input usage"))
    if evidence.missing_ticks:
        unavailable.append(Unavailable("sample_missing", f"{len(evidence.missing_ticks)} selected samples could not be read"))
    sampled = tuple(SampleRef(s.game_time, s.date_label) for s in evidence.samples)
    coverage = ViewCoverage(
        endpoint=SampleRef(snap.game_time, snap.date_label), eligible=evidence.eligible, read=evidence.read,
        used=len(evidence.samples), hydrated=evidence.hydrated, hydration_limit=HYDRATION_LIMIT, sampled=sampled,
        limits={"topN": TOP_N, "maxMonthlySamples": MAX_MONTHLY_SAMPLES, "maxQuarterlySamples": MAX_QUARTERLY_SAMPLES,
                "alternatives": ALTERNATIVES},
        omitted=max(0, evidence.eligible - len(evidence.samples)),
        collection_errors=tuple(dict.fromkeys(str(e) for e in snap.errors)), unavailable=tuple(unavailable))
    return ExpansionView(
        endpoint=coverage.endpoint, unshipped_ratio_limit=context.thresholds.unshipped_ratio,
        full_stock_ratio=context.thresholds.full_stock_ratio,
        candidates=tuple(_candidate(i + 1, c, snap) for i, c in enumerate(picked)),
        candidates_evaluated=len(candidates), outputs_evaluated=len({(c["producer"]["id"], c["cargo"]) for c in candidates}),
        persistence_usable=sum(1 for c in picked if c["persistence"] is not None),
        excluded=tuple(excluded_out), dead_ends=dead_out, proven=proven, town_anchors=anchors,
        starved_consumers=tuple(starved), unassessed_consumers=tuple(unassessed), towns=tuple(_town_demand(snap)),
        catalog=catalog, criteria=_criteria(context.thresholds.unshipped_ratio, context.thresholds.full_stock_ratio),
        coverage=coverage)
