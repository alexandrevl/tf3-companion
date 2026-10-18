"""Engine integration: thresholds, finding overrides, default equivalence and provenance."""
from __future__ import annotations

import copy
import json

import pytest

from conftest import YEAR
from methodology_helpers import Net, cond, companion_with, methodology, troubled_company
from tf3companion import analysis
from tf3companion.methodology import load_default, parse
from tf3companion.methodology.engine import thresholds_for
from tf3companion.snapshot import Snapshot

ENGINE_KEYS = ("code", "severity", "category", "title", "detail", "suggestion", "entity", "evidence")


def comparable(finding):
    data = finding.to_dict() if hasattr(finding, "to_dict") else finding
    return {k: data[k] for k in ENGINE_KEYS}


def test_default_equivalence_with_the_engine_without_a_methodology():
    snap, prev = Snapshot(troubled_company()), Snapshot(copy.deepcopy(troubled_company()))
    prev.raw["meta"]["gameTime"] -= YEAR // 12
    prev.raw["lines"][2]["profitYear"] = 900_000  # makes line 102 a "profit dropping" finding
    before = [comparable(f) for f in analysis.findings(snap, prev)]
    default = load_default()
    after = analysis.findings(snap, prev, methodology=default)
    assert [comparable(f) for f in after] == before
    assert {f.code for f in after} >= {"line_losing_money", "line_overloaded", "line_underused", "line_config_issue",
                                         "line_no_vehicles", "vehicle_no_path", "fleet_idle_in_depot", "industry_closing",
                                         "snapshot_collection_errors", "line_profit_dropping"}
    assert all(f.source == "engine" and f.methodology == "default@1.0.0" for f in after)
    assert thresholds_for(default) == analysis.Thresholds()


def test_default_equivalence_through_the_service(paths):
    companion = companion_with(paths, troubled_company())
    try:
        snap = companion.current()
        expected = [comparable(f) for f in analysis.findings(snap, None)]
        got = companion.findings()
        assert [comparable(f) for f in got] == expected
        assert {f["methodology"] for f in got} == {"default@1.0.0"}
        assert all(f["methodology_hash"] == load_default().short_hash and f["source"] == "engine" for f in got)
    finally:
        companion.close()


def test_threshold_override_changes_maturity_dependent_findings():
    data = Net().station(1, "A", 10, "Alpha").station(2, "B", 20, "Beta").line(100, "Loser", [1, 2], profit=-9_000, age=2).data
    snap = Snapshot(data)
    default = [f for f in analysis.findings(snap, methodology=load_default()) if f.code == "line_losing_money"]
    assert [f.severity for f in default] == ["high"]
    patient = methodology(engine={"thresholds": {"mature_years": 3}})
    patient_findings = [f for f in analysis.findings(snap, methodology=patient) if f.code == "line_losing_money"]
    assert [f.severity for f in patient_findings] == ["low"]  # a 2-year-old line is still maturing under 3 years
    assert thresholds_for(patient).mature_years == 3
    assert analysis.findings(snap, t=analysis.Thresholds(mature_years=1.0), methodology=patient)[0].methodology == "test@1.0.0"


def two_role_net() -> Net:
    net = Net().station(1, "A", 10, "Alpha").station(2, "B", 20, "Beta")
    net.line(100, "Local one", [1, 1], profit=-70_000).line(101, "Trunk one", [1, 2], profit=-80_000)
    net.line(102, "Odd", [1, 2], profit=-90_000, cargo=4)
    return net


def role_override_methodology(**engine):
    return methodology(
        roles={"line": [{"id": "local", "select": {"all": [cond("line.is_passenger_only", "eq", True), cond("line.town_count", "le", 1)]}},
                        {"id": "trunk", "select": {"all": [cond("line.is_passenger_only", "eq", True)]}}]},
        engine=engine)


def test_silencing_a_code_for_one_role_only():
    snap = two_role_net().snapshot()
    m = role_override_methodology(findings=[{"code": "line_losing_money", "role": "local", "action": "off"}])
    found = {f.entity["name"] for f in analysis.findings(snap, methodology=m) if f.code == "line_losing_money"}
    assert found == {"Trunk one", "Odd"}  # the unclassified freight line keeps the engine finding
    verdicts_off = analysis.findings(snap, methodology=m)
    assert all(f.code != "line_losing_money" or f.entity["name"] != "Local one" for f in verdicts_off)


def test_set_severity_override_and_the_disabled_list():
    from tf3companion.methodology import evaluate

    snap = two_role_net().snapshot()
    m = role_override_methodology(findings=[{"code": "line_losing_money", "role": "trunk", "action": "set_severity", "severity": "low"},
                                            {"code": "line_losing_money", "role": "local", "action": "off"}])
    verdicts = evaluate(m, snap)
    found = analysis.findings(snap, methodology=m, verdicts=verdicts)
    severities = {f.entity["name"]: f.severity for f in found if f.code == "line_losing_money"}
    assert severities == {"Trunk one": "low", "Odd": "high"}
    assert verdicts.disabled_findings == [{"code": "line_losing_money", "role": "local", "suppressed": 1}]


def test_unknown_threshold_or_code_is_rejected_when_loading():
    from tf3companion.methodology import MethodologyError

    with pytest.raises(MethodologyError, match="unknown threshold"):
        methodology(engine={"thresholds": {"mature_year": 3}})
    with pytest.raises(MethodologyError, match="unknown finding code"):
        methodology(engine={"findings": [{"code": "nope", "action": "off"}]})


def test_every_engine_finding_code_is_registered():
    """FINDING_CODES must list every code `analysis` can emit, or overrides could not name it."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(analysis))
    emitted = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "Finding" and node.args:
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                emitted.add(first.value)
        if isinstance(node, ast.Dict):  # the stock-code table
            emitted |= {v.value for v in node.values if isinstance(v, ast.Constant) and isinstance(v.value, str) and v.value.endswith(("_full", "_full_unserved"))}
    emitted |= {"line_load_persistently_high", "line_load_persistently_low"}
    emitted |= {"line_orphan", "line_no_vehicles", "line_no_stops"}  # chosen through a variable in _line_findings
    assert emitted <= set(analysis.FINDING_CODES), emitted - set(analysis.FINDING_CODES)
    assert set(analysis.FINDING_CODES) - emitted == set(), set(analysis.FINDING_CODES) - emitted


def test_editing_a_file_without_a_version_bump_changes_the_recorded_hash():
    base = {"schema": "tf3c-methodology/1", "id": "edit", "version": "1.0.0", "name": "N", "description": "D"}
    first = parse(json.dumps(base).encode())
    second = parse(json.dumps({**base, "description": "D, edited"}).encode())
    assert first.identity == second.identity and first.short_hash != second.short_hash


def test_findings_carry_the_hash_and_methodology_findings_the_source(paths):
    m = methodology(rules=[{"id": "loss", "entity": "line", "outcomes": [
        {"when": cond("line.profit_year", "lt", -100_000), "marker": "problem", "message": "{line.name} loses a lot"}]}])
    snap = Snapshot(troubled_company())
    found = analysis.findings(snap, methodology=m)
    engine = [f for f in found if f.source == "engine"]
    own = [f for f in found if f.source == "methodology"]
    assert own and {f.code for f in own} == {"rule:loss"}
    assert {f.methodology_hash for f in found} == {m.short_hash}
    assert engine and own[0].detail == "Mature loser loses a lot"
    assert own[0].suggestion.startswith("Review the evidence")  # rule prose never becomes a free instruction
