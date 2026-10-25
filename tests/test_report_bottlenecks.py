from __future__ import annotations

import json

import pytest

from conftest import YEAR, base_snapshot
from tf3companion import report_bottlenecks as rb
from tf3companion import reports
from tf3companion.analysis_views import EvaluationContext, evaluate_views
from tf3companion.analysis_views.models import plain
from tf3companion.report_policy import resolve_context
from tf3companion.snapshot import Snapshot
from tf3companion.store import Store
from view_helpers import document, view

STEP = YEAR // 12


def make_snapshot(index: int, with_stocks: bool = True) -> dict:
    data = base_snapshot(game_time=10 * YEAR + index * STEP)
    data["meta"]["date"] = {"year": 1980 + index // 12, "month": index % 12 + 1, "day": 1}
    data["meta"]["saveId"] = "save-1"
    data["industries"] = [{
        "id": 700, "name": "Mine <b>X</b>", "inputs": [],
        "outputs": [{"cargo": 3, "producedYear": 400, "shippedYear": 200}],
    }]
    if with_stocks:
        data["depots"] = [{"id": 800, "name": "Depot One"}]
        data["stocks"] = [
            {"kind": "industry", "owner": 700, "ownerName": "Mine <b>X</b>", "stockId": 1, "cargos": [3],
             "count": 100, "capacity": 400},
            {"kind": "warehouse", "owner": 710, "ownerName": "Warehouse A", "stockId": 0, "cargos": [3],
             "count": 100, "capacity": 500},
        ]
    return data


@pytest.fixture
def make_store(tmp_path):
    stores = []

    def factory(count, mod=None, with_stocks=lambda i: True):
        store = Store(tmp_path / f"bn{len(stores)}.db")
        stores.append(store)
        for i in range(count):
            data = make_snapshot(i, with_stocks(i))
            if mod:
                mod(i, data)
            store.add_snapshot(Snapshot(data, source=f"s{i}.lua"))
        return store

    yield factory
    for store in stores:
        store.close()


def priority(doc, status_prefix):
    """Rows of the priority table whose h3 starts with the given status title."""
    rows, active = [], False
    for block in doc.blocks:
        if isinstance(block, reports.Heading) and block.level == 3:
            active = block.text.startswith(status_prefix)
        elif isinstance(block, reports.Heading) and block.level == 2:
            active = False
        elif active and isinstance(block, reports.Table):
            rows.extend(block.rows)
    return rows


def full_stock(i, data):
    data["stocks"][0]["count"] = 400


def _both(store, report_context):
    """The view and document of the latest snapshot under an explicit effective report context."""
    snap = store.latest()
    ctx = EvaluationContext(snap, report_context, store.time_context(snap), None, store.previous_of(snap))
    result = evaluate_views(store, ctx, ("bottlenecks",)).bottlenecks
    return result, rb.build(result, context=ctx)


def _items(result, code=None, status=None):
    return [i for i in result.items if (code is None or i.code == code) and (status is None or i.status == status)]


def test_no_snapshot_raises(tmp_path):
    store = Store(tmp_path / "empty.db")
    try:
        with pytest.raises(ValueError, match="No snapshot"):
            document(store, "bottlenecks")
    finally:
        store.close()


def test_single_snapshot_degrades_without_raising(make_store):
    store = make_store(1)
    doc = document(store, "bottlenecks")
    assert doc.kind == "bottlenecks"
    assert view(store, "bottlenecks").insufficient_history
    assert any(isinstance(b, reports.Note) and b.label == "Limited history" for b in doc.blocks)
    assert reports.render_markdown(doc)


def test_persistent_full_served_stock_is_high_and_counts_samples(make_store):
    store = make_store(6, lambda i, d: full_stock(i, d))
    result, doc = view(store, "bottlenecks"), document(store, "bottlenecks")
    item = _items(result, "stock_output_full")[0]
    assert (item.status, item.severity, item.observations, item.eligible, item.streak) == ("persistent", "high", 6, 6, 6)
    assert item.evidence["shippedRatio"] == 0.5 and item.evidence["fill"] == 1.0
    assert item.first_tick == 10 * YEAR and item.last_tick == 10 * YEAR + 5 * STEP
    rows = priority(doc, "Persistent")
    row = next(r for r in rows if r[2] == "Mine <b>X</b>")
    assert row[0] == "HIGH" and row[1] == "Stocks"
    assert row[4].startswith("6 of 6")


def test_stock_missing_from_early_samples_is_unknown_not_zero(make_store):
    store = make_store(6, lambda i, d: full_stock(i, d) if i >= 2 else None, with_stocks=lambda i: i >= 2)
    result, doc = view(store, "bottlenecks"), document(store, "bottlenecks")
    item = _items(result, "stock_output_full")[0]
    assert (item.observations, item.eligible) == (4, 4)
    sources = {c.source: c for c in result.data_sources}
    assert (sources["stocks"].samples, sources["stocks"].of, sources["stocks"].first.date) == (4, 6, "1980-03-01")
    assert result.stocks.samples_with_stocks == 4
    row = next(r for r in priority(doc, "Persistent") if r[2] == "Mine <b>X</b>")
    assert row[4].startswith("4 of 4")
    coverage = next(t for t in doc.blocks if isinstance(t, reports.Table) and t.columns[0] == "Data source")
    assert ["Stocks (stations/industries/warehouses)", "4 of 6", "1980-03-01"] in coverage.rows


def test_one_off_vs_persistent_vs_new_are_separated(make_store):
    def mod(i, data):
        if i in (1, 2):  # one-off in the past: resolved
            data["vehicles"][0]["noPath"] = True
        if i == 5:       # only in the latest sample: new
            data["lines"][0]["issues"] = [{"type": "NowhereToLoad", "stopIndex": 0, "cargo": 3}]
        if i >= 2:       # persistent through the latest sample
            data["vehicles"].append({"id": 1001, "name": "Stopped 1", "carrier": "ROAD", "state": "EN_ROUTE",
                                     "line": 100, "userStopped": True, "value": 5})
            data["lines"][0]["vehicles"] = [1000, 1001]

    store = make_store(6, mod)
    result, doc = view(store, "bottlenecks"), document(store, "bottlenecks")
    by_name = {(i.name, i.code): i for i in result.items}
    assert (by_name["Stopped 1", "vehicle_user_stopped"].status, by_name["Stopped 1", "vehicle_user_stopped"].eligible) == ("persistent", 4)
    assert by_name["Train A", "line_config_issue"].status == "new"
    gone = by_name["Train 1", "vehicle_no_path"]
    assert (gone.status, gone.observations, gone.eligible, gone.in_latest) == ("resolved", 2, 6, False)
    assert result.summary.resolved == 1 and result.summary.persistent == 1 and result.summary.new == 1
    persistent = priority(doc, "Persistent")
    new = priority(doc, "New")
    resolved = priority(doc, "Seen earlier")
    assert any(r[2] == "Stopped 1" and r[4].startswith("4 of 4") for r in persistent)
    assert any("NowhereToLoad" in r[3] for r in new)
    assert any(r[2] == "Train 1" and r[4] == "2 of 6" and "cannot find a path" in r[3] for r in resolved)
    assert not any(r[2] == "Train 1" for r in persistent + new)


def _crowded(i, data):
    line = data["lines"][0]
    if i == 3:
        line["capacity"] = [{"cargo": 0, "used": 100, "capacity": 100}]  # one-off 100%
    else:
        line["capacity"] = [{"cargo": 0, "used": 55, "capacity": 100}]
    data["lines"].append({"id": 101, "name": "Crowded", "vehicles": [], "stops": [{"stationGroup": 500}, {"stationGroup": 501}],
                          "profitYear": 1, "capacity": [{"cargo": 0, "used": 98, "capacity": 100}], "issues": []})
    data["vehicles"].append({"id": 1002, "name": "Bus c1", "carrier": "ROAD", "state": "EN_ROUTE", "line": 101})
    data["vehicles"].append({"id": 1003, "name": "Bus c2", "carrier": "ROAD", "state": "EN_ROUTE", "line": 101})
    data["lines"][-1]["vehicles"] = [1002, 1003]


def test_single_instant_occupancy_reading_is_not_listed_but_recurring_is(make_store):
    store = make_store(6, _crowded)
    result, doc = view(store, "bottlenecks"), document(store, "bottlenecks")
    names = {r[2] for status in ("Persistent", "Intermittent", "New", "Seen earlier") for r in priority(doc, status)}
    assert "Crowded" in names
    assert "Train A" not in names
    assert {i.name for i in result.items if i.code.startswith("line_load")} == {"Crowded"}
    pattern = result.occupancy[0]
    assert (pattern.name, pattern.pattern, pattern.status, pattern.observations, pattern.eligible) == ("Crowded", "high", "persistent", 6, 6)
    assert pattern.known_samples == 6 and pattern.mean == pytest.approx(.98) and pattern.latest == pytest.approx(.98)
    assert (pattern.minimum, pattern.maximum, pattern.vehicles, pattern.profit_year) == (pytest.approx(.98), pytest.approx(.98), 2, 1)
    table = next(t for t in doc.blocks if isinstance(t, reports.Table) and t.columns[0] == "Line")
    assert table.rows[0][:3] == ["Crowded", "Often full", "6 of 6"] and table.rows[0][3] == "98.0%"


def test_idle_vehicle_with_line_minus_one_is_found_and_grouped_by_depot(make_store):
    def mod(i, data):
        for n in range(2):
            data["vehicles"].append({"id": 2000 + n, "name": f"Idle {n}", "carrier": "WATER", "state": "IN_DEPOT",
                                     "line": -1, "depot": 800, "daysInDepot": 40, "value": 1_000_000})

    store = make_store(5, mod)
    result, doc = view(store, "bottlenecks"), document(store, "bottlenecks")
    item = _items(result, "vehicle_idle_depot")[0]
    assert (item.name, item.severity, item.status) == ("Depot One", "medium", "persistent")
    assert item.evidence["count"] == 2 and item.evidence["value"] == 2_000_000 and item.evidence["days"] == 40
    group = result.depot_groups[0]
    assert (group.name, group.vehicles, group.without_line, group.value_without_line) == ("Depot One", 2, 2, 2_000_000)
    row = next(r for r in priority(doc, "Persistent") if r[1] == "Fleet / depots")
    assert row[2] == "Depot One" and row[0] == "MEDIUM"
    assert "2 vehicle(s)" in row[3] and "2,000,000" in row[3]


def test_unknown_vehicle_value_is_not_summed_as_zero_and_depot_ties_are_ordered(make_store):
    def mod(i, data):
        data["depots"].append({"id": 801, "name": "Depot Two"})
        vehicles = [
            {"id": 2000, "name": "Idle 0", "carrier": "WATER", "state": "IN_DEPOT", "line": -1, "depot": 801, "value": 7},
            {"id": 2001, "name": "Idle 1", "carrier": "WATER", "state": "IN_DEPOT", "line": -1, "depot": 800},
        ]
        data["vehicles"].extend(vehicles if i % 2 else vehicles[::-1])

    store = make_store(4, mod)
    result = view(store, "bottlenecks")
    assert [(g.name, g.vehicles) for g in result.depot_groups] == [("Depot One", 1), ("Depot Two", 1)]
    assert result.depot_groups[0].value_without_line is None
    assert result.depot_groups[1].value_without_line == 7
    doc = document(store, "bottlenecks")
    table = next(t for t in doc.blocks if isinstance(t, reports.Table) and t.columns[0] == "Depot")
    assert [r[0] for r in table.rows] == ["Depot One", "Depot Two"] and table.rows[0][3] is None


def test_html_escapes_game_names_and_is_self_contained(make_store):
    doc = document(make_store(6, lambda i, d: full_stock(i, d)), "bottlenecks")
    html_out = reports.render_html(doc)
    assert "Mine &lt;b&gt;X&lt;/b&gt;" in html_out
    assert "<b>X</b>" not in html_out
    assert "<script" not in html_out
    assert 'href="' not in html_out and 'src="' not in html_out and "url(" not in html_out


def test_multi_year_history_caps_window_and_buckets_charts(make_store):
    def mod(i, data):
        full_stock(i, data)
        data["lines"][0]["issues"] = [{"type": "NowhereToLoad", "stopIndex": 0, "cargo": 3}] if i % 2 else []

    store = make_store(60, mod)  # five game years of monthly samples
    result, doc = view(store, "bottlenecks"), document(store, "bottlenecks")
    assert (result.samples, result.merged_available, result.bucketed) == (36, 60, True)
    assert len(result.health) <= 24 and result.health[-1].tick == result.window_end.tick
    header = dict(doc.header)
    assert "36 used" in header["Persistence Window"] and "60 available" in header["Persistence Window"]
    item = _items(result, "stock_output_full")[0]
    assert (item.observations, item.eligible) == (36, 36)
    row = next(r for r in priority(doc, "Persistent") if r[2] == "Mine <b>X</b>")
    assert row[4].startswith("36 of 36")
    charts = [b for b in doc.blocks if isinstance(b, reports.Chart)]
    assert charts and all(len(c.categories) <= 24 for c in charts)
    assert any(isinstance(b, reports.Note) and b.label == "Sampling" for b in doc.blocks)


def test_every_chart_has_adjacent_table_with_same_numbers_as_the_view(make_store):
    def mod(i, data):
        data["lines"][0]["issues"] = [{"type": "NowhereToLoad", "stopIndex": 0, "cargo": 3}] if i < 3 else []
        full_stock(i, data)

    store = make_store(8, mod)
    result, doc = view(store, "bottlenecks"), document(store, "bottlenecks")
    assert [p.counts["line_issues"] for p in result.health] == [1, 1, 1, 0, 0, 0, 0, 0]
    assert [p.counts["stock_output_full"] for p in result.health] == [1] * 8
    for index, block in enumerate(doc.blocks):
        if isinstance(block, reports.Chart):
            table = doc.blocks[index + 1]
            assert isinstance(table, reports.Table)
            assert table.columns[1:] == [label for label, _ in block.series]
            for col, (_, points) in enumerate(block.series, start=1):
                assert [float(row[col]) for row in table.rows] == points
            assert [row[0] for row in table.rows] == block.categories
    hard = next(b for b in doc.blocks if isinstance(b, reports.Chart) and b.title == "Hard problems per sample")
    assert dict(hard.series)["Lines with issues or incomplete"] == [float(p.counts["line_issues"]) for p in result.health]


def _error_mod(i, data):
    data["errors"] = ["depot[%d].constructionComponent: [string \"x.lua\"]:106: Invalid entity\nstack traceback:\n  ..." % (1000 + i)]


def test_collection_errors_are_summarised_with_affected_conclusions(make_store):
    store = make_store(4, _error_mod)
    result, doc = view(store, "bottlenecks"), document(store, "bottlenecks")
    family = result.error_families[0]
    assert (family.family, family.message, family.samples, family.of, family.latest_occurrences, family.affects) == \
        ("depot[*].constructionComponent", "Invalid entity", 4, 4, 1, "depot")
    assert result.coverage.collection_errors == ("depot[*].constructionComponent",)
    errors = next(t for t in doc.blocks if isinstance(t, reports.Table) and t.columns[0] == "Collector")
    assert errors.rows[0][0] == "depot[*].constructionComponent"
    assert errors.rows[0][1] == "Invalid entity"
    assert errors.rows[0][2] == "4 of 4"
    assert "depot" in errors.rows[0][4]
    assert "stack traceback" not in dict(doc.header)["Collection Errors"]


def test_equally_frequent_error_families_are_ordered_by_name(make_store):
    def mod(i, data):
        errors = ["zeta[1]: z failed", "alpha[2]: a failed"]
        data["errors"] = errors if i % 2 else errors[::-1]

    result = view(make_store(4, mod), "bottlenecks")
    assert [(e.family, e.samples) for e in result.error_families] == [("alpha[*]", 4), ("zeta[*]", 4)]


def _reset_mod(i, data):
    data["vehicles"][0]["daysAtTerminal"] = 12 if i < 3 else 0
    for n in range(10):
        data["vehicles"].append({"id": 3000 + n, "name": f"V{n}", "carrier": "ROAD", "state": "AT_TERMINAL", "line": 100,
                                 "stopIndex": 0, "daysAtTerminal": 12 if i < 3 else 0})
    data["lines"][0]["vehicles"] = [1000] + [3000 + n for n in range(10)]


def test_days_at_terminal_reset_is_disclosed_as_possible_artifact(make_store):
    store = make_store(6, _reset_mod)
    result, doc = view(store, "bottlenecks"), document(store, "bottlenecks")
    assert [(r.from_sample.date, r.to_sample.date, r.before, r.after) for r in result.terminal_resets] == \
        [("1980-03-01", "1980-04-01", 11, 0)]
    note = next(b for b in doc.blocks if isinstance(b, reports.Note) and b.label == "daysAtTerminal discontinuity")
    assert "1980-03-01 to 1980-04-01" in note.text


def _rising(base, step, capacity=400):
    def mod(i, data):
        data["stocks"][0]["count"] = base + step * i
        data["stocks"][0]["capacity"] = capacity
    return mod


def test_rising_stock_slope_is_units_per_sample_over_the_last_six(make_store):
    store = make_store(10, _rising(100, 20))
    result, doc = view(store, "bottlenecks"), document(store, "bottlenecks")
    rise = result.stock_rises[0]
    assert (rise.name, rise.kind, rise.count_latest, rise.count_start, rise.capacity) == ("Mine <b>X</b>", "industry", 280, 180, 400)
    assert rise.slope_per_sample == pytest.approx(20) and rise.samples_to_full == pytest.approx(6)
    assert [p.count for p in rise.points] == [180, 200, 220, 240, 260, 280]
    assert rise.fill == pytest.approx(.7)
    table = next(t for t in doc.blocks if isinstance(t, reports.Table) and t.columns[0] == "Stock owner")
    assert table.rows[0][4:] == [180, 280, "+20.0", 6.0]


def test_rising_stock_below_policy_slope_or_fill_is_not_listed(make_store):
    assert not view(make_store(6, _rising(100, 4)), "bottlenecks").stock_rises   # 1% of capacity per sample
    assert not view(make_store(6, _rising(40, 20)), "bottlenecks").stock_rises   # latest fill 35%, below the minimum
    assert view(make_store(2, _rising(200, 20)), "bottlenecks").stock_rises == ()  # fewer than three samples


def test_equally_rising_stocks_are_ordered_by_name_not_input_order(make_store):
    def mod_for(reverse):
        def mod(i, data):
            stocks = [{"kind": "warehouse", "owner": owner, "ownerName": name, "stockId": 0, "cargos": [3],
                       "count": 250 + 20 * i, "capacity": 500} for owner, name in ((711, "Warehouse B"), (710, "Warehouse A"))]
            data["stocks"] = stocks[::-1] if reverse else stocks
        return mod

    for reverse in (False, True):
        result = view(make_store(6, mod_for(reverse)), "bottlenecks")
        assert [r.name for r in result.stock_rises] == ["Warehouse A", "Warehouse B"]


def test_latest_stock_unavailable_is_reported_as_unknown(make_store):
    store = make_store(6, with_stocks=lambda i: i < 5)
    result, doc = view(store, "bottlenecks"), document(store, "bottlenecks")
    assert not result.stocks.latest_has_stocks and not result.stock_rises
    assert any(u.code == "latest-sample-without-stocks" for u in result.coverage.unavailable)
    assert any(isinstance(b, reports.Note) and b.label == "Insufficient data" for b in doc.blocks)


def test_unserved_full_output_stock_is_counted_not_flagged(make_store):
    def mod(i, data):
        full_stock(i, data)
        data["industries"][0]["outputs"][0]["shippedYear"] = 0

    result = view(make_store(6, mod), "bottlenecks")
    assert not _items(result, "stock_output_full")
    assert [(u.name, u.fill) for u in result.stocks.unserved] == [("Mine <b>X</b>", 1.0)]


# ---- evidence bounds ----------------------------------------------------------------------

def test_past_endpoint_excludes_later_samples_entities_and_stock_findings(make_store):
    def mod(i, data):
        if i >= 5:
            full_stock(i, data)
            data["lines"].append({"id": 101, "name": "Future Line", "vehicles": [], "stops": [], "profitYear": 0,
                                  "capacity": [], "issues": []})

    store = make_store(8, mod)
    assert any(i.name == "Future Line" for i in view(store, "bottlenecks").items)  # visible from the latest endpoint
    earlier = store.hydrate(10 * YEAR + 4 * STEP)
    ctx = EvaluationContext(earlier, resolve_context(), store.time_context(earlier), None, store.previous_of(earlier))
    result = evaluate_views(store, ctx, ("bottlenecks",)).bottlenecks
    doc = rb.build(result, context=ctx)
    assert result.window_end.tick == earlier.game_time and result.samples == 5
    assert all(ref.tick <= earlier.game_time for ref in result.coverage.sampled)
    assert result.coverage.endpoint.tick == earlier.game_time and result.coverage.eligible == 5
    assert not any(i.name == "Future Line" or i.code == "stock_output_full" for i in result.items)
    assert all(i.last_tick <= earlier.game_time for i in result.items)
    assert all(p.tick <= earlier.game_time for p in result.health)
    assert dict(doc.header)["Latest Sample Date"] == earlier.date_label


def test_long_history_is_read_with_bounded_hydration(make_store):
    store = make_store(300, lambda i, d: full_stock(i, d))
    result = view(store, "bottlenecks")
    cov = result.coverage
    assert (cov.eligible, cov.read, cov.used) == (300, 240, 36)
    assert cov.hydrated <= cov.hydration_limit == 240 and cov.omitted == 264
    assert "history-beyond-read-limit" in cov.warnings
    assert (result.samples, result.merged_available) == (36, 240)
    item = _items(result, "stock_output_full")[0]
    assert item.observations == 36 and item.last_tick == store.latest().game_time


def test_view_is_json_serializable_and_independent_of_store_objects(make_store):
    store = make_store(6, lambda i, d: (full_stock(i, d), _error_mod(i, d), _crowded(i, d)))
    result = view(store, "bottlenecks")
    payload = json.loads(json.dumps(plain(result)))
    assert payload["samples"] == 6 and payload["coverage"]["endpoint"]["tick"] == store.latest().game_time
    assert {i["code"] for i in payload["items"]} >= {"stock_output_full", "line_load_high"}
    assert payload["errorFamilies"][0]["family"] == "depot[*].constructionComponent"
    assert [c["name"] for c in payload["criteria"]][:2] == ["persistence_window", "read_limit"]


def test_view_and_report_agree_on_membership_and_order(make_store):
    def mod(i, data):
        full_stock(i, data)
        _crowded(i, data)
        data["lines"][0]["issues"] = [{"type": "NowhereToLoad", "stopIndex": 0, "cargo": 3}]

    store = make_store(6, mod)
    result, doc = view(store, "bottlenecks"), document(store, "bottlenecks")
    shown = [r[2] for status in ("Persistent", "Intermittent", "New", "Seen earlier") for r in priority(doc, status)]
    assert shown == [i.name for st in ("persistent", "intermittent", "new", "resolved")
                     for i in result.items if i.status == st]
    text = reports.render_markdown(doc)
    s = result.summary
    assert f"Active now: {s.high} high, {s.medium} medium, {s.low} low severity" in text


# ---- effective policy consistency (observation, status, labels) ----------------------------

def _ctx(thresholds=None, **bottleneck_policy):
    from methodology_helpers import methodology
    if thresholds is not None:
        return resolve_context(thresholds=thresholds)
    return resolve_context(methodology(report_policies={"bottlenecks": bottleneck_policy} if bottleneck_policy else {}))


def _terminal_vehicles(data, count, days):
    for n in range(count):
        data["vehicles"].append({"id": 3000 + n, "name": f"V{n}", "carrier": "ROAD", "state": "AT_TERMINAL",
                                 "line": 100, "stopIndex": 0, "daysAtTerminal": days})
    data["lines"][0]["vehicles"] = [1000] + [3000 + n for n in range(count)]


def _codes(make_store, count, days, context):
    store = make_store(6, lambda i, d: _terminal_vehicles(d, count, days))
    result, _ = _both(store, context)
    return {i.code for i in result.items}


def test_pileup_and_long_wait_criteria_are_inclusive_at_equality(make_store):
    assert {"station_pileup", "long_terminal_wait"} <= _codes(make_store, 3, 10, _ctx())  # exactly at defaults 3 / 10
    assert "station_pileup" not in _codes(make_store, 3, 10, _ctx(pileup_min=4))
    assert "long_terminal_wait" not in _codes(make_store, 3, 10, _ctx(long_wait_days=11))
    assert "station_pileup" not in _codes(make_store, 2, 10, _ctx())
    assert "station_pileup" in _codes(make_store, 2, 10, _ctx(pileup_min=2))
    assert "long_terminal_wait" in _codes(make_store, 2, 10, _ctx(long_wait_days=10))


def test_station_pileup_group_records_waiting_vehicles_and_lines(make_store):
    store = make_store(6, lambda i, d: _terminal_vehicles(d, 3, 0))
    result, doc = view(store, "bottlenecks"), document(store, "bottlenecks")
    group = result.station_groups[0]
    assert (group.name, group.station_group, group.waiting, group.lines, group.line_names, group.status) == \
        ("Centre", 500, 3, 1, ("Train A",), "persistent")
    table = next(t for t in doc.blocks if isinstance(t, reports.Table) and t.columns[0] == "Station")
    assert table.rows[0][:5] == ["Centre", "6 of 6", 3, 1, "Train A"]


def _chart_labels(doc):
    return {label for b in doc.blocks if isinstance(b, reports.Chart) for label, _ in b.series}


def test_pressure_chart_labels_and_counts_follow_effective_thresholds(make_store):
    from tf3companion.analysis import Thresholds

    def mod(i, data):
        data["lines"][0]["capacity"] = [{"cargo": 0, "used": 85, "capacity": 100}]
        _terminal_vehicles(data, 2, 0)

    store = make_store(6, mod)
    default_labels = _chart_labels(document(store, "bottlenecks"))
    assert not any(label.startswith("Lines at") or label.startswith("Stops with") for label in default_labels)
    result, doc = _both(store, _ctx(Thresholds(overloaded_load=.8)))
    labels = _chart_labels(doc)
    assert "Lines at 80%+ occupancy" in labels  # label names the effective threshold, not a literal 90%
    assert not any("90%+" in label for label in labels)
    assert [p.counts["load_high"] for p in result.health] == [1] * 6
    low = _chart_labels(_both(store, _ctx(Thresholds(underused_load=.9, underused_min_vehicles=1)))[1])
    assert "Lines at 90% or less occupancy" in low and not any("30%" in label for label in low)
    chart = next(b for b in doc.blocks if isinstance(b, reports.Chart) and b.title == "Instant pressure readings")
    assert dict(chart.series)["Lines at 80%+ occupancy"] == [1.0] * 6
    pile_result, pile = _both(store, _ctx(pileup_min=2))
    pile_chart = next(b for b in pile.blocks if isinstance(b, reports.Chart) and b.title == "Instant pressure readings")
    assert dict(pile_chart.series)["Stops with 2+ vehicles waiting"] == [1.0] * 6
    assert [p.counts["pileup"] for p in pile_result.health] == [1] * 6
    assert not any(label.startswith("Stops with 3+") for label in _chart_labels(pile))


def _measured_store(make_store, flags, measurable):
    def mod(i, data):
        line = data["lines"][0]
        if not measurable[i]:
            line["capacity"] = [{"cargo": 0, "used": None, "capacity": None}]
        else:
            line["capacity"] = [{"cargo": 0, "used": 98 if flags[i] else 50, "capacity": 100}]

    return make_store(len(flags), mod)


def test_samples_without_measurable_occupancy_are_not_eligible_for_share(make_store):
    # Four unmeasurable samples, then six measurable ones flagged in four of them (share 4/6).
    store = _measured_store(make_store, [0, 0, 0, 0, 1, 1, 1, 0, 0, 1], [0] * 4 + [1] * 6)
    kept, _ = _both(store, _ctx(noisy_min_share=.66))
    item = _items(kept, "line_load_high")[0]
    assert (item.observations, item.eligible, item.status) == (4, 6, "intermittent")
    assert not _items(_both(store, _ctx(noisy_min_share=.67))[0], "line_load_high")


def test_latest_absence_is_resolved_and_latest_presence_resets_streak(make_store):
    gone = _items(view(_measured_store(make_store, [1, 1, 1, 0, 0], [1] * 5), "bottlenecks"), "line_load_high")
    assert [it.status for it in gone] == ["resolved"]
    back = _items(view(_measured_store(make_store, [1, 1, 1, 0, 1], [1] * 5), "bottlenecks"), "line_load_high")
    assert [it.status for it in back] == ["intermittent"] and back[0].streak == 1
