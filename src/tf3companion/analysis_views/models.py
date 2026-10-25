"""Shared typed values of the analysis views: the operation context, coverage and the one serializer.

Views are frozen dataclasses with tuples for collections. They hold no Store, connection, document,
block or output path. Names stay untrusted display data; unknown numbers are `None` with a stable
reason, never a fabricated zero. `plain()` is the single serializer used at the evaluation boundary.
"""

from __future__ import annotations

import dataclasses
import math
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Mapping

from ..game_time import GameCalendarClock
from ..snapshot import Snapshot

if TYPE_CHECKING:
    from ..methodology.scope import SaveScope
    from ..report_policy import ReportAnalysisContext
    from .bottlenecks import BottlenecksView
    from .expansion import ExpansionView
    from .history import HistoryView
    from .industries import IndustriesView
    from .lines_history import LinesHistoryView
    from .towns import TownsView
    from .vehicle_roi import VehicleRoiView

VIEW_NAMES = ("bottlenecks", "expansion", "lines-history", "history", "industries", "vehicle-roi", "towns")


@dataclass(frozen=True, eq=False)
class EvaluationContext:
    """The prerequisite operation's captured evidence selection, policies and clock for one endpoint.

    Built once from the prepared `Lens`; views never resolve a methodology, a threshold default,
    the latest snapshot or a clock themselves.
    """

    snapshot: Snapshot                         # the selected endpoint, hydrated
    report: "ReportAnalysisContext"            # effective thresholds, report policies and their origins
    clock: GameCalendarClock                   # calendar evidence bounded at the endpoint
    scope: "SaveScope | None" = None
    previous: Snapshot | None = None           # the stored sample before the endpoint, if any

    @property
    def thresholds(self):
        return self.report.thresholds

    @property
    def policies(self):
        return self.report.policies

    @property
    def endpoint(self) -> int:
        return self.snapshot.game_time

    @classmethod
    def from_lens(cls, lens: Any, scope: "SaveScope | None" = None, previous: Snapshot | None = None) -> "EvaluationContext":
        return cls(lens.snapshot, lens.report_context, lens.clock, scope, previous)


@dataclass(frozen=True)
class SampleRef:
    """One stored sample referenced by tick and date label."""

    tick: int
    date: str | None = None


@dataclass(frozen=True)
class Unavailable:
    """A subresult that could not be computed: a stable code plus the evidence that was missing."""

    code: str
    detail: str | None = None
    subject: str | None = None


@dataclass(frozen=True)
class ViewCoverage:
    """What a view actually read and used, and what it could not.

    `eligible` counts stored samples at or before the endpoint that the family may consider; `read`
    counts compact rows streamed; `used` counts samples the algorithm consumed. `hydrated` counts
    full snapshots loaded, bounded by `hydration_limit`. `limits` names the fixed selection bounds
    (existing algorithm constants), never user-chosen query knobs.
    """

    endpoint: SampleRef
    eligible: int = 0
    read: int = 0
    used: int = 0
    hydrated: int = 0
    hydration_limit: int | None = None
    sampled: tuple[SampleRef, ...] = ()
    limits: Mapping[str, Any] = field(default_factory=dict)
    omitted: int = 0
    warnings: tuple[str, ...] = ()
    collection_errors: tuple[str, ...] = ()
    unavailable: tuple[Unavailable, ...] = ()


@dataclass(frozen=True)
class AnalysisViews:
    """The requested views of one evaluation; unrequested families stay None."""

    bottlenecks: "BottlenecksView | None" = None
    expansion: "ExpansionView | None" = None
    lines_history: "LinesHistoryView | None" = None
    history: "HistoryView | None" = None
    industries: "IndustriesView | None" = None
    vehicle_roi: "VehicleRoiView | None" = None
    towns: "TownsView | None" = None

    def to_dict(self) -> dict[str, Any]:
        """Requested views only, keyed by their public names in the fixed family order."""
        return {name: plain(getattr(self, name.replace("-", "_"))) for name in VIEW_NAMES
                if getattr(self, name.replace("-", "_")) is not None}


def camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in rest)


def plain(value: Any) -> Any:
    """JSON-native form of a view value: camelCase keys, lists for tuples, null for non-finite numbers."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {camel(f.name): plain(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, Mapping):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted((plain(v) for v in value), key=repr)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


_NAME = re.compile(r"^[a-z][a-z-]*$")


def select_views(names: Any) -> tuple[str, ...]:
    """Validate a requested selection: closed names, duplicates collapsed, fixed family order."""
    if names is None:
        return ()
    if isinstance(names, str) or not isinstance(names, (list, tuple)):
        raise ValueError(f"views must be a list of names; valid names: {', '.join(VIEW_NAMES)}")
    unknown = [n for n in names if not isinstance(n, str) or n not in VIEW_NAMES]
    if unknown:
        raise ValueError(f"Unknown view {', '.join(repr(n) for n in unknown)}; valid names: {', '.join(VIEW_NAMES)}")
    return tuple(n for n in VIEW_NAMES if n in names)
