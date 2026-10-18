import datetime as dt
from contextlib import closing

import pytest

from conftest import YEAR, base_snapshot
from tf3companion import report_history
from tf3companion.reports import Chart, Heading, Note, Paragraph, Table, render_html, render_markdown
from tf3companion.snapshot import Snapshot
from tf3companion.store import Store

TICKS_PER_DAY = 10  # deliberately unrelated to YEAR (=1000) to prove calendar dates drive elapsed time


def _gt(year, month, day):
    return dt.date(year, month, day).toordinal() * TICKS_PER_DAY


def _snap(year, month, day, *, n_vehicles, n_lines=2, balance=1_000_000, loan=0, pax=0, cargo=0,
          profit=100_000, earnings=None, reason="interval", extra_ticks=0, errors=None, line_name=None):
    data = base_snapshot(game_time=_gt(year, month, day) + extra_ticks)
    data["meta"]["date"] = {"year": year, "month": month, "day": day}
    data["meta"]["reason"] = reason
    data["company"].update({"balance": balance, "loan": loan, "passengersTransported": pax,
                            "cargoTransported": cargo, "earnings": balance if earnings is None else earnings,
                            "value": {"totalScore": 30, "trackTotalLength": 1000 + n_vehicles}})
    data["lines"] = [{"id": 100 + i, "name": line_name or f"Line {i}", "vehicles": [], "stops": [],
                      "profitYear": profit if i % 2 == 0 else -profit // 10} for i in range(n_lines)]
    data["vehicles"] = [{"id": 1000 + i, "name": f"Bus {i}", "carrier": "ROAD" if i % 3 else "RAIL",
                         "state": "EN_ROUTE", "line": 100, "profitYear": 10, "value": 1000 + i,
                         "purchaseTime": _gt(1980 + i * 5 // max(n_vehicles, 1), 6, 1)}
                        for i in range(n_vehicles)]
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
                store.add_snapshot(_snap(
                    year, month, 1, n_vehicles=10 + index, n_lines=2 + index // 6,
                    balance=1_000_000 + index * 100_000 - (3_000_000 if (year, month) == (1983, 3) else 0),
                    loan=500_000 if year == 1981 else 0, pax=index * 1000, cargo=index * 2000,
                    profit=100_000 + index * 1000,
                    errors=["depot[12].constructionComponent: boom"] if index == 7 else None))
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
    doc = report_history.build(five_years)
    header = dict(doc.header)
    assert header["Aggregation"].startswith("quarter (20 period(s))")
    assert "1980-01-01 to 1984-12-01" in header["History Span"]
    assert doc.kind == "history"
    headings = _headings(doc)
    for expected in ("Finance by Quarter", "Network and Fleet Size by Quarter", "Year-over-Year Comparison (quarter level)",
                     "Last Sample of Each Calendar Year", "Milestones and Turning Points",
                     "Surviving Fleet by Purchase Year", "What This History Can and Cannot Tell You"):
        assert expected in headings
    finance = next(t for t in _tables(doc) if t.columns[0] == "Period" and "Balance Change" in t.columns)
    assert len(finance.rows) == 20
    assert finance.rows[0][0] == "1980-Q1" and finance.rows[-1][0] == "1984-Q4"


def test_coverage_discloses_gap_samples_and_errors(five_years):
    doc = report_history.build(five_years)
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
    doc = report_history.build(five_years)
    yoy = next(t for t in _tables(doc) if t.columns[:2] == ["Period", "Year-Ago Period"])
    assert 0 < len(yoy.rows) <= 12
    assert yoy.rows[-1][0] == "1984-Q4" and yoy.rows[-1][1] == "1983-Q4"
    year_end = next(t for t in _tables(doc) if t.columns[0] == "Year")
    assert [r[0] for r in year_end.rows] == ["1980", "1981", "1982", "1983", "1984"]


def test_growth_is_annualised_only_when_span_allows(five_years):
    doc = report_history.build(five_years)
    growth = next(t for t in _tables(doc) if t.columns[0] == "Metric" and "Annualised Growth" in t.columns)
    vehicles = next(r for r in growth.rows if r[0] == "Vehicles")
    assert vehicles[-1].endswith("%") and vehicles[-1] != "-"
    loan = next(r for r in growth.rows if r[0] == "Loan")
    assert loan[-1] == "-"  # zero base can't be annualised


def test_loan_change_and_cash_drop_are_milestones(five_years):
    doc = report_history.build(five_years)
    loan = next(t for t in _tables(doc) if t.columns[0] == "Samples" and "Loan Before" in t.columns)
    assert [r[3] for r in loan.rows] == [500_000, -500_000]
    cash = next(t for t in _tables(doc) if t.columns[0] == "Type")
    drop = cash.rows[0]
    assert drop[0] == "Drop" and drop[1].endswith("1983-03-01") and drop[3] == -2_900_000


def test_rolling_profit_is_never_summed(five_years):
    doc = report_history.build(five_years)
    finance = next(t for t in _tables(doc) if "Rolling Line Profit (level)" in t.columns)
    col = finance.columns.index("Rolling Line Profit (level)")
    levels = [r[col] for r in finance.rows]
    last_snap = five_years.latest()
    assert levels[-1] == sum(line["profitYear"] for line in last_snap.lines)
    assert sum(levels) not in _numbers(doc)
    assert "Rolling Line Profit is the sum of each line's rolling 12-month profit" in render_markdown(doc)


def test_every_chart_value_appears_in_a_table(five_years):
    doc = report_history.build(five_years)
    charts = [b for b in doc.blocks if isinstance(b, Chart)]
    assert len(charts) >= 5
    numbers = _numbers(doc)
    for chart in charts:
        for _, points in chart.series:
            assert all(p in numbers for p in points), chart.title


def test_turnover_counts_and_cohorts(five_years):
    doc = report_history.build(five_years)
    turnover = next(t for t in _tables(doc) if t.columns[:3] == ["Period", "Vehicles Added", "Vehicles Removed"])
    # fleet grows by one vehicle per sample: 55 intervals, 1 vehicle each
    assert sum(r[1] for r in turnover.rows) == 55
    assert sum(r[2] for r in turnover.rows) == 0
    cohort = next(t for t in _tables(doc) if t.columns[0] == "Purchase Year")
    assert sum(r[1] for r in cohort.rows) == len(five_years.latest().vehicles)
    assert cohort.rows[0][0] == "1980"


def test_calendar_calibration_note_when_year_duration_is_off(five_years):
    text = render_markdown(report_history.build(five_years))
    assert "game ticks per calendar day" in text
    assert f"{YEAR / 365.25:,.0f} implied by meta.yearDuration" in text


def test_short_history_has_monthly_level_and_explains_missing_yoy(tmp_path):
    with closing(Store(tmp_path / "short.db")) as store:
        for i, (m, d) in enumerate([(3, 20), (3, 28), (4, 5), (4, 20), (5, 3), (5, 20), (6, 5), (7, 1)]):
            store.add_snapshot(_snap(1983, m, d, n_vehicles=20 + i, balance=2_000_000 + i * 10_000,
                                     pax=i * 100, cargo=i * 50))
        doc = report_history.build(store)
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
        doc = report_history.build(store)
    assert dict(doc.header)["Snapshots Used"].startswith("2 of 3")


def test_single_snapshot_degrades_without_raising(tmp_path):
    with closing(Store(tmp_path / "one.db")) as store:
        store.add_snapshot(_snap(1983, 3, 20, n_vehicles=5))
        doc = report_history.build(store)
        text = render_markdown(doc)
        assert "Insufficient data" in text
        assert render_html(doc).startswith("<!DOCTYPE html>")


def test_empty_store_raises(tmp_path):
    with closing(Store(tmp_path / "empty.db")) as store:
        with pytest.raises(ValueError, match="no snapshot found"):
            report_history.build(store)


def test_hostile_names_are_escaped(tmp_path):
    with closing(Store(tmp_path / "evil.db")) as store:
        store.add_snapshot(_snap(1983, 3, 20, n_vehicles=3, n_lines=2))
        data = _snap(1983, 4, 20, n_vehicles=4, n_lines=3, line_name="New <script>alert(1)</script> | `x`")
        store.add_snapshot(data)
        doc = report_history.build(store)
    output = render_html(doc)
    assert "<script>" not in output
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in output
    md = render_markdown(doc)
    assert "<script>" not in md


def test_limits_section_names_sampling_and_rolling_profit(five_years):
    doc = report_history.build(five_years)
    index = _headings(doc).index("What This History Can and Cannot Tell You")
    start = next(i for i, b in enumerate(doc.blocks) if isinstance(b, Heading) and b.text.endswith("Cannot Tell You"))
    section = " ".join(b.text for b in doc.blocks[start + 1:] if isinstance(b, Paragraph))
    assert index >= 0
    assert "not continuous telemetry" in section and "double-counts" in section


def test_no_unsupported_cash_residual_or_transport_rates(five_years):
    doc = report_history.build(five_years)
    text = render_markdown(doc)
    assert "expected cash gain" not in text
    assert "outside line profit" not in text
    assert "years of the latest rolling line profit" not in text
    assert "per 30 Days" not in text
    assert "per 30 days" not in text
    traffic = next(t for t in _tables(doc) if "Passengers Counter (raw)" in t.columns)
    assert traffic.columns == ["Period", "Passengers Counter (raw)", "Passengers Counter Change",
                               "Cargo Counter (raw)", "Cargo Counter Change"]
    assert "accounting windows are unverified" in text
