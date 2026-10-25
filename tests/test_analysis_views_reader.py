"""Endpoint-bounded, batched evidence access shared by every analysis view."""
from __future__ import annotations

from contextlib import closing

import pytest

from conftest import base_snapshot
from tf3companion import store as store_module
from tf3companion.analysis_views import EvaluationContext, EvidenceReader, evaluate_views, select_views
from tf3companion.report_policy import resolve_context
from tf3companion.snapshot import Snapshot
from tf3companion.store import Store

TICKS = [100 + 10 * i for i in range(600)]


def _snap(tick: int, catalog: bool = False, profit: int = 1) -> Snapshot:
    data = base_snapshot(game_time=tick)
    data["meta"]["date"] = {"year": 1980 + tick // 1000, "month": 1 + tick % 12, "day": 1}
    data["lines"][0]["profitYear"] = profit + tick
    if catalog:
        data["catalog"] = [{"id": 7, "name": f"Model@{tick}", "carrier": "RAIL"}]
    return Snapshot(data)


@pytest.fixture
def long_store(tmp_path):
    with closing(Store(tmp_path / "long.db")) as store:
        for tick in TICKS:
            store.add_snapshot(_snap(tick, catalog=tick in (150, 5000)))
        yield store


def _reader(store: Store, endpoint: int) -> EvidenceReader:
    snap = store.hydrate(endpoint)
    return EvidenceReader(store, EvaluationContext(snap, resolve_context(), store.time_context(snap), None, None))


def test_compact_iterators_stop_at_the_endpoint_and_visit_every_eligible_sample(long_store):
    reader = _reader(long_store, 3000)
    eligible = [t for t in TICKS if t <= 3000]
    assert reader.count_samples() == len(eligible)
    assert [tick for tick, _label, _date in reader.sample_index()] == eligible
    assert [p["game_time"] for p in reader.company_points()] == eligible
    rows = list(reader.line_points(100))
    assert [r["game_time"] for r in rows] == eligible
    assert rows[-1]["profit_year"] == 1 + 3000
    projection = list(reader.projection(("company", "missing")))
    assert [tick for tick, _, _ in projection] == eligible
    assert "missing" not in projection[0][2] and projection[0][2]["company"]["balance"] == 5_000_000
    visited = [tick for tick, _, parts in reader.projection(("meta",), ticks={150, 160, 9999})]
    assert visited == [150, 160]


def test_rows_are_fetched_in_bounded_batches(long_store, monkeypatch):
    sizes = []

    class Spy:
        def __init__(self, cursor):
            self.cursor = cursor

        def fetchmany(self, size):
            sizes.append(size)
            return self.cursor.fetchmany(size)

    real = long_store.conn

    class Conn:
        def execute(self, sql, params=()):
            cursor = real.execute(sql, params)
            return Spy(cursor) if "ORDER BY game_time" in sql and "FROM snapshots" in sql else cursor

        def __getattr__(self, name):
            return getattr(real, name)

    assert store_module.FETCH_BATCH == 256
    monkeypatch.setattr(long_store, "conn", Conn())
    assert len(list(long_store.iter_company_points(2**40))) == len(TICKS)
    assert set(sizes) == {256} and len(sizes) == len(TICKS) // 256 + 2


def test_full_hydration_is_bounded_counted_and_never_after_the_endpoint(long_store):
    reader = _reader(long_store, 3000)
    with pytest.raises(ValueError, match="after the selected endpoint"):
        reader.hydrate(3010)
    with pytest.raises(ValueError, match="after the selected endpoint"):
        reader.at_or_before(5000)
    assert reader.hydrated == 0
    recent = reader.recent(12)
    assert [s.game_time for s in recent] == [t for t in TICKS if t <= 3000][-12:]
    assert reader.hydrated == 11                       # the endpoint itself is already selected
    reader.hydrate(recent[0].game_time)
    reader.recent(12)
    assert reader.hydrated == 11                       # operation-local reuse, no second read


def test_catalog_is_the_newest_at_or_before_the_endpoint(long_store):
    assert _reader(long_store, 3000).catalog().game_time == 150
    late = _reader(long_store, 5100)
    assert late.catalog().game_time == 5000 and late.catalog() is late.catalog()
    assert _reader(long_store, 140).catalog() is None


def test_selection_is_closed_ordered_and_collapsed():
    assert select_views(None) == () and select_views([]) == ()
    assert select_views(["towns", "bottlenecks", "towns"]) == ("bottlenecks", "towns")
    for bad in (["nope"], "towns", [3], ["Towns"]):
        with pytest.raises(ValueError, match="valid names"):
            select_views(bad)


def test_empty_selection_reads_no_history(long_store, monkeypatch):
    for name in ("iter_sample_index", "iter_company_points", "iter_line_points", "iter_projection", "hydrate",
                 "recent_snapshots", "latest_with_catalog"):
        monkeypatch.setattr(long_store, name, lambda *a, **k: pytest.fail("history was read"))
    snap = _snap(3000)
    context = EvaluationContext(snap, resolve_context(), None, None, None)
    assert evaluate_views(long_store, context, ()).to_dict() == {}
