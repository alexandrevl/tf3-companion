"""Read-only Steam userdata discovery, independent of the companion database."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

TF3_STEAM_APP_ID = "3493540"


class ConfigError(RuntimeError):
    """An actionable local configuration or installation problem."""


@dataclass(frozen=True)
class Discovery:
    platform: str
    steam_roots: tuple[Path, ...]
    candidates: tuple[Path, ...]
    userdata: Path | None
    error: str | None = None


def _registry_steam_path() -> str | None:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            return winreg.QueryValueEx(key, "SteamPath")[0]
    except (ImportError, OSError):
        return None


def discover(
    *,
    platform: str | None = None,
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
    registry_reader: Callable[[], str | None] | None = None,
) -> Discovery:
    """Inspect candidates without creating folders or silently choosing an account."""
    platform = platform or sys.platform
    env = os.environ if env is None else env
    home = Path.home() if home is None else home
    override = env.get("TF3C_USERDATA_DIR")
    if override:
        path = Path(override).expanduser().absolute()
        error = None if path.is_dir() else f"TF3C_USERDATA_DIR is not an existing directory: {path}"
        return Discovery(platform, (), (path,), path if error is None else None, error)
    roots: list[Path] = []
    if platform == "win32":
        registry = (registry_reader or _registry_steam_path)()
        if registry:
            roots.append(Path(registry))
        roots.extend(
            Path(env.get(key, default)) / "Steam"
            for key, default in (
                ("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                ("ProgramFiles", r"C:\Program Files"),
            )
        )
    elif platform == "darwin":
        roots.append(home / "Library/Application Support/Steam")
    elif platform.startswith("linux"):
        roots.extend(
            (
                home / ".steam/steam",
                home / ".local/share/Steam",
                home / ".var/app/com.valvesoftware.Steam/.local/share/Steam",
            )
        )
    roots = list(dict.fromkeys(p.resolve() for p in roots))
    candidates: list[Path] = []
    for root in roots:
        try:
            candidates.extend(
                p.resolve() for p in (root / "userdata").glob(f"*/{TF3_STEAM_APP_ID}/local") if p.is_dir()
            )
        except OSError as exc:
            return Discovery(
                platform,
                tuple(roots),
                tuple(candidates),
                None,
                f"Cannot inspect Steam userdata at {root}: {exc}; set TF3C_USERDATA_DIR",
            )
    candidates = sorted(set(candidates))
    if len(candidates) == 1:
        return Discovery(platform, tuple(roots), tuple(candidates), candidates[0])
    if candidates:
        error = "Multiple Steam accounts contain TF3 userdata: " + "; ".join(map(str, candidates))
        error += ". Set TF3C_USERDATA_DIR to the intended account's local folder."
    else:
        searched = (
            "; ".join(str(p / "userdata" / "*" / TF3_STEAM_APP_ID / "local") for p in roots)
            or "no supported Steam roots"
        )
        error = f"Transport Fever 3 userdata not found. Searched: {searched}. Launch the game once or set TF3C_USERDATA_DIR."
    return Discovery(platform, tuple(roots), tuple(candidates), None, error)


def discover_userdata(**kwargs) -> Path:
    result = discover(**kwargs)
    if result.userdata is None:
        raise ConfigError(result.error)
    return result.userdata
