from __future__ import annotations

import pytest

from conftest import YEAR, base_snapshot
from tf3companion import report_bottlenecks as rb
from tf3companion import reports
from tf3companion.snapshot import Snapshot
from tf3companion.store import Store

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


def test_no_snapshot_raises(tmp_path):
    store = Store(tmp_path / "empty.db")
    try:
        with pytest.raises(ValueError, match="No snapshot"):
            rb.build(store)
    finally:
        store.close()


def test_single_snapshot_degrades_without_raising(make_store):
    doc = rb.build(make_store(1))
    assert doc.kind == "bottlenecks"
    assert any(isinstance(b, reports.Note) and b.label == "Limited history" for b in doc.blocks)
    assert reports.render_markdown(doc)


def test_persistent_full_served_stock_is_high_and_counts_samples(make_store):
    doc = rb.build(make_store(6, lambda i, d: full_stock(i, d)))
    rows = priority(doc, "Persistent")
    row = next(r for r in rows if r[2] == "Mine <b>X</b>")
    assert row[0] == "HIGH" and row[1] == "Stocks"
    assert row[4].startswith("6 of 6")


def test_stock_missing_from_early_samples_is_unknown_not_zero(make_store):
    store = make_store(6, lambda i, d: full_stock(i, d) if i >= 2 else None, with_stocks=lambda i: i >= 2)
    doc = rb.build(store)
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

    doc = rb.build(make_store(6, mod))
    persistent = priority(doc, "Persistent")
    new = priority(doc, "New")
    resolved = priority(doc, "Seen earlier")
    assert any(r[2] == "Stopped 1" and r[4].startswith("4 of 4") for r in persistent)
    assert any("NowhereToLoad" in r[3] for r in new)
    assert any(r[2] == "Train 1" and r[4] == "2 of 6" and "cannot find a path" in r[3] for r in resolved)
    assert not any(r[2] == "Train 1" for r in persistent + new)


def test_single_instant_occupancy_reading_is_not_listed_but_recurring_is(make_store):
    def mod(i, data):
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

    doc = rb.build(make_store(6, mod))
    names = {r[2] for status in ("Persistent", "Intermittent", "New", "Seen earlier") for r in priority(doc, status)}
    assert "Crowded" in names
    assert "Train A" not in names


def test_idle_vehicle_with_line_minus_one_is_found_and_grouped_by_depot(make_store):
    def mod(i, data):
        for n in range(2):
            data["vehicles"].append({"id": 2000 + n, "name": f"Idle {n}", "carrier": "WATER", "state": "IN_DEPOT",
                                     "line": -1, "depot": 800, "daysInDepot": 40, "value": 1_000_000})

    doc = rb.build(make_store(5, mod))
    row = next(r for r in priority(doc, "Persistent") if r[1] == "Fleet / depots")
    assert row[2] == "Depot One" and row[0] == "MEDIUM"
    assert "2 vehicle(s)" in row[3] and "2,000,000" in row[3]


def test_html_escapes_game_names_and_is_self_contained(make_store):
    doc = rb.build(make_store(6, lambda i, d: full_stock(i, d)))
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
    doc = rb.build(store)
    header = dict(doc.header)
    assert "36 used" in header["Persistence Window"] and "60 available" in header["Persistence Window"]
    row = next(r for r in priority(doc, "Persistent") if r[2] == "Mine <b>X</b>")
    assert row[4].startswith("36 of 36")
    charts = [b for b in doc.blocks if isinstance(b, reports.Chart)]
    assert charts and all(len(c.categories) <= rb.CHART_POINTS for c in charts)
    assert any(isinstance(b, reports.Note) and b.label == "Sampling" for b in doc.blocks)


def test_every_chart_has_adjacent_table_with_same_numbers(make_store):
    def mod(i, data):
        data["lines"][0]["issues"] = [{"type": "NowhereToLoad", "stopIndex": 0, "cargo": 3}] if i < 3 else []
        full_stock(i, data)

    doc = rb.build(make_store(8, mod))
    for index, block in enumerate(doc.blocks):
        if isinstance(block, reports.Chart):
            table = doc.blocks[index + 1]
            assert isinstance(table, reports.Table)
            assert table.columns[1:] == [label for label, _ in block.series]
            for col, (_, points) in enumerate(block.series, start=1):
                assert [float(row[col]) for row in table.rows] == points
            assert [row[0] for row in table.rows] == block.categories


def test_collection_errors_are_summarised_with_affected_conclusions(make_store):
    def mod(i, data):
        data["errors"] = ["depot[%d].constructionComponent: [string \"x.lua\"]:106: Invalid entity\nstack traceback:\n  ..." % (1000 + i)]

    doc = rb.build(make_store(4, mod))
    errors = next(t for t in doc.blocks if isinstance(t, reports.Table) and t.columns[0] == "Collector")
    assert errors.rows[0][0] == "depot[*].constructionComponent"
    assert errors.rows[0][1] == "Invalid entity"
    assert errors.rows[0][2] == "4 of 4"
    assert "depot" in errors.rows[0][4]
    assert "stack traceback" not in dict(doc.header)["Collection Errors"]


def test_days_at_terminal_reset_is_disclosed_as_possible_artifact(make_store):
    def mod(i, data):
        data["vehicles"][0]["daysAtTerminal"] = 12 if i < 3 else 0
        for n in range(10):
            data["vehicles"].append({"id": 3000 + n, "name": f"V{n}", "carrier": "ROAD", "state": "AT_TERMINAL", "line": 100,
                                     "stopIndex": 0, "daysAtTerminal": 12 if i < 3 else 0})
        data["lines"][0]["vehicles"] = [1000] + [3000 + n for n in range(10)]

    doc = rb.build(make_store(6, mod))
    assert any(isinstance(b, reports.Note) and b.label == "daysAtTerminal discontinuity" for b in doc.blocks)
