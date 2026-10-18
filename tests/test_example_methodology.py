"""Documented boundaries of the packaged optional `local-feeder-intercity-trunk` example.

Self-contained expectations: intercity loss and the town feeder-cost ratio are strictly greater than their
tolerances, instantaneous load is greater-or-equal, maintenance is strictly below its limits, and aircraft
per terminal screens at watch from 3.0 and problem from 3.5. The aircraft markers are policy screening, never
a measured capacity, arrival rate or congestion; absent terminals make the rule unavailable, never zero.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from conftest import YEAR
from methodology_helpers import FREIGHT, Net, markers_of, rule
from tf3companion.methodology import evaluate, load_file

EXAMPLE = Path(__file__).parent.parent / "src" / "tf3companion" / "methodology" / "examples" / "local-feeder-intercity-trunk.tf3c-methodology.json"


def example_net() -> Net:
    net = Net()
    for station, town, name in [(1, 10, "Alpha"), (2, 20, "Beta"), (3, 30, "Gamma"), (4, 40, "Delta"), (5, 50, "Epsilon"),
                                (6, 60, "Zeta"), (7, 70, "Airfield"), (8, 80, "Airport 8"), (9, 90, "Airport 9"),
                                (10, 100, "Mu"), (11, 110, "Nu")]:
        net.station(station, f"Stn {name}", town, name)
    # intercity lines: loss boundaries
    net.line(200, "Bus IC-exact-Alp-Bet-IC-1", [1, 2], profit=-100_000)
    net.line(201, "Bus IC-over-Alp-Bet-IC-2", [1, 2], profit=-100_001)
    net.line(202, "Bus IC-small-Alp-Bet-IC-3", [1, 2], profit=-40_000)
    net.line(203, "Bus IC-profit-Alp-Bet-IC-4", [1, 2], profit=15_000)
    # freight: maturity boundaries and a line without vehicles
    net.line(210, "RC Coal-young-Alp-Bet-IC-5", [1, 2], profit=-9_000, cargo=FREIGHT, age=2.99)
    net.line(211, "RC Coal-old-Alp-Bet-IC-6", [1, 2], profit=-9_000, cargo=FREIGHT, age=3.01)
    net.line(212, "RC Coal-three-Alp-Bet-IC-7", [1, 2], profit=-9_000, cargo=FREIGHT, age=3.0)
    net.line(213, "RC Coal-novehicles-Alp-Bet-IC-8", [1, 2], profit=-9_000, age=None)
    net.line(214, "RC Coal-earning-Alp-Bet-IC-9", [1, 2], profit=9_000, cargo=FREIGHT)
    # load boundaries
    net.line(220, "Bus Load-exact-Alp-LO-5", [1, 1], profit=1, load=(90, 100))
    net.line(221, "Bus Load-below-Alp-LO-6", [1, 1], profit=1, load=(899, 1000))
    # town balance: exactly at, just over and without intercity profit
    net.line(300, "Bus Local-Mu-LO-1", [10, 10], profit=-25_000, load=(1, 100))
    net.line(301, "Bus Trunk-Mu-Nu-IC-10", [10, 11], profit=100_000, load=(1, 100))
    net.line(302, "Bus Local-Gam-LO-1", [3, 3], profit=-25_001, load=(1, 100))
    net.line(303, "Bus Trunk-Gam-Del-IC-1", [3, 4], profit=100_000, load=(1, 100))
    net.line(304, "Bus Local-Eps-LO-1", [5, 5], profit=-10, load=(1, 100))
    net.line(305, "Bus Trunk-Eps-Zet-IC-1", [5, 6], profit=0, load=(1, 100))
    net.line(306, "Bus Local-Nowhere-LO-9", [99, 99], profit=-5, load=(1, 100))  # stops without a station
    # air stations: aircraft per terminal exactly 3.0, 3.5 and 2.5
    net.line(400, "AP Air-A-Ams-Rot-IC-1", [7, 7], carrier="AIR", vehicles=6, terminals=[0, 1])
    net.line(401, "AP Air-B-Ams-Rot-IC-2", [8, 8], carrier="AIR", vehicles=7, terminals=[0, 1])
    net.line(402, "AP Air-C-Ams-Rot-IC-3", [9, 9], carrier="AIR", vehicles=5, terminals=[0, 1])
    for line in net.data["lines"]:
        line.setdefault("capacity", [])
    # maintenance boundaries on three single-vehicle helicopter lines
    for number, state in ((500, 0.69), (501, 0.70), (502, 0.84), (503, 0.85)):
        net.line(number, f"HC Heli-{state}-Alp-IC-1", [1, 2], profit=1, load=(1, 100))
    for vehicle in net.data["vehicles"]:
        line = next(l for l in net.data["lines"] if l["id"] == vehicle["line"])
        for number, state in ((500, 0.69), (501, 0.70), (502, 0.84), (503, 0.85)):
            if line["id"] == number:
                vehicle["maintenanceState"] = state
    return net


@pytest.fixture(scope="module")
def verdicts():
    net = example_net()
    return evaluate(load_file(EXAMPLE), net.snapshot(), clock=net.clock())


def test_intercity_loss_is_strictly_greater_than_the_tolerance(verdicts):
    markers = markers_of(verdicts, "intercity-result")
    assert markers["Bus IC-exact-Alp-Bet-IC-1"] == "watch"      # exactly 100,000 is within tolerance
    assert markers["Bus IC-over-Alp-Bet-IC-2"] == "problem"
    assert markers["Bus IC-small-Alp-Bet-IC-3"] == "watch"
    assert markers["Bus IC-profit-Alp-Bet-IC-4"] == "ok"


def test_freight_is_maturing_below_three_years_and_a_problem_from_three(verdicts):
    markers = markers_of(verdicts, "freight-result")
    assert markers["RC Coal-young-Alp-Bet-IC-5"] == "maturing"
    assert markers["RC Coal-old-Alp-Bet-IC-6"] == "problem"
    assert markers["RC Coal-three-Alp-Bet-IC-7"] == "problem"   # exactly 3 years is no longer below the tolerance
    assert markers["RC Coal-novehicles-Alp-Bet-IC-8"] == "maturing"  # no vehicles: age unknown, so still maturing
    assert markers["RC Coal-earning-Alp-Bet-IC-9"] == "ok"


def test_load_is_flagged_from_exactly_ninety_percent(verdicts):
    markers = markers_of(verdicts, "high-load")
    assert markers["Bus Load-exact-Alp-LO-5"] == "watch"
    assert "Bus Load-below-Alp-LO-6" not in markers
    assert "n/a" not in rule(verdicts, "high-load").hits[0].message and "90%" in next(
        h.message for h in rule(verdicts, "high-load").hits if h.entity["name"] == "Bus Load-exact-Alp-LO-5")


def test_local_lines_that_lose_money_are_within_rule_never_a_finding(verdicts):
    markers = markers_of(verdicts, "local-result")
    assert markers["Bus Local-Mu-LO-1"] == "local-loss-within-rule" and markers["Bus Load-exact-Alp-LO-5"] == "ok"


def test_town_balance_ratio_is_strictly_greater_than_the_tolerance(verdicts):
    result = rule(verdicts, "town-feeder-balance")
    groups = {g["group"]: g for g in result.groups}
    assert groups["Mu"]["marker"] == "local-loss-within-rule"               # exactly 0.25
    assert groups["Mu"]["measures"]["feeder_cost_ratio"] == 0.25
    assert groups["Gamma"]["marker"] == "problem"                           # 25,001 / 100,000
    assert groups["Epsilon"]["marker"] == "problem"                         # no intercity profit
    assert groups["Epsilon"]["measures"]["feeder_cost_ratio"] is None       # ratio not applicable
    assert "Beta" not in groups and "Delta" not in groups and "Nu" not in groups  # no local line there
    assert all(label != "?" for label in groups)                            # no placeholder town bucket
    assert result.excluded_members >= 1                                     # the stop without a station is counted


def test_aircraft_per_terminal_screening(verdicts):
    markers = markers_of(verdicts, "air-station-pressure")
    assert markers == {"Stn Airfield": "watch", "Stn Airport 8": "problem", "Stn Airport 9": "ok"}
    groups = {g["group"]: g["measures"]["fleet_per_terminal"] for g in rule(verdicts, "air-station-pressure").groups}
    assert groups == {"Stn Airfield": 3.0, "Stn Airport 8": 3.5, "Stn Airport 9": 2.5}


def test_maintenance_markers_are_strictly_below_the_limits(verdicts):
    by_state = {}
    for hit in rule(verdicts, "vehicle-maintenance").hits:
        by_state[hit.evidence["vehicle.maintenance_state"]] = hit.marker
    assert by_state[0.69] == "problem"
    assert by_state[0.70] == "watch"      # exactly 0.70 is not below 0.70
    assert by_state[0.84] == "watch"
    assert by_state[0.85] == "ok"         # exactly 0.85 is not below 0.85


def test_helicopters_surface_through_the_role_table(verdicts):
    table = verdicts.tables[0]
    assert table.status == "ok" and table.total == 4
    assert [row[2] for row in table.rows] == [0.69, 0.70, 0.84, 0.85]  # sorted worst first


def test_every_line_gets_a_role_and_none_is_unclassified(verdicts):
    summary = verdicts.roles["line"]
    assert summary.unclassified == 0
    assert {r["id"]: r["count"] for r in summary.roles}["local-passenger"] >= 5


def test_aircraft_screening_is_policy_guidance_not_a_congestion_claim(verdicts):
    result = rule(verdicts, "air-station-pressure")
    hits = {h.entity["name"] if h.entity else h.group["label"]: h.message for h in result.hits}
    assert "check the game" in hits["Stn Airfield"] and "Not capacity or queue" in hits["Stn Airfield"]
    assert "check the game" in hits["Stn Airport 8"] and "Not capacity or queue" in hits["Stn Airport 8"]
    assert "Stn Airport 9" not in hits or "Not capacity" not in hits["Stn Airport 9"]


def test_missing_terminals_make_the_aircraft_rule_unavailable_not_zero():
    net = Net()
    net.station(7, "Stn Field", 70, "Airfield")
    net.line(400, "Air line", [7, 7], carrier="AIR", vehicles=6)           # stops carry no terminal data
    for line in net.data["lines"]:
        line.setdefault("capacity", [])
    result = evaluate(load_file(EXAMPLE), net.snapshot(), clock=net.clock())
    air = rule(result, "air-station-pressure")
    assert air.status == "skipped" and air.reason == "missing data: lines[].stops[].terminal"
    assert air.groups == [] and air.hits == []
    assert {"kind": "rule", "id": "air-station-pressure", "reason": "missing data: lines[].stops[].terminal"} in result.skipped
