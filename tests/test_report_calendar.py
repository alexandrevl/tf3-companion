"""Calendar evidence boundaries must survive report rendering and aggregation."""
from contextlib import closing
from datetime import date

import pytest

from conftest import base_snapshot
from tf3companion.analysis_views import VIEW_NAMES, EvaluationContext, evaluate_views
from tf3companion.report_policy import resolve_context
from tf3companion.reports import Note, Table, compose_report, render_html, render_markdown
from tf3companion.snapshot import Snapshot
from tf3companion.store import Store
from view_helpers import document, view


def observation(tick, dated, capacity, *, purchase=None):
    data = base_snapshot(tick)
    data["meta"]["date"] = dated
    data["towns"][0]["capacities"] = [capacity, 0, 0]
    if purchase is not None:
        data["vehicles"][0]["purchaseTime"] = purchase
    return Snapshot(data)


def tables(document):
    return [block for block in document.blocks if isinstance(block, Table)]


@pytest.mark.parametrize("dated", [None, {"year": 1980, "month": 1, "day": 1}])
def test_town_growth_never_annualizes_missing_or_zero_calendar_span(tmp_path, dated):
    with closing(Store(tmp_path / "towns.db")) as store:
        for tick, capacity in [(1000, 100), (2000, 120), (3000, 150)]:
            store.add_snapshot(observation(tick, dated, capacity))
        doc = document(store, "towns")
        ranking = next(t for t in tables(doc) if "Growth/yr" in t.columns)
        assert ranking.rows[0][ranking.columns.index("Growth/yr")] == "-"
        span = view(store, "towns").summary.span_years
        assert span is None if dated is None else span == 0


def test_purchase_cohorts_do_not_extrapolate_before_observed_history(tmp_path):
    with closing(Store(tmp_path / "cohorts.db")) as store:
        first = observation(1000, {"year": 1980, "month": 1, "day": 1}, 100, purchase=999)
        store.add_snapshot(first)
        last = observation(2000, {"year": 1980, "month": 2, "day": 1}, 110, purchase=999)
        last.raw["vehicles"].append({"id": 1001, "carrier": "ROAD", "purchaseTime": 1000})
        store.add_snapshot(last)
        doc = document(store, "history")
        cohort = next(t for t in tables(doc) if t.columns[0] == "Purchase Year")
        assert [(row[0], row[1]) for row in cohort.rows] == [("1980", 1)]
        assert len(store.latest().vehicles) == 2


def test_calendar_reversal_preserves_current_facts_without_comparative_growth(tmp_path):
    with closing(Store(tmp_path / "reversed.db")) as store:
        store.add_snapshot(observation(1000, {"year": 1980, "month": 2, "day": 1}, 100))
        store.add_snapshot(observation(2000, {"year": 1980, "month": 1, "day": 1}, 200))
        town_doc = document(store, "towns")
        ranking = next(t for t in tables(town_doc) if "Growth/yr" in t.columns)
        assert ranking.rows[0][ranking.columns.index("Growth/yr")] == "-"
        assert ranking.rows[0][ranking.columns.index("Change")] == "-"
        history_doc = document(store, "history")
        current = next(t for t in tables(history_doc) if t.columns[0] == "Latest observed fact")
        assert dict(current.rows)["Snapshot"] == "1980-01-01"
        assert not any("Annualised Growth" in table.columns for table in tables(history_doc))


def dated(year, month, day):
    return {"year": year, "month": month, "day": day}


def fleet(tick, when, purchases=(0, -1), profit=100):
    """A dated observation with one line, vehicles bought at `purchases`, and one industry."""
    data = base_snapshot(tick)
    data["meta"]["date"] = when
    data["lines"] = [{"id": 100, "name": "Line", "vehicles": [1000 + i for i in range(len(purchases))],
                      "stops": [{"stationGroup": 500}, {"stationGroup": 501}], "profitYear": profit,
                      "transportedYear": 5, "rate": 3, "capacity": [], "issues": []}]
    data["vehicles"] = [{"id": 1000 + i, "name": f"Vehicle {i}", "carrier": "ROAD", "state": "EN_ROUTE", "line": 100,
                         "purchaseTime": purchase, "profitYear": profit, "models": [7], "value": 10,
                         "maintenanceState": .9, "loadConfig": [{"cargo": 0, "capacity": 20}], "canCarry": [0]}
                        for i, purchase in enumerate(purchases)]
    data["industries"] = [{"id": 10, "name": "Mine", "type": "industries/coal_mine/coal_mine.con", "level": 3,
                           "maxLevel": 6, "closureTimeStamp": 0, "productionRating": 1, "inputs": [],
                           "outputs": [{"cargo": 3, "producedYear": 100, "maxProductionYear": 100, "shippedYear": 50}]}]
    return Snapshot(data)


def cell(table, key_column, key, column):
    return next(row[table.columns.index(column)] for row in table.rows if row[table.columns.index(key_column)] == key)


def text_of(document):
    return render_markdown(document)


@pytest.mark.parametrize("kind", ["history", "lines-history", "industries"])
def test_known_zero_calendar_span_is_zero_not_unknown_and_never_annualized(tmp_path, kind):
    with closing(Store(tmp_path / "zero.db")) as store:
        for tick in (0, 1000, 2000):
            store.add_snapshot(fleet(tick, dated(1980, 1, 1), purchases=(0, 1500)))
        document = compose_report(store, kind)
        found = tables(document)
        assert not any("Annualised Growth" in t.columns for t in found)
        if kind == "history":
            coverage = next(t for t in found if t.columns[0] == "Coverage fact")
            assert cell(coverage, "Coverage fact", "Calendar span (days)", "Value") == 0
            assert cell(coverage, "Coverage fact", "Game ticks per calendar day (whole-span diagnostic)", "Value") == "-"
        if kind == "industries":
            assert "0.000 GAME-YEAR" in text_of(document)


def test_null_calendar_never_reports_a_zero_span_or_ticks_per_day(tmp_path):
    with closing(Store(tmp_path / "null.db")) as store:
        for tick in (0, 1000, 2000):
            store.add_snapshot(fleet(tick, None))
        history = compose_report(store, "history")
        assert not any(t.columns[0] == "Coverage fact" and "Calendar span (days)" in [r[0] for r in t.rows]
                       for t in tables(history))
        industries = compose_report(store, "industries")
        assert "0.000 GAME-YEAR" not in text_of(industries)
        assert "missing-calendar-date" in text_of(industries)


def test_unknown_age_vehicles_are_neither_mature_nor_young_nor_cohort_members(tmp_path):
    with closing(Store(tmp_path / "unknown.db")) as store:
        for tick, when in [(0, dated(1980, 1, 1)), (1000, dated(1980, 7, 1)), (2000, dated(1981, 1, 1))]:
            # purchase 0 is an exact anchor; 1500 sits between observed anchors; -1 is before history.
            store.add_snapshot(fleet(tick, when, purchases=(0, 1500, -1)))
        roi_view = view(store, "vehicle-roi")
        ages = {o.id: o.age for o in roi_view.observations}
        assert ages[1002] is None and ages[1000] == pytest.approx(1, abs=.01) and ages[1001] is not None
        unknown = next(o for o in roi_view.observations if o.id == 1002)
        assert unknown.maturity == "unknown" and unknown.maturity not in ("mature", "young")
        assert roi_view.overall.mature + roi_view.overall.young <= 2
        cohorts = view(store, "history").cohorts
        assert sum(c.vehicles for c in cohorts.cohorts) == 2 and cohorts.unknown_vehicles == 1   # excluded, not zero-aged
        roi = compose_report(store, "vehicle-roi")
        by_age = [t for t in tables(roi) if t.columns[:2] == ["Carrier", "Age"]]
        assert all(sum(row[2] for row in t.rows) <= 2 for t in by_age)


def test_lines_history_never_calls_unknown_age_lines_mature_or_young(tmp_path):
    with closing(Store(tmp_path / "lines.db")) as store:
        for tick, when in [(0, dated(1980, 1, 1)), (1000, dated(1981, 1, 1)), (2000, dated(1983, 1, 1))]:
            store.add_snapshot(fleet(tick, when, purchases=(-1,)))
        text = text_of(compose_report(store, "lines-history"))
        assert "unknown calendar maturity is insufficient data, never a mature or young fact" in text
        assert "too new / insufficient data" in text


@pytest.mark.parametrize("kind", ["history", "lines-history", "industries", "vehicle-roi", "towns"])
def test_markdown_and_html_carry_identical_time_provenance(tmp_path, kind):
    with closing(Store(tmp_path / "parity.db")) as store:
        for tick, when in [(0, dated(1980, 1, 1)), (1000, dated(1980, 7, 1)), (2000, dated(1981, 1, 1))]:
            store.add_snapshot(fleet(tick, when, purchases=(0, 1500)))
        basis = store.time_context(store.latest()).time_basis
        document = compose_report(store, kind)
        markdown, html = render_markdown(document), render_html(document)
        for rendering in (markdown, html):
            assert basis["anchorHash"] in rendering
            assert "game-calendar-v1" in rendering
        for key, value in document.header:
            if "Time" in key or "Span" in key:
                plain = value.replace("&", "&amp;")
                assert plain in html or value in html
                assert value in markdown or value.replace("(", "\\(").replace(")", "\\)") in markdown


@pytest.fixture
def decisions_store(tmp_path):
    with closing(Store(tmp_path / "decisions.db")) as store:
        first = fleet(1000, dated(1980, 1, 1), profit=100)
        first.raw["meta"]["yearDuration"] = 91312      # nominal windows deliberately unrelated to dated time
        store.add_snapshot(first)
        for tick, when, profit in [(2000, dated(1981, 1, 1), 250), (5000, dated(1984, 1, 1), 400)]:
            later = fleet(tick, when, profit=profit)
            later.raw["meta"]["yearDuration"] = 91312
            store.add_snapshot(later)
        yield store, first


def notes(document):
    return {block.label: block.text for block in document.blocks if isinstance(block, Note)}


def test_decision_followup_separates_calendar_elapsed_from_nominal_window(decisions_store):
    store, first = decisions_store
    store.add_decision("Review", "check the line", ["line:100"], snapshot=first)
    document = compose_report(store, "decisions")
    found = notes(document)
    elapsed = (date(1984, 1, 1).toordinal() - date(1980, 1, 1).toordinal()) / 365.25
    assert f"elapsedGameYears={elapsed}" in found["Calendar elapsed"]
    assert "GAME-YEAR" in found["Calendar elapsed"]
    nominal = (5000 - 1000) / 91312
    assert f"elapsedNominalWindows={nominal}" in found["Nominal query-window diagnostic"]
    assert "not proof of a complete profitYear window" in found["Nominal query-window diagnostic"]
    assert "elapsedNominalWindows" not in found["Calendar elapsed"] and "elapsedGameYears" not in found["Nominal query-window diagnostic"]


def test_decision_followup_discloses_baseline_and_preserves_raw_rolling_profits(decisions_store):
    store, first = decisions_store
    store.add_decision("Review", "check the line", ["line:100"], snapshot=first)
    document = compose_report(store, "decisions")
    comparison = next(t for t in tables(document) if t.columns[0] == "Entity")
    assert "1980-01-01" in comparison.columns[2] and "1984-01-01" in comparison.columns[3]
    profit = next(row for row in comparison.rows if row[1] == "Rolling Annual Profit")
    assert profit[2] == 100 and profit[3] == 400          # raw values, not re-based or accumulated
    assert profit[4] != 100 + 250 + 400 and 250 not in profit[2:4]   # never summed across overlapping snapshots
    assert not any(isinstance(v, (int, float)) and v == 750 for row in comparison.rows for v in row)


def test_decision_followup_partial_coverage_has_unavailable_baseline_and_unknown_elapsed(decisions_store):
    store, _ = decisions_store
    before_history = fleet(500, dated(1979, 1, 1))
    store.add_decision("Early", "recorded before stored history", ["line:100"], snapshot=before_history)
    store.add_decision("Gone", "unresolvable entity", ["line:999"], snapshot=store.snapshot_at_or_before(1000))
    document = compose_report(store, "decisions")
    all_notes = [b for b in document.blocks if isinstance(b, Note) and b.label == "Calendar elapsed"]
    early = next(n for n in all_notes if "elapsedGameYears=None" in n.text)
    assert "outside-observed-calendar" in early.text
    tables_found = [t for t in tables(document) if t.columns[0] == "Entity"]
    assert any("unavailable" in t.columns[2] for t in tables_found)
    assert any(row[1] == "Unresolved or no longer tracked" for t in tables_found for row in t.rows)
    # Every stored raw profit is still reported as observed, never combined.
    values = {row[2] for t in tables_found for row in t.rows if row[1] == "Rolling Annual Profit"}
    assert values <= {100, None}


def test_company_report_baseline_uses_calendar_dates_and_leaves_finance_untouched(decisions_store):
    store, _ = decisions_store
    document = compose_report(store, "company")
    text = notes(document)["Calendar baseline"]
    # Latest baseline at/before 365.25 calendar days earlier: 1981-01-01, not the nominal-tick year ago.
    elapsed = (date(1984, 1, 1).toordinal() - date(1981, 1, 1).toordinal()) / 365.25
    assert "1981-01-01" in text and f"actual elapsed GAME-YEAR: {elapsed}" in text
    assert "does not prove a complete profitYear query window" in text
    assert "window complete" not in render_markdown(document)


@pytest.mark.parametrize("calendar", [dated(1980, 1, 1), None])
def test_every_view_at_an_earlier_endpoint_never_references_later_samples(tmp_path, calendar):
    with closing(Store(tmp_path / "earlier.db")) as store:
        for tick in (0, 1000, 2000, 3000):
            store.add_snapshot(fleet(tick, calendar if calendar is None else dated(1980 + tick // 1000, 1, 1)))
        earlier = store.hydrate(1000)
        ctx = EvaluationContext(earlier, resolve_context(), store.time_context(earlier), None, store.previous_of(earlier))
        views = evaluate_views(store, ctx, VIEW_NAMES)
        for name in VIEW_NAMES:
            coverage = getattr(views, name.replace("-", "_")).coverage
            assert coverage.endpoint.tick == 1000, name
            assert all(ref.tick <= 1000 for ref in coverage.sampled), name
