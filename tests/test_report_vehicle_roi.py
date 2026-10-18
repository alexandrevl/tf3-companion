import pytest
from html.parser import HTMLParser

from conftest import YEAR
from tf3companion import report_vehicle_roi as vroi
from tf3companion.reports import Chart, Table, render_html, render_markdown
from tf3companion.snapshot import Snapshot
from tf3companion.store import Store

PASSENGERS, COAL = 0, 3
BUS_A, BUS_B, BUS_C, TRUCK = 11, 12, 13, 14


def _models(bus_b_name="Bus B"):
    return [
        {"id": BUS_A, "res": "vehicle/bus/a.mdl", "name": "Bus A", "price": 400_000, "runningCosts": 50_000, "lifespan": 20_000},
        {"id": BUS_B, "res": "vehicle/bus/b.mdl", "name": bus_b_name, "price": 500_000, "runningCosts": 80_000, "lifespan": 20_000},
        {"id": BUS_C, "res": "vehicle/bus/c.mdl", "name": "Bus C", "price": 300_000, "runningCosts": 40_000, "lifespan": 20_000},
        {"id": TRUCK, "res": "vehicle/truck/t.mdl", "name": "Truck T", "price": 600_000, "runningCosts": 90_000, "lifespan": 20_000},
    ]


def _catalog(units=None):
    cat = [
        {"id": 1, "res": "vehicle/bus/a.mdl", "name": "Bus A", "carrier": "ROAD", "yearFrom": 1970, "yearTo": 0, "available": True,
         "price": 400_000, "runningCosts": 50_000, "lifespan": 20_000, "topSpeed": 20.0, "capacity": [{"cargo": PASSENGERS, "capacity": 20}]},
        {"id": 2, "res": "vehicle/bus/b.mdl", "name": "Bus B", "carrier": "ROAD", "yearFrom": 1970, "yearTo": 0, "available": True,
         "price": 500_000, "runningCosts": 80_000, "lifespan": 20_000, "topSpeed": 18.0, "capacity": [{"cargo": PASSENGERS, "capacity": 40}]},
        {"id": 3, "res": "vehicle/bus/new.mdl", "name": "Bus New", "carrier": "ROAD", "yearFrom": 1975, "yearTo": 0, "available": True,
         "price": 450_000, "runningCosts": 60_000, "lifespan": 25_000, "topSpeed": 22.0, "capacity": [{"cargo": PASSENGERS, "capacity": 30}]},
        {"id": 4, "res": "vehicle/bus/future.mdl", "name": "Bus Future", "carrier": "ROAD", "yearFrom": 2000, "yearTo": 0, "available": False,
         "price": 450_000, "runningCosts": 10_000, "lifespan": 25_000, "topSpeed": 30.0, "capacity": [{"cargo": PASSENGERS, "capacity": 99}]},
        {"id": 5, "res": "vehicle/truck/t.mdl", "name": "Truck T", "carrier": "ROAD", "yearFrom": 1970, "yearTo": 0, "available": True,
         "price": 600_000, "runningCosts": 90_000, "lifespan": 20_000, "topSpeed": 17.0, "capacity": [{"cargo": COAL, "capacity": 30}]},
        {"id": 6, "res": "vehicle/train/x.mdl", "name": "Train X", "carrier": "RAIL", "yearFrom": 1970, "yearTo": 0, "available": True,
         "price": 1, "runningCosts": 1, "lifespan": 1, "topSpeed": 1.0, "capacity": [{"cargo": PASSENGERS, "capacity": 99}]},
    ]
    return cat, units


def _vehicle(vid, line, model, cargo, profit, age_years, game_time, capacity=20, can_carry=None, carrier="ROAD"):
    return {
        "id": vid, "name": f"V{vid}", "carrier": carrier, "state": "EN_ROUTE", "line": line,
        "purchaseTime": int(game_time - age_years * YEAR), "profitYear": profit, "models": [model], "value": 100_000,
        "runningCost": 50_000, "maintenanceState": 0.9, "capacity": capacity,
        "loadConfig": [{"cargo": cargo, "capacity": capacity}], "canCarry": can_carry if can_carry is not None else [cargo],
    }


def _snapshot(year, month, with_catalog=False, units=None, bus_b_name="Bus B", extra_vehicles=(), b_profit=-30_000):
    game_time = int((year - 1980) * YEAR + month * YEAR / 12) + 5 * YEAR
    vehicles = []
    vid = 1
    # Bus A: 4 mature, profitable, line 100 (load high)
    for _ in range(4):
        vehicles.append(_vehicle(vid, 100, BUS_A, PASSENGERS, 200_000, 5, game_time)); vid += 1
    # Bus B: 4 mature, loss-making on line 101 (load low)
    for _ in range(4):
        vehicles.append(_vehicle(vid, 101, BUS_B, PASSENGERS, b_profit, 6, game_time, capacity=40)); vid += 1
    # Bus C: 2 mature (small sample)
    for _ in range(2):
        vehicles.append(_vehicle(vid, 100, BUS_C, PASSENGERS, 50_000, 3, game_time)); vid += 1
    # Truck: 3 mature, loss-making coal
    for _ in range(3):
        vehicles.append(_vehicle(vid, 102, TRUCK, COAL, -10_000, 4, game_time, capacity=30)); vid += 1
    # Young bus A
    vehicles.append(_vehicle(vid, 100, BUS_A, PASSENGERS, 9_000, 0.2, game_time))
    vehicles.extend(extra_vehicles)
    lines = [
        {"id": 100, "name": "Line <Hot>", "vehicles": [v["id"] for v in vehicles if v["line"] == 100], "stops": [{}, {}],
         "profitYear": 1_000_000, "capacity": [{"cargo": PASSENGERS + 1, "used": 95, "capacity": 100}], "issues": []},
        {"id": 101, "name": "Line Cold", "vehicles": [v["id"] for v in vehicles if v["line"] == 101], "stops": [{}, {}],
         "profitYear": -120_000, "capacity": [{"cargo": PASSENGERS + 1, "used": 10, "capacity": 160}], "issues": []},
        {"id": 102, "name": "Coal Line", "vehicles": [v["id"] for v in vehicles if v["line"] == 102], "stops": [{}, {}],
         "profitYear": -30_000, "capacity": [{"cargo": COAL + 1, "used": 30, "capacity": 90}], "issues": []},
    ]
    raw = {
        "meta": {"schemaVersion": 1, "gameTime": game_time, "yearDuration": YEAR, "date": {"year": year, "month": month, "day": 1},
                 "reason": "interval"},
        "company": {"balance": 1_000_000, "loan": 0},
        "cargos": [{"id": 0, "name": "Passengers"}, {"id": 3, "name": "Coal"}],
        "models": _models(bus_b_name), "lines": lines, "vehicles": vehicles,
        "stations": [], "industries": [], "towns": [], "errors": [], "problems": {},
    }
    if with_catalog:
        raw["catalog"], _ = _catalog()
        raw["meta"]["reason"] = "request"
        if units:
            raw["meta"]["verifiedUnits"] = units
    return Snapshot(raw, source=f"s_{year}_{month}.lua")


def _store(tmp_path, specs):
    store = Store(tmp_path / "t.db")
    for spec in specs:
        store.add_snapshot(_snapshot(**spec))
    return store


MULTI_YEAR = [dict(year=1980 + y, month=m) for y in range(3) for m in (3, 6, 9, 12)]


def _tables(doc):
    return [b for b in doc.blocks if isinstance(b, Table)]


def _text(doc):
    return render_markdown(doc)


def test_no_snapshot_raises(tmp_path):
    store = Store(tmp_path / "empty.db")
    with pytest.raises(ValueError):
        vroi.build(store)
    store.close()


def test_groups_and_small_sample_flags(tmp_path):
    specs = [dict(s) for s in MULTI_YEAR]
    specs[-1]["with_catalog"] = True
    store = _store(tmp_path, specs)
    doc = vroi.build(store)
    assert doc.kind == "vehicle-roi"
    by_model = next(t for t in _tables(doc) if t.columns[0] == "Model [Carrier]" and "Mature (>=1y)" in t.columns)
    rows = {r[0]: r for r in by_model.rows}
    a, b, c = rows["Bus A [ROAD]"], rows["Bus B [ROAD]"], rows["Bus C [ROAD]"]
    cols = by_model.columns
    assert a[cols.index("Vehicles")] == 5 and a[cols.index("Mature (>=1y)")] == 4 and a[cols.index("Young (<1y)")] == 1
    assert a[cols.index("Mean profit/vehicle")] == 200_000
    assert a[cols.index("Sample")] == "OK"
    assert b[cols.index("Loss-making (mature)")] == "100.0%"
    assert c[cols.index("Sample")] == "Small sample (n=2)"
    # young vehicles never enter the mature mean
    assert a[cols.index("Young mean (partial)")] == 9_000


def test_ranking_excludes_small_samples(tmp_path):
    store = _store(tmp_path, MULTI_YEAR)
    doc = vroi.build(store)
    ranking = next(t for t in _tables(doc) if t.columns[:2] == ["Rank", "Model [Carrier]"])
    assert "Bus C [ROAD]" not in [r[1] for r in ranking.rows]
    assert ranking.rows[0][1] == "Bus A [ROAD]"


def test_every_chart_has_adjacent_numbers(tmp_path):
    store = _store(tmp_path, MULTI_YEAR)
    doc = vroi.build(store)
    md = _text(doc)
    for block in doc.blocks:
        if isinstance(block, Chart) and block.kind == "bar":
            for value in block.series[0][1]:
                assert f"{int(value):,}" in md


def test_trend_samples_are_bounded_and_not_summed(tmp_path):
    store = _store(tmp_path, MULTI_YEAR + [dict(year=1983, month=m) for m in range(1, 13)])
    doc = vroi.build(store)
    trend = next(t for t in _tables(doc) if t.columns[0] == "Model [Carrier]" and t.columns[1][:2] == "19")
    assert len(trend.columns) - 1 <= vroi.TREND_COLUMNS
    row = next(r for r in trend.rows if r[0] == "Bus A [ROAD]")
    assert all(cell.startswith("200,000 (n=4)") for cell in row[1:])


def test_trend_movers_report_decline(tmp_path):
    specs = [dict(year=1980, month=3), dict(year=1980, month=6), dict(year=1980, month=9, b_profit=-90_000)]
    store = _store(tmp_path, specs)
    md = _text(vroi.build(store))
    assert "Largest Changes Between" in md
    assert "-60,000" in md  # Bus B mean moved from -30,000 to -90,000


def test_swap_candidates_same_cargo_in_production_only(tmp_path):
    specs = [dict(s) for s in MULTI_YEAR]
    specs[0]["with_catalog"] = True
    store = _store(tmp_path, specs)
    doc = vroi.build(store)
    cand = next(t for t in _tables(doc) if t.columns[:2] == ["Weak group", "Candidate model"])
    rows = [r for r in cand.rows if r[0] == "Bus B [ROAD]"]
    names = [r[1] for r in rows]
    assert "Bus New" in names and "Bus A" in names
    assert "Bus Future" not in names          # not yet in production
    assert "Train X" not in names             # other carrier
    assert "Truck T" not in names             # does not carry passengers
    bus_a = next(r for r in rows if r[1] == "Bus A")
    assert bus_a[cand.columns.index("Capacity ratio")] == "x0.50"
    assert bus_a[cand.columns.index("Running cost ratio")] == "x0.62"
    truck_rows = [r for r in cand.rows if r[0] == "Truck T [ROAD]"]
    assert truck_rows == [] or all(r[1] != "Truck T" for r in truck_rows)
    md = _text(doc)
    assert "hypothes" in md.lower()


def test_unverified_units_are_disclosed_and_not_converted(tmp_path):
    specs = [dict(s) for s in MULTI_YEAR]
    specs[0]["with_catalog"] = True
    md = _text(vroi.build(_store(tmp_path, specs)))
    assert "Top speed unit unverified" in md
    assert "m/s" not in md.replace("m/s by verifiedUnits", "")


def test_verified_units_are_reported_when_present(tmp_path):
    specs = [dict(s) for s in MULTI_YEAR]
    specs[0].update(with_catalog=True, units={"topSpeed": "m/s", "runningCosts": "currency/year"})
    md = _text(vroi.build(_store(tmp_path, specs)))
    assert "labelled m/s by verifiedUnits" in md


def test_missing_catalog_degrades_to_insufficient_data(tmp_path):
    md = _text(vroi.build(_store(tmp_path, MULTI_YEAR)))
    assert "No stored catalog snapshot" in md


def test_single_snapshot_degrades_gracefully(tmp_path):
    store = _store(tmp_path, [dict(year=1980, month=3)])
    md = _text(vroi.build(store))
    assert "Fewer than two sampled snapshots" in md
    assert "Insufficient Data" in md


def test_model_name_markup_is_escaped_in_html(tmp_path):
    specs = [dict(s, bus_b_name="Bus <script>alert(1)</script> | x") for s in MULTI_YEAR]
    html = render_html(vroi.build(_store(tmp_path, specs)))

    class Surface(HTMLParser):
        def __init__(self):
            super().__init__()
            self.tags = []

        def handle_starttag(self, tag, attrs):
            self.tags.append(tag)

    surface = Surface()
    surface.feed(html)
    assert "script" not in surface.tags
    assert "&lt;script&gt;" in html


def test_cargo_not_in_can_carry_is_flagged(tmp_path):
    bad = _vehicle(900, 100, BUS_A, PASSENGERS, 1_000, 5, 5 * YEAR + 2 * YEAR, can_carry=[COAL])
    specs = [dict(s) for s in MULTI_YEAR]
    specs[-1]["extra_vehicles"] = [bad]
    md = _text(vroi.build(_store(tmp_path, specs)))
    assert "canCarry" in md and "V900" in md


def test_ticks_per_year_calibrates_from_dates_not_year_duration(tmp_path):
    snaps = [_snapshot(1980, 1), _snapshot(1981, 1)]
    ticks, note = vroi._ticks_per_year(snaps)
    assert ticks == pytest.approx(YEAR, rel=0.02)
    assert "calibrated" in note
    # Lying yearDuration (4x too small) must not change the calibrated scale.
    for s in snaps:
        s.raw["meta"]["yearDuration"] = YEAR // 4
    ticks2, _ = vroi._ticks_per_year(snaps)
    assert ticks2 == pytest.approx(YEAR, rel=0.02)
    # With one date only, fall back to yearDuration and say so.
    ticks3, note3 = vroi._ticks_per_year(snaps[:1])
    assert ticks3 == YEAR // 4 and "yearDuration" in note3


def test_markdown_and_html_render_without_error(tmp_path):
    specs = [dict(s) for s in MULTI_YEAR]
    specs[0]["with_catalog"] = True
    doc = vroi.build(_store(tmp_path, specs))
    assert render_markdown(doc).startswith("# Vehicle ROI Report")
    assert "<svg" in render_html(doc)
