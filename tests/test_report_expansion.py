from __future__ import annotations

import dataclasses
import json
from html.parser import HTMLParser

import pytest

from conftest import YEAR, base_snapshot
from tf3companion import reports
from tf3companion.analysis import Thresholds
from tf3companion.analysis_views import EvaluationContext, evaluate_views
from tf3companion.analysis_views.models import plain
from tf3companion.snapshot import Snapshot
from tf3companion.store import Store
from tf3companion.report_policy import resolve_context
from view_helpers import document, view

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
    return reports.render_markdown(document(store, "expansion"))


def ev(store):
    return view(store, "expansion")


def lines_for(*, cargo=COAL):
    return (
        [{"id": 100, "name": "Coal Run", "vehicles": [1000], "stops": [{"stationGroup": 500}, {"stationGroup": 501}],
          "profitYear": 5, "capacity": [], "issues": []}],
        [{"id": 1000, "name": "T1", "carrier": "ROAD", "state": "EN_ROUTE", "line": 100, "profitYear": 5, "models": [7],
          "loadConfig": [{"cargo": cargo, "capacity": 20}], "purchaseTime": 0}],
        [{"id": 500, "name": "Mine A", "lines": [100]}, {"id": 501, "name": "Steel B", "lines": [100]}],
    )


def test_no_snapshot_raises(store):
    with pytest.raises(ValueError):
        ev(store)


def test_ranking_scores_components_and_formula(store):
    stocks = [{"kind": "industry", "owner": 1, "cargos": [COAL], "count": 400, "capacity": 400}]
    add(store, make(stocks=stocks))
    v = ev(store)
    md = text(store)
    assert "## Scoring Formula" in md and "Score = Volume + Distance + Urgency + Pull + Chain + Proven - Penalties" in md
    assert [c.producer.name for c in v.candidates] == ["Mine A"]  # Mine C ships 90% so it is not under-shipped
    top = v.candidates[0]
    assert top.rank == 1 and top.consumer.name == "Steel B" and top.volume == 200
    assert top.distance_km == pytest.approx(6.0) and top.distance_method == "industry-positions"
    assert top.parts.volume == 30  # 200 unmet items exceeds the 150 reference
    assert top.parts.distance == 20
    assert top.persistence is None and top.persistence_samples == 1  # a single snapshot: not enough samples
    assert top.parts.urgency == pytest.approx(20 * (0.5 * 1.0 + 0.5 * 1.0))  # nothing shipped, stock 100% full
    assert top.parts.pull == pytest.approx(10.0)  # consumer uses none of its 300 coal capacity
    assert top.parts.chain == 0  # steel output code 7 has no consumer and is not demanded by a town
    assert top.score == pytest.approx(sum(dataclasses.astuple(top.parts)))
    assert any(f.code == "consumer_lacks_inputs" and f.subject == "Iron" for f in top.flags)
    assert "consumer also lacks Iron" in md
    assert "Score Breakdown" in md


def test_view_and_report_agree_on_numbers_and_order(store):
    inds = [
        industry(1, "Mine A", "coal_mine", 0, 0, outputs=[out(COAL, 150, 0)]),
        industry(4, "Mine D", "coal_mine", 0, 4000, outputs=[out(COAL, 150, 20)]),
        industry(2, "Steel B", "steel_mill", 5000, 0, inputs=[inp(COAL, 200)], outputs=[]),
    ]
    add(store, make(industries=inds))
    v = ev(store)
    doc = document(store, "expansion")
    ranking = next(b for b in doc.blocks if isinstance(b, reports.Table) and b.columns[:2] == ["#", "Route (producer -> consumer)"])
    assert [r[0] for r in ranking.rows] == [c.rank for c in v.candidates]
    assert [r[5] for r in ranking.rows] == [round(c.score, 1) for c in v.candidates]
    assert [r[3] for r in ranking.rows] == [round(c.volume) for c in v.candidates]
    breakdown = next(b for b in doc.blocks if isinstance(b, reports.Table) and b.columns[:2] == ["#", "Volume"])
    assert [r[-1] for r in breakdown.rows] == [round(c.score, 1) for c in v.candidates]
    assert v.candidates_evaluated == 2 and v.outputs_evaluated == 2


def test_already_served_pair_is_excluded_not_recommended(store):
    add(store, make(lines=lines_for()))
    v = ev(store)
    assert all(not (c.producer.name == "Mine A" and c.consumer.name == "Steel B") for c in v.candidates)
    assert [(e.producer.name, e.consumer.name, e.lines) for e in v.excluded] == [("Mine A", "Steel B", ("Coal Run",))]
    md = text(store)
    top = md.split("## Top")[1].split("## Extend")[0] if "## Top" in md else ""
    assert "Mine A -&gt; Steel B" not in top
    assert "Coal Run" in md.split("## Cross-Check")[1]


def test_line_without_matching_cargo_does_not_exclude(store):
    add(store, make(lines=lines_for(cargo=0)))
    v = ev(store)
    assert not v.excluded
    assert any(c.producer.name == "Mine A" and c.consumer.name == "Steel B" for c in v.candidates)
    assert "Mine A -&gt; Steel B" in text(store)


def test_closing_consumer_penalised_and_full_input_stock(store):
    inds = default_industries()
    inds[1]["closureTimeStamp"] = 123
    stocks = [{"kind": "industry", "owner": 2, "cargos": [COAL], "count": 790, "capacity": 800}]
    add(store, make(industries=inds, stocks=stocks))
    top = ev(store).candidates[0]
    assert {p.code: p.amount for p in top.penalties} == {"consumer_closing": 30, "consumer_input_stock_full": 15}
    assert top.penalty_total == 45
    assert top.score == pytest.approx(max(0, sum(dataclasses.astuple(top.parts)) - 45))
    assert "consumer input stock 98.8% full" in text(store)


def test_shared_consumer_capacity_is_deducted(store):
    inds = [
        industry(1, "Mine A", "coal_mine", 0, 0, outputs=[out(COAL, 150, 0)]),
        industry(4, "Mine D", "coal_mine", 0, 4000, outputs=[out(COAL, 150, 0)]),
        industry(2, "Steel B", "steel_mill", 5000, 0, inputs=[inp(COAL, 200)], outputs=[]),
    ]
    add(store, make(industries=inds))
    picked = ev(store).candidates
    assert sorted(c.volume for c in picked) == [50, 150]
    assert sum(c.volume for c in picked) <= 200  # conserved: never more than the consumer's recorded unmet input
    assert [c.unmet_available for c in picked] == [200, 50]


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
    v = ev(store)
    top = v.candidates[0]
    assert top.consumer.name == "Oakton" and top.consumer_kind == "town"
    assert top.distance_km == pytest.approx(5.0) and top.unmet_recorded == 80 and top.town_supplied == 20
    assert top.distance_method == "town-anchor-estimate" and top.anchor_industries == 1
    assert any(f.code == "town_distance_estimate" for f in top.flags)
    assert [a.consumer.name for a in top.alternatives] == ["Nowhere"] and top.alternatives[0].distance_km is None
    assert [(a.town.name, a.industries_used) for a in v.town_anchors] == [("Oakton", 1)]
    assert "town estimated from 1 industry named after it" in text(store)


def test_unanchored_town_scores_zero_distance_and_flags_unknown(store):
    inds = [industry(1, "Mine A", "coal_mine", 0, 0, outputs=[out(COAL, 120, 0)])]
    towns = [{"id": 901, "name": "Nowhere", "capacities": [300, 100, 100], "lineUsage": 0.0,
              "cargoSupply": [{"cargo": COAL, "supply": 0, "limit": 100, "extra": 1}]}]
    add(store, make(industries=inds, towns=towns))
    top = ev(store).candidates[0]
    assert top.distance_km is None and top.distance_method == "unknown" and top.parts.distance == 0
    assert any(f.code == "distance_unknown" for f in top.flags)


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
    v = ev(store)
    names = {f.model.name for f in v.catalog.candidates}
    assert names == {"Big Truck", "Small Truck"}  # Old Truck is out of production in 1980
    assert (v.catalog.capacity_matched, v.catalog.capacity_compared) == (1, 1)
    assert v.catalog.price_verified and v.catalog.running_costs_verified
    big = next(f for f in v.catalog.candidates if f.model.name == "Big Truck")
    assert big.why == ("largest_capacity",) and big.capacity == 40 and big.loads_per_year == pytest.approx(200 / 40)
    assert big.price == 3000 and big.running_costs == 200
    md = text(store)
    fit = md.split("### Vehicle Fit")[1].split("## Extend")[0]
    assert "Big Truck" in fit and "Small Truck" in fit and "Old Truck" not in fit
    assert "matches the recorded capacity of 1 of 1" in fit
    assert "omitted when units are unverified" in fit


def test_no_catalog_degrades(store):
    add(store, make())
    v = ev(store)
    assert v.catalog.sample is None and not v.catalog.candidates
    assert any(u.code == "catalog_missing" for u in v.coverage.unavailable)
    assert "No catalog snapshot is stored" in text(store)


def test_no_industries_gives_insufficient_data_not_error(store):
    add(store, make(industries=[]))
    assert not ev(store).candidates
    assert "Insufficient Data" in text(store)
    reports.render_html(document(store, "expansion"))


def test_multi_year_history_is_sampled_and_persistence_uses_it(store):
    for year in range(1980, 1986):
        for month in (1, 4, 7, 10):
            inds = default_industries()
            inds[0]["outputs"][0]["shippedYear"] = 0
            add(store, make(game_time=year * YEAR + month * 10, date=(year, month, 1), industries=inds))
    v = ev(store)
    assert 3 < v.coverage.used <= 21  # at most 12 monthly + 8 quarterly representatives + the endpoint
    assert v.candidates[0].persistence == 1.0
    assert v.coverage.sampled[-1].tick == store.latest().game_time
    md = text(store)
    assert "under-shipped in 100% of" in md
    assert "History Samples" in md


def test_persistence_reduces_urgency_when_flow_was_served_before(store):
    for i, shipped in enumerate([180, 170, 0, 0]):
        inds = default_industries()
        inds[0]["outputs"][0]["shippedYear"] = shipped
        add(store, make(game_time=10 * YEAR + i * 10, date=(1980, 1 + i, 1), industries=inds))
    top = ev(store).candidates[0]
    assert top.persistence == pytest.approx(0.5) and top.persistence_samples == 4


def test_html_escapes_names_and_is_offline(store):
    inds = default_industries()
    inds[0]["name"] = "<script>alert(1)</script> Mine"
    add(store, make(industries=inds))
    html = reports.render_html(document(store, "expansion"))

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
    assert plain(ev(store)) == plain(ev(store))


def test_chart_has_adjacent_table_with_same_scores(store):
    add(store, make())
    doc = document(store, "expansion")
    chart = next(b for b in doc.blocks if isinstance(b, reports.Chart))
    table = doc.blocks[doc.blocks.index(chart) - 1]
    assert isinstance(table, reports.Table)
    assert [r[5] for r in table.rows] == chart.series[0][1]


@pytest.mark.parametrize("distance_m, expected", [
    (200, 0), (1750, 10), (5000, 20), (15000, 20 * 0.7), (50000, 20 * 0.4)])
def test_distance_points_shape(store, distance_m, expected):
    inds = [industry(1, "Mine A", "coal_mine", 0, 0, outputs=[out(COAL, 500, 0)]),
            industry(2, "Steel B", "steel_mill", distance_m, 0, inputs=[inp(COAL, 600)], outputs=[])]
    add(store, make(industries=inds))
    assert ev(store).candidates[0].parts.distance == pytest.approx(expected)


def test_missing_shipping_or_demand_does_not_become_zero(store):
    data = make()
    del data["industries"][0]["outputs"][0]["shippedYear"]
    add(store, data)
    assert not ev(store).candidates
    other = make(game_time=11 * YEAR)
    del other["industries"][1]["inputs"][0]["deliveredYear"]  # unknown demand cannot justify a route
    add(store, other)
    v = ev(store)
    assert not any(c.consumer.name == "Steel B" and c.cargo.id == COAL for c in v.candidates)
    assert any(d.producer.name == "Mine A" for d in v.dead_ends) or v.candidates_evaluated == 0


def test_unverified_costs_are_not_ranked_or_printed(store):
    add(store, make(catalog=True))
    v = ev(store)
    assert v.catalog.sample is not None and not v.catalog.price_verified and not v.catalog.running_costs_verified
    assert all(f.price is None and f.running_costs is None for f in v.catalog.candidates)
    assert all("lowest_running_cost_per_capacity" not in f.why for f in v.catalog.candidates)
    fit = text(store).split("### Vehicle Fit")[1].split("## Extend")[0]
    assert "Small Truck" not in fit  # cheap-cost selection cannot run without units
    table = next(b for b in document(store, "expansion").blocks if isinstance(b, reports.Table) and b.columns[:2] == ["#", "Cargo"])
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
    v = ev(store)
    assert not v.candidates
    assert v.excluded[0].lines == ("Coal feeder", "Coal trunk")


def test_dead_end_reasons_and_order(store):
    inds = [industry(1, "Mine A", "coal_mine", 0, 0, outputs=[out(COAL, 300, 0)]),
            industry(2, "Quarry", "quarry", 0, 3000, outputs=[out(9, 500, 0)]),
            industry(3, "Full Steel", "steel_mill", 6000, 0, inputs=[inp(COAL, 100, delivered=100)], outputs=[])]
    data = make(industries=inds)
    data["cargos"].append({"id": 9, "name": "Stone", "res": "::/cargos/stone/stone.cargo"})
    add(store, data)
    v = ev(store)
    assert [(d.producer.name, d.reasons) for d in v.dead_ends] == [("Quarry", ("no_consumer",)), ("Mine A", ("input_at_capacity",))]
    md = text(store)
    assert "consumer input already at recorded capacity" in md and "no consumer of this cargo in the snapshot" in md


def test_proven_economics_groups_and_ranking_counts(store):
    data = make()
    data["lines"] = [{"id": 100, "name": "Coal Run", "vehicles": [1, 2, 3], "stops": [{"stationGroup": 500}, {"stationGroup": 502}]}]
    data["vehicles"] = [{"id": i, "line": 100, "carrier": "ROAD", "profitYear": p, "loadConfig": [{"cargo": COAL, "capacity": 20}]}
                        for i, p in ((1, 100), (2, 50), (3, -10))]
    data["stations"] = [{"id": 500, "name": "Mine A"}, {"id": 502, "name": "Hub"}]
    add(store, data)
    v = ev(store)
    group = next(g for g in v.proven if g.cargo.id == COAL)
    assert (group.carrier, group.vehicles, group.profitable, group.median_profit, group.qualifies) == ("ROAD", 3, 2, 50, True)
    assert group.candidates_in_ranking == 1
    top = v.candidates[0]
    assert top.proof.share == pytest.approx(2 / 3) and top.proof.best_carrier == "ROAD"
    assert top.parts.proven == pytest.approx(10 * 2 / 3)


def test_starved_consumer_and_unknown_usage_is_not_starved(store):
    add(store, make())
    v = ev(store)
    starved = v.starved_consumers
    assert [(s.consumer.name, s.capacity, s.usage_ratio) for s in starved] == [("Steel B", 600, 0)]
    assert {(s.cargo.id, s.producer.name if s.producer else None) for s in starved[0].suppliers} == {(COAL, "Mine A"), (IRON, "Mine C")}
    assert "Starved Consumers" in text(store)

    other = make(game_time=11 * YEAR)
    for flow in other["industries"][1]["inputs"]:
        flow["deliveredYear"] = flow["consumedYear"] = None
    add(store, other)
    v = ev(store)
    assert not v.starved_consumers  # unknown usage is not "no deliveries"
    assert [r.name for r in v.unassessed_consumers] == ["Steel B"]
    assert any(u.code == "starved_usage_unknown" for u in v.coverage.unavailable)
    assert "not assessed because their recorded input usage is unknown" in text(store)


def test_town_with_unknown_supply_is_not_counted_as_unmet(store):
    towns = [{"id": 900, "name": "Oakton", "capacities": [300, 100, 100], "lineUsage": 0.0,
              "cargoSupply": [{"cargo": COAL, "supply": None, "limit": 100},
                              {"cargo": IRON, "supply": 10, "limit": 100}]}]
    add(store, make(towns=towns))
    row = ev(store).towns[0]
    assert row.town.name == "Oakton" and row.capacity_sum == 500 and row.stations == 0
    assert [c.name for c in row.unmet_cargos] == ["Iron"]
    assert [c.name for c in row.unknown_supply_cargos] == ["Coal"]
    assert "Oakton" in text(store)


def test_nondefault_threshold_changes_membership_not_measurements(store):
    add(store, make())
    default = ev(store)
    loose = view(store, "expansion", Thresholds(unshipped_ratio=0.95))
    assert {c.producer.name for c in default.candidates} == {"Mine A"}
    assert {c.producer.name for c in loose.candidates} == {"Mine A", "Mine C"}
    a_default = default.candidates[0]
    a_loose = next(c for c in loose.candidates if c.producer.name == "Mine A")
    assert (a_default.produced, a_default.shipped, a_default.unshipped) == (a_loose.produced, a_loose.shipped, a_loose.unshipped)


def test_view_is_plain_serializable_and_holds_no_snapshots(store):
    add(store, make(catalog=True))
    v = ev(store)
    encoded = json.dumps(plain(v))
    assert '"candidates"' in encoded and '"coverage"' in encoded
    assert not any(isinstance(x, (Snapshot, Store)) for x in dataclasses.astuple(v))


def test_selected_earlier_endpoint_excludes_later_entities_and_catalog(store):
    early = make(game_time=10 * YEAR, date=(1980, 1, 1))
    late = make(game_time=11 * YEAR, date=(1981, 1, 1), catalog=True)
    late["industries"].append(industry(8, "Future Mine", "coal_mine", 0, 500, outputs=[out(COAL, 300, 0)]))
    add(store, early)
    add(store, late)
    snap = store.snapshot_at_or_before(10 * YEAR)
    ctx = EvaluationContext(snap, resolve_context(), store.time_context(snap), None, store.previous_of(snap))
    v = evaluate_views(store, ctx, ("expansion",)).expansion
    names = {c.producer.name for c in v.candidates} | {d.producer.name for d in v.dead_ends}
    assert "Future Mine" not in names and "Mine A" in names
    assert v.catalog.sample is None  # the only catalog is stored after the endpoint
    assert v.coverage.endpoint.tick == 10 * YEAR and v.coverage.eligible == 1
    assert all(s.tick <= 10 * YEAR for s in v.coverage.sampled)
    latest = ev(store)
    assert "Future Mine" in {c.producer.name for c in latest.candidates}
    assert latest.catalog.sample is not None and latest.coverage.eligible == 2


def test_hydration_is_bounded_for_a_long_history(store):
    for year in range(1980, 1990):
        for month in range(1, 13):
            add(store, make(game_time=year * YEAR + month * 10, date=(year, month, 1), catalog=(year == 1980 and month == 1)))
    v = ev(store)
    assert v.coverage.eligible == 120
    assert v.coverage.used <= 21 and v.coverage.omitted == 120 - v.coverage.used
    assert v.coverage.hydrated <= v.coverage.hydration_limit
    assert v.catalog.sample.tick == 1980 * YEAR + 10  # one catalog, hydrated once
    assert len({s.tick for s in v.coverage.sampled}) == v.coverage.used
