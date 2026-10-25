"""Behavioral policy registry, propagation and isolated real CLI comparison."""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
from pathlib import Path

import pytest

from methodology_helpers import methodology
from test_report_expansion import COAL, industry, inp, make, out
from tf3companion import reports
from tf3companion.analysis import Thresholds
from tf3companion.methodology import load_file
from tf3companion.methodology.lens import build_lens
from tf3companion.report_policy import resolve_context, validate_report_policies
from tf3companion.snapshot import Snapshot
from tf3companion.store import Store
from view_helpers import document, view

FIXTURES = Path(__file__).parent / "fixtures" / "methodologies"


def ctx(**families):
    return resolve_context(methodology(report_policies=families))


@pytest.mark.parametrize("raw,path", [
    ({"unknown": {}}, "/report_policies/unknown"),
    ({"lines-history": {"minimum_points": 1}}, "/report_policies/lines-history/minimum_points"),
    ({"lines-history": {"noise_factor": True}}, "/report_policies/lines-history/noise_factor"),
    ({"lines-history": {"noise_factor": float("nan")}}, "/report_policies/lines-history/noise_factor"),
    ({"bottlenecks": {"persistence_streak": 2}}, "/report_policies/bottlenecks/persistence_streak"),
    ({"bottlenecks": {"pileup_min": 3.5}}, "/report_policies/bottlenecks/pileup_min"),
    ({"expansion": {"weight_volume": 29}}, "/report_policies/expansion/weight_volume"),
    ({"expansion": {"distance_short_km": 3}}, "/report_policies/expansion/distance_short_km"),
])
def test_invalid_registry_fields_fail_locally(raw, path):
    issues = validate_report_policies(raw)
    assert any(p == path for p, _ in issues)


def test_explicit_default_origin_and_frozen_context():
    c = ctx(**{"lines-history": {"noise_factor": 2}})
    p = c.provenance()
    assert p["reportPolicy"]["registryVersion"] == 1
    assert p["reportPolicy"]["origins"]["lines-history"]["noise_factor"] == "methodology"
    assert p["reportPolicy"]["origins"]["lines-history"]["floor_share"] == "default"
    assert resolve_context().provenance()["reportPolicy"]["values"] == resolve_context(methodology(report_policies={})).provenance()["reportPolicy"]["values"]
    with pytest.raises(TypeError):
        c.policies["other"] = None
    with pytest.raises(ValueError):
        resolve_context(methodology(), thresholds=Thresholds())


def lens_for(store, thresholds=None, **families):
    """A lens over the latest sample whose methodology carries the given report policies and engine thresholds."""
    parts = {"report_policies": families}
    if thresholds:
        parts["engine"] = {"thresholds": thresholds}
    return build_lens(store, store.latest(), methodology(**parts))


def lens_view(store, name, thresholds=None, **families):
    return view(store, name, lens=lens_for(store, thresholds, **families))


def lens_document(store, name, thresholds=None, **families):
    return document(store, name, lens=lens_for(store, thresholds, **families))


def pair_distance_parts(tmp_path, tag, km, **families):
    """The distance score of a single coal route whose consumer is `km` kilometres from the producer (None: unknown position)."""
    store = Store(tmp_path / f"{tag}.db")
    try:
        consumer = industry(2, "Consumer", "factory", int(km * 1000) if km is not None else 0, 0, inputs=[inp(COAL, 150)])
        if km is None:
            consumer["position"] = None
        store.add_snapshot(Snapshot(make(industries=[industry(1, "Producer", "coal_mine", 0, 0, outputs=[out(COAL, 150, 0)]), consumer])))
        (candidate,) = lens_view(store, "expansion", **families).candidates
        return candidate
    finally:
        store.close()


def test_distance_breakpoints_and_numeric_priority_reversal(tmp_path):
    p = resolve_context().policies["expansion"]
    points = (p.distance_short_km, p.distance_sweet_from_km, p.distance_sweet_to_km, p.distance_long_km)
    neutral = [pair_distance_parts(tmp_path, f"n{i}", km).parts.distance / p.weight_distance for i, km in enumerate(points)]
    assert neutral == [0, 1, 1, .4]
    unknown = pair_distance_parts(tmp_path, "unknown", None)
    assert unknown.distance_km is None and unknown.parts.distance == 0
    # Numeric priority reversal: a short heavy route beats a longer light one under neutral weights, not under distance-first weights.
    store = Store(tmp_path / "rank.db")
    try:
        store.add_snapshot(Snapshot(evidence(), source="fixture"))
        priority_policy = {"expansion": {"weight_volume": 10, "weight_distance": 40}}
        neutral_view = lens_view(store, "expansion")
        priority_view = lens_view(store, "expansion", **priority_policy)
        def by_producer(v):
            return {c.producer.id: c for c in v.candidates}
        n, pr = by_producer(neutral_view), by_producer(priority_view)
        assert n[3].parts.distance == 20 and pr[3].parts.distance == 40 and n[3].distance_km == pr[3].distance_km == 3
        assert n[3].parts.volume == 6 and pr[3].parts.volume == 2
        assert n[1].parts.distance == pr[1].parts.distance == 0
        assert n[1].score == 45 > n[3].score == 41
        assert pr[3].score == 57 > pr[1].score == 25
    finally:
        store.close()


def evidence(tick=0, month=1):
    # Different cargos prevent shared-demand allocation from obscuring ranking reversal.
    inds = [industry(1, "A volume", "coal_mine", 0, 0, outputs=[out(COAL, 150, 0)]),
            industry(2, "A consumer", "factory", 100, 0, inputs=[inp(COAL, 150)]),
            industry(3, "B distance", "mine", 10000, 0, outputs=[out(4, 30, 0)]),
            industry(4, "B consumer", "factory", 13000, 0, inputs=[inp(4, 30)])]
    lines = ([{"id": 100, "name": "Sampled load", "vehicles": [1000, 1001],
               "stops": [{"stationGroup": 10}, {"stationGroup": 11}], "capacity": [{"cargo": 0, "used": 85, "capacity": 100}],
               "profitYear": 100, "issues": []}],
             [{"id": v, "name": f"Vehicle {v}", "line": 100, "carrier": "ROAD", "state": "EN_ROUTE",
               "purchaseTime": 0, "profitYear": 50, "models": [], "capacity": 50, "loadConfig": [{"cargo": 0, "capacity": 50}]} for v in (1000, 1001)], [])
    return make(game_time=tick, date=(1980, month, 1), industries=inds, lines=lines)


def test_actual_ranking_propagation_and_demand_conservation(tmp_path):
    store = Store(tmp_path / "c.db")
    try:
        store.add_snapshot(Snapshot(evidence(), source="fixture"))
        a = lens_view(store, "expansion").candidates
        b = lens_view(store, "expansion", expansion={"weight_volume": 10, "weight_distance": 40}).candidates
        assert a[0].producer.id == 1
        assert b[0].producer.id == 3
        assert [c.rank for c in a] == [c.rank for c in b] == [1, 2]
        # The policy reorders candidates but never changes the measured volumes, distances or unshipped quantities.
        def measured(cs):
            return {(c.producer.id, c.volume, c.distance_km, c.unshipped, c.produced) for c in cs}
        assert measured(a) == measured(b)
        assert all(c.volume <= c.unmet_available for c in b)
    finally:
        store.close()


def test_selected_policy_disclosure_and_ambiguity_rejection(tmp_path):
    store = Store(tmp_path / "c.db")
    try:
        for i in range(3):
            store.add_snapshot(Snapshot(evidence(i * 1000, i + 1), source=f"f{i}"))
        m = load_file(FIXTURES / "report-policy-priorities.tf3c-methodology.json")
        lens = build_lens(store, store.latest(), m)
        for kind in ("industries", "lines-history", "bottlenecks", "expansion", "vehicle-roi"):
            md = reports.render_report(store, kind, lens=lens)
            html = reports.render_report(store, kind, lens=lens, html=True)
            assert lens.clock.time_basis["anchorHash"] in md and lens.clock.time_basis["anchorHash"] in html
            assert "Report policy" in md and "Report policy" in html
        with pytest.raises(ValueError):
            reports.render_report(store, "expansion", lens=lens, thresholds=Thresholds())
    finally:
        store.close()


def test_cli_compare_smoke(tmp_path):
    root = Path(__file__).parents[1]
    data, userdata = tmp_path / "data", tmp_path / "userdata"
    data.mkdir()
    (userdata / "towns_industries").mkdir(parents=True)
    store = Store(data / "companion.db")
    for i in range(3):
        store.add_snapshot(Snapshot(evidence(i * 1000, i + 1), source=f"fixture-{i}"))
    before = store.conn.execute("SELECT game_time, data FROM snapshots ORDER BY game_time").fetchall()
    before = [tuple(r) for r in before]
    store.close()
    env = {**os.environ, "TF3C_DATA_DIR": str(data), "TF3C_USERDATA_DIR": str(userdata)}
    def cli(*args, success=True):
        result = subprocess.run(["uv", "run", "tf3c", *map(str, args)], cwd=root, env=env, capture_output=True, text=True)
        assert (result.returncode == 0) == success, result.stdout + result.stderr
        return result
    outputs = []
    for name in ("neutral", "priorities"):
        path = FIXTURES / f"report-policy-{name}.tf3c-methodology.json"
        cli("methodology", "validate", path, "--strict")
        outputs.append(json.loads(cli("analyse", "--methodology", path, "--json").stdout))
    assert outputs[0]["timeBasis"] == outputs[1]["timeBasis"]
    manifests = sorted(data.rglob("manifest.json"))
    assert len(manifests) == 2
    contents = {p: p.read_bytes() for p in manifests}
    all_reports = {p: p.read_bytes() for p in data.rglob("*.md")}
    for p in manifests:
        payload = json.loads(p.read_text())
        assert payload["reportPolicy"]["registryVersion"] == 1
        assert payload["timeBasis"] == outputs[0]["timeBasis"]
    folders = {json.loads(p.read_text())["methodology"]["id"]: p.parent for p in manifests}
    neutral_folder = folders["report-policy-neutral"]
    priority_folder = folders["report-policy-priorities"]
    assert neutral_folder != priority_folder
    for name, folder in (("neutral", neutral_folder), ("priorities", priority_folder)):
        m = load_file(FIXTURES / f"report-policy-{name}.tf3c-methodology.json")
        manifest = json.loads((folder / "manifest.json").read_text())
        assert manifest["methodology"]["hash"] == m.short_hash
        assert manifest["reportPolicy"] == resolve_context(m).provenance()["reportPolicy"]
    first_neutral = next(row for row in (neutral_folder / "expansion.md").read_text().splitlines() if row.startswith("| 1 |"))
    first_priority = next(row for row in (priority_folder / "expansion.md").read_text().splitlines() if row.startswith("| 1 |"))
    assert "A volume" in first_neutral and "B distance" in first_priority
    def high_screen(folder):
        section = (folder / "vehicle-roi.md").read_text().split("### Sustained High Load")[1].split("### Sustained Low Load")[0]
        return any("Sampled load" in row for row in section.splitlines() if row.startswith("|"))
    assert not high_screen(neutral_folder) and high_screen(priority_folder)
    again = json.loads(cli("analyse", "--methodology", FIXTURES / "report-policy-priorities.tf3c-methodology.json", "--json").stdout)
    assert again == outputs[1]
    invalid = tmp_path / "invalid.tf3c-methodology.json"
    invalid.write_text(json.dumps({**json.loads((FIXTURES / "report-policy-priorities.tf3c-methodology.json").read_text()),
                                   "report_policies": {"expansion": {"weight_volume": 99}}}))
    cli("analyse", "--methodology", invalid, "--json", success=False)
    assert {p: p.read_bytes() for p in manifests} == contents
    assert {p: p.read_bytes() for p in all_reports} == all_reports
    conn = sqlite3.connect((data / "companion.db").as_uri() + "?mode=ro", uri=True)
    try:
        assert conn.execute("SELECT game_time, data FROM snapshots ORDER BY game_time").fetchall() == before
    finally:
        conn.close()


@pytest.mark.parametrize("profits", [[100, 100, 110, 120, 120], [-120, -120, -110, -100, -100]])
def test_line_history_relative_noise_floor_and_sufficiency(tmp_path, profits):
    def trajectory(tag, overrides, values=profits):
        store = Store(tmp_path / f"{tag}.db")
        try:
            for i, profit in enumerate(values):
                data = evidence(i * 1000, i + 1)
                data["lines"][0]["profitYear"] = profit
                store.add_snapshot(Snapshot(data, source=f"s{i}"))
            # The fixture spans four calendar months, so the shared maturity threshold is lowered below that span.
            return next(t for t in lens_view(store, "lines-history", {"mature_years": .2}, **{"lines-history": overrides}).trajectories
                        if t.name == "Sampled load")
        finally:
            store.close()

    off = {"noise_factor": 0, "floor_share": 0}
    stable = trajectory("stable", {"relative_change_ratio": .2, **off})
    improving = trajectory("improving", {"relative_change_ratio": .1, **off})
    assert stable.early == profits[0] and stable.recent == profits[-1] and stable.delta == 20
    assert stable.threshold == 24 and stable.trend_class == "stable"
    assert improving.threshold == 12 and improving.trend_class == "improving"
    # The policy moves the decision term and the class only: the measured medians and the MAD are identical.
    assert (stable.early, stable.recent, stable.delta, stable.mad, stable.k, stable.window_samples) == \
        (improving.early, improving.recent, improving.delta, improving.mad, improving.k, improving.window_samples)
    equality = trajectory("equality", {"relative_change_ratio": 1 / 6, **off})
    assert equality.threshold == 20 and equality.trend_class == "stable"
    floor = trajectory("floor", {"relative_change_ratio": 0, "noise_factor": 0, "floor_share": 1})
    assert floor.threshold == abs(profits[-1]) and floor.trend_class == "stable"
    noisy = trajectory("noisy", {"relative_change_ratio": 0, "noise_factor": 10, "floor_share": 0})
    assert noisy.threshold == noisy.mad * 10
    for tag, values in (("short", profits[:4]), ("gap", [100, None, 110, 120, 120])):
        guarded = trajectory(tag, {"relative_change_ratio": 0, **off}, values)
        assert guarded.trend_class == "insufficient data"


def bottleneck_store(tmp_path, tag, loads=None, stock_counts=None):
    """Five monthly samples of the fixture company; `loads` overrides the line's used capacity per sample (percent)."""
    store = Store(tmp_path / f"{tag}.db")
    for i in range(5):
        data = evidence(i * 1000, i + 1)
        if loads is not None:
            data["lines"][0]["capacity"][0]["used"] = loads[i]
        if stock_counts is not None:
            data["industries"][0]["outputs"][0]["shippedYear"] = 60
            data["stocks"] = [{"kind": "industry", "owner": 1, "stockId": 1, "ownerName": "Measured stock",
                               "cargos": [3], "count": stock_counts[i], "capacity": 100}]
        store.add_snapshot(Snapshot(data, source=f"s{i}"))
    return store


def test_bottleneck_persistence_share_and_resolved_evidence(tmp_path):
    store = bottleneck_store(tmp_path, "persist", loads=[50, 50, 95, 95, 95])
    try:
        def load_items(**policy):
            v = lens_view(store, "bottlenecks", bottlenecks=policy)
            return [i for i in v.items if i.code == "line_load_high"]
        (item,) = load_items(noisy_min_share=.6)
        assert (item.status, item.observations, item.eligible, item.streak, item.in_latest) == ("persistent", 3, 5, 3, True)
        assert not load_items(noisy_min_share=.61)
        assert not load_items(persistence_streak=4)
    finally:
        store.close()
    # Once the condition clears, a noisy family with two sightings stays below the hard three-sighting safeguard.
    resolved = bottleneck_store(tmp_path, "resolved", loads=[50, 50, 95, 95, 50])
    try:
        v = lens_view(resolved, "bottlenecks", bottlenecks={"noisy_min_share": .4})
        assert not [i for i in v.items if i.code == "line_load_high"]
    finally:
        resolved.close()


def test_rising_stock_exact_boundaries_and_empty_interval(tmp_path):
    store = Store(tmp_path / "rising.db")
    for i, count in enumerate((46, 48, 50)):
        data = evidence(i * 1000, i + 1)
        data["industries"][0]["outputs"][0]["shippedYear"] = 60
        data["stocks"] = [{"kind": "industry", "owner": 1, "stockId": 1, "ownerName": "Measured stock",
                           "cargos": [3], "count": count, "capacity": 100}]
        store.add_snapshot(Snapshot(data, source=f"s{i}"))
    try:
        base = view(store, "bottlenecks")
        (rise,) = base.stock_rises
        assert (rise.name, rise.count_start, rise.count_latest, rise.capacity, rise.fill) == ("Measured stock", 46, 50, 100, .5)
        assert rise.slope_per_sample == pytest.approx(2) and rise.samples_to_full == pytest.approx(25)
        assert not base.rising_interval_empty
        # A minimum fill or slope just above the measurement excludes the rise; the measured stock itself is unchanged.
        assert not lens_view(store, "bottlenecks", bottlenecks={"rising_stock_min_fill": .51}).stock_rises
        assert not lens_view(store, "bottlenecks", bottlenecks={"rising_stock_min_slope": .021}).stock_rises
        (kept,) = lens_view(store, "bottlenecks", bottlenecks={"rising_stock_min_fill": .5, "rising_stock_min_slope": .02}).stock_rises
        assert (kept.count_latest, kept.slope_per_sample, kept.fill) == (50, rise.slope_per_sample, .5)
        # A shared full-stock ratio at the measured fill leaves no rising interval; it is disclosed rather than silently empty.
        at_fill = view(store, "bottlenecks", Thresholds(full_stock_ratio=.5))
        assert not at_fill.stock_rises and at_fill.rising_interval_empty
        assert view(store, "bottlenecks", Thresholds(full_stock_ratio=.45)).rising_interval_empty
        blocks = document(store, "bottlenecks", Thresholds(full_stock_ratio=.45)).blocks
        assert any(isinstance(b, reports.Note) and b.label == "Effective criteria" for b in blocks)
    finally:
        store.close()


def test_roi_effective_fit_threshold_and_sample_guard(tmp_path):
    store = Store(tmp_path / "roi.db")
    try:
        for i in range(3):
            store.add_snapshot(Snapshot(evidence(i * 1000, i + 1), source=f"s{i}"))
        base = view(store, "vehicle-roi")
        assert not base.high_load and not base.low_load  # default overloaded_load .9 vs a .85 median
        (fit,) = view(store, "vehicle-roi", Thresholds(overloaded_load=.8)).high_load
        assert (fit.line, fit.vehicles, fit.load_median, fit.load_samples) == ("Sampled load", 2, .85, 3)
        # The threshold is inclusive at the measured median and exclusive above it; the load measurement is unchanged.
        (at_median,) = view(store, "vehicle-roi", Thresholds(overloaded_load=.85)).high_load
        assert at_median.load_median == fit.load_median
        assert not view(store, "vehicle-roi", Thresholds(overloaded_load=.86)).high_load
        assert not view(store, "vehicle-roi", Thresholds(overloaded_load=.8, underused_min_vehicles=3)).high_load
        # Document membership follows the view.
        blocks = document(store, "vehicle-roi", Thresholds(overloaded_load=.8)).blocks
        assert any(isinstance(b, reports.Heading) and b.text == "Sustained High Load (Possible Undersizing)" for b in blocks)
    finally:
        store.close()
    short = Store(tmp_path / "short.db")
    try:
        for i in range(2):
            short.add_snapshot(Snapshot(evidence(i * 1000, i + 1), source=f"s{i}"))
        assert not view(short, "vehicle-roi", Thresholds(overloaded_load=.8)).high_load
    finally:
        short.close()


def test_industries_capacity_decline_and_shared_fullness_boundaries(tmp_path):
    from test_report_industries import industry as ind_fixture

    def build(tag, capacity=100):
        store = Store(tmp_path / f"{tag}.db")
        for tick, month, produced in ((1000, 1, 120), (2000, 2, 90)):
            data = evidence(tick, month)
            ind = ind_fixture(produced=produced, shipped=10)
            ind["inputs"] = [{"cargo": 4, "consumedYear": 100, "deliveredYear": 100, "maxConsumptionYear": 100}]
            ind["outputs"][0]["maxProductionYear"] = capacity
            data["industries"] = [ind]
            data["stocks"] = [{"kind": "industry", "owner": 10, "stockId": 1, "cargos": [3], "count": 80, "capacity": 100}]
            store.add_snapshot(Snapshot(data, source=f"s{tick}"))
        return store

    full = {"full_stock_ratio": .75}
    store = build("decline")
    try:
        def status(thresholds=None, **policy):
            return [s.status for s in lens_view(
                    store, "industries", thresholds, industries=policy).chains.consumer_statuses]
        # 90 of 100 is not below the default capacity ratio, and the stock is not full at the default fullness.
        assert "output-stock-full" not in status(full)
        assert "output-stock-full" not in status(None, below_capacity_ratio=.95)
        # Both the shared fullness threshold and the capacity-ratio policy are needed.
        assert status(full, below_capacity_ratio=.95) == ["output-stock-full"]
        def measured(thresholds, **policy):
            return lens_view(store, "industries", thresholds, industries=policy).comparison.full_outputs_last
        assert measured(full, below_capacity_ratio=.95) == measured(full) == 1  # raw fullness count is unchanged by the ratio
        # The decline minimum selects the manual-review row at exactly the 30-unit decline and drops it just above.
        for minimum, expected in ((30, True), (31, False)):
            v = lens_view(store, "industries", industries={"production_decline_min": minimum})
            assert ("production-decline" in [m.code for m in v.manual_review]) is expected
            if expected:
                assert next(m for m in v.manual_review if m.code == "production-decline").decline == 30
        doc_rows = [r for b in lens_document(store, "industries", full, industries={"below_capacity_ratio": .95}).blocks
                    if isinstance(b, reports.Table) and "Status" in b.columns for r in b.rows]
        assert [r[2] for r in doc_rows] == ["Output stock full, output below capacity"]
    finally:
        store.close()
    zero = build("zero", capacity=0)
    try:
        assert "output-stock-full" not in [s.status for s in lens_view(
            zero, "industries", full, industries={"below_capacity_ratio": .95}).chains.consumer_statuses]
    finally:
        zero.close()


def test_engine_fullness_and_unshipped_reach_expansion_and_bottlenecks(tmp_path):
    store = Store(tmp_path / "full.db")
    try:
        data = evidence()
        data["stocks"] = [{"kind": "industry", "owner": 2, "stockId": 1, "cargos": [3], "count": 80, "capacity": 100}]
        store.add_snapshot(Snapshot(data))
        full = view(store, "expansion", Thresholds(full_stock_ratio=.75))
        assert full.full_stock_ratio == .75
        producer = next(c for c in full.candidates if c.producer.id == 1)
        assert any(p.code == "consumer_input_stock_full" and p.amount == 15 for p in producer.penalties)
        assert not any(p.code == "consumer_input_stock_full" for p in next(c for c in view(store, "expansion").candidates
                                                                         if c.producer.id == 1).penalties)
        data["industries"][0]["outputs"][0]["shippedYear"] = 90  # ratio .6
        store.add_snapshot(Snapshot(data))
        neutral = view(store, "expansion")
        changed = view(store, "expansion", Thresholds(unshipped_ratio=.7))
        assert 1 not in {c.producer.id for c in neutral.candidates}
        assert 1 in {c.producer.id for c in changed.candidates}
        assert changed.unshipped_ratio_limit == .7 and neutral.unshipped_ratio_limit == .5
        assert next(c for c in changed.candidates if c.producer.id == 1).ratio == pytest.approx(.6)
    finally:
        store.close()


def test_no_lens_default_and_empty_policy_are_analytically_equivalent_and_read_only(tmp_path):
    from tf3companion.methodology import load_default
    kinds = ("industries", "lines-history", "bottlenecks", "expansion", "vehicle-roi")
    store = Store(tmp_path / "equiv.db")
    try:
        for i in range(4):
            store.add_snapshot(Snapshot(evidence(i * 1000, i + 1), source=f"fixture-{i}"))
        def rows():
            return [tuple(r) for r in store.conn.execute("SELECT game_time, data FROM snapshots ORDER BY game_time")]
        before = rows()
        lenses = {"packaged default": build_lens(store, store.latest(), load_default()),
                  "empty policy": build_lens(store, store.latest(), methodology(report_policies={}))}

        def analytic(doc, header_len):
            # Drop only the disclosure: lens header rows and the trailing "Report policy" heading + criteria table.
            assert isinstance(doc.blocks[-2], reports.Heading) and doc.blocks[-2].text == "Report policy"
            return doc.header[:header_len], doc.blocks[:-2]

        for kind in kinds:
            baseline_doc = reports.compose_report(store, kind)
            header_len = len(baseline_doc.header)
            expected = analytic(baseline_doc, header_len)
            assert len(expected[1]) > 3  # a real report, not an empty comparison
            for name, lens in lenses.items():
                doc = reports.compose_report(store, kind, lens=lens)
                assert analytic(doc, header_len) == expected, f"{kind} differs for {name}"
                assert reports.render_markdown(doc) and reports.render_html(doc)
        changed = reports.compose_report(store, "expansion", lens=build_lens(
            store, store.latest(), load_file(FIXTURES / "report-policy-priorities.tf3c-methodology.json")))
        assert analytic(changed, len(reports.compose_report(store, "expansion").header)) != \
            analytic(reports.compose_report(store, "expansion"), len(reports.compose_report(store, "expansion").header))
        assert rows() == before
    finally:
        store.close()
