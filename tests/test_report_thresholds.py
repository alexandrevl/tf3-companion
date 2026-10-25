"""Methodology thresholds reach the report-local copies of the engine's constants."""

from contextlib import closing

from conftest import YEAR
from test_report_industries import add, industry
from test_report_lines_history import _cls, _snap
from tf3companion import reports
from tf3companion.analysis import Thresholds
from tf3companion.snapshot import Snapshot
from tf3companion.store import Store
from view_helpers import document


def _two_year_old_line_store(path):
    """Eight monthly snapshots of one line whose vehicles were bought 2 years before the last one."""
    store = Store(path)
    anchor = _snap(-24, [])
    store.add_snapshot(anchor)
    bought = 10 * YEAR + round(7 * YEAR / 12) - 2 * YEAR
    for i in range(8):
        snap = _snap(i, [(100, "Mid-aged", 1_000_000 - 100_000 * i, 2)])
        for vehicle in snap.raw["vehicles"]:
            vehicle["purchaseTime"] = bought
        store.add_snapshot(Snapshot(snap.raw, source=f"s{i}.lua"))
    return store


def test_mature_years_override_changes_lines_history(tmp_path):
    with closing(_two_year_old_line_store(tmp_path / "lh.db")) as store:
        default_doc = document(store, "lines-history")
        strict_doc = document(store, "lines-history", Thresholds(mature_years=3.0))
        assert _cls(default_doc)["Mid-aged"] != "too new"
        assert _cls(strict_doc)["Mid-aged"] == "too new"


def test_full_stock_ratio_override_changes_industries(tmp_path):
    def full_row(doc):
        summary = next(
            b
            for b in doc.blocks
            if isinstance(b, reports.Table) and any(str(r[0]).startswith("Full output stocks") for r in b.rows)
        )
        return next(r for r in summary.rows if str(r[0]).startswith("Full output stocks"))

    with closing(Store(tmp_path / "ind.db")) as store:
        for tick, month in [(1000, 1), (2000, 2)]:
            add(
                store,
                tick,
                (1980, month, 1),
                [industry()],
                [{"kind": "industry", "owner": 10, "stockId": 1, "cargos": [3], "count": 80, "capacity": 100}],
            )
        default_row = full_row(document(store, "industries"))
        lowered_row = full_row(document(store, "industries", Thresholds(full_stock_ratio=0.75)))
    assert default_row[0] == "Full output stocks ≥90% (all)" and default_row[1:3] == [0, 0]
    assert lowered_row[0] == "Full output stocks ≥75% (all)" and lowered_row[1:3] == [1, 1]
