"""Load methodology files: size limit, strict UTF-8 JSON, schema check, validation."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any

from .model import (
    FILE_SUFFIX, MAX_BYTES, MAX_JSON_DEPTH, SCHEMA_ID, SCHEMA_MAJOR, SCHEMA_PREFIX, Issue, Methodology,
    MethodologyError, content_hash,
)
from .validate import validate


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"duplicate key '{key}'")
        out[key] = value
    return out


def _reject_constant(name: str) -> Any:
    raise ValueError(f"{name} is not valid JSON")


def _depth(value: Any) -> int:
    deepest, stack = 0, [(value, 1)]
    while stack:
        item, level = stack.pop()
        if isinstance(item, (dict, list)):
            deepest = max(deepest, level)
            if deepest > MAX_JSON_DEPTH:
                return deepest
            stack.extend((child, level + 1) for child in (item.values() if isinstance(item, dict) else item))
    return deepest


def parse(raw: bytes, *, source: str = "file", path: str | None = None, label: str = "") -> Methodology:
    """Parse and validate raw file bytes; raises MethodologyError listing every problem."""
    where = label or path or "methodology"
    if len(raw) > MAX_BYTES:
        raise MethodologyError([Issue("", f"file is {len(raw):,} bytes; the limit is {MAX_BYTES:,}")], where)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MethodologyError([Issue("", f"file is not valid UTF-8: {exc.reason}")], where) from exc
    try:
        data = json.loads(text, object_pairs_hook=_pairs, parse_constant=_reject_constant)
    except (ValueError, RecursionError) as exc:
        raise MethodologyError([Issue("", f"invalid JSON: {exc}")], where) from exc
    if _depth(data) > MAX_JSON_DEPTH:
        raise MethodologyError([Issue("", f"JSON nesting exceeds {MAX_JSON_DEPTH} levels")], where)
    if isinstance(data, dict):
        _check_schema(data, where)
    issues = validate(data)
    if issues:
        raise MethodologyError(issues, where)
    return Methodology(data=data, sha256=content_hash(raw), source=source, path=path, raw=raw)


def _check_schema(data: dict[str, Any], where: str) -> None:
    declared = data.get("schema")
    if not isinstance(declared, str) or not declared.startswith(SCHEMA_PREFIX):
        return  # reported by the validator with the other structural problems
    major = declared[len(SCHEMA_PREFIX):]
    if major != str(SCHEMA_MAJOR):
        raise MethodologyError([Issue("/schema", f"declared schema '{declared}' is not supported; this companion "
                                                 f"supports '{SCHEMA_ID}'. No rule was evaluated.")], where)


def read_file(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise MethodologyError([Issue("", "not a regular file")], str(path))
    size = path.stat().st_size
    if size > MAX_BYTES:
        raise MethodologyError([Issue("", f"file is {size:,} bytes; the limit is {MAX_BYTES:,}")], str(path))
    return path.read_bytes()


def load_file(path: Path, *, source: str = "file") -> Methodology:
    path = Path(path).expanduser()
    return parse(read_file(path), source=source, path=str(path), label=str(path))


# ---------------------------------------------------------------------------
# packaged resources (editable checkout and installed wheel alike)

def _packaged_root():
    return files("tf3companion.methodology")


def packaged_files() -> list[tuple[str, bytes]]:
    """(resource name, bytes) of the packaged default and example methodologies."""
    root = _packaged_root()
    out = [("default.json", root.joinpath("default.json").read_bytes())]
    examples = root.joinpath("examples")
    if examples.is_dir():
        out += sorted((f"examples/{e.name}", e.read_bytes()) for e in examples.iterdir() if e.name.endswith(FILE_SUFFIX))
    return out


def load_packaged(name: str) -> Methodology:
    raw = _packaged_root().joinpath(*name.split("/")).read_bytes()
    return parse(raw, source="packaged", path=f"packaged:{name}", label=f"packaged:{name}")


def load_default() -> Methodology:
    return load_packaged("default.json")


def schema_text() -> str:
    return _packaged_root().joinpath("schema-1.json").read_text(encoding="utf-8")
