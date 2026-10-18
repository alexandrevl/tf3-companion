from html.parser import HTMLParser

import pytest
from conftest import YEAR, base_snapshot

from tf3companion import reports
from tf3companion import report_lines_history as lh
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
         "purchaseTime": now - (YEAR // 10 if lid == 104 else 5 * YEAR), "profitYear": 0, "models": [7], "value": 1000}
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


def test_no_snapshot_raises(tmp_path):
    store = Store(tmp_path / "empty.db")
    with pytest.raises(ValueError):
        lh.build(store)


def test_multi_year_classification_and_sections(multi_year):
    doc = lh.build(multi_year)
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
    assert "3.00" in headers["Sample Period"]

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



def test_retained_future_line_history_is_excluded(multi_year):
    multi_year.add_snapshot(_snap(37, [(999, "Future-only line", 9_000_000, 2)]))
    current = _snap(36, [(100, "Current line", 1_000_000, 2)])
    multi_year.add_snapshot(current)

    doc = lh.build(multi_year)
    markdown = reports.render_markdown(doc)

    assert "Future-only line" not in markdown
    assert dict(doc.header)["Latest Sample Date"] == current.date_label

def test_charts_have_matching_tables_and_html_is_offline(multi_year):
    doc = lh.build(multi_year)
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
    assert reports.render_markdown(lh.build(multi_year)) == reports.render_markdown(lh.build(multi_year))


def test_short_history_degrades(tmp_path):
    store = Store(tmp_path / "one.db")
    store.add_snapshot(_snap(0, [(100, "Solo", 1000, 2)]))
    doc = lh.build(store)
    assert _cls(doc)["Solo"] == "insufficient data"
    md = reports.render_markdown(doc)
    assert "Insufficient data" in md
    assert "Compact Trajectory Table" in md
    store.close()


def test_short_history_five_months_uses_whole_history(tmp_path):
    store = Store(tmp_path / "short.db")
    for i in range(8):
        store.add_snapshot(_snap(i, [(100, "Down", 1_000_000 - 100_000 * i, 2), (101, "Same", 300_000, 1)]))
    doc = lh.build(store)
    assert dict(doc.header)["Evaluation Window"] == "entire stored history"
    assert _cls(doc) == {"Down": "deteriorating", "Same": "stable"}
    store.close()
