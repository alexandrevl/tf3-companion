from tf3companion import analysis
from tf3companion.snapshot import Snapshot

from conftest import YEAR, base_snapshot


def titles(items, severity=None):
    return [f.title for f in items if severity is None or f.severity == severity]


def add_line(data, line_id, *, profit, vehicles_age_years=3.0, load=(50, 100), vehicles=1, **extra):
    now = data["meta"]["gameTime"]
    vehicle_ids = [line_id * 10 + i for i in range(vehicles)]
    data["lines"].append({
        "id": line_id, "name": f"L{line_id}", "vehicles": vehicle_ids, "stops": [],
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
    items = analysis.findings(Snapshot(data))
    assert "L1: loss over the last year" in titles(items, "high")
    assert "L2: loss over the last year" in titles(items, "low")
    losing = [f for f in items if f.code == "line_losing_money"]
    assert [(f.entity["id"], f.severity, f.category) for f in losing] == [
        (1, "high", "lines"), (2, "low", "lines")]
    assert "partial" not in losing[0].detail
    assert "partial" in losing[1].detail


def test_load_thresholds_flag_overloaded_and_underused_lines():
    data = base_snapshot()
    add_line(data, 1, profit=10, load=(95, 100))
    add_line(data, 2, profit=10, load=(10, 100), vehicles=3)
    add_line(data, 3, profit=10, load=(10, 100), vehicles=1)  # single vehicle: not "too many vehicles"
    items = analysis.findings(Snapshot(data))
    assert "L1: overloaded (95%)" in titles(items)
    assert "L2: underused (10%)" in titles(items)
    assert not any(t.startswith("L3:") for t in titles(items))
    assert [(f.code, f.category) for f in items] == [
        ("line_overloaded", "lines"), ("line_underused", "lines")]
    assert "instant reading, not an average" in items[1].detail


def test_line_issues_and_empty_lines_are_reported():
    data = base_snapshot()
    add_line(data, 1, profit=0, issues=[{"type": "NowhereToUnload", "stopIndex": 2, "cargo": 3}])
    data["lines"].append({"id": 2, "name": "Empty", "vehicles": [], "stops": [], "capacity": [], "issues": []})
    items = analysis.findings(Snapshot(data))
    issue = next(f for f in items if f.code == "line_config_issue")
    assert issue.severity == "high" and issue.category == "lines" and "Coal" in issue.detail
    empty = next(f for f in items if f.code == "line_no_vehicles")
    assert empty.title == "Empty: no vehicles"
    assert empty.severity == "medium" and empty.category == "lines"


def test_profit_drop_compares_with_previous_snapshot():
    prev = base_snapshot(game_time=9 * YEAR)
    cur = base_snapshot()
    cur["lines"][0]["profitYear"] = 300_000  # was 800_000
    items = analysis.findings(Snapshot(cur), Snapshot(prev))
    assert "Train A: profit dropping" in titles(items, "medium")
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
    items = analysis.findings(Snapshot(data))
    no_path = next(f for f in items if f.code == "vehicle_no_path")
    assert no_path.title == "Lost: no path" and no_path.severity == "high"
    depot = next(f for f in items if f.code == "vehicles_idle_in_depot")
    assert depot.title.startswith("1 vehicle") and "40,000" in depot.detail
    assert depot.severity == "medium" and [v["id"] for v in depot.evidence["vehicles"]] == [2]
    losing = next(f for f in items if f.code == "vehicle_losing_on_profitable_line")
    assert losing.title == "Surplus: loss on a profitable line" and losing.severity == "low"
    assert all(f.category == "vehicles" for f in items)


def test_closing_industry_and_collection_errors():
    data = base_snapshot()
    data["industries"] = [{"id": 50, "name": "Mine", "outputs": []}]
    data["problems"]["closingIndustries"] = [50]
    data["errors"] = ["towns: boom"]
    items = analysis.findings(Snapshot(data))
    closing = next(f for f in items if f.code == "industry_closing")
    assert closing.title == "Mine: scheduled to close" and closing.category == "industries"
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
    assert depot.code == "vehicles_idle_in_depot" and depot.entity is None
    assert depot.title == "3 vehicle(s) idle in depots"
    assert "60,000" in depot.detail
    assert [v["id"] for v in depot.evidence["vehicles"]] == [1, 2, 3]


def test_collection_errors_evidence_is_limited_to_twenty():
    data = base_snapshot()
    data["errors"] = [f"error {i}" for i in range(25)]
    finding, = analysis.findings(Snapshot(data))
    assert finding.code == "snapshot_collection_errors"
    assert finding.title == "Snapshot with 25 collection error(s)"
    assert finding.evidence == {"errors": data["errors"][:20]}


def test_findings_order_by_severity_then_category_then_title():
    data = base_snapshot()
    add_line(data, 2, profit=-100_000)
    add_line(data, 1, profit=-100_000)
    data["vehicles"].append({"id": 1, "name": "Lost", "noPath": True})
    data["industries"] = [{"id": 50, "name": "Mine", "closureTimeStamp": 1}]
    data["errors"] = ["collection failed"]
    items = analysis.findings(Snapshot(data))
    assert [(f.severity, f.category, f.title) for f in items] == [
        ("high", "industries", "Mine: scheduled to close"),
        ("high", "lines", "L1: loss over the last year"),
        ("high", "lines", "L2: loss over the last year"),
        ("high", "vehicles", "Lost: no path"),
        ("low", "data", "Snapshot with 1 collection error(s)"),
    ]
