"""Behavioral safety gates and library-root inheritance, without a game or database."""
import json
from pathlib import Path

import pytest

from tf3companion.methodology.library import Library
from tf3companion.methodology.loader import parse
from tf3companion.methodology.model import MethodologyError
from tf3companion.methodology.prepare import inspect, prepare
from tf3companion.methodology.resolve import Resolver, validate_file
from tf3companion.methodology.scope import UserPreference


def document(ident="policy", version="1.0.0", **extra):
    return {"schema": "tf3c-methodology/1", "id": ident, "version": version,
            "name": "Policy", "description": "Fixture policy.", **extra}


def drop(root, data):
    folder = root / "methodologies"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{data['id']}@{data['version']}.tf3c-methodology.json"
    path.write_text(json.dumps(data))
    return path


def incompatible(ident="unsupported", version="1.0.0"):
    return document(ident, version, rules=[{"id": "unknown", "entity": "line", "outcomes": [
        {"when": {"field": "line.no_such_measure", "op": "gt", "value": 1}, "marker": "review"}]}],
        markers={"review": {"label": "Review"}})


def test_default_inheritance_is_shared_but_save_overrides_are_not(tmp_path):
    for ident in ("one", "two", "pinned"):
        drop(tmp_path, document(ident))
    for save in ("A", "B"):
        scope = tmp_path / "saves" / save
        scope.mkdir(parents=True)
        (scope / "save.json").write_text(json.dumps({"label": save}))
    a, b = Resolver(tmp_path, "A"), Resolver(tmp_path, "B")
    a.use("pinned@1.0.0")
    pinned_bytes = a.scope.metadata.read_bytes()
    a.set_default("one")
    assert a.resolve()[1] == "save-override"
    assert b.resolve()[0].id == "one"
    a.set_default("two")
    assert b.resolve()[0].id == "two"  # same running resolver reads current preference
    assert a.scope.metadata.read_bytes() == pinned_bytes
    assert a.preference.metadata == b.preference.metadata
    a.clear_default()
    assert b.resolve()[1] == "packaged-default"
    a.set_default("one")
    a.unuse()
    assert a.resolve()[1] == "user-default"
    assert json.loads(a.scope.metadata.read_text()) == {"label": "A"}
    assert json.loads(b.scope.metadata.read_text()) == {"label": "B"}


def test_lazy_precedence_reports_lower_error_without_blocking_selection(tmp_path):
    drop(tmp_path, document())
    resolver = Resolver(tmp_path)
    resolver.use("policy")
    resolver.preference.metadata.write_text("broken JSON")
    assert resolver.resolve()[1] == "save-override"
    listing = resolver.listing()
    assert listing["error"] is None
    assert listing["userDefault"]["error"]
    assert listing["saveOverride"]["resolved"] == "policy@1.0.0"
    resolver.scope.metadata.write_text("broken JSON")
    assert resolver.resolve("policy")[1] == "request"
    result = resolver.clear_default()
    assert result["previousError"]
    assert resolver.preference.reference() is None
    assert resolver.scope.metadata.read_text() == "broken JSON"


def test_empty_root_inspection_and_reset_do_not_create_anything(tmp_path):
    root = tmp_path / "absent"
    resolver = Resolver(root)
    assert resolver.listing()["origin"] == "packaged-default"
    resolver.clear_default()
    assert not root.exists()
    other = Resolver(tmp_path / "independent")
    assert other.preference.reference() is None
    with pytest.raises(LookupError):
        Resolver(root, "unknown").listing()
    assert Resolver(root, "unknown").set_default("default")["resolved"] == "default@1.0.0"
    assert not (root / "companion.sqlite3").exists()


def test_incompatible_highest_version_never_downgrades_and_failed_sets_preserve_bytes(tmp_path):
    drop(tmp_path, document("floating", "1.9.0"))
    drop(tmp_path, document("floating", "1.10.0"))
    resolver = Resolver(tmp_path)
    resolver.set_default("floating")
    assert resolver.resolve()[0].version == "1.10.0"
    resolver.use("floating@1.9.0")
    preference, binding = resolver.preference.metadata.read_bytes(), resolver.scope.metadata.read_bytes()
    drop(tmp_path, incompatible("floating", "2.0.0"))
    with pytest.raises(ValueError):
        resolver.set_default("floating")
    with pytest.raises(ValueError):
        resolver.use("floating")
    assert resolver.preference.metadata.read_bytes() == preference
    assert resolver.scope.metadata.read_bytes() == binding
    assert resolver.resolve()[0].version == "1.9.0"
    resolver.unuse()
    with pytest.raises(ValueError, match="user-default"):
        resolver.resolve()


def test_failed_force_import_creates_no_root_and_preserves_existing_target(tmp_path):
    root, source = tmp_path / "library", tmp_path / "draft.json"
    source.write_text(json.dumps(incompatible()))
    with pytest.raises(MethodologyError):
        Library(root).import_file(source, force=True)
    assert not root.exists()
    source.write_text(json.dumps(document()))
    target = Path(Library(root).import_file(source)["file"])
    before = target.read_bytes()
    source.write_text(json.dumps(document(rulez=[])))
    with pytest.raises(MethodologyError):
        Library(root).import_file(source, force=True)
    assert target.read_bytes() == before


def test_validation_diagnostics_include_syntax_locations_and_escaped_pointers(tmp_path):
    _, report = inspect(b'{"schema":\n broken}')
    diagnostic = report["diagnostics"][0]
    assert diagnostic["category"] == "syntax" and diagnostic["path"] == ""
    assert diagnostic["line"] == 2 and diagnostic["column"] is not None
    bad = document(**{"bad/key~": 1, "parameters": {"broken": {"value": []}}})
    _, report = inspect(json.dumps(bad).encode())
    assert {d["path"] for d in report["diagnostics"]} >= {"/bad~1key~0", "/parameters/broken/value"}
    assert all({"category", "code", "severity", "itemId", "ruleId", "line", "column"} <= d.keys()
               for d in report["diagnostics"])
    path = tmp_path / "draft.json"
    path.write_text(json.dumps(incompatible()))
    assert validate_file(str(path))["valid"]
    assert not validate_file(str(path), strict=True)["valid"]


def test_effective_overrides_are_finite_typed_and_isolated():
    raw = json.dumps(document(parameters={"number": {"value": 3}, "flag": {"value": True}})).encode()
    m = parse(raw)
    for override in ({"unknown": 1}, {"number": True}, {"number": float("inf")}, {"flag": 1}):
        with pytest.raises(MethodologyError) as exc:
            prepare(m, override)
        assert exc.value.issues[0].path.startswith("/overrides/")
        assert exc.value.issues[0].category == "override"
    overrides = {"number": 7}
    effective = prepare(m, overrides)
    overrides["number"] = 100
    assert effective.parameters["number"] == 7
    assert m.parameters["number"] == 3
    assert effective.sha256 == m.sha256
    repeated = prepare(effective)
    assert repeated.raw == m.raw and repeated.sha256 == m.sha256
    assert repeated.parameters["number"] == 7
    assert repeated.effective_overrides == {"number": 7}
    assert prepare(repeated, {"number": 9}).sha256 == m.sha256
    from tf3companion.methodology.engine import evaluate
    from conftest import base_snapshot
    from tf3companion.snapshot import Snapshot
    verdicts = evaluate(repeated, Snapshot(base_snapshot()))
    assert verdicts.parameters["number"] == 7
    assert verdicts.overrides == {"number": 7}
    assert verdicts.methodology["sha256"] == m.sha256


def test_changed_dropin_is_revalidated_and_previous_selection_is_not_erased(tmp_path):
    path = drop(tmp_path, document())
    resolver = Resolver(tmp_path)
    resolver.set_default("policy")
    preference = resolver.preference.metadata.read_bytes()
    first = resolver.resolve()[0].sha256
    path.write_text(json.dumps(document(description="Changed valid bytes.")))
    assert resolver.resolve()[0].sha256 != first
    path.write_text(json.dumps(incompatible("policy")))
    with pytest.raises(ValueError):
        resolver.resolve()
    assert resolver.preference.metadata.read_bytes() == preference


def test_readonly_mcp_validation_and_configuration_need_no_companion(tmp_path, monkeypatch):
    from tf3companion import mcp_server
    monkeypatch.setenv("TF3C_DATA_DIR", str(tmp_path / "library"))
    monkeypatch.setattr(mcp_server, "companion", lambda: pytest.fail("must not construct Companion"))
    result = mcp_server.validate_methodology(content=json.dumps(document()))
    assert result["activationEligible"]
    assert mcp_server.list_methodologies()["origin"] == "packaged-default"
    with pytest.raises(ValueError):
        mcp_server.validate_methodology(methodology="/arbitrary/private.json")
    assert not (tmp_path / "library").exists()
    mcp_server.set_methodology_default("default")
    assert mcp_server.list_methodologies()["origin"] == "user-default"
    mcp_server.set_methodology_default(None)
    assert mcp_server.list_methodologies()["origin"] == "packaged-default"


def test_single_report_publication_stages_manifest_before_replacing_old_folder(tmp_path, monkeypatch):
    from tf3companion.methodology import output
    folder = tmp_path / "reports" / "date__policy@1.0.0"
    output.write_bundle(folder, {"company.md": "old", "lines.md": "preserved"}, {"generation": 1})
    before = {p.name: p.read_bytes() for p in folder.iterdir()}
    original = output.atomic_write

    def fail_manifest(path, content):
        if path.name == output.MANIFEST:
            raise OSError("fixture publication failure")
        return original(path, content)

    monkeypatch.setattr(output, "atomic_write", fail_manifest)
    with pytest.raises(OSError):
        output.add_files(folder, {"company.md": "new"}, {"generation": 2})
    assert {p.name: p.read_bytes() for p in folder.iterdir()} == before
    monkeypatch.setattr(output, "atomic_write", original)
    output.add_files(folder, {"company.md": "new"}, {"generation": 2})
    assert (folder / "company.md").read_text() == "new"
    assert (folder / "lines.md").read_text() == "preserved"
    assert json.loads((folder / output.MANIFEST).read_text())["generation"] == 2


def test_mutating_loaded_policy_cannot_bypass_preparation():
    m = parse(json.dumps(document()).encode())
    m.data["unknown-key"] = True
    with pytest.raises(MethodologyError):
        prepare(m)


def test_report_policy_validation_uses_shared_registry_and_preserves_old_default(tmp_path):
    resolver = Resolver(tmp_path)
    resolver.set_default("default")
    before = resolver.preference.metadata.read_bytes()
    drop(tmp_path, document(report_policies={"expansion": {"weight_volume": 99}}))
    with pytest.raises(ValueError):
        resolver.set_default("policy")
    assert resolver.preference.metadata.read_bytes() == before
    row = next(e for e in resolver.listing()["methodologies"] if e["id"] == "policy")
    assert not row["activationEligible"]
    assert any(d["path"].startswith("/report_policies/expansion/") for d in row["diagnostics"])


def test_failed_runtime_regeneration_preserves_reports_manifest_latest_and_evidence(paths):
    from methodology_helpers import companion_with, troubled_company
    from tf3companion.methodology import output
    companion = companion_with(paths, troubled_company())
    try:
        path = drop(paths.data, document(parameters={"limit": {"value": 3}}))
        companion.resolver.set_default("policy")
        summary = companion.analyse()
        companion.report("company")
        folder = Path(summary["outputFolder"])
        before = {str(p.relative_to(paths.data)): p.read_bytes()
                  for p in paths.data.joinpath("reports").rglob("*") if p.is_file()}
        rows = companion.store.conn.execute("SELECT game_time, data FROM snapshots ORDER BY game_time").fetchall()
        for method in (
            lambda: companion.analyse(param_overrides={"limit": float("nan")}),
            lambda: companion.report("company", param_overrides={"limit": "wrong"}),
        ):
            with pytest.raises(ValueError):
                method()
        path.write_text(json.dumps(incompatible("policy")))
        for method in (companion.analyse, companion.findings, lambda: companion.report("company")):
            with pytest.raises(ValueError):
                method()
        after = {str(p.relative_to(paths.data)): p.read_bytes()
                 for p in paths.data.joinpath("reports").rglob("*") if p.is_file()}
        assert before == after
        assert companion.store.conn.execute("SELECT game_time, data FROM snapshots ORDER BY game_time").fetchall() == rows
        assert (folder / output.MANIFEST).is_file()
        assert (paths.data / "reports" / output.LATEST).is_file()
    finally:
        companion.close()


def regex_policy():
    return document(parameters={"pattern": {"value": "^Train"}}, markers={"review": {"label": "Review"}}, rules=[
        {"id": "named", "entity": "line", "outcomes": [
            {"when": {"field": "line.name", "op": "matches", "value": {"param": "pattern"}}, "marker": "review"}]}])


@pytest.mark.parametrize("pattern", ["(a+)+$", "(unclosed"])
def test_override_that_makes_a_consumer_invalid_reports_override_and_related_rule(pattern):
    raw = json.dumps(regex_policy()).encode()
    assert inspect(raw, overrides={"pattern": "^Bus"})[1]["activationEligible"]
    m, report = inspect(raw, overrides={"pattern": pattern})
    assert m is not None and not report["activationEligible"]
    [issue] = report["diagnostics"]
    assert issue["code"] == "invalid-effective-policy" and issue["category"] == "override"
    assert issue["path"] == "/overrides/pattern" and issue["ruleId"] == "named"
    assert issue["relatedPaths"] == ["/rules/0/outcomes/0/when/value/param"]
    with pytest.raises(MethodologyError) as exc:
        prepare(parse(raw), {"pattern": pattern})
    assert exc.value.issues[0].code == "invalid-effective-policy"
    assert exc.value.issues[0].ruleId == "named"


def test_valid_override_retains_provenance_and_unrelated_default_is_untouched():
    m, report = inspect(json.dumps(regex_policy()).encode(), overrides={"pattern": "^Bus"})
    assert report["parameterOverrides"] == {"pattern": "^Bus"} and report["parameters"]["pattern"] == "^Bus"
    assert m.effective_overrides == {"pattern": "^Bus"}
    assert report["sha256"] == m.sha256


def _stored_snapshots(paths):
    import sqlite3
    conn = sqlite3.connect(paths.database)
    try:
        return conn.execute("SELECT game_time, data FROM snapshots ORDER BY game_time").fetchall()
    finally:
        conn.close()


def test_validate_import_select_apply_agree_across_cli_and_mcp_without_touching_evidence(paths, monkeypatch, capsys):
    from conftest import write_snapshot
    from methodology_helpers import troubled_company
    from tf3companion import mcp_server
    from tf3companion.cli import main
    from tf3companion.service import Companion
    monkeypatch.setenv("TF3C_DATA_DIR", str(paths.data))
    monkeypatch.setenv("TF3C_USERDATA_DIR", str(paths.userdata))
    monkeypatch.setattr(mcp_server, "companion", lambda: Companion(paths))
    write_snapshot(paths.snapshot_folder, troubled_company())
    draft = document("sequence", parameters={"limit": {"value": 3}}, markers={"review": {"label": "Review"}}, rules=[
        {"id": "many", "entity": "line", "outcomes": [
            {"when": {"field": "line.vehicle_count", "op": "gt", "value": {"param": "limit"}}, "marker": "review"}]}])
    source = paths.data.parent / "draft.json"
    source.write_text(json.dumps(draft))

    def cli(*argv):
        code = main(list(argv))
        return code, json.loads(capsys.readouterr().out or "null")

    code, checked = cli("methodology", "validate", str(source), "--strict", "--param", "limit=7")
    assert code == 0 and checked["valid"] and checked["parameters"]["limit"] == 7
    drafted = mcp_server.validate_methodology(content=source.read_text(), parameters={"limit": 7})
    assert drafted["activationEligible"] and drafted["hash"] == checked["hash"]
    assert not paths.database.exists() and not (paths.data / "methodologies").exists()

    assert cli("methodology", "import", str(source))[1]["hash"] == checked["hash"]
    assert cli("methodology", "use", "sequence")[1]["hash"] == checked["hash"]
    assert not paths.database.exists()  # selection needs no snapshot and creates no store
    code, via_cli = cli("analyse", "--json", "--param", "limit=7")
    assert code == 0
    evidence = _stored_snapshots(paths)
    assert evidence

    assert mcp_server.set_save_methodology(None)["target"] == "save-override"
    assert mcp_server.set_methodology_default("sequence")["hash"] == checked["hash"]
    via_mcp = mcp_server.evaluate(parameters={"limit": 7})
    via_mcp_defaults = mcp_server.analyse()
    for applied in (via_cli["methodology"], via_mcp["methodology"], via_mcp_defaults["methodology"]):
        assert applied["hash"] == checked["hash"] and applied["identity"] == "sequence@1.0.0"
    assert via_cli["methodology"]["parameters"] == via_mcp["methodology"]["parameters"] == {"limit": 7}
    assert via_cli["methodology"]["parameterOverrides"] == {"limit": 7}
    assert via_mcp_defaults["methodology"]["parameters"] == {"limit": 3}
    assert _stored_snapshots(paths) == evidence


def test_cli_analyse_without_snapshots_fails_without_writing_reports(paths, monkeypatch, capsys):
    from tf3companion.cli import main
    monkeypatch.setenv("TF3C_DATA_DIR", str(paths.data))
    monkeypatch.setenv("TF3C_USERDATA_DIR", str(paths.userdata))
    assert main(["analyse"]) != 0
    assert not (paths.data / "reports").exists()
