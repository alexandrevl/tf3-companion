"""Line detail: capacity entries name the cargo they carry and list only positive capacity (P-010/P-011)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from conftest import base_snapshot, write_snapshot
from tf3companion import mcp_server
from tf3companion.cli import main
from tf3companion.service import Companion

CARGO_COUNT = 37
CRUDE_OIL_ID = 18


def freight_snapshot() -> dict[str, Any]:
    """Thirty-seven cargo types; the line's stored capacity lists all of them (index = id + 1), one carried."""
    data = base_snapshot()
    data["cargos"] = [{"id": i, "name": "Passengers" if i == 0 else f"Cargo {i}"} for i in range(CARGO_COUNT)]
    data["cargos"][CRUDE_OIL_ID]["name"] = "Crude Oil"
    capacity = [{"cargo": index, "used": 0, "capacity": 0} for index in range(1, CARGO_COUNT + 1)]
    capacity[CRUDE_OIL_ID] = {"cargo": CRUDE_OIL_ID + 1, "used": 12, "capacity": 80}
    data["lines"][0]["capacity"] = capacity
    data["lines"][0]["issues"] = [
        {"type": "VehicleUseless", "stopIndex": 0, "cargo": 3},
        {"type": "LineCargoConfig", "stopIndex": 1, "cargo": 999},
    ]
    return data


def passenger_snapshot() -> dict[str, Any]:
    data = freight_snapshot()
    data["lines"][0]["capacity"] = [{"cargo": 1, "used": 30, "capacity": 100}] + [
        {"cargo": index, "used": 0, "capacity": 0} for index in range(2, CARGO_COUNT + 1)
    ]
    data["lines"][0]["issues"] = []
    return data


@pytest.fixture
def isolated(paths, monkeypatch):
    monkeypatch.setenv("TF3C_DATA_DIR", str(paths.data))
    monkeypatch.setenv("TF3C_USERDATA_DIR", str(paths.userdata))
    return paths


def store(paths, data: dict[str, Any]) -> None:
    write_snapshot(paths.snapshot_folder, data)


def service_detail(paths) -> dict[str, Any]:
    companion = Companion(paths)
    try:
        return companion.line_detail("Train A")
    finally:
        companion.close()


def test_freight_line_lists_only_the_carried_cargo_by_its_real_name(isolated):
    store(isolated, freight_snapshot())
    capacity = service_detail(isolated)["capacity"]
    assert len(capacity) == 1
    assert capacity[0]["cargo"] == "Crude Oil"
    assert (capacity[0]["used"], capacity[0]["capacity"]) == (12, 80)


def test_passenger_line_names_passengers(isolated):
    store(isolated, passenger_snapshot())
    capacity = service_detail(isolated)["capacity"]
    assert [(c["cargo"], c["capacity"]) for c in capacity] == [("Passengers", 100)]


def test_a_line_without_positive_capacity_reports_an_empty_list(isolated):
    data = freight_snapshot()
    for entry in data["lines"][0]["capacity"]:
        entry["capacity"] = 0
    store(isolated, data)
    assert service_detail(isolated)["capacity"] == []


def test_issue_cargo_that_cannot_be_resolved_is_marked_unknown(isolated):
    store(isolated, freight_snapshot())
    issues = service_detail(isolated)["issues"]
    resolved, unresolved = issues
    assert resolved["cargo"] == "Cargo 3"
    assert "999" in unresolved["cargo"] and "nknown" in unresolved["cargo"]
    assert all(name not in unresolved["cargo"] for name in ("Crude Oil", "Cargo 3"))


def test_capacity_entry_with_an_unresolvable_index_is_marked_unknown(isolated):
    data = freight_snapshot()
    data["lines"][0]["capacity"] = [{"cargo": 500, "used": 1, "capacity": 9}]
    store(isolated, data)
    capacity = service_detail(isolated)["capacity"]
    assert len(capacity) == 1 and "nknown" in capacity[0]["cargo"]


def test_cli_and_mcp_show_the_same_capacity(isolated, capsys):
    store(isolated, freight_snapshot())
    capsys.readouterr()
    assert main(["line", "Train A"]) == 0
    via_cli = json.loads(capsys.readouterr().out)["capacity"]
    via_mcp = mcp_server.line_detail("Train A")["capacity"]
    assert via_cli == via_mcp
    assert [c["cargo"] for c in via_cli] == ["Crude Oil"]
