"""The methodology library: packaged files plus `<data>/methodologies/`, identity, conflicts, import/export."""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .loader import load_file, packaged_files, parse, read_file
from .model import FILE_SUFFIX, ID_RE, VERSION_RE, Issue, Methodology, MethodologyError, content_hash, version_key

USER_FOLDER = "methodologies"
PACKAGED, USER = "packaged", "user"
REF_RE = re.compile(r"^([a-z0-9]+(?:-[a-z0-9]+)*)(?:@((?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)))?$")
PLACE_HINT = ("Only library ids (`id` or `id@version`) are accepted here. Place the file in the methodologies folder "
              "or import it with `tf3c methodology import <file>`.")


class LibraryError(ValueError):
    """A methodology reference cannot be resolved to exactly one valid file."""


@dataclass
class Entry:
    id: str | None
    version: str | None
    name: str | None
    source: str                    # packaged | user
    file: str                      # display path
    status: str                    # valid | invalid | conflict
    sha256: str | None
    error: str | None = None
    methodology: Methodology | None = None

    @property
    def identity(self) -> str | None:
        return f"{self.id}@{self.version}" if self.id and self.version else None

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "version": self.version, "identity": self.identity, "name": self.name,
                "source": self.source, "file": self.file, "status": self.status,
                "hash": f"sha256:{self.sha256[:12]}" if self.sha256 else None, "error": self.error}


def parse_ref(ref: str) -> tuple[str, str | None]:
    match = REF_RE.match(ref.strip()) if isinstance(ref, str) else None
    if not match:
        raise LibraryError(f"{ref!r} is not a methodology id. {PLACE_HINT}")
    return match.group(1), match.group(2)


def looks_like_path(ref: str) -> bool:
    return os.sep in ref or "/" in ref or ref.endswith(".json") or ref.startswith(("~", "."))


class Library:
    def __init__(self, data_dir: Path) -> None:
        self.directory = Path(data_dir) / USER_FOLDER

    # ---- listing -----------------------------------------------------------------
    def entries(self) -> list[Entry]:
        """All candidate files. Never creates the user folder."""
        found: list[Entry] = []
        for name, raw in packaged_files():
            found.append(self._entry(raw, PACKAGED, f"packaged:{name}", None))
        if self.directory.is_dir():
            for path in sorted(self.directory.iterdir()):
                if path.name.endswith(FILE_SUFFIX) and not path.name.startswith("."):
                    try:
                        raw = read_file(path)
                    except (MethodologyError, OSError) as exc:
                        found.append(Entry(None, None, None, USER, str(path), "invalid", None, str(exc)))
                        continue
                    found.append(self._entry(raw, USER, str(path), path))
        return self._mark_conflicts(found)

    @staticmethod
    def _entry(raw: bytes, source: str, label: str, path: Path | None) -> Entry:
        try:
            m = parse(raw, source=source, path=str(path) if path else label, label=label)
        except MethodologyError as exc:
            ident = _lenient_identity(raw)
            return Entry(ident[0], ident[1], ident[2], source, label, "invalid", content_hash(raw), str(exc))
        return Entry(m.id, m.version, m.name, source, label, "valid", m.sha256, None, m)

    @staticmethod
    def _mark_conflicts(entries: list[Entry]) -> list[Entry]:
        groups: dict[str, list[Entry]] = {}
        for entry in entries:
            if entry.status == "valid":
                groups.setdefault(entry.identity or "", []).append(entry)
        for identity, group in groups.items():
            if len({e.sha256 for e in group}) > 1:
                files = "; ".join(f"{e.file} (sha256:{(e.sha256 or '')[:12]})" for e in group)
                for entry in group:
                    entry.status = "conflict"
                    entry.error = f"{identity} is declared by files with different content: {files}"
        return entries

    # ---- resolution -----------------------------------------------------------------
    def resolve(self, ref: str) -> Methodology:
        """Resolve `id` (highest valid version) or `id@version` to one valid methodology."""
        ident, version = parse_ref(ref)
        candidates = [e for e in self.entries() if e.id == ident and (version is None or e.version == version)]
        usable = [e for e in candidates if e.status in ("valid", "conflict")]
        if not usable:
            invalid = [e for e in candidates if e.status == "invalid"]
            if invalid:
                raise LibraryError(f"Methodology '{ref}' only exists as an invalid file: {invalid[0].file}: {invalid[0].error}")
            known = sorted({e.identity for e in self.entries() if e.identity})
            raise LibraryError(f"Methodology '{ref}' is not in the library. Available: {', '.join(known)}. "
                               f"Import a file with `tf3c methodology import <file>`.")
        best = max(usable, key=lambda e: version_key(e.version or "0.0.0"))
        if best.status == "conflict":
            raise LibraryError(best.error or f"{best.identity} is in conflict")
        assert best.methodology is not None
        return best.methodology

    def load_path(self, path: str) -> Methodology:
        """A one-off file given on the CLI (the user typed the path); not copied into the library."""
        return load_file(Path(path), source="file")

    # ---- import / export ------------------------------------------------------------
    def import_file(self, path: Path, force: bool = False) -> dict[str, Any]:
        m = load_file(Path(path))
        target = self.directory / f"{m.id}@{m.version}{FILE_SUFFIX}"
        for entry in self.entries():
            if entry.status == "invalid" or entry.identity != m.identity or entry.sha256 == m.sha256:
                continue
            if entry.source == PACKAGED:
                raise LibraryError(f"{m.identity} is a packaged methodology with different content "
                                   f"(sha256:{(entry.sha256 or '')[:12]} vs {m.short_hash}); change the id or version.")
            if not force:
                raise LibraryError(f"{m.identity} already exists with different content: library "
                                   f"sha256:{(entry.sha256 or '')[:12]} ({entry.file}), new file {m.short_hash}. "
                                   "Bump the version or re-run with --force to replace it.")
        self.directory.mkdir(parents=True, exist_ok=True)
        existed = target.is_file()
        _atomic_bytes(target, m.raw)
        return {"identity": m.identity, "hash": m.short_hash, "file": str(target),
                "result": "unchanged" if existed and content_hash(target.read_bytes()) == m.sha256 and not force else "imported"}

    def export(self, ref: str, destination: Path, force: bool = False) -> dict[str, Any]:
        m = self.resolve(ref)
        destination = Path(destination).expanduser()
        if destination.exists() and not force:
            raise LibraryError(f"{destination} already exists; choose another path or pass --force.")
        _atomic_bytes(destination, m.raw)
        return {"identity": m.identity, "hash": m.short_hash, "file": str(destination)}


def _lenient_identity(raw: bytes) -> tuple[str | None, str | None, str | None]:
    """Best-effort id/version/name of an invalid file, for display only."""
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, RecursionError):
        return None, None, None
    if not isinstance(data, dict):
        return None, None, None
    ident, version, name = data.get("id"), data.get("version"), data.get("name")
    return (ident if isinstance(ident, str) and ID_RE.match(ident) else None,
            version if isinstance(version, str) and VERSION_RE.match(version) else None,
            name if isinstance(name, str) else None)


def _atomic_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
