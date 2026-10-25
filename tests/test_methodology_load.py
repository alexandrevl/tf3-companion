"""Loader, structural validator and bounded regular expressions."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from tf3companion.methodology import MethodologyError, load_default, load_file, parse
from tf3companion.methodology.model import MAX_BYTES, MAX_DEPTH, MAX_RULES
from tf3companion.methodology.safe_regex import bounded_search, check_pattern

EXAMPLES = Path(__file__).parent.parent / "src" / "tf3companion" / "methodology" / "examples"
AUTHOR_PATTERN = r"^(?P<mode>\S+) .*?-(?P<scope>LO|IC|RE)-(?P<n>\d+)$"

BASE = {
    "schema": "tf3c-methodology/1",
    "id": "demo",
    "version": "1.0.0",
    "name": "Demo",
    "description": "A demo.",
    "parameters": {"limit": {"value": 10}},
    "markers": {"ok": {"label": "ok"}, "bad": {"label": "bad", "finding": "high"}},
    "roles": {"line": [{"id": "freight", "select": {"field": "line.is_passenger_only", "op": "eq", "value": False}}]},
    "rules": [
        {
            "id": "r1",
            "entity": "line",
            "role": "freight",
            "outcomes": [
                {"when": {"field": "line.profit_year", "op": "lt", "value": {"param": "limit"}}, "marker": "bad"}
            ],
            "default": {"marker": "ok"},
        }
    ],
}


def doc(**changes):
    out = copy.deepcopy(BASE)
    out.update(changes)
    return out


def load(data) -> object:
    return parse(json.dumps(data).encode("utf-8"))


def errors(data) -> str:
    with pytest.raises(MethodologyError) as info:
        load(data)
    return str(info.value)


def test_valid_file_is_accepted_with_identity_and_hash():
    m = load(BASE)
    assert m.identity == "demo@1.0.0" and m.short_hash.startswith("sha256:") and len(m.sha256) == 64


def test_packaged_default_and_example_load():
    assert load_default().id == "default"
    example = load_file(EXAMPLES / "local-feeder-intercity-trunk.tf3c-methodology.json")
    assert example.identity == "local-feeder-intercity-trunk@1.0.0"


def test_unknown_structural_key_names_rule_and_key():
    data = doc()
    data["rules"][0]["outcome"] = data["rules"][0].pop("outcomes")
    message = errors(data)
    assert "outcome" in message and "outcomes" in message and "r1" in message


def test_wrong_types_are_errors():
    assert "must be a string" in errors(doc(name=5))
    assert "must be a three-part number" in errors(doc(version=3))
    assert "list" in errors(doc(rules={"a": 1}))


@pytest.mark.parametrize(
    "change, fragment",
    [
        (lambda d: d["rules"][0]["outcomes"][0]["when"].__setitem__("value", {"param": "nope"}), "undefined parameter"),
        (lambda d: d["rules"][0].__setitem__("role", "ghost"), "not defined for line roles"),
        (lambda d: d["rules"][0]["outcomes"][0].__setitem__("marker", "ghost"), "undefined marker"),
        (lambda d: d["rules"][0]["outcomes"][0].__setitem__("when", {"ref": "ghost"}), "undefined definition"),
    ],
)
def test_undefined_references_are_errors(change, fragment):
    data = doc()
    change(data)
    assert fragment in errors(data)


def test_duplicate_ids_are_errors():
    data = doc()
    data["rules"].append(copy.deepcopy(data["rules"][0]))
    assert "duplicate rule id 'r1'" in errors(data)
    data = doc()
    data["roles"]["line"].append(copy.deepcopy(data["roles"]["line"][0]))
    assert "duplicate role id" in errors(data)


def test_duplicate_json_keys_are_rejected():
    raw = b'{"schema": "tf3c-methodology/1", "id": "a", "id": "b", "version": "1.0.0", "name": "n", "description": "d"}'
    with pytest.raises(MethodologyError, match="duplicate key"):
        parse(raw)


def test_cyclic_ref_is_an_error():
    data = doc(definitions={"a": {"ref": "b"}, "b": {"ref": "a"}})
    assert "cyclic reference" in errors(data)


@pytest.mark.parametrize(
    "field, value", [("id", "../../x"), ("id", "Upper"), ("id", "a" * 70), ("version", "1.0/evil"), ("version", "1.0")]
)
def test_path_unsafe_identity_names_the_field(field, value):
    message = errors(doc(**{field: value}))
    assert f"/{field}" in message


def test_unsupported_schema_version_states_declared_and_supported():
    message = errors(doc(schema="tf3c-methodology/2"))
    assert "tf3c-methodology/2" in message and "tf3c-methodology/1" in message and "No rule was evaluated" in message


def test_size_limit_applies_before_parsing():
    with pytest.raises(MethodologyError, match="the limit is"):
        parse(b" " * (MAX_BYTES + 1))


def test_rule_count_limit():
    data = doc(
        rules=[
            {
                "id": f"r{i}",
                "entity": "line",
                "outcomes": [{"when": {"field": "line.profit_year", "op": "lt", "value": 0}, "marker": "ok"}],
            }
            for i in range(MAX_RULES + 1)
        ]
    )
    assert "the limit is 200" in errors(data)


def test_condition_depth_limit():
    node = {"field": "line.profit_year", "op": "lt", "value": 0}
    for _ in range(MAX_DEPTH + 2):
        node = {"not": node}
    data = doc()
    data["rules"][0]["outcomes"][0]["when"] = node
    assert "nesting exceeds" in errors(data)


def test_text_length_limit():
    assert "the limit is 2000" in errors(doc(description="x" * 2001))


def test_aggregate_outcomes_cannot_read_member_fields():
    data = doc()
    data["rules"] = [
        {
            "id": "agg",
            "entity": "line",
            "aggregate": {
                "group_by": "town",
                "measures": {"n": {"agg": "count", "via": "line.first_stop_town"}},
                "outcomes": [{"when": {"field": "line.profit_year", "op": "lt", "value": 0}, "marker": "ok"}],
            },
        }
    ]
    assert "read measures" in errors(data)


def test_town_grouping_requires_via():
    data = doc()
    data["rules"] = [
        {
            "id": "agg",
            "entity": "line",
            "aggregate": {
                "group_by": "town",
                "measures": {"n": {"agg": "count"}},
                "outcomes": [{"when": {"measure": "n", "op": "gt", "value": 0}, "marker": "ok"}],
            },
        }
    ]
    assert "needs a 'via'" in errors(data)


def test_engine_overrides_reject_unknown_names():
    assert "unknown threshold" in errors(doc(engine={"thresholds": {"mature_year": 3}}))
    assert "unknown finding code" in errors(doc(engine={"findings": [{"code": "line_losing_mony", "action": "off"}]}))
    assert "not defined for line roles" in errors(
        doc(engine={"findings": [{"code": "line_losing_money", "role": "ghost", "action": "off"}]})
    )
    assert "set_severity requires severity" in errors(
        doc(engine={"findings": [{"code": "line_losing_money", "action": "set_severity"}]})
    )


def test_unknown_report_kind_lists_valid_kinds():
    message = errors(doc(reports={"kinds": ["company", "nonsense"]}))
    assert "unknown report kind 'nonsense'" in message and "bottlenecks" in message


def test_template_placeholder_validation():
    data = doc()
    data["rules"][0]["outcomes"][0]["message"] = "{line.name|bogus}"
    assert "unknown format" in errors(data)
    data["rules"][0]["outcomes"][0]["message"] = "{param.ghost}"
    assert "undefined parameter" in errors(data)
    data["rules"][0]["outcomes"][0]["message"] = "{group}"
    assert "only in aggregate" in errors(data)
    data["rules"][0]["outcomes"][0]["message"] = "{vehicle.name}"
    assert "belongs to vehicle" in errors(data)
    data["rules"][0]["outcomes"][0]["message"] = "{line.name"
    assert "malformed placeholder" in errors(data)


def test_unknown_field_does_not_invalidate_the_file():
    data = doc()
    data["rules"][0]["outcomes"][0]["when"] = {"field": "line.profit_yeer", "op": "lt", "value": 0}
    assert load(data).id == "demo"


def test_undeclared_name_capture_is_an_error():
    data = doc()
    data["rules"][0]["outcomes"][0]["when"] = {"field": "line.name_capture.mode", "op": "eq", "value": "Bus"}
    assert "not declared by any name pattern" in errors(data)


# ---- bounded regular expressions ------------------------------------------------------


def test_author_name_pattern_is_accepted_and_matches():
    assert check_pattern(AUTHOR_PATTERN) is None
    match = bounded_search(AUTHOR_PATTERN, "Bus Passengers-Mon-LO-4")
    assert match and match.group("scope") == "LO" and match.group("n") == "4"


@pytest.mark.parametrize(
    "pattern, fragment",
    [
        ("(a+)+$", "quantifier"),
        ("(a*)*", "quantifier"),
        ("(a|aa)+", "alternation"),
        (r"(a)\1", "backreferences"),
        ("(?=a)a", "lookahead"),
        ("(?<=a)b", "lookahead"),
        ("a" * 201, "limit is 200"),
        ("a+b+c+d+", "unbounded"),
        ("(unclosed", "invalid regular expression"),
    ],
)
def test_unsafe_patterns_are_rejected(pattern, fragment):
    assert fragment in check_pattern(pattern)


def test_unsafe_pattern_in_file_is_rejected_at_load():
    data = doc(name_patterns={"line": [{"id": "bad", "pattern": "(a+)+$"}]})
    assert "quantified group" in errors(data)


def test_subjects_are_truncated_before_matching():
    subject = "a" * 100_000 + "b"
    assert bounded_search("^a+$", subject) is not None  # only the first 200 characters are examined
    assert bounded_search("b$", subject) is None
