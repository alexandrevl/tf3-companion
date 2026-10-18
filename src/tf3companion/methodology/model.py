"""Methodology value objects, limits and shared constants."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Mapping

SCHEMA_PREFIX = "tf3c-methodology/"
SCHEMA_MAJOR = 1
SCHEMA_ID = f"{SCHEMA_PREFIX}{SCHEMA_MAJOR}"
FILE_SUFFIX = ".tf3c-methodology.json"

# Limits (documented in docs/methodologies.md and schema-1.json).
MAX_BYTES = 256 * 1024
MAX_RULES = 200
MAX_ROLES_PER_ENTITY = 20
MAX_TEXT = 2000
MAX_REGEX = 200
MAX_SUBJECT = 200
MAX_DEPTH = 12          # condition nesting, references included
MAX_JSON_DEPTH = 40     # raw JSON nesting
MAX_UNBOUNDED_QUANTIFIERS = 3

ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
VERSION_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
IDENT_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
MAX_ID = 64

ENTITIES = ("line", "vehicle", "stop", "industry", "stock", "town")
ROLE_ENTITIES = ("line", "vehicle", "industry", "stock", "town")
CARRIERS = ("ROAD", "RAIL", "TRAM", "WATER", "AIR")
SEVERITIES = ("high", "medium", "low")
OPS = ("eq", "ne", "lt", "le", "gt", "ge", "in", "not_in", "matches", "contains_any", "exists", "missing")
FORMATS = ("money", "pct", "int", "km", "years", "text")
AGGREGATES = ("sum", "count", "distinct_count", "min", "max", "ratio")
CHART_TYPES = ("bar", "pie", "history_line")
CHART_AGGS = ("sum", "count", "mean", "min", "max")

UNCLASSIFIED = "unclassified"


@dataclass(frozen=True)
class Issue:
    """One validation problem with a JSON-pointer-like location."""

    path: str
    message: str
    category: str = "structure"
    code: str = "invalid-structure"
    severity: str = "error"
    itemKind: str | None = None
    itemId: str | None = None
    ruleId: str | None = None
    hint: str | None = None
    line: int | None = None
    column: int | None = None
    relatedPaths: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        from dataclasses import asdict
        value = asdict(self)
        value["relatedPaths"] = list(self.relatedPaths)
        return value

    def __str__(self) -> str:
        return f"{self.path or '/'}: {self.message}"


class MethodologyError(ValueError):
    """A methodology file is unusable; carries every issue found."""

    def __init__(self, issues: list[Issue], source: str = "") -> None:
        self.issues = issues
        self.source = source
        head = f"{source}: " if source else ""
        super().__init__(head + "; ".join(str(i) for i in issues[:10]) + (f" (+{len(issues) - 10} more)" if len(issues) > 10 else ""))


@dataclass(frozen=True, eq=False)
class Methodology:
    """A validated methodology file: parsed content plus its identity and content hash."""

    data: Mapping[str, Any]
    sha256: str
    source: str = "file"        # packaged | user | file
    path: str | None = None
    raw: bytes = field(default=b"", repr=False)
    selection: Mapping[str, Any] = field(default_factory=dict)
    effective_overrides: Mapping[str, Any] = field(default_factory=dict, repr=False)

    @property
    def id(self) -> str:
        return self.data["id"]

    @property
    def version(self) -> str:
        return self.data["version"]

    @property
    def identity(self) -> str:
        return f"{self.id}@{self.version}"

    @property
    def name(self) -> str:
        return self.data["name"]

    @property
    def short_hash(self) -> str:
        return f"sha256:{self.sha256[:12]}"

    @property
    def parameters(self) -> dict[str, Any]:
        return {k: v["value"] for k, v in (self.data.get("parameters") or {}).items()}

    def provenance(self) -> dict[str, Any]:
        return {"id": self.id, "version": self.version, "identity": self.identity,
                "hash": self.short_hash, "sha256": self.sha256, "source": self.source}


def content_hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def version_key(version: str) -> tuple[int, int, int]:
    major, minor, patch = (int(p) for p in version.split("."))
    return major, minor, patch
