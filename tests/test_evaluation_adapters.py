"""CLI and MCP adapters over the stored-only evaluation."""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Any

import anyio
import pytest
from mcp.server.mcpserver.exceptions import ToolError

from conftest import YEAR
from methodology_helpers import methodology, troubled_company
from tf3companion import mcp_server
from tf3companion.cli import main
from tf3companion.snapshot import Snapshot
from tf3companion.store import Store

EXAMPLE = (
    Path(__file__).parent.parent
    / "src"
    / "tf3companion"
    / "methodology"
    / "examples"
    / "local-feeder-intercity-trunk.tf3c-methodology.json"
)


def seed(data: Path, *raws: dict[str, Any]) -> Path:
    data.mkdir(parents=True, exist_ok=True)
    store = Store(data / "companion.db")
    for raw in raws:
        store.add_snapshot(Snapshot(raw, source="synthetic.lua"))
    store.close()
    return data


def inventory(root: Path) -> dict[str, str | None]:
    return {
        str(p): hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None for p in sorted(root.rglob("*"))
    }


@pytest.fixture
def stored(tmp_path, monkeypatch):
    """Evidence only in the companion store; the Steam userdata directory deliberately does not exist."""
    data = seed(tmp_path / "data", troubled_company())
    monkeypatch.setenv("TF3C_DATA_DIR", str(data))
    monkeypatch.setenv("TF3C_USERDATA_DIR", str(tmp_path / "no-steam"))
    return data


def cli_json(capsys, *args: str) -> dict[str, Any]:
    capsys.readouterr()
    assert main(["evaluate", *args, "--json"]) == 0
    return json.loads(capsys.readouterr().out)


def tool(name: str, arguments: dict[str, Any] | None = None):
    async def go():
        return await mcp_server.server.call_tool(name, arguments or {})

    return anyio.run(go)


def tool_payload(name: str, arguments: dict[str, Any] | None = None) -> Any:
    result = tool(name, arguments)
    if result.structured_content is not None:
        return result.structured_content
    return json.loads(result.content[0].text)


# ---- CLI ----------------------------------------------------------------------------------------------------


def test_cli_evaluates_without_steam_and_changes_nothing(stored, tmp_path, capsys):
    before = inventory(tmp_path)
    result = cli_json(capsys, "--methodology", "default")
    assert result["version"] == 1 and result["snapshot"]["gameTime"] == 10 * YEAR
    assert "outputFolder" not in result and "files" not in result
    assert inventory(tmp_path) == before
    assert not (tmp_path / "no-steam").exists()
    assert main(["analyse", "--methodology", "default"]) == 1  # acquisition-aware commands still need the game folder
    assert "TF3C_USERDATA_DIR" in capsys.readouterr().err


def test_cli_human_output_makes_no_report_claims(stored, capsys):
    capsys.readouterr()
    assert main(["evaluate"]) == 0
    out = capsys.readouterr().out
    assert "Methodology: default@1.0.0" in out and "Findings:" in out
    for claim in ("Output folder", "Files:", "written", "report"):
        assert claim not in out


def test_cli_missing_store_fails_without_creating_it(tmp_path, monkeypatch, capsys):
    missing = tmp_path / "missing"
    monkeypatch.setenv("TF3C_DATA_DIR", str(missing))
    monkeypatch.setenv("TF3C_USERDATA_DIR", str(tmp_path / "no-steam"))
    capsys.readouterr()
    assert main(["evaluate", "--json"]) == 1
    captured = capsys.readouterr()
    assert "No companion database" in captured.err and captured.out == ""
    assert not missing.exists()


def test_cli_explicit_save_scope(stored, tmp_path, capsys):
    seed(stored / "saves" / "alpha", troubled_company())
    before = inventory(tmp_path)
    result = cli_json(capsys, "--save", "alpha")
    assert result["save"]["saveId"] == "alpha" and result["save"]["isolated"] is True
    assert main(["evaluate", "--save", "ghost"]) == 1
    assert "not found" in capsys.readouterr().err
    assert inventory(tmp_path) == before and not (stored / "saves" / "ghost").exists()


def test_cli_one_off_path_and_invalid_overrides(stored, tmp_path, capsys):
    path = tmp_path / "one-off.json"
    path.write_bytes(methodology(id="one-off", parameters={"tolerance": {"value": 1}}).raw)
    before = inventory(tmp_path)
    result = cli_json(capsys, "--methodology", str(path), "--param", "tolerance=5")
    assert result["methodology"]["identity"] == "one-off@1.0.0" and result["methodology"]["origin"] == "file"
    assert result["methodology"]["parameters"]["tolerance"] == 5
    capsys.readouterr()
    assert main(["evaluate", "--methodology", str(path), "--param", "nope=1"]) == 1
    assert main(["evaluate", "--methodology", str(tmp_path / "absent.json")]) == 1
    assert capsys.readouterr().out == ""
    assert inventory(tmp_path) == before


# ---- MCP ----------------------------------------------------------------------------------------------------


def test_mcp_tool_is_registered_with_its_documented_arguments():
    async def listed():
        return {t.name: t for t in await mcp_server.server.list_tools()}

    schema = anyio.run(listed)["evaluate"].input_schema
    assert set(schema["properties"]) == {"methodology", "save", "parameters", "views"} and not schema.get("required")


def test_mcp_and_cli_return_the_same_analytical_result(stored, tmp_path, capsys):
    before = inventory(tmp_path)
    cli = cli_json(capsys, "--methodology", "default")
    machine = tool_payload("evaluate", {"methodology": "default"})
    assert machine == cli
    assert inventory(tmp_path) == before
    implicit = tool_payload("evaluate")
    assert implicit["methodology"]["origin"] == "packaged-default"  # no explicit request: the default applies
    assert implicit["methodology"]["sha256"] == cli["methodology"]["sha256"] and [
        (f["code"], f["title"]) for f in implicit["findings"]
    ] == [(f["code"], f["title"]) for f in cli["findings"]]


def test_mcp_rejects_paths_and_invalid_parameters(stored, tmp_path):
    before = inventory(tmp_path)
    for reference in (str(EXAMPLE), "../x.json", "x.tf3c-methodology.json"):
        with pytest.raises(ToolError, match="(?i)only library ids|methodologies folder"):
            tool("evaluate", {"methodology": reference})
    with pytest.raises(ToolError):
        tool("evaluate", {"methodology": "default", "parameters": {"nope": 1}})
    with pytest.raises(ToolError, match="not found"):
        tool("evaluate", {"save": "ghost"})
    assert inventory(tmp_path) == before


def test_mcp_is_correct_across_repeated_and_concurrent_calls_with_updated_evidence(stored):
    newer = troubled_company()
    newer["meta"]["gameTime"] = 11 * YEAR
    newer["meta"]["date"] = {"year": 1981, "month": 1, "day": 1}
    results: list[dict[str, Any]] = []
    errors: list[BaseException] = []

    def reader() -> None:
        try:
            for _ in range(3):
                results.append(tool_payload("evaluate", {"methodology": "default"}))
        except BaseException as exc:  # reported on the main thread
            errors.append(exc)

    threads = [threading.Thread(target=reader) for _ in range(6)]
    for thread in threads:
        thread.start()
    writer = Store(stored / "companion.db")
    writer.add_snapshot(Snapshot(newer, source="newer.lua"))
    writer.close()
    for thread in threads:
        thread.join()
    assert not errors and len(results) == 18
    for result in results:  # every call is internally consistent with exactly one selected snapshot
        assert result["snapshot"]["gameTime"] in (10 * YEAR, 11 * YEAR)
        assert result["timeBasis"]["selectedTick"] == result["snapshot"]["gameTime"]
        assert result["methodology"]["hash"] == results[0]["methodology"]["hash"]
    assert tool_payload("evaluate", {"methodology": "default"})["snapshot"]["gameTime"] == 11 * YEAR
    assert tool_payload("evaluate", {"methodology": "default"}) == tool_payload("evaluate", {"methodology": "default"})


# ---- analysis views ----------------------------------------------------------------------------------------

ALL_VIEWS = ["bottlenecks", "expansion", "lines-history", "history", "industries", "vehicle-roi", "towns"]


def test_service_cli_and_mcp_return_the_same_requested_views_without_writing(stored, tmp_path, capsys):
    from tf3companion.service import Companion

    before = inventory(tmp_path)
    service = Companion.open_stored()
    try:
        via_service = service.evaluate("default", views=ALL_VIEWS)
        assert service.evaluate("default")["analysisViews"] == {}
        assert service.evaluate("default", views=[])["analysisViews"] == {}
        with pytest.raises(ValueError, match="Unknown view"):
            service.evaluate("default", views=["bottleneck"])
    finally:
        service.close()
    via_cli = cli_json(capsys, "--methodology", "default", *[a for name in ALL_VIEWS for a in ("--view", name)])
    via_mcp = tool_payload("evaluate", {"methodology": "default", "views": ALL_VIEWS})
    assert list(via_service["analysisViews"]) == ALL_VIEWS
    assert via_cli["analysisViews"] == via_service["analysisViews"] == via_mcp["analysisViews"]
    for name, view in via_service["analysisViews"].items():
        assert view["coverage"]["endpoint"]["tick"] == via_service["snapshot"]["gameTime"], name
    two = cli_json(capsys, "--methodology", "default", "--view", "towns", "--view", "bottlenecks", "--view", "towns")
    assert list(two["analysisViews"]) == ["bottlenecks", "towns"]
    assert tool_payload("evaluate", {"views": []})["analysisViews"] == {}
    assert inventory(tmp_path) == before and not (tmp_path / "no-steam").exists()


def test_unknown_view_names_fail_in_every_adapter_before_reading(stored, tmp_path, capsys):
    before = inventory(tmp_path)
    capsys.readouterr()
    assert main(["evaluate", "--view", "reports"]) == 1
    captured = capsys.readouterr()
    assert "Unknown view" in captured.err and captured.out == ""
    with pytest.raises(ToolError, match="Unknown view"):
        tool("evaluate", {"views": ["history", "reports"]})
    with pytest.raises(ToolError):
        tool("evaluate", {"views": "history"})
    assert inventory(tmp_path) == before
