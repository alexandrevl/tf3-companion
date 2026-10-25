"""Lens-folder output layout, manifests, `analyse` and the report cutover."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import YEAR, write_snapshot
from methodology_helpers import companion_with, methodology, troubled_company
from tf3companion.cli import main
from tf3companion.methodology import output
from tf3companion.methodology.library import Library
from tf3companion.service import Companion, NoSnapshotError

SRC = Path(__file__).parent.parent / "src" / "tf3companion" / "methodology"
EXAMPLE = "local-feeder-intercity-trunk"
LADDER = Path(__file__).parent / "fixtures" / "methodologies" / "mode-ladder.tf3c-methodology.json"


def folders(root: Path) -> list[str]:
    return sorted(p.name for p in (root / "reports").iterdir() if p.is_dir())


def test_analyse_summary_and_bundle_contents(paths):
    companion = companion_with(paths, troubled_company())
    try:
        summary = companion.analyse(EXAMPLE)
    finally:
        companion.close()
    assert summary["methodology"]["identity"] == "local-feeder-intercity-trunk@1.0.0"
    assert summary["methodology"]["origin"] == "request" and summary["methodology"]["hash"].startswith("sha256:")
    assert summary["save"]["isolated"] is False and "not isolated" in summary["save"]["note"]
    assert summary["roles"]["line"]["roles"].keys() == {"local-passenger", "intercity-passenger", "freight"}
    assert set(summary["markersByRule"]) >= {"intercity-result", "freight-result", "town-feeder-balance"}
    assert summary["findings"]["bySource"].keys() >= {"engine", "methodology"}
    assert summary["recommendations"] and summary["recommendations"][0]["untrusted"] is True
    folder = Path(summary["outputFolder"])
    assert folder == paths.data / "reports" / "1980-01-01__local-feeder-intercity-trunk@1.0.0"
    assert sorted(summary["files"]) == sorted(p.name for p in folder.iterdir())
    assert {"company.md", "lines-history.md", "towns.md", "cargo.md", "fleet.md", "methodology.md", "manifest.json"} == set(summary["files"])
    manifest = json.loads((folder / "manifest.json").read_text())
    assert manifest["methodology"]["identity"] == "local-feeder-intercity-trunk@1.0.0"
    assert manifest["methodology"]["parameters"]["intercity_loss_alert"] == 100_000
    assert manifest["snapshot"] == {"date": "1980-01-01", "gameTime": 10 * YEAR}
    assert manifest["save"]["isolated"] is False and manifest["files"] == sorted(summary["files"])
    assert "counts" in manifest and "skipped" in manifest and "unsupported" in manifest and "notEvaluable" in manifest
    assert "Coverage" in (folder / "methodology.md").read_text()


def test_rerun_is_idempotent_and_overwrites_the_same_folder(paths):
    companion = companion_with(paths, troubled_company())
    try:
        first = companion.analyse(EXAMPLE)
        stale = Path(first["outputFolder"]) / "stale.md"
        stale.write_text("left over from nowhere")
        second = companion.analyse(EXAMPLE)
    finally:
        companion.close()
    assert first["outputFolder"] == second["outputFolder"]
    assert folders(paths.data) == ["1980-01-01__local-feeder-intercity-trunk@1.0.0"]
    assert not stale.exists()  # the folder is replaced as a whole
    assert not [p for p in (paths.data / "reports").iterdir() if p.name.startswith(".")]  # no temporary siblings left


def test_two_lenses_coexist_for_the_same_game_date(paths):
    companion = companion_with(paths, troubled_company())
    try:
        companion.analyse(EXAMPLE)
        before = (paths.data / "reports" / "1980-01-01__local-feeder-intercity-trunk@1.0.0" / "manifest.json").read_text()
        companion.analyse("default")
        after = (paths.data / "reports" / "1980-01-01__local-feeder-intercity-trunk@1.0.0" / "manifest.json").read_text()
    finally:
        companion.close()
    assert folders(paths.data) == ["1980-01-01__default@1.0.0", "1980-01-01__local-feeder-intercity-trunk@1.0.0"]
    assert before == after  # the first lens folder was not touched


def test_default_lens_generates_the_standard_set_plus_verdicts(paths):
    companion = companion_with(paths, troubled_company())
    try:
        summary = companion.analyse()
    finally:
        companion.close()
    assert summary["methodology"]["origin"] == "packaged-default"
    assert set(summary["files"]) == {"company.md", "lines.md", "fleet.md", "cargo.md", "methodology.md", "manifest.json"}


def test_two_saves_stay_apart(paths):
    for save in ("save-a", "save-b"):
        (paths.data / "saves" / save).mkdir(parents=True)
    write_snapshot(paths.snapshot_folder, troubled_company())
    a, b = Companion(paths, save="save-a"), Companion(paths, save="save-b")
    try:
        a.resolver.use(EXAMPLE)
        out_a, out_b = a.analyse(), b.analyse()
    finally:
        a.close()
        b.close()
    assert out_a["methodology"]["identity"].startswith(EXAMPLE) and out_b["methodology"]["identity"] == "default@1.0.0"
    assert Path(out_a["outputFolder"]).parts[-4:-2] == ("saves", "save-a")
    assert out_a["save"]["isolated"] is True and out_a["save"].get("note") is None
    assert folders(paths.data / "saves" / "save-a") == ["1980-01-01__local-feeder-intercity-trunk@1.0.0"]
    assert folders(paths.data / "saves" / "save-b") == ["1980-01-01__default@1.0.0"]
    assert not (paths.data / "reports").exists()  # the implicit save's reports folder is not shared


def test_renaming_the_save_label_does_not_move_files(paths):
    save = paths.data / "saves" / "stable-id"
    save.mkdir(parents=True)
    (save / "save.json").write_text(json.dumps({"label": "Old label"}))
    write_snapshot(paths.snapshot_folder, troubled_company())
    companion = Companion(paths, save="stable-id")
    try:
        first = companion.analyse()
        (save / "save.json").write_text(json.dumps({"label": "A completely new label"}))
        second = companion.analyse()
    finally:
        companion.close()
    assert first["outputFolder"] == second["outputFolder"]
    assert folders(save) == ["1980-01-01__default@1.0.0"]


def test_interrupted_write_leaves_the_previous_folder_intact(paths, monkeypatch):
    companion = companion_with(paths, troubled_company())
    try:
        first = Path(companion.analyse(EXAMPLE)["outputFolder"])
        snapshot_before = {p.name: p.read_bytes() for p in first.iterdir()}
        real = output.atomic_write
        calls = []

        def failing(path, content):
            calls.append(path.name)
            if len(calls) == 3:
                raise OSError("disk full")
            real(path, content)

        monkeypatch.setattr(output, "atomic_write", failing)
        with pytest.raises(OSError, match="disk full"):
            companion.analyse(EXAMPLE)
    finally:
        companion.close()
    assert {p.name: p.read_bytes() for p in first.iterdir()} == snapshot_before
    assert folders(paths.data) == ["1980-01-01__local-feeder-intercity-trunk@1.0.0"]
    assert not [p for p in (paths.data / "reports").iterdir() if p.name.startswith(".")]


def test_snapshot_without_a_calendar_date_uses_the_game_time_name(paths):
    data = troubled_company()
    data["meta"].pop("date")
    companion = companion_with(paths, data)
    try:
        summary = companion.analyse("default")
    finally:
        companion.close()
    assert Path(summary["outputFolder"]).name == f"t{10 * YEAR}__default@1.0.0"


def test_no_snapshot_fails_and_writes_nothing(paths):
    companion = Companion(paths)
    try:
        with pytest.raises(NoSnapshotError):
            companion.analyse()
        with pytest.raises(NoSnapshotError):
            companion.report("company")
    finally:
        companion.close()
    assert not (paths.data / "reports").exists()


def test_skipped_rules_are_visible_in_summary_report_and_manifest(paths):
    draft = methodology(rules=[{
        "id": "maintenance", "entity": "vehicle",
        "outcomes": [{"when": {"field": "vehicle.maintenance_state", "op": "lt", "value": 0.7}, "marker": "problem"}],
    }])
    draft_file = paths.userdata / "maintenance.json"
    draft_file.write_bytes(draft.raw)
    Library(paths.data).import_file(draft_file)
    observed = troubled_company()
    for vehicle in observed["vehicles"]:
        vehicle.pop("maintenanceState", None)
    companion = companion_with(paths, observed)
    try:
        summary = companion.analyse("test")
    finally:
        companion.close()
    assert [(i["kind"], i["id"]) for i in summary["skipped"]] == [("rule", "maintenance")]
    folder = Path(summary["outputFolder"])
    assert json.loads((folder / "manifest.json").read_text())["skipped"][0]["id"] == "maintenance"


def test_single_report_is_written_into_the_lens_folder_with_latest_copy(paths):
    companion = companion_with(paths, troubled_company())
    try:
        with pytest.raises(LookupError, match="No report generated yet"):
            companion.latest_report()
        result = companion.report("company", html=True)
        annual = companion.report("annual")
    finally:
        companion.close()
    folder = paths.data / "reports" / "1980-01-01__default@1.0.0"
    assert result["file"] == str(folder / "company.md") and result["html_file"] == str(folder / "company.html")
    assert (folder / "company.md").read_text() == result["markdown"]
    assert "**Methodology:** default@1.0.0" in result["markdown"]
    assert (paths.data / "reports" / "latest.md").read_text() == annual["markdown"]
    assert Path(annual["file"]).name == "annual-1980.md"
    assert not (paths.data / "reports" / "company.md").exists()  # the old flat layout is gone
    manifest = json.loads((folder / "manifest.json").read_text())
    assert {"company.md", "company.html", "annual-1980.md", "manifest.json"} <= set(manifest["files"])
    companion = Companion(paths)
    try:
        assert companion.latest_report() == annual["markdown"]
    finally:
        companion.close()


def test_cli_analyse_end_to_end(tmp_path, monkeypatch, capsys):
    data, userdata = tmp_path / "data", tmp_path / "userdata"
    monkeypatch.setenv("TF3C_DATA_DIR", str(data))
    monkeypatch.setenv("TF3C_USERDATA_DIR", str(userdata))
    write_snapshot(userdata / "towns_industries", troubled_company())
    assert main(["methodology", "import", str(SRC / "examples" / f"{EXAMPLE}.tf3c-methodology.json")]) == 0
    assert main(["methodology", "use", EXAMPLE]) == 0
    capsys.readouterr()
    assert main(["analyse"]) == 0
    capsys.readouterr()
    first_manifest = data / "reports" / "1980-01-01__local-feeder-intercity-trunk@1.0.0" / "manifest.json"
    before = first_manifest.read_bytes()
    assert json.loads(before)["selection"]["origin"] == "save-override"
    assert main(["analyse", "--methodology", "default", "--param", "x=1"]) == 1  # default has no parameters
    assert first_manifest.read_bytes() == before
    assert main(["analyse", "--methodology", "default"]) == 0
    assert folders(data) == ["1980-01-01__default@1.0.0", "1980-01-01__local-feeder-intercity-trunk@1.0.0"]
    capsys.readouterr()
    assert main(["findings", "--json", "--methodology", "default"]) == 0
    items = json.loads(capsys.readouterr().out)
    assert {i["methodology"] for i in items} == {"default@1.0.0"} and {i["source"] for i in items} == {"engine"}
    assert main(["analyse", "--methodology", str(tmp_path / "missing.json")]) == 1


def test_selection_provenance_reaches_summary_manifest_header_and_findings(paths):
    companion = companion_with(paths, troubled_company())
    try:
        summary = companion.analyse(EXAMPLE)
        found = companion.findings(methodology=EXAMPLE)
    finally:
        companion.close()
    expected = summary["methodology"]["selection"]
    assert expected["origin"] == "request" and expected["reference"] == EXAMPLE
    assert expected["libraryRoot"] == str(paths.data)
    folder = Path(summary["outputFolder"])
    assert json.loads((folder / "manifest.json").read_text())["selection"] == expected
    header = (folder / "methodology.md").read_text()
    assert "**Selection:**" in header and "request" in header.split("**Selection:**")[1].splitlines()[0]
    assert found and all(f["methodology_selection"] == expected for f in found)


def test_analyse_summary_is_a_presentation_of_the_same_evaluation(paths):
    companion = companion_with(paths, troubled_company())
    try:
        summary = companion.analyse(EXAMPLE)
        evaluation = companion.evaluate(EXAMPLE)
    finally:
        companion.close()
    assert summary["methodology"] == evaluation["methodology"] and summary["snapshot"] == evaluation["snapshot"]
    assert summary["findings"]["bySeverity"] == {
        severity: sum(f["severity"] == severity for f in evaluation["findings"])
        for severity in {f["severity"] for f in evaluation["findings"]}}
    assert summary["recommendations"] == evaluation["recommendations"][:15]
    assert "outputFolder" not in evaluation and "files" not in evaluation
    assert not any(p.name == "evaluation.json" for p in Path(summary["outputFolder"]).iterdir())
