"""Filesystem locations used by TF3 Companion."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_data_path

TF3_STEAM_APP_ID = "3493540"


class ConfigError(RuntimeError):
    pass


def _detect_userdata_dir() -> Path:
    steam_userdata = Path.home() / "Library/Application Support/Steam/userdata"
    candidates = [p for p in steam_userdata.glob(f"*/{TF3_STEAM_APP_ID}/local") if p.is_dir()]
    if not candidates:
        raise ConfigError(
            f"Transport Fever 3 userdata not found under {steam_userdata}; set TF3C_USERDATA_DIR"
        )
    return max(candidates, key=lambda p: p.stat().st_mtime)


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


def load_paths() -> Paths:
    userdata_env = os.environ.get("TF3C_USERDATA_DIR")
    userdata = Path(userdata_env).expanduser() if userdata_env else _detect_userdata_dir()
    data_env = os.environ.get("TF3C_DATA_DIR")
    data = Path(data_env).expanduser() if data_env else user_data_path("tf3-companion", appauthor=False, roaming=False)
    data.mkdir(parents=True, exist_ok=True)
    return Paths(userdata=userdata, data=data)
