import json
from html.parser import HTMLParser

import pytest

from conftest import YEAR
from tf3companion.analysis import Thresholds
from tf3companion.analysis_views import EvaluationContext, evaluate_views
from tf3companion.analysis_views.models import plain
from tf3companion.analysis_views.vehicle_roi import MIN_SAMPLE
from tf3companion.analysis_views.vehicle_roi_evidence import TREND_COLUMNS
from tf3companion.report_policy import resolve_context
from tf3companion.reports import Chart, Table, render_html, render_markdown
from tf3companion.snapshot import Snapshot
from tf3companion.store import Store
from view_helpers import document, view

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


def _snapshot(year, month, with_catalog=False, units=None, bus_b_name="Bus B", extra_vehicles=(), b_profit=-30_000,
              year_duration=YEAR):
    game_time = int((year - 1980) * YEAR + month * YEAR / 12) + 10 * YEAR
    vehicles = []
    vid = 1
    # Bus A: 4 mature, profitable, line 100 (load high)
    for _ in range(4):
        vehicles.append(_vehicle(vid, 100, BUS_A, PASSENGERS, 200_000, 5, game_time))
        vid += 1
    # Bus B: 4 mature, loss-making on line 101 (load low)
    for _ in range(4):
        vehicles.append(_vehicle(vid, 101, BUS_B, PASSENGERS, b_profit, 6, game_time, capacity=40))
        vid += 1
    # Bus C: 2 mature (small sample)
    for _ in range(2):
        vehicles.append(_vehicle(vid, 100, BUS_C, PASSENGERS, 50_000, 3, game_time))
        vid += 1
    # Truck: 3 mature, loss-making coal
    for _ in range(3):
        vehicles.append(_vehicle(vid, 102, TRUCK, COAL, -10_000, 4, game_time, capacity=30))
        vid += 1
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
        "meta": {"schemaVersion": 1, "gameTime": game_time, "yearDuration": year_duration,
                 "date": {"year": year, "month": month, "day": 1}, "reason": "interval"},
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


def _store(tmp_path, specs, anchor=True, name="t.db", year_duration=YEAR):
    store = Store(tmp_path / name)
    if anchor:
        # Dated observation bounds old purchases explicitly; never extrapolate their ages.
        store.add_snapshot(Snapshot({"meta": {"schemaVersion": 1, "gameTime": 0, "yearDuration": YEAR,
                                             "date": {"year": 1970, "month": 1, "day": 1}}},
                                    source="calendar-anchor.lua"))
    for spec in specs:
        store.add_snapshot(_snapshot(year_duration=year_duration, **spec))
    return store


MULTI_YEAR = [dict(year=1980 + y, month=m) for y in range(3) for m in (3, 6, 9, 12)]


def _tables(doc):
    return [b for b in doc.blocks if isinstance(b, Table)]


def _text(doc):
    return render_markdown(doc)


def _roi(store, **kwargs):
    return view(store, "vehicle-roi", **kwargs)


def _group(v, key):
    return next(m for m in v.models if m.key == key)


def test_no_snapshot_raises(tmp_path):
    store = Store(tmp_path / "empty.db")
    with pytest.raises(ValueError):
        document(store, "vehicle-roi")
    store.close()


def test_groups_and_small_sample_flags(tmp_path):
    specs = [dict(s) for s in MULTI_YEAR]
    specs[-1]["with_catalog"] = True
    store = _store(tmp_path, specs)
    doc = document(store, "vehicle-roi")
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
    v = _roi(store)
    ga, gb, gc = _group(v, "Bus A [ROAD]"), _group(v, "Bus B [ROAD]"), _group(v, "Bus C [ROAD]")
    assert (ga.stats.n, ga.stats.mature, ga.stats.young, ga.stats.mean, ga.stats.young_mean) == (5, 4, 1, 200_000, 9_000)
    assert ga.stats.sample == "ok" and gc.stats.sample == "small-sample" and gc.rank is None
    assert gb.stats.loss_share == 1.0 and gb.stats.return_on_value == -30_000 / 100_000
    assert v.overall.n == 14 == len(v.observations)


def test_ranking_excludes_small_samples_and_matches_view(tmp_path):
    store = _store(tmp_path, MULTI_YEAR)
    doc = document(store, "vehicle-roi")
    ranking = next(t for t in _tables(doc) if t.columns[:2] == ["Rank", "Model [Carrier]"])
    assert "Bus C [ROAD]" not in [r[1] for r in ranking.rows]
    assert ranking.rows[0][1] == "Bus A [ROAD]"
    v = _roi(store)
    ranked = sorted((m for m in v.models if m.rank is not None), key=lambda m: m.rank)
    assert [r[1] for r in ranking.rows] == [m.key for m in ranked][:6] + [m.key for m in ranked][6:][-6:]
    assert [m.rank for m in ranked] == list(range(1, len(ranked) + 1))
    assert all(m.stats.mature >= MIN_SAMPLE for m in ranked)
    by_model = next(t for t in _tables(doc) if t.columns[0] == "Model [Carrier]" and "Mature (>=1y)" in t.columns)
    assert [r[0] for r in by_model.rows] == [m.key for m in v.models]


def test_every_chart_has_adjacent_numbers(tmp_path):
    store = _store(tmp_path, MULTI_YEAR)
    doc = document(store, "vehicle-roi")
    md = _text(doc)
    for block in doc.blocks:
        if isinstance(block, Chart) and block.kind == "bar":
            for _, values in block.series:
                for value in values:
                    assert f"{int(value):,}" in md


def test_trend_samples_are_bounded_and_not_summed(tmp_path):
    store = _store(tmp_path, MULTI_YEAR + [dict(year=1983, month=m) for m in range(1, 13)])
    doc = document(store, "vehicle-roi")
    trend = next(t for t in _tables(doc) if t.columns[0] == "Model [Carrier]" and t.columns[1][:2] == "19")
    assert len(trend.columns) - 1 <= TREND_COLUMNS
    row = next(r for r in trend.rows if r[0] == "Bus A [ROAD]")
    assert row[1] == "-"  # Calendar-only prehistory does not invent vehicle-group observations.
    assert all(cell.startswith("200,000 (n=4)") for cell in row[2:])
    v = _roi(store)
    assert len(v.trend_samples) <= TREND_COLUMNS
    assert [s.sample.date for s in v.trend_samples] == trend.columns[1:]


def test_trend_movers_report_decline(tmp_path):
    # Ten yearly samples: the trend keeps the newest eight, so the calendar-only anchor does not hide the comparison.
    specs = [dict(year=1980 + i, month=12) for i in range(10)]
    specs[-1]["b_profit"] = -90_000
    store = _store(tmp_path, specs)
    v = _roi(store)
    assert len(v.trend_samples) == TREND_COLUMNS
    mover = next(m for m in v.trend_movers if m.key == "Bus B [ROAD]")
    assert (mover.first_mean, mover.first_n, mover.last_mean, mover.last_n, mover.change) == (-30_000, 4, -90_000, 4, -60_000)
    assert [m.change for m in v.trend_movers] == sorted(m.change for m in v.trend_movers)
    doc = document(store, "vehicle-roi")
    changes = next(t for t in _tables(doc) if t.columns[-1] == "Change")
    row = next(r for r in changes.rows if r[0] == "Bus B [ROAD]")
    assert row[1] == -30_000 and row[3] == -90_000 and row[-1] == -60_000


def test_swap_candidates_same_cargo_in_production_only(tmp_path):
    specs = [dict(s) for s in MULTI_YEAR]
    specs[0]["with_catalog"] = True
    store = _store(tmp_path, specs)
    doc = document(store, "vehicle-roi")
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

    v = _roi(store)
    assert v.swap_status == "assessed" and v.catalog is not None
    weak = next(g for g in v.weak_groups if g.key == "Bus B [ROAD]")
    assert weak.status == "assessed" and weak.cargo == "Passengers" and weak.current_capacity == 40
    candidate = next(c for c in weak.candidates if c.name == "Bus A")
    assert candidate.capacity_ratio == pytest.approx(0.5) and candidate.running_cost_ratio == pytest.approx(50_000 / 80_000)
    assert candidate.in_fleet and candidate.own_mature == 4 and candidate.own_mean == 200_000
    assert {c.name for c in weak.candidates} <= {"Bus A", "Bus New", "Bus B"}
    assert len(weak.candidates) <= 3
    # candidates are ordered by capacity per raw running cost
    assert [c.name for c in weak.candidates] == ["Bus New", "Bus A"]
    assert {c.name for g in v.weak_groups for c in g.candidates}.isdisjoint({"Bus Future", "Train X"})
    assert "Truck T [ROAD]" in {g.key for g in v.weak_groups}


def test_unverified_units_are_disclosed_and_not_converted(tmp_path):
    specs = [dict(s) for s in MULTI_YEAR]
    specs[0]["with_catalog"] = True
    store = _store(tmp_path, specs)
    md = _text(document(store, "vehicle-roi"))
    assert "Top speed unit unverified" in md
    assert "m/s" not in md.replace("m/s by verifiedUnits", "")
    catalog = _roi(store).catalog
    assert catalog is not None and not catalog.top_speed_verified and not catalog.running_cost_verified


def test_verified_units_are_reported_when_present(tmp_path):
    specs = [dict(s) for s in MULTI_YEAR]
    specs[0].update(with_catalog=True, units={"topSpeed": "m/s", "runningCosts": "currency/year"})
    store = _store(tmp_path, specs)
    assert "labelled m/s by verifiedUnits" in _text(document(store, "vehicle-roi"))
    catalog = _roi(store).catalog
    assert catalog.top_speed_verified and catalog.running_cost_verified


def test_missing_catalog_degrades_to_insufficient_data(tmp_path):
    store = _store(tmp_path, MULTI_YEAR)
    assert "No stored catalog snapshot" in _text(document(store, "vehicle-roi"))
    v = _roi(store)
    assert v.catalog is None and v.swap_status == "no-catalog"
    assert all(g.status == "no-catalog" and not g.candidates for g in v.weak_groups) and v.weak_groups


def test_single_snapshot_degrades_gracefully(tmp_path):
    store = _store(tmp_path, [dict(year=1980, month=3)])
    doc = document(store, "vehicle-roi")
    trend = next(t for t in _tables(doc) if t.columns[0] == "Model [Carrier]" and t.columns[1][:2] == "19")
    row = next(r for r in trend.rows if r[0] == "Bus A [ROAD]")
    assert row[1] == "-" and row[2].startswith("200,000 (n=4)")
    assert _roi(store).swap_status == "no-catalog"   # weak groups exist but no catalog is stored


def test_model_name_markup_is_escaped_in_html(tmp_path):
    specs = [dict(s, bus_b_name="Bus <script>alert(1)</script> | x") for s in MULTI_YEAR]
    html = render_html(document(_store(tmp_path, specs), "vehicle-roi"))

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
    store = _store(tmp_path, specs)
    md = _text(document(store, "vehicle-roi"))
    assert "canCarry" in md and "V900" in md
    v = _roi(store)
    assert [(m.vehicle, [r.code for r in m.reasons]) for m in v.mismatches] == [("V900", ["cargo-not-in-can-carry"])]
    assert v.mismatch_checked == 15


def test_ages_use_bounded_calendar_not_nominal_fallback(tmp_path):
    specs = [dict(year=1980, month=1), dict(year=1981, month=1)]
    ages = []
    for i, duration in enumerate((YEAR, YEAR // 4)):
        store = _store(tmp_path, specs, name=f"d{i}.db", year_duration=duration)
        ages.append([(o.id, o.age) for o in _roi(store).observations])
        store.close()
    assert ages[0] == ages[1]
    # Without a calendar anchor before the purchases, ages are unknown (never nominal-tick derived).
    store = _store(tmp_path, specs, anchor=False, name="plain.db")
    v = _roi(store)
    unknown = [o for o in v.observations if o.age is None]
    assert unknown and all(o.maturity == "unknown" and o.age_reason for o in unknown)
    assert all(o.age_reason is None for o in v.observations if o.age is not None)
    assert v.overall.mature == 0 and v.overall.mean is None   # unknown is not treated as zero
    assert v.coverage.unavailable and v.coverage.unavailable[0].code == "unknown-vehicle-age"


def test_unknown_profit_is_not_counted_as_mature_or_zero(tmp_path):
    odd = _vehicle(901, 100, BUS_A, PASSENGERS, None, 5, 5 * YEAR + 2 * YEAR)
    specs = [dict(s) for s in MULTI_YEAR]
    specs[-1]["extra_vehicles"] = [odd]
    v = _roi(_store(tmp_path, specs))
    a = _group(v, "Bus A [ROAD]").stats
    assert (a.n, a.mature, a.young, a.mean) == (6, 4, 1, 200_000)
    assert next(o for o in v.observations if o.id == 901).maturity == "unknown"


def test_sustained_load_screens_follow_thresholds(tmp_path):
    store = _store(tmp_path, MULTI_YEAR)
    v = _roi(store)
    assert [f.line for f in v.high_load] == ["Line <Hot>"] and [f.line for f in v.low_load] == ["Line Cold"]
    hot = v.high_load[0]
    assert hot.load_median == pytest.approx(0.95) and hot.load_samples == 12
    assert hot.vehicles == 7 and hot.line_profit == 1_000_000
    stricter = _roi(store, thresholds=Thresholds(overloaded_load=0.99))
    assert stricter.high_load == () and stricter.low_load == v.low_load
    crowded = _roi(store, thresholds=Thresholds(overloaded_load=0.8, underused_min_vehicles=8))
    assert crowded.high_load == () and crowded.low_load == ()
    # fewer than MIN_LOAD_SAMPLES sampled snapshots: no sustained screen at all
    short = _roi(_store(tmp_path, MULTI_YEAR[:2], name="short.db"))
    assert short.high_load == () and short.low_load == ()
    doc = document(store, "vehicle-roi")
    high = next(t for t in _tables(doc) if t.columns[0] == "Line" and "Load across samples: median (range)" in t.columns)
    assert high.rows[0][0] == "Line <Hot>"


def test_same_line_comparison_membership_and_order(tmp_path):
    store = _store(tmp_path, MULTI_YEAR)
    v = _roi(store)
    assert [(c.line, c.better, c.weaker) for c in v.same_line] == [("Line <Hot>", "Bus A [ROAD]", "Bus C [ROAD]")]
    c = v.same_line[0]
    assert c.gap == 150_000 and c.small_sample and c.weaker_n == 2
    doc = document(store, "vehicle-roi")
    table = next(t for t in _tables(doc) if t.columns[0] == "Line" and "Better model" in t.columns)
    assert [r[0] for r in table.rows] == [x.line for x in v.same_line] and table.rows[0][5] == 150_000


def test_age_groups_are_derived_per_carrier(tmp_path):
    v = _roi(_store(tmp_path, MULTI_YEAR))
    young = next(a for a in v.ages if a.lower_years == 0.0)
    assert young.partial_window and young.stats.young == 1 and young.reported_mean == 9_000
    assert all(a.carrier == "ROAD" for a in v.ages)
    assert [a.lower_years for a in v.ages] == sorted(a.lower_years for a in v.ages)


def test_view_is_serializable_and_discloses_criteria(tmp_path):
    specs = [dict(s) for s in MULTI_YEAR]
    specs[0]["with_catalog"] = True
    v = _roi(_store(tmp_path, specs))
    data = json.loads(json.dumps(plain(v)))
    assert data["swapStatus"] == "assessed" and data["coverage"]["endpoint"]["tick"] == v.coverage.endpoint.tick
    criteria = {c["name"]: c["value"] for c in data["criteria"]}
    assert criteria["weak-group-loss-share"] == 0.4 and criteria["minimum-mature-sample"] == MIN_SAMPLE


def test_selected_earlier_endpoint_excludes_later_evidence(tmp_path):
    future = _vehicle(950, 100, BUS_A, PASSENGERS, 5_000, 5, 5 * YEAR + 2 * YEAR)
    specs = [dict(s) for s in MULTI_YEAR]
    specs[-1].update(with_catalog=True, extra_vehicles=[future])
    store = _store(tmp_path, specs)
    snaps = store.snapshots()
    earlier = next(s for s in snaps if s.date_label == "1981-06-01")
    ctx = EvaluationContext(earlier, resolve_context(), store.time_context(earlier), None, store.previous_of(earlier))
    v = evaluate_views(store, ctx, ("vehicle-roi",)).vehicle_roi
    assert v.coverage.endpoint.tick == earlier.game_time == v.last_sample.tick
    assert v.catalog is None and v.swap_status == "no-catalog"       # the only catalog is after the endpoint
    assert 950 not in {o.id for o in v.observations}
    assert v.coverage.eligible == sum(1 for s in snaps if s.game_time <= earlier.game_time)
    assert all(r.tick <= earlier.game_time for r in v.coverage.sampled)
    assert all(r.tick <= earlier.game_time for r in v.load_samples) and v.trend_samples[-1].sample.tick == earlier.game_time
    doc = document_at(store, ctx)
    assert "No stored catalog snapshot" in _text(doc) and "V950" not in _text(doc)


def document_at(store, ctx):
    from tf3companion import report_vehicle_roi
    return report_vehicle_roi.build(evaluate_views(store, ctx, ("vehicle-roi",)).vehicle_roi, context=ctx)


def test_hydration_is_bounded_for_a_long_history(tmp_path):
    specs = [dict(year=1980 + i // 12, month=i % 12 + 1) for i in range(60)]
    specs[0]["with_catalog"] = True
    store = _store(tmp_path, specs)
    v = _roi(store)
    cov = v.coverage
    assert cov.eligible == cov.read == 61                       # 60 samples plus the calendar anchor
    assert 0 < cov.hydrated <= cov.hydration_limit
    assert cov.used <= 33 and len(v.trend_samples) <= TREND_COLUMNS and len(v.load_samples) == 24
    assert cov.omitted == cov.eligible - cov.used
    assert v.first_sample.date == "1970-01-01" and v.last_sample.date == "1984-12-01"
    assert v.catalog is not None and v.catalog.sample.date == "1980-01-01"


def test_markdown_and_html_render_without_error(tmp_path):
    specs = [dict(s) for s in MULTI_YEAR]
    specs[0]["with_catalog"] = True
    doc = document(_store(tmp_path, specs), "vehicle-roi")
    assert render_markdown(doc).startswith("# Vehicle ROI Report")
    assert "<svg" in render_html(doc)
