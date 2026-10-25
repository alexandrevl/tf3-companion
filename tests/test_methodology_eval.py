"""Evaluator: three-valued logic, availability, roles, rules, aggregates, recommendations and ladders."""

from __future__ import annotations

import itertools
from dataclasses import replace
from pathlib import Path

import pytest

from methodology_helpers import FREIGHT, Net, cond, markers_of, methodology, rule, run
from tf3companion.methodology import MethodologyError, fields, load_file
from tf3companion.methodology.conditions import compare, first_true
from tf3companion.methodology.conditions import evaluate as eval_condition
from tf3companion.methodology.prepare import inspect

FIXTURES = Path(__file__).parent / "fixtures" / "methodologies"
T, F_, U = True, False, None


@pytest.fixture
def geometry_capability(monkeypatch):
    """Exercise evaluator geometry with an explicitly supported hypothetical collector capability."""
    name = "line.route_km"
    monkeypatch.setitem(fields._REGISTRY, name, replace(fields.lookup(name), collected=True))


def test_current_release_rejects_geometry_even_if_a_draft_snapshot_contains_positions():
    m = load_file(FIXTURES / "mode-ladder.tf3c-methodology.json")
    with pytest.raises(MethodologyError) as error:
        run(m, ladder_net(95, "ROAD"))
    assert any(
        issue.category == "unsupported-capability" and issue.itemId == "mode-by-distance"
        for issue in error.value.issues
    )


class Scope:
    """A scope whose leaf `field` names say the outcome: t, f or u (unknown)."""

    params: dict = {"p": 5}
    definitions: dict = {}

    def field(self, name):
        return {"t": 1, "f": 0, "u": None}[name]

    def measure(self, name):
        return self.field(name)

    def members(self):
        return []


def leaf(kind: str):
    return {"field": kind, "op": "gt", "value": 0}  # t: 1 > 0 true; f: 0 > 0 false; u: missing


def kleene_all(values):
    return F_ if F_ in values else (U if U in values else T)


def kleene_any(values):
    return T if T in values else (U if U in values else F_)


@pytest.mark.parametrize("values", list(itertools.product([T, F_, U], repeat=2)))
def test_kleene_all_any_truth_table(values):
    names = {T: "t", F_: "f", U: "u"}
    parts = [leaf(names[v]) for v in values]
    assert eval_condition({"all": parts}, Scope()) is kleene_all(values)
    assert eval_condition({"any": parts}, Scope()) is kleene_any(values)


@pytest.mark.parametrize("value, expected", [(T, F_), (F_, T), (U, U)])
def test_kleene_not(value, expected):
    names = {T: "t", F_: "f", U: "u"}
    assert eval_condition({"not": leaf(names[value])}, Scope()) is expected


def test_exists_and_missing_give_definite_answers():
    assert eval_condition({"field": "u", "op": "missing"}, Scope()) is True
    assert eval_condition({"field": "u", "op": "exists"}, Scope()) is False
    assert eval_condition({"field": "t", "op": "exists"}, Scope()) is True


def test_compound_condition_with_an_unknown_part():
    assert eval_condition({"all": [leaf("f"), leaf("u")]}, Scope()) is False
    assert eval_condition({"all": [leaf("t"), leaf("u")]}, Scope()) is None


@pytest.mark.parametrize(
    "op, left, right, expected",
    [
        ("eq", 3, 3, T),
        ("ne", 3, 4, T),
        ("lt", 3, 4, T),
        ("le", 4, 4, T),
        ("gt", 5, 4, T),
        ("ge", 4, 4, T),
        ("lt", 4, 4, F_),
        ("in", "a", ["a", "b"], T),
        ("not_in", "c", ["a", "b"], T),
        ("matches", "oil_refinery", "oil|refiner", T),
        ("matches", "coal", "oil", F_),
        ("contains_any", ["x", "y"], ["y", "z"], T),
        ("contains_any", ["x"], ["z"], F_),
        ("lt", None, 4, U),
        ("eq", "a", 1, U),
        ("eq", True, 1, U),
        ("in", None, ["a"], U),
        ("matches", None, "a", U),
    ],
)
def test_operators(op, left, right, expected):
    assert compare(op, left, right) is expected


def test_unknown_before_a_true_outcome_makes_the_entity_not_evaluable():
    outcomes = [{"when": leaf("u"), "marker": "a"}, {"when": leaf("t"), "marker": "b"}]
    assert first_true(outcomes, Scope()) == (None, True)
    assert first_true([{"when": leaf("f"), "marker": "a"}, {"when": leaf("t"), "marker": "b"}], Scope()) == (1, False)
    assert first_true([{"when": leaf("f"), "marker": "a"}], Scope()) == (None, False)


# ---- availability ---------------------------------------------------------------------


def test_known_field_without_snapshot_data_is_skipped(geometry_capability):
    net = Net().station(1, "A", 10, "Alpha").station(2, "B", 20, "Beta").line(100, "L", [1, 2], profit=-1)
    m = load_file(FIXTURES / "mode-ladder.tf3c-methodology.json")
    verdicts = run(m, net)
    ladder = verdicts.ladders[0]
    assert ladder.status == "skipped" and "missing data: station positions" in ladder.reason
    assert ladder.items == []
    assert rule(verdicts, "passenger-lines").status == "ok"  # the other rules are still evaluated


def test_typo_is_inspectable_but_blocks_application_of_the_whole_policy():
    net = Net().station(1, "A", 10, "Alpha").line(100, "L", [1], profit=-5)
    m = methodology(
        rules=[
            {
                "id": "typo",
                "entity": "line",
                "outcomes": [{"when": cond("line.profit_yeer", "lt", 0), "marker": "problem"}],
            },
            {
                "id": "good",
                "entity": "line",
                "outcomes": [{"when": cond("line.profit_year", "lt", 0), "marker": "problem"}],
            },
        ]
    )
    _, diagnostic = inspect(m.raw)
    assert diagnostic["structurallyValid"] and not diagnostic["activationEligible"]
    support = {entry["id"]: entry["status"] for entry in diagnostic["rules"]}
    assert support == {"typo": "unsupported", "good": "ok"}
    assert any(
        issue["ruleId"] == "typo" and issue["category"] == "unsupported-field" for issue in diagnostic["diagnostics"]
    )
    with pytest.raises(MethodologyError):
        run(m, net)


def test_per_entity_missing_value_counts_as_not_evaluable():
    net = (
        Net()
        .station(1, "A", 10, "Alpha")
        .line(100, "Old", [1], profit=-1, age=5)
        .line(101, "NoVehicles", [1], profit=-1, age=None)
    )
    m = methodology(
        rules=[
            {
                "id": "age",
                "entity": "line",
                "outcomes": [{"when": cond("line.age_years", "lt", 3), "marker": "note"}],
                "default": {"marker": "ok"},
            }
        ]
    )
    result = rule(run(m, net), "age")
    assert result.evaluated == 2 and result.not_evaluable == 1
    assert markers_of(run(m, net), "age") == {"Old": "ok"}  # the line without vehicles gets no marker


def test_supported_unclassified_reports_roles_with_unknown_data():
    net = Net().station(1, "A", 10, "Alpha").line(100, "L", [1], age=None)
    m = methodology(roles={"line": [{"id": "x", "select": cond("line.cargo_keys", "contains_any", ["coal"])}]})
    summary = run(m, net).roles["line"]
    assert summary.unclassified == 1 and summary.unclassified_unknown == 1


# ---- roles ------------------------------------------------------------------------------

ROLE_DOC = {
    "roles": {
        "line": [
            {
                "id": "local",
                "select": {"all": [cond("line.is_passenger_only", "eq", True), cond("line.town_count", "le", 1)]},
            },
            {"id": "intercity", "select": cond("line.is_passenger_only", "eq", True)},
            {"id": "freight", "select": cond("line.is_passenger_only", "eq", False)},
        ]
    }
}


def test_name_free_classification():
    net = (
        Net()
        .station(1, "A", 10, "Alpha")
        .station(2, "B", 20, "Beta")
        .line(100, "Line 7", [1, 2])
        .line(101, "Line 8", [1, 1])
        .line(102, "Line 9", [1], cargo=FREIGHT)
    )
    verdicts = run(methodology(**ROLE_DOC), net)
    index = verdicts.role_index["line"]
    assert index == {100: "intercity", 101: "local", 102: "freight"}


def test_first_matching_role_wins_and_unclassified_lines_are_counted():
    net = Net().station(1, "A", 10, "Alpha").line(100, "P", [1]).line(101, "Empty", [1], age=None)
    verdicts = run(methodology(**ROLE_DOC), net)
    summary = verdicts.roles["line"]
    assert {r["id"]: r["count"] for r in summary.roles} == {"local": 1, "intercity": 0, "freight": 0}
    assert summary.unclassified == 1 and summary.unclassified_unknown == 1  # passenger-ness is unknown without capacity
    assert verdicts.role_index["line"][101] == "unclassified"


def test_name_codes_never_decide_the_town():
    net = (
        Net()
        .station(1, "Mon central", 10, "Monnickendam")
        .station(2, "Mon harbour", 20, "Montfoort")
        .line(100, "Bus x-Mon-LO-1", [1], profit=-10)
        .line(101, "Bus y-Mon-LO-2", [2], profit=-20)
    )
    m = methodology(
        name_patterns={"line": [{"id": "coded", "pattern": r"^(?P<mode>\S+) .*?-(?P<scope>LO|IC)-(?P<n>\d+)$"}]},
        roles={"line": [{"id": "local", "select": cond("line.name_capture.scope", "eq", "LO")}]},
        rules=[
            {
                "id": "by-town",
                "entity": "line",
                "aggregate": {
                    "group_by": "town",
                    "measures": {"result": {"agg": "sum", "value": "line.profit_year", "via": "line.first_stop_town"}},
                    "outcomes": [{"when": {"measure": "result", "op": "lt", "value": 0}, "marker": "note"}],
                },
            }
        ],
    )
    groups = {g["group"]: g["measures"]["result"] for g in rule(run(m, net), "by-town").groups}
    assert groups == {"Monnickendam": -10, "Montfoort": -20}  # two towns share the code "Mon" and stay distinct


def test_name_patterns_use_the_first_matching_pattern_all_or_nothing():
    net = (
        Net().station(1, "A", 10, "Alpha").line(100, "Bus x-IC-3", [1]).line(101, "Tram plain", [1]).line(102, "", [1])
    )
    m = methodology(
        name_patterns={
            "line": [
                {"id": "coded", "pattern": r"^(?P<mode>\S+) .*?-(?P<scope>LO|IC)-(?P<n>\d+)$"},
                {"id": "first-word", "pattern": r"^(?P<mode>\S+)"},
            ]
        },
        rules=[
            {
                "id": "caps",
                "entity": "line",
                "outcomes": [
                    {"when": cond("line.name_capture.scope", "missing"), "marker": "note"},
                    {"when": cond("line.name_capture.scope", "eq", "IC"), "marker": "watch"},
                ],
                "default": {"marker": "ok"},
            }
        ],
    )
    result = markers_of(run(m, net), "caps")
    assert result["Bus x-IC-3"] == "watch"
    assert result["Tram plain"] == "note"  # the second pattern matched mode only: scope stays missing
    assert result[""] == "note"  # an empty name matches no pattern at all, so every capture is missing


# ---- entity rules -----------------------------------------------------------------------------------


def graded_rules():
    return methodology(
        parameters={"loss_alert": {"value": 100000}},
        rules=[
            {
                "id": "loss",
                "label": "Loss",
                "entity": "line",
                "outcomes": [
                    {
                        "when": cond("line.loss_year", "gt", {"param": "loss_alert"}),
                        "marker": "problem",
                        "message": "{line.name} loses {line.loss_year|money} a year, above {param.loss_alert|money}.",
                    },
                    {
                        "when": cond("line.profit_year", "lt", 0),
                        "marker": "watch",
                        "message": "{line.name} loses {line.loss_year|money}.",
                    },
                ],
                "default": {"marker": "ok"},
            }
        ],
    )


def test_graded_intercity_loss_and_marker_findings():
    net = (
        Net()
        .station(1, "A", 10, "Alpha")
        .line(100, "Big", [1], profit=-150_000)
        .line(101, "Small", [1], profit=-40_000)
        .line(102, "Edge", [1], profit=-100_000)
        .line(103, "Fine", [1], profit=1)
    )
    verdicts = run(graded_rules(), net)
    assert markers_of(verdicts, "loss") == {"Big": "problem", "Small": "watch", "Edge": "watch", "Fine": "ok"}
    hit = next(h for h in rule(verdicts, "loss").hits if h.entity["name"] == "Big")
    assert hit.message == "Big loses 150,000 a year, above 100,000."
    assert hit.evidence["line.loss_year"] == 150_000


def test_marker_without_finding_produces_no_finding():
    from tf3companion.methodology.engine import rule_findings

    net = (
        Net()
        .station(1, "A", 10, "Alpha")
        .line(100, "Big", [1], profit=-150_000)
        .line(101, "Small", [1], profit=-40_000)
    )
    m = graded_rules()
    verdicts = run(m, net)
    found = rule_findings(m, verdicts)
    assert {f.entity["name"]: f.severity for f in found} == {"Big": "high", "Small": "low"}
    assert all(f.source == "methodology" and f.code == "rule:loss" for f in found)
    assert all(f.methodology == "test@1.0.0" and f.methodology_hash.startswith("sha256:") for f in found)
    quiet = methodology(
        markers={"ok": {"label": "ok"}, "note": {"label": "within rule"}},
        rules=[
            {"id": "l", "entity": "line", "outcomes": [{"when": cond("line.profit_year", "lt", 0), "marker": "note"}]}
        ],
    )
    assert markers_of(run(quiet, net), "l") == {"Big": "note", "Small": "note"}
    assert rule_findings(quiet, run(quiet, net)) == []


def test_template_with_missing_value_prints_not_available():
    net = Net().station(1, "A", 10, "Alpha").line(100, "L", [1], profit=-5, age=None)
    m = methodology(
        rules=[
            {
                "id": "r",
                "entity": "line",
                "outcomes": [
                    {
                        "when": cond("line.profit_year", "lt", 0),
                        "marker": "note",
                        "message": "{line.name}: age {line.age_years|years}",
                    }
                ],
            }
        ]
    )
    assert rule(run(m, net), "r").hits[0].message == "L: age n/a"


def test_hostile_text_is_stripped_of_control_characters():
    net = Net().station(1, "A", 10, "Alpha").line(100, "Line\x00with\x1bcontrol\nchars", [1], profit=-5)
    m = methodology(
        rules=[
            {
                "id": "r",
                "entity": "line",
                "outcomes": [
                    {"when": cond("line.profit_year", "lt", 0), "marker": "note", "message": "bad {line.name}"}
                ],
            }
        ]
    )
    message = rule(run(m, net), "r").hits[0].message
    assert "\x00" not in message and "\x1b" not in message and "\n" not in message


def test_parameter_override_at_apply_time():
    net = Net().station(1, "A", 10, "Alpha").line(100, "Big", [1], profit=-150_000)
    verdicts = run(graded_rules(), net, overrides={"loss_alert": 200_000})
    assert markers_of(verdicts, "loss") == {"Big": "watch"}
    assert verdicts.parameters["loss_alert"] == 200_000 and verdicts.overrides == {"loss_alert": 200_000}
    with pytest.raises(MethodologyError) as failure:
        run(graded_rules(), net, overrides={"nope": 1})
    assert [(i.path, i.category) for i in failure.value.issues] == [("/overrides/nope", "override")]


# ---- aggregates -----------------------------------------------------------------------------------------------


def town_balance():
    return methodology(
        parameters={"ratio_alert": {"value": 0.25}},
        roles={
            "line": [
                {
                    "id": "local",
                    "select": {"all": [cond("line.is_passenger_only", "eq", True), cond("line.town_count", "le", 1)]},
                },
                {"id": "intercity", "select": cond("line.is_passenger_only", "eq", True)},
            ]
        },
        markers={
            "ok": {"label": "ok"},
            "problem": {"label": "problem", "finding": "high"},
            "within": {"label": "within rule"},
        },
        rules=[
            {
                "id": "balance",
                "entity": "line",
                "aggregate": {
                    "group_by": "town",
                    "measures": {
                        "local_result": {
                            "agg": "sum",
                            "value": "line.profit_year",
                            "where": cond("line.role", "eq", "local"),
                            "via": "line.first_stop_town",
                        },
                        "local_lines": {
                            "agg": "count",
                            "where": cond("line.role", "eq", "local"),
                            "via": "line.first_stop_town",
                        },
                        "intercity_result": {
                            "agg": "sum",
                            "value": "line.profit_year",
                            "where": cond("line.role", "eq", "intercity"),
                            "via": "line.stop_towns",
                        },
                        "ratio": {
                            "agg": "ratio",
                            "numerator": {"measure": "local_result", "negate": True},
                            "denominator": {"measure": "intercity_result"},
                        },
                    },
                    "having": {"measure": "local_lines", "op": "gt", "value": 0},
                    "outcomes": [
                        {
                            "when": {
                                "all": [
                                    {"measure": "local_result", "op": "lt", "value": 0},
                                    {
                                        "any": [
                                            {"measure": "intercity_result", "op": "le", "value": 0},
                                            {"measure": "ratio", "op": "gt", "value": {"param": "ratio_alert"}},
                                        ]
                                    },
                                ]
                            },
                            "marker": "problem",
                            "message": "{group}: local {local_result|money}, intercity {intercity_result|money}",
                        },
                        {"when": {"measure": "local_result", "op": "lt", "value": 0}, "marker": "within"},
                    ],
                    "default": {"marker": "ok"},
                },
            }
        ],
    )


def balance_net(local_loss: int, intercity: int) -> Net:
    net = Net().station(1, "A1", 10, "Alpha").station(2, "B1", 20, "Beta")
    net.line(100, "Local", [1, 1], profit=-local_loss).line(101, "Trunk", [1, 2], profit=intercity)
    return net


@pytest.mark.parametrize(
    "local_loss, intercity, marker, ratio",
    [
        (30_000, 100_000, "problem", 0.30),
        (20_000, 100_000, "within", 0.20),
        (25_000, 100_000, "within", 0.25),  # exactly the tolerance: strictly greater is required
        (10_000, 0, "problem", None),  # no intercity profit: always a problem, ratio not applicable
        (10_000, -5_000, "problem", None),
        (-5_000, 100_000, "ok", -0.05),  # local lines profitable
    ],
)
def test_town_balance_scenarios(local_loss, intercity, marker, ratio):
    verdicts = run(town_balance(), balance_net(local_loss, intercity))
    groups = {g["group"]: g for g in rule(verdicts, "balance").groups}
    assert groups["Alpha"]["marker"] == marker
    if ratio is None:
        assert groups["Alpha"]["measures"]["ratio"] is None
    else:
        assert groups["Alpha"]["measures"]["ratio"] == pytest.approx(ratio)


def test_town_balance_only_towns_with_local_lines_and_evidence():
    verdicts = run(town_balance(), balance_net(30_000, 100_000))
    result = rule(verdicts, "balance")
    assert [g["group"] for g in result.groups] == ["Alpha"]  # Beta has an intercity line but no local line
    hit = result.hits[0]
    assert hit.message == "Alpha: local -30,000, intercity 100,000"
    assert hit.evidence["ratio"] == pytest.approx(0.3) and hit.evidence["local_lines"] == 1


def test_first_town_versus_every_distinct_town():
    net = balance_net(0, 100_000)  # the trunk touches Alpha and Beta; its profit counts for both
    net.line(102, "Local B", [2, 2], profit=-1)
    verdicts = run(town_balance(), net)
    groups = {g["group"]: g["measures"] for g in rule(verdicts, "balance").groups}
    assert groups["Alpha"]["intercity_result"] == 100_000 and groups["Beta"]["intercity_result"] == 100_000
    assert groups["Beta"]["local_result"] == -1


def air_station():
    return methodology(
        parameters={"watch": {"value": 3.0}},
        rules=[
            {
                "id": "air",
                "entity": "stop",
                "aggregate": {
                    "group_by": "stop.station",
                    "having": {"any_member": cond("stop.line.carrier", "eq", "AIR")},
                    "measures": {
                        "vehicles": {"agg": "sum", "value": "stop.line.vehicle_count", "distinct_by": "stop.line_id"},
                        "terminals": {"agg": "distinct_count", "value": "stop.terminal"},
                        "per_terminal": {
                            "agg": "ratio",
                            "numerator": {"measure": "vehicles"},
                            "denominator": {"measure": "terminals"},
                        },
                    },
                    "outcomes": [
                        {
                            "when": {"measure": "per_terminal", "op": "ge", "value": {"param": "watch"}},
                            "marker": "watch",
                            "message": "{group}: {per_terminal} per terminal",
                        }
                    ],
                    "default": {"marker": "ok"},
                },
            }
        ],
    )


def air_net(vehicles_a: int, vehicles_b: int, terminals) -> Net:
    net = Net().station(1, "Airport", 10, "Alpha").station(2, "Bus stop", 10, "Alpha")
    net.line(100, "AP 1", [1, 1], carrier="AIR", vehicles=vehicles_a, terminals=terminals[:2])
    net.line(101, "AP 2", [1, 1], carrier="AIR", vehicles=vehicles_b, terminals=terminals[2:])
    net.line(102, "Bus", [2, 2], carrier="ROAD", vehicles=9, terminals=[0, 0])
    return net


def test_air_station_pressure_counts_each_line_once_and_ignores_non_air_stations():
    verdicts = run(air_station(), air_net(4, 2, [0, 1, 0, 1]))
    groups = {g["group"]: g for g in rule(verdicts, "air").groups}
    assert list(groups) == ["Airport"]  # the bus stop has no air line
    assert groups["Airport"]["measures"] == {"vehicles": 6, "terminals": 2, "per_terminal": 3.0}
    assert groups["Airport"]["marker"] == "watch"  # exactly 3.0 per terminal is on watch
    assert run(air_station(), air_net(3, 2, [0, 1, 0, 1])).rules[0].hits[0].marker == "ok"  # 2.5 aircraft per terminal


def test_missing_terminals_are_not_evaluable_never_zero():
    net = (
        Net().station(1, "Airport", 10, "Alpha").line(100, "AP 1", [1, 1], carrier="AIR", vehicles=4)
    )  # no terminal values
    verdicts = run(air_station(), net)
    result = rule(verdicts, "air")
    assert (
        result.status == "skipped" and "stops[].terminal" in result.reason
    )  # the collector emitted no terminals at all


def test_partial_terminal_data_marks_the_group_not_evaluable():
    net = air_net(4, 2, [0, 1, 0, 1])
    for stop in net.data["lines"][0]["stops"] + net.data["lines"][1]["stops"]:
        stop.pop("terminal")
    for stop in net.data["lines"][2]["stops"]:
        stop["terminal"] = 0  # terminals exist somewhere, so the data is "present", but not for the air stops
    result = rule(run(air_station(), net), "air")
    assert result.status == "ok" and result.not_evaluable == 1 and result.hits == []
    assert result.excluded_members > 0


# ---- recommendations ----------------------------------------------------------------------------------


def recommended():
    return methodology(
        roles={
            "line": [
                {"id": "freight", "select": cond("line.is_passenger_only", "eq", False)},
                {"id": "pax", "select": cond("line.is_passenger_only", "eq", True)},
            ]
        },
        rules=[
            {
                "id": "loss",
                "entity": "line",
                "outcomes": [{"when": cond("line.profit_year", "lt", 0), "marker": "problem"}],
                "default": {"marker": "ok"},
            }
        ],
        recommendations=[
            {
                "id": "fix",
                "when": {"rule": "loss", "marker": "problem", "role": "freight"},
                "priority": 2,
                "text": "Review {line.name}: it loses {line.loss_year|money}.",
            }
        ],
    )


def test_recommendation_from_a_rule_hit_with_evidence_and_role_filter():
    net = (
        Net()
        .station(1, "A", 10, "Alpha")
        .line(100, "Coal", [1], profit=-9_000, cargo=FREIGHT)
        .line(101, "People", [1], profit=-4_000)
    )
    verdicts = run(recommended(), net)
    advice = verdicts.recommendations[0]
    assert advice.status == "ok" and len(advice.items) == 1  # only the freight hit matches the role filter
    item = advice.items[0]
    assert item["text"] == "Review Coal: it loses 9,000."
    assert item["evidence"]["rule"] == "loss" and item["evidence"]["marker"] == "problem"
    assert item["evidence"]["entity"]["name"] == "Coal" and item["evidence"]["values"]["line.loss_year"] == 9_000


def test_recommendation_is_skipped_when_its_trigger_is_skipped(geometry_capability):
    m = methodology(
        rules=[
            {
                "id": "needs-positions",
                "entity": "line",
                "outcomes": [{"when": cond("line.route_km", "gt", 10), "marker": "problem"}],
            }
        ],
        recommendations=[
            {"id": "go", "when": {"rule": "needs-positions", "marker": "problem"}, "priority": 1, "text": "Go."}
        ],
    )
    net = Net().station(1, "A", 10, "Alpha").line(100, "L", [1])
    verdicts = run(m, net)
    advice = verdicts.recommendations[0]
    assert advice.status == "skipped" and "missing data: station positions" in advice.reason and advice.items == []
    assert {"kind": "recommendation", "id": "go"} == {k: v for k, v in verdicts.skipped[1].items() if k != "reason"}


# ---- distance-band ladder (positions exist only in this synthetic fixture) ---------------------------------


def ladder_net(distance_km: float, carrier: str) -> Net:
    net = (
        Net()
        .station(1, "A", 10, "Alpha", position=[0, 0, 0])
        .station(2, "B", 20, "Beta", position=[distance_km * 1000, 0, 0])
    )
    return net.line(100, "Trunk", [1, 2], carrier=carrier)


def test_ladder_recommends_the_band_mode_when_the_carrier_differs(geometry_capability):
    m = load_file(FIXTURES / "mode-ladder.tf3c-methodology.json")
    verdicts = run(m, ladder_net(95, "ROAD"))
    ladder = verdicts.ladders[0]
    assert ladder.status == "ok" and len(ladder.items) == 1
    item = ladder.items[0]
    assert item["text"] == "Trunk spans 95.0 km; the band suggests RAIL, the line runs on ROAD."
    assert item["evidence"]["distanceKm"] == 95.0 and item["evidence"]["carrier"] == "ROAD"
    assert item["evidence"]["band"] == {"fromKm": 40, "toKm": 150, "mode": "RAIL"}


@pytest.mark.parametrize("km, carrier", [(20, "ROAD"), (95, "RAIL"), (300, "AIR")])
def test_ladder_is_silent_when_the_carrier_matches_the_band(km, carrier, geometry_capability):
    m = load_file(FIXTURES / "mode-ladder.tf3c-methodology.json")
    assert run(m, ladder_net(km, carrier)).ladders[0].items == []


def test_ladder_band_edges_belong_to_the_next_band(geometry_capability):
    m = load_file(FIXTURES / "mode-ladder.tf3c-methodology.json")
    item = run(m, ladder_net(40, "ROAD")).ladders[0].items[0]
    assert item["evidence"]["band"]["mode"] == "RAIL"  # exactly 40 km is no longer "below 40 km"
