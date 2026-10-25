from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from tf3companion import luadata
from tf3companion.paths import Paths

YEAR = 1000  # game time units per year in fixtures


def base_snapshot(game_time: int = 10 * YEAR) -> dict[str, Any]:
    """A small but complete company: one healthy line, plus room for tests to add trouble."""
    return copy.deepcopy(
        {
            "meta": {
                "schemaVersion": 1,
                "gameTime": game_time,
                "yearDuration": YEAR,
                "date": {"year": 1980, "month": 1, "day": 1},
                "reason": "interval",
            },
            "company": {"balance": 5_000_000, "loan": 0, "earnings": 1_000_000},
            "cargos": [{"id": 0, "name": "Passengers"}, {"id": 3, "name": "Coal"}],
            "models": [{"id": 7, "res": "vehicle/train/a.mdl"}],
            "lines": [
                {
                    "id": 100,
                    "name": "Train A",
                    "vehicles": [1000],
                    "stops": [{"stationGroup": 500}, {"stationGroup": 501}],
                    "profitYear": 800_000,
                    "transportedYear": 5000,
                    "rate": 300,
                    "capacity": [{"cargo": 0, "used": 60, "capacity": 100}],
                    "issues": [],
                },
            ],
            "vehicles": [
                {
                    "id": 1000,
                    "name": "Train 1",
                    "carrier": "RAIL",
                    "state": "EN_ROUTE",
                    "line": 100,
                    "purchaseTime": game_time - 3 * YEAR,
                    "profitYear": 800_000,
                    "models": [7],
                    "value": 100_000,
                },
            ],
            "stations": [{"id": 500, "name": "Centre", "lines": [100]}, {"id": 501, "name": "Port", "lines": [100]}],
            "industries": [],
            "towns": [{"id": 900, "name": "Town", "capacities": [500, 200, 100], "lineUsage": 0.4}],
            "problems": {"noPathVehicles": [], "closingIndustries": []},
            "errors": [],
        }
    )


def write_snapshot(folder: Path, data: dict[str, Any]) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"tf3c_snap_{data['meta']['gameTime']:015d}.lua"
    path.write_text(luadata.dumps(data), encoding="utf-8")
    return path


@pytest.fixture
def paths(tmp_path: Path) -> Paths:
    userdata = tmp_path / "userdata"
    userdata.mkdir()
    data = tmp_path / "data"
    data.mkdir()
    return Paths(userdata=userdata, data=data)
