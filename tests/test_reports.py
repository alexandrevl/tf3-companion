import pytest
from contextlib import closing
from html.parser import HTMLParser
from tf3companion import reports
from tf3companion.snapshot import Snapshot
from tf3companion.store import Store
from conftest import YEAR, base_snapshot


@pytest.fixture
def test_store(tmp_path):
    store = Store(tmp_path / "test.db")
    for month in range(1, 13):
        data = base_snapshot(game_time=(1984 * YEAR) + (month * (YEAR // 12)))
        data["meta"]["date"] = {"year": 1984, "month": month, "day": 1}
        data["company"]["balance"] = 1_000_000 + month * 50_000
        data["company"]["loan"] = 500_000
        data["lines"][0]["profitYear"] = 100_000 + month * 5_000
        data["lines"][0]["name"] = 'Main <script>alert(1)</script> | "quoted"'
        store.add_snapshot(Snapshot(data, source=f"snap_{month}.lua"))
    yield store
    store.close()


def test_invalid_kind_raises_error(test_store):
    with pytest.raises(ValueError, match="Unknown report kind 'weekly'"):
        reports.render_report(test_store, "weekly")


def test_html_escapes_entity_markup_and_has_no_external_dependencies(test_store):
    class Surface(HTMLParser):
        def __init__(self):
            super().__init__()
            self.tags = []
            self.urls = []

        def handle_starttag(self, tag, attrs):
            self.tags.append(tag)
            self.urls.extend(value for name, value in attrs if name in ("src", "href"))

    output = reports.render_report(test_store, "lines", html=True)
    surface = Surface()
    surface.feed(output)
    assert "script" not in surface.tags
    assert not surface.urls
    assert "Main &lt;script&gt;alert(1)&lt;/script&gt;" in output

def test_markdown_entity_names_cannot_inject_images_or_raw_html(test_store):
    document = reports.ReportDocument("lines", "Lines", [], [
        reports.Table(["Name"], [['![remote](https://example.invalid/image) <script>bad</script>']])
    ])
    output = reports.render_markdown(document)
    assert "![remote](" not in output
    assert "<script>" not in output
    assert r"\!\[remote\]\(" in output


def test_annual_profit_is_closing_rolling_window_not_sum(test_store):
    document = reports.compose_report(test_store, "annual", 1984)
    money_tables = [block for block in document.blocks if isinstance(block, reports.Table)]
    profit_row = next(row for table in money_tables for row in table.rows
                      if row[0] == "Closing Rolling Annual Line Profit")
    assert profit_row[2] == 160_000
    assert profit_row[2] != sum(100_000 + month * 5_000 for month in range(1, 13))


def test_annual_coverage_rejects_stale_baseline(tmp_path):
    with closing(Store(tmp_path / "stale.db")) as store:
        data = base_snapshot(game_time=10 * YEAR)
        data["meta"]["date"] = {"year": 1982, "month": 12, "day": 31}
        store.add_snapshot(Snapshot(data))
        for month in range(1, 13):
            data = base_snapshot(game_time=(month + 10) * YEAR)
            data["meta"]["date"] = {"year": 1984, "month": month, "day": 1}
            store.add_snapshot(Snapshot(data))
        document = reports.compose_report(store, "annual", 1984)
        assert dict(document.header)["Coverage Assessment"] == "partial-year coverage"


@pytest.mark.parametrize("kind,year", [("company", 1984), ("annual", -1), ("annual", True)])
def test_invalid_report_year_is_rejected(test_store, kind, year):
    with pytest.raises(ValueError):
        reports.render_report(test_store, kind, year=year)


def test_annual_report_coverage_and_year_gap(tmp_path):
    store = Store(tmp_path / "gap.db")
    for month in (1, 2, 4, 10):
        data = base_snapshot(game_time=(1984 * YEAR) + (month * (YEAR // 12)))
        data["meta"]["date"] = {"year": 1984, "month": month, "day": 1}
        store.add_snapshot(Snapshot(data))

    md = reports.render_report(store, "annual", year=1984, html=False)
    assert "partial-year coverage" in md
    assert "Missing Calendar Months" in md
    assert "no previous-year data" in md

    with pytest.raises(ValueError, match="No snapshots found for year 1950"):
        reports.render_report(store, "annual", year=1950)


def test_ranking_tables_do_not_repeat_lines_when_count_is_between_15_and_30(tmp_path):
    store = Store(tmp_path / "rankings.db")
    data = base_snapshot()
    data["lines"] = [{"id": i, "name": f"Line {i}", "profitYear": i, "vehicles": [], "stops": []}
                     for i in range(20)]
    store.add_snapshot(Snapshot(data))
    document = reports.compose_report(store, "lines")
    tables = [block for block in document.blocks if isinstance(block, reports.Table)]
    names = [row[0] for table in tables[:2] for row in table.rows]
    assert names == [f"Line {i}" for i in range(19, 4, -1)] + [f"Line {i}" for i in range(4, -1, -1)]
    assert len(set(names)) == 20
    store.close()


def test_decision_tracks_renamed_line_by_baseline_identity(tmp_path):
    store = Store(tmp_path / "decisions.db")
    before = base_snapshot(game_time=10 * YEAR)
    store.add_snapshot(Snapshot(before))
    decision = store.add_decision("Expand", "Observed queues", ["Train A"], Snapshot(before))
    after = base_snapshot(game_time=10 * YEAR + YEAR // 2)
    after["meta"]["date"] = {"year": 1980, "month": 7, "day": 1}
    after["lines"][0].update(name="Renamed Express", profitYear=900_000, vehicles=[1000, 1001])
    after["lines"][0]["capacity"][0]["used"] = 80
    store.add_snapshot(Snapshot(after))
    document = reports.compose_report(store, "decisions")
    table = next(block for block in document.blocks
                 if isinstance(block, reports.Table) and block.columns[0] == "Entity")
    assert table.rows == [
        ["Renamed Express", "Rolling Annual Profit", 800_000, 900_000, "+100,000"],
        ["Renamed Express", "Vehicles", 1, 2, "+1"],
        ["Renamed Express", "Instant Load Ratio", 0.6, 0.8, "+0.20"],
    ]
    store.close()


def test_company_report_excludes_retained_future_after_rewind(tmp_path):
    store = Store(tmp_path / "rewind.db")
    future = base_snapshot(game_time=12 * YEAR)
    future["meta"]["date"] = {"year": 1982, "month": 1, "day": 1}
    future["company"]["balance"] = 99_000_000
    store.add_snapshot(Snapshot(future))
    current = base_snapshot(game_time=10 * YEAR)
    store.add_snapshot(Snapshot(current))
    document = reports.compose_report(store, "company")
    financial_table = next(block for block in document.blocks if isinstance(block, reports.Table))
    assert financial_table.rows[0][1] == 5_000_000
    assert dict(document.header)["Latest Sample Date"] == "1980-01-01"
    store.close()


def _tables(document):
    return [block for block in document.blocks if isinstance(block, reports.Table)]


def test_company_net_position_and_chart_do_not_turn_unknown_into_zero(tmp_path):
    with closing(Store(tmp_path / "unknown.db")) as store:
        for month, balance in ((1, 1_000), (2, None), (3, 3_000)):
            data = base_snapshot(game_time=month * 100)
            data["meta"]["date"] = {"year": 1980, "month": month, "day": 1}
            data["company"].update(balance=balance, loan=400)
            store.add_snapshot(Snapshot(data))
        document = reports.compose_report(store, "company")
        table = _tables(document)[0]
        assert next(r for r in table.rows if r[0].startswith("Net Position"))[1] == 2_600
        data = base_snapshot(game_time=400)
        data["company"].update(balance=None, loan=400)
        store.add_snapshot(Snapshot(data))
        document = reports.compose_report(store, "company")
        assert next(r for r in _tables(document)[0].rows if r[0].startswith("Net Position"))[1] is None
        chart = next(b for b in document.blocks if isinstance(b, reports.Chart) and b.kind == "line")
        assert chart.categories == ["1980-01-01", "1980-03-01"]
        assert chart.series == [("Balance", [1_000.0, 3_000.0]), ("Loan", [400.0, 400.0])]
        history = next(t for t in _tables(document) if t.columns == ["Date", "Balance", "Loan"])
        assert [row[1] for row in history.rows] == [1_000, None, 3_000, None]


def test_annual_closing_profit_is_a_known_subtotal_and_tied_lines_are_ordered_by_id(tmp_path):
    with closing(Store(tmp_path / "annual.db")) as store:
        data = base_snapshot(game_time=1984 * YEAR)
        data["meta"]["date"] = {"year": 1984, "month": 1, "day": 1}
        data["lines"] = [{"id": i, "name": f"L{i}", "profitYear": p, "vehicles": [], "stops": []}
                         for i, p in ((3, 50), (1, 50), (2, None), (4, 70))]
        store.add_snapshot(Snapshot(data))
        document = reports.compose_report(store, "annual", 1984)
        summary = _tables(document)[0]
        assert next(r for r in summary.rows if r[0] == "Closing Rolling Annual Line Profit")[2] == 170
        assert "1 line(s) without a recorded profit" in "".join(b.text for b in document.blocks if isinstance(b, reports.Paragraph))
        top = next(t for t in _tables(document) if t.columns == ["Line", "Rolling Annual Profit"])
        assert [r[0] for r in top.rows] == ["L4", "L1", "L3", "L2"]


def test_annual_report_excludes_samples_after_the_selected_endpoint(tmp_path):
    with closing(Store(tmp_path / "future.db")) as store:
        for tick, month, balance in ((1984 * YEAR + 10, 1, 100), (1984 * YEAR + 30, 3, 999_999), (1984 * YEAR + 20, 2, 200)):
            data = base_snapshot(game_time=tick)
            data["meta"]["date"] = {"year": 1984, "month": month, "day": 1}
            data["company"]["balance"] = balance
            store.add_snapshot(Snapshot(data))
        document = reports.compose_report(store, "annual", 1984)
        assert dict(document.header)["Closing Sample"] == "1984-02-01"
        assert "retained future history" in dict(document.header)["Coverage Assessment"]
        timeline = next(t for t in _tables(document) if t.columns == ["Date", "Balance", "Loan"])
        assert [r[1] for r in timeline.rows] == [100, 200]


def test_decision_comparison_ignores_decisions_recorded_after_the_endpoint(tmp_path):
    with closing(Store(tmp_path / "decisions.db")) as store:
        late = base_snapshot(game_time=12 * YEAR)
        store.add_snapshot(Snapshot(late))
        store.add_decision("Future", "Recorded on the rewound branch", ["Train A"], Snapshot(late))
        current = base_snapshot(game_time=10 * YEAR)
        store.add_snapshot(Snapshot(current))
        store.add_decision("Now", "Before the endpoint", ["Train A"], Snapshot(current))
        document = reports.compose_report(store, "decisions")
        journal = _tables(document)[0]
        assert [row[2] for row in journal.rows] == ["Now"]


def test_cargo_full_stock_screen_uses_the_effective_threshold_and_label(tmp_path):
    from tf3companion.analysis import Thresholds
    with closing(Store(tmp_path / "cargo.db")) as store:
        data = base_snapshot()
        data["industries"] = [{"id": 7, "name": "Mine", "outputs": [{"cargo": 3, "producedYear": 10, "shippedYear": 0}]}]
        data["stocks"] = [{"kind": "industry", "owner": 7, "ownerName": "Mine", "cargos": [3], "count": 75, "capacity": 100}]
        store.add_snapshot(Snapshot(data))
        default = reports.compose_report(store, "cargo")
        lowered = reports.compose_report(store, "cargo", thresholds=Thresholds(full_stock_ratio=0.75))
        assert not any(isinstance(b, reports.Table) and b.columns[0] == "Facility" for b in default.blocks)
        assert "90%" in "".join(b.text for b in default.blocks if isinstance(b, reports.Paragraph))
        heading = next(b.text for b in lowered.blocks if isinstance(b, reports.Heading))
        assert "75%" in heading and "90%" not in heading
        assert _tables(lowered)[0].rows[0][0] == "Mine"
