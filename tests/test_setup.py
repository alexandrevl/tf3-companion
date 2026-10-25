"""Portable discovery and installer tests use isolated fake game folders only."""

import json
from contextlib import contextmanager

import pytest

from tf3companion import setup_tools
from tf3companion.discovery import ConfigError, discover, discover_userdata
from tf3companion.paths import Paths, load_paths


def game(root, account="123"):
    path = root / "userdata" / account / "3493540" / "local"
    path.mkdir(parents=True)
    return path


@pytest.mark.parametrize(
    "platform,relative",
    [
        ("darwin", "Library/Application Support/Steam"),
        ("linux", ".steam/steam"),
        ("linux", ".local/share/Steam"),
        ("linux", ".var/app/com.valvesoftware.Steam/.local/share/Steam"),
    ],
)
def test_native_and_flatpak_discovery(tmp_path, platform, relative):
    expected = game(tmp_path / relative)
    result = discover(platform=platform, env={}, home=tmp_path)
    assert result.userdata == expected
    assert result.candidates == (expected,)


@pytest.mark.parametrize("registry", [True, False])
def test_windows_registry_and_default(tmp_path, registry):
    root = tmp_path / ("custom-steam" if registry else "program-files/Steam")
    expected = game(root)
    result = discover(
        platform="win32",
        env={
            "ProgramFiles(x86)": str(tmp_path / "program-files"),
            "ProgramFiles": str(tmp_path / "other-program-files"),
        },
        home=tmp_path,
        registry_reader=lambda: str(root) if registry else None,
    )
    assert result.userdata == expected


def test_ambiguity_requires_override(tmp_path):
    root = tmp_path / "Library/Application Support/Steam"
    first, second = game(root, "1"), game(root, "2")
    kwargs = {"platform": "darwin", "env": {}, "home": tmp_path}
    assert discover(**kwargs).userdata is None
    assert set(discover(**kwargs).candidates) == {first, second}
    with pytest.raises(ConfigError):
        discover_userdata(**kwargs)
    assert discover(platform="darwin", home=tmp_path, env={"TF3C_USERDATA_DIR": str(second)}).userdata == second


def test_override_skips_registry_and_rejects_missing_directory(tmp_path):
    def unexpected_registry():
        pytest.fail("override must bypass registry discovery")

    assert (
        discover(
            platform="win32", env={"TF3C_USERDATA_DIR": str(tmp_path)}, registry_reader=unexpected_registry
        ).userdata
        == tmp_path
    )
    assert discover(env={"TF3C_USERDATA_DIR": str(tmp_path / "missing")}).userdata is None


def test_missing_game_reports_all_search_roots(tmp_path):
    result = discover(platform="linux", env={}, home=tmp_path)
    assert result.userdata is None
    assert len(result.steam_roots) == 3
    assert all(str(root) in result.error for root in result.steam_roots)


def test_linux_aliases_do_not_create_false_ambiguity(tmp_path):
    root = tmp_path / ".local/share/Steam"
    expected = game(root)
    alias = tmp_path / ".steam/steam"
    alias.parent.mkdir()
    alias.symlink_to(root, target_is_directory=True)
    assert discover(platform="linux", env={}, home=tmp_path).candidates == (expected,)


@pytest.fixture
def installation(tmp_path, monkeypatch):
    userdata = tmp_path / "game"
    userdata.mkdir()
    paths = Paths(userdata, tmp_path / "data")
    source = tmp_path / "bundled"
    source.mkdir()
    (source / "mod.json").write_text(json.dumps({"revision": 7}))
    (source / "bridge.lua").write_text("return {}")

    @contextmanager
    def bundle():
        yield source

    monkeypatch.setattr(setup_tools, "bundled_mod", bundle)
    return paths, source


def test_install_replaces_only_bridge_and_uninstall_preserves_data(installation):
    paths, source = installation
    target = paths.staging_area / setup_tools.MOD_NAME
    target.mkdir(parents=True)
    (target / "obsolete.lua").write_text("old")
    other = paths.staging_area / "other-mod"
    other.mkdir()
    (other / "file").write_text("keep")
    paths.snapshot_folder.mkdir()
    snapshot = paths.snapshot_folder / "tf3c_snap_0001.lua"
    snapshot.write_text("keep")
    paths.data.mkdir()
    paths.database.write_bytes(b"keep database")
    paths.notes.write_text("keep notes")
    result = setup_tools.install_mod(paths)
    assert result["revision"] == 7
    assert set(p.name for p in target.iterdir()) == set(p.name for p in source.iterdir())
    assert (target / "bridge.lua").read_bytes() == (source / "bridge.lua").read_bytes()
    assert setup_tools.uninstall_mod(paths)["changed"]
    assert not target.exists()
    assert not setup_tools.uninstall_mod(paths)["changed"]
    assert (other / "file").read_text() == snapshot.read_text() == "keep"
    assert paths.database.read_bytes() == b"keep database"
    assert paths.notes.read_text() == "keep notes"


@pytest.mark.parametrize("location", ["staging", "target", "nested", "file"])
@pytest.mark.parametrize("operation", ["install_mod", "uninstall_mod"])
def test_operations_refuse_target_symlinks(installation, tmp_path, location, operation):
    paths, _ = installation
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "precious").write_text("untouched")
    target = paths.staging_area / setup_tools.MOD_NAME
    if location == "staging":
        paths.staging_area.symlink_to(outside, target_is_directory=True)
    elif location == "target":
        paths.staging_area.mkdir()
        target.symlink_to(outside, target_is_directory=True)
    else:
        target.mkdir(parents=True)
        if location == "nested":
            (target / "nested").symlink_to(outside, target_is_directory=True)
        else:
            (target / "linked").symlink_to(outside / "precious")
    with pytest.raises(ConfigError):
        getattr(setup_tools, operation)(paths)
    assert (outside / "precious").read_text() == "untouched"


def test_failed_copy_preserves_existing_install(installation, monkeypatch):
    paths, _ = installation
    target = paths.staging_area / setup_tools.MOD_NAME
    target.mkdir(parents=True)
    (target / "old").write_text("keep")

    def fail_copy(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(setup_tools.shutil, "copytree", fail_copy)
    with pytest.raises(ConfigError):
        setup_tools.install_mod(paths)
    assert (target / "old").read_text() == "keep"
    assert set(p.name for p in paths.staging_area.iterdir()) == {setup_tools.MOD_NAME}


def test_doctor_without_game_never_creates_data(tmp_path, monkeypatch):
    data = tmp_path / "not-created"
    monkeypatch.setenv("TF3C_USERDATA_DIR", str(tmp_path / "absent-game"))
    monkeypatch.setenv("TF3C_DATA_DIR", str(data))
    report = setup_tools.doctor()
    assert report["ok"] is False
    assert report["userdata"] is None
    assert not data.exists()
    assert any(c["name"] == "knowledge" and c["status"] == "ok" for c in report["checks"])


def test_doctor_mod_and_snapshot_details(installation, monkeypatch):
    paths, _ = installation
    monkeypatch.setenv("TF3C_USERDATA_DIR", str(paths.userdata))
    monkeypatch.setenv("TF3C_DATA_DIR", str(paths.data))
    setup_tools.install_mod(paths)
    paths.snapshot_folder.mkdir()
    snapshot = paths.snapshot_folder / "tf3c_snap_0001.lua"
    snapshot.write_text("{}")
    paths.game_log.parent.mkdir()
    paths.game_log.write_text("[tf3c] snapshot written\n")
    report = setup_tools.doctor()
    assert report["ok"]
    assert report["mod"]["revision"] == report["mod"]["bundled_revision"] == 7
    assert report["snapshots"]["count"] == 1
    assert report["snapshots"]["age_seconds"] >= 0
    assert report["game_log"]["bridge_seen"]
    assert not paths.data.exists()


def test_load_paths_keeps_existing_storage_contract(tmp_path, monkeypatch):
    monkeypatch.setenv("TF3C_USERDATA_DIR", str(tmp_path))
    monkeypatch.setenv("TF3C_DATA_DIR", str(tmp_path / "data"))
    paths = load_paths()
    assert paths.database == tmp_path / "data/companion.db"
    assert paths.snapshot_folder == tmp_path / "towns_industries"
    assert paths.request_file == tmp_path / "towns_industries/tf3c_request.lua"
    assert paths.data.is_dir()


def test_install_allows_system_alias_above_configured_game_root(installation, tmp_path):
    paths, _ = installation
    alias = tmp_path / "system-alias"
    alias.symlink_to(paths.userdata.parent, target_is_directory=True)
    aliased_paths = Paths(alias / paths.userdata.name, paths.data)
    setup_tools.install_mod(aliased_paths)
    assert (paths.staging_area / setup_tools.MOD_NAME / "mod.json").is_file()
    setup_tools.uninstall_mod(aliased_paths)
    assert not (paths.staging_area / setup_tools.MOD_NAME).exists()
