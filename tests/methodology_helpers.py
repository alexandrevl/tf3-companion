"""Synthetic snapshots and tiny methodologies shared by the methodology tests."""

from __future__ import annotations

import copy
import json
from datetime import date
from typing import Any

from conftest import YEAR, base_snapshot
from tf3companion.game_time import GameCalendarClock
from tf3companion.methodology import evaluate, parse
from tf3companion.snapshot import Snapshot

PASSENGERS = 1  # lines[].capacity[].cargo is the cargo id + 1: 1 means passengers (cargo id 0)
FREIGHT = 4  # cargo id 3


def fixture_clock(raw: dict[str, Any]) -> GameCalendarClock:
    """Eight calendar years of explicit test anchors, independent of production nominal conversion."""
    now, dated = raw["meta"]["gameTime"], raw["meta"].get("date")
    samples = [{"gameTime": now, "date": dated}]
    if dated:
        end = date(dated["year"], dated["month"], dated["day"])
        samples.insert(0, {"gameTime": now - 8 * YEAR, "date": end.replace(year=end.year - 8).isoformat()})
    return GameCalendarClock.from_samples(samples, context={"selectedTick": now, "isolation": "legacy-unverified"})


class Net:
    """Builds a snapshot with stations, towns, lines and vehicles."""

    def __init__(self, game_time: int = 10 * YEAR) -> None:
        self.data = base_snapshot(game_time)
        self.data["lines"], self.data["vehicles"], self.data["stations"], self.data["towns"] = [], [], [], []
        self.data["cargos"] = [
            {"id": 0, "name": "Passengers", "res": "::/cargos/passengers/passengers.cargo"},
            {"id": 3, "name": "Coal", "res": "::/cargos/coal/coal.cargo"},
        ]
        self._vehicle = 1000

    @property
    def now(self) -> int:
        return self.data["meta"]["gameTime"]

    def station(self, station_id: int, name: str, town_id: int | None, town_name: str | None, position=None) -> "Net":
        entry: dict[str, Any] = {"id": station_id, "name": name, "lines": []}
        if town_id is not None:
            entry["town"], entry["townName"] = town_id, town_name
        if position is not None:
            entry["position"] = position
        self.data["stations"].append(entry)
        if town_id is not None and not any(t["id"] == town_id for t in self.data["towns"]):
            self.data["towns"].append({"id": town_id, "name": town_name, "capacities": [100, 50, 10], "lineUsage": 0.1})
        return self

    def line(
        self,
        line_id: int,
        name: str,
        stations: list[int],
        *,
        profit: int = 0,
        cargo: int = PASSENGERS,
        load=(50, 100),
        carrier: str = "ROAD",
        age: float | None = 3.0,
        vehicles: int = 1,
        terminals: list[int] | None = None,
    ) -> "Net":
        ids = []
        for _ in range(vehicles if age is not None else 0):
            self._vehicle += 1
            ids.append(self._vehicle)
            self.data["vehicles"].append(
                {
                    "id": self._vehicle,
                    "name": f"V{self._vehicle}",
                    "carrier": carrier,
                    "state": "EN_ROUTE",
                    "line": line_id,
                    "purchaseTime": self.now - int(age * YEAR),
                    "profitYear": profit // max(vehicles, 1),
                    "models": [7],
                    "maintenanceState": 1.0,
                }
            )
        stops = []
        for index, station in enumerate(stations):
            stop: dict[str, Any] = {"stationGroup": station, "name": f"stop {index}"}
            if terminals is not None:
                stop["terminal"] = terminals[index]
            stops.append(stop)
        capacity = [{"cargo": cargo, "used": load[0], "capacity": load[1]}] if ids else []
        self.data["lines"].append(
            {
                "id": line_id,
                "name": name,
                "vehicles": ids,
                "stops": stops,
                "profitYear": profit,
                "transportedYear": 100,
                "capacity": capacity,
                "issues": [],
            }
        )
        return self

    def snapshot(self) -> Snapshot:
        return Snapshot(copy.deepcopy(self.data))

    def clock(self) -> GameCalendarClock:
        return fixture_clock(self.data)


def methodology(**parts: Any):
    """A tiny valid methodology; `parts` are merged over the minimal document."""
    data: dict[str, Any] = {
        "schema": "tf3c-methodology/1",
        "id": "test",
        "version": "1.0.0",
        "name": "Test",
        "description": "Test methodology.",
        "markers": {
            "ok": {"label": "ok"},
            "watch": {"label": "watch", "finding": "low"},
            "problem": {"label": "problem", "finding": "high"},
            "note": {"label": "note"},
        },
    }
    data.update(parts)
    return parse(json.dumps(data).encode("utf-8"))


def run(m, net: Net, **kwargs):
    kwargs.setdefault("clock", net.clock())
    return evaluate(m, net.snapshot(), **kwargs)


def rule(verdicts, rule_id: str):
    return next(r for r in verdicts.rules if r.id == rule_id)


def markers_of(verdicts, rule_id: str) -> dict[str, str]:
    """entity (or group) name -> marker."""
    return {(h.entity["name"] if h.entity else h.group["label"]): h.marker for h in rule(verdicts, rule_id).hits}


def cond(field: str, op: str, value: Any = None) -> dict[str, Any]:
    leaf: dict[str, Any] = {"field": field, "op": op}
    if op not in ("exists", "missing"):
        leaf["value"] = value
    return leaf


# ---------------------------------------------------------------------------
# Companion fixtures


def companion_with(paths, *snapshots: dict[str, Any]):
    """A Companion over `paths` with the given raw snapshot dicts ingested."""
    from conftest import write_snapshot
    from tf3companion.service import Companion

    for data in snapshots:
        write_snapshot(paths.snapshot_folder, data)
    return Companion(paths)


def troubled_company() -> dict[str, Any]:
    """A snapshot that triggers most engine findings (losses, load, issues, idle depot, closing industry, full stock)."""
    net = Net(game_time=10 * YEAR)
    net.station(1, "A", 10, "Alpha").station(2, "B", 20, "Beta")
    net.line(100, "Mature loser", [1, 2], profit=-300_000, age=3, load=(40, 100))
    net.line(101, "Young loser", [1, 2], profit=-50_000, age=0.3)
    net.line(102, "Crowded", [1, 2], profit=500_000, load=(95, 100))
    net.line(103, "Quiet", [1, 2], profit=10_000, load=(10, 100), vehicles=3)
    net.line(104, "Coal", [1, 2], profit=-80_000, cargo=FREIGHT, age=2)
    net.line(105, "Parked", [1, 2], age=None)
    net.data["lines"][0]["issues"] = [{"type": "NowhereToUnload", "stopIndex": 2, "cargo": 3}]
    net.data["vehicles"][0]["noPath"] = True
    net.data["vehicles"].append(
        {
            "id": 5000,
            "name": "Idle bus",
            "carrier": "ROAD",
            "state": "IN_DEPOT",
            "line": 0,
            "depot": 77,
            "daysInDepot": 90,
            "value": 12_000,
            "purchaseTime": net.now - YEAR,
        }
    )
    net.data["depots"] = [{"id": 77, "name": "Depot"}]
    net.data["industries"] = [
        {
            "id": 900,
            "name": "Old mine",
            "type": "::/industries/coal_mine/coal_mine.con",
            "closureTimeStamp": 123,
            "inputs": [],
            "outputs": [{"cargo": 3, "producedYear": 10, "shippedYear": 0}],
        }
    ]
    net.data["stocks"] = [
        {"kind": "industry", "owner": 900, "ownerName": "Old mine", "count": 95, "capacity": 100, "cargos": [3]}
    ]
    net.data["errors"] = ["collector: partial data"]
    return net.data
