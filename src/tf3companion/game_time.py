"""Evidence-bound calendar time. No nominal tick duration is a calendar fallback."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Any, Iterable, Mapping

DAYS_PER_YEAR = 365.25
VERSION = "game-calendar-v1"


def calendar_ordinal(value: Any) -> int | None:
    try:
        if isinstance(value, str):
            return date.fromisoformat(value).toordinal()
        if isinstance(value, Mapping):
            parts = [value[k] for k in ("year", "month", "day")]
            if any(type(v) is not int for v in parts):
                return None
            return date(*parts).toordinal()
    except (ValueError, TypeError, KeyError):
        pass
    return None


@dataclass(frozen=True)
class TimeMeasure:
    value: float | None
    method: str = "unavailable"
    reason: str | None = None
    anchors: tuple[dict[str, Any], ...] = ()
    unit: str = "GAME-YEAR"

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value, "unit": self.unit, "method": self.method,
                "reason": self.reason, "anchors": list(self.anchors)}


@dataclass(frozen=True)
class CalendarEstimate:
    ordinal: float | None
    method: str = "unavailable"
    reason: str | None = None
    anchors: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "method": self.method, "reason": self.reason,
                "anchors": list(self.anchors)}


@dataclass(frozen=True)
class GameCalendarClock:
    anchors: tuple[tuple[float, int], ...]
    context: Mapping[str, Any]
    ambiguous: bool = False
    invalid_dates: bool = False
    unavailable_ticks: tuple[tuple[float, str], ...] = ()

    def __post_init__(self) -> None:
        scope = dict(self.context)
        if "warnings" in scope:
            scope["warnings"] = tuple(scope["warnings"])
        object.__setattr__(self, "context", MappingProxyType(scope))

    @classmethod
    def from_samples(cls, samples: Iterable[Any], *, context: Mapping[str, Any] | None = None) -> GameCalendarClock:
        scope = dict(context or {})
        pairs: dict[float, int] = {}
        ambiguous = bool(scope.get("ambiguous"))
        invalid = False
        unavailable = {}
        identities = set()
        for sample in samples:
            if isinstance(sample, Mapping):
                tick, dated = sample.get("gameTime"), sample.get("date")
                if scope.get("selectedTick") is None or (tick is not None and tick <= scope["selectedTick"]):
                    identities.add(sample.get("saveId"))
                    if scope.get("saveId") is not None and sample.get("saveId") != scope["saveId"]:
                        ambiguous = True
                    if scope.get("branchId") is not None and sample.get("branchId") != scope["branchId"]:
                        ambiguous = True
            else:
                tick, dated = sample[:2]
            if not isinstance(tick, (int, float)) or isinstance(tick, bool) or not math.isfinite(tick):
                continue
            if scope.get("selectedTick") is not None and tick > scope["selectedTick"]:
                continue
            ordinal = calendar_ordinal(dated)
            if ordinal is None:
                invalid |= dated is not None
                unavailable[tick] = "invalid-calendar-date" if dated is not None else "missing-calendar-date"
                continue
            if tick in pairs and pairs[tick] != ordinal:
                ambiguous = True
            pairs[tick] = ordinal
        if len(identities) > 1:
            ambiguous = True
        anchors = tuple(sorted(pairs.items()))
        ambiguous |= any(b[1] < a[1] for a, b in zip(anchors, anchors[1:]))
        return cls(anchors, scope, ambiguous, invalid, tuple(sorted(unavailable.items())))

    def bounded(self, tick: float) -> GameCalendarClock:
        """Reuse compact evidence at/before a historical endpoint, never future anchors."""
        return GameCalendarClock(tuple(a for a in self.anchors if a[0] <= tick),
                                 {**self.context, "selectedTick": tick},
                                 self.ambiguous, self.invalid_dates,
                                 tuple(a for a in self.unavailable_ticks if a[0] <= tick))

    @property
    def time_basis(self) -> dict[str, Any]:
        scope = {k: self.context.get(k) for k in ("saveId", "branchId", "isolation", "selectedTick")}
        scope["isolation"] = scope["isolation"] or "legacy-unverified"
        digest = hashlib.sha256(json.dumps([scope, self.anchors], sort_keys=True).encode()).hexdigest()
        warnings = list(self.context.get("warnings", []))
        if scope["isolation"] == "legacy-unverified":
            warnings.append("Legacy history is unverified; save/branch isolation is not guaranteed.")
        if self.ambiguous:
            warnings.append("Ambiguous timeline: cross-snapshot conversion refused.")
        rates = {(b[0] - a[0]) / (b[1] - a[1]) for a, b in zip(self.anchors, self.anchors[1:]) if b[1] > a[1]}
        if len(rates) > 1:
            warnings.append("Observed tick/calendar rates vary; interpolation is a local estimate.")
        return {"version": VERSION, "daysPerYear": DAYS_PER_YEAR, **scope,
                "anchorHash": digest, "anchorBounds": [self._ref(a) for a in (self.anchors[:1] + self.anchors[-1:])],
                "warnings": warnings}

    @staticmethod
    def _ref(anchor: tuple[float, int]) -> dict[str, Any]:
        return {"gameTime": anchor[0], "date": date.fromordinal(anchor[1]).isoformat()}

    def calendar_at_tick(self, tick: float | None) -> CalendarEstimate:
        if tick is None or not isinstance(tick, (int, float)) or isinstance(tick, bool) or not math.isfinite(tick):
            return CalendarEstimate(None, reason="missing-timestamp")
        if self.context.get("selectedTick") is not None and tick > self.context["selectedTick"]:
            return CalendarEstimate(None, reason="future-timestamp")
        if self.ambiguous:
            return CalendarEstimate(None, reason="ambiguous-timeline")
        for unavailable_tick, reason in self.unavailable_ticks:
            if tick == unavailable_tick:
                return CalendarEstimate(None, reason=reason)
        for anchor in self.anchors:
            if tick == anchor[0]:
                return CalendarEstimate(float(anchor[1]), "calendar-dates", anchors=(self._ref(anchor),))
        if not self.anchors:
            return CalendarEstimate(None, reason="invalid-calendar-date" if self.invalid_dates else "missing-calendar-date")
        if tick < self.anchors[0][0] or tick > self.anchors[-1][0]:
            return CalendarEstimate(None, reason="outside-observed-calendar")
        from bisect import bisect_left, bisect_right
        ticks = tuple(a[0] for a in self.anchors)
        days = tuple(a[1] for a in self.anchors)
        right = bisect_right(ticks, tick)
        best = None
        for a in self.anchors[:bisect_left(ticks, tick)]:
            index = max(right, bisect_left(days, a[1] + 7))
            if index >= len(self.anchors):
                continue
            b = self.anchors[index]
            candidate = (b[0] - a[0], a[0], b[0], a, b)
            if best is None or candidate[:3] < best[:3]:
                best = candidate
        if best is None:
            return CalendarEstimate(None, reason="insufficient-calendar-span")
        a, b = best[3:]
        ordinal = a[1] + (tick - a[0]) * (b[1] - a[1]) / (b[0] - a[0])
        span = b[1] - a[1]
        refs = tuple({**self._ref(anchor), "pairSpanDays": span,
                      "pairTicksPerDay": (b[0] - a[0]) / span} for anchor in (a, b))
        return CalendarEstimate(ordinal, "calendar-interpolation", anchors=refs)

    def elapsed_between_ticks(self, start: float | None, end: float | None) -> TimeMeasure:
        if start is not None and end is not None and start > end:
            return TimeMeasure(None, reason="future-timestamp")
        a, b = self.calendar_at_tick(start), self.calendar_at_tick(end)
        if a.ordinal is None or b.ordinal is None:
            return TimeMeasure(None, reason=a.reason if a.ordinal is None else b.reason)
        anchors = tuple({json.dumps(x, sort_keys=True): x for x in a.anchors + b.anchors}.values())
        method = "calendar-interpolation" if "calendar-interpolation" in (a.method, b.method) else "calendar-dates"
        return TimeMeasure((b.ordinal - a.ordinal) / DAYS_PER_YEAR, method, anchors=anchors)

    def elapsed_between_dates(self, start: Any, end: Any) -> TimeMeasure:
        if self.ambiguous:
            return TimeMeasure(None, reason="ambiguous-timeline")
        a, b = calendar_ordinal(start), calendar_ordinal(end)
        if a is None or b is None:
            return TimeMeasure(None, reason="invalid-calendar-date" if start is not None and end is not None else "missing-calendar-date")
        if b < a:
            return TimeMeasure(None, reason="ambiguous-timeline")
        return TimeMeasure((b - a) / DAYS_PER_YEAR, "calendar-dates")
