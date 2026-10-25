"""Release helpers: a tag must match the package version; the bridge archive is the mod folder."""

from __future__ import annotations

import importlib.util
import json
import sys
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("release_assets", REPO / "scripts" / "release_assets.py")
release = importlib.util.module_from_spec(SPEC)
sys.modules["release_assets"] = release
SPEC.loader.exec_module(release)


def fake_repo(
    tmp_path: Path,
    declared: str = "1.2.3",
    fallback: str | None = None,
    revision: int = 7,
    changelog: str | None = None,
) -> Path:
    (tmp_path / "src" / "tf3companion").mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text(f'[project]\nname = "x"\nversion = "{declared}"\n', encoding="utf-8")
    (tmp_path / "src" / "tf3companion" / "__init__.py").write_text(
        f'__version__ = "{fallback or declared}"\n', encoding="utf-8"
    )
    (tmp_path / "CHANGELOG.md").write_text(
        changelog if changelog is not None else f"# Changelog\n\n## {declared} (unreleased)\n\n- x\n", encoding="utf-8"
    )
    mod = tmp_path / "mod" / "tf3_companion_bridge"
    (mod / "content").mkdir(parents=True)
    (mod / "mod.json").write_text(json.dumps({"modId": "tf3_companion_bridge", "revision": revision}), encoding="utf-8")
    (mod / "content" / "bridge.lua").write_text("return 1\n", encoding="utf-8")
    return tmp_path


def test_matching_tag_returns_the_version(tmp_path):
    assert release.check_tag("v1.2.3", fake_repo(tmp_path)) == "1.2.3"


@pytest.mark.parametrize("tag", ["v1.2.4", "1.2.3", "v1.2", "release-1.2.3", ""])
def test_a_tag_that_differs_or_is_malformed_fails(tmp_path, tag):
    with pytest.raises(ValueError):
        release.check_tag(tag, fake_repo(tmp_path))


def test_a_stale_source_fallback_version_fails_even_when_the_tag_matches(tmp_path):
    repo = fake_repo(tmp_path, declared="1.2.3", fallback="1.2.2")
    with pytest.raises(ValueError, match="fallback"):
        release.check_tag("v1.2.3", repo)


def test_a_release_without_a_changelog_section_fails(tmp_path):
    repo = fake_repo(tmp_path, changelog="# Changelog\n\n## 1.2.2\n\n- older\n")
    with pytest.raises(ValueError, match="CHANGELOG"):
        release.check_tag("v1.2.3", repo)


def test_the_checked_in_repository_has_one_version_everywhere():
    assert release.fallback_version() == release.package_version()
    assert release.check_tag(f"v{release.package_version()}") == release.package_version()


def test_bridge_archive_is_named_by_revision_and_rooted_at_the_mod_folder(tmp_path):
    repo = fake_repo(tmp_path / "repo", revision=9)
    archive = release.bridge_zip(tmp_path / "out", repo)
    assert archive.name == "tf3_companion_bridge-9.zip"
    with zipfile.ZipFile(archive) as z:
        assert sorted(z.namelist()) == ["tf3_companion_bridge/content/bridge.lua", "tf3_companion_bridge/mod.json"]


def test_the_real_bridge_archive_contains_the_mod_files(tmp_path):
    archive = release.bridge_zip(tmp_path)
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
    assert "tf3_companion_bridge/mod.json" in names
    assert any(n.endswith("bridge.script.lua") for n in names)
    assert all(n.startswith("tf3_companion_bridge/") for n in names)


def test_cli_reports_a_mismatch_and_succeeds_on_a_match(capsys):
    assert release.main(["check-tag", "v9.9.9"]) == 1
    assert "does not match" in capsys.readouterr().err
    assert release.main(["check-tag", f"v{release.package_version()}"]) == 0
