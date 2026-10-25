"""Field registry: declared attributes and derived values against hand-computed fixtures."""

from __future__ import annotations

import pytest

from methodology_helpers import FREIGHT, PASSENGERS, Net
from tf3companion.methodology import fields as F


def test_unknown_and_dynamic_names():
    assert F.lookup("line.profit_yeer") is None
    assert F.suggest("line.profit_yeer") == "line.profit_year"
    assert F.lookup("vehicle.line.carrier").entity == "vehicle"
    assert F.lookup("stop.line.vehicle_count").entity == "stop"
    assert F.capture_name("line.name_capture.mode") == ("line", "mode")
    assert F.lookup("line.name_capture.mode").type == F.STRING


def record(net: Net, entity: str, index: int = 0, patterns=()):
    facts = F.Facts(net.snapshot(), tuple(patterns), clock=net.clock())
    return facts.records(entity)[index]


def test_line_derived_values():
    net = (
        Net()
        .station(1, "A", 10, "Alpha")
        .station(2, "B", 10, "Alpha")
        .station(3, "C", 20, "Beta")
        .line(100, "Bus x-IC-1", [1, 2, 3], profit=-120_000, load=(90, 100), age=2.5, vehicles=2)
    )
    line = record(net, "line")
    assert line.get("line.loss_year") == 120_000
    assert line.get("line.profit_year") == -120_000
    assert line.get("line.stop_towns") == [10, 20]
    assert line.get("line.first_stop_town") == 10
    assert line.get("line.town_count") == 2
    assert line.get("line.is_passenger_only") is True
    assert line.get("line.cargo_ids") == [0]
    assert line.get("line.cargo_keys") == ["passengers"]
    assert line.get("line.load") == pytest.approx(0.9)
    assert line.get("line.age_years") == pytest.approx(2.5)
    assert line.get("line.carrier") == "ROAD"
    assert line.get("line.vehicle_count") == 2 and line.get("line.stop_count") == 3
    assert F.Facts(net.snapshot()).label("town", 10) == "Alpha"


def test_profit_and_loss_edge_cases():
    net = Net().station(1, "A", 10, "Alpha").line(100, "L", [1], profit=5_000)
    line = record(net, "line")
    assert line.get("line.loss_year") == 0  # a profit is a zero loss, not a missing value
    net.data["lines"][0].pop("profitYear")
    assert record(net, "line").get("line.loss_year") is None


def test_freight_and_mixed_capacity_passenger_flag():
    net = Net().station(1, "A", 10, "Alpha").line(100, "Freight", [1], cargo=FREIGHT).line(101, "Empty", [1], age=None)
    assert record(net, "line", 0).get("line.is_passenger_only") is False
    assert record(net, "line", 0).get("line.cargo_ids") == [3]
    assert record(net, "line", 0).get("line.cargo_keys") == ["coal"]
    empty = record(net, "line", 1)
    assert empty.get("line.is_passenger_only") is None  # no capacity: unknown, not False
    assert empty.get("line.age_years") is None and empty.get("line.carrier") is None
    assert empty.get("line.vehicle_count") == 0
    net.data["lines"][0]["capacity"].append({"cargo": PASSENGERS, "used": 1, "capacity": 20})
    assert record(net, "line", 0).get("line.is_passenger_only") is False  # passengers plus freight


def test_stop_without_station_has_no_town():
    net = Net().station(1, "A", 10, "Alpha").line(100, "L", [1, 99], terminals=[0, 1])
    line = record(net, "line")
    assert line.get("line.stop_towns") == [10]  # the unresolved stop contributes nothing
    stops = net.snapshot()
    facts = F.Facts(stops)
    first, second = facts.records("stop")
    assert first.get("stop.town") == 10 and second.get("stop.town") is None
    assert first.get("stop.terminal") == 0 and second.get("stop.terminal") == 1
    assert second.get("stop.line.name") == "L"


def test_vehicle_model_family_and_age():
    net = Net().station(1, "A", 10, "Alpha").line(100, "L", [1], age=1.5)
    net.data["models"] = [{"id": 7, "res": "::/vehicle/helicopter/bell/bell.mdl"}]
    vehicle = record(net, "vehicle")
    assert vehicle.get("vehicle.model_family") == "helicopter"
    assert vehicle.get("vehicle.age_years") == pytest.approx(1.5)
    assert vehicle.get("vehicle.line.name") == "L"
    assert F.model_family("::/vehicle/bus/x/x.mdl") == "bus"
    assert F.model_family("vehicle/train/a.mdl") == "train"
    assert F.model_family("vehicle/a.mdl") is None  # nothing between the vehicle segment and the file: unknown
    assert F.model_family(None) is None


def test_industry_and_stock_ratios():
    net = Net()
    net.data["industries"] = [
        {
            "id": 1,
            "name": "Refinery",
            "type": "::/industries/oil_refinery/oil_refinery.con",
            "level": 2,
            "productionRating": 0.8,
            "inputs": [
                {"cargo": 1, "deliveredYear": 30, "maxConsumptionYear": 60},
                {"cargo": 2, "deliveredYear": 10, "maxConsumptionYear": 40},
            ],
            "outputs": [
                {"cargo": 3, "producedYear": 50, "shippedYear": 20},
                {"cargo": 4, "producedYear": 50, "shippedYear": 30},
            ],
        },
        {
            "id": 2,
            "name": "Mine",
            "type": "::/industries/coal_mine/coal_mine.con",
            "inputs": [],
            "outputs": [{"cargo": 3, "producedYear": 0, "shippedYear": 0}],
        },
    ]
    net.data["stocks"] = [
        {"kind": "industry", "owner": 1, "ownerName": "Refinery", "count": 45, "capacity": 50},
        {"kind": "warehouse", "owner": 3, "ownerName": "W", "count": 5, "capacity": 0},
    ]
    refinery, mine = record(net, "industry", 0), record(net, "industry", 1)
    assert refinery.get("industry.shipped_ratio") == pytest.approx(0.5)
    assert refinery.get("industry.input_delivery_ratio") == pytest.approx(0.4)
    assert mine.get("industry.shipped_ratio") is None  # produces nothing: not a zero ratio
    assert mine.get("industry.input_delivery_ratio") is None
    assert refinery.get("industry.closing") is False
    assert record(net, "stock", 0).get("stock.fill_ratio") == pytest.approx(0.9)
    assert record(net, "stock", 1).get("stock.fill_ratio") is None


def test_town_fields_and_positions():
    net = (
        Net()
        .station(1, "A", 10, "Alpha", position=[0, 0, 0])
        .station(2, "B", 20, "Beta", position=[3000, 4000, 0])
        .line(100, "L", [1, 2])
    )
    town = record(net, "town", 0)
    assert town.get("town.capacity_sum") == 160 and town.get("town.line_usage") == 0.1
    assert town.get("town.pair_distance_km") == [pytest.approx(5.0)]
    line = record(net, "line")
    assert line.get("line.route_km") == pytest.approx(5.0)
    assert line.get("line.stop_distances_km") == [pytest.approx(5.0)]


def test_positions_absent_means_distance_missing():
    net = Net().station(1, "A", 10, "Alpha").station(2, "B", 20, "Beta").line(100, "L", [1, 2])
    assert record(net, "line").get("line.route_km") is None


def test_probe_distinguishes_absent_data_from_empty_sections():
    snap = Net().station(1, "A", 10, "Alpha").line(100, "L", [1]).snapshot()
    assert F.probe_path(snap, "lines[].profitYear") is True
    assert F.probe_path(snap, "lines[].stops[].terminal") is False  # stops exist but none has a terminal
    assert F.probe_path(snap, "stations[].position") is False
    assert F.probe_path(snap, "industries[].type") is None  # no industries at all: inconclusive
    assert F.probe_path(snap, "meta.yearDuration") is True
