"""Explicit mod installation and read-only diagnostics; no game or database required."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from contextlib import contextmanager
from importlib import resources
from pathlib import Path

from .discovery import ConfigError, discover
from .paths import Paths, data_directory

MOD_NAME = "tf3_companion_bridge"


@contextmanager
def bundled_mod():
    """Use wheel assets first, falling back only to the source checkout."""
    resource = resources.files("tf3companion").joinpath("_mod", MOD_NAME)
    if resource.is_dir():
        with resources.as_file(resource) as path:
            yield path
        return
    source = Path(__file__).resolve().parents[2] / "mod" / MOD_NAME
    if not (source / "mod.json").is_file():
        raise ConfigError("Bundled bridge mod is missing; reinstall TF3 Companion from a complete wheel.")
    yield source


def _revision(path: Path) -> int | None:
    try:
        value = json.loads((path / "mod.json").read_text(encoding="utf-8")).get("revision")
        return value if type(value) is int else None
    except (OSError, ValueError, AttributeError):
        return None


def _unsafe(path: Path) -> bool:
    return path.is_symlink() or path.is_junction()


def _safe_target(paths: Paths) -> Path:
    target = paths.staging_area / MOD_NAME
    # The configured root is trusted; macOS /var and /tmp are system aliases.
    # Reject redirection inside the managed game/mod boundary, not above it.
    for component in (target, paths.staging_area, paths.userdata):
        if _unsafe(component):
            raise ConfigError(f"Refusing mod operation through symlink or junction: {component}")
    if not paths.userdata.is_dir():
        raise ConfigError(f"Game userdata does not exist: {paths.userdata}")
    if paths.staging_area.exists() and not paths.staging_area.is_dir():
        raise ConfigError(f"Mod staging area is not a directory: {paths.staging_area}")
    if target.exists():
        if not target.is_dir():
            raise ConfigError(f"Mod target is not a directory: {target}")
        _safe_tree(target)
    return target


def _safe_tree(path: Path) -> None:
    if _unsafe(path):
        raise ConfigError(f"Refusing symlink or junction in mod folder: {path}")
    for root, directories, files in os.walk(path, followlinks=False):
        for name in directories + files:
            child = Path(root) / name
            if _unsafe(child):
                raise ConfigError(f"Refusing symlink or junction in mod folder: {child}")


def install_mod(paths: Paths) -> dict:
    """Replace only this bridge's staging folder; never alter player data."""
    target = _safe_target(paths)
    try:
        with bundled_mod() as source:
            _safe_tree(source)
            revision = _revision(source)
            if revision is None:
                raise ConfigError("Bundled bridge mod has invalid revision metadata; reinstall the package.")
            paths.staging_area.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix=".tf3c-install-", dir=paths.staging_area, ignore_cleanup_errors=True) as work:
                staged, previous = Path(work) / "new", Path(work) / "previous"
                shutil.copytree(source, staged)
                _safe_target(paths)
                if target.exists():
                    target.rename(previous)
                try:
                    staged.rename(target)
                except OSError:
                    if previous.exists():
                        previous.rename(target)
                    raise
    except OSError as exc:
        raise ConfigError(f"Cannot install bridge mod at {target}: {exc}") from exc
    return {"action": "install", "changed": True, "mod_path": str(target), "revision": revision,
            "next_steps": ["Enable TF3 Companion Bridge in this save's mod list.",
                           "Return to the main menu, reload the save, then save the game."]}


def uninstall_mod(paths: Paths) -> dict:
    """Remove only this bridge; snapshots, history, notes and other mods remain."""
    target = _safe_target(paths)
    changed = target.exists()
    revision = _revision(target) if changed else None
    try:
        if changed:
            shutil.rmtree(target)
    except OSError as exc:
        raise ConfigError(f"Cannot uninstall bridge mod at {target}: {exc}") from exc
    return {"action": "uninstall", "changed": changed, "mod_path": str(target), "revision": revision,
            "next_steps": ["Disable TF3 Companion Bridge in the save's mod list.",
                           "Return to the main menu and reload the save; retained companion data is unchanged."]}


def doctor() -> dict:
    """Return diagnostics without loading Paths, creating storage, or opening SQLite."""
    discovery = discover()
    checks = []

    def check(name, status, detail, fix=None):
        checks.append({"name": name, "status": status, "detail": detail, "fix": fix})

    check("userdata", "ok" if discovery.userdata else "error",
          str(discovery.userdata) if discovery.userdata else discovery.error,
          None if discovery.userdata else "Set TF3C_USERDATA_DIR to the intended existing game local folder.")
    data = data_directory()
    check("data_dir", "ok" if data.is_dir() else "warning", str(data),
          None if data.is_dir() else "Storage is created when a data command is first used.")
    check("save_isolation", "warning", "One companion store is shared across saves; automatic save isolation is not implemented.",
          "Use separate TF3C_DATA_DIR locations for different saves.")
    try:
        with bundled_mod() as source:
            bundled_revision = _revision(source)
        check("bundled_mod", "ok" if bundled_revision is not None else "error",
              f"Bundled revision: {bundled_revision}",
              None if bundled_revision is not None else "Reinstall the companion package.")
    except (ConfigError, OSError) as exc:
        bundled_revision = None
        check("bundled_mod", "error", str(exc), "Reinstall the companion package.")
    knowledge = resources.files("tf3companion").joinpath("knowledge")
    available = knowledge.is_dir() and any(p.name.endswith(".md") for p in knowledge.iterdir())
    check("knowledge", "ok" if available else "error", "Packaged knowledge available" if available else "Packaged knowledge missing",
          None if available else "Reinstall the companion package.")
    mod = {"path": None, "installed": False, "revision": None, "bundled_revision": bundled_revision}
    snapshots = {"count": 0, "latest": None, "age_seconds": None}
    game_log = {"path": None, "exists": False, "bridge_seen": False}
    if discovery.userdata:
        paths = Paths(discovery.userdata, data)
        target = paths.staging_area / MOD_NAME
        mod["path"] = str(target)
        try:
            _safe_target(paths)
            mod["installed"] = target.is_dir()
            mod["revision"] = _revision(target) if mod["installed"] else None
            healthy = mod["installed"] and mod["revision"] == bundled_revision and bundled_revision is not None
            check("installed_mod", "ok" if healthy else "warning", f"Installed revision: {mod['revision']}; bundled: {bundled_revision}",
                  None if healthy else "Run tf3c mod install, enable the mod and reload the save.")
        except (ConfigError, OSError) as exc:
            check("installed_mod", "error", str(exc), "Remove the unsafe link manually before installing the bridge.")
        try:
            files = [p for p in paths.snapshot_folder.glob("tf3c_snap_*.lua") if p.is_file()]
            snapshots["count"] = len(files)
            if files:
                latest = max(files, key=lambda p: p.stat().st_mtime)
                snapshots.update(latest=str(latest), age_seconds=max(0, time.time() - latest.stat().st_mtime))
            check("snapshots", "ok" if files else "warning", f"Snapshot files: {len(files)}; newest age (seconds): {snapshots['age_seconds']}",
                  None if files else "Enable the bridge, load the save and run tf3c refresh.")
        except OSError as exc:
            check("snapshots", "error", str(exc), "Check permissions on the game userdata folder.")
        game_log["path"] = str(paths.game_log)
        try:
            game_log["exists"] = paths.game_log.is_file()
            if game_log["exists"]:
                with paths.game_log.open("rb") as stream:
                    stream.seek(0, os.SEEK_END)
                    stream.seek(max(0, stream.tell() - 262144))
                    recent = stream.read().decode("utf-8", errors="replace").splitlines()[-2000:]
                game_log["bridge_seen"] = any("[tf3c]" in line for line in recent)
            check("game_log", "ok" if game_log["bridge_seen"] else "warning", str(paths.game_log),
                  None if game_log["bridge_seen"] else "Load the save with the bridge enabled and check tf3c log.")
        except OSError as exc:
            check("game_log", "warning", str(exc), "Check log permissions and mod activation.")
    return {"ok": not any(c["status"] == "error" for c in checks), "platform": discovery.platform,
            "steam_roots": list(map(str, discovery.steam_roots)), "userdata_candidates": list(map(str, discovery.candidates)),
            "userdata": str(discovery.userdata) if discovery.userdata else None, "data_dir": str(data),
            "checks": checks, "mod": mod, "snapshots": snapshots, "game_log": game_log, "active_save": None}
