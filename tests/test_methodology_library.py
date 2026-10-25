"""Library, CLI commands, per-save binding, resolution precedence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tf3companion.cli import main
from tf3companion.methodology import MethodologyError
from tf3companion.methodology.library import Library, LibraryError
from tf3companion.methodology.resolve import Resolver, validate_file
from tf3companion.methodology.scope import SaveScope

PACKAGED = Path(__file__).parent.parent / "src" / "tf3companion" / "methodology" / "examples"
EXAMPLE = PACKAGED / "local-feeder-intercity-trunk.tf3c-methodology.json"
FIXTURES = Path(__file__).parent / "fixtures" / "methodologies"
OIL = FIXTURES / "oil-chemicals-chain.tf3c-methodology.json"
LADDER = FIXTURES / "mode-ladder.tf3c-methodology.json"


def doc(ident="sample", version="1.0.0", **extra):
    return {
        "schema": "tf3c-methodology/1",
        "id": ident,
        "version": version,
        "name": f"Sample {version}",
        "description": "A sample.",
        **extra,
    }


def drop(data_dir: Path, name: str, data) -> Path:
    folder = data_dir / "methodologies"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
    return path


# ---- library ---------------------------------------------------------------------------------------


def test_read_only_listing_shows_packaged_files_and_creates_no_folder(tmp_path):
    entries = Library(tmp_path / "data").entries()
    assert {e.identity for e in entries} == {"default@1.0.0", "local-feeder-intercity-trunk@1.0.0"}
    assert all(e.source == "packaged" and e.status == "valid" for e in entries)
    assert not (tmp_path / "data").exists()
    Resolver(tmp_path / "data").listing()
    assert not (tmp_path / "data").exists()


def test_drop_in_file_is_listed_without_any_command(tmp_path):
    drop(tmp_path, "sample@1.0.0.tf3c-methodology.json", doc())
    rows = {e["identity"]: e for e in Resolver(tmp_path).listing()["methodologies"]}
    assert rows["sample@1.0.0"]["source"] == "user" and rows["sample@1.0.0"]["status"] == "valid"
    assert rows["sample@1.0.0"]["name"] == "Sample 1.0.0" and rows["sample@1.0.0"]["file"].endswith(
        ".tf3c-methodology.json"
    )


def test_invalid_file_is_isolated_and_other_files_remain_usable(tmp_path):
    drop(tmp_path, "good.tf3c-methodology.json", doc("good"))
    drop(tmp_path, "bad.tf3c-methodology.json", doc("bad", rulez=[]))
    drop(tmp_path, "broken.tf3c-methodology.json", "{not json")
    drop(tmp_path, "notes.txt", "ignored: wrong extension")
    library = Library(tmp_path)
    by_file = {Path(e.file).name: e for e in library.entries() if e.source == "user"}
    assert by_file["good.tf3c-methodology.json"].status == "valid"
    assert (
        by_file["bad.tf3c-methodology.json"].status == "invalid"
        and "rulez" in by_file["bad.tf3c-methodology.json"].error
    )
    assert (
        by_file["broken.tf3c-methodology.json"].status == "invalid"
        and "invalid JSON" in by_file["broken.tf3c-methodology.json"].error
    )
    assert "notes.txt" not in by_file
    assert library.resolve("good").identity == "good@1.0.0"
    with pytest.raises(LibraryError, match="invalid file"):
        library.resolve("bad")


def test_conflicting_duplicates_name_both_files_and_block_use(tmp_path):
    a = drop(tmp_path, "a.tf3c-methodology.json", doc("dup", description="one"))
    b = drop(tmp_path, "b.tf3c-methodology.json", doc("dup", description="two"))
    library = Library(tmp_path)
    statuses = {Path(e.file).name: e.status for e in library.entries() if e.id == "dup"}
    assert statuses == {"a.tf3c-methodology.json": "conflict", "b.tf3c-methodology.json": "conflict"}
    for ref in ("dup", "dup@1.0.0"):
        with pytest.raises(LibraryError) as info:
            library.resolve(ref)
        assert str(a) in str(info.value) and str(b) in str(info.value) and "different content" in str(info.value)


def test_same_content_twice_is_not_a_conflict(tmp_path):
    drop(tmp_path, "a.tf3c-methodology.json", doc("same"))
    drop(tmp_path, "b.tf3c-methodology.json", doc("same"))
    assert Library(tmp_path).resolve("same").identity == "same@1.0.0"


def test_bare_id_resolves_to_the_highest_valid_version(tmp_path):
    for version in ("1.2.0", "1.10.0", "1.9.9"):
        drop(tmp_path, f"s{version}.tf3c-methodology.json", doc("multi", version))
    library = Library(tmp_path)
    assert library.resolve("multi").version == "1.10.0"  # numeric, not lexical, ordering
    assert library.resolve("multi@1.2.0").version == "1.2.0"
    with pytest.raises(LibraryError, match="not in the library"):
        library.resolve("multi@9.9.9")
    with pytest.raises(LibraryError, match="Only library ids"):
        library.resolve("../escape")


# ---- import / export ---------------------------------------------------------------------------------------


def test_import_copies_under_a_name_derived_from_identity_and_round_trips_the_hash(tmp_path):
    here, there = tmp_path / "here", tmp_path / "there"
    first = Library(here).import_file(EXAMPLE)
    assert Path(first["file"]).name == "local-feeder-intercity-trunk@1.0.0.tf3c-methodology.json"
    exported = tmp_path / "shared.json"
    Library(here).export("local-feeder-intercity-trunk", exported)
    assert exported.read_bytes() == EXAMPLE.read_bytes()
    second = Library(there).import_file(exported)
    assert first["hash"] == second["hash"] == Library(there).resolve("local-feeder-intercity-trunk").short_hash
    assert Library(there).import_file(exported)["result"] == "unchanged"
    with pytest.raises(LibraryError, match="already exists"):
        Library(there).export("local-feeder-intercity-trunk", exported)


def test_import_refuses_invalid_files_and_different_content_unless_forced(tmp_path):
    library = Library(tmp_path)
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(doc(rulez=[])))
    with pytest.raises(MethodologyError, match="rulez"):
        library.import_file(bad)
    assert not (tmp_path / "methodologies").exists()  # nothing was copied or created
    one, two = tmp_path / "one.json", tmp_path / "two.json"
    one.write_text(json.dumps(doc(description="one")))
    two.write_text(json.dumps(doc(description="two")))
    library.import_file(one)
    with pytest.raises(LibraryError) as info:
        library.import_file(two)
    assert "sha256:" in str(info.value) and "--force" in str(info.value)
    assert library.import_file(two, force=True)["result"] == "imported"
    assert library.resolve("sample").short_hash.startswith("sha256:")


def test_import_cannot_shadow_a_packaged_identity(tmp_path):
    altered = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    altered["description"] = "tampered"
    path = tmp_path / "t.json"
    path.write_text(json.dumps(altered))
    with pytest.raises(LibraryError, match="packaged"):
        Library(tmp_path / "data").import_file(path, force=True)


# ---- CLI --------------------------------------------------------------------------------------------------------------


@pytest.fixture
def cli_env(tmp_path, monkeypatch):
    data = tmp_path / "data"
    monkeypatch.setenv("TF3C_DATA_DIR", str(data))
    monkeypatch.setenv("TF3C_USERDATA_DIR", str(tmp_path / "userdata"))
    return data


def run_cli(capsys, *argv):
    code = main(list(argv))
    out = capsys.readouterr()
    return code, out.out, out.err


def test_cli_validate_reports_errors_and_unsupported_rules(cli_env, capsys, tmp_path):
    code, out, _ = run_cli(capsys, "methodology", "validate", str(EXAMPLE), "--strict")
    assert code == 0 and json.loads(out)["valid"] is True
    code, out, _ = run_cli(capsys, "methodology", "validate", str(OIL), "--strict")
    assert code == 0
    code, out, _ = run_cli(capsys, "methodology", "validate", str(LADDER))
    result = json.loads(out)
    assert code == 0 and [r["id"] for r in result["unsupported"]] == ["mode-by-distance"]
    code, out, _ = run_cli(capsys, "methodology", "validate", str(LADDER), "--strict")
    result = json.loads(out)
    assert code == 1 and result["valid"] is False
    assert result["unsupported"][0]["reason"].startswith("missing data: station positions")
    assert "stations[].position" in result["unsupported"][0]["needs"]
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(doc(rulez=[])))
    code, out, _ = run_cli(capsys, "methodology", "validate", str(bad))
    assert code == 1 and "rulez" in json.loads(out)["errors"][0]
    assert not cli_env.exists()  # validate never imports or creates the library


def test_cli_typo_field_is_reported_as_unsupported_strictly(cli_env, capsys, tmp_path):
    typo = tmp_path / "typo.json"
    typo.write_text(
        json.dumps(
            doc(
                markers={"ok": {"label": "ok"}},
                rules=[
                    {
                        "id": "r",
                        "entity": "line",
                        "outcomes": [{"when": {"field": "line.profit_yeer", "op": "lt", "value": 0}, "marker": "ok"}],
                    }
                ],
            )
        )
    )
    assert run_cli(capsys, "methodology", "validate", str(typo))[0] == 0
    code, out, _ = run_cli(capsys, "methodology", "validate", str(typo), "--strict")
    assert code == 1 and "did you mean 'line.profit_year'" in json.loads(out)["unsupported"][0]["reason"]


def test_cli_import_export_list_use_unuse_and_fields(cli_env, capsys, tmp_path):
    code, out, _ = run_cli(capsys, "methodology", "list")
    assert code == 0 and "default@1.0.0" in out and "no per-save isolation" in out and not cli_env.exists()
    sample = tmp_path / "sample.json"
    sample.write_text(json.dumps(doc()))
    code, out, _ = run_cli(capsys, "methodology", "import", str(sample))
    assert code == 0 and json.loads(out)["identity"] == "sample@1.0.0"
    code, out, _ = run_cli(capsys, "methodology", "list")
    assert "sample@1.0.0" in out and "user" in out
    exported = tmp_path / "out.json"
    assert run_cli(capsys, "methodology", "export", "sample", str(exported))[0] == 0
    assert exported.read_bytes() == sample.read_bytes()
    assert run_cli(capsys, "methodology", "use", "sample")[0] == 0
    code, out, _ = run_cli(capsys, "methodology", "list", "--json")
    listing = json.loads(out)
    assert listing["effective"] == "sample@1.0.0" and listing["origin"] == "save-override"
    assert listing["saveOverride"]["reference"] == "sample"
    assert [e["selectedAsSaveOverride"] for e in listing["methodologies"] if e["identity"] == "sample@1.0.0"] == [True]
    assert (cli_env / "methodology.json").read_text().strip().startswith("{")
    assert run_cli(capsys, "methodology", "unuse")[0] == 0
    assert json.loads(run_cli(capsys, "methodology", "list", "--json")[1])["effective"] == "default@1.0.0"
    code, out, _ = run_cli(capsys, "methodology", "fields", "--entity", "stop")
    assert {r["name"] for r in json.loads(out)} >= {"stop.station", "stop.terminal", "stop.town"}
    code, _, err = run_cli(capsys, "methodology", "use", "missing-one")
    assert code == 1 and "not in the library" in err


def test_cli_export_import_hash_round_trip_between_machines(cli_env, capsys, tmp_path, monkeypatch):
    assert run_cli(capsys, "methodology", "import", str(EXAMPLE))[0] == 0
    exported = tmp_path / "shared.tf3c-methodology.json"
    assert run_cli(capsys, "methodology", "export", "local-feeder-intercity-trunk@1.0.0", str(exported))[0] == 0
    monkeypatch.setenv("TF3C_DATA_DIR", str(tmp_path / "other-machine"))
    code, out, _ = run_cli(capsys, "methodology", "import", str(exported))
    assert code == 0
    other = Library(tmp_path / "other-machine").resolve("local-feeder-intercity-trunk")
    assert (
        json.loads(out)["hash"]
        == other.short_hash
        == Library(cli_env).resolve("local-feeder-intercity-trunk").short_hash
    )


# ---- per-save binding and resolution -----------------------------------------------------------------------------------


def test_two_scopes_keep_different_bindings(tmp_path):
    data = tmp_path / "data"
    for save in ("save-a", "save-b"):
        (data / "saves" / save).mkdir(parents=True)
    drop(data, "s.tf3c-methodology.json", doc("sample"))
    drop(data, "o.tf3c-methodology.json", doc("oil-chain"))
    a, b = Resolver(data, "save-a"), Resolver(data, "save-b")
    a.use("sample")
    b.use("oil-chain@1.0.0")
    assert a.resolve()[0].id == "sample" and b.resolve()[0].id == "oil-chain"
    assert a.resolve()[1] == "save-override"
    assert a.scope.isolated and a.scope.metadata == data / "saves" / "save-a" / "save.json"
    assert Resolver(data).resolve()[1] == "packaged-default"  # the implicit save is untouched
    assert json.loads((data / "saves" / "save-b" / "save.json").read_text()) == {"methodology": "oil-chain@1.0.0"}


def test_binding_keeps_other_save_metadata(tmp_path):
    (tmp_path / "saves" / "s1").mkdir(parents=True)
    meta = tmp_path / "saves" / "s1" / "save.json"
    meta.write_text(json.dumps({"label": "My first save"}))
    resolver = Resolver(tmp_path, "s1")
    resolver.use("default")
    assert json.loads(meta.read_text()) == {"label": "My first save", "methodology": "default"}
    resolver.unuse()
    assert json.loads(meta.read_text()) == {"label": "My first save"}


def test_fallback_scope_does_not_claim_isolation(tmp_path):
    scope = SaveScope.fallback(tmp_path)
    assert scope.describe()["isolated"] is False and "not isolated" in scope.describe()["note"]
    assert scope.metadata == tmp_path / "methodology.json" and scope.reports == tmp_path / "reports"
    with pytest.raises(LookupError, match="not found"):
        SaveScope.for_save(tmp_path, "nope")
    with pytest.raises(ValueError, match="Invalid save id"):
        SaveScope.for_save(tmp_path, "../escape")


def test_precedence_request_over_binding_over_default(tmp_path):
    drop(tmp_path, "s.tf3c-methodology.json", doc("sample"))
    drop(tmp_path, "t.tf3c-methodology.json", doc("other"))
    resolver = Resolver(tmp_path)
    assert resolver.resolve()[1] == "packaged-default"
    resolver.use("sample")
    assert resolver.resolve()[0].id == "sample"
    m, origin = resolver.resolve("other")
    assert (m.id, origin) == ("other", "request")
    assert resolver.scope.binding() == "sample"  # an explicit request never rebinds


def test_broken_binding_is_an_error_not_a_silent_default(tmp_path):
    path = drop(tmp_path, "s.tf3c-methodology.json", doc("sample"))
    resolver = Resolver(tmp_path)
    resolver.use("sample")
    path.unlink()
    with pytest.raises(LibraryError):
        resolver.resolve()
    assert resolver.scope.binding() == "sample"
    listing = resolver.listing()
    assert listing["effective"] is None and listing["saveOverride"]["reference"] == "sample"


def test_path_is_allowed_once_on_the_cli_and_rejected_for_mcp(tmp_path):
    resolver = Resolver(tmp_path)
    m, origin = resolver.resolve(str(OIL), allow_path=True)
    assert (m.identity, origin) == ("oil-chemicals-chain@0.1.0", "file") and not (tmp_path / "methodologies").exists()
    assert resolver.scope.binding() is None
    with pytest.raises(LibraryError) as info:
        resolver.resolve(str(OIL))
    assert "file path" in str(info.value) and "methodologies folder" in str(info.value) and "import" in str(info.value)
    with pytest.raises(LibraryError, match="Only library ids"):
        resolver.resolve("some name with spaces")


def test_validate_file_without_a_snapshot_lists_needed_data():
    result = validate_file(str(EXAMPLE), strict=True)
    needs = {n for row in result["rules"] for n in row["needs"]}
    assert result["valid"] and "lines[].profitYear" in needs and "lines[].stops[].terminal" in needs


def test_cli_validate_effective_params_reports_override_diagnostics_and_exit_codes(cli_env, capsys, tmp_path):
    draft = tmp_path / "params.json"
    draft.write_text(
        json.dumps(
            doc(
                parameters={"limit": {"value": 3}, "pattern": {"value": "^T"}},
                markers={"m": {"label": "M"}},
                rules=[
                    {
                        "id": "named",
                        "entity": "line",
                        "outcomes": [
                            {
                                "when": {"field": "line.name", "op": "matches", "value": {"param": "pattern"}},
                                "marker": "m",
                            }
                        ],
                    }
                ],
            )
        )
    )
    code, out, _ = run_cli(capsys, "methodology", "validate", str(draft), "--strict", "--param", "limit=5")
    result = json.loads(out)
    assert code == 0 and result["valid"] and result["parameterOverrides"] == {"limit": 5}
    for bad in ("unknown=1", 'limit="text"', "limit=true"):
        code, out, _ = run_cli(capsys, "methodology", "validate", str(draft), "--param", bad)
        result = json.loads(out)  # plain mode keeps structural validity but exposes ineligibility
        assert code == 0 and result["valid"] and result["structurallyValid"] and not result["activationEligible"]
        [issue] = result["diagnostics"]
        assert issue["category"] == "override" and issue["path"].startswith("/overrides/")
        code, out, _ = run_cli(capsys, "methodology", "validate", str(draft), "--strict", "--param", bad)
        assert code == 1 and not json.loads(out)["valid"]
    code, out, _ = run_cli(capsys, "methodology", "validate", str(draft), "--strict", "--param", "pattern=(a+)+$")
    [issue] = json.loads(out)["diagnostics"]
    assert code == 1 and issue["code"] == "invalid-effective-policy" and issue["ruleId"] == "named"
    assert issue["relatedPaths"] == ["/rules/0/outcomes/0/when/value/param"]
    assert run_cli(capsys, "methodology", "validate", str(draft))[0] == 0  # same draft without the override
    assert not cli_env.exists()


def test_cli_validate_multi_error_draft_returns_every_independent_diagnostic(cli_env, capsys, tmp_path):
    draft = tmp_path / "many.json"
    draft.write_text(
        json.dumps(
            doc(
                markers={"m": {"label": "M"}},
                parameters={"p": {"value": []}},
                surprise=1,
                rules=[
                    {
                        "id": "r",
                        "entity": "line",
                        "outcomes": [
                            {"when": {"field": "line.profit_year", "op": "lt", "value": "x"}, "marker": "nope"}
                        ],
                    }
                ],
            )
        )
    )
    code, out, _ = run_cli(capsys, "methodology", "validate", str(draft))
    result = json.loads(out)
    paths = {d["path"] for d in result["diagnostics"]}
    assert code == 1 and not result["valid"] and not result["structurallyValid"]
    assert {"/surprise", "/parameters/p/value"} <= paths and len(result["diagnostics"]) >= 3
    assert all({"category", "code", "severity", "path", "message"} <= d.keys() for d in result["diagnostics"])
    assert len(result["errors"]) == len(result["diagnostics"])
    broken = tmp_path / "broken.json"
    broken.write_text('{"schema":\n nope}')
    code, out, _ = run_cli(capsys, "methodology", "validate", str(broken), "--strict")
    syntax = json.loads(out)["diagnostics"][0]
    assert code == 1 and syntax["category"] == "syntax" and syntax["line"] == 2
    code, out, _ = run_cli(capsys, "methodology", "validate", str(tmp_path / "missing.json"))
    assert code == 1 and json.loads(out)["diagnostics"][0]["category"] == "io"
    assert not cli_env.exists()
