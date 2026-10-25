from conftest import YEAR, base_snapshot
from methodology_helpers import fixture_clock
from tf3companion import analysis
from tf3companion.snapshot import Snapshot


def add_line(data, line_id, *, profit, vehicles_age_years=3.0, load=(50, 100), vehicles=1, **extra):
    now = data["meta"]["gameTime"]
    vehicle_ids = [line_id * 10 + i for i in range(vehicles)]
    data["lines"].append({
        "id": line_id, "name": f"L{line_id}", "vehicles": vehicle_ids,
        "stops": [{"stationGroup": 20}, {"stationGroup": 21}],
        "profitYear": profit, "capacity": [{"cargo": 0, "used": load[0], "capacity": load[1]}], "issues": [],
        **extra,
    })
    for vid in vehicle_ids:
        data["vehicles"].append({
            "id": vid, "name": f"V{vid}", "state": "EN_ROUTE", "line": line_id,
            "purchaseTime": now - int(vehicles_age_years * YEAR), "profitYear": profit // max(vehicles, 1),
        })


def test_healthy_company_has_no_findings():
    assert analysis.findings(Snapshot(base_snapshot())) == []


def test_losing_line_severity_depends_on_line_maturity():
    data = base_snapshot()
    add_line(data, 1, profit=-200_000, vehicles_age_years=2)
    add_line(data, 2, profit=-50_000, vehicles_age_years=0.4)
    items = analysis.findings(Snapshot(data), clock=fixture_clock(data))
    losing = [f for f in items if f.code == "line_losing_money"]
    assert [(f.entity["id"], f.severity, f.category) for f in losing] == [
        (1, "high", "lines"), (2, "low", "lines")]


def test_load_thresholds_flag_overloaded_and_underused_lines():
    data = base_snapshot()
    add_line(data, 1, profit=10, load=(95, 100))
    add_line(data, 2, profit=10, load=(10, 100), vehicles=3)
    add_line(data, 3, profit=10, load=(10, 100), vehicles=1)  # single vehicle: not "too many vehicles"
    items = analysis.findings(Snapshot(data))
    assert [(f.code, f.category) for f in items] == [
        ("line_overloaded", "lines"), ("line_underused", "lines")]


def test_line_issues_and_empty_lines_are_reported():
    data = base_snapshot()
    add_line(data, 1, profit=0, issues=[{"type": "NowhereToUnload", "stopIndex": 2, "cargo": 3}])
    data["lines"].append({"id": 2, "name": "Empty", "vehicles": [], "stops": [1, 2], "capacity": [], "issues": []})
    items = analysis.findings(Snapshot(data))
    issue = next(f for f in items if f.code == "line_config_issue")
    assert issue.severity == "high" and issue.category == "lines"
    empty = next(f for f in items if f.code == "line_no_vehicles")
    assert empty.severity == "medium" and empty.category == "lines"


def test_orphan_and_no_stop_lines():
    data = base_snapshot()
    data["lines"].append({"id": 10, "name": "Orphan", "vehicles": [], "stops": [], "capacity": [], "issues": []})
    data["lines"].append({"id": 11, "name": "OneStop", "vehicles": [110], "stops": [1], "capacity": [], "issues": []})
    data["vehicles"].append({"id": 110, "name": "V110", "line": 11, "state": "EN_ROUTE"})
    items = analysis.findings(Snapshot(data))
    assert any(f.code == "line_orphan" and f.entity["id"] == 10 for f in items)
    assert any(f.code == "line_no_stops" and f.entity["id"] == 11 for f in items)

def test_profit_drop_compares_with_previous_snapshot():
    prev = base_snapshot(game_time=9 * YEAR)
    cur = base_snapshot()
    cur["lines"][0]["profitYear"] = 300_000  # was 800_000
    items = analysis.findings(Snapshot(cur), Snapshot(prev))
    drop = next(f for f in items if f.code == "line_profit_dropping")
    assert drop.category == "lines"
    assert drop.evidence == {"previous": 800_000, "current": 300_000}
    small = base_snapshot()
    small["lines"][0]["profitYear"] = 750_000
    assert not any(f.code == "line_profit_dropping" for f in analysis.findings(Snapshot(small), Snapshot(prev)))


def test_vehicle_findings():
    data = base_snapshot()
    data["vehicles"] += [
        {"id": 1, "name": "Lost", "state": "EN_ROUTE", "line": 100, "noPath": True},
        {"id": 2, "name": "Idle", "state": "IN_DEPOT", "line": None, "daysInDepot": 90, "value": 40_000},
        {"id": 3, "name": "Recent", "state": "IN_DEPOT", "line": None, "daysInDepot": 5, "value": 99},
        {"id": 4, "name": "Surplus", "state": "EN_ROUTE", "line": 100, "profitYear": -20_000,
         "purchaseTime": data["meta"]["gameTime"] - 2 * YEAR},
    ]
    items = analysis.findings(Snapshot(data), clock=fixture_clock(data))
    no_path = next(f for f in items if f.code == "vehicle_no_path")
    assert no_path.entity["id"] == 1 and no_path.severity == "high"
    depot = next(f for f in items if f.code == "fleet_idle_in_depot")
    assert depot.severity == "medium" and [v["id"] for v in depot.evidence["vehicles"]] == [2]
    losing = next(f for f in items if f.code == "vehicle_losing_on_profitable_line")
    assert losing.entity["id"] == 4 and losing.severity == "low"
    assert all(f.category == "vehicles" for f in items)


def test_closing_industry_and_collection_errors():
    data = base_snapshot()
    data["industries"] = [{"id": 50, "name": "Mine", "outputs": []}]
    data["problems"]["closingIndustries"] = [50]
    data["errors"] = ["towns: boom"]
    items = analysis.findings(Snapshot(data))
    closing = next(f for f in items if f.code == "industry_closing")
    assert closing.entity["id"] == 50 and closing.category == "industries"
    assert closing.severity == "high"
    errors = next(f for f in items if f.code == "snapshot_collection_errors")
    assert errors.category == "data" and errors.severity == "low"
    assert errors.evidence == {"errors": ["towns: boom"]}
    assert "incomplete" in errors.detail
    assert items[0].severity == "high"  # sorted by severity


def test_opportunities_pair_unshipped_cargo_with_nearest_consumers():
    data = base_snapshot()
    data["industries"] = [
        {"id": 1, "name": "Mine", "position": [0, 0, 0],
         "outputs": [{"cargo": 3, "producedYear": 400, "maxProductionYear": 800, "shippedYear": 100}]},
        {"id": 2, "name": "Distant plant", "position": [9000, 0, 0], "inputs": [{"cargo": 3, "deliveredYear": 0}]},
        {"id": 3, "name": "Nearby plant", "position": [3000, 4000, 0], "inputs": [{"cargo": 3, "deliveredYear": 50}]},
        {"id": 4, "name": "Served mine", "position": [0, 0, 0],
         "outputs": [{"cargo": 3, "producedYear": 400, "maxProductionYear": 400, "shippedYear": 390}]},
        {"id": 5, "name": "Idle factory", "position": [20000, 0, 0],
         "inputs": [{"cargo": 3, "deliveredYear": 0}, {"cargo": 0, "deliveredYear": 20}],
         "outputs": [{"cargo": 0, "producedYear": 0, "maxProductionYear": 900, "shippedYear": 0}]},
    ]
    ops = analysis.opportunities(Snapshot(data))
    # cargo actually waiting comes first, even if idle capacity elsewhere is larger
    assert [(o["producer"]["name"], o["kind"]) for o in ops] == [("Mine", "unshipped"), ("Idle factory", "needs_inputs")]
    op = ops[0]
    assert op["cargo"] == "Coal" and op["unshippedYear"] == 300
    assert [(c["name"], c["distanceKm"]) for c in op["nearestConsumers"]] == [
        ("Nearby plant", 5.0), ("Distant plant", 9.0), ("Idle factory", 20.0)]
    assert ops[1]["idleCapacityYear"] == 900 and ops[1]["missingInputs"] == ["Coal"]


def test_company_overview_reports_deltas():
    prev = base_snapshot(game_time=9 * YEAR)
    cur = base_snapshot()
    cur["company"]["balance"] = 6_000_000
    add_line(cur, 1, profit=-5)
    ov = analysis.company_overview(Snapshot(cur), Snapshot(prev))
    assert ov["previous"]["balanceDelta"] == 1_000_000
    assert ov["previous"]["linesDelta"] == 1
    assert ov["linesLosingMoney"] == 1


def test_finding_codes_are_stable_across_snapshots():
    previous = base_snapshot(game_time=9 * YEAR)
    current = base_snapshot()
    add_line(previous, 1, profit=-100_000)
    add_line(current, 1, profit=-200_000)
    old = analysis.findings(Snapshot(previous))
    new = analysis.findings(Snapshot(current))
    assert [f.code for f in old] == [f.code for f in new] == ["line_losing_money"]


def test_idle_depot_finding_aggregates_vehicles_and_value():
    data = base_snapshot()
    data["vehicles"].extend(
        {"id": i, "name": f"Idle {i}", "state": "IN_DEPOT", "line": None,
         "daysInDepot": 40, "value": 10_000 * i}
        for i in range(1, 4)
    )
    items = analysis.findings(Snapshot(data))
    assert len(items) == 1
    depot = items[0]
    assert depot.code == "fleet_idle_in_depot" and depot.entity["name"] == "Unknown depot"
    assert [v["id"] for v in depot.evidence["vehicles"]] == [1, 2, 3]


def test_collection_errors_evidence_is_limited_to_twenty():
    data = base_snapshot()
    data["errors"] = [f"error {i}" for i in range(25)]
    finding, = analysis.findings(Snapshot(data))
    assert finding.code == "snapshot_collection_errors"
    assert finding.evidence == {"errors": data["errors"][:20]}


def test_high_severity_findings_precede_collection_warnings():
    data = base_snapshot()
    add_line(data, 2, profit=-100_000)
    add_line(data, 1, profit=-100_000)
    data["vehicles"].append({"id": 1, "name": "Lost", "noPath": True})
    data["industries"] = [{"id": 50, "name": "Mine", "closureTimeStamp": 1}]
    data["errors"] = ["collection failed"]
    items = analysis.findings(Snapshot(data), clock=fixture_clock(data))
    assert [(f.severity, f.category, f.entity["id"] if f.entity else None) for f in items] == [
        ("high", "industries", 50),
        ("high", "lines", 1),
        ("high", "lines", 2),
        ("high", "vehicles", 1),
        ("low", "data", None),
    ]


def test_full_stocks_and_unserved_summary():
    data = base_snapshot()
    data["industries"] = [
        {"id": 1, "name": "Served Mill", "outputs": [{"cargo": 1, "shippedYear": 100}]},
        {"id": 2, "name": "Unserved Mill", "outputs": [{"cargo": 2, "shippedYear": 0}]},
    ]
    data["stocks"] = [
        {"kind": "industry", "owner": 1, "ownerName": "Served Mill", "cargos": [1], "count": 95, "capacity": 100},
        {"kind": "industry", "owner": 2, "ownerName": "Unserved Mill", "cargos": [2], "count": 92, "capacity": 100},
        {"kind": "warehouse", "owner": 3, "ownerName": "Central WH", "cargos": [1], "count": 100, "capacity": 100},
    ]
    items = analysis.findings(Snapshot(data))
    codes = [f.code for f in items]
    assert "industry_output_full" in codes
    assert "industries_output_full_unserved" in codes
    assert "warehouse_full" in codes


def test_load_trend_uses_distinct_monthly_samples():
    samples = []
    for month, used in ((1, 20), (2, 50), (3, 80)):
        data = base_snapshot(game_time=YEAR + month * (YEAR // 12))
        data["meta"]["date"] = {"year": 1984, "month": month, "day": 1}
        data["lines"][0]["capacity"][0]["used"] = used
        samples.append(Snapshot(data))
    snap1, snap2, snap3 = samples
    trend = analysis.load_trend([snap1, snap2, snap3])
    assert len(trend) == 1
    assert trend[0]["samples"] == 3
    assert trend[0]["meanLoad"] == 0.5
    assert trend[0]["latestLoad"] == 0.8
    assert trend[0]["slope"] > 0

    fit_pending = analysis.fleet_fit(snap3, None)
    assert fit_pending["status"] == "unavailable"
