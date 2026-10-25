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

# Stable finding codes the engine can emit, mapped to the entity kind whose methodology role
# can scope an override (None: the finding has no role-bearing entity).
FINDING_CODES: dict[str, str | None] = {
    "line_orphan": "line",
    "line_no_vehicles": "line",
    "line_no_stops": "line",
    "line_losing_money": "line",
    "line_overloaded": "line",
    "line_underused": "line",
    "line_config_issue": "line",
    "line_profit_dropping": "line",
    "line_load_persistently_high": "line",
    "line_load_persistently_low": "line",
    "vehicle_no_path": "vehicle",
    "vehicle_losing_on_profitable_line": "vehicle",
    "fleet_idle_in_depot": None,
    "industry_closing": "industry",
    "industry_output_full": "industry",
    "warehouse_full": None,
    "station_stock_full": None,
    "industries_output_full_unserved": None,
    "snapshot_collection_errors": None,
}


@dataclass(frozen=True)
class Thresholds:
    overloaded_load: float = 0.9  # line occupancy at snapshot time
    underused_load: float = 0.3
    underused_min_vehicles: int = 2
    mature_years: float = 1.0  # GAME-YEAR policy, not proof of financial-window completeness
    idle_depot_days: int = 30
    unshipped_ratio: float = 0.5  # shipped / produced below this = cargo left behind
    profit_drop_ratio: float = 0.3  # line profit fell by more than 30% since previous snapshot
    min_profit_drop: int = 100_000
    full_stock_ratio: float = 0.9
    trend_snapshots: int = 6
    trend_min_samples: int = 3
    fit_improvement: float = 0.25


@dataclass
class Finding:
    code: str
    severity: str  # high | medium | low
    category: str  # finance | lines | vehicles | industries | data
    title: str
    detail: str
    suggestion: str
    entity: dict[str, Any] | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    methodology: str | None = None  # id@version of the methodology applied
    methodology_hash: str | None = None  # sha256:<12 hex> of the methodology file
    source: str = "engine"  # engine | methodology
    methodology_selection: dict[str, Any] = field(default_factory=dict)

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


def line_age_time(snap: Snapshot, line: dict[str, Any], *, clock=None):
    from .game_time import TimeMeasure

    times = [v["purchaseTime"] for v in snap.line_vehicles(line) if v.get("purchaseTime") is not None]
    if not times:
        return TimeMeasure(None, reason="missing-timestamp")
    return (
        clock.elapsed_between_ticks(min(times), snap.game_time)
        if clock
        else TimeMeasure(None, reason="missing-calendar-context")
    )


def line_age_years(snap: Snapshot, line: dict[str, Any], *, clock=None) -> float | None:
    """Oldest currently assigned vehicle age, not line creation or first observation."""
    return line_age_time(snap, line, clock=clock).value


def line_row(snap: Snapshot, line: dict[str, Any], *, clock=None) -> dict[str, Any]:
    load = line_load(line)
    age_time = line_age_time(snap, line, clock=clock)
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
        "ageYears": age_time.value,
        "ageTime": age_time.to_dict(),
        "timeBasis": clock.time_basis if clock else None,
    }


def vehicle_row(snap: Snapshot, vehicle: dict[str, Any], *, clock=None) -> dict[str, Any]:
    from .game_time import TimeMeasure

    age_time = (
        clock.elapsed_between_ticks(vehicle.get("purchaseTime"), snap.game_time)
        if clock
        else TimeMeasure(None, reason="missing-calendar-context")
    )
    line = snap.lines_by_id.get(vehicle.get("line"))
    models = [
        snap.models.get(m, {}).get("name") or snap.models.get(m, {}).get("res") for m in vehicle.get("models") or []
    ]
    return {
        "id": vehicle["id"],
        "name": vehicle.get("name"),
        "carrier": vehicle.get("carrier"),
        "state": vehicle.get("state"),
        "line": vehicle.get("line"),
        "lineName": line.get("name") if line else None,
        "models": sorted({m for m in models if m}),
        "ageYears": age_time.value,
        "ageTime": age_time.to_dict(),
        "timeBasis": clock.time_basis if clock else None,
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
        "closing": bool(industry.get("closureTimeStamp"))
        or industry["id"] in set(snap.problems.get("closingIndustries") or []),
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


def _line_findings(snap: Snapshot, prev: Snapshot | None, t: Thresholds, *, clock=None) -> list[Finding]:
    out: list[Finding] = []
    for line in snap.lines:
        row = line_row(snap, line, clock=clock)
        name = row["name"] or f"line {row['id']}"
        mature = row["ageYears"] is not None and row["ageYears"] >= t.mature_years

        if row["vehicles"] == 0 or row["stops"] < 2:
            code = (
                "line_orphan"
                if row["vehicles"] == 0 and row["stops"] < 2
                else ("line_no_vehicles" if row["vehicles"] == 0 else "line_no_stops")
            )
            out.append(
                Finding(
                    code,
                    "medium",
                    "lines",
                    f"{name}: incomplete line",
                    f"{row['vehicles']} vehicles and {row['stops']} stops.",
                    "Review the line in the game; assign vehicles and at least two stops, or remove abandoned lines.",
                    _entity("line", line),
                    {"stops": row["stops"], "vehicles": row["vehicles"]},
                )
            )

        profit = row["profitYear"]
        if profit is not None and profit < 0 and row["vehicles"] > 0:
            partial = (
                ""
                if mature
                else (
                    f" (calendar age below maturity policy {t.mature_years:g} GAME-YEAR)"
                    if row["ageYears"] is not None
                    else " (calendar maturity unknown; conservative low-severity policy)"
                )
            )
            out.append(
                Finding(
                    "line_losing_money",
                    "high" if mature else "low",
                    "lines",
                    f"{name}: loss over the last year",
                    f"Annual result {profit:,}{partial}. Current load: {_pct(row['load'])}.",
                    "Check whether demand justifies the fleet: reduce vehicles, review the stops "
                    "or change transport mode. If the line feeds another line (network), assess the whole before cutting.",
                    _entity("line", line),
                    row,
                )
            )

        load = row["load"]
        if load is not None and load >= t.overloaded_load:
            out.append(
                Finding(
                    "line_overloaded",
                    "medium",
                    "lines",
                    f"{name}: overloaded ({_pct(load)})",
                    "Vehicles are almost full at snapshot time. Load is an instant reading, not an average; "
                    "this alone does not establish persistent crowding or unmet demand.",
                    "Compare earlier snapshots and station queues before changing fleet size. If persistent "
                    "crowding is confirmed, consider more or larger vehicles and check station frequency limits.",
                    _entity("line", line),
                    row,
                )
            )
        elif load is not None and load <= t.underused_load and row["vehicles"] >= t.underused_min_vehicles:
            out.append(
                Finding(
                    "line_underused",
                    "low",
                    "lines",
                    f"{name}: underused ({_pct(load)})",
                    "Little cargo or few passengers aboard at snapshot time. This is an instant reading, not an average.",
                    "If this repeats in successive snapshots, remove vehicles or combine with another line.",
                    _entity("line", line),
                    row,
                )
            )

        for issue in line.get("issues") or []:
            if issue.get("type") in (None, "None"):
                continue
            out.append(
                Finding(
                    "line_config_issue",
                    "high",
                    "lines",
                    f"{name}: configuration issue ({issue.get('type')})",
                    f"Stop {issue.get('stopIndex')}, cargo {snap.cargo(issue.get('cargo')) or '-'}.",
                    "Open the line in the game and adjust loading/unloading or compatible vehicles.",
                    _entity("line", line),
                    {"issue": issue},
                )
            )

        if prev is not None and profit is not None:
            old = prev.lines_by_id.get(line["id"])
            old_profit = old.get("profitYear") if old else None
            if old_profit is not None and old_profit > 0:
                drop = old_profit - profit
                if drop >= t.min_profit_drop and drop / old_profit >= t.profit_drop_ratio:
                    out.append(
                        Finding(
                            "line_profit_dropping",
                            "medium",
                            "lines",
                            f"{name}: profit dropping",
                            f"From {old_profit:,} ({prev.date_label}) to {profit:,} ({snap.date_label}).",
                            "Check whether demand fell (competition from another line, an industry closing) "
                            "or costs rose (new vehicles, maintenance).",
                            _entity("line", line),
                            {"previous": old_profit, "current": profit},
                        )
                    )
    return out


def _vehicle_findings(snap: Snapshot, t: Thresholds, *, clock=None) -> list[Finding]:
    out: list[Finding] = []
    idle: list[dict[str, Any]] = []
    for v in snap.vehicles:
        row = vehicle_row(snap, v, clock=clock)
        name = row["name"] or f"vehicle {row['id']}"
        if v.get("noPath"):
            out.append(
                Finding(
                    "vehicle_no_path",
                    "high",
                    "vehicles",
                    f"{name}: no path",
                    f"The vehicle cannot find a path on line {row['lineName'] or '-'}.",
                    "Check for disconnected tracks/roads, signalling or electrification along the route.",
                    _entity("vehicle", v),
                    row,
                )
            )
        if v.get("state") == "IN_DEPOT" and not v.get("line") and (v.get("daysInDepot") or 0) >= t.idle_depot_days:
            idle.append(row)
        line = snap.lines_by_id.get(v.get("line"))
        profit = v.get("profitYear")
        if (
            line is not None
            and profit is not None
            and profit < 0
            and (line.get("profitYear") or 0) > 0
            and row["ageYears"] is not None
            and row["ageYears"] >= t.mature_years
        ):
            out.append(
                Finding(
                    "vehicle_losing_on_profitable_line",
                    "low",
                    "vehicles",
                    f"{name}: loss on a profitable line",
                    f"Vehicle {profit:,} over the year; line {line.get('name')} earns {line.get('profitYear'):,}.",
                    "There may be too many vehicles on the line. Try removing one and monitor load.",
                    _entity("vehicle", v),
                    row,
                )
            )
    total = sum(r.get("value") or 0 for r in idle)
    depots = {d["id"]: d for d in snap.depots}
    groups: dict[Any, list[dict[str, Any]]] = {}
    for row in idle:
        groups.setdefault(row["depot"], []).append(row)
    for depot_id, rows in groups.items():
        depot = depots.get(depot_id, {"id": depot_id, "name": "Unknown depot"})
        name = depot.get("name") or f"Depot #{depot_id}"
        value = sum(r.get("value") or 0 for r in rows)
        out.append(
            Finding(
                "fleet_idle_in_depot",
                "medium",
                "vehicles",
                f"{name}: {len(rows)} idle vehicle(s)",
                f"No assigned line for {t.idle_depot_days}+ days; recorded resale value {value:,}.",
                "Consider assigning or selling these vehicles after checking intended reserve capacity.",
                _entity("depot", depot),
                {"vehicles": rows, "value": value, "totalIdleValue": total, "idleDepotDays": t.idle_depot_days},
            )
        )
    return out


def _industry_findings(snap: Snapshot, t: Thresholds) -> list[Finding]:
    out: list[Finding] = []
    closing = set(snap.problems.get("closingIndustries") or [])
    for ind in snap.industries:
        row = industry_row(snap, ind)
        name = row["name"] or f"industry {row['id']}"
        if ind["id"] in closing or ind.get("closureTimeStamp"):
            out.append(
                Finding(
                    "industry_closing",
                    "high",
                    "industries",
                    f"{name}: scheduled to close",
                    "The industry is marked for closure.",
                    "If any of your lines depend on it, ensure deliveries/shipments now or plan a migration.",
                    _entity("industry", ind),
                    row,
                )
            )
    return out


def _data_findings(snap: Snapshot) -> list[Finding]:
    if not snap.errors:
        return []
    return [
        Finding(
            "snapshot_collection_errors",
            "low",
            "data",
            f"Snapshot with {len(snap.errors)} collection error(s)",
            "The mod could not read some data; numbers may be incomplete.",
            "Show the errors (tf3c status / status tool) to fix the collector.",
            None,
            {"errors": snap.errors[:20]},
        )
    ]


def findings(
    snap: Snapshot,
    prev: Snapshot | None = None,
    t: Thresholds | None = None,
    history: list[Snapshot] | None = None,
    methodology: Any = None,
    verdicts: Any = None,
    *,
    clock=None,
) -> list[Finding]:
    """Engine findings, then the methodology's role-scoped overrides and rule findings.

    `t` defaults to the defaults plus the methodology's `engine.thresholds`. Pass `verdicts` (from
    `methodology.evaluate`) to avoid evaluating the methodology twice.
    """
    if t is None:
        from .methodology import thresholds_for

        t = thresholds_for(methodology)
    out = (
        _line_findings(snap, prev, t, clock=clock)
        + _vehicle_findings(snap, t, clock=clock)
        + _industry_findings(snap, t)
        + _stock_findings(snap, t)
        + _data_findings(snap)
    )
    if history:
        trends = load_trend(history, t)
        sufficient = {r["id"] for r in trends if r["samples"] >= t.trend_min_samples}
        out = [f for f in out if not (f.code in {"line_overloaded", "line_underused"} and f.entity["id"] in sufficient)]
        for row in trends:
            line = snap.lines_by_id.get(row["id"])
            if line is None or row["id"] not in sufficient:
                continue
            high = row["meanLoad"] >= t.overloaded_load
            low = row["meanLoad"] <= t.underused_load and len(line.get("vehicles") or []) >= t.underused_min_vehicles
            if high or low:
                out.append(
                    Finding(
                        "line_load_persistently_high" if high else "line_load_persistently_low",
                        "medium" if high else "low",
                        "lines",
                        f"{row['name']}: repeated sampled occupancy",
                        "Sample mean is not a time average or proof of unmet demand.",
                        "Inspect queues and complete trips before changing the fleet.",
                        _entity("line", line),
                        {**row, "threshold": t.overloaded_load if high else t.underused_load},
                    )
                )
    if methodology is not None:
        from .methodology import engine

        if verdicts is None:
            verdicts = engine.evaluate(methodology, snap, history=history, clock=clock)
        out = engine.apply_finding_overrides(methodology, verdicts, out)
        for item in out:
            item.methodology, item.methodology_hash = methodology.identity, methodology.short_hash
        out += engine.rule_findings(methodology, verdicts)
        for item in out:
            item.methodology_selection = dict(methodology.selection)
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
        g = groups.setdefault(
            carrier, {"carrier": carrier, "lines": 0, "vehicles": 0, "profitYear": 0, "losingLines": 0}
        )
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
    bands = [
        (0.0, 0.2, "0–20%"),
        (0.2, 0.4, "20–40%"),
        (0.4, 0.6, "40–60%"),
        (0.6, 0.8, "60–80%"),
        (0.8, 1.01, "80–100%"),
    ]
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
            targets.append(
                {
                    "id": consumer["id"],
                    "name": consumer.get("name"),
                    "distanceKm": round(dist / 1000, 2) if dist is not None else None,
                    "alreadyDeliveredYear": delivered,
                }
            )
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
                    unshipped.append(
                        {
                            **base,
                            "kind": "unshipped",
                            "unshippedYear": produced - shipped,
                            "shippedRatio": round(ratio, 3),
                        }
                    )
            elif capacity > 0 and ind.get("inputs"):
                missing = [snap.cargo(f.get("cargo")) for f in ind["inputs"] if not (f.get("deliveredYear") or 0)]
                starved.append({**base, "kind": "needs_inputs", "idleCapacityYear": capacity, "missingInputs": missing})
    unshipped.sort(key=lambda o: o["unshippedYear"], reverse=True)
    starved.sort(key=lambda o: o["idleCapacityYear"], reverse=True)
    return (unshipped + starved)[:limit]


def _pct(value: float | None) -> str:
    return "-" if value is None else f"{value * 100:.0f}%"


def full_stocks(snap: Snapshot, t: Thresholds = Thresholds()) -> list[dict[str, Any]]:
    """Measured stock fill; industry rows require verified output-cargo overlap."""
    rows = []
    for stock in snap.stocks:
        count, capacity = stock.get("count"), stock.get("capacity")
        if count is None or capacity is None or capacity <= 0 or count / capacity < t.full_stock_ratio:
            continue
        industry = snap.industries_by_id.get(stock.get("owner"))
        if stock.get("kind") == "industry":
            outputs = industry.get("outputs") or [] if industry else []
            cargos = set(stock.get("cargos") or [])
            matching = [f for f in outputs if f.get("cargo") in cargos]
            if not matching:
                continue
            served = any((f.get("shippedYear") or 0) > 0 for f in matching)
        else:
            served = None
        rows.append(
            {
                **stock,
                "fill": count / capacity,
                "served": served,
                "name": stock.get("ownerName") or f"{stock.get('kind', 'Stock').title()} #{stock.get('owner')}",
                "cargoNames": [snap.cargo(c) for c in stock.get("cargos") or []],
            }
        )
    return rows


def _stock_findings(snap: Snapshot, t: Thresholds) -> list[Finding]:
    out, unserved = [], []
    codes = {"industry": "industry_output_full", "warehouse": "warehouse_full", "station": "station_stock_full"}
    for row in full_stocks(snap, t):
        if row["served"] is False:
            unserved.append(row)
            continue
        code = codes.get(row.get("kind"))
        if code:
            out.append(
                Finding(
                    code,
                    "medium",
                    "industries",
                    f"{row['name']}: stock full",
                    f"{row['count']:,} of {row['capacity']:,} units at this sample.",
                    "Inspect shipment connections and queues; fullness alone does not identify a cause.",
                    {"type": row["kind"], "id": row.get("owner"), "name": row["name"]},
                    {**row, "threshold": t.full_stock_ratio},
                )
            )
    if unserved:
        out.append(
            Finding(
                "industries_output_full_unserved",
                "low",
                "industries",
                f"{len(unserved)} unshipped output stocks full",
                "These output stocks have no recorded annual shipping.",
                "Review demand and network connections before proposing a route.",
                None,
                {
                    "count": len(unserved),
                    "stocks": sorted(unserved, key=lambda r: r["fill"], reverse=True)[:20],
                    "threshold": t.full_stock_ratio,
                },
            )
        )
    return out


def load_trend(history: list[Snapshot], t: Thresholds = Thresholds()) -> list[dict[str, Any]]:
    """Unweighted sample mean and sample-index slope, never a time average."""
    monthly: dict[Any, Snapshot] = {}
    for snap in sorted(history, key=lambda s: s.game_time):
        key = (snap.date["year"], snap.date["month"]) if snap.date else ("time", snap.game_time)
        monthly[key] = snap
    samples = sorted(monthly.values(), key=lambda s: s.game_time)[-t.trend_snapshots :]
    grouped: dict[int, list[tuple[Snapshot, dict[str, Any], float]]] = {}
    for snap in samples:
        for line in snap.lines:
            load = line_load(line)
            if load is not None:
                grouped.setdefault(line["id"], []).append((snap, line, load))
    rows = []
    for line_id, points in grouped.items():
        values = [p[2] for p in points]
        n = len(values)
        mean = sum(values) / n
        center = (n - 1) / 2
        denominator = sum((i - center) ** 2 for i in range(n))
        slope = sum((i - center) * (v - mean) for i, v in enumerate(values)) / denominator if denominator else None
        rows.append(
            {
                "id": line_id,
                "name": points[-1][1].get("name") or f"Line #{line_id}",
                "meanLoad": mean,
                "latestLoad": values[-1],
                "samples": n,
                "slope": slope,
                "status": "sampled" if n >= t.trend_min_samples else "insufficient_history",
                "observations": [{"date": s.date_label, "load": v} for s, _, v in points],
            }
        )
    return rows


def fleet_fit(snap: Snapshot, catalog_snap: Snapshot | None, t: Thresholds = Thresholds()) -> dict[str, Any]:
    """A capacity-speed/cost heuristic only with explicitly verified measurement units."""
    units = catalog_snap.meta.get("verifiedUnits", {}) if catalog_snap else {}
    if not catalog_snap or not catalog_snap.catalog:
        return {"status": "unavailable", "reason": "No catalog snapshot is stored.", "rows": []}
    if units.get("topSpeed") != "m/s" or units.get("runningCosts") != "currency/year":
        return {
            "status": "unavailable",
            "reason": "Catalog speed and annual running-cost units are not verified.",
            "rows": [],
            "catalogDate": catalog_snap.date_label,
        }
    year = (snap.date or {}).get("year", snap.meta.get("year"))
    if year is None:
        return {"status": "unavailable", "reason": "Game year is missing.", "rows": []}

    def score(model, cargo):
        capacity = sum(c.get("capacity") or 0 for c in model.get("capacity") or [] if c.get("cargo") == cargo)
        speed, cost = model.get("topSpeed"), model.get("runningCosts")
        return capacity * speed / cost if capacity > 0 and speed and speed > 0 and cost and cost > 0 else None

    def available(model):
        start, end = model.get("yearFrom"), model.get("yearTo")
        return (start is None or start <= 0 or start <= year) and (end is None or end <= 0 or year < end)

    rows = []
    catalog = catalog_snap.catalog
    for vehicle in snap.vehicles:
        configs = vehicle.get("loadConfig") or []
        if not configs:
            continue
        cargo = max(configs, key=lambda c: c.get("capacity") or 0).get("cargo")
        for model_id in vehicle.get("models") or []:
            model = snap.models.get(model_id, {})
            matches = [m for m in catalog if model.get("res") and m.get("res") == model["res"]]
            current = matches[0] if len(matches) == 1 else None
            current_score = score(current, cargo) if current else None
            alternatives = [
                m
                for m in catalog
                if m.get("carrier") == vehicle.get("carrier") and available(m) and score(m, cargo) is not None
            ]
            best = max(alternatives, key=lambda m: score(m, cargo), default=None)
            improvement = score(best, cargo) / current_score - 1 if best and current_score else None
            rows.append(
                {
                    "vehicle": vehicle.get("name") or f"Vehicle #{vehicle['id']}",
                    "model": model.get("name") or model.get("res") or f"Model #{model_id}",
                    "cargo": snap.cargo(cargo),
                    "score": current_score,
                    "alternative": best.get("name") or best.get("res") if best else None,
                    "improvement": improvement,
                    "better": improvement is not None and improvement >= t.fit_improvement,
                    "outOfProduction": not available(current) if current else None,
                    "status": "matched" if current_score else "unmatched",
                }
            )
    return {"status": "heuristic", "catalogDate": catalog_snap.date_label, "rows": rows}
