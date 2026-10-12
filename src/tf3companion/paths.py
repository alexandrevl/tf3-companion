"""Filesystem locations used by TF3 Companion."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_data_path

from .discovery import ConfigError, TF3_STEAM_APP_ID, discover_userdata


@dataclass(frozen=True)
class Paths:
    userdata: Path
    data: Path

    @property
    def snapshot_folder(self) -> Path:
        return self.userdata / "towns_industries"

    @property
    def request_file(self) -> Path:
        return self.snapshot_folder / "tf3c_request.lua"

    @property
    def staging_area(self) -> Path:
        return self.userdata / "staging_area"

    @property
    def game_log(self) -> Path:
        return self.userdata / "crash_dump" / "stdout.txt"

    @property
    def database(self) -> Path:
        return self.data / "companion.db"

    @property
    def notes(self) -> Path:
        return self.data / "notes.md"


def data_directory() -> Path:
    """Resolve companion storage without creating it (safe for diagnostics)."""
    data_env = os.environ.get("TF3C_DATA_DIR")
    return Path(data_env).expanduser() if data_env else user_data_path("tf3-companion", appauthor=False, roaming=False)


def load_paths() -> Paths:
    userdata = discover_userdata()
    data = data_directory()
    data.mkdir(parents=True, exist_ok=True)
    return Paths(userdata=userdata, data=data)
