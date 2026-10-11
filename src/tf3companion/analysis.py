"""Decision layer: turns a snapshot (and the previous one) into rows, findings and opportunities.

Everything here is deterministic and explainable: each finding carries the
numbers that triggered it so the agent (and you) can argue with it.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any

from .snapshot import Snapshot

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


@dataclass(frozen=True)
class Thresholds:
    overloaded_load: float = 0.9          # line occupancy at snapshot time
    underused_load: float = 0.3
    underused_min_vehicles: int = 2
    mature_years: float = 1.0             # profit window is one year; younger lines are partial
    idle_depot_days: int = 30
    unshipped_ratio: float = 0.5          # shipped / produced below this = cargo left behind
    profit_drop_ratio: float = 0.3        # line profit fell by more than 30% since previous snapshot
    min_profit_drop: int = 100_000


@dataclass
class Finding:
    code: str
    severity: str           # high | medium | low
    category: str           # finance | lines | vehicles | industries | data
    title: str
    detail: str
    suggestion: str
    entity: dict[str, Any] | None = None
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# rows

def _ratio(num: float | None, den: float | None) -> float | None:
    if num is None or not den:
        return None
    return num / den


def line_load(line: dict[str, Any]) -> float | None:
    used = sum((c.get("used") or 0) for c in line.get("capacity") or [])
    cap = sum((c.get("capacity") or 0) for c in line.get("capacity") or [])
    return _ratio(used, cap)


def line_carrier(snap: Snapshot, line: dict[str, Any]) -> str | None:
    carriers = Counter(v.get("carrier") for v in snap.line_vehicles(line) if v.get("carrier"))
    return carriers.most_common(1)[0][0] if carriers else None


def line_age_years(snap: Snapshot, line: dict[str, Any]) -> float | None:
    """Age of the oldest vehicle on the line: a lower bound for how long the line has been running."""
    times = [v["purchaseTime"] for v in snap.line_vehicles(line) if v.get("purchaseTime") is not None]
    return snap.age_years(min(times)) if times else None


def line_row(snap: Snapshot, line: dict[str, Any]) -> dict[str, Any]:
    load = line_load(line)
    age = line_age_years(snap, line)
    return {
        "id": line["id"],
        "name": line.get("name"),
        "carrier": line_carrier(snap, line),
        "stops": len(line.get("stops") or []),
        "vehicles": len(line.get("vehicles") or []),
        "profitYear": line.get("profitYear"),
        "transportedYear": line.get("transportedYear"),
        "rate": line.get("rate"),
        "load": round(load, 3) if load is not None else None,
        "issues": len(line.get("issues") or []),
        "ageYears": round(age, 2) if age is not None else None,
    }


def vehicle_row(snap: Snapshot, vehicle: dict[str, Any]) -> dict[str, Any]:
    age = snap.age_years(vehicle.get("purchaseTime"))
    line = snap.lines_by_id.get(vehicle.get("line"))
    models = [snap.models.get(m, {}).get("name") or snap.models.get(m, {}).get("res") for m in vehicle.get("models") or []]
    return {
        "id": vehicle["id"],
        "name": vehicle.get("name"),
        "carrier": vehicle.get("carrier"),
        "state": vehicle.get("state"),
        "line": vehicle.get("line"),
        "lineName": line.get("name") if line else None,
        "models": sorted({m for m in models if m}),
        "ageYears": round(age, 2) if age is not None else None,
        "profitYear": vehicle.get("profitYear"),
        "value": vehicle.get("value"),
        "maintenanceState": vehicle.get("maintenanceState"),
        "noPath": vehicle.get("noPath"),
        "userStopped": vehicle.get("userStopped"),
        "daysInDepot": vehicle.get("daysInDepot"),
        "carries": [f"{snap.cargo(c['cargo'])} ({c['capacity']})" for c in vehicle.get("loadConfig") or []],
        "canCarry": [snap.cargo(c) for c in vehicle.get("canCarry") or []],
        "depot": vehicle.get("depot"),
    }


def industry_row(snap: Snapshot, industry: dict[str, Any]) -> dict[str, Any]:
    def flows(key: str) -> list[dict[str, Any]]:
        out = []
        for f in industry.get(key) or []:
            row = {k: v for k, v in f.items() if k != "cargo"}
            row["cargo"] = snap.cargo(f.get("cargo"))
            out.append(row)
        return out

    return {
        "id": industry["id"],
        "name": industry.get("name"),
        "type": industry.get("type"),
        "level": industry.get("level"),
        "maxLevel": industry.get("maxLevel"),
        "productionRating": industry.get("productionRating"),
        "closing": bool(industry.get("closureTimeStamp")) or industry["id"] in set(snap.problems.get("closingIndustries") or []),
        "inputs": flows("inputs"),
        "outputs": flows("outputs"),
    }


def town_row(town: dict[str, Any]) -> dict[str, Any]:
    caps = town.get("capacities") or []
    return {
        "id": town["id"],
        "name": town.get("name"),
        "population": sum(caps) if caps else None,
        "capacities": caps,
        "lineUsage": town.get("lineUsage"),
        "developmentActive": town.get("developmentActive"),
    }


# ---------------------------------------------------------------------------
# company

def company_overview(snap: Snapshot, prev: Snapshot | None) -> dict[str, Any]:
    c = snap.company
    profits = [line.get("profitYear") for line in snap.lines if line.get("profitYear") is not None]
    out: dict[str, Any] = {
        "date": snap.date_label,
        "balance": c.get("balance"),
        "loan": c.get("loan"),
        "earnings": c.get("earnings"),
        "companyValue": c.get("value"),
        "passengersTransported": c.get("passengersTransported"),
        "cargoTransported": c.get("cargoTransported"),
        "lines": len(snap.lines),
        "vehicles": len(snap.vehicles),
        "linesProfitYear": sum(profits) if profits else None,
        "linesLosingMoney": sum(1 for p in profits if p < 0),
        "snapshotErrors": len(snap.errors),
    }
    if prev is not None:
        pc = prev.company
        out["previous"] = {
            "date": prev.date_label,
            "balanceDelta": _delta(c.get("balance"), pc.get("balance")),
            "loanDelta": _delta(c.get("loan"), pc.get("loan")),
            "linesDelta": len(snap.lines) - len(prev.lines),
            "vehiclesDelta": len(snap.vehicles) - len(prev.vehicles),
        }
    return out


def _delta(a: float | None, b: float | None) -> float | None:
    return None if a is None or b is None else a - b


# ---------------------------------------------------------------------------
# findings

def _entity(kind: str, item: dict[str, Any]) -> dict[str, Any]:
    return {"type": kind, "id": item.get("id"), "name": item.get("name")}


def _line_findings(snap: Snapshot, prev: Snapshot | None, t: Thresholds) -> list[Finding]:
    out: list[Finding] = []
    for line in snap.lines:
        row = line_row(snap, line)
        name = row["name"] or f"line {row['id']}"
        mature = row["ageYears"] is not None and row["ageYears"] >= t.mature_years

        if row["vehicles"] == 0:
            out.append(Finding(
                "line_no_vehicles", "medium", "lines", f"{name}: no vehicles",
                "The line exists but has no vehicles assigned.",
                "Assign vehicles or delete the line if it has been abandoned.",
                _entity("line", line), {"stops": row["stops"]},
            ))

        profit = row["profitYear"]
        if profit is not None and profit < 0 and row["vehicles"] > 0:
            partial = "" if mature else " (line younger than 1 year: the number is partial)"
            out.append(Finding(
                "line_losing_money", "high" if mature else "low", "lines", f"{name}: loss over the last year",
                f"Annual result {profit:,}{partial}. Current load: {_pct(row['load'])}.",
                "Check whether demand justifies the fleet: reduce vehicles, review the stops "
                "or change transport mode. If the line feeds another line (network), assess the whole before cutting.",
                _entity("line", line), row,
            ))

        load = row["load"]
        if load is not None and load >= t.overloaded_load:
            out.append(Finding(
                "line_overloaded", "medium", "lines", f"{name}: overloaded ({_pct(load)})",
                "Vehicles are almost full at snapshot time. Load is an instant reading, not an average; "
                "this alone does not establish persistent crowding or unmet demand.",
                "Compare earlier snapshots and station queues before changing fleet size. If persistent "
                "crowding is confirmed, consider more or larger vehicles and check station frequency limits.",
                _entity("line", line), row,
            ))
        elif load is not None and load <= t.underused_load and row["vehicles"] >= t.underused_min_vehicles:
            out.append(Finding(
                "line_underused", "low", "lines", f"{name}: underused ({_pct(load)})",
                "Little cargo or few passengers aboard at snapshot time. This is an instant reading, not an average.",
                "If this repeats in successive snapshots, remove vehicles or combine with another line.",
                _entity("line", line), row,
            ))

        for issue in line.get("issues") or []:
            if issue.get("type") in (None, "None"):
                continue
            out.append(Finding(
                "line_config_issue", "high", "lines", f"{name}: configuration issue ({issue.get('type')})",
                f"Stop {issue.get('stopIndex')}, cargo {snap.cargo(issue.get('cargo')) or '-'}.",
                "Open the line in the game and adjust loading/unloading or compatible vehicles.",
                _entity("line", line), {"issue": issue},
            ))

        if prev is not None and profit is not None:
            old = prev.lines_by_id.get(line["id"])
            old_profit = old.get("profitYear") if old else None
            if old_profit is not None and old_profit > 0:
                drop = old_profit - profit
                if drop >= t.min_profit_drop and drop / old_profit >= t.profit_drop_ratio:
                    out.append(Finding(
                        "line_profit_dropping", "medium", "lines", f"{name}: profit dropping",
                        f"From {old_profit:,} ({prev.date_label}) to {profit:,} ({snap.date_label}).",
                        "Check whether demand fell (competition from another line, an industry closing) "
                        "or costs rose (new vehicles, maintenance).",
                        _entity("line", line), {"previous": old_profit, "current": profit},
                    ))
    return out


def _vehicle_findings(snap: Snapshot, t: Thresholds) -> list[Finding]:
    out: list[Finding] = []
    idle: list[dict[str, Any]] = []
    for v in snap.vehicles:
        row = vehicle_row(snap, v)
        name = row["name"] or f"vehicle {row['id']}"
        if v.get("noPath"):
            out.append(Finding(
                "vehicle_no_path", "high", "vehicles", f"{name}: no path",
                f"The vehicle cannot find a path on line {row['lineName'] or '-'}.",
                "Check for disconnected tracks/roads, signalling or electrification along the route.",
                _entity("vehicle", v), row,
            ))
        if v.get("state") == "IN_DEPOT" and not v.get("line") and (v.get("daysInDepot") or 0) >= t.idle_depot_days:
            idle.append(row)
        line = snap.lines_by_id.get(v.get("line"))
        profit = v.get("profitYear")
        if (
            line is not None
            and profit is not None and profit < 0
            and (line.get("profitYear") or 0) > 0
            and row["ageYears"] is not None and row["ageYears"] >= t.mature_years
        ):
            out.append(Finding(
                "vehicle_losing_on_profitable_line", "low", "vehicles", f"{name}: loss on a profitable line",
                f"Vehicle {profit:,} over the year; line {line.get('name')} earns {line.get('profitYear'):,}.",
                "There may be too many vehicles on the line. Try removing one and monitor load.",
                _entity("vehicle", v), row,
            ))
    if idle:
        value = sum(r.get("value") or 0 for r in idle)
        out.append(Finding(
            "vehicles_idle_in_depot", "medium", "vehicles", f"{len(idle)} vehicle(s) idle in depots",
            f"Without a line for {t.idle_depot_days}+ days. Total resale value: {value:,}.",
            "Sell them or assign them to a line; idle vehicles only depreciate.",
            None, {"vehicles": idle},
        ))
    return out


def _industry_findings(snap: Snapshot, t: Thresholds) -> list[Finding]:
    out: list[Finding] = []
    closing = set(snap.problems.get("closingIndustries") or [])
    for ind in snap.industries:
        row = industry_row(snap, ind)
        name = row["name"] or f"industry {row['id']}"
        if ind["id"] in closing or ind.get("closureTimeStamp"):
            out.append(Finding(
                "industry_closing", "high", "industries", f"{name}: scheduled to close",
                "The industry is marked for closure.",
                "If any of your lines depend on it, ensure deliveries/shipments now or plan a migration.",
                _entity("industry", ind), row,
            ))
    return out


def _data_findings(snap: Snapshot) -> list[Finding]:
    if not snap.errors:
        return []
    return [Finding(
        "snapshot_collection_errors", "low", "data", f"Snapshot with {len(snap.errors)} collection error(s)",
        "The mod could not read some data; numbers may be incomplete.",
        "Show the errors (tf3c status / status tool) to fix the collector.",
        None, {"errors": snap.errors[:20]},
    )]


def findings(snap: Snapshot, prev: Snapshot | None = None, t: Thresholds = Thresholds()) -> list[Finding]:
    out = (
        _line_findings(snap, prev, t)
        + _vehicle_findings(snap, t)
        + _industry_findings(snap, t)
        + _data_findings(snap)
    )
    return sorted(out, key=lambda f: (SEVERITY_ORDER[f.severity], f.category, f.title))


# ---------------------------------------------------------------------------
# opportunities: cargo produced but not shipped, matched with consumers

def _distance(a: list[float] | None, b: list[float] | None) -> float | None:
    if not a or not b or len(a) < 2 or len(b) < 2:
        return None
    return math.hypot(a[0] - b[0], a[1] - b[1])


def modal_summary(snap: Snapshot) -> list[dict[str, Any]]:
    """Lines, vehicles and annual profit per transport mode (carrier), most profitable first."""
    groups: dict[str, dict[str, Any]] = {}
    for line in snap.lines:
        row = line_row(snap, line)
        carrier = row["carrier"] or "NO VEHICLE"
        g = groups.setdefault(carrier, {"carrier": carrier, "lines": 0, "vehicles": 0, "profitYear": 0, "losingLines": 0})
        g["lines"] += 1
        g["vehicles"] += row["vehicles"]
        g["profitYear"] += row["profitYear"] or 0
        g["losingLines"] += 1 if (row["profitYear"] or 0) < 0 else 0
    out = list(groups.values())
    for g in out:
        g["profitPerVehicle"] = round(g["profitYear"] / g["vehicles"]) if g["vehicles"] else None
    return sorted(out, key=lambda g: g["profitYear"], reverse=True)


def load_distribution(snap: Snapshot) -> list[dict[str, Any]]:
    """How many lines fall in each occupancy band (snapshot instant)."""
    bands = [(0.0, 0.2, "0–20%"), (0.2, 0.4, "20–40%"), (0.4, 0.6, "40–60%"), (0.6, 0.8, "60–80%"), (0.8, 1.01, "80–100%")]
    counts = {label: 0 for _, _, label in bands}
    for line in snap.lines:
        load = line_load(line)
        if load is None:
            continue
        for lo, hi, label in bands:
            if lo <= load < hi:
                counts[label] += 1
                break
    return [{"band": label, "lines": counts[label]} for _, _, label in bands]


def opportunities(snap: Snapshot, t: Thresholds = Thresholds(), limit: int = 20) -> list[dict[str, Any]]:
    """Cargo opportunities, each paired with the nearest industries that consume that cargo.

    kind="unshipped": the industry produces but ships less than `unshipped_ratio` of it (cargo waiting).
    kind="needs_inputs": capacity exists but nothing is produced; the missing inputs are listed
    (feeding them unlocks the output).
    """
    consumers: dict[int, list[dict[str, Any]]] = {}
    for ind in snap.industries:
        for flow in ind.get("inputs") or []:
            consumers.setdefault(flow.get("cargo"), []).append(ind)

    def nearest(ind: dict[str, Any], cargo_id: int) -> list[dict[str, Any]]:
        targets = []
        for consumer in consumers.get(cargo_id, []):
            if consumer["id"] == ind["id"]:
                continue
            dist = _distance(ind.get("position"), consumer.get("position"))
            delivered = sum(
                (f.get("deliveredYear") or 0) for f in consumer.get("inputs") or [] if f.get("cargo") == cargo_id
            )
            targets.append({
                "id": consumer["id"],
                "name": consumer.get("name"),
                "distanceKm": round(dist / 1000, 2) if dist is not None else None,
                "alreadyDeliveredYear": delivered,
            })
        targets.sort(key=lambda x: (x["distanceKm"] is None, x["distanceKm"] or 0))
        return targets[:3]

    unshipped: list[dict[str, Any]] = []
    starved: list[dict[str, Any]] = []
    for ind in snap.industries:
        for flow in ind.get("outputs") or []:
            produced = flow.get("producedYear") or 0
            capacity = flow.get("maxProductionYear") or 0
            shipped = flow.get("shippedYear") or 0
            cargo_id = flow.get("cargo")
            base = {
                "producer": {"id": ind["id"], "name": ind.get("name"), "type": ind.get("type")},
                "cargo": snap.cargo(cargo_id),
                "producedYear": produced,
                "maxProductionYear": capacity,
                "shippedYear": shipped,
                "nearestConsumers": nearest(ind, cargo_id),
            }
            if produced > 0:
                ratio = shipped / produced
                if ratio < t.unshipped_ratio:
                    unshipped.append({**base, "kind": "unshipped", "unshippedYear": produced - shipped,
                                      "shippedRatio": round(ratio, 3)})
            elif capacity > 0 and ind.get("inputs"):
                missing = [snap.cargo(f.get("cargo")) for f in ind["inputs"] if not (f.get("deliveredYear") or 0)]
                starved.append({**base, "kind": "needs_inputs", "idleCapacityYear": capacity, "missingInputs": missing})
    unshipped.sort(key=lambda o: o["unshippedYear"], reverse=True)
    starved.sort(key=lambda o: o["idleCapacityYear"], reverse=True)
    return (unshipped + starved)[:limit]


def _pct(value: float | None) -> str:
    return "-" if value is None else f"{value * 100:.0f}%"
