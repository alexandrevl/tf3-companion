import pytest

from tf3companion import report_towns
from tf3companion.reports import Chart, Table, render_html, render_markdown
from tf3companion.snapshot import Snapshot
from tf3companion.store import Store
from conftest import YEAR, base_snapshot

PAX_INDEX = 1  # lines[].capacity[].cargo is cargoTypeId + 1; passengers are cargo id 0


def _towns(step: int) -> list[dict]:
    """step = number of capacity steps gained by the growing towns so far."""
    def town(tid, name, caps, usage, supply=None, **extra):
        return {"id": tid, "name": name, "capacities": caps, "lineUsage": usage, "developmentActive": True,
                "noise": 60.0 + tid % 5, "pollution": 1000.0 * (tid % 7 + 1),
                "cargoSupply": supply if supply is not None else [], **extra}
    return [
        town(1, "Alpha", [500 + 10 * step, 300, 200], 0.7, [{"cargo": 3, "supply": 20.0, "limit": 100.0, "extra": 5}],
             position=[0, 0, 0]),
        town(2, "Beta <script>x</script>", [400, 300, 100], 0.2, [{"cargo": 3, "supply": 0, "limit": 80.0, "extra": 5}],
             position=[30000, 40000, 0]),
        town(3, "Gamma", [300, 200, 100], 0.0, position=[0, 90000, 0]),
        town(4, "Delta", [250, 100, 100], 0.0),
        town(5, "Epsilon", [100, 50, 50], 0.0),
        town(6, "Zeta", [100 + 20 * step, 50, 50], 0.0),
    ]


def _snapshot(year: int, month: int, step: int, with_positions: bool = True) -> Snapshot:
    data = base_snapshot(game_time=year * YEAR + month * (YEAR // 12))
    data["meta"]["date"] = {"year": year, "month": month, "day": 1}
    data["cargos"] = [{"id": 0, "name": "Passengers", "res": "::/cargos/passengers/passengers.cargo"},
                      {"id": 3, "name": "Coal", "res": "::/cargos/coal/coal.cargo"}]
    data["towns"] = _towns(step)
    if not with_positions:
        for t in data["towns"]:
            t.pop("position", None)
    data["stations"] = [
        {"id": 500, "name": "Alpha Central", "town": 1, "townName": "Alpha", "lines": [100]},
        {"id": 501, "name": "Beta Port", "town": 2, "townName": "Beta", "lines": [100]},
        {"id": 502, "name": "Delta Yard", "town": 4, "townName": "Delta", "lines": [101]},
    ]
    data["lines"] = [
        {"id": 100, "name": "Pax A-B", "vehicles": [], "stops": [{"stationGroup": 500}, {"stationGroup": 501}],
         "profitYear": 1, "transportedYear": 1, "rate": 1, "capacity": [{"cargo": PAX_INDEX, "used": 1, "capacity": 40}]},
        {"id": 101, "name": "Freight D", "vehicles": [], "stops": [{"stationGroup": 502}, {"stationGroup": 500}],
         "profitYear": 1, "transportedYear": 1, "rate": 1, "capacity": [{"cargo": 4, "used": 1, "capacity": 40}]},
    ]
    data["vehicles"] = []
    data["industries"] = [{"id": 7, "name": "Mine", "outputs": [{"cargo": 3, "producedYear": 100, "shippedYear": 20}]}]
    return Snapshot(data, source=f"{year}-{month}.lua")


@pytest.fixture
def multi_year_store(tmp_path):
    store = Store(tmp_path / "multi.db")
    step = 0
    for year in (1980, 1981, 1982, 1983):
        for month in (1, 4, 7, 10):
            store.add_snapshot(_snapshot(year, month, step))
            step += 1
    yield store
    store.close()


def _tables(doc):
    return [b for b in doc.blocks if isinstance(b, Table)]


def _text(doc):
    return render_markdown(doc)


def test_no_snapshot_raises(tmp_path):
    store = Store(tmp_path / "empty.db")
    with pytest.raises(ValueError):
        report_towns.build(store)
    store.close()


def test_multi_year_sections_and_growth(multi_year_store):
    doc = report_towns.build(multi_year_store)
    assert doc.kind == "towns"
    text = _text(doc)
    for heading in ("Key findings", "Evolution", "Town ranking", "Growth and stalls", "Coverage by our lines",
                    "Cargo demand: supply vs limit", "Pollution and noise hot spots"):
        assert f"## {heading}" in text
    # window is 3.75 calendar years, so annualised growth is shown and quarterly sampling is used
    assert "3.75 calendar years" in text
    evolution = next(t for t in _tables(doc) if t.columns[0] == "Sample")
    assert 10 <= len(evolution.rows) <= 16
    assert evolution.rows[0][0] == "1980-01-01" and evolution.rows[-1][0] == "1983-10-01"
    ranking = next(t for t in _tables(doc) if t.columns[1] == "Town" and "Growth/yr" in t.columns)
    alpha = next(r for r in ranking.rows if r[1] == "Alpha")
    assert alpha[5] == "+150"  # 15 steps of +10 capacity
    assert alpha[7] != "-"


def test_chart_has_adjacent_table_with_same_numbers(multi_year_store):
    doc = report_towns.build(multi_year_store)
    chart = next(b for b in doc.blocks if isinstance(b, Chart) and b.kind == "line")
    table = next(t for t in _tables(doc) if t.columns[0] == "Sample")
    assert [r[0] for r in table.rows] == chart.categories
    assert [r[1].replace(",", "") for r in table.rows] == [f"{v:.0f}" for v in chart.series[0][1]]


def test_coverage_and_stall_classification(multi_year_store):
    doc = report_towns.build(multi_year_store)
    text = _text(doc)
    assert "Freight lines only" in text  # Delta: station only used by a freight line
    assert "No station of ours" in text  # Gamma, Epsilon, Zeta
    stalled = next(t for t in _tables(doc) if t.columns[0] == "Town" and "Situation" in t.columns)
    names = [r[0] for r in stalled.rows]
    assert "Gamma" in names and "Alpha" not in names and "Zeta" not in names


def test_pairs_use_positions_when_available_and_say_unknown_otherwise(multi_year_store, tmp_path):
    with_pos = _text(report_towns.build(multi_year_store))
    assert "50.0" in with_pos  # Alpha-Beta 30/40 km triangle is linked, but Alpha-Gamma is 90 km, Beta-Gamma 50 km
    assert "90.0" in with_pos
    assert "Estimate" in with_pos
    store = Store(tmp_path / "nopos.db")
    for i, month in enumerate((1, 4, 7)):
        store.add_snapshot(_snapshot(1980, month, i, with_positions=False))
    without = _text(report_towns.build(store))
    assert "Unverifiable" in without and "unknown" in without
    store.close()


def test_directly_linked_pair_is_excluded(multi_year_store):
    doc = report_towns.build(multi_year_store)
    pairs = next(t for t in _tables(doc) if t.columns[0] == "Town A")
    assert not any({r[0], r[1]} == {"Alpha", "Beta <script>x</script>"} for r in pairs.rows)


def test_cargo_demand_cross_links_producers(multi_year_store):
    doc = report_towns.build(multi_year_store)
    by_cargo = next(t for t in _tables(doc) if t.columns[0] == "Cargo")
    coal = next(r for r in by_cargo.rows if r[0] == "Coal")
    assert coal[1] == 2 and coal[2] == 1  # two towns demand, one at zero supply
    assert coal[6] == 1 and coal[8] == "80"  # one producer, 80 unshipped/yr


def test_single_snapshot_degrades_without_raising(tmp_path):
    store = Store(tmp_path / "one.db")
    store.add_snapshot(_snapshot(1980, 1, 0))
    doc = report_towns.build(store)
    text = _text(doc)
    assert "Insufficient data" in text
    assert "## Town ranking" in text
    store.close()


def test_missing_town_data_does_not_raise(tmp_path):
    store = Store(tmp_path / "bare.db")
    snap = _snapshot(1980, 1, 0)
    snap.raw["towns"] = []
    store.add_snapshot(snap)
    assert "Insufficient data" in _text(report_towns.build(store))
    snap2 = _snapshot(1980, 2, 0)
    for town in snap2.raw["towns"]:
        for key in ("capacities", "lineUsage", "noise", "pollution", "cargoSupply"):
            town.pop(key, None)
    snap2.raw["stations"] = []
    store.add_snapshot(snap2)
    report_towns.build(store)
    store.close()


def test_html_escapes_town_names_and_is_offline(multi_year_store):
    output = render_html(report_towns.build(multi_year_store))
    assert "<script>x" not in output
    assert "Beta &lt;script&gt;x&lt;/script&gt;" in output
    assert "http://" not in output.replace("http://www.w3.org/2000/svg", "")
    assert "https://" not in output


def test_deterministic(multi_year_store):
    assert _text(report_towns.build(multi_year_store)) == _text(report_towns.build(multi_year_store))
