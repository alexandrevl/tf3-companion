"""Typed view over a bridge snapshot (see packaged knowledge/snapshot_schema.md)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any

from . import luadata

SUPPORTED_SCHEMA = 1
SNAPSHOT_FILE = re.compile(r"^tf3c_snap_(\d+)\.lua$")


def _list(value: Any) -> list:
    """Lua empty tables decode as []; tolerate dicts produced by sparse tables."""
    if value is None:
        return []
    if isinstance(value, dict):
        return list(value.values())
    return value


@dataclass
class Snapshot:
    raw: dict[str, Any]
    source: str = ""
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.raw, dict) or not isinstance(self.raw.get("meta"), dict):
            raise ValueError("snapshot requires a metadata table")
        meta = self.meta
        schema = meta.get("schemaVersion")
        if type(schema) is not int or schema < 1:
            raise ValueError("snapshot schemaVersion must be a positive integer")
        if schema > SUPPORTED_SCHEMA:
            raise ValueError(f"snapshot schema {schema} is newer than supported schema "
                             f"{SUPPORTED_SCHEMA}; update TF3 Companion.")
        for key in ("gameTime", "yearDuration", "requestId", "year"):
            value = meta.get(key)
            if (key == "gameTime" or value is not None) and (
                type(value) is not int or not 0 <= value <= 2**63 - 1
            ):
                raise ValueError(f"meta.{key} must be a nonnegative 64-bit integer")
        if "saveId" in meta and (not isinstance(meta["saveId"], str) or not meta["saveId"].strip()):
            raise ValueError("meta.saveId must be a nonempty string")
        date = meta.get("date")
        if date is not None and date != [] and date != {}:
            if not isinstance(date, dict) or any(type(date.get(k)) is not int for k in ("year", "month", "day")):
                raise ValueError("meta.date requires integer year, month and day")
            if not (0 <= date["year"] <= 2**63 - 1 and 1 <= date["month"] <= 12 and 1 <= date["day"] <= 31):
                raise ValueError("meta.date year, month or day is out of range")
        for section in ("company", "problems"):
            value = self.raw.get(section)
            if value is not None and value != [] and not isinstance(value, dict):
                raise ValueError(f"{section} must be a table")
        for section in ("lines", "vehicles", "stations", "industries", "towns", "cargos",
                        "models", "stocks", "depots", "catalog", "errors"):
            value = self.raw.get(section)
            if value is not None and not isinstance(value, (list, dict)):
                raise ValueError(f"{section} must be a collection")
            entries = _list(value)
            if section == "errors":
                if any(not isinstance(entry, str) for entry in entries):
                    raise ValueError("errors must contain strings")
                continue
            if any(not isinstance(entry, dict) for entry in entries):
                raise ValueError(f"{section} must contain tables")
            if section in ("lines", "vehicles", "stations", "industries", "towns", "cargos", "models"):
                ids = [entry.get("id") for entry in entries]
                if any(type(id_) is not int or not 0 <= id_ <= 2**63 - 1 for id_ in ids):
                    raise ValueError(f"{section} requires nonnegative integer entity ids")
                if len(set(ids)) != len(ids):
                    raise ValueError(f"{section} contains duplicate entity ids")

    @classmethod
    def from_file(cls, path: Path) -> "Snapshot":
        data = luadata.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"{path.name}: expected a table at top level")
        return cls(raw=data, source=path.name)

    # ---- meta -----------------------------------------------------------------
    @property
    def meta(self) -> dict[str, Any]:
        return self.raw.get("meta") or {}

    @property
    def schema_version(self) -> int | None:
        return self.meta.get("schemaVersion")

    @property
    def game_time(self) -> int:
        return int(self.meta["gameTime"])

    @property
    def year_duration(self) -> int:
        return int(self.meta.get("yearDuration") or 0)

    @property
    def date(self) -> dict[str, int] | None:
        return self.meta.get("date") or None

    @property
    def date_label(self) -> str:
        d = self.date
        if d:
            return f"{d['year']:04d}-{d['month']:02d}-{d['day']:02d}"
        year = self.meta.get("year")
        return str(year) if year else f"t={self.game_time}"

    def age_years(self, game_time: int | None) -> float | None:
        if game_time is None or not self.year_duration:
            return None
        return (self.game_time - game_time) / self.year_duration

    # ---- sections --------------------------------------------------------------
    @property
    def company(self) -> dict[str, Any]:
        return self.raw.get("company") or {}

    @property
    def lines(self) -> list[dict[str, Any]]:
        return _list(self.raw.get("lines"))

    @property
    def vehicles(self) -> list[dict[str, Any]]:
        return _list(self.raw.get("vehicles"))

    @property
    def stations(self) -> list[dict[str, Any]]:
        return _list(self.raw.get("stations"))

    @property
    def industries(self) -> list[dict[str, Any]]:
        return _list(self.raw.get("industries"))

    @property
    def towns(self) -> list[dict[str, Any]]:
        return _list(self.raw.get("towns"))

    @property
    def problems(self) -> dict[str, Any]:
        p = self.raw.get("problems")
        return p if isinstance(p, dict) else {}

    @property
    def errors(self) -> list[str]:
        return _list(self.raw.get("errors"))

    # ---- lookups ---------------------------------------------------------------
    @cached_property
    def cargo_names(self) -> dict[int, str]:
        return {c["id"]: c.get("name") or c.get("res") or str(c["id"]) for c in _list(self.raw.get("cargos"))}

    @cached_property
    def models(self) -> dict[int, dict[str, Any]]:
        return {m["id"]: m for m in _list(self.raw.get("models"))}

    @cached_property
    def lines_by_id(self) -> dict[int, dict[str, Any]]:
        return {line["id"]: line for line in self.lines}

    @cached_property
    def vehicles_by_id(self) -> dict[int, dict[str, Any]]:
        return {v["id"]: v for v in self.vehicles}

    @cached_property
    def industries_by_id(self) -> dict[int, dict[str, Any]]:
        return {i["id"]: i for i in self.industries}

    def cargo(self, cargo_id: int | None) -> str | None:
        if cargo_id is None:
            return None
        return self.cargo_names.get(cargo_id, str(cargo_id))

    def line_vehicles(self, line: dict[str, Any]) -> list[dict[str, Any]]:
        return [self.vehicles_by_id[v] for v in _list(line.get("vehicles")) if v in self.vehicles_by_id]

    @property
    def stocks(self) -> list[dict[str, Any]]:
        return _list(self.raw.get("stocks"))

    @property
    def depots(self) -> list[dict[str, Any]]:
        return _list(self.raw.get("depots"))

    @property
    def catalog(self) -> list[dict[str, Any]]:
        return _list(self.raw.get("catalog"))

    def find_line(self, ref: int | str) -> dict[str, Any] | None:
        """Find a line by entity id or (case-insensitive, partial) name."""
        if isinstance(ref, int) or (isinstance(ref, str) and ref.isdigit()):
            return self.lines_by_id.get(int(ref))
        needle = ref.casefold()
        exact = [line for line in self.lines if (line.get("name") or "").casefold() == needle]
        if exact:
            return exact[0]
        partial = [line for line in self.lines if needle in (line.get("name") or "").casefold()]
        return partial[0] if len(partial) == 1 else None


def snapshot_files(folders: list[Path]) -> list[Path]:
    """Snapshot files across the mod's output folders, oldest game time first."""
    files = {
        p.resolve() for folder in folders if folder.is_dir() for p in folder.iterdir()
        if SNAPSHOT_FILE.match(p.name) and p.is_file() and not p.is_symlink()
    }
    return sorted(files, key=lambda p: (int(SNAPSHOT_FILE.match(p.name).group(1)), str(p)))
