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
    document = reports._build_annual_report(test_store, 1984)
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
        document = reports._build_annual_report(store, 1984)
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
    document = reports._build_lines_report(store)
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
    blocks = reports._decision_details(store, decision, Snapshot(after))
    table = next(block for block in blocks if isinstance(block, reports.Table))
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
    document = reports._build_company_report(store)
    financial_table = next(block for block in document.blocks if isinstance(block, reports.Table))
    assert financial_table.rows[0][1] == 5_000_000
    assert dict(document.header)["Latest Sample Date"] == "1980-01-01"
    store.close()
