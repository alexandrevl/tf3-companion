"""Generated knowledge topic, documented examples and documented commands stay true."""
from __future__ import annotations

import json
import re
import shlex
import shutil
from pathlib import Path

import pytest

from conftest import write_snapshot
from methodology_helpers import troubled_company
from tf3companion.cli import main
from tf3companion.methodology import fields as F
from tf3companion.methodology import parse
from tf3companion.methodology.catalog_doc import TOPIC, render_catalog, topic_path
from tf3companion.service import Companion

ROOT = Path(__file__).parent.parent
DOCS = {name: (ROOT / name).read_text(encoding="utf-8") for name in
        ("docs/methodologies.md", "docs/reports.md", "docs/agents.md", "README.md")}
EXAMPLE = ROOT / "src" / "tf3companion" / "methodology" / "examples" / "local-feeder-intercity-trunk.tf3c-methodology.json"


def test_knowledge_topic_is_generated_from_the_registry_and_lists_every_field():
    committed = topic_path().read_text(encoding="utf-8")
    assert committed == render_catalog(), "run `uv run python -m tf3companion.methodology.catalog_doc`"
    for spec in F.all_fields():
        assert f"`{spec.name}`" in committed, spec.name
    topic = Companion.knowledge("methodology-fields")["content"]
    assert topic == committed and "methodology-fields" in Companion.knowledge()["topics"]
    assert "vehicle.line.<field>" in committed or "`<entity>.line.<field>`" in committed
    assert "**Not collected yet.**" in committed and "`line.route_km`" in committed
    assert TOPIC == "methodology-fields.md"


def json_blocks(text: str) -> list[str]:
    return re.findall(r"```json\n(.*?)```", text, flags=re.S)


def test_every_complete_methodology_in_the_docs_validates():
    blocks = [b for b in json_blocks(DOCS["docs/methodologies.md"]) if '"schema": "tf3c-methodology/1"' in b]
    assert blocks, "the page must show a complete methodology"
    for block in blocks:
        assert parse(block.encode("utf-8")).identity.startswith("my-methodology@")
    assert parse(EXAMPLE.read_bytes()).id == "local-feeder-intercity-trunk"


def test_documented_fragments_are_valid_json_conditions():
    fragments = [b for b in json_blocks(DOCS["docs/methodologies.md"]) if '"schema"' not in b]
    assert fragments
    for fragment in fragments:
        text = fragment.strip()
        json.loads(text if text.startswith(("{", "[")) else "{" + text + "}")


def commands(markdown: str) -> list[list[str]]:
    out = []
    for block in re.findall(r"```(?:sh|bash)\n(.*?)```", markdown, flags=re.S):
        for line in block.splitlines():
            line = line.strip().removeprefix("uv run ")
            if not line.startswith("tf3c "):
                continue
            words = shlex.split(line)[1:]
            if words[:1] in (["methodology"], ["analyse"]) or "--methodology" in words or words[:2] == ["report", "methodology"]:
                out.append(words)
    return out


@pytest.mark.parametrize("doc", ["docs/methodologies.md", "docs/reports.md", "README.md"])
def test_documented_commands_run_as_written_against_a_fixture_data_directory(doc, tmp_path, monkeypatch, capsys):
    data, userdata, work = tmp_path / "data", tmp_path / "userdata", tmp_path / "work"
    work.mkdir()
    monkeypatch.setenv("TF3C_DATA_DIR", str(data))
    monkeypatch.setenv("TF3C_USERDATA_DIR", str(userdata))
    monkeypatch.chdir(work)
    write_snapshot(userdata / "towns_industries", troubled_company())
    drafted = json_blocks(DOCS["docs/methodologies.md"])[0]  # a methodology drafted by following the page
    (work / "my-methodology.tf3c-methodology.json").write_text(drafted, encoding="utf-8")
    target = work / "src" / "tf3companion" / "methodology" / "examples"
    target.mkdir(parents=True)
    shutil.copy(EXAMPLE, target / EXAMPLE.name)
    ran = commands(DOCS[doc])
    assert ran, f"{doc} should show methodology commands"
    for words in ran:
        code = main(words)
        captured = capsys.readouterr()
        assert code == 0, f"`tf3c {' '.join(words)}` failed: {captured.err}"
    if doc == "docs/methodologies.md":
        assert (work / "shared-copy.tf3c-methodology.json").is_file()
        assert (data / "methodologies" / "my-methodology@1.0.0.tf3c-methodology.json").is_file()
