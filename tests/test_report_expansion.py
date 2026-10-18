from __future__ import annotations

import copy
import re
from html.parser import HTMLParser

import pytest

from conftest import YEAR, base_snapshot
from tf3companion import report_expansion as rx
from tf3companion import reports
from tf3companion.snapshot import Snapshot
from tf3companion.store import Store

COAL, IRON, PLANKS = 3, 4, 5


def industry(id_, name, kind, x, y, inputs=(), outputs=(), **extra):
    return {"id": id_, "name": name, "type": f"::/industries/{kind}/{kind}.con", "position": [x, y, 0],
            "inputs": [dict(i) for i in inputs], "outputs": [dict(o) for o in outputs], "closureTimeStamp": 0, **extra}


def out(cargo, produced, shipped, maximum=None):
    return {"cargo": cargo, "producedYear": produced, "shippedYear": shipped, "maxProductionYear": maximum or produced}


def inp(cargo, maximum, delivered=0, consumed=0):
    return {"cargo": cargo, "maxConsumptionYear": maximum, "deliveredYear": delivered, "consumedYear": consumed}


def make(game_time=10 * YEAR, date=(1980, 1, 1), industries=None, stocks=None, towns=None, catalog=False, lines=None):
    data = base_snapshot(game_time)
    data["meta"]["date"] = {"year": date[0], "month": date[1], "day": date[2]}
    data["cargos"] = [{"id": 0, "name": "Passengers", "res": "::/cargos/passengers/passengers.cargo"},
                      {"id": COAL, "name": "Coal", "res": "::/cargos/coal/coal.cargo"},
                      {"id": IRON, "name": "Iron", "res": "::/cargos/iron_ore/iron_ore.cargo"},
                      {"id": PLANKS, "name": "Planks", "res": "::/cargos/planks/planks.cargo"}]
    data["industries"] = industries if industries is not None else default_industries()
    data["stocks"] = stocks or []
    if towns is not None:
        data["towns"] = towns
    if lines is not None:
        data["lines"], data["vehicles"], data["stations"] = lines
    if catalog:
        data["catalog"] = [
            {"id": 1, "name": "Small Truck", "res": "t1", "carrier": "ROAD", "available": True, "capacity": [{"cargo": COAL, "capacity": 20}],
             "price": 1000, "runningCosts": 60, "yearFrom": 1970, "yearTo": 2000},
            {"id": 2, "name": "Big Truck", "res": "t2", "carrier": "ROAD", "available": True, "capacity": [{"cargo": COAL, "capacity": 40}],
             "price": 3000, "runningCosts": 200, "yearFrom": 1970, "yearTo": 2000},
            {"id": 3, "name": "Old Truck", "res": "t3", "carrier": "ROAD", "available": True, "capacity": [{"cargo": COAL, "capacity": 99}],
             "price": 10, "runningCosts": 1, "yearFrom": 1920, "yearTo": 1950},
        ]
    return data


def default_industries():
    return [
        industry(1, "Mine A", "coal_mine", 0, 0, outputs=[out(COAL, 200, 0)]),
        industry(2, "Steel B", "steel_mill", 6000, 0, inputs=[inp(COAL, 300), inp(IRON, 300)], outputs=[out(7, 0, 0, 200)]),
        industry(3, "Mine C", "iron_ore_mine", 0, 1000, outputs=[out(IRON, 100, 90)]),
    ]


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "x.db")
    yield s
    s.close()


def add(store, data):
    store.add_snapshot(Snapshot(data, source=f"s{data['meta']['gameTime']}.lua"))


def text(store):
    return reports.render_markdown(rx.build(store))


def test_no_snapshot_raises(store):
    with pytest.raises(ValueError):
        rx.build(store)


def test_ranking_scores_components_and_formula(store):
    stocks = [{"kind": "industry", "owner": 1, "cargos": [COAL], "count": 400, "capacity": 400}]
    add(store, make(stocks=stocks))
    doc = rx.build(store)
    md = reports.render_markdown(doc)
    assert "## Scoring Formula" in md and "Score = Volume + Distance + Urgency + Pull + Chain + Proven - Penalties" in md
    ctx = rx._Context(store, store.latest())
    cands, excluded, dead = rx._candidates(ctx)
    picked = rx._rank(ctx, cands, 10)
    assert [c["producer"]["name"] for c in picked] == ["Mine A"]  # Mine C ships 90% so it is not under-shipped
    top = picked[0]
    assert top["consumer"]["name"] == "Steel B" and top["volume"] == 200
    assert top["distance"] == pytest.approx(6.0)
    parts = top["parts"]
    assert parts["volume"] == 30  # 200 unmet items exceeds the 150 reference
    assert parts["distance"] == 20
    assert top["persistence"] is None  # a single snapshot: not enough samples
    assert parts["urgency"] == pytest.approx(20 * (0.5 * 1.0 + 0.5 * 1.0))  # nothing shipped, stock 100% full
    assert parts["pull"] == pytest.approx(10.0)  # consumer uses none of its 300 coal capacity
    assert parts["chain"] == 0  # steel output code 7 has no consumer and is not demanded by a town
    assert top["score"] == pytest.approx(sum(parts.values()))
    assert "consumer also lacks Iron" in "; ".join(top["flags"])
    # breakdown table sums
    assert "Score Breakdown" in md


def test_already_served_pair_is_excluded_not_recommended(store):
    lines = (
        [{"id": 100, "name": "Coal Run", "vehicles": [1000], "stops": [{"stationGroup": 500}, {"stationGroup": 501}],
          "profitYear": 5, "capacity": [], "issues": []}],
        [{"id": 1000, "name": "T1", "carrier": "ROAD", "state": "EN_ROUTE", "line": 100, "profitYear": 5, "models": [7],
          "loadConfig": [{"cargo": COAL, "capacity": 20}], "purchaseTime": 0}],
        [{"id": 500, "name": "Mine A", "lines": [100]}, {"id": 501, "name": "Steel B", "lines": [100]}],
    )
    add(store, make(lines=lines))
    md = text(store)
    top = md.split("## Top")[1].split("## Extend")[0]
    assert "Mine A -&gt; Steel B" not in top
    assert "Coal Run" in md.split("## Cross-Check")[1]


def test_line_without_matching_cargo_does_not_exclude(store):
    lines = (
        [{"id": 100, "name": "Pax Run", "vehicles": [1000], "stops": [{"stationGroup": 500}, {"stationGroup": 501}],
          "profitYear": 5, "capacity": [], "issues": []}],
        [{"id": 1000, "name": "T1", "carrier": "ROAD", "state": "EN_ROUTE", "line": 100, "profitYear": 5, "models": [7],
          "loadConfig": [{"cargo": 0, "capacity": 20}], "purchaseTime": 0}],
        [{"id": 500, "name": "Mine A", "lines": [100]}, {"id": 501, "name": "Steel B", "lines": [100]}],
    )
    add(store, make(lines=lines))
    assert "Mine A -&gt; Steel B" in text(store)


def test_closing_consumer_penalised_and_full_input_stock(store):
    inds = default_industries()
    inds[1]["closureTimeStamp"] = 123
    stocks = [{"kind": "industry", "owner": 2, "cargos": [COAL], "count": 790, "capacity": 800}]
    add(store, make(industries=inds, stocks=stocks))
    ctx = rx._Context(store, store.latest())
    picked = rx._rank(ctx, rx._candidates(ctx)[0], 5)
    assert picked and dict(picked[0]["penalties"]) == {"consumer industry is closing": 30, "consumer input stock 98.8% full": 15}
    assert picked[0]["score"] == pytest.approx(max(0, sum(picked[0]["parts"].values()) - 45))


def test_shared_consumer_capacity_is_deducted(store):
    inds = [
        industry(1, "Mine A", "coal_mine", 0, 0, outputs=[out(COAL, 150, 0)]),
        industry(4, "Mine D", "coal_mine", 0, 4000, outputs=[out(COAL, 150, 0)]),
        industry(2, "Steel B", "steel_mill", 5000, 0, inputs=[inp(COAL, 200)], outputs=[]),
    ]
    add(store, make(industries=inds))
    ctx = rx._Context(store, store.latest())
    picked = rx._rank(ctx, rx._candidates(ctx)[0], 5)
    assert sorted(c["volume"] for c in picked) == [50, 150]


def test_town_candidate_uses_name_anchor_and_marks_estimate(store):
    inds = [
        industry(1, "Mine A", "coal_mine", 0, 0, outputs=[out(COAL, 120, 0)]),
        industry(9, "Depot of Oakton", "farm", 4000, 3000),
    ]
    towns = [{"id": 900, "name": "Oakton", "capacities": [300, 100, 100], "lineUsage": 0.0,
              "cargoSupply": [{"cargo": COAL, "supply": 20, "limit": 100, "extra": 1}]},
             {"id": 901, "name": "Nowhere", "capacities": [300, 100, 100], "lineUsage": 0.0,
              "cargoSupply": [{"cargo": COAL, "supply": 0, "limit": 100, "extra": 1}]}]
    add(store, make(industries=inds, towns=towns))
    ctx = rx._Context(store, store.latest())
    cands = rx._candidates(ctx)[0]
    by_town = {c["consumer"]["name"]: c for c in cands if c["type"] == "town"}
    assert by_town["Oakton"]["distance"] == pytest.approx(5.0)
    assert by_town["Oakton"]["unmet"] == 80
    assert by_town["Nowhere"]["distance"] is None
    picked = rx._rank(ctx, cands, 5)
    assert picked[0]["consumer"]["name"] == "Oakton"
    nowhere = rx._score(ctx, by_town["Nowhere"], {})
    assert nowhere["parts"]["distance"] == 0 and "distance unknown" in nowhere["flags"]


def test_vehicle_fit_uses_available_models_and_capacity_crosscheck(store):
    lines = (
        [{"id": 100, "name": "Coal Run", "vehicles": [1000], "stops": [{"stationGroup": 500}, {"stationGroup": 501}],
          "profitYear": 5, "capacity": [], "issues": []}],
        [{"id": 1000, "name": "T1", "carrier": "ROAD", "state": "EN_ROUTE", "line": 100, "profitYear": 5, "models": [7],
          "loadConfig": [{"cargo": COAL, "capacity": 20}], "purchaseTime": 0}],
        [{"id": 500, "name": "Elsewhere", "lines": [100]}, {"id": 501, "name": "Other", "lines": [100]}],
    )
    data = make(catalog=True, lines=lines)
    data["models"] = [{"id": 7, "res": "t1"}]
    data["meta"]["verifiedUnits"] = {"runningCosts": "currency/year", "price": "currency"}
    add(store, data)
    md = text(store)
    fit = md.split("### Vehicle Fit")[1].split("## Extend")[0]
    assert "Big Truck" in fit and "Small Truck" in fit
    assert "Old Truck" not in fit  # out of production in 1980
    assert "matches the recorded capacity of 1 of 1" in fit
    assert "omitted when units are unverified" in fit


def test_no_catalog_degrades(store):
    add(store, make())
    assert "No catalog snapshot is stored" in text(store)


def test_no_industries_gives_insufficient_data_not_error(store):
    add(store, make(industries=[]))
    md = text(store)
    assert "Insufficient Data" in md
    reports.render_html(rx.build(store))


def test_multi_year_history_is_sampled_and_persistence_uses_it(store):
    n = 0
    for year in range(1980, 1986):
        for month in (1, 4, 7, 10):
            n += 1
            shipped = 0 if not (year == 1985 and month == 10) else 0
            inds = default_industries()
            inds[0]["outputs"][0]["shippedYear"] = shipped
            add(store, make(game_time=year * YEAR + month * 10, date=(year, month, 1), industries=inds))
    ctx = rx._Context(store, store.latest())
    assert len(ctx.samples) <= rx.MAX_MONTHLY_SAMPLES + rx.MAX_QUARTERLY_SAMPLES + 1
    assert len(ctx.samples) > rx.PERSISTENCE_MIN_SAMPLES
    picked = rx._rank(ctx, rx._candidates(ctx)[0], 5)
    assert picked[0]["persistence"] == 1.0
    md = text(store)
    assert "under-shipped in 100% of" in md
    assert "History Samples" in md


def test_persistence_reduces_urgency_when_flow_was_served_before(store):
    for i, shipped in enumerate([180, 170, 0, 0]):
        inds = default_industries()
        inds[0]["outputs"][0]["shippedYear"] = shipped
        add(store, make(game_time=10 * YEAR + i * 10, date=(1980, 1 + i, 1), industries=inds))
    ctx = rx._Context(store, store.latest())
    picked = rx._rank(ctx, rx._candidates(ctx)[0], 5)
    assert picked[0]["persistence"] == pytest.approx(0.5)


def test_html_escapes_names_and_is_offline(store):
    inds = default_industries()
    inds[0]["name"] = "<script>alert(1)</script> Mine"
    add(store, make(industries=inds))
    html = reports.render_html(rx.build(store))

    class P(HTMLParser):
        def __init__(self):
            super().__init__()
            self.tags, self.urls = [], []

        def handle_starttag(self, tag, attrs):
            self.tags.append(tag)
            self.urls += [v for k, v in attrs if k in ("src", "href")]

    p = P()
    p.feed(html)
    assert "script" not in p.tags and not p.urls
    assert "&lt;script&gt;alert(1)&lt;/script&gt; Mine" in html


def test_deterministic(store):
    add(store, make())
    assert text(store) == text(store)


def test_chart_has_adjacent_table_with_same_scores(store):
    add(store, make())
    doc = rx.build(store)
    chart = next(b for b in doc.blocks if isinstance(b, reports.Chart))
    table = doc.blocks[doc.blocks.index(chart) - 1]
    assert isinstance(table, reports.Table)
    assert [r[5] for r in table.rows] == chart.series[0][1]


def test_distance_points_shape():
    assert rx._distance_points(None) == 0
    assert rx._distance_points(0.2) == 0
    assert rx._distance_points(1.75) == pytest.approx(10)
    assert rx._distance_points(5) == 20
    assert rx._distance_points(15) == pytest.approx(20 * 0.7)
    assert rx._distance_points(50) == pytest.approx(20 * 0.4)


def test_missing_shipping_or_demand_does_not_become_zero(store):
    data = make()
    del data["industries"][0]["outputs"][0]["shippedYear"]
    add(store, data)
    ctx = rx._Context(store, store.latest())
    assert not rx._candidates(ctx)[0]
    assert rx._unmet_input({"inputs": [{"cargo": COAL, "maxConsumptionYear": 300}]}, COAL) == (0, 0)


def test_unverified_costs_are_not_ranked_or_printed(store):
    add(store, make(catalog=True))
    fit = text(store).split("### Vehicle Fit")[1].split("## Extend")[0]
    assert "Small Truck" not in fit  # cheap-cost selection cannot run without units
    table = next(b for b in rx.build(store).blocks if isinstance(b, reports.Table) and b.columns[:2] == ["#", "Cargo"])
    assert all(row[7:9] == [None, None] for row in table.rows)


def test_transfer_connection_is_conservatively_excluded(store):
    data = make()
    data["lines"] = [
        {"id": 100, "name": "Coal feeder", "vehicles": [1000], "stops": [{"stationGroup": 500}, {"stationGroup": 502}]},
        {"id": 101, "name": "Coal trunk", "vehicles": [1001], "stops": [{"stationGroup": 502}, {"stationGroup": 501}]},
    ]
    data["vehicles"] = [{"id": vid, "line": lid, "loadConfig": [{"cargo": COAL, "capacity": 20}]}
                        for vid, lid in ((1000, 100), (1001, 101))]
    data["stations"] = [{"id": 500, "name": "Mine A"}, {"id": 501, "name": "Steel B"}, {"id": 502, "name": "Hub"}]
    add(store, data)
    ctx = rx._Context(store, store.latest())
    candidates, excluded, _ = rx._candidates(ctx)
    assert not candidates
    assert excluded[0]["lines"] == ["Coal feeder", "Coal trunk"]
