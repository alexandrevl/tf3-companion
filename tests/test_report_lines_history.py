import json
from html.parser import HTMLParser

import pytest
from conftest import YEAR, base_snapshot
from methodology_helpers import methodology
from view_helpers import document, view

from tf3companion import reports
from tf3companion.analysis_views import EvaluationContext, evaluate_views
from tf3companion.analysis_views.models import plain
from tf3companion.report_policy import resolve_context
from tf3companion.snapshot import Snapshot
from tf3companion.store import Store


def _line(lid, name, profit, vehicles, now, load=0.5):
    vids = [lid * 100 + k for k in range(vehicles)]
    return {
        "id": lid, "name": name, "vehicles": vids, "stops": [{"stationGroup": 500}, {"stationGroup": 501}],
        "profitYear": profit, "transportedYear": 1000, "rate": 100,
        "capacity": [{"cargo": 0, "used": int(100 * load), "capacity": 100}], "issues": [],
    }, [
        {"id": v, "name": f"V{v}", "carrier": "ROAD", "state": "EN_ROUTE", "line": lid,
         "purchaseTime": now - YEAR // 10 if lid == 104 else 10 * YEAR, "profitYear": 0, "models": [7], "value": 1000}
        for v in vids
    ]


def _snap(i: int, specs: list[tuple]) -> Snapshot:
    """Month index i (0 = Jan of year 1980); gameTime spaced so a year is YEAR ticks."""
    gt = 10 * YEAR + round(i * YEAR / 12)
    data = base_snapshot(game_time=gt)
    data["meta"]["date"] = {"year": 1980 + i // 12, "month": i % 12 + 1, "day": 1}
    data["lines"], data["vehicles"] = [], []
    for lid, name, profit, veh in specs:
        line, vehicles = _line(lid, name, profit, veh, gt)
        data["lines"].append(line)
        data["vehicles"].extend(vehicles)
    return Snapshot(data, source=f"s{i}.lua")


@pytest.fixture
def multi_year(tmp_path):
    store = Store(tmp_path / "mh.db")
    for i in range(37):
        specs = [
            (100, "Rising <b>Line</b> | x", 100_000 + 20_000 * i, 2),
            (101, "Falling", 2_000_000 - 30_000 * i, 2 if i < 20 else 4),
            (102, "Flat", 500_000 + (5_000 if i % 2 else -5_000), 2),
            (103, "Sawtooth", 100_000 if i % 2 else 500_000, 2),
            (106, "Chronic loss", -50_000, 1),
        ]
        if i <= 15:
            specs.append((105, "Gone", 10_000, 1))
        if i >= 30:
            specs.append((104, "Fresh", 1_000 * i, 1))
        store.add_snapshot(_snap(i, specs))
    yield store
    store.close()


def _cls(doc):
    table = next(b for b in doc.blocks if isinstance(b, reports.Table) and b.columns[0] == "Line"
                 and "Class" in b.columns and "Profit path" in b.columns)
    return {row[0]: row[1] for row in table.rows}


def _context(store, snap, **policies):
    resolved = resolve_context(methodology(report_policies=policies)) if policies else resolve_context()
    return EvaluationContext(snap, resolved, store.time_context(snap), None, store.previous_of(snap))


def _by_name(v):
    return {t.name: t for t in v.trajectories}


def test_no_snapshot_raises(tmp_path):
    store = Store(tmp_path / "empty.db")
    with pytest.raises(ValueError):
        document(store, "lines-history")


def test_multi_year_classification_and_sections(multi_year):
    doc = document(multi_year, "lines-history")
    assert doc.kind == "lines-history"
    classes = _cls(doc)
    assert classes["Rising <b>Line</b> | x"] == "improving"
    assert classes["Falling"] == "deteriorating"
    assert classes["Flat"] == "stable"
    assert classes["Sawtooth"] == "stable"
    assert classes["Fresh"] == "too new"
    assert "Gone" not in classes  # removed lines are not classified
    headers = dict(doc.header)
    assert "last year" in headers["Evaluation Window"]

    md = reports.render_markdown(doc)
    assert "## Classification Rule" in md
    assert "median absolute deviation" in md
    assert "### Created lines (1)".replace("(", "\\(").replace(")", "\\)") in md
    assert "Gone" in md and "Fresh" in md

    events = [b for b in doc.blocks if isinstance(b, reports.Table) and "Verdict" in b.columns]
    assert events
    row = next(r for r in events[0].rows if r[0] == "Falling")
    assert row[2] == "2 → 4" and row[-1] == "profit fell"

    follow = next(b for b in doc.blocks if isinstance(b, reports.Table) and "Suggested manual check" in b.columns)
    names = [r[0] for r in follow.rows]
    assert "Falling" in names and "Chronic loss" in names


def test_view_classes_threshold_terms_and_maturity(multi_year):
    v = view(multi_year, "lines-history")
    lines = _by_name(v)
    assert v.window_kind == "last-year" and v.span.value is not None and v.span.value >= 1.5
    for name in ("Rising <b>Line</b> | x", "Falling", "Flat", "Sawtooth"):
        t = lines[name]
        assert t.k >= 2 and t.window_samples >= 5
        assert t.threshold == max(t.relative_term, t.noise_term, t.floor_term)
        assert t.delta == pytest.approx(t.recent - t.early)
    rising, falling, flat, saw = (lines["Rising <b>Line</b> | x"], lines["Falling"], lines["Flat"], lines["Sawtooth"])
    assert rising.trend_class == "improving" and rising.delta > rising.threshold
    assert falling.trend_class == "deteriorating" and falling.delta < -falling.threshold
    assert rising.mad < 0.001 * abs(rising.delta)         # a steady trend adds (almost) no noise
    assert saw.noise_term == pytest.approx(2 * saw.mad)
    assert flat.trend_class == saw.trend_class == "stable"
    fresh = lines["Fresh"]
    assert fresh.trend_class == "too new" and fresh.reason == "too-new"
    assert fresh.maturity.value is not None and fresh.maturity.value < 1 and fresh.delta is None
    gone = lines["Gone"]
    assert not gone.current and gone.trend_class == "insufficient data" and gone.reason == "removed"
    assert gone.threshold is None and gone.window_points == ()
    assert v.floor == pytest.approx(0.02 * v.median_current_profit)


def test_nondefault_policy_changes_decision_terms_not_measurements(multi_year):
    snap = multi_year.latest()
    default = _by_name(evaluate_views(multi_year, _context(multi_year, snap), ("lines-history",)).lines_history)
    strict = _by_name(evaluate_views(multi_year, _context(multi_year, snap, **{"lines-history": {"floor_share": 1}}),
                                     ("lines-history",)).lines_history)
    name = "Rising <b>Line</b> | x"
    assert default[name].trend_class == "improving" and strict[name].trend_class == "stable"
    for field in ("early", "recent", "delta", "mad", "k", "window_samples"):
        assert getattr(default[name], field) == getattr(strict[name], field)
    assert strict[name].floor_term > default[name].floor_term


def test_vehicle_changes_created_removed_and_follow_ups(multi_year):
    v = view(multi_year, "lines-history")
    fell = next(e for e in v.vehicle_changes if e.name == "Falling")
    assert (fell.vehicles_before, fell.vehicles_after) == (2, 4) and fell.verdict == "profit-fell"
    assert fell.delta < -fell.threshold and fell.samples_after >= 2
    assert fell.profit_per_vehicle_before == pytest.approx(fell.profit_before / 2)
    assert fell.profit_per_vehicle_after == pytest.approx(fell.profit_after / 4)
    assert [e.verdict for e in v.vehicle_changes][0] == "profit-fell"
    assert v.additions + v.reductions == len(v.vehicle_changes)
    assert v.changes_comparable
    assert [c.name for c in v.created] == ["Fresh"] and [c.name for c in v.removed] == ["Gone"]
    gone = v.removed[0]
    assert gone.window_start.tick < gone.window_end.tick and gone.trend_class is None
    assert gone.profit_last == 10_000
    codes = {f.name: f.code for f in v.follow_ups}
    assert codes["Falling"] == "declining-without-added-vehicles"   # fleet was already 4 at the window start
    assert codes["Chronic loss"] == "persistent-loss"
    assert all(f.occupancy_samples > 0 for f in v.follow_ups)


def test_report_agrees_with_view(multi_year):
    v = view(multi_year, "lines-history")
    doc = document(multi_year, "lines-history")
    classes = _cls(doc)
    assert classes == {t.name: t.trend_class for t in v.trajectories if t.current}
    events = next(b for b in doc.blocks if isinstance(b, reports.Table) and "Verdict" in b.columns)
    assert [r[0] for r in events.rows] == [e.name for e in v.vehicle_changes][:25]
    det = next(b for b in doc.blocks if isinstance(b, reports.Table) and b.columns[0] == "Line" and "Noise threshold" in b.columns)
    by_id = {t.line_id: t for t in v.trajectories}
    expected = [by_id[i].name for i in next(o.line_ids for o in v.class_order if o.trend_class == "deteriorating")]
    assert [r[0] for r in det.rows] == expected
    summary = next(b for b in doc.blocks if isinstance(b, reports.Table) and b.columns[0] == "Class")
    assert {r[0]: r[1] for r in summary.rows} == {s.trend_class: s.lines for s in v.class_summary}
    assert dict(doc.header)["Occupancy Samples"].startswith(f"{len(v.coverage.sampled)} snapshots")


def test_endpoint_excludes_later_samples_and_lines(multi_year):
    multi_year.add_snapshot(_snap(37, [(999, "Future-only line", 9_000_000, 2)]))
    snap = multi_year.hydrate(10 * YEAR + round(25 * YEAR / 12))
    ctx = _context(multi_year, snap)
    v = evaluate_views(multi_year, ctx, ("lines-history",)).lines_history
    names = {t.name for t in v.trajectories}
    assert "Fresh" not in names and "Future-only line" not in names
    assert v.samples[-1].tick == snap.game_time and v.coverage.endpoint.tick == snap.game_time
    assert v.coverage.eligible == 26 and v.coverage.used == 26
    assert all(p.tick <= snap.game_time for t in v.trajectories for p in t.points)
    assert all(s.tick <= snap.game_time for s in v.coverage.sampled)
    doc = document_at(multi_year, ctx, v)
    assert "Future-only line" not in reports.render_markdown(doc)


def document_at(store, ctx, v):
    from tf3companion import report_lines_history
    return report_lines_history.build(v, context=ctx)


def test_view_is_serializable_and_bounded(multi_year):
    v = view(multi_year, "lines-history")
    payload = json.loads(json.dumps(plain(v)))
    assert payload["trajectories"][0]["points"][0]["tick"] == v.trajectories[0].points[0].tick
    assert payload["coverage"]["eligible"] == 37 and payload["coverage"]["used"] == 37
    assert v.coverage.hydrated <= v.coverage.hydration_limit == 12
    assert 0 < len(v.coverage.sampled) <= 12 and v.coverage.sampled[-1].tick == v.samples[-1].tick


def test_larger_history_reads_every_sample_but_hydrates_at_most_twelve(tmp_path):
    store = Store(tmp_path / "long.db")
    for i in range(80):
        store.add_snapshot(_snap(i, [(100, "Only", 100_000 + 1_000 * i, 2)]))
    v = view(store, "lines-history")
    store.close()
    assert v.coverage.eligible == 80 and v.coverage.used == 80
    assert len(v.trajectories[0].points) == 80
    assert v.coverage.hydrated <= 12 and len(v.coverage.sampled) <= 12


def test_one_retained_sample_per_date(tmp_path):
    store = Store(tmp_path / "dup.db")
    for i in range(6):
        store.add_snapshot(_snap(i, [(100, "Only", 100_000 + 1_000 * i, 2)]))
    twin = _snap(3, [(100, "Only", 777, 2)])
    twin.raw["meta"]["gameTime"] += 3
    store.add_snapshot(twin)
    store.add_snapshot(_snap(6, [(100, "Only", 106_000, 2)]))
    v = view(store, "lines-history")
    store.close()
    assert v.coverage.eligible == 8 and v.coverage.used == 7
    point = next(p for p in v.trajectories[0].points if p.date == twin.date_label)
    assert point.tick == twin.game_time and point.profit == 777


def test_charts_have_matching_tables_and_html_is_offline(multi_year):
    doc = document(multi_year, "lines-history")
    for i, b in enumerate(doc.blocks):
        if isinstance(b, reports.Chart) and b.kind == "line":
            table = next(x for x in doc.blocks[i + 1:] if isinstance(x, reports.Table))
            assert [r[0] for r in table.rows] == b.categories
            assert len(table.columns) == len(b.series) + 1
    html = reports.render_html(doc)
    assert "<script" not in html and "http" not in html.replace("http://www.w3.org/2000/svg", "")
    assert "<b>Line</b>" not in html

    class P(HTMLParser):
        pass
    P().feed(html)


def test_deterministic(multi_year):
    assert (reports.render_markdown(document(multi_year, "lines-history"))
            == reports.render_markdown(document(multi_year, "lines-history")))


def test_short_history_degrades(tmp_path):
    store = Store(tmp_path / "one.db")
    snap = _snap(0, [(100, "Solo", 1000, 2)])
    for vehicle in snap.raw["vehicles"]:
        vehicle["purchaseTime"] -= YEAR
    store.add_snapshot(snap)
    doc = document(store, "lines-history")
    assert _cls(doc)["Solo"] == "insufficient data"
    md = reports.render_markdown(doc)
    assert "Insufficient data" in md
    assert "Compact Trajectory Table" in md
    assert not view(store, "lines-history").changes_comparable
    store.close()


def test_short_history_five_months_uses_whole_history(tmp_path):
    store = Store(tmp_path / "short.db")
    store.add_snapshot(_snap(-6, []))
    for i in range(8):
        snap = _snap(i, [(100, "Down", 1_000_000 - 100_000 * i, 2), (101, "Same", 300_000, 1)])
        for vehicle in snap.raw["vehicles"]:
            vehicle["purchaseTime"] = 10 * YEAR - YEAR // 2
        store.add_snapshot(snap)
    doc = document(store, "lines-history")
    assert dict(doc.header)["Evaluation Window"] == "entire stored history"
    assert _cls(doc) == {"Down": "deteriorating", "Same": "stable"}
    store.close()
