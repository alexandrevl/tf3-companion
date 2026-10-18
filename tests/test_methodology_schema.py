"""The published JSON Schema and the in-repo validator must agree on structure."""
from __future__ import annotations

import copy
import json
from importlib.resources import files
from pathlib import Path

import jsonschema
import pytest

from tf3companion.methodology import MethodologyError, parse
from tf3companion.methodology.loader import schema_text

PACKAGE = files("tf3companion.methodology")
FIXTURES = Path(__file__).parent / "fixtures" / "methodologies"
EXAMPLE = json.loads(PACKAGE.joinpath("examples", "local-feeder-intercity-trunk.tf3c-methodology.json").read_text(encoding="utf-8"))
SCHEMA = json.loads(schema_text())
VALIDATOR = jsonschema.Draft202012Validator(SCHEMA)


def schema_accepts(data) -> bool:
    return VALIDATOR.is_valid(data)


def validator_accepts(data) -> bool:
    try:
        parse(json.dumps(data).encode("utf-8"))
    except MethodologyError:
        return False
    return True


def mutated(change):
    data = copy.deepcopy(EXAMPLE)
    change(data)
    return data


def test_the_schema_itself_is_valid_draft_2020_12():
    jsonschema.Draft202012Validator.check_schema(SCHEMA)


VALID = {
    "default": json.loads(PACKAGE.joinpath("default.json").read_text(encoding="utf-8")),
    "example": EXAMPLE,
    "oil": json.loads((FIXTURES / "oil-chemicals-chain.tf3c-methodology.json").read_text(encoding="utf-8")),
    "ladder": json.loads((FIXTURES / "mode-ladder.tf3c-methodology.json").read_text(encoding="utf-8")),
}

# Structural mistakes: both the schema and the validator must reject them.
STRUCTURAL = {
    "unknown top-level key": lambda d: d.update(bogus=1),
    "missing description": lambda d: d.pop("description"),
    "name has wrong type": lambda d: d.update(name=3),
    "version not three parts": lambda d: d.update(version="1.0"),
    "path-unsafe id": lambda d: d.update(id="../../x"),
    "unsupported schema id": lambda d: d.update(schema="tf3c-methodology/2"),
    "parameter without value": lambda d: d["parameters"]["high_load"].pop("value"),
    "parameter value of wrong type": lambda d: d["parameters"]["high_load"].update(value=[1]),
    "marker finding not a severity": lambda d: d["markers"]["watch"].update(finding="critical"),
    "marker missing label": lambda d: d["markers"]["watch"].pop("label"),
    "rule key typo": lambda d: d["rules"][0].update(outcome=d["rules"][0].pop("outcomes")),
    "rule without entity": lambda d: d["rules"][0].pop("entity"),
    "unknown operator": lambda d: d["rules"][0]["outcomes"][0]["when"].update(op="roughly"),
    "comparison without value": lambda d: d["rules"][0]["outcomes"][0]["when"].pop("value"),
    "exists with a value": lambda d: d["rules"][0]["outcomes"][0].update(when={"field": "line.name", "op": "exists", "value": 1}),
    "condition with field and measure": lambda d: d["rules"][0]["outcomes"][0].update(
        when={"field": "line.name", "measure": "x", "op": "exists"}),
    "empty all": lambda d: d["rules"][0]["outcomes"][0].update(when={"all": []}),
    "field name not a path": lambda d: d["rules"][0]["outcomes"][0]["when"].update(field="profit"),
    "outcomes empty": lambda d: d["rules"][0].update(outcomes=[]),
    "aggregate measure without value": lambda d: d["rules"][5]["aggregate"]["measures"]["local_result"].pop("value"),
    "aggregate agg unknown": lambda d: d["rules"][5]["aggregate"]["measures"]["local_lines"].update(agg="median"),
    "ratio side without measure": lambda d: d["rules"][5]["aggregate"]["measures"]["feeder_cost_ratio"]["numerator"].pop("measure"),
    "recommendation priority out of range": lambda d: d["recommendations"][0].update(priority=9),
    "recommendation without text": lambda d: d["recommendations"][0].pop("text"),
    "report chart type unknown": lambda d: d.update(reports={"charts": [{"id": "c", "type": "radar", "entity": "line", "agg": "count"}]}),
    "role without select": lambda d: d["roles"]["line"][0].pop("select"),
    "roles for an unknown entity": lambda d: d["roles"].update(station=[]),
    "engine override without action": lambda d: d["engine"]["findings"][0].pop("action"),
    "set_severity without severity": lambda d: d["engine"]["findings"][0].update(action="set_severity"),
    "negative threshold": lambda d: d.update(engine={"thresholds": {"mature_years": -1}}),
    "ladder entity not line": lambda d: d.update(ladders=[{"id": "l", "entity": "vehicle", "metric": "line.route_km",
                                                          "bands": [{"mode": "AIR"}], "text": "t"}]),
    "ladder band mode unknown": lambda d: d.update(ladders=[{"id": "l", "entity": "line", "metric": "line.route_km",
                                                            "bands": [{"mode": "ROCKET"}], "text": "t"}]),
    "description too long": lambda d: d.update(description="x" * 2001),
}

# Cross-reference or semantic mistakes only the validator can see; the schema documents that it cannot.
VALIDATOR_ONLY = {
    "undefined parameter": lambda d: d["rules"][0]["outcomes"][0]["when"].update(value={"param": "ghost"}),
    "undefined marker": lambda d: d["rules"][0]["outcomes"][0].update(marker="ghost"),
    "undefined role": lambda d: d["rules"][0].update(role="ghost"),
    "undefined definition": lambda d: d["rules"][0]["outcomes"][0].update(when={"ref": "ghost"}),
    "unknown threshold name": lambda d: d.update(engine={"thresholds": {"mature_year": 3}}),
    "unknown finding code": lambda d: d["engine"]["findings"][0].update(code="line_losing_mony"),
    "unknown report kind": lambda d: d.update(reports={"kinds": ["nonsense"]}),
    "unsafe regular expression": lambda d: d.update(name_patterns={"line": [{"id": "x", "pattern": "(a+)+$"}]}),
}


@pytest.mark.parametrize("name", sorted(VALID))
def test_valid_documents_are_accepted_by_both(name):
    assert schema_accepts(VALID[name]) and validator_accepts(VALID[name])


@pytest.mark.parametrize("name", sorted(STRUCTURAL))
def test_structural_mistakes_are_rejected_by_both(name):
    data = mutated(STRUCTURAL[name])
    assert not schema_accepts(data), "the schema should reject this"
    assert not validator_accepts(data), "the validator should reject this"


@pytest.mark.parametrize("name", sorted(VALIDATOR_ONLY))
def test_cross_reference_mistakes_are_caught_only_by_the_validator(name):
    data = mutated(VALIDATOR_ONLY[name])
    assert schema_accepts(data)
    assert not validator_accepts(data)


# report_policies: structural and range rules must agree between schema and runtime validator.
# Cross-field rules (weight total, distance ordering) are runtime-only by design.
def _with_policies(policies):
    data = copy.deepcopy(VALID["default"])
    data["report_policies"] = policies
    return data


def _policy_cases():
    from tf3companion.report_policy import REGISTRY
    valid, invalid = [], []
    for family, entries in REGISTRY.items():
        valid.append((f"{family} empty", {family: {}}))
        for key, spec in entries.items():
            cross_field = key.startswith("weight_") or key.startswith("distance_") and key.endswith("_km")
            good = [spec.default] if cross_field else [spec.default, spec.maximum]
            if not cross_field:
                good.append(spec.minimum if not spec.exclusive_minimum else spec.default / 2)
            for value in good:
                value = int(value) if spec.integer else value
                valid.append((f"{family}.{key}={value}", {family: {key: value}}))
            bad = [spec.maximum + 1, "1", True, None, [1], {"v": 1}]
            bad.append(spec.minimum if spec.exclusive_minimum else spec.minimum - 1)
            if spec.integer:
                bad.append(spec.default + 0.5)
            for value in bad:
                invalid.append((f"{family}.{key}={value!r}", {family: {key: value}}))
            invalid.append((f"{family}.{key} sibling unknown", {family: {key: spec.default, "ghost": 1}}))
    invalid += [("unknown family", {"ghost": {}}), ("family not object", {"bottlenecks": 3}),
                ("policies not object", [])]
    return valid, invalid


_VALID_POLICIES, _INVALID_POLICIES = _policy_cases()


@pytest.mark.parametrize("name,policies", _VALID_POLICIES, ids=[n for n, _ in _VALID_POLICIES])
def test_report_policies_valid_values_accepted_by_both(name, policies):
    data = _with_policies(policies)
    assert schema_accepts(data) and validator_accepts(data)


@pytest.mark.parametrize("name,policies", _INVALID_POLICIES, ids=[n for n, _ in _INVALID_POLICIES])
def test_report_policies_structural_and_range_errors_rejected_by_both(name, policies):
    data = _with_policies(policies)
    assert not schema_accepts(data), "the schema should reject this"
    assert not validator_accepts(data), "the validator should reject this"


def test_report_policies_cross_field_rules_are_runtime_only():
    for policies in ({"expansion": {"weight_volume": 29}},
                     {"expansion": {"distance_short_km": 3}}):
        data = _with_policies(policies)
        assert schema_accepts(data)
        assert not validator_accepts(data)
