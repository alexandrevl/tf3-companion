import datetime as dt
import json
from contextlib import closing

import pytest

from conftest import base_snapshot
from tf3companion import report_history
from tf3companion.analysis_views import EvaluationContext, evaluate_views
from tf3companion.analysis_views.models import plain
from tf3companion.report_policy import resolve_context
from tf3companion.reports import Chart, Heading, Note, Table, render_html, render_markdown
from tf3companion.snapshot import Snapshot
from tf3companion.store import Store
from view_helpers import document, view

TICKS_PER_DAY = 10  # deliberately unrelated to YEAR (=1000) to prove calendar dates drive elapsed time


def _gt(year, month, day):
    return dt.date(year, month, day).toordinal() * TICKS_PER_DAY


def _snap(
    year,
    month,
    day,
    *,
    n_vehicles,
    n_lines=2,
    balance=1_000_000,
    loan=0,
    pax=0,
    cargo=0,
    profit=100_000,
    earnings=None,
    reason="interval",
    extra_ticks=0,
    errors=None,
    line_name=None,
):
    data = base_snapshot(game_time=_gt(year, month, day) + extra_ticks)
    data["meta"]["date"] = {"year": year, "month": month, "day": day}
    data["meta"]["reason"] = reason
    data["company"].update(
        {
            "balance": balance,
            "loan": loan,
            "passengersTransported": pax,
            "cargoTransported": cargo,
            "earnings": balance if earnings is None else earnings,
            "value": {"totalScore": 30, "trackTotalLength": 1000 + n_vehicles},
        }
    )
    data["lines"] = [
        {
            "id": 100 + i,
            "name": line_name or f"Line {i}",
            "vehicles": [],
            "stops": [],
            "profitYear": profit if i % 2 == 0 else -profit // 10,
        }
        for i in range(n_lines)
    ]
    data["vehicles"] = [
        {
            "id": 1000 + i,
            "name": f"Bus {i}",
            "carrier": "ROAD" if i % 3 else "RAIL",
            "state": "EN_ROUTE",
            "line": 100,
            "profitYear": 10,
            "value": 1000 + i,
            "purchaseTime": _gt(1980 + i * 5 // max(n_vehicles, 1), 6, 1),
        }
        for i in range(n_vehicles)
    ]
    data["errors"] = errors or []
    return Snapshot(data, source=f"s_{year}_{month}_{day}.lua")


@pytest.fixture
def five_years(tmp_path):
    with closing(Store(tmp_path / "five.db")) as store:
        index = 0
        for year in range(1980, 1985):
            for month in range(1, 13):
                if (year, month) in {(1982, 5), (1982, 6), (1982, 7), (1982, 8)}:
                    continue  # a four-month collection gap
                index += 1
                store.add_snapshot(
                    _snap(
                        year,
                        month,
                        1,
                        n_vehicles=10 + index,
                        n_lines=2 + index // 6,
                        balance=1_000_000 + index * 100_000 - (3_000_000 if (year, month) == (1983, 3) else 0),
                        loan=500_000 if year == 1981 else 0,
                        pax=index * 1000,
                        cargo=index * 2000,
                        profit=100_000 + index * 1000,
                        errors=["depot[12].constructionComponent: boom"] if index == 7 else None,
                    )
                )
        yield store


def _tables(doc):
    return [b for b in doc.blocks if isinstance(b, Table)]


def _headings(doc):
    return [b.text for b in doc.blocks if isinstance(b, Heading)]


def _numbers(doc):
    out = set()
    for table in _tables(doc):
        for row in table.rows:
            for cell in row:
                if isinstance(cell, (int, float)) and not isinstance(cell, bool):
                    out.add(float(cell))
    return out


def test_five_year_history_uses_quarters_and_degrades_nothing(five_years):
    doc = document(five_years, "history")
    header = dict(doc.header)
    assert header["Aggregation"].startswith("quarter (20 period(s))")
    assert "1980-01-01 to 1984-12-01" in header["History Span"]
    assert doc.kind == "history"
    headings = _headings(doc)
    for expected in (
        "Finance by Quarter",
        "Network and Fleet Size by Quarter",
        "Year-over-Year Comparison (quarter level)",
        "Last Sample of Each Calendar Year",
        "Milestones and Turning Points",
        "Surviving Fleet by Purchase Year",
        "What This History Can and Cannot Tell You",
    ):
        assert expected in headings
    finance = next(t for t in _tables(doc) if t.columns[0] == "Period" and "Balance Change" in t.columns)
    assert len(finance.rows) == 20
    assert finance.rows[0][0] == "1980-Q1" and finance.rows[-1][0] == "1984-Q4"


def test_coverage_discloses_gap_samples_and_errors(five_years):
    doc = document(five_years, "history")
    text = render_markdown(doc)
    assert "Gaps Longer Than Usual" in text
    gap = next(t for t in _tables(doc) if t.columns == ["From", "To", "Days"])
    assert gap.rows[0][0] == "1982-04-01" and gap.rows[0][1] == "1982-09-01"
    coverage = dict((r[0], r[1]) for t in _tables(doc) if t.columns[0] == "Coverage fact" for r in t.rows)
    assert coverage["Stored samples"] == 56
    assert coverage["Periods with no sample"] == "-"  # gap spans months, quarters are still hit
    assert "depot[].constructionComponent (1 samples)" in text.replace("\\", "")
    assert dict(doc.header)["Collection Errors"] == "1 of 56 samples reported errors"


def test_year_over_year_and_year_end_tables(five_years):
    doc = document(five_years, "history")
    yoy = next(t for t in _tables(doc) if t.columns[:2] == ["Period", "Year-Ago Period"])
    assert 0 < len(yoy.rows) <= 12
    assert yoy.rows[-1][0] == "1984-Q4" and yoy.rows[-1][1] == "1983-Q4"
    year_end = next(t for t in _tables(doc) if t.columns[0] == "Year")
    assert [r[0] for r in year_end.rows] == ["1980", "1981", "1982", "1983", "1984"]


def test_growth_is_annualised_only_when_span_allows(five_years):
    doc = document(five_years, "history")
    growth = next(t for t in _tables(doc) if t.columns[0] == "Metric" and "Annualised Growth" in t.columns)
    vehicles = next(r for r in growth.rows if r[0] == "Vehicles")
    assert vehicles[-1].endswith("%") and vehicles[-1] != "-"
    loan = next(r for r in growth.rows if r[0] == "Loan")
    assert loan[-1] == "-"  # zero base can't be annualised


def test_loan_change_and_cash_drop_are_milestones(five_years):
    doc = document(five_years, "history")
    loan = next(t for t in _tables(doc) if t.columns[0] == "Samples" and "Loan Before" in t.columns)
    assert [r[3] for r in loan.rows] == [500_000, -500_000]
    cash = next(t for t in _tables(doc) if t.columns[0] == "Type")
    drop = cash.rows[0]
    assert drop[0] == "Drop" and drop[1].endswith("1983-03-01") and drop[3] == -2_900_000


def test_rolling_profit_is_never_summed(five_years):
    doc = document(five_years, "history")
    finance = next(t for t in _tables(doc) if "Rolling Line Profit (level)" in t.columns)
    col = finance.columns.index("Rolling Line Profit (level)")
    levels = [r[col] for r in finance.rows]
    last_snap = five_years.latest()
    assert levels[-1] == sum(line["profitYear"] for line in last_snap.lines)
    assert sum(levels) not in _numbers(doc)
    assert "Rolling Line Profit is the sum of each line's rolling 12-month profit" in render_markdown(doc)


def test_every_chart_value_appears_in_a_table(five_years):
    doc = document(five_years, "history")
    charts = [b for b in doc.blocks if isinstance(b, Chart)]
    assert len(charts) >= 5
    numbers = _numbers(doc)
    for chart in charts:
        for _, points in chart.series:
            assert all(p in numbers for p in points), chart.title


def test_turnover_counts_and_cohorts(five_years):
    doc = document(five_years, "history")
    turnover = next(t for t in _tables(doc) if t.columns[:3] == ["Period", "Vehicles Added", "Vehicles Removed"])
    # fleet grows by one vehicle per sample: 55 intervals, 1 vehicle each
    assert sum(r[1] for r in turnover.rows) == 55
    assert sum(r[2] for r in turnover.rows) == 0
    cohort = next(t for t in _tables(doc) if t.columns[0] == "Purchase Year")
    assert sum(r[1] for r in cohort.rows) == len(five_years.latest().vehicles)
    assert cohort.rows[0][0] == "1980"


def test_short_history_has_monthly_level_and_explains_missing_yoy(tmp_path):
    with closing(Store(tmp_path / "short.db")) as store:
        for i, (m, d) in enumerate([(3, 20), (3, 28), (4, 5), (4, 20), (5, 3), (5, 20), (6, 5), (7, 1)]):
            store.add_snapshot(
                _snap(1983, m, d, n_vehicles=20 + i, balance=2_000_000 + i * 10_000, pax=i * 100, cargo=i * 50)
            )
        doc = document(store, "history")
    header = dict(doc.header)
    assert header["Aggregation"].startswith("month (5 period(s))")
    text = render_markdown(doc)
    assert "under one year" in text
    yoy = next(i for i, b in enumerate(doc.blocks) if isinstance(b, Heading) and b.text.startswith("Year-over-Year"))
    assert isinstance(doc.blocks[yoy + 1], Note) and doc.blocks[yoy + 1].label == "Insufficient data"
    assert "Last Sample of Each Calendar Year" not in text


def test_near_duplicate_requests_are_merged(tmp_path):
    with closing(Store(tmp_path / "dup.db")) as store:
        store.add_snapshot(_snap(1983, 3, 20, n_vehicles=5, reason="start"))
        store.add_snapshot(_snap(1983, 3, 20, n_vehicles=5, reason="request", extra_ticks=3))
        store.add_snapshot(_snap(1983, 4, 20, n_vehicles=6))
        doc = document(store, "history")
    assert dict(doc.header)["Snapshots Used"].startswith("2 of 3")


def test_single_snapshot_degrades_without_raising(tmp_path):
    with closing(Store(tmp_path / "one.db")) as store:
        store.add_snapshot(_snap(1983, 3, 20, n_vehicles=5))
        doc = document(store, "history")
        text = render_markdown(doc)
        assert "Insufficient data" in text
        assert render_html(doc).startswith("<!DOCTYPE html>")


def test_empty_store_raises(tmp_path):
    with closing(Store(tmp_path / "empty.db")) as store:
        with pytest.raises(ValueError, match="No snapshot found"):
            document(store, "history")


def test_hostile_names_are_escaped(tmp_path):
    with closing(Store(tmp_path / "evil.db")) as store:
        store.add_snapshot(_snap(1983, 3, 20, n_vehicles=3, n_lines=2))
        data = _snap(1983, 4, 20, n_vehicles=4, n_lines=3, line_name="New <script>alert(1)</script> | `x`")
        store.add_snapshot(data)
        doc = document(store, "history")
    output = render_html(doc)
    assert "<script>" not in output
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in output
    md = render_markdown(doc)
    assert "<script>" not in md


def test_no_unsupported_cash_residual_or_transport_rates(five_years):
    doc = document(five_years, "history")
    text = render_markdown(doc)
    assert "expected cash gain" not in text
    assert "outside line profit" not in text
    assert "years of the latest rolling line profit" not in text
    assert "per 30 Days" not in text
    assert "per 30 days" not in text
    traffic = next(t for t in _tables(doc) if "Passengers Counter (raw)" in t.columns)
    assert traffic.columns == [
        "Period",
        "Passengers Counter (raw)",
        "Passengers Counter Change",
        "Cargo Counter (raw)",
        "Cargo Counter Change",
    ]
    assert "accounting windows are unverified" in text


# ---------------------------------------------------------------------------
# Direct view assertions, view/report agreement and evidence bounds
# ---------------------------------------------------------------------------


def _at(store, tick):
    snap = store.snapshot_at_or_before(tick)
    ctx = EvaluationContext(snap, resolve_context(), store.time_context(snap), None, store.previous_of(snap))
    return snap, evaluate_views(store, ctx, ("history",)).history


def test_view_periods_and_events_match_report(five_years):
    result = view(five_years, "history")
    doc = document(five_years, "history")
    assert result.status == "ok" and result.level == "quarter" and len(result.periods) == 20
    finance = next(t for t in _tables(doc) if t.columns[0] == "Period" and "Balance Change" in t.columns)
    assert [r[0] for r in finance.rows] == [p.label for p in result.periods]
    assert [r[4] for r in finance.rows] == [p.close.balance for p in result.periods]
    assert [r[5] for r in finance.rows] == [p.balance_change for p in result.periods]
    assert result.periods[0].compared and result.periods[0].balance_change == 200_000  # first sample is the baseline
    drop = result.cash_drops[0]
    assert drop.balance_change == -2_900_000 and drop.end_label == "1983-03-01"
    cash = next(t for t in _tables(doc) if t.columns[0] == "Type")
    assert [r[3] for r in cash.rows[: len(result.cash_drops)]] == [e.balance_change for e in result.cash_drops]
    assert [e.loan_change for e in result.loan_changes] == [500_000, -500_000]
    assert sum(p.vehicles_added for p in result.periods) == 55 and sum(p.vehicles_removed for p in result.periods) == 0
    assert result.interval_count == 55 and result.usable_samples == result.stored_samples == 56


def test_view_growth_cadence_and_extremes(five_years):
    result = view(five_years, "history")
    growth = {g.code: g for g in result.growth}
    assert result.annualised and growth["vehicles"].annualised_percent is not None
    assert growth["loan"].annualised_percent is None  # zero base
    assert growth["passengers-counter"].annualised_percent is None  # raw counters never annualised
    gap = result.cadence.gaps_longer_than_usual[0]
    assert (gap.start_label, gap.end_label) == ("1982-04-01", "1982-09-01")
    assert (
        result.cadence.errors.samples == 1
        and result.cadence.errors.collectors[0].family == "depot[].constructionComponent"
    )
    extremes = {x.code: x for x in result.extremes}
    assert extremes["lowest-balance"].label == "1980-01-01" and extremes["highest-balance"].label == "1984-12-01"
    assert [y.year for y in result.year_ends] == [1980, 1981, 1982, 1983, 1984]
    pair = result.year_over_year[-1]
    assert (pair.label, pair.prior_label) == ("1984-Q4", "1983-Q4")
    assert result.rolling_profit.latest.value == sum(line["profitYear"] for line in five_years.latest().lines)


def test_view_cohorts_cover_surviving_fleet(five_years):
    result = view(five_years, "history")
    assert sum(c.vehicles for c in result.cohorts.cohorts) == len(five_years.latest().vehicles)
    assert result.cohorts.unknown_vehicles == 0 and result.cohorts.cohorts[0].year == 1980
    assert abs(sum(c.share for c in result.cohorts.cohorts) - 1) < 1e-9


def test_earnings_offset_segments(tmp_path):
    with closing(Store(tmp_path / "earn.db")) as store:
        for i in range(8):
            store.add_snapshot(
                _snap(
                    1983,
                    1 + i,
                    1,
                    n_vehicles=5,
                    balance=1_000_000 + i * 50_000,
                    earnings=1_000_000 + i * 50_000 - (0 if i < 4 else 5_000_000),
                )
            )
        result = view(store, "history")
        doc = document(store, "history")
    earnings = result.earnings
    assert earnings.status == "segments" and earnings.segment_count == 2 and earnings.offset_changes == 1
    assert [s.offset for s in earnings.segments] == [0, 5_000_000]
    assert [(s.start_label, s.end_label, s.samples) for s in earnings.segments] == [
        ("1983-01-01", "1983-04-01", 4),
        ("1983-05-01", "1983-08-01", 4),
    ]
    table = next(t for t in _tables(doc) if t.columns[0] == "Segment")
    assert [r[6] for r in table.rows] == [0, 5_000_000]
    assert "income statement" in render_markdown(doc)


def test_unknown_counters_stay_unknown_not_zero(tmp_path):
    with closing(Store(tmp_path / "unknown.db")) as store:
        for i in range(3):
            snap = _snap(1983, 3 + i, 1, n_vehicles=4 + i, pax=None, cargo=None)
            del snap.raw["company"]["loan"]
            store.add_snapshot(snap)
        result = view(store, "history")
        doc = document(store, "history")
    assert all(p.passengers is None and p.cargo is None and p.loan is None for p in result.points)
    assert all(p.net is None for p in result.points)  # balance minus an unknown loan is unknown, not the balance
    growth = {g.code: g for g in result.growth}
    assert growth["net"].first is None and growth["passengers-counter"].change is None
    assert not result.traffic.has_counters and result.constant_loan is None
    assert "No sample carries the company transport counters." in render_markdown(doc)
    finance = next(t for t in _tables(doc) if "Net (Balance - Loan)" in t.columns)
    assert all(r[finance.columns.index("Net (Balance - Loan)")] is None for r in finance.rows)


def test_collector_families_with_equal_counts_have_stable_order(tmp_path):
    with closing(Store(tmp_path / "ties.db")) as store:
        for i in range(2):
            store.add_snapshot(_snap(1983, 3 + i, 1, n_vehicles=4, errors=["zeta[1]: x", "alpha: y", "mid: z"]))
        result = view(store, "history")
    assert [c.family for c in result.cadence.errors.collectors] == ["alpha", "mid", "zeta[]"]
    assert result.coverage.collection_errors == ("alpha", "mid", "zeta[]")


def test_earlier_endpoint_excludes_later_stored_evidence(five_years):
    tick = _gt(1982, 1, 1)
    snap, early = _at(five_years, tick)
    assert snap.date_label == "1982-01-01"
    assert early.points[-1].label == "1982-01-01" and early.stored_samples == 25
    assert early.later_samples == 56 - 25
    assert early.coverage.endpoint.tick == tick and early.coverage.eligible == 25
    assert [y.year for y in early.year_ends] == [1980, 1981, 1982]
    assert not early.cash_drops  # the 1983 drop is after the endpoint
    assert all(e.label != "1983-03-01" for e in early.extremes)
    assert early.cohorts.sample.tick == tick and early.cohorts.fleet == len(snap.vehicles)
    assert max(p.tick for p in early.points) <= tick
    ctx = EvaluationContext(snap, resolve_context(), five_years.time_context(snap), None, None)
    text = render_markdown(report_history.build(early, context=ctx))
    assert "1983" not in text and "newest by game time" in text


def test_view_is_serializable_and_hydration_is_bounded(five_years):
    result = view(five_years, "history")
    json.dumps(plain(result))
    cov = result.coverage
    assert cov.eligible == 56 and cov.read == 56 and cov.used == 56
    assert cov.hydration_limit is not None and cov.hydrated <= cov.hydration_limit
    assert [s.tick for s in cov.sampled] == [result.points[0].tick, result.points[-1].tick]


def test_ambiguous_and_undated_histories_are_explicit(tmp_path):
    with closing(Store(tmp_path / "undated.db")) as store:
        for i in range(2):
            snap = _snap(1983, 3 + i, 1, n_vehicles=4)
            del snap.raw["meta"]["date"]
            store.add_snapshot(snap)
        result = view(store, "history")
        doc = document(store, "history")
    assert result.status == "no-dated-samples" and result.points == () and result.undated_samples == 2
    assert result.coverage.unavailable[0].code == "missing-calendar-date"
    assert "No stored snapshot carries a calendar date" in render_markdown(doc)


def test_history_points_store_projection_is_endpoint_bounded(five_years):
    tick = _gt(1980, 3, 1)
    rows = list(five_years.iter_history_points(tick))
    assert [r["date_label"] for r in rows] == ["1980-01-01", "1980-02-01", "1980-03-01"]
    last = rows[-1]
    assert (
        last["game_time"] == tick
        and last["balance"] == 1_300_000
        and last["stations"] == len(five_years.snapshot_at_or_before(tick).stations)
    )
    assert len(last["vehicles"]) == 13 and {"id", "name", "carrier", "value", "purchase"} == set(last["vehicles"][0])
    assert all(line["profit"] is not None for line in last["lines"])
    with pytest.raises(ValueError):
        list(five_years.iter_history_points(-1))
