import json

import pytest

from conftest import YEAR, base_snapshot
from tf3companion.analysis_views import EvaluationContext, evaluate_views
from tf3companion.analysis_views.models import plain
from tf3companion.report_policy import resolve_context
from tf3companion.reports import Chart, Table, render_html, render_markdown
from tf3companion.snapshot import Snapshot
from tf3companion.store import Store
from view_helpers import document, view

PAX_INDEX = 1  # lines[].capacity[].cargo is cargoTypeId + 1; passengers are cargo id 0


def _towns(step: int) -> list[dict]:
    """step = number of capacity steps gained by the growing towns so far."""

    def town(tid, name, caps, usage, supply=None, **extra):
        return {
            "id": tid,
            "name": name,
            "capacities": caps,
            "lineUsage": usage,
            "developmentActive": True,
            "noise": 60.0 + tid % 5,
            "pollution": 1000.0 * (tid % 7 + 1),
            "cargoSupply": supply if supply is not None else [],
            **extra,
        }

    return [
        town(
            1,
            "Alpha",
            [500 + 10 * step, 300, 200],
            0.7,
            [{"cargo": 3, "supply": 20.0, "limit": 100.0, "extra": 5}],
            position=[0, 0, 0],
        ),
        town(
            2,
            "Beta <script>x</script>",
            [400, 300, 100],
            0.2,
            [{"cargo": 3, "supply": 0, "limit": 80.0, "extra": 5}],
            position=[30000, 40000, 0],
        ),
        town(3, "Gamma", [300, 200, 100], 0.0, position=[0, 90000, 0]),
        town(4, "Delta", [250, 100, 100], 0.0),
        town(5, "Epsilon", [100, 50, 50], 0.0),
        town(6, "Zeta", [100 + 20 * step, 50, 50], 0.0),
    ]


def _snapshot(year: int, month: int, step: int, with_positions: bool = True) -> Snapshot:
    data = base_snapshot(game_time=year * YEAR + month * (YEAR // 12))
    data["meta"]["date"] = {"year": year, "month": month, "day": 1}
    data["cargos"] = [
        {"id": 0, "name": "Passengers", "res": "::/cargos/passengers/passengers.cargo"},
        {"id": 3, "name": "Coal", "res": "::/cargos/coal/coal.cargo"},
    ]
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
        {
            "id": 100,
            "name": "Pax A-B",
            "vehicles": [],
            "stops": [{"stationGroup": 500}, {"stationGroup": 501}],
            "profitYear": 1,
            "transportedYear": 1,
            "rate": 1,
            "capacity": [{"cargo": PAX_INDEX, "used": 1, "capacity": 40}],
        },
        {
            "id": 101,
            "name": "Freight D",
            "vehicles": [],
            "stops": [{"stationGroup": 502}, {"stationGroup": 500}],
            "profitYear": 1,
            "transportedYear": 1,
            "rate": 1,
            "capacity": [{"cargo": 4, "used": 1, "capacity": 40}],
        },
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
        document(store, "towns")
    store.close()


def test_multi_year_sections_and_growth(multi_year_store):
    doc = document(multi_year_store, "towns")
    assert doc.kind == "towns"
    text = _text(doc)
    for heading in (
        "Key findings",
        "Evolution",
        "Town ranking",
        "Growth and stalls",
        "Coverage by our lines",
        "Cargo demand: supply vs limit",
        "Pollution and noise hot spots",
    ):
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
    doc = document(multi_year_store, "towns")
    chart = next(b for b in doc.blocks if isinstance(b, Chart) and b.kind == "line")
    table = next(t for t in _tables(doc) if t.columns[0] == "Sample")
    assert [r[0] for r in table.rows] == chart.categories
    assert [r[1].replace(",", "") for r in table.rows] == [f"{v:.0f}" for v in chart.series[0][1]]


def test_coverage_and_stall_classification(multi_year_store):
    doc = document(multi_year_store, "towns")
    text = _text(doc)
    assert "Freight lines only" in text  # Delta: station only used by a freight line
    assert "No station of ours" in text  # Gamma, Epsilon, Zeta
    stalled = next(t for t in _tables(doc) if t.columns[0] == "Town" and "Situation" in t.columns)
    names = [r[0] for r in stalled.rows]
    assert "Gamma" in names and "Alpha" not in names and "Zeta" not in names


def test_pairs_use_positions_when_available_and_say_unknown_otherwise(multi_year_store, tmp_path):
    with_pos = _text(document(multi_year_store, "towns"))
    assert "50.0" in with_pos  # Alpha-Beta 30/40 km triangle is linked, but Alpha-Gamma is 90 km, Beta-Gamma 50 km
    assert "90.0" in with_pos
    assert "Estimate" in with_pos
    store = Store(tmp_path / "nopos.db")
    for i, month in enumerate((1, 4, 7)):
        store.add_snapshot(_snapshot(1980, month, i, with_positions=False))
    without = _text(document(store, "towns"))
    assert "Unverifiable" in without and "unknown" in without
    store.close()


def test_directly_linked_pair_is_excluded(multi_year_store):
    doc = document(multi_year_store, "towns")
    pairs = next(t for t in _tables(doc) if t.columns[0] == "Town A")
    assert not any({r[0], r[1]} == {"Alpha", "Beta <script>x</script>"} for r in pairs.rows)


def test_cargo_demand_cross_links_producers(multi_year_store):
    doc = document(multi_year_store, "towns")
    by_cargo = next(t for t in _tables(doc) if t.columns[0] == "Cargo")
    coal = next(r for r in by_cargo.rows if r[0] == "Coal")
    assert coal[1] == 2 and coal[2] == 1  # two towns demand, one at zero supply
    assert coal[6] == 1 and coal[8] == "80"  # one producer, 80 unshipped/yr


def test_single_snapshot_degrades_without_raising(tmp_path):
    store = Store(tmp_path / "one.db")
    store.add_snapshot(_snapshot(1980, 1, 0))
    doc = document(store, "towns")
    text = _text(doc)
    assert "Insufficient data" in text
    assert "## Town ranking" in text
    store.close()


def test_missing_town_data_does_not_raise(tmp_path):
    store = Store(tmp_path / "bare.db")
    snap = _snapshot(1980, 1, 0)
    snap.raw["towns"] = []
    store.add_snapshot(snap)
    assert "Insufficient data" in _text(document(store, "towns"))
    snap2 = _snapshot(1980, 2, 0)
    for town in snap2.raw["towns"]:
        for key in ("capacities", "lineUsage", "noise", "pollution", "cargoSupply"):
            town.pop(key, None)
    snap2.raw["stations"] = []
    store.add_snapshot(snap2)
    document(store, "towns")
    store.close()


def test_html_escapes_town_names_and_is_offline(multi_year_store):
    output = render_html(document(multi_year_store, "towns"))
    assert "<script>x" not in output
    assert "Beta &lt;script&gt;x&lt;/script&gt;" in output
    assert "http://" not in output.replace("http://www.w3.org/2000/svg", "")
    assert "https://" not in output


def test_deterministic(multi_year_store):
    assert _text(document(multi_year_store, "towns")) == _text(document(multi_year_store, "towns"))


# ---------------------------------------------------------------------------
# Direct view assertions
# ---------------------------------------------------------------------------


def _rows(v):
    return {r.name: r for r in v.rows}


def _context_at(store, snap):
    return EvaluationContext(snap, resolve_context(), store.time_context(snap), None, store.previous_of(snap))


def test_view_rows_ranks_growth_and_coverage(multi_year_store):
    v = view(multi_year_store, "towns")
    rows = _rows(v)
    assert [r.name for r in v.rows][:3] == ["Alpha", "Beta <script>x</script>", "Gamma"]
    assert rows["Alpha"].rank == 1 and rows["Alpha"].capacity == 1000 + 150 and rows["Alpha"].delta == 150
    assert rows["Alpha"].first_capacity == 1000 and abs(rows["Alpha"].growth - 0.15) < 1e-9
    assert rows["Alpha"].annual_growth is not None and rows["Alpha"].last_change == "1983-10-01"
    assert rows["Alpha"].large and not rows["Epsilon"].large
    assert rows["Delta"].served and rows["Delta"].lines_passenger == 0 and rows["Delta"].reading == "freight-only"
    assert rows["Gamma"].reading == "no-station" and rows["Gamma"].stations == 0
    assert rows["Alpha"].lines_passenger == 1 and rows["Alpha"].lines_all == 2
    assert rows["Alpha"].supply[0].cargo_name == "Coal"
    assert v.summary.window_samples == 16 and abs(v.summary.span_years - 3.75) < 0.01
    assert v.growth.window_sufficient and rows["Gamma"].id in v.growth.stalled
    assert rows["Alpha"].id not in v.growth.stalled and rows["Zeta"].id not in v.growth.stalled
    names = {r.id: r.name for r in v.rows}
    assert {names[i] for i in v.coverage_screen.passenger_gaps} == {"Gamma", "Delta", "Epsilon", "Zeta"}
    assert {c.name for c in v.criteria} >= {"largeQuantile", "pairPool", "usageCap"}


def test_view_pairs_and_unknown_geometry(multi_year_store, tmp_path):
    v = view(multi_year_store, "towns")
    names = {r.id: r.name for r in v.rows}
    pairs = {(names[p.town_a], names[p.town_b]): p for p in v.pairs.pairs}
    assert not any({a, b} == {"Alpha", "Beta <script>x</script>"} for a, b in pairs)
    alpha_gamma = pairs[("Alpha", "Gamma")]
    assert alpha_gamma.status == "no-passenger-link" and alpha_gamma.distance_km == 90.0
    assert v.pairs.any_distance and len(v.pairs.pool) == 6
    store = Store(tmp_path / "nopos.db")
    for i, month in enumerate((1, 4, 7)):
        store.add_snapshot(_snapshot(1980, month, i, with_positions=False))
    bare = view(store, "towns")
    assert not bare.pairs.any_distance and all(p.distance_km is None for p in bare.pairs.pairs)
    assert all(r.position is None for r in bare.rows)
    store.close()


def test_report_numbers_equal_view(multi_year_store):
    v = view(multi_year_store, "towns")
    doc = document(multi_year_store, "towns")
    ranking = next(t for t in _tables(doc) if t.columns[1] == "Town" and "Growth/yr" in t.columns)
    assert [r[1] for r in ranking.rows] == [r.name for r in v.rows if r.capacity is not None][: len(ranking.rows)]
    assert [r[2].replace(",", "") for r in ranking.rows] == [f"{r.capacity:.0f}" for r in v.rows][: len(ranking.rows)]
    evolution = next(t for t in _tables(doc) if t.columns[0] == "Sample")
    assert [r[0] for r in evolution.rows] == [p.label for p in v.evolution]
    assert evolution.rows[0][0] == "1980-01-01" and evolution.rows[-1][0] == "1983-10-01"
    pairs = next(t for t in _tables(doc) if t.columns[0] == "Town A")
    names = {r.id: r.name for r in v.rows}
    assert [(r[0], r[1]) for r in pairs.rows] == [(names[p.town_a], names[p.town_b]) for p in v.pairs.pairs][
        : len(pairs.rows)
    ]
    by_cargo = next(t for t in _tables(doc) if t.columns[0] == "Cargo")
    assert [r[0] for r in by_cargo.rows] == [c.cargo_name for c in v.cargo_demand.by_cargo]
    coal = v.cargo_demand.by_cargo[0]
    assert coal.towns == 2 and coal.zero_supply_towns == 1 and coal.producers == 1 and coal.unshipped_year == 80


def test_view_is_serializable(multi_year_store):
    v = view(multi_year_store, "towns")
    encoded = json.dumps(plain(v), allow_nan=False)
    assert '"rows"' in encoded and '"criteria"' in encoded
    assert plain(
        evaluate_views(multi_year_store, _context_at(multi_year_store, multi_year_store.latest()), ("towns",)).towns
    ) == plain(v)


def test_entities_after_an_earlier_endpoint_are_excluded(multi_year_store):
    earlier = multi_year_store.hydrate(1981 * YEAR + 7 * (YEAR // 12))
    future = _snapshot(1984, 1, 20)
    future.raw["towns"].append(
        {"id": 99, "name": "Future Town", "capacities": [900, 900, 900], "lineUsage": 0.1, "cargoSupply": []}
    )
    future.raw["cargos"].append({"id": 8, "name": "Future Cargo", "res": "::/cargos/f/f.cargo"})
    multi_year_store.add_snapshot(future)
    ctx = _context_at(multi_year_store, earlier)
    v = evaluate_views(multi_year_store, ctx, ("towns",)).towns
    assert "Future Town" not in {r.name for r in v.rows}
    assert v.summary.window_last.tick == earlier.game_time and v.summary.window_samples == 7
    assert v.coverage.endpoint.tick == earlier.game_time and v.coverage.eligible == 7
    assert v.rows[0].name == "Alpha" and v.rows[0].delta == 60  # 6 steps, not the later 20


def test_bounded_hydration_and_counts_for_large_history(tmp_path):
    store = Store(tmp_path / "long.db")
    n = 0
    for year in range(1900, 1915):
        for month in range(1, 13):
            store.add_snapshot(_snapshot(year, month, n))
            n += 1
    v = view(store, "towns")
    assert v.coverage.eligible == 180 and v.coverage.used == 180 and v.coverage.read == 180
    assert v.coverage.hydrated <= v.coverage.hydration_limit
    assert len(v.evolution) <= 40 and v.evolution[0].label == "1900-01-01" and v.evolution[-1].label == "1914-12-01"
    assert len(v.coverage.sampled) == len(v.evolution)
    assert _rows(v)["Alpha"].delta == 10 * 179
    store.close()


def test_zero_usage_note_requires_a_known_usage(tmp_path):
    store = Store(tmp_path / "unknown-usage.db")
    for i, month in enumerate((1, 4, 7)):
        snap = _snapshot(1980, month, i)
        for town in snap.raw["towns"]:
            if town["name"] == "Alpha":
                town.pop("lineUsage")
            if town["name"] == "Beta <script>x</script>":
                town["lineUsage"] = 0.0
        store.add_snapshot(snap)
    v = view(store, "towns")
    rows = _rows(v)
    assert v.coverage_screen.zero_usage == (rows["Beta <script>x</script>"].id,)
    assert rows["Alpha"].usage is None and rows["Alpha"].reading == "usage-unknown"
    store.close()


def test_unreported_industry_flows_are_not_zero(tmp_path):
    store = Store(tmp_path / "flows.db")
    snap = _snapshot(1980, 1, 0)
    snap.raw["industries"].append({"id": 8, "name": "Unreporting", "outputs": [{"cargo": 3}]})
    store.add_snapshot(snap)
    coal = view(store, "towns").cargo_demand.by_cargo[0]
    assert coal.producers == 2 and coal.produced_year == 100 and coal.unshipped_year == 80
    assert coal.produced_unknown == 1 and coal.unshipped_unknown == 1
    cell = next(t for t in _tables(document(store, "towns")) if t.columns[0] == "Cargo").rows[0]
    assert "unreported" in cell[7] and "unreported" in cell[8]
    store.close()


def test_idle_cargo_needs_known_flows(tmp_path):
    store = Store(tmp_path / "idle.db")
    snap = _snapshot(1980, 1, 0)
    snap.raw["industries"] = [{"id": 7, "name": "Mine", "outputs": [{"cargo": 3}]}]
    for town in snap.raw["towns"]:
        town["cargoSupply"] = [{"cargo": 3, "supply": 0, "limit": 50.0}] if town["id"] == 1 else []
    store.add_snapshot(snap)
    assert view(store, "towns").cargo_demand.idle_cargos == ()
    snap2 = _snapshot(1980, 2, 0)
    snap2.raw["industries"] = [
        {"id": 7, "name": "Mine", "outputs": [{"cargo": 3, "producedYear": 0, "shippedYear": 0}]}
    ]
    for town in snap2.raw["towns"]:
        town["cargoSupply"] = [{"cargo": 3, "supply": 0, "limit": 50.0}] if town["id"] == 1 else []
    store.add_snapshot(snap2)
    assert view(store, "towns").cargo_demand.idle_cargos == (3,)
    store.close()


def test_ambiguous_calendar_keeps_only_the_latest_sample(tmp_path):
    store = Store(tmp_path / "ambiguous.db")
    store.add_snapshot(_snapshot(1980, 1, 0))
    store.add_snapshot(_snapshot(1980, 4, 1))
    late = _snapshot(1980, 7, 2)
    late.raw["meta"]["date"] = {"year": 1979, "month": 1, "day": 1}  # date goes backwards while the tick advances
    store.add_snapshot(late)
    v = view(store, "towns")
    assert v.coverage.eligible == 3
    assert v.coverage.used == 1 and v.summary.span_years is None and v.growth.window_sufficient is False
    assert any(u.code == "ambiguous-timeline" for u in v.coverage.unavailable)
    store.close()
