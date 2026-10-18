from contextlib import closing

import pytest

from conftest import base_snapshot
from tf3companion.report_industries import build, _flatten, _sample_of, _pick_evenly
from tf3companion.reports import Chart, Table, render_html, render_markdown
from tf3companion.snapshot import Snapshot
from tf3companion.store import Store


def industry(iid=10, name="Mine", produced=100, shipped=50, level=2, closure=0):
    return {"id": iid, "name": name, "type": "industries/coal_mine/coal_mine.con",
            "level": level, "maxLevel": 6, "closureTimeStamp": closure, "productionRating": 1,
            "inputs": [], "outputs": [{"cargo": 3, "producedYear": produced,
                                         "maxProductionYear": 100, "shippedYear": shipped}]}


def add(store, tick, date, inds, stocks=None):
    raw = base_snapshot(tick)
    raw["meta"]["date"] = dict(zip(("year", "month", "day"), date))
    raw["industries"] = inds
    if stocks is not None:
        raw["stocks"] = stocks
    store.add_snapshot(Snapshot(raw, source=f"sample-{tick}.lua"))
    return raw


def test_no_snapshot(tmp_path):
    with closing(Store(tmp_path / "empty.db")) as store:
        with pytest.raises(ValueError, match="No snapshot"):
            build(store)


def test_realistic_change_lifecycle_and_closure_calendar(tmp_path):
    with closing(Store(tmp_path / "x.db")) as store:
        before = industry()
        before["productionRating"] = 0.7
        add(store, 1000, (1980, 1, 1), [before, industry(20, "Closing", 0, 0, closure=4000)])
        add(store, 4100, (1980, 2, 1), [industry(produced=140, shipped=100, level=3), industry(30, "New")])
        text = render_markdown(build(store))
        assert "100 → 140" in text
        assert "50 → 100" in text
        assert "2 → 3" in text
        assert "Closed" in text and "as scheduled" in text and "Closing" in text
        assert "New industry" in text
        assert "31 calendar days" in text
        assert "Production-rating changes" in text


def test_ratio_above_one_is_not_silently_capped(tmp_path):
    with closing(Store(tmp_path / "x.db")) as store:
        add(store, 1000, (1980, 1, 1), [industry(shipped=120)])
        add(store, 2000, (1980, 2, 1), [industry(shipped=150)])
        text = render_markdown(build(store))
        assert "120.0%" in text and "150.0%" in text
        assert "stock draw-down" in text


def test_single_snapshot_and_missing_sections(tmp_path):
    with closing(Store(tmp_path / "x.db")) as store:
        add(store, 1000, (1980, 1, 1), [industry()])
        doc = build(store)
        text = render_markdown(doc)
        assert "single snapshot" in text
        assert "Insufficient data" in text
        assert "no snapshot contains stock data" in text
        assert not any(isinstance(b, Chart) and b.kind == "line" for b in doc.blocks)


def test_missing_flow_values_are_not_zero():
    raw = base_snapshot()
    ind = industry()
    ind["outputs"][0].pop("shippedYear")
    raw["industries"] = [ind]
    flat = _flatten(Snapshot(raw))
    assert not flat[10].outs
    assert not flat[10].idle


def test_all_unknown_flows_degrade_clearly(tmp_path):
    with closing(Store(tmp_path / "x.db")) as store:
        ind = industry()
        ind["outputs"][0].pop("producedYear")
        add(store, 1000, (1980, 1, 1), [ind])
        text = render_markdown(build(store))
        assert "no industry has complete" in text
        assert "unknown, not zero" in text


def test_stocks_and_safe_offline_html(tmp_path):
    name = '<script>alert(1)</script> | "bad"'
    with closing(Store(tmp_path / "x.db")) as store:
        for tick, month, count in [(1000, 1, 50), (2000, 2, 95)]:
            add(store, tick, (1980, month, 1), [industry(name=name)],
                [{"kind": "industry", "owner": 10, "stockId": 1, "cargos": [3], "count": count, "capacity": 100}])
        doc = build(store)
        md, html = render_markdown(doc), render_html(doc)
        assert "50.0% → 95.0%" in md and "+45.0 pp" in md
        assert '<script>' not in html
        assert '&lt;script&gt;' in html
        assert '<script' not in html and 'src="http' not in html


def test_multi_year_sampling_retains_endpoints_and_adjacent_tables(tmp_path):
    with closing(Store(tmp_path / "x.db")) as store:
        for year in range(1980, 1990):
            for month in range(1, 13):
                add(store, (year - 1979) * 1000 + month * 10, (year, month, 1),
                    [industry(produced=100 + (year - 1980) * 20, shipped=50 + (year - 1980) * 10)])
        doc = build(store)
        text = render_markdown(doc)
        assert "1980-01-01" in text and "1989-12-01" in text
        picks = _pick_evenly([_sample_of(s) for s in store.snapshots()])
        assert len(picks) <= 14 and picks[0].label == "1980-01-01" and picks[-1].label == "1989-12-01"
        for idx, block in enumerate(doc.blocks):
            if isinstance(block, Chart):
                assert isinstance(doc.blocks[idx - 1], Table)
                table = doc.blocks[idx - 1]
                assert len(table.rows) >= len(block.categories)


def test_chain_consumption_and_station_inference(tmp_path):
    with closing(Store(tmp_path / "x.db")) as store:
        ind = industry(name="Centre")
        ind["inputs"] = [{"cargo": 3, "consumedYear": 10, "maxConsumptionYear": 100}]
        raw = add(store, 1000, (1980, 1, 1), [ind])
        # Real bridge's line capacity uses a Lua index: cargoTypeId + 1.
        raw["lines"][0]["capacity"] = [{"cargo": 4, "used": 5, "capacity": 100}]
        store.add_snapshot(Snapshot(raw))
        text = render_markdown(build(store))
        assert "Centre" in text and "Train A" in text
        assert "cargo matches" in text and "Coal" in text
        assert "Input-limited" in text
        assert "NOT verified" in text
