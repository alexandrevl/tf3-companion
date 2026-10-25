import json
from contextlib import closing

import pytest

from conftest import base_snapshot
from tf3companion.analysis import Thresholds
from tf3companion.analysis_views import EvaluationContext, evaluate_views
from tf3companion.analysis_views.models import plain
from tf3companion.report_policy import resolve_context
from tf3companion.reports import Chart, Table, render_html, render_markdown
from tf3companion.snapshot import Snapshot
from tf3companion.store import Store
from view_helpers import document, view


def industry(iid=10, name="Mine", produced=100, shipped=50, level=2, closure=0):
    return {
        "id": iid,
        "name": name,
        "type": "industries/coal_mine/coal_mine.con",
        "level": level,
        "maxLevel": 6,
        "closureTimeStamp": closure,
        "productionRating": 1,
        "inputs": [],
        "outputs": [{"cargo": 3, "producedYear": produced, "maxProductionYear": 100, "shippedYear": shipped}],
    }


def add(store, tick, date, inds, stocks=None):
    raw = base_snapshot(tick)
    raw["meta"]["date"] = dict(zip(("year", "month", "day"), date))
    raw["industries"] = inds
    if stocks is not None:
        raw["stocks"] = stocks
    store.add_snapshot(Snapshot(raw, source=f"sample-{tick}.lua"))
    return raw


def industries_view(store):
    return view(store, "industries")


def at(store, tick, thresholds=None):
    snap = store.hydrate(tick)
    return EvaluationContext(
        snap, resolve_context(thresholds=thresholds), store.time_context(snap), None, store.previous_of(snap)
    )


def evaluated(store, tick):
    ctx = at(store, tick)
    return evaluate_views(store, ctx, ("industries",)).industries, ctx


def tables(doc):
    return [b for b in doc.blocks if isinstance(b, Table)]


def test_no_snapshot(tmp_path):
    with closing(Store(tmp_path / "empty.db")) as store:
        with pytest.raises(ValueError, match="No snapshot"):
            document(store, "industries")


def test_realistic_change_lifecycle_and_closure_calendar(tmp_path):
    with closing(Store(tmp_path / "x.db")) as store:
        before = industry()
        before["productionRating"] = 0.7
        add(store, 1000, (1980, 1, 1), [before, industry(20, "Closing", 0, 0, closure=4000)])
        add(store, 4100, (1980, 2, 1), [industry(produced=140, shipped=100, level=3), industry(30, "New")])
        text = render_markdown(document(store, "industries"))
        assert "100 → 140" in text
        assert "50 → 100" in text
        assert "2 → 3" in text
        assert "Closed" in text and "as scheduled" in text and "Closing" in text
        assert "New industry" in text
        assert "31 calendar days" in text
        assert "Production-rating changes" in text

        v = industries_view(store)
        assert [(e.code, e.industry.id) for e in v.events] == [
            ("closure-at-first-sample", 20),
            ("new-industry", 30),
            ("closed-as-scheduled", 20),
        ]
        assert v.events[0].remaining.status == "estimate" or v.events[0].remaining.status == "unavailable"
        assert v.comparison.common_count == 1
        assert (v.comparison.common_first.produced, v.comparison.common_last.produced) == (100, 140)
        assert (v.comparison.common_first.shipped, v.comparison.common_last.shipped) == (50, 100)
        assert v.comparison.level_ups == 1 and v.comparison.new_count == 1 and v.comparison.vanished_count == 1
        assert v.span.calendar_days == pytest.approx(31)
        change = v.levels.level_changes[0]
        assert (change.level_first, change.level_last) == (2, 3)
        assert v.levels.rating_changes[0].rating_first == pytest.approx(0.7)
        assert [(m.direction, m.delta) for m in v.levels.movers] == [("up", 40)]


def test_view_and_report_agree_on_numbers_membership_and_order(tmp_path):
    with closing(Store(tmp_path / "x.db")) as store:
        add(store, 1000, (1980, 1, 1), [industry(10, "Alpha", 100, 50), industry(20, "Beta", 200, 100, level=1)])
        add(
            store,
            2000,
            (1980, 2, 1),
            [industry(10, "Alpha", 150, 90, level=3), industry(20, "Beta", 400, 200, level=4)],
        )
        v, doc = industries_view(store), document(store, "industries")
        movers = [t for t in tables(doc) if t.columns[0] == "Direction"][0]
        assert [r[1] for r in movers.rows] == [m.name for m in v.levels.movers] == ["Beta", "Alpha"]
        assert [r[4] for r in movers.rows] == ["+200", "+50"]
        summary = [t for t in tables(doc) if t.columns[0] == "Metric"][0]
        produced = [r for r in summary.rows if r[0].startswith("Production")][0]
        assert produced[1:3] == [int(v.comparison.common_first.produced), int(v.comparison.common_last.produced)]
        levels = [t for t in tables(doc) if t.columns[0] == "Industry" and "Max level" in t.columns][0]
        assert [r[0] for r in levels.rows] == [c.name for c in v.levels.level_changes]
        assert dict(zip(("first", "last"), (doc.header[1][1], doc.header[2][1]))) == {
            "first": v.first.date,
            "last": v.latest.date,
        }


def test_ratio_above_one_is_not_silently_capped(tmp_path):
    with closing(Store(tmp_path / "x.db")) as store:
        add(store, 1000, (1980, 1, 1), [industry(shipped=120)])
        add(store, 2000, (1980, 2, 1), [industry(shipped=150)])
        text = render_markdown(document(store, "industries"))
        assert "120.0%" in text and "150.0%" in text
        assert "stock draw-down" in text
        v = industries_view(store)
        assert (v.comparison.common_first.ratio, v.comparison.common_last.ratio) == (1.2, 1.5)
        assert (v.service_by_cargo[0].ratio_first, v.service_by_cargo[0].ratio_last) == (1.2, 1.5)


def test_single_snapshot_and_missing_sections(tmp_path):
    with closing(Store(tmp_path / "x.db")) as store:
        add(store, 1000, (1980, 1, 1), [industry()])
        doc = document(store, "industries")
        text = render_markdown(doc)
        assert "single snapshot" in text
        assert "Insufficient data" in text
        assert "no snapshot contains stock data" in text
        assert not any(isinstance(b, Chart) and b.kind == "line" for b in doc.blocks)
        v = industries_view(store)
        assert v.comparison is None and v.events == () and v.levels is None
        assert {u.code for u in v.coverage.unavailable} >= {"insufficient-comparison", "no-stock-data"}


def test_missing_flow_values_are_not_zero(tmp_path):
    with closing(Store(tmp_path / "x.db")) as store:
        ind = industry()
        ind["outputs"][0].pop("shippedYear")
        add(store, 1000, (1980, 1, 1), [ind, industry(11, "Good", 80, 20)])
        v = industries_view(store)
        flat = {i.id: i for i in v.industries}
        assert flat[10].unknown_flows and not flat[10].outputs
        assert not flat[10].idle and not flat[10].producing
        assert v.unknown_flow_count == 1
        assert v.status == "ok"
        # the incomplete industry is excluded from the totals, not counted as zero
        assert v.evolution[0].stats.n == 2 and v.evolution[0].stats.produced == 80
        assert "1 latest industries excluded" in dict(document(store, "industries").header)["Unknown Flows"]


def test_all_unknown_flows_degrade_clearly(tmp_path):
    with closing(Store(tmp_path / "x.db")) as store:
        ind = industry()
        ind["outputs"][0].pop("producedYear")
        add(store, 1000, (1980, 1, 1), [ind])
        text = render_markdown(document(store, "industries"))
        assert "no industry has complete" in text
        assert "unknown, not zero" in text
        v = industries_view(store)
        assert v.status == "incomplete-flows" and v.evolution is None
        assert any(u.code == "no-industry-with-complete-flows" for u in v.coverage.unavailable)


def test_no_industries_in_latest_sample(tmp_path):
    with closing(Store(tmp_path / "x.db")) as store:
        add(store, 1000, (1980, 1, 1), [])
        assert industries_view(store).status == "no-industries"
        assert "lists no industries" in render_markdown(document(store, "industries"))


def test_stocks_and_safe_offline_html(tmp_path):
    name = '<script>alert(1)</script> | "bad"'
    with closing(Store(tmp_path / "x.db")) as store:
        for tick, month, count in [(1000, 1, 50), (2000, 2, 95)]:
            add(
                store,
                tick,
                (1980, month, 1),
                [industry(name=name)],
                [{"kind": "industry", "owner": 10, "stockId": 1, "cargos": [3], "count": count, "capacity": 100}],
            )
        doc = document(store, "industries")
        md, html = render_markdown(doc), render_html(doc)
        assert "50.0% → 95.0%" in md and "+45.0 pp" in md
        assert "<script>" not in html
        assert "&lt;script&gt;" in html
        assert "<script" not in html and 'src="http' not in html
        st = industries_view(store).stocks
        assert st.samples_with_stocks == 2
        assert [(g.code, g.stocks_last, g.mean_fill_first, g.mean_fill_last) for g in st.groups][0] == (
            "output-shipped",
            1,
            0.5,
            0.95,
        )
        assert [(m.fill_first, m.fill_last) for m in st.movers] == [(0.5, 0.95)]


def test_multi_year_sampling_retains_endpoints_and_adjacent_tables(tmp_path):
    with closing(Store(tmp_path / "x.db")) as store:
        for year in range(1980, 1990):
            for month in range(1, 13):
                add(
                    store,
                    (year - 1979) * 1000 + month * 10,
                    (year, month, 1),
                    [industry(produced=100 + (year - 1980) * 20, shipped=50 + (year - 1980) * 10)],
                )
        doc = document(store, "industries")
        text = render_markdown(doc)
        assert "1980-01-01" in text and "1989-12-01" in text
        v = industries_view(store)
        picks = v.evolution
        assert len(picks) <= 14 and picks[0].sample.date == "1980-01-01" and picks[-1].sample.date == "1989-12-01"
        assert v.sample_count == 120 and v.coverage.eligible == 120 and v.coverage.used == 120
        assert [s.tick for s in v.coverage.sampled] == [p.sample.tick for p in picks]
        for idx, block in enumerate(doc.blocks):
            if isinstance(block, Chart):
                assert isinstance(doc.blocks[idx - 1], Table)
                table = doc.blocks[idx - 1]
                assert len(table.rows) >= len(block.categories)


def test_bounded_hydration_for_large_history(tmp_path):
    with closing(Store(tmp_path / "x.db")) as store:
        for n in range(60):
            add(store, 1000 + n * 100, (1980 + n // 12, n % 12 + 1, 1), [industry(produced=100 + n)])
        v = industries_view(store)
        assert v.coverage.eligible == 60 and v.coverage.used == 60 and v.coverage.read == 60
        assert v.coverage.hydrated <= v.coverage.hydration_limit
        assert len(v.evolution) <= 14 and v.coverage.omitted == 60 - len(v.evolution)


def test_chain_consumption_and_station_inference(tmp_path):
    with closing(Store(tmp_path / "x.db")) as store:
        ind = industry(name="Centre")
        ind["inputs"] = [{"cargo": 3, "consumedYear": 10, "maxConsumptionYear": 100}]
        raw = add(store, 1000, (1980, 1, 1), [ind])
        # Real bridge's line capacity uses a Lua index: cargoTypeId + 1.
        raw["lines"][0]["capacity"] = [{"cargo": 4, "used": 5, "capacity": 100}]
        store.add_snapshot(Snapshot(raw))
        text = render_markdown(document(store, "industries"))
        assert "Centre" in text and "Train A" in text
        assert "cargo matches" in text and "Coal" in text
        assert "Input-limited" in text
        assert "NOT verified" in text

        v = industries_view(store)
        status = v.chains.consumer_statuses[0]
        assert (status.status, status.limiting_cargo_name, status.consumed_last) == ("input-limited", "Coal", 10)
        link = v.links.links[0]
        assert link.industry.name == "Centre" and link.cargo_matches and link.serving_lines == ("Train A",)
        assert [c.name for c in link.matched_cargos] == ["Coal"]
        assert link.role == "producer-consumer"


def test_full_stock_threshold_comes_from_the_context(tmp_path):
    with closing(Store(tmp_path / "x.db")) as store:
        for tick, month in [(1000, 1), (2000, 2)]:
            add(
                store,
                tick,
                (1980, month, 1),
                [industry()],
                [{"kind": "industry", "owner": 10, "stockId": 1, "cargos": [3], "count": 80, "capacity": 100}],
            )
        default = view(store, "industries")
        lowered = view(store, "industries", Thresholds(full_stock_ratio=0.75))
        assert default.comparison.full_outputs_last == 0 and lowered.comparison.full_outputs_last == 1
        assert default.stocks.groups[0].mean_fill_last == lowered.stocks.groups[0].mean_fill_last == 0.8
        assert {c.name: c.value for c in lowered.criteria}["full_stock_ratio"] == 0.75
        assert [m.code for m in lowered.manual_review] == []


def test_manual_review_candidates(tmp_path):
    with closing(Store(tmp_path / "x.db")) as store:
        add(store, 1000, (1980, 1, 1), [industry(10, "Fall", 200, 50), industry(20, "Doomed", 50, 10, closure=9000)])
        add(store, 2000, (1980, 2, 1), [industry(10, "Fall", 100, 50), industry(20, "Doomed", 50, 10, closure=9000)])
        v = industries_view(store)
        assert [(r.priority, r.code, r.name) for r in v.manual_review] == [
            (1, "closure-flagged", "Doomed"),
            (2, "production-decline", "Fall"),
        ]
        assert v.manual_review[1].decline == 100
        text = render_markdown(document(store, "industries"))
        assert "Suggested Manual Review Priorities" in text and "200 → 100" in text


def test_historical_endpoint_excludes_later_entities_samples_and_stocks(tmp_path):
    with closing(Store(tmp_path / "x.db")) as store:
        add(store, 1000, (1980, 1, 1), [industry(10, "Old")])
        add(store, 2000, (1980, 2, 1), [industry(10, "Old", 120, 60)])
        add(
            store,
            3000,
            (1980, 3, 1),
            [industry(10, "Old", 130, 70), industry(99, "Future", 500, 0, closure=5000)],
            [{"kind": "industry", "owner": 10, "stockId": 1, "cargos": [3], "count": 99, "capacity": 100}],
        )
        v, ctx = evaluated(store, 2000)
        assert v.latest.tick == 2000 and v.sample_count == 2 and v.coverage.eligible == 2
        assert [i.name for i in v.industries] == ["Old"]
        assert all(e.industry.name != "Future" for e in v.events)
        assert v.stock_samples == 0 and v.stocks.samples_with_stocks == 0
        assert v.coverage.endpoint.tick == 2000
        assert "Future" not in render_markdown(
            __import__("tf3companion.report_industries", fromlist=["build"]).build(v, context=ctx)
        )


def test_views_are_serializable(tmp_path):
    with closing(Store(tmp_path / "x.db")) as store:
        ind = industry(20, "Centre")
        ind["inputs"] = [{"cargo": 3, "consumedYear": 10, "maxConsumptionYear": 100}]
        add(
            store,
            1000,
            (1980, 1, 1),
            [industry(), ind, industry(30, "Gone", 0, 0, closure=1500)],
            [{"kind": "industry", "owner": 10, "stockId": 1, "cargos": [3], "count": 50, "capacity": 100}],
        )
        add(
            store,
            2000,
            (1980, 2, 1),
            [industry(produced=150, shipped=0, level=3), ind],
            [{"kind": "industry", "owner": 10, "stockId": 1, "cargos": [3], "count": 95, "capacity": 100}],
        )
        payload = plain(industries_view(store))
        decoded = json.loads(json.dumps(payload))
        assert decoded["status"] == "ok" and decoded["coverage"]["eligible"] == 2
        assert decoded["comparison"]["commonCount"] == 2
        assert decoded["events"][0]["code"] in {"closure-at-first-sample", "closed-as-scheduled"}


def test_malformed_subresult_is_unavailable_not_healthy(tmp_path):
    with closing(Store(tmp_path / "x.db")) as store:
        raw = add(store, 1000, (1980, 1, 1), [industry(10, "Centre")])
        raw["stations"] = [{"id": 500, "name": "Centre", "lines": [[1]]}]  # unhashable line reference
        store.add_snapshot(Snapshot(raw))
        v = industries_view(store)
        assert v.links is None and v.closures is not None
        codes = {(u.code, u.subject) for u in v.coverage.unavailable}
        assert ("section-uninterpretable", "lines") in codes
        text = render_markdown(document(store, "industries"))
        assert "Section unavailable" in text
        # the other sections still render from the interpretable evidence
        assert "Closures and Risk" in text


def test_unknown_service_ratio_is_not_charted_as_zero(tmp_path):
    with closing(Store(tmp_path / "x.db")) as store:
        add(store, 1000, (1980, 1, 1), [industry(produced=100, shipped=50)])
        add(store, 2000, (1980, 2, 1), [industry(produced=0, shipped=0)])
        v = industries_view(store)
        assert [p.stats.ratio for p in v.evolution] == [0.5, None]
        doc = document(store, "industries")
        chart = [b for b in doc.blocks if isinstance(b, Chart) and b.title.startswith("Service ratio (%)")][0]
        assert chart.categories == ["1980-01-01"] and chart.series == [("Service ratio %", [50.0])]
        ratio_table = [t for t in tables(doc) if t.columns == ["Sample", "Service ratio (%)"]][0]
        assert ratio_table.rows[-1] == ["1980-02-01", "-"]


def test_equal_keys_order_by_entity_id_regardless_of_input_order(tmp_path):
    results = []
    for n, order in enumerate(((30, 31), (31, 30))):
        with closing(Store(tmp_path / f"x{n}.db")) as store:
            add(store, 1000, (1980, 1, 1), [industry()])
            add(store, 2000, (1980, 2, 1), [industry()] + [industry(i, "Twin", 100, 0) for i in order])
            results.append([e.industry.id for e in industries_view(store).events])
    assert results[0] == results[1] == [30, 31]
