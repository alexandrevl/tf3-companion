"""Packaged methodology resources work from the checkout and from an installed wheel."""
from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from tf3companion.methodology import load_default
from tf3companion.methodology.loader import packaged_files, schema_text

ROOT = Path(__file__).parent.parent


def test_packaged_resources_load_from_the_checkout():
    assert load_default().id == "default"
    names = [name for name, _ in packaged_files()]
    assert names == ["default.json", "examples/local-feeder-intercity-trunk.tf3c-methodology.json"]
    assert '"tf3c-methodology/1"' in schema_text()


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv is needed to build the wheel")
def test_the_built_wheel_contains_the_methodology_json_files(tmp_path):
    subprocess.run(["uv", "build", "--wheel", "-o", str(tmp_path)], cwd=ROOT, check=True, capture_output=True)
    wheel = next(tmp_path.glob("tf3_companion-*.whl"))
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
    assert {
        "tf3companion/methodology/default.json",
        "tf3companion/methodology/schema-1.json",
        "tf3companion/methodology/examples/local-feeder-intercity-trunk.tf3c-methodology.json",
        "tf3companion/knowledge/methodology-fields.md",
    } <= names
