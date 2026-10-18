"""Expansion opportunities report: ranked, evidence-backed candidates for new or extended routes.

Candidates are (producer industry, cargo, consumer) triples where the consumer is either an
industry that takes the cargo as an input or a town that demands it. Each candidate is scored
with a transparent additive formula (components are printed with the ranking) and cross-checked
against routes the company already runs, so pairs that already exist are listed as excluded
rather than recommended.

Everything here is derived from stored snapshots; nothing is measured in the game beyond what
the bridge collects. Distances are straight-line estimates, rolling annual figures are never
summed across snapshots, and missing values are treated as unknown.
"""

from __future__ import annotations

import math
import re
import statistics
from collections import defaultdict
from typing import Any

from . import analysis
from .reports import (
    Chart,
    Heading,
    Note,
    Paragraph,
    ReportDocument,
    Table,
    _base_header,
    _fmt_pct,
    _recent_current,
)
from .snapshot import Snapshot
from .store import Store

TOP_N = 10

# Score budget (sums to 100 before penalties).
W_VOLUME, W_DISTANCE, W_URGENCY, W_PULL, W_CHAIN, W_PROVEN = 30, 20, 20, 10, 10, 10
VOLUME_REF = 150          # items per year (as recorded) that earns the full volume budget
SHORT_KM, SWEET_FROM_KM, SWEET_TO_KM, LONG_KM, LONG_FLOOR = 0.5, 3.0, 10.0, 20.0, 0.4
PROVEN_MIN_VEHICLES = 3
PERSISTENCE_MIN_SAMPLES = 3
FULL_INPUT_STOCK = 0.9
PENALTY_CLOSING = 30
PENALTY_FULL_INPUT = 15
WATER_INDUSTRIES = {"oil_platform", "sand_excavator"}
BOOSTER_CARGOS = {"fertilizer", "tools", "machines"}
MAX_MONTHLY_SAMPLES, MAX_QUARTERLY_SAMPLES = 12, 8

DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


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


def _is_closing(snap: Snapshot, industry: dict[str, Any]) -> bool:
    return bool(industry.get("closureTimeStamp")) or industry.get("id") in set(snap.problems.get("closingIndustries") or [])


def _km(a: Any, b: Any) -> float | None:
    dist = analysis._distance(a, b)
    return None if dist is None else dist / 1000


def _num(value: Any) -> float:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def _f(value: float | None, digits: int = 1) -> str:
    return "-" if value is None else f"{value:,.{digits}f}"


def _short(text: str, limit: int = 34) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _distance_points(km: float | None) -> float:
    if km is None or km < SHORT_KM:
        return 0.0
    if km < SWEET_FROM_KM:
        return W_DISTANCE * (km - SHORT_KM) / (SWEET_FROM_KM - SHORT_KM)
    if km <= SWEET_TO_KM:
        return float(W_DISTANCE)
    if km <= LONG_KM:
        return W_DISTANCE * (1 - (1 - LONG_FLOOR) * (km - SWEET_TO_KM) / (LONG_KM - SWEET_TO_KM))
    return W_DISTANCE * LONG_FLOOR


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
# history sampling (graceful with months or years of snapshots)
# ---------------------------------------------------------------------------

def _sample_times(store: Store, latest: Snapshot) -> list[int]:
    """Latest snapshot per game month for the newest 12 months, then per quarter for older history."""
    rows = [r for r in store.company_history(limit=1_000_000) if r["game_time"] <= latest.game_time]
    keyed: list[tuple[int, int]] = []
    for row in rows:
        match = DATE_RE.match(str(row.get("date_label") or ""))
        if match:
            keyed.append((int(match[1]) * 12 + int(match[2]) - 1, row["game_time"]))
    if not keyed:
        return [latest.game_time]
    newest = max(month for month, _ in keyed)
    monthly: dict[int, int] = {}
    quarterly: dict[int, int] = {}
    for month, game_time in sorted(keyed, key=lambda x: x[1]):
        if newest - month < 12:
            monthly[month] = game_time
        else:
            quarterly[month // 3] = game_time
    times = [t for _, t in sorted(monthly.items())][-MAX_MONTHLY_SAMPLES:]
    times = [t for _, t in sorted(quarterly.items())][-MAX_QUARTERLY_SAMPLES:] + times
    return sorted(set(times) | {latest.game_time})


def _history(store: Store, latest: Snapshot) -> list[Snapshot]:
    out: list[Snapshot] = []
    for game_time in _sample_times(store, latest):
        snap = latest if game_time == latest.game_time else store.snapshot_at_or_before(game_time)
        if snap is not None:
            out.append(snap)
    return out


def _persistence(samples: list[Snapshot], producer: int, cargo: int, ratio_limit: float) -> tuple[float | None, int]:
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


# ---------------------------------------------------------------------------
# evidence: proven cargo economics, stocks, towns
# ---------------------------------------------------------------------------

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
                 carriers: tuple[str, ...] | None = None) -> dict[str, Any]:
    rows = [(carrier, row) for (c, carrier), row in proven.items()
            if c == cargo and (carriers is None or carrier in carriers)]
    vehicles = sum(r["vehicles"] for _, r in rows)
    profitable = sum(r["profitable"] for _, r in rows)
    solid = [(carrier, r) for carrier, r in rows if r["vehicles"] >= PROVEN_MIN_VEHICLES and r["median"] > 0]
    best = max(solid, key=lambda x: x[1]["median"])[0] if solid else None
    return {"vehicles": vehicles, "profitable": profitable,
            "share": profitable / vehicles if vehicles >= PROVEN_MIN_VEHICLES else None,
            "bestCarrier": best}


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
    """Town positions are not collected; estimate from industries whose name contains the town name.

    Returns town id -> (position, industries used, spread km). Low confidence by construction.
    """
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


class _Context:
    def __init__(self, store: Store, latest: Snapshot) -> None:
        self.snap = latest
        self.thresholds = analysis.Thresholds()
        self.network = _Network(latest)
        self.fills = _stock_fill(latest)
        self.proven = _proven(latest)
        self.anchors = _town_anchors(latest)
        self.samples = _history(store, latest)
        self.consuming: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for ind in latest.industries:
            for flow in ind.get("inputs") or []:
                self.consuming[flow.get("cargo")].append(ind)
        self.town_cargos = {c["cargo"] for t in latest.towns for c in t.get("cargoSupply") or []
                            if isinstance(c, dict) and _num(c.get("limit")) > 0}


def _candidates(ctx: _Context) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
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
                distance = _km(producer.get("position"), consumer.get("position"))
                targets.append((distance is None, distance or 0.0, consumer["id"], consumer, unmet, capacity))
            targets.sort(key=lambda t: t[:3])
            for _, _, _, consumer, unmet, capacity in targets[:5]:
                direct = ctx.network.lines_between(producer["id"], consumer["id"], cargo)
                if direct:
                    excluded.append({**base, "consumer": consumer["name"], "lines": direct, "kind": "industry"})
                    reasons.add("already linked by a line")
                    continue
                if unmet <= 0:
                    reasons.add("consumer input already at recorded capacity")
                    continue
                candidates.append({**base, "type": "industry", "consumer": consumer, "unmet": unmet,
                                   "consumerCapacity": capacity,
                                   "distance": _km(producer.get("position"), consumer.get("position")),
                                   "distanceNote": "industry positions",
                                   "inFill": ctx.fills.get((consumer["id"], cargo, "in"))})
                found += 1
                if found >= 3:
                    break
            for town in snap.towns:
                supply = next((c for c in town.get("cargoSupply") or [] if isinstance(c, dict) and c.get("cargo") == cargo), None)
                if not supply or supply.get("supply") is None or _num(supply.get("limit")) <= 0:
                    continue
                unmet = _num(supply["limit"]) - _num(supply.get("supply"))
                if unmet <= 0:
                    continue
                anchor = ctx.anchors.get(town["id"])
                distance = _km(producer.get("position"), anchor[0]) if anchor else None
                direct = ctx.network.lines_to_town(producer["id"], town["id"], cargo)
                if direct:
                    excluded.append({**base, "consumer": _name(town, "Town"), "lines": direct, "kind": "town"})
                    continue
                candidates.append({**base, "type": "town", "consumer": town, "unmet": unmet,
                                   "consumerCapacity": _num(supply["limit"]),
                                   "distance": distance, "distanceNote": (
                                       f"town estimated from {anchor[1]} industr{'y' if anchor[1] == 1 else 'ies'} "
                                       f"named after it (spread {anchor[2]:.1f} km)" if anchor else "town position not collected"),
                                   "inFill": None})
                found += 1
            if not found:
                booster = _cargo_key(snap, cargo) in BOOSTER_CARGOS
                dead_ends.append({**base, "why": "; ".join(sorted(reasons)) or (
                    "booster cargo: primary industries use it but the snapshot lists no booster inputs" if booster
                    else "no consumer of this cargo in the snapshot")})
    return candidates, excluded, dead_ends


def _score(ctx: _Context, cand: dict[str, Any], remaining: dict[tuple[int, int], float]) -> dict[str, Any]:
    snap = ctx.snap
    producer, consumer, cargo = cand["producer"], cand["consumer"], cand["cargo"]
    unmet = remaining.get((consumer["id"], cargo), cand["unmet"])
    volume = max(0.0, min(cand["unshipped"], unmet))
    parts: dict[str, float] = {}
    parts["volume"] = W_VOLUME * min(1.0, volume / VOLUME_REF)
    parts["distance"] = _distance_points(cand["distance"])
    waiting = cand["outFill"]
    base_urgency = (0.5 * (1 - cand["ratio"]) + 0.5 * waiting) if waiting is not None else 0.5 * (1 - cand["ratio"]) * 0.5
    persistence = cand["persistence"]
    if persistence is not None:
        base_urgency *= 0.5 + 0.5 * persistence
    parts["urgency"] = W_URGENCY * base_urgency
    flags: list[str] = []
    penalties: list[tuple[str, float]] = []
    if cand["type"] == "industry":
        capacity = cand["consumerCapacity"]
        parts["pull"] = W_PULL * (unmet / capacity if capacity else 0.0)
        missing = _other_inputs_missing(snap, consumer, cargo)
        cand["missingInputs"] = missing
        useful = _outputs_useful(snap, consumer, ctx.consuming, ctx.town_cargos)
        parts["chain"] = W_CHAIN * useful * (0.5 if missing else 1.0)
        if missing:
            flags.append("consumer also lacks " + ", ".join(missing))
        if cand["inFill"] is not None and cand["inFill"] >= FULL_INPUT_STOCK:
            penalties.append((f"consumer input stock {_fmt_pct(cand['inFill'])} full", PENALTY_FULL_INPUT))
        if _is_closing(snap, consumer):
            penalties.append(("consumer industry is closing", PENALTY_CLOSING))
    else:
        parts["pull"] = W_PULL * (unmet / cand["consumerCapacity"] if cand["consumerCapacity"] else 0.0)
        parts["chain"] = W_CHAIN / 2
        cand["missingInputs"] = []
    if _is_closing(snap, producer):
        penalties.append(("producer industry is closing", PENALTY_CLOSING))
    water = _industry_key(producer) in WATER_INDUSTRIES
    proof = _cargo_proof(ctx.proven, cargo, ("WATER",) if water else None)
    cand["water"] = water
    cand["proof"] = proof
    parts["proven"] = W_PROVEN * proof["share"] if proof["share"] is not None else 0.0
    if cand["distance"] is None:
        flags.append("distance unknown")
    elif cand["type"] == "town":
        flags.append("town distance is a rough estimate")
    if cand["producerLines"]:
        flags.append("producer already served by " + _short(cand["producerLines"][0], 40) + " (check capacity first)")
    if waiting is not None and waiting >= FULL_INPUT_STOCK:
        flags.append(f"output stock {_fmt_pct(waiting)} full: destruction risk at capacity")
    if water:
        flags.append("water-based producer: ships/ports needed")
    if persistence is None:
        flags.append(f"persistence n/a ({cand['persistenceN']} usable samples)")
    else:
        flags.append(f"under-shipped in {persistence * 100:.0f}% of {cand['persistenceN']} samples")
    penalty = sum(p for _, p in penalties)
    total = max(0.0, sum(parts.values()) - penalty)
    return {**cand, "volume": volume, "parts": parts, "penalties": penalties, "score": total, "flags": flags}


def _rank(ctx: _Context, candidates: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
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
        best["alternatives"] = [f"{_name(c['consumer'], 'Town' if c['type'] == 'town' else 'Industry')} (score {c['score']:.1f}, "
                                f"{_f(c['distance']) + ' km' if c['distance'] is not None else 'distance unknown'})"
                                for c in scored[1:]
                                if c["producer"]["id"] == best["producer"]["id"] and c["cargo"] == best["cargo"]][:2]
        picked.append(best)
        key = (best["consumer"]["id"], best["cargo"])
        remaining[key] = max(0.0, remaining.get(key, best["unmet"]) - best["volume"])
        pool = [c for c in pool if not (c["producer"]["id"] == best["producer"]["id"] and c["cargo"] == best["cargo"])]
    return picked


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


def _years(model: dict[str, Any]) -> str:
    start, end = model.get("yearFrom"), model.get("yearTo")
    return f"{start or 'any'} to {end if end else 'open'}"


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


def _vehicle_fit(catalog_snap: Snapshot | None, year: int | None, cand: dict[str, Any]) -> list[dict[str, Any]]:
    if catalog_snap is None:
        return []
    cargo = cand["cargo"]
    carriers: list[str]
    if cand["water"]:
        carriers = ["WATER"]
    else:
        carriers = []
        best = cand["proof"]["bestCarrier"]
        if best:
            carriers.append(best)
        carriers.append("ROAD")
        if (cand["distance"] or 0) >= 6:
            carriers.append("RAIL")
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
        units = catalog_snap.meta.get("verifiedUnits") or {}
        priced = [m for m in models if _num(m.get("runningCosts")) > 0] if units.get("runningCosts") == "currency/year" else []
        cheapest = min(priced, key=lambda m: (_num(m["runningCosts"]) / _capacity_for(m, cargo), str(m.get("name")))) if priced else None
        for tag, model in (("largest capacity", biggest), ("lowest annual running cost per capacity", cheapest)):
            if model is None:
                continue
            if rows and rows[-1]["carrier"] == carrier and rows[-1]["model"] is model:
                rows[-1]["why"] += " and " + tag
                continue
            capacity = _capacity_for(model, cargo)
            rows.append({"carrier": carrier, "model": model, "why": tag, "capacity": capacity,
                         "loads": cand["volume"] / capacity if capacity else None})
    return rows


# ---------------------------------------------------------------------------
# report sections
# ---------------------------------------------------------------------------

def _formula_blocks() -> list[Any]:
    return [
        Heading(2, "Scoring Formula"),
        Paragraph("Score = Volume + Distance + Urgency + Pull + Chain + Proven - Penalties, floored at 0. "
                  "Maximum before penalties is 100. Every component is printed per candidate in the breakdown table."),
        Table(["Component", "Max", "Definition"], [
            ["Volume", W_VOLUME, f"{W_VOLUME} x min(1, V / {VOLUME_REF}) where V = min(producer unshipped items per year, consumer unmet input or town unmet demand per year), "
                                 "as recorded. Volume is deducted from a shared consumer as candidates are chosen, so two rows never claim the same capacity twice."],
            ["Distance", W_DISTANCE, f"Straight-line km estimate. 0 below {SHORT_KM} km, linear ramp to full at {SWEET_FROM_KM} km, full to {SWEET_TO_KM} km, "
                                     f"then declines to {int(LONG_FLOOR * 100)}% at {LONG_KM:g} km and stays there. Heuristic: income grows with distance but trip time does too. Unknown distance scores 0."],
            ["Urgency", W_URGENCY, f"{W_URGENCY} x (0.5 x (1 - shipped/produced) + 0.5 x output stock fill). Without a stock reading use 0.25 x (1 - shipped/produced) instead of the entire bracket. "
                                   f"Scaled by 0.5 + 0.5 x persistence when at least {PERSISTENCE_MIN_SAMPLES} samples exist."],
            ["Pull", W_PULL, f"{W_PULL} x unmet share of the consumer's recorded annual input capacity (industry) or of the town's recorded demand limit (town)."],
            ["Chain", W_CHAIN, f"Industry consumers: {W_CHAIN} if the consumer's outputs feed another industry, 60% of that if they only feed towns, halved while the consumer lacks another mandatory input. "
                               f"Town consumers: flat {W_CHAIN // 2}."],
            ["Proven", W_PROVEN, f"{W_PROVEN} x share of our vehicles hauling this cargo that currently show positive rolling annual profit (needs at least {PROVEN_MIN_VEHICLES} such vehicles, else 0). Water-based sources use WATER vehicles only."],
            ["Penalties", f"-{PENALTY_FULL_INPUT} / -{PENALTY_CLOSING}", f"-{PENALTY_FULL_INPUT} consumer input stock at or above {int(FULL_INPUT_STOCK * 100)}% full; "
                                                                          f"-{PENALTY_CLOSING} each for a closing producer or consumer."],
        ], ["left", "right", "left"]),
        Note("Weights", "The weights and thresholds are this report's own heuristics, not game mechanics; treat the score as a ranking aid, never a profit forecast."),
    ]


def _candidate_label(cand: dict[str, Any]) -> str:
    producer = _name(cand["producer"], "Industry")
    return f"{producer} -> {_name(cand['consumer'], 'Town' if cand['type'] == 'town' else 'Industry')}"


def _steps(cand: dict[str, Any], snap: Snapshot) -> str:
    producer, consumer = _name(cand["producer"], "Industry"), _name(cand["consumer"], "Industry")
    cargo = snap.cargo(cand["cargo"])
    steps = [f"1. Check on the map that a road, rail or water connection between {producer} and {consumer} is physically possible."]
    if cand["producerLines"]:
        steps.append(f"2. {producer} already has a line carrying this cargo ({_short(cand['producerLines'][0], 50)}); "
                     "first look at whether adding vehicles or fixing that line's destination removes the surplus.")
    else:
        steps.append(f"2. Build or reuse a loading station at {producer} and an unloading station at {consumer}, and create a line between them that carries {cargo}.")
    steps.append("3. Compare the cargo-compatible models with purchase and upkeep figures in the game; the table is a shortlist, not a fleet-size prescription. Begin conservatively and inspect both stocks in later samples before adding vehicles.")
    if cand.get("missingInputs"):
        steps.append(f"4. {consumer} also needs {', '.join(cand['missingInputs'])}; delivering only {cargo} may not start its production. See the starved-consumer table for candidate suppliers.")
    if cand["type"] == "industry" and cand.get("inFill") is not None and cand["inFill"] >= FULL_INPUT_STOCK:
        steps.append("5. Its input stock is nearly full: deliveries could be refused or cargo destroyed until it consumes more.")
    return " ".join(steps)


def _observation(cand: dict[str, Any], snap: Snapshot) -> str:
    cargo = snap.cargo(cand["cargo"])
    bits = [f"{_name(cand['producer'], 'Industry')} produced {cand['produced']:,.0f} {cargo} per year and shipped {cand['shipped']:,.0f} ({_fmt_pct(cand['ratio'])})."]
    if cand["outFill"] is not None:
        bits.append(f"Its {cargo} output stock is {_fmt_pct(cand['outFill'])} full.")
    if cand["type"] == "industry":
        cons = cand["consumer"]
        bits.append(f"{_name(cons, 'Industry')} has {cand['unmet']:,.0f} of {cand['consumerCapacity']:,.0f} recorded annual {cargo} input capacity unused.")
    else:
        bits.append(f"{_name(cand['consumer'], 'Town')} records demand limit {cand['consumerCapacity']:,.1f} with {cand['consumerCapacity'] - cand['unmet']:,.1f} supplied (interpretation of 'limit' and 'supply' is unverified).")
    proof = cand["proof"]
    if proof["share"] is not None:
        bits.append(f"Proven: {proof['profitable']} of {proof['vehicles']} of our {cargo} vehicles show positive rolling annual profit"
                    + (f"; best carrier {proof['bestCarrier']}." if proof["bestCarrier"] else "."))
    else:
        bits.append(f"No proof: fewer than {PROVEN_MIN_VEHICLES} of our vehicles currently haul {cargo} on a line.")
    return " ".join(bits)


def _risks(cand: dict[str, Any]) -> str:
    risks = [p for p, _ in cand["penalties"]]
    if cand["type"] == "industry" and cand.get("inFill") is not None and cand["inFill"] >= 0.5 and cand["inFill"] < FULL_INPUT_STOCK:
        risks.append(f"consumer input stock already {_fmt_pct(cand['inFill'])} full")
    risks.append("a full destination stock can block unloading and destroy cargo")
    if cand["type"] == "town":
        risks.append("town position is estimated, not measured")
    return "; ".join(risks)


def _ranking_blocks(ctx: _Context, picked: list[dict[str, Any]], catalog_snap: Snapshot | None) -> list[Any]:
    snap = ctx.snap
    if not picked:
        return [Heading(2, "Top Expansion Candidates"),
                Note("Insufficient Data", "No producer currently ships less than half of its output to an unserved consumer, "
                                          "or the stored snapshot lacks industry flow data.")]
    blocks: list[Any] = [Heading(2, f"Top {len(picked)} Expansion Candidates")]
    blocks.append(Table(
        ["#", "Route (producer -> consumer)", "Cargo", "Volume / Yr", "Distance (km, straight line)", "Score", "Flags"],
        [[i + 1, _candidate_label(c), snap.cargo(c["cargo"]), round(c["volume"]), _f(c["distance"]) if c["distance"] is not None else "unknown",
          round(c["score"], 1), "; ".join(c["flags"]) or "-"] for i, c in enumerate(picked)],
        ["right", "left", "left", "right", "right", "right", "left"]))
    blocks.append(Chart("bar", "Expansion score (higher is better)",
                        [f"{i + 1}. {_short(_name(c['producer'], 'Industry'), 14)}" for i, c in enumerate(picked)],
                        [("Score", [round(c["score"], 1) for c in picked])]))
    blocks.append(Heading(3, "Score Breakdown"))
    blocks.append(Table(
        ["#", "Volume", "Distance", "Urgency", "Pull", "Chain", "Proven", "Penalties", "Total"],
        [[i + 1, *(round(c["parts"][k], 1) for k in ("volume", "distance", "urgency", "pull", "chain", "proven")),
          f"-{sum(p for _, p in c['penalties']):g}" if c["penalties"] else "0", round(c["score"], 1)] for i, c in enumerate(picked)],
        ["right"] * 9))
    blocks.append(Paragraph("Volume is items per year as recorded by the bridge; distances use industry positions assumed to be metres; "
                            "town distances use an anchor estimated from industries named after the town."))

    blocks.append(Heading(3, "Candidate Detail"))
    for i, c in enumerate(picked):
        blocks.append(Note(f"#{i + 1} {_candidate_label(c)} ({snap.cargo(c['cargo'])})",
                           f"Observation: {_observation(c, snap)} Distance basis: {c['distanceNote']}. "
                           f"{'Alternative consumers for the same output: ' + '; '.join(c['alternatives']) + '. ' if c['alternatives'] else ''}"
                           f"Risks: {_risks(c)}. Manual steps: {_steps(c, snap)}"))

    year = (snap.date or {}).get("year", snap.meta.get("year"))
    fit_rows: list[list[Any]] = []
    for i, c in enumerate(picked):
        for row in _vehicle_fit(catalog_snap, year, c):
            m = row["model"]
            fit_rows.append([i + 1, snap.cargo(c["cargo"]), row["carrier"], m.get("name") or m.get("res") or f"Model #{m.get('id')}",
                             row["why"], row["capacity"], _f(row["loads"]) if row["loads"] else "-",
                             m.get("price") if (catalog_snap.meta.get("verifiedUnits") or {}).get("price") == "currency" else None,
                             m.get("runningCosts") if (catalog_snap.meta.get("verifiedUnits") or {}).get("runningCosts") == "currency/year" else None,
                             _years(m)])
    blocks.append(Heading(3, "Vehicle Fit"))
    if catalog_snap is None:
        blocks.append(Note("Analysis Pending", "No catalog snapshot is stored, so vehicle models cannot be suggested."))
    else:
        matched, compared = _capacity_check(snap, catalog_snap)
        blocks.append(Table(
            ["#", "Cargo", "Carrier", "Model", "Why listed", "Capacity / Unit", "Loads / Yr To Move Volume", "Price (verified currency)", "Running Cost (verified currency/year)", "Years"],
            fit_rows, ["right", "left", "left", "left", "left", "right", "right", "right", "right", "left"]))
        check = (f"Capacity per unit matches the recorded capacity of {matched} of {compared} single-model fleet vehicles compared against this catalog."
                 if compared else "Catalog capacity could not be cross-checked against any fleet vehicle.")
        blocks.append(Note("Unit Limit", f"{check} Price and running costs are omitted when units are unverified; "
                                         "cost-based ranking and speed are omitted without verified units. Models are limited to those available in the game year; "
                                         "rail rows are wagons or units and a locomotive is also needed. Models listed fit the cargo, not necessarily the terrain."))
    return blocks


def _proven_blocks(ctx: _Context, picked: list[dict[str, Any]]) -> list[Any]:
    snap = ctx.snap
    rows = sorted(ctx.proven.items(), key=lambda kv: (-kv[1]["median"], str(snap.cargo(kv[0][0])), kv[0][1]))
    rows = [(k, v) for k, v in rows if k[0] != 0 and v["vehicles"] >= PROVEN_MIN_VEHICLES and v["median"] > 0]
    blocks: list[Any] = [Heading(2, "Extend the Proven: Cargo That Already Pays for Us")]
    if not rows:
        blocks.append(Note("Insufficient Data", f"No freight cargo and carrier combination has at least {PROVEN_MIN_VEHICLES} line-assigned vehicles with a positive median rolling annual profit."))
        return blocks
    in_ranking = defaultdict(int)
    for c in picked:
        in_ranking[c["cargo"]] += 1
    blocks.append(Table(
        ["Cargo", "Carrier", "Vehicles", "Profitable", "Median Rolling Annual Profit / Vehicle", "Candidates In Top List"],
        [[snap.cargo(cargo), carrier, v["vehicles"], v["profitable"], round(v["median"]), in_ranking.get(cargo, 0)]
         for (cargo, carrier), v in rows[:12]],
        ["left", "left", "right", "right", "right", "right"]))
    blocks.append(Note("Reading This", "Figures are rolling annual profit of vehicles at the latest sample only (one snapshot, never summed across samples). "
                                       "A vehicle's main cargo is its largest configured load; a multi-cargo line's profit cannot be split by cargo. "
                                       "Profit is raw game currency units. Past profit on a cargo does not guarantee a new route's profit."))
    if len(ctx.proven) and len(rows) > 12:
        blocks.append(Paragraph(f"{len(rows) - 12} further cargo and carrier combinations omitted."))
    return blocks


def _starved_blocks(ctx: _Context) -> list[Any]:
    snap = ctx.snap
    producers: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for ind in snap.industries:
        for flow in ind.get("outputs") or []:
            if _num(flow.get("producedYear")) > 0 and not _is_closing(snap, ind):
                producers[flow["cargo"]].append({"ind": ind, "flow": flow})
    rows: list[tuple[float, list[Any]]] = []
    for consumer in snap.industries:
        inputs = consumer.get("inputs") or []
        capacity = sum(_num(f.get("maxConsumptionYear")) for f in inputs)
        used = sum(max(_num(f.get("deliveredYear")), _num(f.get("consumedYear"))) for f in inputs)
        if capacity <= 0 or used / capacity >= 0.1 or _is_closing(snap, consumer):
            continue
        suppliers = []
        for flow in inputs:
            cargo = flow["cargo"]
            options = [(_km(consumer.get("position"), p["ind"].get("position")), p) for p in producers.get(cargo, []) if p["ind"]["id"] != consumer["id"]]
            options = [o for o in options if o[0] is not None]
            if options:
                dist, best = min(options, key=lambda o: (o[0], o[1]["ind"]["id"]))
                gone = max(0.0, _num(best["flow"].get("producedYear")) - _num(best["flow"].get("shippedYear")))
                suppliers.append(f"{snap.cargo(cargo)}: {_name(best['ind'], 'Industry')} {dist:.1f} km, {gone:,.0f} unshipped/yr")
            else:
                suppliers.append(f"{snap.cargo(cargo)}: no industry currently producing it")
        outputs = ", ".join(snap.cargo(f.get("cargo")) or "?" for f in consumer.get("outputs") or []) or "-"
        rows.append((capacity, [_name(consumer, "Industry"), round(capacity), outputs, " | ".join(suppliers)]))
    blocks: list[Any] = [Heading(2, "Starved Consumers: Chains That Cannot Start")]
    if not rows:
        blocks.append(Note("Insufficient Data", "No industry with recorded input capacity is currently below 10% input usage."))
        return blocks
    rows.sort(key=lambda r: (-r[0], r[1][0]))
    blocks.append(Table(["Consumer", "Annual Input Capacity (all inputs)", "Outputs Waiting To Start", "Nearest Producer Per Input"],
                        [r[1] for r in rows[:10]], ["left", "right", "left", "left"]))
    if len(rows) > 10:
        blocks.append(Paragraph(f"{len(rows) - 10} further starved consumers omitted; shown by largest input capacity."))
    blocks.append(Note("Reading This", "Usage is the larger of delivered and consumed per year over the recorded capacity. "
                                       "Multi-input consumers need all mandatory inputs (a Food Factory takes Fish or Meat plus Sheet Metal), so supplying one input alone usually does nothing. "
                                       "Nearest producer ignores whether that producer's output is already shipped elsewhere."))
    return blocks


def _town_blocks(ctx: _Context) -> list[Any]:
    snap = ctx.snap
    station_towns: dict[int, int] = defaultdict(int)
    for station in snap.stations:
        if station.get("town") is not None:
            station_towns[station["town"]] += 1
    rows = []
    for town in snap.towns:
        usage = town.get("lineUsage")
        stations = station_towns.get(town["id"], 0)
        if stations and isinstance(usage, (int, float)) and usage >= 0.2:
            continue
        unmet = [c for c in town.get("cargoSupply") or [] if isinstance(c, dict) and _num(c.get("limit")) - _num(c.get("supply")) > 0]
        rows.append([_name(town, "Town"), sum(town.get("capacities") or []) or None, usage, stations,
                     ", ".join(sorted(snap.cargo(c["cargo"]) or "?" for c in unmet)) or "-"])
    rows.sort(key=lambda r: (-(r[1] or 0), r[0]))
    blocks: list[Any] = [Heading(2, "Towns With No or Little Service")]
    if not rows:
        blocks.append(Note("Insufficient Data", "Every town has at least one of our stations and line usage of 20% or more."))
        return blocks
    blocks.append(Table(["Town", "Capacity Sum (population proxy)", "Line Usage", "Our Stations", "Cargo With Unmet Demand"],
                        rows[:10], ["left", "right", "right", "right", "left"]))
    if len(rows) > 10:
        blocks.append(Paragraph(f"{len(rows) - 10} further towns omitted; shown by capacity sum."))
    blocks.append(Note("Reading This", "Town positions are not collected, so no passenger route is scored or sized here. Capacity sum (residential + commercial + industrial) is an unverified population proxy; "
                                       "line usage is a recorded fraction whose exact meaning is unverified. These are leads to inspect, not recommendations."))
    return blocks


def _excluded_blocks(ctx: _Context, excluded: list[dict[str, Any]], dead_ends: list[dict[str, Any]]) -> list[Any]:
    snap = ctx.snap
    blocks: list[Any] = [Heading(2, "Cross-Check: Routes That Already Exist (Never Recommended)")]
    seen = set()
    rows = []
    for e in excluded:
        key = (e["producer"]["id"], e["cargo"], e["consumer"])
        if key in seen:
            continue
        seen.add(key)
        rows.append([_name(e["producer"], "Industry"), e["consumer"], snap.cargo(e["cargo"]), _fmt_pct(e["ratio"]), "; ".join(e["lines"][:2])])
    if rows:
        blocks.append(Table(["Producer", "Consumer", "Cargo", "Shipped / Produced", "Existing Line(s)"], rows[:10], ["left", "left", "left", "right", "left"]))
        if len(rows) > 10:
            blocks.append(Paragraph(f"{len(rows) - 10} further existing pairs omitted."))
        blocks.append(Note("Meaning", "These producers still ship under half of their output although a cargo-compatible line or transfer path of ours connects both ends. "
                                      "Inspect its filters, capacity and scheduling before proposing a duplicate route; this is a possible connection, not proof of delivery."))
    else:
        blocks.append(Paragraph("No under-shipping producer is already linked to a consumer by one of our lines."))
    blocks.append(Note("Matching Limit", "Industries match only station groups with exactly the industry's name. Cargo-compatible transfers at shared station groups are conservatively excluded; "
                                         "renamed stations, catchment overlap and unloading filters are not collected, so verify every candidate's existing network manually before construction."))
    blocks.append(Heading(3, "Unshipped Output With No Viable Target"))
    if dead_ends:
        dead = sorted(dead_ends, key=lambda d: (-d["unshipped"], d["producer"]["id"], d["cargo"]))
        blocks.append(Table(["Producer", "Cargo", "Unshipped / Yr", "Reason"],
                            [[_name(d["producer"], "Industry"), snap.cargo(d["cargo"]), round(d["unshipped"]), d["why"]] for d in dead[:10]],
                            ["left", "left", "right", "left"]))
        if len(dead) > 10:
            blocks.append(Paragraph(f"{len(dead) - 10} further producers omitted."))
    else:
        blocks.append(Paragraph("Every under-shipping producer has at least one viable target."))
    return blocks


def build(store: Store) -> ReportDocument:
    snaps = _recent_current(store, 1)
    if not snaps:
        raise ValueError("no snapshot found")
    latest = snaps[-1]
    ctx = _Context(store, latest)
    catalog_snap = store.latest_with_catalog(game_time=latest.game_time)

    candidates, excluded, dead_ends = _candidates(ctx)
    picked = _rank(ctx, candidates, TOP_N)

    header = _base_header(latest, len(ctx.samples))
    dates = [s.date_label for s in ctx.samples]
    header.insert(2, ("History Samples", f"{len(ctx.samples)} (monthly for the newest 12 game months, quarterly before): {dates[0]} to {dates[-1]}"))
    header.insert(3, ("Catalog Sample", catalog_snap.date_label if catalog_snap else "none stored"))
    header.append(("Candidates Evaluated", f"{len(candidates)} producer-consumer pairs from {len({(c['producer']['id'], c['cargo']) for c in candidates})} under-shipping outputs"))

    blocks: list[Any] = [
        Paragraph("Ranked candidates for new or extended routes, built from producers that ship less than half of their output "
                  "and consumers (industries or towns) that can use the cargo. Observations come straight from the latest sample; "
                  "scores and fit lists are inference; manual steps are suggestions for you to carry out. Nothing here changes the game."),
    ]
    blocks.extend(_formula_blocks())
    blocks.extend(_ranking_blocks(ctx, picked, catalog_snap))
    blocks.extend(_proven_blocks(ctx, picked))
    blocks.extend(_starved_blocks(ctx))
    blocks.extend(_town_blocks(ctx))
    blocks.extend(_excluded_blocks(ctx, excluded, dead_ends))
    persistent = sum(1 for c in picked if c["persistence"] is not None)
    blocks.append(Heading(2, "Coverage and Limits"))
    blocks.append(Note("Sampling", f"Output flows are rolling annual figures from the latest sample; persistence over earlier samples was usable for {persistent} of {len(picked)} listed candidates "
                                   f"(needs at least {PERSISTENCE_MIN_SAMPLES} samples). As snapshots accumulate over years, persistence and the history window fill in automatically."))
    blocks.append(Note("Measurement Limits", "Distances are straight-line estimates between recorded positions and say nothing about terrain, rivers or route length. "
                                              "Production and demand figures are per-year values as recorded; the accounting of transportedYear is unverified. "
                                              "Town positions and station positions are not collected. Missing values are treated as unknown, not zero."))
    return ReportDocument("expansion", "Expansion Opportunities Report", header, blocks)
