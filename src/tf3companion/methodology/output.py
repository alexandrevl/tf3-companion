"""Report output layout: `<save root>/reports/<game-date>__<methodology-id>@<version>/` (design D12)."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from ..snapshot import Snapshot
from .model import Methodology
from .scope import SaveScope

MANIFEST = "manifest.json"
LATEST = "latest.md"


def game_date(snap: Snapshot) -> str:
    """`YYYY-MM-DD` from the snapshot, or `t<gameTime>` when it carries no calendar date."""
    date = snap.date
    if date:
        return f"{date['year']:04d}-{date['month']:02d}-{date['day']:02d}"
    return f"t{snap.game_time}"


def folder_name(snap: Snapshot, m: Methodology) -> str:
    return f"{game_date(snap)}__{m.id}@{m.version}"


def lens_folder(scope: SaveScope, snap: Snapshot, m: Methodology) -> Path:
    return scope.reports / folder_name(snap, m)


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def manifest_text(manifest: dict[str, Any]) -> str:
    return json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"


def write_bundle(folder: Path, files: dict[str, str], manifest: dict[str, Any]) -> Path:
    """Replace the whole folder atomically: build a temporary sibling, then swap it in.

    An error while building leaves the previous folder untouched.
    """
    folder.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=f".{folder.name}.new-", dir=folder.parent))
    try:
        for name, content in files.items():
            atomic_write(tmp / name, content)
        atomic_write(tmp / MANIFEST, manifest_text({**manifest, "files": sorted([*files, MANIFEST])}))
        old = None
        if folder.exists():
            old = folder.with_name(f".{folder.name}.old-{os.getpid()}")
            os.replace(folder, old)
        try:
            os.replace(tmp, folder)
        except BaseException:
            if old is not None:
                os.replace(old, folder)
            raise
        if old is not None:
            shutil.rmtree(old, ignore_errors=True)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return folder


def add_files(folder: Path, files: dict[str, str], manifest: dict[str, Any]) -> Path:
    """Write individual files (single-kind reports) into a lens folder and merge them into its manifest."""
    folder.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        atomic_write(folder / name, content)
    path = folder / MANIFEST
    try:
        current = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, ValueError):
        current = {}
    names = sorted({*current.get("files", []), *files, MANIFEST})
    atomic_write(path, manifest_text({**current, **manifest, "files": names}))
    return folder
